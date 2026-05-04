"""Tests for scripts/alpha_factory/analyze_stage_a_diagnostic.py.

Run-28 施策 C1 (= devnotes/20260504-1236-fx-improve/detailed-design.md, design-review Round 3 APPROVED).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import pytest

from scripts.alpha_factory.analyze_stage_a_diagnostic import (
    P1_RAW_MAX_THRESHOLD,
    SENTINEL_THRESHOLD,
    compute_diversity,
    compute_extra_metrics,
    compute_fitness_pen_decomposition,
    compute_penalty_effect,
    compute_plateau_length,
    compute_trade_count_buckets,
    compute_trade_sharpe_by_generation,
    compute_valid_mask,
    diagnose_root_cause,
)


def _make_df(rows: list[dict]) -> pd.DataFrame:
    """archive Parquet 形式の最小 DataFrame を構築."""
    base_cols = {
        "generation": 0,
        "individual_name": "g0_i0",
        "fitness_pen": 0.0,
        "fitness_raw": 0.0,
        "trade_count": 100,
        "stage_a_pass": False,
        "stage_b_pass": False,
        "stage_c_pass": False,
        "trade_sharpe_raw": 0.0,
        "n_nodes": 2,
        "active_clause": 1,
        "run_number": 27,
    }
    return pd.DataFrame([{**base_cols, **r} for r in rows])


# --- compute_valid_mask ---


def test_valid_mask_excludes_sentinel():
    df = _make_df([
        {"fitness_pen": -1e9, "trade_sharpe_raw": 0.001},
        {"fitness_pen": -0.05, "trade_sharpe_raw": -0.05},
    ])
    mask = compute_valid_mask(df)
    assert list(mask) == [False, True]


def test_valid_mask_excludes_nan_inf():
    df = _make_df([
        {"fitness_pen": float("nan"), "trade_sharpe_raw": 0.001},
        {"fitness_pen": float("inf"), "trade_sharpe_raw": 0.001},
        {"fitness_pen": -0.05, "trade_sharpe_raw": float("nan")},
        {"fitness_pen": -0.05, "trade_sharpe_raw": -0.05},
    ])
    mask = compute_valid_mask(df)
    assert list(mask) == [False, False, False, True]


# --- buckets ---


def test_trade_count_buckets_boundaries():
    df = _make_df([
        {"trade_count": 0},
        {"trade_count": 1},
        {"trade_count": 49},
        {"trade_count": 50},
        {"trade_count": 499},
        {"trade_count": 500},
        {"trade_count": 1499},
        {"trade_count": 1500},
        {"trade_count": 5000},
    ])
    buckets = compute_trade_count_buckets(df)
    counts = {b["bucket"]: b["n"] for b in buckets}
    assert counts == {"0": 1, "1-49": 2, "50-499": 2, "500-1499": 2, ">=1500": 2}


# --- fitness_pen 分解 ---


def test_fitness_pen_decomposition_with_alpha():
    df = _make_df([
        {"trade_sharpe_raw": 0.001, "fitness_pen": -0.005},  # size_norm = 0.006/0.03 = 0.2
        {"trade_sharpe_raw": 0.0, "fitness_pen": -0.01},      # size_norm = 0.01/0.03 = 0.333
    ])
    out = compute_fitness_pen_decomposition(df, alpha=0.03)
    assert out["_alpha_used"] == 0.03
    assert out["trade_sharpe_raw"]["max"] == pytest.approx(0.001)
    assert out["fitness_pen"]["max"] == pytest.approx(-0.005)
    assert out["size_norm_inferred"]["max"] == pytest.approx(0.333, abs=0.001)


def test_fitness_pen_decomposition_alpha_none():
    df = _make_df([{"trade_sharpe_raw": 0.001, "fitness_pen": -0.005}])
    out = compute_fitness_pen_decomposition(df, alpha=None)
    assert out["_alpha_used"] is None
    assert out["size_norm_inferred"]["max"] is None
    assert "参考値扱い" in out["_size_norm_note"]


# --- penalty effect ---


def test_penalty_effect_kills_raw_positive():
    df = _make_df([
        # raw>0 で penalty で潰される個体 (= K に含まれる)
        {"trade_sharpe_raw": 0.001, "fitness_pen": -0.005},
        {"trade_sharpe_raw": 0.002, "fitness_pen": -0.003},
        # raw>0 で通過する個体
        {"trade_sharpe_raw": 0.05, "fitness_pen": 0.04},
        # raw<=0 (= 関係ない)
        {"trade_sharpe_raw": -0.01, "fitness_pen": -0.02},
    ])
    pe = compute_penalty_effect(df)
    assert pe["n_raw_positive"] == 3
    assert pe["n_raw_positive_and_penalty_killed"] == 2
    assert pe["n_raw_positive_and_pass"] == 1


# --- plateau ---


def test_plateau_length_isclose():
    rows = []
    for gen in range(5):
        rows.append({"generation": gen, "fitness_pen": -0.05, "trade_sharpe_raw": -0.04})
    # 後半 3 世代で best が -0.001 で安定
    for gen in range(5, 8):
        rows.append({"generation": gen, "fitness_pen": -0.001 + 1e-15, "trade_sharpe_raw": 0.001})
    df = _make_df(rows)
    plateau, start = compute_plateau_length(df)
    assert plateau == 3
    assert start == 5


# --- diversity ---


def test_diversity_rolls_per_generation():
    df = _make_df([
        {"generation": 0, "n_nodes": 4, "active_clause": 1},
        {"generation": 0, "n_nodes": 2, "active_clause": 1},
        {"generation": 1, "n_nodes": 3, "active_clause": 2},
        {"generation": 1, "n_nodes": 3, "active_clause": 2},
    ])
    out = compute_diversity(df)
    assert out[0]["generation"] == 0
    assert out[0]["n_nodes_mean"] == pytest.approx(3.0)
    assert out[0]["active_clause_unique"] == 1
    assert out[1]["n_nodes_mean"] == pytest.approx(3.0)
    assert out[1]["n_nodes_std"] == pytest.approx(0.0)


# --- diagnose_root_cause ---


def _decomp_with_raw_max(raw_max: float) -> dict:
    return {
        "trade_sharpe_raw": {"max": raw_max, "mean": raw_max / 2, "std": 0.01},
        "fitness_pen": {"max": raw_max - 0.01, "mean": -0.05, "std": 0.05},
    }


def test_diagnose_p1_high_confidence():
    """raw_max < 0.005 + max_clause >=2 → P1 high."""
    d, rationale, meta = diagnose_root_cause(
        _decomp_with_raw_max(0.001),
        diversity=[{"n_nodes_std": 1.0, "active_clause_unique": 2, "generation": 0}, {"n_nodes_std": 0.9, "active_clause_unique": 2, "generation": 1}],
        penalty_effect={"n_raw_positive": 1, "n_raw_positive_and_penalty_killed": 1, "n_raw_positive_and_pass": 0},
        n_valid=100,
        run_effective_config={"max_clause": 2, "_source": "run_effective"},
    )
    assert d == "P1"
    assert meta["confidence"] == "high"
    assert "P3" in meta["evaluated_hypotheses"]


def test_diagnose_p1_with_p3_unevaluable_max_clause_1():
    """raw_max < 0.005 + max_clause=1 → P1 high, P3 N/A."""
    d, rationale, meta = diagnose_root_cause(
        _decomp_with_raw_max(0.001),
        diversity=[],
        penalty_effect={"n_raw_positive": 0, "n_raw_positive_and_penalty_killed": 0, "n_raw_positive_and_pass": 0},
        n_valid=600,
        run_effective_config={"max_clause": 1, "_source": "run_effective"},
    )
    assert d == "P1"
    assert meta["confidence"] == "high"
    assert "P3" not in meta["evaluated_hypotheses"]
    assert "non_evaluable_reason" in meta["falsification"]["P3"]
    assert "max_clause=1" in meta["falsification"]["P3"]["non_evaluable_reason"]


def test_diagnose_p2_match():
    """raw>0 個体多、 penalty で K=10 個 kill (>= max(3, 0.01*100)=3) → P2."""
    d, rationale, meta = diagnose_root_cause(
        _decomp_with_raw_max(0.05),  # raw_max >= 0.005 = P1 不成立
        diversity=[],
        penalty_effect={"n_raw_positive": 20, "n_raw_positive_and_penalty_killed": 10, "n_raw_positive_and_pass": 10},
        n_valid=100,
        run_effective_config={"max_clause": 1, "_source": "run_effective"},
    )
    assert d == "P2"


def test_diagnose_p3_match_with_clause_2():
    """max_clause=2 + n_nodes std drop > 0.5 + active_unique=1 → P3."""
    d, rationale, meta = diagnose_root_cause(
        _decomp_with_raw_max(0.05),  # P1 不成立
        diversity=[
            {"n_nodes_std": 1.0, "active_clause_unique": 2, "generation": 0},
            {"n_nodes_std": 0.3, "active_clause_unique": 1, "generation": 14},
        ],
        penalty_effect={"n_raw_positive": 1, "n_raw_positive_and_penalty_killed": 1, "n_raw_positive_and_pass": 0},
        n_valid=100,
        run_effective_config={"max_clause": 2, "_source": "run_effective"},
    )
    assert d == "P3"


def test_diagnose_inconclusive_multiple_match():
    """P1 + P2 同時 match → INCONCLUSIVE low."""
    d, rationale, meta = diagnose_root_cause(
        _decomp_with_raw_max(0.001),  # P1 match
        diversity=[],
        penalty_effect={"n_raw_positive": 20, "n_raw_positive_and_penalty_killed": 10, "n_raw_positive_and_pass": 10},  # P2 match
        n_valid=100,
        run_effective_config={"max_clause": 1, "_source": "run_effective"},
    )
    assert d == "INCONCLUSIVE"
    assert meta["confidence"] == "low"


def test_diagnose_inconclusive_no_match():
    """全仮説 unmatched → INCONCLUSIVE."""
    d, rationale, meta = diagnose_root_cause(
        _decomp_with_raw_max(0.05),  # P1 不成立
        diversity=[],
        penalty_effect={"n_raw_positive": 1, "n_raw_positive_and_penalty_killed": 1, "n_raw_positive_and_pass": 0},  # P2 不成立 (K=1 < 3)
        n_valid=100,
        run_effective_config={"max_clause": 1, "_source": "run_effective"},
    )
    assert d == "INCONCLUSIVE"


def test_diagnose_p3_unevaluable_config_unavailable():
    """max_clause=None (= summary 不在) → P3 non_evaluable + confidence cap medium."""
    d, rationale, meta = diagnose_root_cause(
        _decomp_with_raw_max(0.001),
        diversity=[],
        penalty_effect={"n_raw_positive": 0, "n_raw_positive_and_penalty_killed": 0, "n_raw_positive_and_pass": 0},
        n_valid=100,
        run_effective_config={"max_clause": None, "_source": "fallback_default"},
    )
    assert d == "P1"
    assert meta["confidence"] == "medium"  # cap by config_unavailable
    assert "summary.json" in meta["falsification"]["P3"]["non_evaluable_reason"]


# --- extra metrics ---


def test_extra_metrics_counts():
    df = _make_df([
        {"generation": 0, "trade_sharpe_raw": 0.001, "fitness_pen": -0.005},
        {"generation": 0, "trade_sharpe_raw": 0.05, "fitness_pen": 0.04},
        {"generation": 0, "trade_sharpe_raw": -0.01, "fitness_pen": -0.02},
        {"generation": 0, "trade_sharpe_raw": 0.0, "fitness_pen": -1e9},  # sentinel
        {"generation": 1, "trade_sharpe_raw": 0.0, "fitness_pen": -1e9},  # sentinel
    ])
    em = compute_extra_metrics(df)
    assert em["raw_positive_count"] == 2
    assert em["fitness_pen_positive_count"] == 1
    assert em["sentinel_by_generation"] == {0: 1, 1: 1}
    assert em["best_generation"] == 0
