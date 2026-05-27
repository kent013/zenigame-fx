"""Alpha Factory GA Run エントリポイント (Phase 2 完全統合、T018).

Phase 2 基盤 (Clause Genome + Stage A/B/C gates + GenomeArchive +
cross-pair shadow + swim-lane manager) を統合した run-ga orchestrator。

フロー:
    1. ``config/alpha_factory/default.yaml`` + CLI overrides → ``AlphaFactoryConfig``
    2. DB から Stage A / Stage B / Stage C holdout の 3 区間 bars を取得
    3. ``LaneManager`` / ``Tier1Lane`` / ``GraduationLane`` 構築
    4. 世代 loop: random/breed → ``lane_manager.run_generation`` (Stage A/B/C +
       archive 4 段伝搬 + graduation 判定) → archive から cache 更新
    5. ``archive.flush()`` で Parquet、``summary.json`` / ``history.json`` /
       ``best_genome.json`` を ``reports/run-reports/run-{N}/`` に書き出し

出力契約 (既存 ``analyze_run.py`` / ``generate_run_report.py`` と互換):
    - summary.json の top-level キー: ``run_id`` / ``run_number`` /
      ``generated_at`` / ``dataset.instrument,start,end,bars`` / ``ga_config`` /
      ``backtest_config`` / ``best.name,fitness,metrics`` / ``live_criteria`` /
      ``population_size`` は **従来通り保持**、新情報は追加キーのみ。
    - ``best.fitness`` / ``history[*].best_fitness`` は有限 Decimal 文字列
      (非有限値は ``"0"`` にフォールバック + ``best.fitness_finite=false``)。

設計根拠:
    - devnotes/20260423-2324-run-ga-full-rewrite/conceptual-design.md
    - devnotes/20260423-2324-run-ga-full-rewrite/conceptual-design-r2.md
    - devnotes/20260423-2324-run-ga-full-rewrite/detailed-design.md
    - devnotes/20260423-2324-run-ga-full-rewrite/detailed-design-r2.md
"""

from __future__ import annotations

import argparse
import json
import math
import numbers
import os
import random
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Literal

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from scripts.alpha_factory.get_latest_run_number import get_latest_run_number
from src.alpha_factory._registry_bridge import build_random_gen_registry
from src.alpha_factory.archive import GenomeArchive
from src.alpha_factory.aux_loader import AuxBundle, build_aux_bundle_from_db
from src.alpha_factory.aux_preflight import (
    HARD_REQUIRED_AUX,
    SOFT_REQUIRED_AUX,
    compute_extended_period,
    preflight_check_aux_data,
)
from src.alpha_factory.calibrate_gate_history import DEFAULT_HISTORY_PATH
from src.alpha_factory.calibrate_state import (
    compute_base_config_hash,
    compute_full_config_hash,
    load_calibrated_threshold,
)
from src.alpha_factory.config import (
    AlphaFactoryConfig,
    BacktestSectionConfig,
    DatasetConfig,
    GAFeasibilityConfig,
    StageWindowsConfig,
    load_config,
)
from src.alpha_factory.diagnostics_collector import DiagnosticsCollector
from src.alpha_factory.diagnostics_sidecar import (
    sidecar_relative_path,
    write_stage_a_provenance,
)
from src.alpha_factory.diagnostics_stage_a_top_fold import (
    stage_a_top_fold_relative_path,
    write_stage_a_top_fold,
)
from src.alpha_factory.epoch_manager import EpochWindow, make_epoch_id
from src.alpha_factory.nsga2_selection import (
    make_selection_seed,
    select_from_pareto_features,
)
from src.alpha_factory.observability import (
    build_default_archive_churn_metric,
    build_default_bypass_ratio_metric,
    build_default_failure_metric,
    build_default_feasible_ratio_metric,
    build_default_inflow_consistency_metric,
    build_default_q_force_recommendation,
    build_default_selection_metric,
    build_default_session_entropy_metric,
    build_run_observability_report,
    compute_ab_divergence_on_b_evaluated,
    serialize_run_observability_report,
)
from src.alpha_factory.parallel_eval import (
    GenomeEvaluator,
    LaneEvalContext,
    MultiPairTrainInputs,
    PreflightPayload,
    measure_peak_rss_mb,
)
from src.alpha_factory.pareto_features import ParetoFeaturesLite
from src.alpha_factory.primitives import (
    RegistryEvaluator,
    clear as _clear_registry,
    ensure_registered,
)
from src.alpha_factory.run_context import RunContext, generate_epoch_id_stub
from src.alpha_factory.schema_contract import (
    CASCADE_CONTRACT_VERSION,
    assert_run_report_v2,
)
from src.alpha_factory.stage_b_inconclusive import is_stage_b_inconclusive
from src.alpha_factory.stage_gate import (
    STAGE_GATE_VERSION,
    _annualize_trade_sharpe,
)
from src.alpha_factory.stage_partition_guard import validate_stage_partition
from src.alpha_factory.swim_lane import (
    GRADUATION_LANE_ID,
    GraduationLane,
    LaneManager,
    Tier1Lane,
)
from src.alpha_factory.walk_forward import (
    compute_max_folds,
    n_unique_dates,
    wf_min_unique_dates,
)
from src.alpha_factory.warmstart import load_warmstart_motifs
from src.backtest.engine import BacktestConfig
from src.broker import InstrumentMeta
from src.db.connection import SessionLocal
from src.db.models import CurrencyPair, PriceBarM1
from src.domain.price import Ohlc, PriceBar
from src.dsl import genome_to_dict
from src.dsl.genome import Genome
from src.ga.operators import crossover, mutate
from src.ga.random_gen import PrimitiveSpec as RandomGenSpec
from src.ga.random_gen import random_genome

logger = structlog.get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "alpha_factory" / "default.yaml"
RUN_REPORTS_DIR = REPO_ROOT / "reports" / "run-reports"
RUN_CACHE_DIR = REPO_ROOT / ".cache" / "alpha_factory" / "runs"

_BARS_PER_DAY = 24 * 60  # M1 bars


# ---------------------------------------------------------------------------
# Internal dataclass / helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LaneBarsBundle:
    """Stage A / B / C の 3 区間 bars + meta."""

    meta: InstrumentMeta
    bars_stage_a: list[PriceBar]
    bars_stage_b: list[PriceBar]
    bars_holdout: list[PriceBar]


@dataclass(frozen=True)
class IndividualCacheEntry:
    """GA selection 用の cache entry (archive 由来).

    T031 RPC Phase 1: ``feasible`` / ``violation_magnitude`` を追加し
    ``selection_score`` 6 要素化 (v2)。
    T045 Stage C Feasibility: ``stage_c_feasible`` (PnL>0 ∧ Sharpe>0) を
    ``feasible`` 直後に挿入し v3 7 要素化。
    T046 v3.1: stage_b_pass を stage_c_feasible より前 (上位) に移動して
    Stage B 整合との両立を確保 (Run-20→21 で観測された B 退行 834→0 の解消)。
    """

    generation: int
    fitness_pen: float
    stage_a_pass: bool
    stage_b_pass: bool
    stage_c_pass: bool
    feasible: bool = True
    violation_magnitude: float = 0.0
    # T045
    stage_c_feasible: bool = True
    # cycle 4 (improve-cycle): pfre >= fold_robust_threshold (default 0.4) を
    # 満たすか。 selection_score 9-tuple で fitness_pen より上位の lex 要素。
    # 詳細: devnotes/20260506-1622-fx-improve-c4/detailed-design.md
    fold_robust: bool = False
    # T091 cycle_phase1 段階 2 (2026-05-09): trade_count_full_dataset を
    # selection feasibility 用に保持。 archive の同名列を _update_cache で
    # 読み込み、 None なら trade_count (Stage A 60d) を fallback。
    # 詳細: devnotes/20260508-1203-stage-b-gate-redesign/detailed-design.md
    trade_count_full_dataset: int | None = None
    # T112: NSGA-II selection 用 Stage B pooled fold-CV Pareto 軸 (archive 由来)。
    # nsga2_selection_enabled=True 時のみ _breed_next_gen が消費。default OFF では
    # selection_score (lex 10-tuple) に一切寄与せず bit-exact。
    pareto_net_pnl: float | None = None
    pareto_pooled_dd: float | None = None
    pareto_mission_inf_gap: float | None = None
    pareto_axis_usable: bool = False
    # T115: cross-pair 実測シグナル (archive cross_pair_aggregate_fitness 由来)。
    # cross_pair.selection_pressure=True 時のみ _selection_key が tie-break に消費。
    # default OFF では selection_score (10-tuple) に一切寄与せず bit-exact。None は
    # cross-pair 未実行 (enable=False / skipped)。
    cross_pair_margin: float | None = None
    # cycle26 (D): anti-overfit 連続値スコア (archive fold 統計由来、[0,1])。
    # ga.robust_selection_enabled=True 時のみ _selection_key が fold_robust と
    # fitness_pen の間 (cross_pair_margin より上位) に挿入。default OFF では
    # selection_score (10-tuple) に一切寄与せず bit-exact。None は fold 統計欠損
    # (= selection 上不利 -inf 扱い、 pass 整合)。
    robust_score: float | None = None

    @property
    def selection_score(self) -> tuple[int, float, int, int, int, int, int, int, int, float]:
        """Lexicographic 10-tuple v3.3 (cycle 5 で 9→10 要素化):
        ``(feasible, -violation, stage_b_pass_and_feasible, stage_b_pass,
        stage_c_feasible, C_pass, B_pass, A_pass, fold_robust, fitness_pen)``.

        cycle 5: ``stage_b_pass_and_feasible`` (3 要素目) を昇格。
        Stage B pass かつ entry_count adequate (= feasible) 個体を最優先化し、
        cycle 4 で観測された「Stage B pass だが trade_count<50 (entry_count_min 不達)」
        個体支配を解消する (analyze-codex 推奨 D')。

        cycle 4: ``fold_robust`` (9 要素目) を fitness_pen より上位に維持。

        T046: stage_b_pass (4 要素目) を stage_c_feasible より前に置き
        「Stage B 整合 + 単期間 PnL/Sharpe 正」の両立を構造的に保証。

        非有限値 (NaN/inf) は順序比較を破壊するため finite guard で正規化:
        - violation: 非有限なら ``+inf`` 扱い (= ``-inf`` を要素 2 に置く → 最下位)
        - fitness_pen: 非有限は ``-inf`` として比較最下位扱い
        """
        v = self.violation_magnitude
        v_norm = math.inf if not math.isfinite(v) else float(v)
        fp = self.fitness_pen
        fp_norm = -math.inf if not math.isfinite(fp) else float(fp)
        stage_b_pass_and_feasible = bool(self.stage_b_pass) and bool(self.feasible)
        return (
            int(self.feasible),
            -v_norm,
            int(stage_b_pass_and_feasible),  # cycle 5: NEW、 真の Stage B pass を最優先化
            int(self.stage_b_pass),  # T046: Stage B 整合 priority
            int(self.stage_c_feasible),
            int(self.stage_c_pass),
            int(self.stage_b_pass),
            int(self.stage_a_pass),
            int(self.fold_robust),  # cycle 4: fold_robust を fitness_pen より上位に
            fp_norm,
        )

    @property
    def _legacy_selection_score(self) -> tuple[int, int, int, float]:
        """旧 4 要素 selection_score (fallback / v1 互換用)."""
        fp = self.fitness_pen if math.isfinite(self.fitness_pen) else -math.inf
        return (
            int(self.stage_c_pass),
            int(self.stage_b_pass),
            int(self.stage_a_pass),
            fp,
        )


def _compute_robust_score(
    row: Mapping[str, Any],
    *,
    w_pfre: float,
    w_sign: float,
    w_disp: float,
) -> float | None:
    """cycle26 (D): fold-CV 安定性の連続値 robust_score を archive row から算出.

    ``robust_score = w_pfre*pfre + w_sign*(1-fold_sign_ratio)
                     + w_disp*(1-norm_iqr)`` を [0,1] に clip。
    - ``pfre`` = positive_fold_ratio_effective (fold の正 sharpe 比率、高=一貫)。
    - ``fold_sign_ratio`` = 符号反転比率 (低=方向安定) → (1-ratio)。
    - ``norm_iqr`` = clip(oos_total_pnl_iqr / (|median_oos_total_pnl| + eps), 0, 1)
      (低=fold 間 PnL magnitude 安定) → (1-norm_iqr)。
    holdout 情報は一切不使用 (Stage B fold 統計のみ)。pfre / fold_sign_ratio が欠損なら
    安定性シグナル無しとして ``None`` (selection 上 -inf 扱い)。IQR / median 欠損時は
    分散項のみ中立 0.5 を補完 (符号一貫性シグナルは活かす)。
    """
    pfre = _coerce_optional_float(row.get("positive_fold_ratio_effective"))
    sign_ratio = _coerce_optional_float(row.get("fold_sign_ratio"))
    if pfre is None or sign_ratio is None:
        return None
    iqr = _coerce_optional_float(row.get("oos_total_pnl_iqr"))
    med = _coerce_optional_float(row.get("median_oos_total_pnl"))
    if iqr is not None and med is not None and math.isfinite(iqr) and math.isfinite(med):
        norm_iqr = iqr / (abs(med) + 1e-9)
        norm_iqr = min(1.0, max(0.0, norm_iqr))
        disp_term = 1.0 - norm_iqr
    else:
        # 分散項を中立 0.5 で補完 (n_fold<2 等で IQR 未算出のケース)。
        disp_term = 0.5
    score = (
        w_pfre * pfre
        + w_sign * (1.0 - sign_ratio)
        + w_disp * disp_term
    )
    return min(1.0, max(0.0, float(score)))


def _resolve_robust_selection(cfg: Any) -> tuple[bool, str]:
    """cycle26 (D): anti-overfit 選択圧の effective 判定 (単一 SSOT)。

    nsga2 経路は _selection_key を tie-break に使わないため no-op。
    """
    if not getattr(cfg.ga, "robust_selection_enabled", False):
        return False, "robust_selection_enabled=False"
    if getattr(cfg.ga, "nsga2_selection_enabled", False):
        return False, "nsga2_selection_enabled=True (legacy tournament 経路でないため no-op)"
    return True, "enabled"


def _selection_key(
    entry: IndividualCacheEntry,
    fallback_active: bool,
    *,
    selection_pressure: bool = False,
    margin_threshold: float = 0.0,
    robust_selection: bool = False,
) -> tuple[Any, ...]:
    """selection 用 lexicographic key.

    ``fallback_active=True`` (cache 全体が infeasible) の場合は旧 4 要素に
    フォールバックする。

    T116 (T115 連続値化): ``selection_pressure=True`` 時のみ、selection_score
    (10-tuple) の fold_robust(9 要素目) と fitness_pen(10 要素目) の間に cross-pair
    margin の **連続値** ``cp_val = float(margin) if finite else -inf`` を挿入し
    11-tuple にする (fold_robust より下位・fitness_pen より上位)。T115 の bool
    tie-break (``int(margin>threshold)``) は gen0 飽和で勾配ゼロだったため、連続値で
    pass 閾値方向の勾配を継続付与する。``margin_threshold`` は連続値経路では未使用
    (CrossPairConfig.__post_init__ で !=0.0 を fail-closed)。
    **default (selection_pressure=False) では現行 10-tuple をそのまま返す (bit-exact)**。
    keyword-only 引数化で全呼出経路への thread 漏れを型で防ぐ (Codex Round1 Critical3)。
    """
    if fallback_active:
        return entry._legacy_selection_score
    score = entry.selection_score
    if not selection_pressure and not robust_selection:
        return score
    # fold_robust(index 8) と fitness_pen(index 9) の間に連続値 tie-break を挿入。
    # 優先順位: robust_score (anti-overfit, cycle26) > cross_pair margin (T116) >
    # fitness_pen。いずれも None/NaN/inf は -inf (最下位、シグナルなし個体は不利、
    # pass 整合)。default (両 OFF) は上の早期 return で 10-tuple のまま bit-exact。
    inserts: list[float] = []
    if robust_selection:
        r = entry.robust_score
        inserts.append(
            float(r) if (r is not None and math.isfinite(r)) else -math.inf
        )
    if selection_pressure:
        m = entry.cross_pair_margin
        inserts.append(
            float(m) if (m is not None and math.isfinite(m)) else -math.inf
        )
    return (*score[:9], *inserts, score[9])


