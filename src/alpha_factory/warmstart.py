"""T101: warmstart pool — 既知 mission/Stage-C 通過個体を GA 初期集団に注入する。

seed-locked な GA 探索 (seed により mission 個体到達可否が分岐) に対し、archive から
``stage_c_pass==True AND total_pnl>=20000`` の genome を抽出して初期集団に注入し、
mission 個体を **seed 非依存に保持/再発見** する再現性確保のための足場。

- 評価関数・閾値・selection・GA dynamics は不変 (注入個体も同じ live_criteria で評価)。
- ``warmstart_ratio=0.0`` (default) で本経路は呼ばれず挙動完全不変。
- fail-soft: archive 不在/読込失敗/該当個体ゼロ なら ``[]`` を返し warmstart なしで継続。

設計: devnotes/20260521-0753-fx-improve/detailed-design.md (Codex design-review APPROVED)
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from src.dsl.genome import Genome
from src.dsl.serialize import genome_from_dict

logger = structlog.get_logger(__name__)

# 注入 motif 数の上限 (過大注入防止)。
DEFAULT_MAX_MOTIFS = 64
# motif 採用の最低 total_pnl (T101 設計: Stage C 20k+ 系統)。
WARMSTART_MIN_TOTAL_PNL = 20000.0


def load_warmstart_motifs(
    archive_path: Path | str,
    *,
    max_motifs: int = DEFAULT_MAX_MOTIFS,
    min_total_pnl: float = WARMSTART_MIN_TOTAL_PNL,
) -> list[Genome]:
    """archive Parquet から warmstart motif (Genome list) を抽出する。

    抽出条件: ``stage_c_pass==True AND total_pnl>=min_total_pnl``。
    ``mission_score`` (なければ ``fitness_pen``) 降順で sort し先頭 ``max_motifs`` 件を返す
    (motifs[0] = 最良個体 = 非 mutate アンカー注入の対象)。

    fail-soft: 不在/読込失敗/該当ゼロ/genome 復元失敗は warning ログのみで部分/空リスト返却。
    """
    path = Path(archive_path)
    if not path.exists():
        logger.warning("warmstart.archive_missing", path=str(path))
        return []
    try:
        import pyarrow.parquet as pq

        table = pq.read_table(path)
        df = table.to_pandas()
    except Exception as exc:  # pragma: no cover - I/O 異常系
        logger.warning(
            "warmstart.archive_read_failed", path=str(path),
            error=str(exc), error_type=type(exc).__name__,
        )
        return []

    required = {"stage_c_pass", "total_pnl", "genome_json"}
    if not required.issubset(df.columns):
        logger.warning(
            "warmstart.archive_schema_mismatch",
            path=str(path), missing=sorted(required - set(df.columns)),
        )
        return []

    import pandas as pd

    sel = df[(df["stage_c_pass"] == True) & (  # noqa: E712 - pandas mask
        pd.to_numeric(df["total_pnl"], errors="coerce") >= min_total_pnl
    )].copy()
    if sel.empty:
        logger.warning(
            "warmstart.no_motif", path=str(path), min_total_pnl=min_total_pnl
        )
        return []

    # 降順 sort キー: mission_score 優先、なければ fitness_pen。
    sort_col = (
        "mission_score" if "mission_score" in sel.columns
        else ("fitness_pen" if "fitness_pen" in sel.columns else None)
    )
    if sort_col is not None:
        sel["_sortkey"] = pd.to_numeric(sel[sort_col], errors="coerce")
        sel = sel.sort_values("_sortkey", ascending=False, na_position="last")

    motifs: list[Genome] = []
    for gj in sel["genome_json"].tolist():
        if len(motifs) >= max_motifs:
            break
        try:
            d = json.loads(gj) if isinstance(gj, str) else gj
            motifs.append(genome_from_dict(d))
        except Exception as exc:
            logger.warning(
                "warmstart.genome_restore_failed",
                error=str(exc), error_type=type(exc).__name__,
            )
            continue

    logger.info(
        "warmstart.motifs_loaded",
        path=str(path), n_motifs=len(motifs), min_total_pnl=min_total_pnl,
    )
    return motifs
