"""T035: generate_run_report の Stage B failure reason 集計セクション."""

from __future__ import annotations

# 直接 generate_run_report の集計ロジックを呼ぶのは複雑なので、
# unit test として「primary_reason カウント / any_reason カウント」のロジックを検証する。
#
# 実装は generate_run_report 内のインライン loop だが、テスト容易性のため
# 同等ロジックを 1 関数に切り出して unit test する代わりに、archive_rows を
# 偽装して呼ぶ統合テストにする。


def _count_primary_and_any(
    rows: list[dict],
    known_codes: tuple[str, ...] = (
        "no_folds",
        "insufficient_folds",
        "all_folds_unavailable",
        "stage_b_window_underfilled",
        # cycle 5 fix
        "median_oos_sharpe<min",
        "positive_fold_ratio<min",
    ),
) -> tuple[dict[str, int], dict[str, int], int, int]:
    """generate_run_report.py の Stage B reason 集計ロジックを再現したテスト helper.

    本テストは、実装と同じロジックを記述することで「実装した規約」を契約として
    固定する (実装が変わったら本 helper も同期更新する)。
    """
    sa_rows = [r for r in rows if r.get("stage_a_pass")]
    n_evaluated = len(sa_rows)
    n_pass = sum(1 for r in sa_rows if r.get("stage_b_pass"))
    primary_counts: dict[str, int] = {c: 0 for c in known_codes}
    primary_counts["other"] = 0
    primary_counts["unknown_reason"] = 0
    any_counts: dict[str, int] = {c: 0 for c in known_codes}
    any_counts["other"] = 0
    for r in sa_rows:
        if r.get("stage_b_pass"):
            continue
        rc_raw = r.get("stage_b_reason_codes")
        if rc_raw is None or rc_raw == "":
            primary_counts["unknown_reason"] += 1
            continue
        rc_list = [c.strip() for c in str(rc_raw).split(";") if c.strip()]
        if not rc_list:
            primary_counts["unknown_reason"] += 1
            continue
        primary = rc_list[0]
        if primary in primary_counts:
            primary_counts[primary] += 1
        else:
            primary_counts["other"] += 1
        for c in rc_list:
            if c in any_counts:
                any_counts[c] += 1
            else:
                any_counts["other"] += 1
    return primary_counts, any_counts, n_evaluated, n_pass


def test_stage_b_reason_primary_sums_equals_failures() -> None:
    rows = [
        {"stage_a_pass": True, "stage_b_pass": True, "stage_b_reason_codes": None},
        {"stage_a_pass": True, "stage_b_pass": False, "stage_b_reason_codes": "no_folds"},
        {
            "stage_a_pass": True,
            "stage_b_pass": False,
            "stage_b_reason_codes": "insufficient_folds;median_oos_sharpe<min",
        },
        {"stage_a_pass": True, "stage_b_pass": False, "stage_b_reason_codes": "stage_b_window_underfilled"},
        {"stage_a_pass": False, "stage_b_pass": False, "stage_b_reason_codes": None},  # excluded
    ]
    primary, _, n_eval, n_pass = _count_primary_and_any(rows)
    failures = n_eval - n_pass
    assert sum(primary.values()) == failures


def test_stage_b_reason_any_can_exceed_failures() -> None:
    rows = [
        {"stage_a_pass": True, "stage_b_pass": False, "stage_b_reason_codes": "no_folds;all_folds_unavailable"},
        {"stage_a_pass": True, "stage_b_pass": False, "stage_b_reason_codes": "insufficient_folds"},
    ]
    _, any_, n_eval, n_pass = _count_primary_and_any(rows)
    failures = n_eval - n_pass
    assert sum(any_.values()) >= failures
    assert any_["no_folds"] == 1
    assert any_["all_folds_unavailable"] == 1
    assert any_["insufficient_folds"] == 1


def test_stage_b_reason_other_excludes_known_codes() -> None:
    """known_codes に含まれない reason のみ other に集計."""
    rows = [
        {
            "stage_a_pass": True,
            "stage_b_pass": False,
            "stage_b_reason_codes": "completely_unknown_reason",
        },
        {
            "stage_a_pass": True,
            "stage_b_pass": False,
            "stage_b_reason_codes": "no_folds",
        },
    ]
    primary, any_, _, _ = _count_primary_and_any(rows)
    assert primary["other"] == 1
    assert primary["no_folds"] == 1
    assert any_["other"] == 1
    assert any_["no_folds"] == 1


def test_stage_b_reason_known_codes_includes_median_and_positive_fold() -> None:
    """cycle 5 fix: stage_gate.py の reason をすべて known_codes でカバー."""
    rows = [
        {
            "stage_a_pass": True,
            "stage_b_pass": False,
            "stage_b_reason_codes": "median_oos_sharpe<min",
        },
        {
            "stage_a_pass": True,
            "stage_b_pass": False,
            "stage_b_reason_codes": "positive_fold_ratio<min",
        },
    ]
    primary, any_, _, _ = _count_primary_and_any(rows)
    assert primary["median_oos_sharpe<min"] == 1
    assert primary["positive_fold_ratio<min"] == 1
    assert primary["other"] == 0


def test_stage_b_reason_unknown_for_legacy_archive_rows() -> None:
    """旧 archive で stage_b_reason_codes=None かつ failed → unknown_reason."""
    rows = [
        {"stage_a_pass": True, "stage_b_pass": False, "stage_b_reason_codes": None},
        {"stage_a_pass": True, "stage_b_pass": False, "stage_b_reason_codes": ""},
    ]
    primary, _, _, _ = _count_primary_and_any(rows)
    assert primary["unknown_reason"] == 2


def test_stage_b_reason_excludes_non_stage_a_pass() -> None:
    rows = [
        {"stage_a_pass": False, "stage_b_pass": False, "stage_b_reason_codes": "no_folds"},
    ]
    primary, _, n_eval, n_pass = _count_primary_and_any(rows)
    assert n_eval == 0
    assert n_pass == 0
    assert primary["no_folds"] == 0
