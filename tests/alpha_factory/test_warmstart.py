"""T101: warmstart pool (load_warmstart_motifs) unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.alpha_factory.warmstart import (
    WARMSTART_MIN_TOTAL_PNL,
    load_warmstart_motifs,
)
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from src.dsl.serialize import genome_to_dict


def _genome(name: str) -> Genome:
    return Genome(
        name=name,
        units=10000,
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="D1", weight=1.0),),
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(
            entry_threshold=0.5, exit_threshold=0.2, max_pos=1, time_stop_min=0
        ),
        risk=RiskConfig(stop_atr=2.0, take_atr=3.0),
    )


def _write_archive(
    path: Path,
    rows: list[dict],
) -> None:
    """rows: list of {name, stage_c_pass, total_pnl, mission_score}."""
    data = {
        "stage_c_pass": [r["stage_c_pass"] for r in rows],
        "total_pnl": [r["total_pnl"] for r in rows],
        "mission_score": [r.get("mission_score") for r in rows],
        "genome_json": [json.dumps(genome_to_dict(_genome(r["name"]))) for r in rows],
    }
    pq.write_table(pa.table(data), path)


def test_load_warmstart_motifs_filters_and_sorts(tmp_path: Path) -> None:
    archive = tmp_path / "arc.parquet"
    _write_archive(
        archive,
        [
            {"name": "good_hi", "stage_c_pass": True, "total_pnl": 60000.0, "mission_score": 0.98},
            {"name": "good_lo", "stage_c_pass": True, "total_pnl": 25000.0, "mission_score": 0.95},
            {"name": "below_pnl", "stage_c_pass": True, "total_pnl": 10000.0, "mission_score": 0.99},
            {"name": "not_c", "stage_c_pass": False, "total_pnl": 70000.0, "mission_score": 0.99},
        ],
    )
    motifs = load_warmstart_motifs(archive)
    names = [g.name for g in motifs]
    # stage_c_pass==True AND total_pnl>=20000 のみ、mission_score 降順
    assert names == ["good_hi", "good_lo"]


def test_load_warmstart_motifs_respects_min_total_pnl_default() -> None:
    assert WARMSTART_MIN_TOTAL_PNL == 20000.0


def test_load_warmstart_motifs_missing_archive_is_empty(tmp_path: Path) -> None:
    assert load_warmstart_motifs(tmp_path / "nope.parquet") == []


def test_load_warmstart_motifs_no_match_is_empty(tmp_path: Path) -> None:
    archive = tmp_path / "arc.parquet"
    _write_archive(
        archive,
        [{"name": "x", "stage_c_pass": False, "total_pnl": 99999.0, "mission_score": 0.9}],
    )
    assert load_warmstart_motifs(archive) == []


def test_load_warmstart_motifs_max_motifs_cap(tmp_path: Path) -> None:
    archive = tmp_path / "arc.parquet"
    rows = [
        {"name": f"g{i}", "stage_c_pass": True, "total_pnl": 30000.0 + i, "mission_score": float(i)}
        for i in range(10)
    ]
    _write_archive(archive, rows)
    motifs = load_warmstart_motifs(archive, max_motifs=3)
    assert len(motifs) == 3
    # mission_score 降順 (i=9,8,7)
    assert [g.name for g in motifs] == ["g9", "g8", "g7"]


def test_load_warmstart_motifs_restored_genome_is_valid(tmp_path: Path) -> None:
    archive = tmp_path / "arc.parquet"
    _write_archive(
        archive,
        [{"name": "m", "stage_c_pass": True, "total_pnl": 30000.0, "mission_score": 0.9}],
    )
    motifs = load_warmstart_motifs(archive)
    assert len(motifs) == 1
    g = motifs[0]
    assert isinstance(g, Genome)
    assert g.units == 10000
    assert len(g.clauses) == 1


class TestGAConfigWarmstart:
    def _ga(self, **kw):
        from src.alpha_factory.config import GAConfig

        base = dict(
            population_size=8, generations=2, crossover_rate=0.7, mutation_rate=0.3,
            tournament_size=3, elite_count=2, max_depth=4,
        )
        base.update(kw)
        return GAConfig(**base)

    def test_warmstart_ratio_default_zero(self) -> None:
        cfg = self._ga()
        assert cfg.warmstart_ratio == 0.0
        assert cfg.warmstart_motif_archive is None

    def test_warmstart_ratio_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="warmstart_ratio must be in"):
            self._ga(warmstart_ratio=1.5)
        with pytest.raises(ValueError, match="warmstart_ratio must be in"):
            self._ga(warmstart_ratio=-0.1)

    def test_warmstart_ratio_valid(self) -> None:
        cfg = self._ga(warmstart_ratio=0.1, warmstart_motif_archive="x.parquet")
        assert cfg.warmstart_ratio == 0.1
        assert cfg.warmstart_motif_archive == "x.parquet"
