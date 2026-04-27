"""Genome archive — Parquet 永続化基盤 (T015)。

GA Run の個体評価結果を 1 行 = 1 個体 (lane × generation × individual_name)
として buffering し、`flush()` で Parquet に書き出す。横断分析・系譜追跡
（parent_a / parent_b）に使う。

主な公開 API:
    - :data:`GENOMES_SCHEMA` — Parquet schema (33 カラム; T-sharpe Phase 1A で +2、T035 で +3)
    - :class:`GenomeArchive` — 1 Run 分の buffering + flush

仕様:
    - docs/alpha_factory/concepts/genome-archive-schema.md
    - devnotes/20260423-1826-genome-archive-schema/{conceptual,detailed}-design.md

設計上のポイント:
    - **複合主キー** ``(lane_id, generation, individual_name)`` で
      multi-lane (Tier 1 各 instrument + Graduation) の同名個体衝突を防ぐ
    - **monotonic enrich**: 後段 stage による上書きのみ許可、前段への
      逆流は WARN + no-op（``_max_stage_seen`` フィールドで追跡）
    - **4 段伝搬契約**: GENOMES_SCHEMA → ``_create_row_template`` →
      ``collect_stage_*`` → ``flush`` のカラム抜けは import-time assert と
      ``flush`` の last-mile guard で 2 段検証
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, cast

import pyarrow as pa
import pyarrow.parquet as pq
import structlog

from src.alpha_factory.stage_gate import CrossPairResult, StageResult
from src.alpha_factory.statistics import fold_sign_ratio
from src.dsl.genome import Genome
from src.dsl.serialize import genome_to_dict

__all__ = [
    "GENOMES_SCHEMA",
    "GenomeArchive",
]

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Schema definition (28 columns)
# ---------------------------------------------------------------------------

GENOMES_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("run_id", pa.string(), nullable=False),
        pa.field("run_number", pa.int32(), nullable=False),
        pa.field("generation", pa.int32(), nullable=False),
        pa.field("individual_name", pa.string(), nullable=False),
        pa.field("instrument", pa.string(), nullable=False),
        pa.field("lane_id", pa.string(), nullable=False),
        pa.field("parent_a", pa.string(), nullable=True),
        pa.field("parent_b", pa.string(), nullable=True),
        pa.field("genome_json", pa.string(), nullable=False),
        pa.field("fitness_raw", pa.float64(), nullable=False),
        pa.field("fitness_pen", pa.float64(), nullable=False),
        pa.field("stage_a_pass", pa.bool_(), nullable=False),
        pa.field("stage_b_pass", pa.bool_(), nullable=False),
        pa.field("stage_c_pass", pa.bool_(), nullable=False),
        pa.field("trade_count", pa.int32(), nullable=False),
        pa.field("total_pnl", pa.float64(), nullable=False),
        pa.field("sharpe", pa.float64(), nullable=True),
        pa.field("sortino", pa.float64(), nullable=True),
        pa.field("calmar", pa.float64(), nullable=True),
        pa.field("max_drawdown_pct", pa.float64(), nullable=False),
        pa.field("active_clause", pa.int32(), nullable=False),
        pa.field("n_nodes", pa.int32(), nullable=False),
        pa.field("bootstrap_ci_lower", pa.float64(), nullable=True),
        pa.field("bootstrap_ci_upper", pa.float64(), nullable=True),
        pa.field("fold_sign_ratio", pa.float64(), nullable=True),
        pa.field("dsr", pa.float64(), nullable=True),
        pa.field("ii_lite_pass", pa.bool_(), nullable=True),
        pa.field("graduated", pa.bool_(), nullable=False),
        # T-sharpe Phase 1A: trade-level Sharpe (v2) と calc version
        # T044: trade_sharpe_raw は **Stage A 値で固定** (selection 基準と
        # 整合させるため Stage B/C で上書きしない)。Stage B IS sharpe / Stage C
        # base sharpe は trade_sharpe_stage_b / trade_sharpe_stage_c で別保持。
        pa.field("trade_sharpe_raw", pa.float64(), nullable=True),
        pa.field("sharpe_calc_version", pa.string(), nullable=True),
        # T044: stage 別 sharpe (selection と切り離した観測列)
        pa.field("trade_sharpe_stage_b", pa.float64(), nullable=True),
        pa.field("trade_sharpe_stage_c", pa.float64(), nullable=True),
        # T035: Stage B 観察可能性 (n_fold_effective / positive_fold_ratio_effective / reason_codes)
        pa.field("n_fold_effective", pa.int64(), nullable=True),
        pa.field("positive_fold_ratio_effective", pa.float64(), nullable=True),
        pa.field("stage_b_reason_codes", pa.string(), nullable=True),
        # T054: Stage B fold unavailable の排他的 reason 別カウント。
        # JSON 文字列として永続化 (FoldUnavailableReason value → count)。
        # 不変条件: 全 reason の合計 == n_fold_unavailable。
        # 既存 stage_b_reason_codes との後方互換: 追加のみ、既存値は維持。
        pa.field("stage_b_unavailable_reason_counts", pa.string(), nullable=True),
        # T043: live_criteria 4 軸 soft 合算スコア (Stage C base 評価から計算)。
        # 観測指標として archive/report に記録。GA fitness や stage_c.passed には影響しない。
        # 詳細: docs/alpha_factory/mission-score.md
        pa.field("mission_score", pa.float64(), nullable=True),
        # T036: Factor Shadow Plane (FSP) — single instrument 用 diagnostic layer。
        # post-RUN updater (src/alpha_factory/fsp_updater.py) が一括書き戻し。
        # collect_stage_* は触らない (template 初期化時の None のまま flush)。
        # 詳細: docs/alpha_factory/factor-shadow-plane.md /
        # devnotes/20260425-0956-factor-shadow-plane-single-instr/
        pa.field("fsp_runtime_mode", pa.string(), nullable=True),
        pa.field("fsp_sampling_mode", pa.string(), nullable=True),
        pa.field("fsp_factor_set", pa.list_(pa.string()), nullable=True),
        pa.field("fsp_rolling_corr_60d", pa.list_(pa.float64()), nullable=True),
        pa.field("fsp_explained_variance", pa.float64(), nullable=True),
        pa.field("fsp_idio_ratio", pa.float64(), nullable=True),
    ]
)


# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

_STAGE_ORDER: dict[str, int] = {"": 0, "A": 1, "B": 2, "C": 3}
_MAX_STAGE_KEY = "_max_stage_seen"  # row dict 内の private field (Parquet には書かない)


# ---------------------------------------------------------------------------
# Row template (defaults)
# ---------------------------------------------------------------------------


def _create_row_template() -> dict[str, Any]:
    """GENOMES_SCHEMA 全カラムを default 値で初期化した dict を返す。

    nullable -> ``None``、non-null bool -> ``False``、non-null int -> ``0``、
    non-null float -> ``0.0``、non-null string -> ``""`` を入れる。
    呼び出し元（``collect_stage_*``）が必須カラム（``run_id`` / ``generation`` /
    ``individual_name`` / ``instrument`` / ``lane_id`` / ``genome_json``）を
    上書きする。
    """
    return {
        "run_id": "",
        "run_number": 0,
        "generation": 0,
        "individual_name": "",
        "instrument": "",
        "lane_id": "",
        "parent_a": None,
        "parent_b": None,
        "genome_json": "",
        "fitness_raw": 0.0,
        "fitness_pen": 0.0,
        "stage_a_pass": False,
        "stage_b_pass": False,
        "stage_c_pass": False,
        "trade_count": 0,
        "total_pnl": 0.0,
        "sharpe": None,
        "sortino": None,
        "calmar": None,
        "max_drawdown_pct": 0.0,
        "active_clause": 0,
        "n_nodes": 0,
        "bootstrap_ci_lower": None,
        "bootstrap_ci_upper": None,
        "fold_sign_ratio": None,
        "dsr": None,
        "ii_lite_pass": None,
        "graduated": False,
        # T-sharpe Phase 1A
        "trade_sharpe_raw": None,
        "sharpe_calc_version": "v2_trade_level",
        # T044: stage 別 sharpe
        "trade_sharpe_stage_b": None,
        "trade_sharpe_stage_c": None,
        # T035: Stage B 観察可能性
        "n_fold_effective": None,
        "positive_fold_ratio_effective": None,
        "stage_b_reason_codes": None,
        # T054: Stage B fold unavailable reason 別カウント (JSON 文字列)
        "stage_b_unavailable_reason_counts": None,
        # T043: mission_score (Stage C 評価時のみ書き込み、それ以外は None)
        "mission_score": None,
        # T036: FSP — post-RUN updater が一括書き戻し、template は null 初期化のみ
        "fsp_runtime_mode": None,
        "fsp_sampling_mode": None,
        "fsp_factor_set": None,
        "fsp_rolling_corr_60d": None,
        "fsp_explained_variance": None,
        "fsp_idio_ratio": None,
    }


# Import-time guard: template と SCHEMA のカラム名集合が完全一致すること
_TEMPLATE_KEYS = set(_create_row_template().keys())
_SCHEMA_NAMES = set(GENOMES_SCHEMA.names)
assert _TEMPLATE_KEYS == _SCHEMA_NAMES, (
    f"row template / schema mismatch: "
    f"missing={_SCHEMA_NAMES - _TEMPLATE_KEYS}, "
    f"extra={_TEMPLATE_KEYS - _SCHEMA_NAMES}"
)


# ---------------------------------------------------------------------------
# Structural metrics
# ---------------------------------------------------------------------------


def _compute_n_nodes(genome: Genome) -> int:
    """directional + local_gate の signal 合計数を返す（複雑度指標）。"""
    return sum(len(c.directional) + len(c.local_gate) for c in genome.clauses)


def _read_active_clause_from_payload(payload: Mapping[str, object]) -> int:
    """T037: Stage A payload から ``active_clause`` (runtime fired clause idx 数)
    を取り出す。

    payload に key が無い / 非数値 / 負値の場合は 0 (defensive)。
    archive ``active_clause`` 列は non-null int32 契約のため、不明時も 0 で埋める。
    Stage A 経路 (``evaluate_stage_a``) では必ず int を入れる契約 (T037 完了)。
    """
    v = payload.get("active_clause")
    if isinstance(v, bool):
        return 0  # bool は数値として扱わない (archive 規約)
    if isinstance(v, int):
        return v if v >= 0 else 0
    return 0


# ---------------------------------------------------------------------------
# Payload extraction helpers (mypy-safe)
# ---------------------------------------------------------------------------


def _extract_payload(stage_result: StageResult) -> Mapping[str, object]:
    """``StageResult.metrics["payload"]`` を ``Mapping[str, object]`` で返す。

    payload キーが無い・``Mapping`` でない場合は空 dict（defensive）。
    """
    payload_obj = stage_result.metrics.get("payload")
    if isinstance(payload_obj, Mapping):
        return cast(Mapping[str, object], payload_obj)
    return {}


def _opt_float(payload: Mapping[str, object], key: str) -> float | None:
    v = payload.get(key)
    if v is None:
        return None
    if isinstance(v, bool):
        return None  # bool は数値として扱わない
    if isinstance(v, int | float):
        return float(v)
    return None


def _opt_int(payload: Mapping[str, object], key: str) -> int | None:
    v = payload.get(key)
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return int(v)
    if isinstance(v, float):
        return int(v)
    return None


def _required_float(
    payload: Mapping[str, object], key: str, default: float = 0.0
) -> float:
    v = _opt_float(payload, key)
    return v if v is not None else default


def _required_int(
    payload: Mapping[str, object], key: str, default: int = 0
) -> int:
    v = _opt_int(payload, key)
    return v if v is not None else default


def _extract_oos_sharpes(payload: Mapping[str, object]) -> list[float] | None:
    """``payload["oos_sharpes"]`` を ``list[float]`` として取り出す。

    None / 非 list-tuple / 要素に非数値が混ざっている場合は ``None`` を返す。
    """
    v = payload.get("oos_sharpes")
    if v is None:
        return None
    if not isinstance(v, list | tuple):
        return None
    out: list[float] = []
    for x in v:
        if isinstance(x, bool):
            return None
        if isinstance(x, int | float):
            out.append(float(x))
        else:
            return None
    return out


def _extract_cross_pair(
    payload: Mapping[str, object],
) -> tuple[bool, CrossPairResult | None]:
    """``payload["cross_pair"]`` から ``(skipped, result)`` を取り出す。"""
    cp_obj = payload.get("cross_pair")
    if not isinstance(cp_obj, Mapping):
        return True, None
    cp = cast(Mapping[str, object], cp_obj)
    skipped = bool(cp.get("skipped", True))
    result_obj = cp.get("result")
    if isinstance(result_obj, CrossPairResult):
        return skipped, result_obj
    return skipped, None


# ---------------------------------------------------------------------------
# GenomeArchive
# ---------------------------------------------------------------------------


@dataclass
class GenomeArchive:
    """1 Run 分の Genome 評価結果を buffering して Parquet に flush する。

    Attributes:
        run_id: ``run_YYYYMMDD_HHMMSS`` 形式の Run 識別子。
        run_number: 連番。

    Internal:
        _rows: 主キー ``(lane_id, generation, individual_name)`` の dict。
            value は row dict（各 stage の collect で部分更新される）。

    重複 collect ポリシー (monotonic enrich):
        - 新規行 (key 未登録) → template から作成、collect 適用
        - 後段 stage 適用 (`_max_stage_seen` < incoming) → enrich 上書き
        - 同 stage 再 collect → 上書き + WARN ログ
        - 前段 stage 逆流 → 無視 (no-op) + WARN ログ
    """

    run_id: str
    run_number: int

    _rows: dict[tuple[str, int, str], dict[str, Any]] = field(
        default_factory=dict, init=False, repr=False
    )

    DEFAULT_OUTPUT_DIR: ClassVar[Path] = Path(".cache/alpha_factory/runs")

    # ------------------------------------------------------------------
    # Public collect API
    # ------------------------------------------------------------------

    def collect_stage_a(
        self,
        genome: Genome,
        lane_id: str,
        generation: int,
        stage_result: StageResult,
        *,
        instrument: str,
        parent_a: str | None = None,
        parent_b: str | None = None,
    ) -> None:
        """Stage A 評価結果を archive に取り込む。

        ``instrument`` は新規行作成時に必須（Stage A は通常 1 個体の最初の
        evaluation なので row 新規が多い）。
        """
        if stage_result.stage != "A":
            raise ValueError(
                f"collect_stage_a expected stage='A', got {stage_result.stage!r}"
            )
        if not instrument:
            raise ValueError("instrument must be a non-empty string")

        key = (lane_id, generation, genome.name)
        if not self._allow_collect(key, "A"):
            return

        row = self._rows.setdefault(
            key,
            self._new_row(
                generation=generation,
                genome=genome,
                instrument=instrument,
                lane_id=lane_id,
                parent_a=parent_a,
                parent_b=parent_b,
            ),
        )
        payload = _extract_payload(stage_result)
        row["fitness_raw"] = _required_float(payload, "fitness_raw")
        row["fitness_pen"] = _required_float(payload, "fitness_pen")
        row["stage_a_pass"] = bool(stage_result.passed)
        row["trade_count"] = _required_int(payload, "trade_count")
        # T-sharpe Phase 1A: payload key を "sharpe_raw" → "trade_sharpe_raw" にリネーム
        # 旧 archive 互換のため "sharpe" 列は v1 値で残す経路を維持しないが、
        # 既存 schema 順守のため None を入れる (Phase 2 で sharpe 列削除予定)
        row["trade_sharpe_raw"] = _opt_float(payload, "trade_sharpe_raw")
        row["sharpe_calc_version"] = "v2_trade_level"
        row["sharpe"] = None  # v2 archive では legacy sharpe は埋めない
        row["n_nodes"] = _compute_n_nodes(genome)
        # T037: placeholder (常時 0) を撤廃、Stage A payload の runtime fired
        # clause 数を読み取る。`evaluate_stage_a` が必ず int を入れる契約。
        row["active_clause"] = _read_active_clause_from_payload(payload)
        row["genome_json"] = json.dumps(genome_to_dict(genome), sort_keys=True)
        self._mark_stage(row, "A")

    def collect_stage_b(
        self,
        genome: Genome,
        lane_id: str,
        generation: int,
        stage_result: StageResult,
        *,
        instrument: str | None = None,
    ) -> None:
        """Stage B 評価結果を archive に取り込む。

        既存 row への enrich を想定するが、Stage A をスキップして Stage B
        が初回呼び出しになる場合は ``instrument`` 必須。
        """
        if stage_result.stage != "B":
            raise ValueError(
                f"collect_stage_b expected stage='B', got {stage_result.stage!r}"
            )
        key = (lane_id, generation, genome.name)
        if not self._allow_collect(key, "B"):
            return

        if key not in self._rows and not instrument:
            raise ValueError(
                f"instrument is required for new row at {key} (Stage B first)"
            )
        row = self._rows.setdefault(
            key,
            self._new_row(
                generation=generation,
                genome=genome,
                instrument=instrument or "",
                lane_id=lane_id,
            ),
        )
        payload = _extract_payload(stage_result)
        row["stage_b_pass"] = bool(stage_result.passed)

        oos = _extract_oos_sharpes(payload)
        if oos is None or len(oos) == 0:
            row["fold_sign_ratio"] = None
        else:
            row["fold_sign_ratio"] = float(fold_sign_ratio(oos))

        row["dsr"] = _opt_float(payload, "dsr")
        # T035: Stage B 観察可能性メトリクス
        row["n_fold_effective"] = _opt_int(payload, "n_fold_effective")
        row["positive_fold_ratio_effective"] = _opt_float(
            payload, "positive_fold_ratio_effective"
        )
        # T035: reason_codes 永続化 (空タプルなら None、複数は ";" 区切り)
        rc = stage_result.reason_codes
        row["stage_b_reason_codes"] = ";".join(rc) if rc else None
        # T054: 排他的 reason 別カウントを JSON 文字列で永続化
        urc_obj = payload.get("unavailable_reason_counts")
        if isinstance(urc_obj, Mapping) and urc_obj:
            row["stage_b_unavailable_reason_counts"] = json.dumps(
                {str(k): int(v) for k, v in urc_obj.items()},
                sort_keys=True,
            )
        else:
            row["stage_b_unavailable_reason_counts"] = None
        # T044: Stage B の is_full_sharpe を **trade_sharpe_stage_b 専用列** に
        # 書き込む。trade_sharpe_raw は Stage A 値で固定 (selection と整合)。
        # is_full_sharpe / is_full_total_pnl / is_full_trade_count は Stage B
        # 全期間 backtest の集計値で、Stage A 60 日とは別 metric。
        is_sharpe = _opt_float(payload, "is_full_sharpe")
        if is_sharpe is not None:
            row["trade_sharpe_stage_b"] = is_sharpe
        # T044: total_pnl / trade_count は archive 全体の上書き対象から外し、
        # Stage A 値を保持する (Stage B の is_full_total_pnl は別途観測したい
        # 場合は将来 stage 別列で持つ。Phase 0 では Stage A 値で固定)。
        # bootstrap_ci_lower/upper / sortino / calmar は本 TODO スコープ外
        self._mark_stage(row, "B")

    def collect_stage_c(
        self,
        genome: Genome,
        lane_id: str,
        generation: int,
        stage_result: StageResult,
        *,
        instrument: str | None = None,
    ) -> None:
        """Stage C 評価結果を archive に取り込む。

        ``ii_lite_pass`` は ``stage_result.metrics["payload"]["cross_pair"]``
        から導出される（別引数では受け取らない、SSOT を StageResult に統一）。
        """
        if stage_result.stage != "C":
            raise ValueError(
                f"collect_stage_c expected stage='C', got {stage_result.stage!r}"
            )
        key = (lane_id, generation, genome.name)
        if not self._allow_collect(key, "C"):
            return

        if key not in self._rows and not instrument:
            raise ValueError(
                f"instrument is required for new row at {key} (Stage C first)"
            )
        row = self._rows.setdefault(
            key,
            self._new_row(
                generation=generation,
                genome=genome,
                instrument=instrument or "",
                lane_id=lane_id,
            ),
        )
        payload = _extract_payload(stage_result)
        row["stage_c_pass"] = bool(stage_result.passed)

        # T044: Stage C base sharpe を **trade_sharpe_stage_c 専用列** に書き込む。
        # trade_sharpe_raw は Stage A 値で固定 (selection と整合)。
        # 旧 path では Stage C の payload "trade_sharpe_raw" で上書きしていたが、
        # 名前は "trade_sharpe_raw" でも実体は Stage C base 評価値で別 metric。
        sharpe = _opt_float(payload, "trade_sharpe_raw")
        if sharpe is not None:
            row["trade_sharpe_stage_c"] = sharpe
        # T044: total_pnl / trade_count / max_drawdown_pct は Stage A 値を保持。
        # Stage C base 評価値は payload に残るので report が必要なら別出し。
        max_dd_frac = _opt_float(payload, "max_drawdown_frac")
        if max_dd_frac is not None:
            # max_drawdown_pct は Stage A 値で初期化されているが Stage C で
            # 上書きする (live_criteria 評価対象は Stage C 60 日 holdout)。
            # T044 は trade_sharpe_raw の上書き撤廃のみがスコープで、
            # max_drawdown_pct / total_pnl / trade_count は別 TODO 検討事項。
            row["max_drawdown_pct"] = max_dd_frac * 100.0
        total_pnl = _opt_float(payload, "total_pnl")
        if total_pnl is not None:
            row["total_pnl"] = total_pnl
        tc = _opt_int(payload, "trade_count")
        if tc is not None:
            row["trade_count"] = tc

        skipped, cp_result = _extract_cross_pair(payload)
        if skipped or cp_result is None:
            row["ii_lite_pass"] = None
        else:
            row["ii_lite_pass"] = bool(cp_result.passed)
        # T043: mission_score を payload から書き写す (stage_gate 側で計算済)。
        # base 評価が trade を出さず Sharpe=None だった場合は None になる。
        row["mission_score"] = _opt_float(payload, "mission_score")
        self._mark_stage(row, "C")

    def mark_graduated(
        self, lane_id: str, generation: int, individual_name: str
    ) -> None:
        """Tier 1 → Graduation lane への昇格を flag する。

        Raises:
            KeyError: 該当行が無い場合。
        """
        key = (lane_id, generation, individual_name)
        if key not in self._rows:
            raise KeyError(
                f"individual not in archive: lane_id={lane_id!r}, "
                f"generation={generation}, name={individual_name!r}"
            )
        self._rows[key]["graduated"] = True

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def flush(self, output_dir: Path | None = None) -> Path:
        """全 row を Parquet に書き出して path を返す。

        ``output_dir`` 未指定なら ``DEFAULT_OUTPUT_DIR`` (``.cache/alpha_factory/runs/``)。
        """
        out_dir = (
            Path(output_dir) if output_dir is not None else self.DEFAULT_OUTPUT_DIR
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"genomes_{self.run_id}.parquet"

        # last-mile guard: row dict のキー集合が SCHEMA と一致するか検証
        schema_names = set(GENOMES_SCHEMA.names)
        clean_rows: list[dict[str, Any]] = []
        for key, row in self._rows.items():
            cr = {k: v for k, v in row.items() if k != _MAX_STAGE_KEY}
            cr_keys = set(cr.keys())
            if cr_keys != schema_names:
                missing = sorted(schema_names - cr_keys)
                extra = sorted(cr_keys - schema_names)
                raise ValueError(
                    f"row keys mismatch for key={key}: "
                    f"missing={missing} extra={extra}"
                )
            clean_rows.append(cr)

        table = pa.Table.from_pylist(clean_rows, schema=GENOMES_SCHEMA)
        pq.write_table(table, path)
        return path

    @staticmethod
    def load(parquet_path: Path) -> pa.Table:
        """Parquet ファイルを ``pyarrow.Table`` として読み戻す。"""
        return pq.read_table(parquet_path)

    # ------------------------------------------------------------------
    # T-sharpe Phase 1A: canonical Sharpe accessor
    # ------------------------------------------------------------------

    @staticmethod
    def get_trade_sharpe(row: Mapping[str, Any]) -> float | None:
        """v2 archive 行の ``trade_sharpe_raw`` を返す比較用 accessor。

        v1 archive 行（``sharpe_calc_version`` が ``"v2_trade_level"`` 以外）の
        場合は ``ValueError`` を送出して静かな v1/v2 混在を防ぐ。

        Args:
            row: archive 行 (Mapping)。

        Raises:
            ValueError: v1/未知 archive 行に対して呼び出された場合。
        """
        raw_version = row.get("sharpe_calc_version")
        version = "v1_bar_annualized" if raw_version is None else raw_version
        if version != "v2_trade_level":
            raise ValueError(
                f"get_trade_sharpe: sharpe_calc_version={version!r} は v2 専用 "
                f"accessor では読めません。v1 archive との比較は禁止されています。"
            )
        v = row.get("trade_sharpe_raw")
        return float(v) if v is not None else None

    @staticmethod
    def get_legacy_bar_sharpe(row: Mapping[str, Any]) -> float | None:
        """v1 archive 行の bar-level annualized ``sharpe`` を返す閲覧専用 accessor。

        H2 検証など過去 archive の bar-level Sharpe を読む用途専用。
        比較・判定には絶対に使用しない。v2 archive 行に対しては ``ValueError``。

        Args:
            row: archive 行 (Mapping)。

        Raises:
            ValueError: v2 archive 行に対して呼び出された場合。
        """
        raw_version = row.get("sharpe_calc_version")
        version = "v1_bar_annualized" if raw_version is None else raw_version
        if version == "v2_trade_level":
            raise ValueError(
                "get_legacy_bar_sharpe: v2 archive には v1 bar-level Sharpe は"
                "存在しません。"
            )
        v = row.get("sharpe")
        return float(v) if v is not None else None

    # ------------------------------------------------------------------
    # Row snapshot (run_ga.py selection cache 用; T018)
    # ------------------------------------------------------------------

    def get_row_snapshot(
        self, lane_id: str, generation: int, individual_name: str
    ) -> Mapping[str, Any] | None:
        """特定 row の snapshot dict (shallow copy) を返す。

        run_ga.py が GA selection / best 選出 / live_criteria 判定のために
        archive に蓄積された fitness_pen / stage pass / metrics を read-back
        する用途 (T018)。未登録 key は ``None``、内部フィールド
        ``_max_stage_seen`` は除外する。

        Args:
            lane_id: lane 識別子 (``tier1_{instrument}`` or GRADUATION_LANE_ID)。
            generation: 世代番号。
            individual_name: ``genome.name``。

        Returns:
            Schema 準拠の row dict の shallow copy、未登録なら ``None``。
        """
        key = (lane_id, generation, individual_name)
        row = self._rows.get(key)
        if row is None:
            return None
        return {k: v for k, v in row.items() if k != _MAX_STAGE_KEY}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _new_row(
        self,
        *,
        generation: int,
        genome: Genome,
        instrument: str,
        lane_id: str,
        parent_a: str | None = None,
        parent_b: str | None = None,
    ) -> dict[str, Any]:
        row = _create_row_template()
        row["run_id"] = self.run_id
        row["run_number"] = int(self.run_number)
        row["generation"] = int(generation)
        row["individual_name"] = genome.name
        row["instrument"] = instrument
        row["lane_id"] = lane_id
        row["parent_a"] = parent_a
        row["parent_b"] = parent_b
        row[_MAX_STAGE_KEY] = ""
        return row

    def _allow_collect(
        self, key: tuple[str, int, str], incoming: str
    ) -> bool:
        existing = self._rows.get(key)
        if existing is None:
            return True
        prev = str(existing.get(_MAX_STAGE_KEY, ""))
        if _STAGE_ORDER[incoming] < _STAGE_ORDER[prev]:
            logger.warning(
                "archive.stage_regression_ignored",
                lane_id=key[0],
                generation=key[1],
                individual_name=key[2],
                incoming=incoming,
                prev=prev,
            )
            return False
        if _STAGE_ORDER[incoming] == _STAGE_ORDER[prev]:
            logger.warning(
                "archive.same_stage_recollect",
                lane_id=key[0],
                generation=key[1],
                individual_name=key[2],
                stage=incoming,
            )
        return True

    def _mark_stage(self, row: dict[str, Any], incoming: str) -> None:
        prev = str(row.get(_MAX_STAGE_KEY, ""))
        if _STAGE_ORDER[incoming] > _STAGE_ORDER[prev]:
            row[_MAX_STAGE_KEY] = incoming