def _resolve_cross_pair_selection_pressure(cfg: Any) -> tuple[bool, str]:
    """T115: cross-pair in-loop selection pressure の effective 判定 (単一 SSOT)。

    Codex Round2 [Warning1]: pressure=True でも前提が崩れると no-op になる判定を
    log / summary / selection 呼出で一元化し乖離を防ぐ。

    Returns:
        (effective, reason): effective=True なら selection に圧をかける。
        reason は no-op 理由 (effective=True なら "enabled")。
    """
    cp = cfg.cross_pair
    if not getattr(cp, "selection_pressure", False):
        return False, "selection_pressure=False"
    if not getattr(cp, "enable", False):
        # cross_pair eval が走らず aggregate_fitness が None → 圧が乗らない
        return False, "cross_pair.enable=False (aggregate_fitness 計算されず no-op)"
    if getattr(cfg.ga, "nsga2_selection_enabled", False):
        # NSGA-II 経路は _selection_key を tie-break に使わないため no-op
        return False, "nsga2_selection_enabled=True (legacy tournament 経路でないため no-op)"
    return True, "enabled"


def _is_all_infeasible(
    entries: Iterable[IndividualCacheEntry],
    feasibility_cfg: GAFeasibilityConfig,
) -> bool:
    """cache 全体スコープで全個体 infeasible なら True (fallback 発動条件)."""
    if not feasibility_cfg.enable_fallback_when_all_infeasible:
        return False
    return not any(e.feasible for e in entries)


def _safe_finite(x: float) -> tuple[float, bool]:
    """非有限 (-inf / +inf / nan) を 0.0 に落とす (summary/history の Decimal
    互換保証)."""
    if math.isfinite(x):
        return x, True
    return 0.0, False


def _fitness_to_str(x: float) -> str:
    """fitness float → Decimal 互換文字列 (非有限値は '0' 固定).

    ``Decimal(str(val)).normalize()`` で trailing zero を落とす
    (e.g. "0.0" → "0", "1.50" → "1.5")。
    """
    val, finite = _safe_finite(x)
    if not finite:
        return "0"
    # -0.0 は 0.0 に正規化 (符号 flip で文字列の一貫性を保つ)
    if val == 0.0:
        val = 0.0
    d = Decimal(str(val)).normalize()
    # 指数表記 (E+N) を避けて固定小数点形式にする
    s = f"{d:f}" if "E" in f"{d}" else str(d)
    # trailing zero の残りを除去
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    # "-0" を "0" に
    if s in ("", "-0", "-"):
        return "0"
    return s


# ---------------------------------------------------------------------------
# CLI / config
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Alpha Factory GA run (Phase 2 integration)"
    )
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--run-id", default=None)
    p.add_argument("--instrument", default=None)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--population-size", type=int, default=None)
    p.add_argument("--generations", type=int, default=None)
    p.add_argument("--mutation-rate", type=float, default=None)
    p.add_argument("--crossover-rate", type=float, default=None)
    p.add_argument("--tournament-size", type=int, default=None)
    p.add_argument("--elite-count", type=int, default=None)
    p.add_argument("--max-depth", type=int, default=None)
    p.add_argument(
        "--fitness-metric",
        choices=["total_pnl", "sharpe", "calmar"],
        default=None,
    )
    p.add_argument("--seed", type=int, default=None)
    # T101: warmstart pool (既知 mission/Stage-C 個体を初期集団注入、再現性確保)
    p.add_argument("--warmstart-ratio", type=float, default=None)
    p.add_argument("--warmstart-motif-archive", type=str, default=None)
    # T112: NSGA-II only selection (Stage B pooled fold-CV Pareto 3軸)。
    # 未指定=None で yaml default(False)尊重、 指定で True override。
    p.add_argument(
        "--nsga2-selection", action="store_const", const=True, default=None
    )
    # cycle24: experimental primitive F15 MTFTrendPullback (マルチTF) を母集団へ投入。
    # 未指定=OFF で registry 32本のまま (bit-exact)。指定時のみ register_experimental()。
    p.add_argument(
        "--enable-mtf-primitive", action="store_true", default=False
    )
    # T114: cross-pair (ii-lite) shadow 有効化。未指定=None で yaml default(False)尊重。
    p.add_argument(
        "--cross-pair-enable", action="store_const", const=True, default=None
    )
    # T115: cross-pair in-loop selection pressure。未指定=None で yaml default(False)。
    p.add_argument(
        "--cross-pair-selection-pressure",
        action="store_const", const=True, default=None,
    )
    # cycle26 (D): anti-overfit 選択圧 (fold-CV 安定性連続値を selection tie-break に挿入)。
    # 未指定=None で yaml default(False)尊重、 指定で True override。重み 3 つは
    # 未指定=None で default(0.4/0.3/0.3)。
    p.add_argument(
        "--robust-selection", action="store_const", const=True, default=None
    )
    p.add_argument("--robust-w-pfre", type=float, default=None)
    p.add_argument("--robust-w-sign", type=float, default=None)
    p.add_argument("--robust-w-disp", type=float, default=None)
    # T117: multi-pair training (Stage A fitness を複数ペアで min 集約)。
    # 未指定=None で yaml default(False)。
    p.add_argument(
        "--multi-pair-training", action="store_const", const=True, default=None
    )
    p.add_argument(
        "--multi-pair-pairs", type=str, default=None,
        help="multi-pair training の対象ペア (comma 区切り、target + anchor)。",
    )
    # T118: multi-pair fitness 集約方式。未指定=None で yaml default(min)。
    # cycle 9: min は min-collapse (target 選抜圧消失) → mean で target 信号保持。
    p.add_argument(
        "--multi-pair-aggregate", type=str, default=None,
        choices=["min", "mean"],
        help="multi-pair training の fitness 集約方式 (min|mean)。",
    )
    p.add_argument(
        "--no-report",
        action="store_true",
        help=(
            "reports/run-reports/run-{N}/ への成果物書き出しを skip する。"
            "プロファイル RUN 等で report を汚したくない場合に指定。"
            "archive Parquet と RUN_CACHE_DIR state (.cache/) は常に書く。"
        ),
    )
    # T052: GA 評価並列ワーカー数 (canonical: --max-workers, alias: --workers)
    p.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help=(
            "GA 評価並列ワーカー数 (1 = sequential, 2 以上で multiprocessing.Pool)。"
            "未指定時は YAML config の値を使用 (default 1)。"
        ),
    )
    p.add_argument(
        "--workers",
        type=int,
        default=None,
        dest="workers_alias",
        help="--max-workers のエイリアス (zenigame との表記互換)",
    )
    p.add_argument(
        "--max-tasks-per-child",
        type=int,
        default=None,
        help=(
            "GA 評価 worker のリサイクル間隔 (multiprocessing.Pool の "
            "maxtasksperchild)。worker が指定タスク数を処理したら退役 → "
            "新規 spawn し、断片化した pymalloc アリーナを OS に返却して "
            "per-worker RSS を頭打ちにする。未指定時は "
            "2*population_size//max_workers を自動導出。"
        ),
    )
    p.add_argument(
        "--strict-memory-guard",
        action="store_true",
        help=(
            "max_workers が available_memory ベースの推奨値を超えたら "
            "起動時 fail-fast (autopilot 等で OOM を未然防止)。"
        ),
    )
    # T054: Stage A threshold CLI override (history より優先)
    p.add_argument(
        "--stage-a-threshold",
        type=float,
        default=None,
        help=(
            "Stage A threshold を CLI で明示指定 (history.jsonl override より優先)。"
            "未指定時は (1) history.jsonl の最新適用可能 record (2) config 値 の順で fallback。"
        ),
    )
    # T099 cycle 22 (improve-cycle 2026-05-13): Stage B gate kind opt-in
    p.add_argument(
        "--stage-b-gate-kind",
        choices=["legacy", "profit_safe_pfr"],
        default=None,
        help=(
            "T099 cycle 22: Stage B gate mode を CLI で明示指定 (yaml stage_gate.stage_b.gate_kind"
            " より優先)。 legacy (default)=現行 sign-based (median_oos_sharpe + positive_fold_ratio AND)。"
            " profit_safe_pfr=4 条件 AND (pfr_eff>=0.4 ∧ median_oos_total_pnl>=0 ∧"
            " sum_oos_total_pnl>=0 ∧ n_fold_effective>=20)。 1 RUN smoke 必須。"
            " 詳細: devnotes/20260513-2007-fx-improve/detailed-design.md"
        ),
    )
    # PR4: Stage A fitness mode CLI override (yaml phase4.fitness_mode より優先)
    p.add_argument(
        "--fitness-mode",
        choices=["legacy", "legacy_pnl_smoke"],
        default=None,
        help=(
            "PR4: Stage A fitness mode を CLI で明示指定 (yaml phase4.fitness_mode より"
            "優先)。 未指定時は yaml の値 (default `legacy` = 行動完全不変)。 smoke 検証"
            "時のみ `legacy_pnl_smoke` 指定 (1 RUN smoke 必須、 60-487 分、 baseline "
            "5 RUN median と比較)。 詳細: "
            "devnotes/20260513-1715-todo-pr4-legacy-pnl-smoke/."
        ),
    )
    # T057 Phase 2 Gate C: aux preflight override (dev 用)
    p.add_argument(
        "--allow-aux-missing",
        action="store_true",
        help=(
            "preflight aux data check で hard_missing があっても fail-closed "
            "せず WARN log のみで継続する (dev / smoke test 用)。"
            "production では config strict_aux_required=true を維持し本 flag は外す。"
        ),
    )
    # T091 cycle_phase1 段階 3 (2026-05-09): holdout 長不整合 escape hatch
    p.add_argument(
        "--allow-holdout-short",
        action="store_true",
        help=(
            "stage_partition_guard の holdout 長検証 (config holdout_days vs "
            "実態 calendar span) で fail-closed せず WARN log のみで継続する "
            "(smoke test 専用、 二重 opt-in 必須: 本 flag AND env "
            "ZENIGAME_FX_SMOKE_TEST=1 の両方指定時のみ有効)。 production では "
            "本 flag を外し dataset 期間を延長すること。"
        ),
    )
    args = p.parse_args(argv)
    # alias 統合 (両方指定時は同値でなければエラー)
    if args.max_workers is None and args.workers_alias is not None:
        args.max_workers = args.workers_alias
    elif (
        args.max_workers is not None
        and args.workers_alias is not None
        and args.max_workers != args.workers_alias
    ):
        p.error(
            f"--max-workers ({args.max_workers}) と "
            f"--workers ({args.workers_alias}) が異なる値で指定されました"
        )
    return args


def _args_to_overrides(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "dataset": {
            "instrument": args.instrument,
            "start": args.start,
            "end": args.end,
        },
        "ga": {
            "population_size": args.population_size,
            "generations": args.generations,
            "mutation_rate": args.mutation_rate,
            "crossover_rate": args.crossover_rate,
            "tournament_size": args.tournament_size,
            "elite_count": args.elite_count,
            "max_depth": args.max_depth,
            "fitness_metric": args.fitness_metric,
            "seed": args.seed,
            "max_workers": args.max_workers,
            "max_tasks_per_child": args.max_tasks_per_child,
            "warmstart_ratio": args.warmstart_ratio,
            "warmstart_motif_archive": args.warmstart_motif_archive,
            "nsga2_selection_enabled": args.nsga2_selection,
            # cycle26 (D): anti-overfit 選択圧 override (None なら yaml default 尊重)。
            # getattr 防御 (多 pair override と同パターン、 最小 Namespace test 互換)。
            "robust_selection_enabled": getattr(args, "robust_selection", None),
            "robust_w_pfre": getattr(args, "robust_w_pfre", None),
            "robust_w_sign": getattr(args, "robust_w_sign", None),
            "robust_w_disp": getattr(args, "robust_w_disp", None),
        },
        # PR4: --fitness-mode CLI override (= yaml phase4.fitness_mode より優先)。
        # None なら _build_phase4 が dataclass default を尊重する。
        "phase4": {
            "fitness_mode": args.fitness_mode,
        },
        # T114/T115: cross-pair override (None なら yaml default 尊重)。
        "cross_pair": {
            "enable": args.cross_pair_enable,
            "selection_pressure": args.cross_pair_selection_pressure,
        },
        # T117/T118: multi-pair training override (None なら yaml default 尊重)。
        "multi_pair_training": {
            "enable": getattr(args, "multi_pair_training", None),
            "pairs": (
                [p.strip() for p in args.multi_pair_pairs.split(",") if p.strip()]
                if getattr(args, "multi_pair_pairs", None)
                else None
            ),
            "aggregate": getattr(args, "multi_pair_aggregate", None),
        },
    }


# ---------------------------------------------------------------------------
# Bars loader
# ---------------------------------------------------------------------------


# T106: server-side cursor streaming のバッチサイズ。 1 タスク = 1 row ではなく
# DB → client への row 転送をこの単位でバッファする (psycopg3 server-side cursor)。
# smoke で 5_000 とも比較する (devnotes/20260520-0954-db-load-yield-per/)。
_LOAD_BARS_BATCH_SIZE: Final[int] = 10_000

# T106: PriceBar 構築に必要な列のみ取得する (ORM entity を identity map に
# 載せず、 ロード中の二重保持を回避する)。
_PRICE_BAR_M1_COLUMNS: Final = (
    PriceBarM1.bar_time,
    PriceBarM1.open_bid,
    PriceBarM1.high_bid,
    PriceBarM1.low_bid,
    PriceBarM1.close_bid,
    PriceBarM1.open_ask,
    PriceBarM1.high_ask,
    PriceBarM1.low_ask,
    PriceBarM1.close_ask,
    PriceBarM1.volume,
    PriceBarM1.complete,
)


def _construct_price_bar(
    *,
    pair_name: str,
    bar_time: datetime,
    open_bid: Decimal,
    high_bid: Decimal,
    low_bid: Decimal,
    close_bid: Decimal,
    open_ask: Decimal,
    high_ask: Decimal,
    low_ask: Decimal,
    close_ask: Decimal,
    volume: int,
    complete: bool,
) -> PriceBar:
    """Row tuple / ORM row どちらからでも PriceBar を組み立てる共通関数 (T106)."""
    return PriceBar(
        pair_name=pair_name,
        bar_time=bar_time,
        bid=Ohlc(open=open_bid, high=high_bid, low=low_bid, close=close_bid),
        ask=Ohlc(open=open_ask, high=high_ask, low=low_ask, close=close_ask),
        volume=volume,
        complete=complete,
    )


def _bar_row_to_price_bar(row: PriceBarM1, pair_name: str) -> PriceBar:
    return _construct_price_bar(
        pair_name=pair_name,
        bar_time=row.bar_time,
        open_bid=row.open_bid,
        high_bid=row.high_bid,
        low_bid=row.low_bid,
        close_bid=row.close_bid,
        open_ask=row.open_ask,
        high_ask=row.high_ask,
        low_ask=row.low_ask,
        close_ask=row.close_ask,
        volume=row.volume,
        complete=row.complete,
    )


def _stream_bars(
    session: Session,
    *,
    pair_id: int,
    pair_name: str,
    start: datetime,
    end: datetime,
    batch_size: int = _LOAD_BARS_BATCH_SIZE,
) -> list[PriceBar]:
    """server-side cursor で column tuple を streaming し PriceBar list を構築する (T106).

    実装契約:
      - select は ORM entity ではなく必要列のみ (identity map に載せない =
        caller-owned session を汚さない)
      - ``execution_options(yield_per=batch_size)`` で server-side cursor 経由の
        streaming を発動する (SQLAlchemy 2.x)
      - row は **属性アクセスのみ** で消費する (``row.bar_time`` 等)。
        ``row[0]`` / ``row._mapping`` は使わない (テストダブルを軽量にできる)
      - 途中例外時も ``result.close()`` で cursor を確実に解放する
    """
    stmt = (
        select(*_PRICE_BAR_M1_COLUMNS)
        .where(PriceBarM1.pair_id == pair_id)
        .where(PriceBarM1.bar_time >= start)
        .where(PriceBarM1.bar_time < end)
        .order_by(PriceBarM1.bar_time.asc())
        .execution_options(yield_per=batch_size)
    )
    bars: list[PriceBar] = []
    result = session.execute(stmt)
    try:
        for row in result:
            bars.append(
                _construct_price_bar(
                    pair_name=pair_name,
                    bar_time=row.bar_time,
                    open_bid=row.open_bid,
                    high_bid=row.high_bid,
                    low_bid=row.low_bid,
                    close_bid=row.close_bid,
                    open_ask=row.open_ask,
                    high_ask=row.high_ask,
                    low_ask=row.low_ask,
                    close_ask=row.close_ask,
                    volume=row.volume,
                    complete=row.complete,
                )
            )
    finally:
        result.close()
    return bars


def _log_phase_marker(phase: str, **extra: Any) -> None:
    """main プロセス RSS を phase marker として記録する (T106)."""
    error_type: str | None = None
    try:
        import psutil

        rss_mb = psutil.Process().memory_info().rss / 1024 / 1024
    except Exception as exc:  # psutil 不在 / sandbox 等
        rss_mb = -1.0
        error_type = type(exc).__name__
    logger.info(
        "run_ga.phase_rss_marker",
        phase=phase,
        main_rss_mb=rss_mb,
        error_type=error_type,
        **extra,
    )


def _meta_from_pair(pair: CurrencyPair) -> InstrumentMeta:
    return InstrumentMeta(
        oanda_name=pair.oanda_name,
        base_currency=pair.base_currency,
        quote_currency=pair.quote_currency,
        margin_rate=pair.margin_rate,
        pip_size=InstrumentMeta.default_pip_size_for_quote(pair.quote_currency),
        display_precision=InstrumentMeta.default_display_precision_for_quote(pair.quote_currency),
    )


def _build_multi_pair_train_inputs(
    cfg: AlphaFactoryConfig,
    bt_factory: Callable[[str], BacktestConfig],
) -> MultiPairTrainInputs | None:
    """T117: multi-pair training の anchor 入力を構築 (default None)。

    ``multi_pair_training.enable=True`` 時のみ、target を除く anchor ペアの
    Stage A bars + meta + bt_cfg を ``_load_lane_bars`` (Stage A/B 区間、
    holdout_only でない) でロードし :class:`MultiPairTrainInputs` を返す。
    enable=False は None = 単一ペア現挙動 bit-exact。
    """
    mp = cfg.multi_pair_training
    if not mp.enable:
        return None
    target = cfg.dataset.instrument
    anchors = tuple(p for p in mp.pairs if p != target)
    if not anchors:
        raise RuntimeError(
            "multi_pair_training.enable=True but no anchor pairs distinct from "
            f"target ({target}); pairs={mp.pairs}"
        )
    bars_a_map: dict[str, tuple[PriceBar, ...]] = {}
    meta_map: dict[str, InstrumentMeta] = {}
    bt_cfg_map: dict[str, BacktestConfig] = {}
    for anchor in anchors:
        # T117: anchor は Stage A fitness のみ使用 → holdout 不要 (Codex Warning3)。
        anchor_bundle = _load_lane_bars(
            anchor, cfg.dataset, cfg.stage_windows, require_holdout=False
        )
        bars_a_map[anchor] = tuple(anchor_bundle.bars_stage_a)
        meta_map[anchor] = anchor_bundle.meta
        bt_cfg_map[anchor] = bt_factory(anchor)
    logger.info(
        "run_ga.multi_pair_training.enabled",
        target=target,
        anchors=list(anchors),
        aggregate=mp.aggregate,
        scope=mp.scope,
    )
    return MultiPairTrainInputs(
        anchor_pairs=anchors,
        bars_a_map=bars_a_map,
        meta_map=meta_map,
        bt_cfg_map=bt_cfg_map,
        aggregate=mp.aggregate,
    )


def _load_lane_bars(
    instrument: str,
    dataset: DatasetConfig,
    stage_windows: StageWindowsConfig,
    *,
    require_holdout: bool = True,
) -> LaneBarsBundle:
    """DB から Stage A/B/C の 3 区間 bars + meta を取得する (T087)。

    T117: ``require_holdout=False`` で holdout ロード/fail-closed を省略
    (multi-pair training の anchor は Stage A fitness のみ使用 → holdout 不要、
    I/O・失敗面を削減)。bars_holdout は空 list。

    - Stage A bars = ``[dataset.end - stage_a_window, dataset.end)``
    - Stage B bars = ``[dataset.start, dataset.end - stage_a_window)``
      (T087 で Stage A 期間を時系列上 disjoint に除外)
    - Stage C holdout = ``[dataset.end, dataset.end + holdout_days)``
      取得不能時は **fail-closed (RuntimeError)**。 fallback slice は廃止 (T087)。
    """
    stage_a_n_bars = stage_windows.stage_a_window_days * _BARS_PER_DAY
    with SessionLocal() as session:
        pair = session.scalars(
            select(CurrencyPair).where(CurrencyPair.oanda_name == instrument)
        ).one_or_none()
        if pair is None:
            raise RuntimeError(f"currency_pair for {instrument} not found")
        meta = _meta_from_pair(pair)
        pair_id = pair.id
        _log_phase_marker("after_pair_resolve", instrument=instrument)

        # T106: server-side cursor streaming (ORM entity を経由しない)。
        bars_stage_b_full = _stream_bars(
            session,
            pair_id=pair_id,
            pair_name=instrument,
            start=dataset.start,
            end=dataset.end,
        )
        _log_phase_marker(
            "after_stage_b_full_load",
            instrument=instrument,
            bar_count=len(bars_stage_b_full),
        )
        if not bars_stage_b_full:
            raise RuntimeError(
                f"no bars for {instrument} in "
                f"[{dataset.start}, {dataset.end})"
            )

        holdout_end = dataset.end + timedelta(
            days=stage_windows.stage_c_holdout_days
        )
        if require_holdout:
            bars_holdout = _stream_bars(
                session,
                pair_id=pair_id,
                pair_name=instrument,
                start=dataset.end,
                end=holdout_end,
            )
            _log_phase_marker(
                "after_holdout_load",
                instrument=instrument,
                bar_count=len(bars_holdout),
            )
        else:
            # T117: multi-pair anchor は Stage A fitness のみ → holdout 不要。
            bars_holdout = []

    if require_holdout and not bars_holdout:
        # T087: fallback slice (Stage B 末尾を holdout に再利用) は廃止 (partition
        # guard の disjoint 検証と矛盾するため)。 test fixture は test-only helper で
        # LaneBarsBundle を直接構築する経路に切り替えること。
        raise RuntimeError(
            f"no holdout bars for {instrument} in "
            f"[{dataset.end}, {holdout_end}); "
            f"holdout fetch failed and fallback slice is no longer supported "
            f"(would violate stage partition disjoint contract; T087)"
        )

    # T087: Stage A 期間を bars_stage_b から時系列上 disjoint に除外する。
    # `>=` 判定で disjoint 後の bars_stage_b が空になるケースも同時に検出。
    if stage_a_n_bars >= len(bars_stage_b_full):
        raise RuntimeError(
            f"dataset too short for disjoint stage A/B: "
            f"stage_a_n_bars={stage_a_n_bars} >= "
            f"len(bars_stage_b_full)={len(bars_stage_b_full)} "
            f"(instrument={instrument}, dataset=[{dataset.start}, {dataset.end})). "
            f"Extend dataset or reduce stage_a_window_days."
        )
    bars_stage_a = bars_stage_b_full[-stage_a_n_bars:]
    bars_stage_b = bars_stage_b_full[:-stage_a_n_bars]

    log_payload: dict[str, Any] = {
        "instrument": instrument,
        "stage_a_bar_first": bars_stage_a[0].bar_time.isoformat(),
        "stage_a_bar_last": bars_stage_a[-1].bar_time.isoformat(),
        "stage_a_count": len(bars_stage_a),
        "stage_b_bar_first": bars_stage_b[0].bar_time.isoformat(),
        "stage_b_bar_last": bars_stage_b[-1].bar_time.isoformat(),
        "stage_b_count": len(bars_stage_b),
        "holdout_count": len(bars_holdout),
        "require_holdout": require_holdout,
    }
    if require_holdout:
        log_payload.update(
            holdout_bar_first=bars_holdout[0].bar_time.isoformat(),
            holdout_bar_last=bars_holdout[-1].bar_time.isoformat(),
        )
    logger.info("run_ga.lane_bars_loaded", **log_payload)

    return LaneBarsBundle(
        meta=meta,
        bars_stage_a=bars_stage_a,
        bars_stage_b=bars_stage_b,
        bars_holdout=bars_holdout,
    )


def _load_holdout_only(
    instrument: str,
    dataset: DatasetConfig,
    stage_windows: StageWindowsConfig,
) -> tuple[list[PriceBar], InstrumentMeta]:
    """T114: anchor ペアの holdout 区間 bars + meta のみをロードする (Stage A/B 省略)。

    cross-pair (ii-lite) shadow 評価は anchor ペアの holdout のみ必要なため、
    ``_load_lane_bars`` の Stage A/B ロードを省いた軽量版。holdout 窓は target と
    同一 ``[dataset.end, dataset.end + stage_c_holdout_days)``。

    coverage fail-closed (Codex design-review Round 2 [Warning]): non-empty に
    加え、先頭 >= dataset.end / 末尾 < holdout_end / 単調増加・重複なし を検証。
    短い anchor holdout で ii_lite_pass が誤って計測されるのを防ぐ。
    """
    holdout_end = dataset.end + timedelta(days=stage_windows.stage_c_holdout_days)
    with SessionLocal() as session:
        pair = session.scalars(
            select(CurrencyPair).where(CurrencyPair.oanda_name == instrument)
        ).one_or_none()
        if pair is None:
            raise RuntimeError(
                f"cross-pair anchor currency_pair for {instrument} not found"
            )
        meta = _meta_from_pair(pair)
        bars = _stream_bars(
            session,
            pair_id=pair.id,
            pair_name=instrument,
            start=dataset.end,
            end=holdout_end,
        )
    if not bars:
        raise RuntimeError(
            f"cross-pair anchor {instrument} has no holdout bars in "
            f"[{dataset.end}, {holdout_end})"
        )
    # coverage / 単調性 fail-closed
    if bars[0].bar_time < dataset.end or bars[-1].bar_time >= holdout_end:
        raise RuntimeError(
            f"cross-pair anchor {instrument} holdout out of window: "
            f"first={bars[0].bar_time} last={bars[-1].bar_time} "
            f"expected [{dataset.end}, {holdout_end})"
        )
    prev = None
    for b in bars:
        if prev is not None and b.bar_time <= prev:
            raise RuntimeError(
                f"cross-pair anchor {instrument} holdout not strictly increasing "
                f"(dup/unordered at {b.bar_time})"
            )
        prev = b.bar_time
    logger.info(
        "run_ga.cross_pair_anchor_loaded",
        instrument=instrument,
        bar_count=len(bars),
        holdout_first=bars[0].bar_time.isoformat(),
        holdout_last=bars[-1].bar_time.isoformat(),
    )
    return bars, meta


# ---------------------------------------------------------------------------
# Backtest config factory
# ---------------------------------------------------------------------------


def _make_bt_factory(
    dataset: DatasetConfig, backtest: BacktestSectionConfig
) -> Callable[[str], BacktestConfig]:
    def factory(instrument: str) -> BacktestConfig:
        return BacktestConfig(
            instrument=instrument,
            start=dataset.start,
            end=dataset.end,
            initial_cash=backtest.initial_cash,
            leverage=backtest.leverage,
            max_spread_bps=backtest.max_spread_bps,
            holding_cost_per_day_bps=backtest.holding_cost_per_day_bps,
            session_close_utc_hours=frozenset(backtest.session_close_utc_hours),
            bar_minutes=1,
        )

    return factory


# ---------------------------------------------------------------------------
# Breeding
# ---------------------------------------------------------------------------


def _tournament(
    pop: list[Genome],
    cache: dict[str, IndividualCacheEntry],
    rng: random.Random,
    k: int,
    feasibility_cfg: GAFeasibilityConfig,
    *,
    selection_pressure: bool = False,
    margin_threshold: float = 0.0,
    robust_selection: bool = False,
) -> Genome:
    """``feasibility_cfg`` を見て fallback (cache 全体 infeasible) 判定後に max.

    T115: selection_pressure を _selection_key に thread (default False=現行不変)。
    cycle26: robust_selection も同様に thread (default False=現行不変)。
    """
    sample = rng.sample(pop, k=min(k, len(pop)))
    fallback = _is_all_infeasible(cache.values(), feasibility_cfg)
    return max(
        sample,
        key=lambda g: _selection_key(
            cache[g.name],
            fallback,
            selection_pressure=selection_pressure,
            margin_threshold=margin_threshold,
            robust_selection=robust_selection,
        ),
    )


def _cache_entry_to_pareto_lite(
    entry: IndividualCacheEntry | None,
) -> ParetoFeaturesLite:
    """T112: cache entry の Stage B pooled Pareto 軸を ParetoFeaturesLite へ.

    archive 列が無い / axis_usable=False の個体は unusable sentinel
    (= NSGA-II eligible から除外)。
    """
    if entry is None or not entry.pareto_axis_usable:
        return ParetoFeaturesLite.unusable()
    return ParetoFeaturesLite(
        net_pnl_after_cost=entry.pareto_net_pnl,
        pooled_dd_per_fold_max=entry.pareto_pooled_dd,
        mission_inf_gap=entry.pareto_mission_inf_gap,
        is_feasible_invariant=True,
        pareto_axis_usable=True,
        source_stage="B",
    )


def _breed_nsga2(
    prev_pop: list[Genome],
    cache: dict[str, IndividualCacheEntry],
    ga_cfg: Any,
    registry: dict[str, RandomGenSpec],
    rng: random.Random,
    gen: int,
    run_id: str,
) -> tuple[list[Genome], dict[str, tuple[str | None, str | None]]] | None:
    """T112 (Phase2 step5a): NSGA-II only parent 選抜で次世代を生成.

    Stage B pooled fold-CV Pareto 3軸 (cache 由来) で non-dominated sort + crowding を
    行い、 ``population_size`` 体を crossover/mutate で生成する。elite copy はしない
    (front-1 を parent pool として優先するため、 survivor の二重カウントを避ける)。

    parent 選抜の rng は ``make_selection_seed(run_id, gen)`` で run 跨ぎ deterministic。
    crossover/mutate は GA 主 rng (``rng``) を使う (探索多様性の seed 系統を維持)。

    Returns:
        ``(genomes, provenance)``。eligible (pareto_axis_usable) が 0 のときは ``None``
        を返し、 呼出元が従来 tournament に fallback する。
    """
    features_by_idx: dict[int, ParetoFeaturesLite] = {}
    genome_hash_by_idx: dict[int, str] = {}
    idx_to_genome: dict[int, Genome] = {}
    for i, g in enumerate(prev_pop):
        features_by_idx[i] = _cache_entry_to_pareto_lite(cache.get(g.name))
        genome_hash_by_idx[i] = g.name  # 世代内一意 = deterministic tie-break/dedup
        idx_to_genome[i] = g

    sel_rng = random.Random(make_selection_seed(run_id, gen))
    result = select_from_pareto_features(
        features_by_idx,
        offspring_count=ga_cfg.population_size,
        rng=sel_rng,
        genome_hash_by_idx=genome_hash_by_idx,
    )
    if not result.parent_pairs:
        # eligible 0 (= 全個体 pareto_axis_usable=False) → tournament fallback
        logger.info(
            "run_ga.nsga2_selection.no_eligible_fallback_tournament",
            generation=gen,
            warnings=list(result.sample_size_warnings),
        )
        return None

    next_genomes: list[Genome] = []
    provenance: dict[str, tuple[str | None, str | None]] = {}
    for i1, i2 in result.parent_pairs:
        if len(next_genomes) >= ga_cfg.population_size:
            break
        p1 = idx_to_genome[i1]
        p2 = idx_to_genome[i2]
        # crossover/mutate は GA 主 rng を使用 (legacy 経路と同じ演算子)
        if rng.random() < ga_cfg.crossover_rate:
            c1, _c2 = crossover(p1, p2, rng, max_depth=ga_cfg.max_depth)
        else:
            c1 = p1
        c1 = mutate(
            c1,
            rng,
            ga_cfg.mutation_rate,
            max_clause=ga_cfg.max_clause,
            max_depth=ga_cfg.max_depth,
            registry=registry,
            n_edit_max=ga_cfg.n_edit_max,
        )
        name = f"g{gen}_i{len(next_genomes)}"
        next_genomes.append(replace(c1, name=name))
        provenance[name] = (p1.name, p2.name)
    return next_genomes, provenance


def _breed_next_gen(
    prev_pop: list[Genome],
    cache: dict[str, IndividualCacheEntry],
    ga_cfg: Any,  # GAConfig (from config.py)
    registry: dict[str, RandomGenSpec],
    rng: random.Random,
    gen: int,
    run_id: str = "",
    *,
    selection_pressure: bool = False,
    margin_threshold: float = 0.0,
    robust_selection: bool = False,
) -> tuple[list[Genome], dict[str, tuple[str | None, str | None]]]:
    """次世代 genomes を生成。elite → crossover/mutate で埋める。

    elite 選抜 / tournament いずれも cache 全体スコープで一度だけ fallback 判定し、
    同一規則で sort / max するため、elite と tournament の規則不整合を回避する。

    T112: ``ga_cfg.nsga2_selection_enabled=True`` のとき NSGA-II 経路
    (:func:`_breed_nsga2`) を試行。eligible 0 なら従来 tournament に fallback。
    default False では本分岐に入らず完全 bit-exact。
    """
    if getattr(ga_cfg, "nsga2_selection_enabled", False):
        nsga2_result = _breed_nsga2(
            prev_pop, cache, ga_cfg, registry, rng, gen, run_id
        )
        if nsga2_result is not None:
            return nsga2_result
        # eligible 0: legacy tournament に fall through (warning は _breed_nsga2 内)
    feasibility_cfg = ga_cfg.feasibility
    fallback = _is_all_infeasible(cache.values(), feasibility_cfg)
    sorted_pop = sorted(
        prev_pop,
        key=lambda g: _selection_key(
            cache[g.name],
            fallback,
            selection_pressure=selection_pressure,
            margin_threshold=margin_threshold,
            robust_selection=robust_selection,
        ),
        reverse=True,
    )
    elites = sorted_pop[: ga_cfg.elite_count]
    next_genomes: list[Genome] = []
    provenance: dict[str, tuple[str | None, str | None]] = {}
    for e in elites:
        new_name = f"g{gen}_i{len(next_genomes)}"
        renamed = replace(e, name=new_name)
        next_genomes.append(renamed)
        provenance[new_name] = (e.name, None)
    while len(next_genomes) < ga_cfg.population_size:
        p1 = _tournament(
            prev_pop, cache, rng, ga_cfg.tournament_size, feasibility_cfg,
            selection_pressure=selection_pressure,
            margin_threshold=margin_threshold,
            robust_selection=robust_selection,
        )
        p2 = _tournament(
            prev_pop, cache, rng, ga_cfg.tournament_size, feasibility_cfg,
            selection_pressure=selection_pressure,
            margin_threshold=margin_threshold,
            robust_selection=robust_selection,
        )
        if rng.random() < ga_cfg.crossover_rate:
            c1, c2 = crossover(p1, p2, rng, max_depth=ga_cfg.max_depth)
        else:
            c1, c2 = p1, p2
        c1 = mutate(
            c1,
            rng,
            ga_cfg.mutation_rate,
            max_clause=ga_cfg.max_clause,
            max_depth=ga_cfg.max_depth,
            registry=registry,
            n_edit_max=ga_cfg.n_edit_max,
        )
        c2 = mutate(
            c2,
            rng,
            ga_cfg.mutation_rate,
            max_clause=ga_cfg.max_clause,
            max_depth=ga_cfg.max_depth,
            registry=registry,
            n_edit_max=ga_cfg.n_edit_max,
        )
        name1 = f"g{gen}_i{len(next_genomes)}"
        r1 = replace(c1, name=name1)
        next_genomes.append(r1)
        provenance[name1] = (p1.name, p2.name)
        if len(next_genomes) < ga_cfg.population_size:
            name2 = f"g{gen}_i{len(next_genomes)}"
            r2 = replace(c2, name=name2)
            next_genomes.append(r2)
            provenance[name2] = (p1.name, p2.name)
    return next_genomes, provenance


# ---------------------------------------------------------------------------
# Cache update
# ---------------------------------------------------------------------------


def _coerce_optional_float(value: Any) -> float | None:
    """row dict 値を finite float に正規化する (T112、 Pareto 軸 archive 読込用).

    None / NaN / ±inf / 非数値 / bool / list 等は None に潰す。
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        if hasattr(value, "__len__"):
            return None
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _coerce_optional_int(value: Any) -> int | None:
    """row dict 値を non-negative int に正規化する (T091 段階 2、 2026-05-09).

    棄却条件 (None 返す):
    - None / NaN / pd.NA
    - list / tuple / dict / array (hasattr __len__)
    - bool / np.bool_ (整数値偽装)
    - 非有限値 (inf, -inf)
    - 非整数 float (例: 100.5)
    - 負数 (trade_count は非負前提)

    許容: int, np.int64, 整数値の float (例: 100.0)。
    """
    if value is None:
        return None
    try:
        if hasattr(value, "__len__"):
            return None
    except (TypeError, ValueError):
        return None
    try:
        if value != value:  # NaN
            return None
    except (TypeError, ValueError):
        return None
    if isinstance(value, bool):
        return None
    try:
        import numpy as _np

        if isinstance(value, _np.bool_):
            return None
    except ImportError:
        pass
    try:
        f = float(value)
        if not math.isfinite(f):
            return None
        if not f.is_integer():
            return None
        if f < 0:
            return None
        return int(f)
    except (TypeError, ValueError, OverflowError):
        return None


def _update_cache(
    cache: dict[str, IndividualCacheEntry],
    population: list[Genome],
    archive: GenomeArchive,
    lane_id: str,
    generation: int,
    feasibility_cfg: GAFeasibilityConfig,
    stage_c_feasibility_apply: bool = True,
    fold_robust_threshold: float = 0.4,
    robust_w_pfre: float = 0.4,
    robust_w_sign: float = 0.3,
    robust_w_disp: float = 0.3,
) -> None:
    """archive の row から fitness_pen / stage pass / feasibility を取り出し cache 更新.

    T031: ``feasibility_cfg.apply_from_generation <= generation`` で feasibility を
    実評価。archive 不在 (評価失敗) は明確に infeasible として violation を最大化。
    T045: ``stage_c_feasibility_apply=True`` で archive 行の total_pnl>0 ∧ trade_sharpe_raw>0
    を満たす個体に ``stage_c_feasible=True`` をセット (selection_score v3)。
    T091 段階 2 (2026-05-09): selection feasibility を Stage A 60d trade_count から
    trade_count_full_dataset (Stage A unique + Stage B unique) に切替。 旧 archive
    (新列なし) は trade_count fallback で後方互換維持。
    """
    apply = generation >= feasibility_cfg.apply_from_generation
    entry_min = feasibility_cfg.entry_count_min
    for g in population:
        row = archive.get_row_snapshot(lane_id, generation, g.name)
        if row is None:
            cache[g.name] = IndividualCacheEntry(
                generation=generation,
                fitness_pen=-math.inf,
                stage_a_pass=False,
                stage_b_pass=False,
                stage_c_pass=False,
                feasible=(not apply),
                violation_magnitude=float(entry_min) if apply else 0.0,
                stage_c_feasible=(not stage_c_feasibility_apply),
            )
            continue
        fp_raw = row.get("fitness_pen")
        try:
            fp = float(fp_raw) if fp_raw is not None else -math.inf
        except (TypeError, ValueError):
            fp = -math.inf
        # T091 段階 2: trade_count_full_dataset (Stage A unique + Stage B unique) を
        # selection feasibility に使用。 None / 旧 archive なら trade_count
        # (Stage A 60d) を fallback。
        tc_full = _coerce_optional_int(row.get("trade_count_full_dataset"))
        tc_legacy = _coerce_optional_int(row.get("trade_count"))
        if tc_full is not None:
            trade_count_for_feasibility = tc_full
        elif tc_legacy is not None:
            trade_count_for_feasibility = tc_legacy
        else:
            trade_count_for_feasibility = 0
        if apply:
            feasible = trade_count_for_feasibility >= entry_min
            violation = max(0.0, float(entry_min - trade_count_for_feasibility))
        else:
            feasible = True
            violation = 0.0
        # T045: stage_c_feasible 計算
        if stage_c_feasibility_apply:
            try:
                pnl = float(row.get("total_pnl") or 0.0)
            except (TypeError, ValueError):
                pnl = 0.0
            sharpe_raw = row.get("trade_sharpe_raw")
            try:
                sharpe = (
                    float(sharpe_raw) if sharpe_raw is not None else 0.0
                )
            except (TypeError, ValueError):
                sharpe = 0.0
            stage_c_feasible = (
                math.isfinite(pnl)
                and math.isfinite(sharpe)
                and pnl > 0.0
                and sharpe > 0.0
            )
        else:
            stage_c_feasible = True
        # cycle 4: fold_robust 判定 (pfre >= fold_robust_threshold)
        pfre_raw = row.get("positive_fold_ratio_effective")
        try:
            pfre_val = float(pfre_raw) if pfre_raw is not None else None
        except (TypeError, ValueError):
            pfre_val = None
        fold_robust = bool(
            pfre_val is not None
            and math.isfinite(pfre_val)
            and pfre_val >= fold_robust_threshold
        )
        # T112: Stage B pooled fold-CV Pareto 軸 (NSGA-II selection 用)。
        # archive 列が None / 旧 archive なら axis_usable=False で fallback
        # (= nsga2 経路では eligible から除外、 OFF 経路には無影響)。
        pareto_net = _coerce_optional_float(row.get("pareto_b_net_pnl"))
        pareto_dd = _coerce_optional_float(row.get("pareto_b_pooled_dd"))
        pareto_gap = _coerce_optional_float(row.get("pareto_b_mission_inf_gap"))
        pareto_usable = bool(row.get("pareto_b_axis_usable") is True)
        cache[g.name] = IndividualCacheEntry(
            generation=generation,
            fitness_pen=fp,
            stage_a_pass=bool(row.get("stage_a_pass", False)),
            stage_b_pass=bool(row.get("stage_b_pass", False)),
            stage_c_pass=bool(row.get("stage_c_pass", False)),
            feasible=feasible,
            violation_magnitude=violation,
            stage_c_feasible=stage_c_feasible,
            fold_robust=fold_robust,
            # T091 段階 2 (Codex Round 1 [Warning] 対応): 0 と None の意味混同回避。
            # tc_full が None なら欠損 (旧 archive or 計算失敗)、 0 件なら 0 を保持。
            # replay/report で「欠損 vs 0 件」 を区別可能。
            trade_count_full_dataset=tc_full,
            pareto_net_pnl=pareto_net,
            pareto_pooled_dd=pareto_dd,
            pareto_mission_inf_gap=pareto_gap,
            pareto_axis_usable=pareto_usable,
            # T115: cross-pair 実測シグナル。is not None 明示 (Codex Round1 Critical2:
            # or fallback は 0.0 偽扱い/NaN 真扱いで壊れるため使わない)。
            cross_pair_margin=_coerce_optional_float(
                row.get("cross_pair_aggregate_fitness")
            ),
            # cycle26 (D): anti-overfit robust_score (fold 統計由来、観測値の計算のみ)。
            # robust_selection OFF 時は _selection_key が無視するため bit-exact。
            robust_score=_compute_robust_score(
                row,
                w_pfre=robust_w_pfre,
                w_sign=robust_w_sign,
                w_disp=robust_w_disp,
            ),
        )


def _select_best(
    cache: Mapping[str, IndividualCacheEntry],
    feasibility_cfg: GAFeasibilityConfig,
    *,
    selection_pressure: bool = False,
    margin_threshold: float = 0.0,
    robust_selection: bool = False,
) -> tuple[str, IndividualCacheEntry]:
    if not cache:
        raise RuntimeError("no individuals evaluated")
    fallback = _is_all_infeasible(cache.values(), feasibility_cfg)
    return max(
        cache.items(),
        key=lambda kv: _selection_key(
            kv[1],
            fallback,
            selection_pressure=selection_pressure,
            margin_threshold=margin_threshold,
            robust_selection=robust_selection,
        ),
    )


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------


def _coerce_n_fold_effective(value: object) -> int | None:
    """T087: archive row の n_fold_effective を summary 用に整数 or None へ正規化。

    is_stage_b_inconclusive と同じ型防御 (Integral 以外 / NaN / bool は None)
    で、 summary 生成時の ``int(...)`` 失敗による report 落下を防ぐ。
    """
    import math
    from numbers import Integral

    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if not isinstance(value, Integral):
        return None
    return int(value)


def _row_to_metrics_dict(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {}

    def _dec_or_none(v: Any) -> str | None:
        return str(v) if v is not None else None

    # T-sharpe Phase 1A: report 出力の "sharpe" 列は trade_sharpe_raw (v2) を採用
    return {
        "total_pnl": str(row.get("total_pnl", "0")),
        "sharpe": _dec_or_none(row.get("trade_sharpe_raw")),
        "sortino": _dec_or_none(row.get("sortino")),
        "calmar": _dec_or_none(row.get("calmar")),
        "max_drawdown_pct": str(row.get("max_drawdown_pct", "0")),
        "trade_count": int(row.get("trade_count", 0)),
        "sharpe_calc_version": str(
            row.get("sharpe_calc_version") or "v1_bar_annualized"
        ),
    }


def _check_live_criteria(
    row: Mapping[str, Any] | None,
    criteria: Mapping[str, float | int],
    *,
    holdout_days: int,
    stage_a_window_days: int,
) -> dict[str, Any]:
    """live_criteria 判定 (cycle 23 C1: Stage C 内部判定と整合化)。

    sharpe は trade-level → annualized 換算後に sharpe_min (= annualized) と比較する。
    比較値は `trade_sharpe_stage_c` 第一優先 (= Stage C scope、 holdout_days で annualize)、
    fallback で `trade_sharpe_raw` (= Stage A scope、 stage_a_window_days で annualize)。

    `value` には annualized SSOT を、 `value_trade_level` には trade-level を併記する。
    `sharpe_calc_version` は `<original>_annualized_live` に拡張 (summary 内専用 SSOT)。
    archive 側の `sharpe_calc_version` 列は変更しない (= 既存 consumer 互換、 Codex
    design-review Round 1 Warning 反映)。
    """
    if row is None:
        return {"checks": {}, "all_pass": False}
    checks: dict[str, dict[str, Any]] = {}

    # T-sharpe Phase 1A: live_criteria.sharpe_min は trade_sharpe_raw (v2) と比較。
    # v1 archive 行は sharpe_calc_version で識別し検査時に None 扱い (比較禁止)。
    raw_version = row.get("sharpe_calc_version")
    version = "v1_bar_annualized" if raw_version is None else str(raw_version)
    if version not in ("v1_bar_annualized", "v2_trade_level"):
        logger.warning(
            "live_criteria.unknown_sharpe_calc_version",
            sharpe_calc_version=version,
        )

    # cycle 23 C1: sharpe 比較値の優先順位
    # 1. trade_sharpe_stage_c (Stage C scope、 第一優先) → holdout_days で annualize
    # 2. trade_sharpe_raw (Stage A scope、 fallback) → stage_a_window_days で annualize
    sharpe_trade_level: float | None = None
    sharpe_source: str = "none"
    annualize_window_days: int = holdout_days
    if version == "v2_trade_level":
        stage_c_val = row.get("trade_sharpe_stage_c")
        if stage_c_val is not None:
            try:
                sharpe_trade_level = float(stage_c_val)
                sharpe_source = "trade_sharpe_stage_c"
                annualize_window_days = holdout_days
            except (TypeError, ValueError):
                sharpe_trade_level = None
        if sharpe_trade_level is None:
            raw_val = row.get("trade_sharpe_raw")
            if raw_val is not None:
                try:
                    sharpe_trade_level = float(raw_val)
                    sharpe_source = "trade_sharpe_raw"
                    # Codex design-review Round 1 Warning: raw fallback は Stage A scope
                    # = stage_a_window_days で annualize する。 holdout_days を使うとスケール不整合
                    annualize_window_days = stage_a_window_days
                except (TypeError, ValueError):
                    sharpe_trade_level = None

    trade_count = int(row.get("trade_count", 0) or 0)
    sharpe_min = float(criteria.get("sharpe_min", 0.0))

    sharpe_annualized = _annualize_trade_sharpe(
        sharpe_trade_level, trade_count, annualize_window_days
    ) if sharpe_trade_level is not None else None

    # version 拡張は summary 内専用 (= archive 列は変更しない、 Codex Warning 反映)
    version_summary = (
        f"{version}_annualized_live" if sharpe_annualized is not None else version
    )

    if sharpe_annualized is None:
        checks["sharpe"] = {
            "value": None,
            "value_trade_level": (
                str(sharpe_trade_level)
                if sharpe_trade_level is not None
                else None
            ),
            "threshold": str(sharpe_min),
            "pass": False,
            "sharpe_calc_version": version_summary,
            "sharpe_source": sharpe_source,
            "annualize_window_days": annualize_window_days,
        }
    else:
        checks["sharpe"] = {
            "value": str(sharpe_annualized),
            "value_trade_level": str(sharpe_trade_level),
            "threshold": str(sharpe_min),
            "pass": sharpe_annualized >= sharpe_min,
            "sharpe_calc_version": version_summary,
            "sharpe_source": sharpe_source,
            "annualize_window_days": annualize_window_days,
        }

    pnl_val = float(row.get("total_pnl", 0.0) or 0.0)
    pnl_min = float(criteria.get("total_pnl_min", 0.0))
    checks["total_pnl"] = {
        "value": str(pnl_val),
        "threshold": str(pnl_min),
        "pass": pnl_val >= pnl_min,
    }

    dd_pct = float(row.get("max_drawdown_pct", 0.0) or 0.0)  # 既に percent
    dd_frac = dd_pct / 100.0
    dd_max = float(criteria.get("max_drawdown_max", 1.0))
    checks["max_drawdown_pct"] = {
        "value": str(dd_pct),
        "threshold": str(dd_max * 100.0),
        "pass": dd_frac <= dd_max,
    }

    tc = int(row.get("trade_count", 0))
    tc_min = int(criteria.get("trade_count_min", 0))
    tc_max = int(criteria.get("trade_count_max", 10**9))
    checks["trade_count"] = {
        "value": tc,
        "threshold_min": tc_min,
        "threshold_max": tc_max,
        "pass": tc_min <= tc <= tc_max,
    }

    all_pass = all(c["pass"] for c in checks.values())
    return {"checks": checks, "all_pass": all_pass}


def _write_reports(
    *,
    run_dir: Path,
    cfg: AlphaFactoryConfig,
    run_id: str,
    run_number: int,
    bundle: LaneBarsBundle,
    per_generation: list[dict[str, Any]],
    best_name: str,
    best_entry: IndividualCacheEntry,
    best_genome: Genome,
    best_row: Mapping[str, Any] | None,
    final_population: list[Genome],
    final_population_cache: dict[str, IndividualCacheEntry],
    archive_path: Path,
    lane_manager: LaneManager,
    cross_pair_mode: str,
    now: datetime,
    run_context: RunContext,
    effective_max_tasks_per_child: int,
    diagnostics_sidecar_path: Path | None = None,
    top_fold_sidecar_path: Path | None = None,
    peak_rss_per_generation: list[dict[str, float]] | None = None,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    # T058 PR 5: 全 artifact に同一 dataset_epoch_id を伝搬する SSOT (RunContext 経由)
    dataset_epoch_id = run_context.dataset_epoch_id
    # T115: cross-pair selection pressure の effective 判定 (run loop と同一 helper SSOT)。
    _cp_sel_eff, _cp_sel_reason = _resolve_cross_pair_selection_pressure(cfg)

    best_fitness_val, best_finite = _safe_finite(best_entry.fitness_pen)
    best_fitness_str = _fitness_to_str(best_entry.fitness_pen)
    best_metrics = _row_to_metrics_dict(best_row)
    # cycle 23 C1: holdout_days / stage_a_window_days を渡して annualize 経路に統一
    live_check = _check_live_criteria(
        best_row,
        cfg.live_criteria,
        holdout_days=cfg.stage_gate.stage_c_holdout_days,
        stage_a_window_days=cfg.stage_gate.stage_a_window_days,
    )

    # per_generation.best_fitness_pen を非有限値から保護する
    # (R1 impl-review B1: summary.json に -inf/nan が漏れる経路遮断)
    sanitized_per_generation: list[dict[str, Any]] = []
    for idx, pg in enumerate(per_generation):
        raw_fp = float(pg["best_fitness_pen"])
        finite_val, finite_flag = _safe_finite(raw_fp)
        # T052: 世代毎 RSS ピーク (測定された世代のみ追加 field として記録)
        # ga_worker_* (pool_pids 指定時) と all_children_* (fallback) のどちらか
        # 非ゼロ側を採用 (sequential or pool_pids fallback では all_children を使う)
        rss_for_gen: dict[str, float] = {}
        if peak_rss_per_generation is not None and idx < len(peak_rss_per_generation):
            rss = peak_rss_per_generation[idx]
            worker_max = float(rss.get("ga_worker_max_rss_mb", 0.0))
            worker_total = float(rss.get("ga_worker_total_rss_mb", 0.0))
            # fallback: all_children_* に集計されたケース
            if worker_max == 0.0 and worker_total == 0.0:
                worker_max = float(rss.get("all_children_max_rss_mb", 0.0))
                worker_total = float(rss.get("all_children_total_rss_mb", 0.0))
            rss_for_gen = {
                "peak_main_rss_mb": float(rss.get("main_rss_mb", 0.0)),
                "peak_rss_mb_per_worker": worker_max,
                "peak_total_rss_mb": float(
                    rss.get("main_rss_mb", 0.0) + worker_total
                ),
            }
        sanitized_per_generation.append(
            {
                "generation": pg["generation"],
                "n_evaluated": pg["n_evaluated"],
                "stage_a_pass": pg["stage_a_pass"],
                "stage_b_pass": pg["stage_b_pass"],
                "stage_c_pass": pg["stage_c_pass"],
                "graduation_count": pg["graduation_count"],
                "best_fitness_pen": finite_val,
                "best_fitness_pen_finite": bool(finite_flag),
                "feasible_count": int(pg.get("feasible_count", 0)),
                # T052: stage 別 timing (sum + max 併記、legacy path では 0.0)
                "stage_a_seconds_total": float(pg.get("stage_a_seconds_total", 0.0)),
                "stage_a_seconds_max": float(pg.get("stage_a_seconds_max", 0.0)),
                "stage_b_seconds_total": float(pg.get("stage_b_seconds_total", 0.0)),
                "stage_b_seconds_max": float(pg.get("stage_b_seconds_max", 0.0)),
                "stage_c_seconds_total": float(pg.get("stage_c_seconds_total", 0.0)),
                "stage_c_seconds_max": float(pg.get("stage_c_seconds_max", 0.0)),
                **rss_for_gen,
            }
        )

    # T052: schema_version bump (1.0 → 1.1)
    # 1.1 で追加: per_generation[*].stage_*_seconds_total/_max,
    #            per_generation[*].peak_*_rss_mb, top-level parallel_config,
    #            top-level max_rss_mb_per_worker
    # 後方互換: consumer は未知 field を無視する義務 (additionalProperties: true)
    #
    # T058 PR 5: ``cascade_contract_version`` (int=2) と ``dataset_epoch_id``
    # (string) を summary.json 先頭に追加 (詳細設計 行 1354-1362)。
    # ``schema_version`` は **string "1.1" のまま維持** (test 互換性、
    # 詳細設計 行 1404)。 cascade_contract_version は int で型分離。
    summary: dict[str, Any] = {
        "schema_version": "1.1",
        "cascade_contract_version": CASCADE_CONTRACT_VERSION,
        "dataset_epoch_id": dataset_epoch_id,
        "run_id": run_id,
        "run_number": run_number,
        "generated_at": now.isoformat(),
        "dataset": {
            "instrument": cfg.dataset.instrument,
            "start": cfg.dataset.start.isoformat(),
            "end": cfg.dataset.end.isoformat(),
            # T087: `bars` は disjoint 化前と同じ意味 (= dataset 全期間
            # = bars_stage_a + bars_stage_b の合計) を据え置き、 後方互換維持。
            "bars": len(bundle.bars_stage_a) + len(bundle.bars_stage_b),
            "bars_dataset_total": len(bundle.bars_stage_a)
            + len(bundle.bars_stage_b),
            "bars_stage_a": len(bundle.bars_stage_a),
            "bars_stage_b": len(bundle.bars_stage_b),
            "bars_holdout": len(bundle.bars_holdout),
            "bars_stage_b_excludes_stage_a": True,
            "stage_a_bar_first": bundle.bars_stage_a[0].bar_time.isoformat(),
            "stage_a_bar_last": bundle.bars_stage_a[-1].bar_time.isoformat(),
            "stage_b_bar_first": bundle.bars_stage_b[0].bar_time.isoformat(),
            "stage_b_bar_last": bundle.bars_stage_b[-1].bar_time.isoformat(),
            "holdout_bar_first": bundle.bars_holdout[0].bar_time.isoformat(),
            "holdout_bar_last": bundle.bars_holdout[-1].bar_time.isoformat(),
        },
        "ga_config": {
            "population_size": cfg.ga.population_size,
            "generations": cfg.ga.generations,
            "crossover_rate": cfg.ga.crossover_rate,
            "mutation_rate": cfg.ga.mutation_rate,
            "tournament_size": cfg.ga.tournament_size,
            "elite_count": cfg.ga.elite_count,
            "max_depth": cfg.ga.max_depth,
            "max_clause": cfg.ga.max_clause,
            "units": cfg.backtest.units,
            "fitness_metric": cfg.ga.fitness_metric,
            "seed": cfg.ga.seed,
        },
        "backtest_config": {
            "initial_cash": str(cfg.backtest.initial_cash),
            "leverage": cfg.backtest.leverage,
            "units": cfg.backtest.units,
        },
        "stage_gate_config": {
            "stage_a_window_days": cfg.stage_gate.stage_a_window_days,
            "stage_a_alpha": cfg.stage_gate.stage_a_alpha,
            "stage_a_threshold": cfg.stage_gate.stage_a_threshold,
            "stage_b_window_months": cfg.stage_gate.stage_b_window_months,
            "stage_c_holdout_days": cfg.stage_gate.stage_c_holdout_days,
            "spread_stress_multiplier": cfg.stage_gate.spread_stress_multiplier,
        },
        "cross_pair_config": {
            "mode": cfg.cross_pair.mode,
            "aggregator_lambda": cfg.cross_pair.aggregator_lambda,
            # T115: in-loop selection pressure の effective 判定 (単一 helper SSOT)。
            "selection_pressure_requested": cfg.cross_pair.selection_pressure,
            "selection_pressure_effective": _cp_sel_eff,
            "selection_pressure_reason": _cp_sel_reason,
            "selection_pressure_margin_threshold": (
                cfg.cross_pair.selection_pressure_margin_threshold
            ),
        },
        "cross_pair_runtime_mode": cross_pair_mode,
        # T116: pressure ON 時は selection_key が 11-tuple で cross-pair margin 連続値
        # (v3_5_continuous)、OFF は 10-tuple (v3_3)。R88(bool,v3_4) と R89(continuous,
        # v3_5) を A/B 監査で識別可能にする (Codex Round1 Critical)。
        "selection_key_schema": (
            "v3_5_cross_pair_pressure_continuous" if _cp_sel_eff else "v3_3"
        ),
        "per_generation": sanitized_per_generation,
        "best": {
            "name": best_name,
            "generation": best_entry.generation,
            "fitness": best_fitness_str,
            "fitness_finite": bool(best_finite),
            "stage_a_pass": bool(best_entry.stage_a_pass),
            "stage_b_pass": bool(best_entry.stage_b_pass),
            "stage_c_pass": bool(best_entry.stage_c_pass),
            "feasible": bool(best_entry.feasible),
            "violation_magnitude": float(
                _safe_finite(best_entry.violation_magnitude)[0]
            ),
            # T045
            "stage_c_feasible": bool(best_entry.stage_c_feasible),
            "selection_score": [
                int(best_entry.feasible),
                -float(_safe_finite(best_entry.violation_magnitude)[0]),
                int(bool(best_entry.stage_b_pass) and bool(best_entry.feasible)),  # cycle 5
                int(best_entry.stage_b_pass),  # T046 v3.1
                int(best_entry.stage_c_feasible),
                int(best_entry.stage_c_pass),
                int(best_entry.stage_b_pass),
                int(best_entry.stage_a_pass),
                int(best_entry.fold_robust),  # cycle 4: fold_robust
                float(best_fitness_val),
            ],
            "selection_score_schema": "v3_3_stage_b_feasible_priority",
            "fold_robust": bool(best_entry.fold_robust),
            "stage_b_pass_and_feasible": bool(  # cycle 5
                bool(best_entry.stage_b_pass) and bool(best_entry.feasible)
            ),
            "metrics": best_metrics,
        },
        "stage_b": {
            # T087: best 個体ぶんの n_fold_effective を summary level で参照可能に
            # (downstream consumer / report 側の inconclusive 判定 SSOT)。
            # is_stage_b_inconclusive と整合した型防御 (Integral 以外は None)。
            "n_fold_effective": _coerce_n_fold_effective(
                best_row.get("n_fold_effective") if best_row is not None else None
            ),
            "statistical_inconclusive": is_stage_b_inconclusive(
                best_row.get("n_fold_effective") if best_row is not None else None
            ),
        },
        "live_criteria": live_check,
        "population_size": len(final_population),
        "graduation_count": lane_manager.promote_graduates(),
        "archive_parquet": str(archive_path),
        # T052: 並列実行設定と RSS ピーク (RUN 全体最大)
        "parallel_config": {
            "max_workers": cfg.ga.max_workers,
            "mode": "parallel" if cfg.ga.max_workers > 1 else "sequential",
            # worker リサイクル間隔の実効値 (observability)。main() で導出した
            # 値を引数で受け取り再導出しない (SSOT)。max_workers<=1 (pool 無し)
            # では maxtasksperchild は無効のため null を記録する。
            # @ref: devnotes/20260514-2045-ga-worker-memory/
            "max_tasks_per_child": (
                effective_max_tasks_per_child
                if cfg.ga.max_workers > 1
                else None
            ),
        },
        "max_rss_mb_per_worker": float(
            max(
                (
                    max(
                        rss.get("ga_worker_max_rss_mb", 0.0),
                        rss.get("all_children_max_rss_mb", 0.0),
                    )
                    for rss in (peak_rss_per_generation or [])
                ),
                default=0.0,
            )
        ),
    }
    # T033: 書き込み成功時のみ summary に sidecar path を追加
    # (consumer は missing field を無視できる契約)
    if diagnostics_sidecar_path is not None:
        try:
            summary["diagnostics_sidecar"] = str(
                diagnostics_sidecar_path.relative_to(REPO_ROOT)
            )
        except ValueError:
            summary["diagnostics_sidecar"] = str(diagnostics_sidecar_path)
    # cycle 3: Stage A top-fold robustness sidecar も同じ契約で配線
    if top_fold_sidecar_path is not None:
        try:
            summary["diagnostics_stage_a_top_fold"] = str(
                top_fold_sidecar_path.relative_to(REPO_ROOT)
            )
        except ValueError:
            summary["diagnostics_stage_a_top_fold"] = str(top_fold_sidecar_path)
    # T058 PR 5: passive validation (LOG_ONLY default で warning のみ、
    # FAIL_CLOSED で必須 field 欠落 raise)
    assert_run_report_v2(summary, mode=cfg.schema_contract.to_mode())
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    history: list[dict[str, Any]] = []
    for pg in per_generation:
        history.append(
            {
                # T058 PR 5: 各世代 entry にも dataset_epoch_id 付与 (詳細設計 行 1366-1370)
                "dataset_epoch_id": dataset_epoch_id,
                "generation": pg["generation"],
                "best_fitness": _fitness_to_str(
                    float(pg["best_fitness_pen"])
                ),
                "stage_a_pass": pg["stage_a_pass"],
                "stage_b_pass": pg["stage_b_pass"],
                "stage_c_pass": pg["stage_c_pass"],
                "graduation_count": pg["graduation_count"],
            }
        )
    (run_dir / "history.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # T058 PR 5: best_genome.json に dataset_epoch_id を merge
    # (詳細設計 行 1372-1373、 既存 genome_to_dict 構造に同一 epoch_id を追加)
    best_genome_payload: dict[str, Any] = {"dataset_epoch_id": dataset_epoch_id}
    best_genome_payload.update(genome_to_dict(best_genome))
    (run_dir / "best_genome.json").write_text(
        json.dumps(best_genome_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (run_dir / "population.jsonl").open("w", encoding="utf-8") as f:
        for g in final_population:
            ent = final_population_cache.get(g.name)
            fit_val = ent.fitness_pen if ent is not None else 0.0
            # T058 PR 5: 各 line に dataset_epoch_id 付与 (詳細設計 行 1375-1377)
            f.write(
                json.dumps(
                    {
                        "dataset_epoch_id": dataset_epoch_id,
                        "name": g.name,
                        "fitness": _fitness_to_str(fit_val),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _check_memory_budget(max_workers: int, strict: bool) -> None:
    """T052: max_workers が available memory budget を超えたら warning。

    `--strict-memory-guard` 指定時は SystemExit (autopilot 等で OOM 防止)。

    NOTE: 旧来の「1 worker 約 400MB」前提は実測 (5.5〜8.7GB) と乖離している。
    実 per-worker RSS は pymalloc アリーナ断片化 (run_backtest の Decimal
    churn 由来) で数 GB 規模に達する。maxtasksperchild による worker
    リサイクル (devnotes/20260514-2045-ga-worker-memory/) で頭打ちするが、
    本関数の // 400 式自体の本格修正 (4 項モデル化) は Decimal churn 削減
    タスクとセットで別途行う。現状は粗い下限ガードとして残置する。
    """
    try:
        import psutil
    except ImportError:
        return  # psutil 不在ならスキップ
    available_mb = psutil.virtual_memory().available / 1024 / 1024
    worker_budget_mb = available_mb - 4096
    recommended_max = max(1, int(worker_budget_mb // 400))
    if max_workers > recommended_max:
        logger.warning(
            "run_ga.max_workers_exceeds_memory_budget",
            requested=max_workers,
            recommended=recommended_max,
            available_mb=int(available_mb),
        )
        if strict:
            raise SystemExit(
                f"strict-memory-guard: max_workers={max_workers} > "
                f"recommended {recommended_max} "
                f"(available_mb={int(available_mb)})"
            )


def _derive_max_tasks_per_child(
    configured: int | None,
    population_size: int,
    max_workers: int,
) -> tuple[int, str]:
    """GenomeEvaluator に渡す maxtasksperchild の実効値を決定する。

    - configured が非 None: その値をそのまま使う (source="config")。
    - configured が None: ``2*population_size // max_workers`` を自動導出
      (= 各 worker をおよそ 2 世代ごとにリサイクル、source="auto")。
      下限 1。

    Returns:
        ``(effective_value, source)``。
    """
    if configured is not None:
        return configured, "config"
    derived = max(1, (2 * population_size) // max(1, max_workers))
    return derived, "auto"


def _aggregate_ab_summary(
    *,
    summary_out: Mapping[str, Any],
    all_ab_score_pairs: list[tuple[float, float]],
    b_evaluated_count: int,
    excluded_preflight_count: int,
    current_score_source: str | None,
) -> tuple[int, int, str | None]:
    """T081 step 1: lane_manager.run_generation の summary_out から AB pair / counter
    / source 集約 (詳細設計 § 3.4.3)。

    破壊的更新: ``all_ab_score_pairs`` に extend する。

    Args:
        summary_out: lane_manager.run_generation の戻り dict (= ab_score_pairs /
            ab_score_source / ab_b_evaluated_count / ab_excluded_preflight_count
            の必須 4 キーを含む)。
        all_ab_score_pairs: Run loop 全世代の集約 list (in-place extend)。
        b_evaluated_count: 集約済 b_evaluated_count (= 累積)。
        excluded_preflight_count: 集約済 excluded_preflight_count (= 累積)。
        current_score_source: 現在までに観測した source (= None / "noop" / Phase 1 source)。

    Returns:
        ``(new_b_evaluated_count, new_excluded_preflight_count, new_score_source)``

    Raises:
        RuntimeError: ab_score_source が run 内で異なる値が観測された場合
            (= mixing 禁止、 Codex Round 1 [Critical] 1 取込)。
    """
    new_pairs = summary_out.get("ab_score_pairs", [])
    if new_pairs:
        for pair in new_pairs:
            # consumer 側 defensive: numbers.Real (= numpy 数値型 covered) +
            # bool 除外 (= producer 側でも弾いているが二重防御、 impl-review Round 1
            # [Suggestion] 取込)
            if (
                isinstance(pair, tuple)
                and len(pair) == 2
                and isinstance(pair[0], numbers.Real)
                and not isinstance(pair[0], bool)
                and isinstance(pair[1], numbers.Real)
                and not isinstance(pair[1], bool)
            ):
                all_ab_score_pairs.append(
                    (float(pair[0]), float(pair[1]))
                )
    new_b_evaluated = b_evaluated_count + int(
        summary_out.get("ab_b_evaluated_count", 0)
    )
    new_excluded = excluded_preflight_count + int(
        summary_out.get("ab_excluded_preflight_count", 0)
    )
    new_source_value = summary_out.get("ab_score_source", "noop")
    new_score_source: str | None = current_score_source
    if isinstance(new_source_value, str) and new_source_value != "noop":
        if new_score_source is None:
            new_score_source = new_source_value
        elif new_score_source != new_source_value:
            raise RuntimeError(
                f"ab_score_source mixing detected: "
                f"existing={new_score_source!r} new={new_source_value!r}"
            )
    return new_b_evaluated, new_excluded, new_score_source


def _resolve_stage_a_threshold(
    cfg: AlphaFactoryConfig,
    *,
    cli_override: float | None,
    history_path: Path,
    dataset_epoch_id: str,
) -> tuple[float, Literal["config", "history", "cli"]]:
    """T054: Stage A threshold の effective 値と source を確定する。

    優先順位:
        1. CLI override (--stage-a-threshold) があれば最優先 → source="cli"
        2. history.jsonl の最新適用可能 record (cross-run guard 通過) → source="history"
        3. config 値 (yaml load 値) → source="config"

    cross-run contamination guard (load_calibrated_threshold) で
    base_config_hash / dataset_span / instrument / stage_gate_version /
    dataset_epoch_id の AND 一致確認 + decision filter (tighten/loosen) を行う。

    T058 PR 5: ``dataset_epoch_id`` を caller (RunContext 経由) から受取り、
    PR 3 の literal "epoch_legacy" 直書きを置換 (詳細設計 行 1078-1085)。
    """
    # 1. CLI override 優先
    if cli_override is not None:
        return float(cli_override), "cli"

    # 2. history.jsonl から override 試行
    base_hash = compute_base_config_hash(cfg)
    dataset_span = (str(cfg.dataset.start), str(cfg.dataset.end))
    # T058 PR 5: dataset_epoch_id を RunContext 経由で受け取る (synthesis § 12.1)
    calibrated = load_calibrated_threshold(
        history_path=history_path,
        base_config_hash=base_hash,
        dataset_epoch_id=dataset_epoch_id,
        dataset_span=dataset_span,
        instrument=cfg.dataset.instrument,
        stage_gate_version=STAGE_GATE_VERSION,
    )
    if calibrated is not None:
        return calibrated, "history"

    # 3. config 値 fallback
    return cfg.stage_gate.stage_a_threshold, "config"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cfg = load_config(args.config, overrides=_args_to_overrides(args))

    # T059: dataset_epoch_id の deterministic 生成 (T058 stub からの卒業).
    # RunContext は run_id 確定後 (下方) に生成するが、 threshold 解決が
    # それより前にあるため、 epoch_id 値だけ先取りして両方に渡す SSOT。
    #
    # 戦略: ``make_epoch_id(EpochWindow(start, end))`` で deterministic 生成。
    # cfg.dataset の (start, end) を window として直接使う (Phase 2 で
    # ``EpochManager.reserve_run_slot`` 経由に切替予定)。
    # backward compat: ``EpochWindow.__post_init__`` の ``ValueError`` (= end<=start)
    # は cfg load 時点で既に弾かれている (config.py: ``DatasetConfig.__post_init__``)
    # が、 万一の防御として ``ValueError`` のみ捕捉して ``generate_epoch_id_stub``
    # に fallback する (= T058 PR 1-7 の規範、 silent regression を避けるため
    # warning log を必ず出力)。 broad ``except Exception`` は意図的に避け、
    # 真に想定された例外型のみ救済する (Codex impl-review-pr1 Round 1 NIT C1)。
    try:
        dataset_epoch_id = make_epoch_id(
            EpochWindow(start=cfg.dataset.start, end=cfg.dataset.end)
        )
    except ValueError as exc:
        logger.warning(
            "run_ga.epoch_id_deterministic_fallback",
            error=str(exc),
            fallback_to="generate_epoch_id_stub",
        )
        dataset_epoch_id = generate_epoch_id_stub(cfg.dataset)

    # T099 cycle 22 (Codex impl-review Round 1 Critical 修正): Stage B gate kind
    # CLI override を **_resolve_stage_a_threshold より前** に適用する。
    # 理由: compute_base_config_hash が stage_b_gate_kind / profit_safe_pfr_*
    # を含むため、 override 後の cfg で hash を計算しないと cross-run guard
    # (history record の base_config_hash 一致判定) が override 時に効かなくなる。
    if args.stage_b_gate_kind is not None and args.stage_b_gate_kind != cfg.stage_gate.stage_b_gate_kind:
        logger.info(
            "stage_gate.stage_b_gate_kind_override",
            old=cfg.stage_gate.stage_b_gate_kind,
            new=args.stage_b_gate_kind,
            source="cli",
        )
        cfg = replace(
            cfg,
            stage_gate=replace(cfg.stage_gate, stage_b_gate_kind=args.stage_b_gate_kind),
        )

    # T054: Stage A threshold の effective 値と source を確定し cfg に反映する。
    # source 単一値 ("config" | "history" | "cli") を必ず確定 (詳細設計 §0b)。
    repo_root = Path(__file__).resolve().parents[2]
    history_path = repo_root / DEFAULT_HISTORY_PATH
    effective_threshold, threshold_source = _resolve_stage_a_threshold(
        cfg,
        cli_override=args.stage_a_threshold,
        history_path=history_path,
        dataset_epoch_id=dataset_epoch_id,
    )
    if effective_threshold != cfg.stage_gate.stage_a_threshold:
        logger.info(
            "stage_gate.threshold_override",
            old=cfg.stage_gate.stage_a_threshold,
            new=effective_threshold,
            source=threshold_source,
        )
        # frozen dataclass なので replace で書き換え (cfg / cfg.stage_gate 両方 frozen)
        cfg = replace(
            cfg,
            stage_gate=replace(
                cfg.stage_gate, stage_a_threshold=effective_threshold
            ),
        )
    # 必ず effective threshold + source を log 出力 (V0-B、source 単一値で確定)
    logger.info(
        "stage_gate.effective_threshold",
        stage_a_threshold=cfg.stage_gate.stage_a_threshold,
        source=threshold_source,
        full_config_hash=compute_full_config_hash(cfg),
    )

    # T099 cycle 22: 必ず effective stage_b_gate_kind を log 出力 (override は上記で適用済)
    logger.info(
        "stage_gate.stage_b_gate_kind",
        kind=cfg.stage_gate.stage_b_gate_kind,
        profit_safe_pfr_threshold=cfg.stage_gate.profit_safe_pfr_threshold,
        profit_safe_pfr_min_n_fold=cfg.stage_gate.profit_safe_pfr_min_n_fold,
    )

    if cfg.ga.fitness_metric != "sharpe":
        logger.warning(
            "run_ga.fitness_metric_override",
            requested=cfg.ga.fitness_metric,
            note=(
                "Phase 2: Stage A fitness_pen (sharpe - alpha*size_norm) を "
                "唯一の内部選択指標として使用。CLI/config の fitness_metric "
                "値は summary への記録のみで効かない"
            ),
        )

    now = datetime.now(tz=UTC)
    run_id = args.run_id or f"run_{now.strftime('%Y%m%d_%H%M%S')}"
    run_number = get_latest_run_number() + 1
    run_dir = RUN_REPORTS_DIR / f"run-{run_number}"

    # T058 PR 5: RunContext 生成 (詳細設計 行 1334-1341)
    # 1 Run スコープで固定される runtime context。 archive / report 全
    # artifact が同じ source から dataset_epoch_id 等を読む SSOT。
    run_context = RunContext(
        run_id=run_id,
        run_number=run_number,
        dataset_epoch_id=dataset_epoch_id,
        base_config_hash=compute_base_config_hash(cfg),
        instrument=cfg.dataset.instrument,
    )

    logger.info(
        "ga.run.start",
        run_id=run_id,
        run_number=run_number,
        instrument=cfg.dataset.instrument,
        population_size=cfg.ga.population_size,
        generations=cfg.ga.generations,
        dataset_epoch_id=dataset_epoch_id,
    )

    # cycle24 Codex impl-review Critical: registry を per-run で再構築し、同一
    # プロセス内の前 run (experimental ON) の状態 (F15 残留) が OFF run に漏れるのを
    # 防ぐ。clear()→ensure_registered() で常に 32本基準、flag ON 時のみ F15 追加。
    _clear_registry()
    ensure_registered()
    if getattr(args, "enable_mtf_primitive", False):
        # cycle24: opt-in で experimental primitive F15 を registry に追加してから
        # pool を構築。default(未指定) では呼ばれず registry 32本 = bit-exact。
        from src.alpha_factory.primitives.directional_generic import (
            register_experimental,
        )

        register_experimental()
        logger.info("run_ga.experimental_primitive.enabled kind=mtf_trend_pullback id=F15")
    rg_registry = build_random_gen_registry()

    bundle = _load_lane_bars(
        cfg.dataset.instrument, cfg.dataset, cfg.stage_windows
    )

    # T087: Stage Partition Integrity Guard (fail-closed)。
    # aux_preflight より前に呼ぶ理由: bars 区間が壊れていれば aux 評価は意味がない。
    # 違反時は StagePartitionInputError / StagePartitionLeakError で起動停止。
    # T091 cycle_phase1 段階 3 (2026-05-09): B-2 holdout 長検証 + 二重 opt-in escape hatch。
    # holdout_short_override = (CLI --allow-holdout-short) AND (env ZENIGAME_FX_SMOKE_TEST=1)
    # 両方 set でない場合 holdout 長違反は fail-closed (production 誤発動防止)。
    smoke_test_mode = os.environ.get("ZENIGAME_FX_SMOKE_TEST") == "1"
    cli_allow_short = bool(getattr(args, "allow_holdout_short", False))
    if cli_allow_short and not smoke_test_mode:
        raise SystemExit(
            "--allow-holdout-short requires ZENIGAME_FX_SMOKE_TEST=1 env var. "
            "This double-opt-in prevents accidental production override."
        )
    holdout_short_override = cli_allow_short and smoke_test_mode
    if holdout_short_override:
        logger.warning(
            "run_ga.holdout_short_override_enabled",
            note="smoke test mode: holdout 長違反は WARN のみで継続する",
        )
    validate_stage_partition(
        bundle.bars_stage_a,
        bundle.bars_stage_b,
        bundle.bars_holdout,
        expected_holdout_days=cfg.stage_gate.stage_c_holdout_days,
        allow_holdout_short=holdout_short_override,
    )
    logger.info(
        "run_ga.stage_partition_guard.passed",
        instrument=cfg.dataset.instrument,
        stage_gate_version=STAGE_GATE_VERSION,
        expected_holdout_days=cfg.stage_gate.stage_c_holdout_days,
        holdout_short_override=holdout_short_override,
    )

    # T058 PR 5: archive に RunContext + enforcement_mode を注入
    # (詳細設計 行 1344-1349)。 既存 backward compat (run_context=None) は
    # 維持されるが、 production 経路では必ず RunContext を渡す。
    archive = GenomeArchive(
        run_id=run_id,
        run_number=run_number,
        run_context=run_context,
        enforcement_mode=cfg.schema_contract.to_mode(),
    )
    lane_id = f"tier1_{cfg.dataset.instrument}"

    # T057 Phase 2 Gate B/C: aux preflight + AuxBundle 構築
    # CLI > config の優先順位: --allow-aux-missing が指定されたら strict 無効化
    effective_strict = cfg.stage_gate.strict_aux_required and not args.allow_aux_missing
    logger.info(
        "preflight.effective_strict_mode",
        strict=effective_strict,
        config_strict=cfg.stage_gate.strict_aux_required,
        cli_allow_aux_missing=args.allow_aux_missing,
        source=("cli_override" if args.allow_aux_missing else "config"),
    )
    aux_bundle: AuxBundle | None = None
    try:
        with SessionLocal() as aux_session:
            preflight_period = (cfg.dataset.start, cfg.dataset.end)
            preflight_result = preflight_check_aux_data(
                db_session=aux_session,
                period=preflight_period,
                stage_b_window_months=cfg.stage_gate.stage_b_window_months,
                stage_c_holdout_days=cfg.stage_gate.stage_c_holdout_days,
                allow_missing=not effective_strict,
            )
            logger.info(
                "preflight.aux_data_check",
                hard_satisfied=preflight_result.hard_satisfied,
                hard_missing=preflight_result.hard_missing,
                soft_satisfied=preflight_result.soft_satisfied,
                soft_missing=preflight_result.soft_missing,
                coverage_pct=preflight_result.coverage_pct_by_series,
            )
            # AuxBundle を 1 度だけ構築 (raw)
            # Codex impl-review-round-1 [Critical]: preflight と同じ拡張期間を
            # 使う必要がある (Stage B 18ヶ月 history + Stage C holdout)。
            # dataset 期間だけでは Stage B/holdout の bars に対応する aux 観測が
            # 0 埋め経路に落ちる ("preflight 通過したのに評価で safe default"
            # 値伝搬漏れリスク)。
            all_series = list(HARD_REQUIRED_AUX.keys()) + list(
                SOFT_REQUIRED_AUX.keys()
            )
            extended_period = compute_extended_period(
                preflight_period,
                stage_b_window_months=cfg.stage_gate.stage_b_window_months,
                stage_c_holdout_days=cfg.stage_gate.stage_c_holdout_days,
            )
            aux_bundle = build_aux_bundle_from_db(
                db_session=aux_session,
                period=extended_period,
                series_ids=all_series,
                aux_pairs=("EUR_USD", "USD_JPY"),
            )
            logger.info(
                "preflight.aux_bundle_built",
                daily_series_count=len(aux_bundle.daily_series),
                aux_pair_mid_count=sum(
                    int(v.mid_close.size)
                    for v in aux_bundle.aux_pair_mid_index.values()
                ),
                event_calendar_loaded=aux_bundle.event_calendar is not None,
                vix_snapshot_loaded=aux_bundle.vix_snapshot is not None,
            )
            # T107: raw columnar 構築直後の RSS (aux pair mid index 構築効果を観測)。
            # align は worker 側で lazy に行われるため main では raw 構築が支配的。
            _log_phase_marker("after_raw_aux_index_built")
    except Exception as exc:
        # preflight が effective_strict=True で失敗 → re-raise (fail-closed)
        # それ以外は WARN log を残して aux_bundle=None で継続 (safe default 経路)
        if effective_strict:
            raise
        logger.warning(
            "preflight.aux_bundle_build_failed",
            error=str(exc),
            note="continuing with aux_bundle=None (safe default path)",
        )
        aux_bundle = None

    _log_phase_marker(
        "after_aux_bundle_built",
        aux_bundle_present=aux_bundle is not None,
    )

    primitive_evaluator = RegistryEvaluator(pair=cfg.dataset.instrument)
    bt_factory = _make_bt_factory(cfg.dataset, cfg.backtest)

    # T033: Stage A/B/C diagnostics を蓄積する run-level collector。
    # GA 完了後 sidecar Parquet として flush する。
    diagnostics_collector = DiagnosticsCollector()

    tier1_lane = Tier1Lane(
        lane_id=lane_id,
        instrument=cfg.dataset.instrument,
        bars_60d=bundle.bars_stage_a,
        bars_stage_b=bundle.bars_stage_b,
        bars_holdout=bundle.bars_holdout,
        meta=bundle.meta,
    )
    # T114: cross-pair enable 時、ANCHOR_PAIRS[target] の holdout をロードし
    # cp_inputs / GraduationLane.pair_bars に配線する (default OFF=現状不変)。
    _cp_inputs = None
    _cp_pair_bars: dict[str, list[PriceBar]] = {}
    _cp_pair_meta: dict[str, InstrumentMeta] = {}
    _cp_runtime_mode = "skipped_disabled"
    if cfg.cross_pair.enable:
        from src.alpha_factory.cross_pair import ANCHOR_PAIRS
        from src.alpha_factory.parallel_eval import CrossPairLaneInputs

        _tgt = cfg.dataset.instrument
        _anchors = ANCHOR_PAIRS.get(_tgt)
        if _anchors is None:
            logger.warning(
                "run_ga.cross_pair.target_not_configured",
                target=_tgt,
                known_targets=sorted(ANCHOR_PAIRS.keys()),
            )
            _cp_runtime_mode = "skipped_target_not_configured"
        else:
            _cp_pair_bars[_tgt] = list(bundle.bars_holdout)
            _cp_pair_meta[_tgt] = bundle.meta
            for _a in _anchors:
                if _a == _tgt:
                    continue
                _a_bars, _a_meta = _load_holdout_only(
                    _a, cfg.dataset, cfg.stage_windows
                )
                _cp_pair_bars[_a] = _a_bars
                _cp_pair_meta[_a] = _a_meta
            _cp_inputs = CrossPairLaneInputs(
                target_pair=_tgt,
                pair_bars_map={k: tuple(v) for k, v in _cp_pair_bars.items()},
                meta_map=dict(_cp_pair_meta),
            )
            _cp_runtime_mode = "enabled"
            logger.info(
                "run_ga.cross_pair.enabled",
                target=_tgt,
                anchors=list(_anchors),
                n_pairs=len(_cp_pair_bars),
            )
    graduation_lane = GraduationLane(
        lane_id=GRADUATION_LANE_ID,
        pair_bars=_cp_pair_bars,
        pair_meta=_cp_pair_meta,
    )
    cross_pair_mode = _cp_runtime_mode

    # T052: GenomeEvaluator を構築 (max_workers=1 で in-process / >1 で Pool)。
    # LaneEvalContext は RUN 中 immutable (Pool initializer で 1 度だけ broadcast)。
    #
    # preflight 値 (Stage B fold 不足判定) を RUN 開始時に計算して context に
    # 埋め込む。これにより worker 側 evaluate_genome が Stage A pass 後に Stage
    # B/C を短絡 skip でき、無駄計算を排除できる (Codex impl-review §1 Critical)。
    bars_b_list = list(bundle.bars_stage_b)
    lane_n_unique_dates = n_unique_dates(bars_b_list)
    wf_min_dates = wf_min_unique_dates(
        cfg.stage_gate.wf_train_days,
        cfg.stage_gate.wf_embargo_days,
        cfg.stage_gate.wf_test_days,
    )
    lane_max_folds = compute_max_folds(
        lane_n_unique_dates,
        cfg.stage_gate.wf_train_days,
        cfg.stage_gate.wf_embargo_days,
        cfg.stage_gate.wf_test_days,
        cfg.stage_gate.wf_step_days,
    )
    wf_min_folds = cfg.stage_gate.wf_min_folds_required
    preflight_underfilled = lane_max_folds < wf_min_folds
    preflight_payload = PreflightPayload(
        n_unique_dates=lane_n_unique_dates,
        wf_min_unique_dates=wf_min_dates,
        max_folds=lane_max_folds,
        wf_min_folds_required=wf_min_folds,
        n_bars=len(bars_b_list),
    )

    wf_min_safe_folds = cfg.stage_gate.wf_min_safe_folds
    logger.info(
        "stage_b_fold_guard.evaluating",
        compute_max_folds=lane_max_folds,
        wf_min_safe_folds=wf_min_safe_folds,
        wf_min_folds_required=wf_min_folds,
        wf_train_days=cfg.stage_gate.wf_train_days,
        wf_test_days=cfg.stage_gate.wf_test_days,
        wf_step_days=cfg.stage_gate.wf_step_days,
        wf_embargo_days=cfg.stage_gate.wf_embargo_days,
        n_unique_dates_b=lane_n_unique_dates,
        n_bars_b=len(bars_b_list),
        lane_id=lane_id,
        instrument=cfg.dataset.instrument,
    )
    if lane_max_folds < wf_min_safe_folds:
        raise RuntimeError(
            f"Stage B fold guard failed: compute_max_folds={lane_max_folds} "
            f"< wf_min_safe_folds={wf_min_safe_folds} "
            f"(n_unique_dates_b={lane_n_unique_dates}, "
            f"wf_train={cfg.stage_gate.wf_train_days}d, "
            f"wf_test={cfg.stage_gate.wf_test_days}d, "
            f"wf_step={cfg.stage_gate.wf_step_days}d, "
            f"wf_embargo={cfg.stage_gate.wf_embargo_days}d, "
            f"lane_id={lane_id}). "
            f"Stage B 偽陽性回避のため fail-closed (cycle 2 improve-cycle)。 "
            f"対応: WF 値 (wf_train/wf_test/wf_step) を短縮するか partition (B 期間) を拡張。"
        )
    logger.info("stage_b_fold_guard.passed", lane_id=lane_id)

    # T117: multi-pair training。enable 時 anchor ペアの Stage A bars + meta +
    # bt_cfg をロードし mp_train_inputs を構築 (default None=単一=現挙動 bit-exact)。
    _mp_inputs = _build_multi_pair_train_inputs(cfg, bt_factory)

    lane_ctx = LaneEvalContext(
        lane_id=lane_id,
        bars_a=tuple(bundle.bars_stage_a),
        bars_b=tuple(bundle.bars_stage_b),
        bars_holdout=tuple(bundle.bars_holdout),
        meta=bundle.meta,
        bt_cfg=bt_factory(cfg.dataset.instrument),
        cp_inputs=_cp_inputs,  # T114: cross_pair.enable 時のみ非None (本番parallel経路)
        preflight_underfilled=preflight_underfilled,
        preflight_payload=preflight_payload,
        aux_bundle=aux_bundle,  # T057 Phase 2: stage 別 align 用 raw container
        mp_train_inputs=_mp_inputs,  # T117: multi-pair training (default None)
    )
    # T052: max_workers が available memory budget を超えたら warning
    # (--strict-memory-guard 指定時のみ fail-fast)
    _check_memory_budget(cfg.ga.max_workers, args.strict_memory_guard)
    cpu_count = os.cpu_count()
    if cpu_count is not None and cfg.ga.max_workers > cpu_count:
        logger.warning(
            "run_ga.max_workers_exceeds_cpu_count",
            requested=cfg.ga.max_workers,
            cpu_count=cpu_count,
        )
    logger.info(
        "run_ga.parallel_mode",
        max_workers=cfg.ga.max_workers,
        mode="parallel" if cfg.ga.max_workers > 1 else "sequential",
    )
    # worker リサイクル間隔 (pymalloc アリーナ断片化対策) の実効値を決定
    effective_max_tasks_per_child, mtpc_source = _derive_max_tasks_per_child(
        cfg.ga.max_tasks_per_child,
        cfg.ga.population_size,
        cfg.ga.max_workers,
    )
    logger.info(
        "run_ga.max_tasks_per_child",
        value=effective_max_tasks_per_child,
        source=mtpc_source,
        active=cfg.ga.max_workers > 1,  # max_workers==1 (pool 無し) では未使用
    )

    # GA loop は GenomeEvaluator の `with` 文内で実行 (close 漏れ防止)
    per_generation: list[dict[str, Any]] = []
    prev_population: list[Genome] = []
    genomes_by_name: dict[str, Genome] = {}
    cache: dict[str, IndividualCacheEntry] = {}
    rng = random.Random(cfg.ga.seed)
    peak_rss_per_generation: list[dict[str, float]] = []

    with GenomeEvaluator(
        max_workers=cfg.ga.max_workers,
        max_tasks_per_child=effective_max_tasks_per_child,
        stage_gate_cfg=cfg.stage_gate,
        cross_pair_cfg=cfg.cross_pair,
        prim_evaluator=primitive_evaluator,
        lane_contexts={lane_id: lane_ctx},
        # cycle25: spawn worker registry にも experimental primitive (F15) を
        # 登録させる。ON 時のみ True。OFF (default) は False で従来 bit-exact。
        enable_experimental=getattr(args, "enable_mtf_primitive", False),
    ) as genome_evaluator:
        lane_manager = LaneManager(
            tier1={lane_id: tier1_lane},
            graduation=graduation_lane,
            stage_gate_config=cfg.stage_gate,
            cross_pair_config=cfg.cross_pair,
            primitive_evaluator=primitive_evaluator,
            archive=archive,
            backtest_config_factory=bt_factory,
            diagnostics_collector=diagnostics_collector,
            genome_evaluator=genome_evaluator,
        )

        # T081 step 1: ABDivergenceMetric 実値配線用集約 (詳細設計 § 3.4.3)
        # 全世代の (a_score, b_score) ペアを list で集約 (= 衝突回避)。
        # ab_score_source は run 内で不変、 異なる source を検出したら fail-fast。
        all_ab_score_pairs: list[tuple[float, float]] = []
        all_ab_b_evaluated_count = 0
        all_ab_excluded_preflight_count = 0
        ab_score_source: str | None = None  # run 内 mixing 検出用 (= None / "noop" 以外で固定)

        # T115: cross-pair in-loop selection pressure の effective 判定 (RUN 中不変)。
        _cp_sel_pressure, _cp_sel_reason = _resolve_cross_pair_selection_pressure(cfg)
        _cp_sel_threshold = cfg.cross_pair.selection_pressure_margin_threshold
        logger.info(
            "run_ga.cross_pair.selection_pressure",
            effective=_cp_sel_pressure,
            reason=_cp_sel_reason,
            requested=cfg.cross_pair.selection_pressure,
            margin_threshold=_cp_sel_threshold,
        )
        # cycle26 (D): anti-overfit 選択圧の effective 判定 (RUN 中不変)。
        _robust_sel, _robust_reason = _resolve_robust_selection(cfg)
        logger.info(
            "run_ga.robust_selection",
            effective=_robust_sel,
            reason=_robust_reason,
            requested=cfg.ga.robust_selection_enabled,
            w_pfre=cfg.ga.robust_w_pfre,
            w_sign=cfg.ga.robust_w_sign,
            w_disp=cfg.ga.robust_w_disp,
        )

        _log_phase_marker("before_ga_loop", generations=cfg.ga.generations)

        for gen in range(cfg.ga.generations + 1):
            if gen == 0:
                # T101: warmstart pool 注入。warmstart_ratio=0.0 (default) では
                # n_ws=0 となり下記 warmstart 経路に入らず、population は random_genome
                # のみ (name=g0_i*)・rng 消費順とも現行と完全同一 (挙動不変)。
                ws_genomes: list = []
                _n_ws = int(cfg.ga.population_size * cfg.ga.warmstart_ratio)
                if cfg.ga.warmstart_ratio > 0.0 and not cfg.ga.warmstart_motif_archive:
                    # 誤設定検知 (Codex impl-review Suggestion): ratio>0 だが archive 未指定
                    logger.warning(
                        "ga.warmstart.ratio_set_but_no_archive",
                        warmstart_ratio=cfg.ga.warmstart_ratio,
                    )
                if _n_ws > 0 and cfg.ga.warmstart_motif_archive:
                    _motifs = load_warmstart_motifs(cfg.ga.warmstart_motif_archive)
                    for _i in range(_n_ws):
                        if not _motifs:
                            break
                        if _i == 0:
                            # 非 mutate アンカー: 最良 motif を厳密保持 (再現性の核)
                            _cand = _motifs[0]
                        else:
                            _src = _motifs[rng.randrange(len(_motifs))]
                            # n_edit_max も通常 breeding と同じく伝搬 (Codex impl-review
                            # [Warning]: warmstart のみ編集強度がズレるのを防ぐ)
                            _cand = mutate(
                                _src,
                                rng,
                                cfg.ga.mutation_rate,
                                max_clause=cfg.ga.max_clause,
                                max_depth=cfg.ga.max_depth,
                                registry=rg_registry,
                                n_edit_max=cfg.ga.n_edit_max,
                            )
                        # genome_from_dict は archive 元 name を復元するため改名必須
                        ws_genomes.append(
                            replace(
                                _cand,
                                name=f"g0_ws{_i}",
                                units=cfg.backtest.units,
                            )
                        )
                _n_rand = cfg.ga.population_size - len(ws_genomes)
                rand_genomes = [
                    random_genome(
                        rng,
                        name=f"g0_i{i}",
                        units=cfg.backtest.units,
                        max_clause=cfg.ga.max_clause,
                        max_depth=cfg.ga.max_depth,
                        registry=rg_registry,
                    )
                    for i in range(_n_rand)
                ]
                population = ws_genomes + rand_genomes
                if ws_genomes:
                    logger.info(
                        "ga.warmstart.injected",
                        n_warmstart=len(ws_genomes),
                        n_anchor=1,
                        n_mutated=max(0, len(ws_genomes) - 1),
                        n_random=_n_rand,
                        warmstart_ratio=cfg.ga.warmstart_ratio,
                        motif_archive=cfg.ga.warmstart_motif_archive,
                    )
                provenance: dict[str, tuple[str | None, str | None]] = {
                    g.name: (None, None) for g in population
                }
            else:
                population, provenance = _breed_next_gen(
                    prev_population, cache, cfg.ga, rg_registry, rng, gen,
                    run_id,
                    selection_pressure=_cp_sel_pressure,
                    margin_threshold=_cp_sel_threshold,
                    robust_selection=_robust_sel,
                )

            for g in population:
                genomes_by_name[g.name] = g

            # lane.generation_count は run_generation で +1 される。ここで使う
            # "この世代 ID" は呼び出し前の generation_count をキャプチャする。
            current_generation = tier1_lane.generation_count
            tier1_lane.population = population
            tier1_lane.provenance = provenance
            summary_out = lane_manager.run_generation(lane_id)
            # T081 step 1: AB pair 集約 (詳細設計 § 3.4.3、 helper 化で test 可能)
            (
                all_ab_b_evaluated_count,
                all_ab_excluded_preflight_count,
                ab_score_source,
            ) = _aggregate_ab_summary(
                summary_out=summary_out,
                all_ab_score_pairs=all_ab_score_pairs,
                b_evaluated_count=all_ab_b_evaluated_count,
                excluded_preflight_count=all_ab_excluded_preflight_count,
                current_score_source=ab_score_source,
            )
            _update_cache(
                cache,
                population,
                archive,
                lane_id,
                current_generation,
                cfg.ga.feasibility,
                stage_c_feasibility_apply=cfg.stage_gate.stage_c_feasibility_apply,
                fold_robust_threshold=cfg.stage_gate.fold_robust_threshold,
                robust_w_pfre=cfg.ga.robust_w_pfre,
                robust_w_sign=cfg.ga.robust_w_sign,
                robust_w_disp=cfg.ga.robust_w_disp,
            )

            best_fp = max(
                (cache[g.name].fitness_pen for g in population),
                default=-math.inf,
            )
            feasible_count = sum(
                1
                for g in population
                if g.name in cache and cache[g.name].feasible
            )
            # T052: stage 別 timing を per_generation に伝搬
            per_generation.append(
                {
                    "generation": gen,
                    "n_evaluated": int(summary_out["n_evaluated"]),
                    "stage_a_pass": int(summary_out["stage_a_pass"]),
                    "stage_b_pass": int(summary_out["stage_b_pass"]),
                    "stage_c_pass": int(summary_out["stage_c_pass"]),
                    "graduation_count": int(summary_out["graduation_count"]),
                    "best_fitness_pen": best_fp,
                    "feasible_count": feasible_count,
                    # T052: stage 別 timing (legacy path で未提供時は 0.0)
                    "stage_a_seconds_total": float(
                        summary_out.get("stage_a_seconds_total", 0.0)
                    ),
                    "stage_a_seconds_max": float(
                        summary_out.get("stage_a_seconds_max", 0.0)
                    ),
                    "stage_b_seconds_total": float(
                        summary_out.get("stage_b_seconds_total", 0.0)
                    ),
                    "stage_b_seconds_max": float(
                        summary_out.get("stage_b_seconds_max", 0.0)
                    ),
                    "stage_c_seconds_total": float(
                        summary_out.get("stage_c_seconds_total", 0.0)
                    ),
                    "stage_c_seconds_max": float(
                        summary_out.get("stage_c_seconds_max", 0.0)
                    ),
                }
            )
            # T052: 世代終了時 RSS ピーク測定
            # pool_pids が空 (sequential or AttributeError fallback) なら
            # None を渡して all_children_* 経路で集計
            # (parallel_eval.measure_peak_rss_mb の契約に従う)
            _pids = genome_evaluator.pool_pids
            peak_rss_per_generation.append(
                measure_peak_rss_mb(pool_pids=_pids if _pids else None)
            )
            prev_population = population

    archive_path = archive.flush()

    best_name, best_entry = _select_best(
        cache,
        cfg.ga.feasibility,
        selection_pressure=_cp_sel_pressure,
        margin_threshold=_cp_sel_threshold,
        robust_selection=_robust_sel,
    )
    best_row = archive.get_row_snapshot(
        lane_id, best_entry.generation, best_name
    )
    best_genome = genomes_by_name[best_name]

    # T033: Stage A diagnostics sidecar を _write_reports の前に flush して、
    # 書き込み成功時のみ summary.json に diagnostics_sidecar field を追加する。
    # --no-report 時は sidecar も skip (reports/ ディレクトリを触らない契約と整合)。
    # T058 PR 5: write_stage_a_provenance に run_context / mode を伝搬 (PR 4 で
    # optional 化された kwargs を production 経路で必ず渡す)。
    sidecar_path_written: Path | None = None
    if not args.no_report:
        sidecar_path = REPO_ROOT / sidecar_relative_path(run_number)
        sidecar_path_written = write_stage_a_provenance(
            diagnostics_collector,
            sidecar_path,
            run_context=run_context,
            mode=cfg.schema_contract.to_mode(),
        )

    # cycle 3 (improve-cycle): Stage A 上位 20% fold robustness sidecar 追加。
    # archive Parquet を入力に、 generation 別 集計を生成し、
    # reports/run-reports/run-{N}/diagnostics/stage_a_top_fold_robustness.parquet に出力。
    # fail-open 一貫化 (read+build+write は write_stage_a_top_fold 内部、 例外は関数内で warning + None)。
    # 詳細: devnotes/20260506-1345-fx-improve-c3/detailed-design.md § C1
    top_fold_path_written: Path | None = None
    if not args.no_report and archive_path is not None and archive_path.exists():
        top_fold_path_written = write_stage_a_top_fold(
            archive_path,
            REPO_ROOT / stage_a_top_fold_relative_path(run_number),
            run_id=run_id,
            dataset_epoch_id=run_context.dataset_epoch_id,
        )

    if not args.no_report:
        _write_reports(
            run_dir=run_dir,
            cfg=cfg,
            run_id=run_id,
            run_number=run_number,
            bundle=bundle,
            per_generation=per_generation,
            best_name=best_name,
            best_entry=best_entry,
            best_genome=best_genome,
            best_row=best_row,
            final_population=prev_population,
            final_population_cache=cache,
            archive_path=archive_path,
            lane_manager=lane_manager,
            cross_pair_mode=cross_pair_mode,
            now=now,
            run_context=run_context,
            effective_max_tasks_per_child=effective_max_tasks_per_child,
            diagnostics_sidecar_path=sidecar_path_written,
            top_fold_sidecar_path=top_fold_path_written,
            peak_rss_per_generation=peak_rss_per_generation,
        )
    else:
        logger.info(
            "run_ga.skip_report",
            run_id=run_id,
            reason="--no-report",
            note="reports/run-reports/ was not touched (archive + cache only)",
        )

    # T081 step 1: RunObservabilityReport を JSON 出力
    # ABDivergenceMetric のみ実値配線、 残り 8 metric は stub default (= 後続 step 2-6 で実値置換)。
    # 詳細設計: devnotes/20260502-2206-todo-T081-observability-real-values/detailed-design.md § 3.4.3
    # --no-report 時は reports/ ディレクトリを触らない契約と整合 (skip).
    if not args.no_report:
        # 診断 log (Codex Round 1 [Warning] 4 取込: preflight 除外可視化)
        logger.info(
            "ga.observability.ab_score_pairs_collected",
            run_id=run_id,
            n_pairs=len(all_ab_score_pairs),
            b_evaluated_count=all_ab_b_evaluated_count,
            excluded_preflight_count=all_ab_excluded_preflight_count,
            score_source=ab_score_source or "noop",
        )
        # ABDivergenceMetric 実値計算 (= list[tuple] → Sequence[Decimal] 2 本に分解)
        a_scores = [Decimal(repr(a)) for a, _ in all_ab_score_pairs]
        b_scores = [Decimal(repr(b)) for _, b in all_ab_score_pairs]
        ab_divergence_metric = compute_ab_divergence_on_b_evaluated(
            a_scores, b_scores
        )
        # 残り 8 metric は default constructor で stub default を取得 (= 後続 step で実値置換)
        observability_report = build_run_observability_report(
            run_id=run_id,
            dataset_epoch_id=run_context.dataset_epoch_id,
            generation_count=cfg.ga.generations,
            ab_divergence=ab_divergence_metric,  # ← step 1 で実値
            q_force_recommendation=build_default_q_force_recommendation(),
            archive_churn=build_default_archive_churn_metric(),
            bypass_ratio=build_default_bypass_ratio_metric(),
            session_entropy=build_default_session_entropy_metric(),
            feasible_ratio=build_default_feasible_ratio_metric(),
            selection=build_default_selection_metric(),
            inflow_consistency=build_default_inflow_consistency_metric(),
            failure=build_default_failure_metric(run_id),
        )
        observability_path = run_dir / "observability.json"
        observability_path.write_text(
            serialize_run_observability_report(observability_report),
            encoding="utf-8",
        )
        logger.info(
            "ga.observability.report_written",
            run_id=run_id,
            path=str(observability_path),
            ab_divergence_status=ab_divergence_metric.status,
            ab_divergence_n_pairs=ab_divergence_metric.n_pairs,
            note="T081 step 1: ABDivergenceMetric 実値、 残 8 metric は stub default",
        )

    # T058 PR 5: run cache JSON に dataset_epoch_id を伝搬 (詳細設計 行 1379-1381)
    RUN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (RUN_CACHE_DIR / f"{run_id}.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "run_number": run_number,
                "dataset_epoch_id": run_context.dataset_epoch_id,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    logger.info(
        "ga.run.done",
        run_id=run_id,
        run_number=run_number,
        best_name=best_name,
        best_fitness=str(best_entry.fitness_pen),
        stage_c_pass=best_entry.stage_c_pass,
    )
    report_field = "skipped(--no-report)" if args.no_report else str(run_dir)
    print(
        f"[done] run_id={run_id} run_number={run_number} "
        f"best={best_name} fitness_pen={best_entry.fitness_pen} "
        f"stage_c={best_entry.stage_c_pass} report={report_field}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
