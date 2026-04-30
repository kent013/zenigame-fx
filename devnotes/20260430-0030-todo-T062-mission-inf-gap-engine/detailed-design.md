# 詳細設計: T062 — mission_inf_gap engine

## 使命・制約 (絶対遵守)

zenigame-fx Alpha Factory 使命: live_criteria 全指標同時充足 + (ii-lite) 通過。 絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。 禁止事項 1-7 (synthesis § 1.3) + 8 (archive スキーマ伝搬漏れ、 T058 対応済)。 コーディングルール: バグ修正テストファースト / 全施策テスト必須・振る舞いベース命名 / uv 必須 / ruff & mypy 通過 / Python 3.13。

## 概念設計リファレンス

`devnotes/20260430-0030-todo-T062-mission-inf-gap-engine/conceptual-design.md` (Round 2 で APPROVED)

## 2026-04-30 注記: synthesis Round 21 改訂済

本詳細設計策定時 (2026-04-30 00:42 JST) は synthesis § 8.3 (CA #5 = `mission_margin = -mission_inf_gap`) の命名と数式が乖離しており、 暫定 SSOT として本詳細設計内の `mission_signed_margin` 実装を採用していた。 **2026-04-30 10:45 JST に synthesis Round 21 改訂 PR (`devnotes/20260430-1045-synthesis-revise-mission-signed-margin/`) が成立**し、 synthesis § 8.3 の CA #5 が `mission_signed_margin = min(slack_*)` に SSOT 昇格、 `mission_margin` は BACKWARD COMPAT 整理に確定。 本詳細設計内の「synthesis 改訂 PR で修正予定」 「暫定 SSOT」 等の表記は **synthesis Round 21 改訂後の事実反映として「改訂済」 と読み替える**。 実装内容 (MissionGapResult dataclass / compute_mission_signed_margin / `MISSION_SIGNED_MARGIN_INFEASIBLE_SENTINEL=-inf`) は不変、 docstring / コメントは Phase 2 実装時に「synthesis § 8.3 (Round 21 改訂後) の SSOT 実装」 の文言で確定する。

## Round 2 review 反映 (Codex 概念レビュー)

| 概念 Round 2 [Warning/Suggestion] | 詳細設計での吸収 |
|---|---|
| [W1] synthesis § 8.3 と実装方針 (CA #5 = mission_signed_margin) の暫定乖離を明文化 | 詳細設計冒頭 + DoD で「**暫定 SSOT は T062/T067 設計**、 synthesis § 8.3 は T064 完了後に改訂 PR」 を明記。 **【改訂済 2026-04-30】synthesis Round 21 改訂 PR (`devnotes/20260430-1045-synthesis-revise-mission-signed-margin/`) で CA #5 = mission_signed_margin が synthesis SSOT に昇格**、 暫定乖離は解消 |
| [W2] constrained-domination の degenerate case (全個体 infeasible 世代) | T065 詳細設計時に確定する旨を T065 申し送りに明記。 T062 では infeasible 同士の序列化用に **`constraint_violation` 有限値 field** を提供 (詳細 Round 1 [C1] 反映) |
| [W3] per_metric_shortfall 表示は is_feasible とセット解釈固定 | docstring に「**always interpret with `is_feasible` flag**」 + 「infeasible 時は raw 計算値、 strategic_* 時は意味損なわれ可能性」 を明記 |
| [S1] doctest / 仕様表に 4 代表ケース追加 | テスト計画に「全達成 / 1 指標不足 / infeasible / NaN」 4 ケースを **explicit unit test** で追加 (DoD 文言統一、 詳細 Round 1 [S4]) |
| [S2] mission_margin の互換目的明記 + 実運用は mission_signed_margin | dataclass field comment 先頭に「**(DEPRECATED-COMPAT: synthesis § 8.3 命名通り、 数式と命名が乖離。 実運用 ordering は mission_signed_margin を使うこと)**」 (詳細 Round 1 [S2] 反映) |
| [S3] +inf/-inf 比較規約節 | 専用節「Sentinel Comparison Convention」 を新設 |

## 詳細 Round 1 review 反映 (Codex 詳細レビュー)

| 詳細 Round 1 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [C1] infeasible 個体の序列化仕様が内部矛盾 (全 infeasible に +inf 同値で violation 序列不能、 Deb 2000 違反) | **`mission_inf_gap` から sentinel +inf を撤廃**、 純粋に synthesis § 6.4 式 = `max(max(0, -slack_m))` を返す (is_feasible に依存しない有限値 0 以上)。 sentinel `MISSION_GAP_INFEASIBLE_SENTINEL` 削除。 新規 `constraint_violation: float` field を `MissionGapResult` に追加 (Deb 2000 の infeasible 同士 violation 序列化用、 is_feasible=True なら 0.0、 is_feasible=False なら 4 指標 max(0, -slack) 同値の有限値)。 `MISSION_SIGNED_MARGIN_INFEASIBLE_SENTINEL=-inf` は維持 (archive eviction 用、 比較規約上問題なし) |
| [C2] NaN fail-fast が feasible 分岐にしか効かない (is_feasible=False 分岐で slack 検証 skip) | **`evaluate_mission_inf_gap` の is_feasible 判定**前** に slack 4 指標の NaN 検証を実施**。 NaN は engine 合成 bug indicator で全経路 fail-fast、 is_feasible に依存しない |
| [W1] per_metric_shortfall infeasible 時の値 (`{k: inf}` 固定) が「raw」 と不整合 | infeasible 時も raw 計算値 (`max(0, -slack_m)`) を返す。 NaN 防御で +inf になり得るが、 docstring に「raw 計算値、 +inf 寄与は upstream slack=-inf に対応」 を明記 |
| [W2] `frozen dataclass` だが `per_metric_shortfall: dict` は外部から変更可能 | `per_metric_shortfall: types.MappingProxyType[str, float]` (immutable view) に変更。 dataclass `__post_init__` で MappingProxyType wrap |
| [W3] C2 parallel-path grep DoD で `import src.alpha_factory.mission_inf_gap as ...` 等を取りこぼす | grep 段階を 5 段階化 (alias import / relative import 追加)、 T061 の 4 段階を superset 化 |
| [W4] 学術引用が略記のみ (Deb 2000 / Deb et al. 2002) | full citation + DOI 形式に書き直し: `https://doi.org/10.1016/S0045-7825(99)00389-8` (Deb 2000)、 `https://doi.org/10.1109/4235.996017` (NSGA-II) |
| [S1] `MissionGapResult` に `constraint_violation` 別 field、 `mission_inf_gap` を § 6.4 純粋式に限定 | 上記 [C1] と統合済 |
| [S2] `mission_margin` に @deprecated 相当コメント強化 | dataclass field 先頭に `(DEPRECATED-COMPAT: ...)` prefix、 docstring に「**実運用 ordering は mission_signed_margin / constraint_violation を使うこと**」 |
| [S3] infeasible 同士の順位付け契約テスト (pending/xfail) | `test_infeasible_constraint_violation_ordering_contract_for_t065` を pytest.mark.xfail で追加、 T065 実装後に xfail 解除 |
| [S4] 4 代表ケースは doctest or unit test 統一 | **explicit unit test** に統一 (doctest は外部依存があるため。 DoD 文言「explicit unit test」 で固定) |

## 施策一覧 (Phase 1: T062 PR、 Phase 2 は別 PR)

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | `mission_inf_gap.py` 新規 (MissionGapResult dataclass + 4 helper + top-level entry + sentinel const) | `src/alpha_factory/mission_inf_gap.py` (新規) | Critical |
| 2 | `tests/alpha_factory/test_mission_inf_gap.py` 新規 (4 代表ケース + invariant 連鎖 + sentinel 比較 + NaN handling) | (新規) | Critical |

**Phase 1 (T062 PR) スコープ = 上記 2 施策**。 既存 GA / archive / cross_pair / swim_lane への組込は **Phase 2 (T065-T067 と同時)** で実施。 T062 PR 単独 merge で runtime に影響なし。

**SSOT 宣言 (Round 2 [W1] 反映、 synthesis Round 21 改訂済)**: `MissionGapResult.mission_signed_margin` は archive CA #5 ordering の SSOT。 ~~synthesis § 8.3 の `mission_margin = -mission_inf_gap` 命名は T064 PR 完了後に改訂 PR で修正予定。 それまで本詳細設計が runtime SSOT~~。 → **synthesis Round 21 改訂 PR (2026-04-30) で synthesis § 8.3 の CA #5 が `mission_signed_margin = min(slack_*)` に SSOT 昇格、 `mission_margin` は BACKWARD COMPAT 整理。 本詳細設計と synthesis 間の乖離は解消、 暫定 SSOT は確定 SSOT に格上げ。**

---

## 施策 1: `mission_inf_gap.py` 新規作成

### 変更箇所

- ファイル: `src/alpha_factory/mission_inf_gap.py` (新規)

### 波及変更

- `AGENTS.md`: なし (Phase 2 で synthesis 改訂 PR と同時に追記候補)
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/*.md`: なし

### 変更後コード

```python
"""T062: mission_inf_gap engine — synthesis § 6.4 / § 6.5 / § 8.3 確定式の単一実装.

詳細:
- 概念設計: devnotes/20260430-0030-todo-T062-mission-inf-gap-engine/conceptual-design.md
- synthesis § 6.4 (mission_inf_gap)、 § 6.5 (Pareto 3 軸)、 § 8.3 (archive eviction)、 § 17 (用語)
- T061 依存: CanonicalFiveResult.slack_sharpe / slack_pnl / slack_dd / slack_tc を消費

Phase 1 (本 TODO): 単体実装 + テストのみ、 GA / archive / cross_pair 未変更。
Phase 2 (別 PR): T065-T067 と同時、 7 箇所同時更新 (Phase 2 申し送り参照)。

SSOT 宣言 (synthesis Round 21 改訂済):
- mission_signed_margin は archive CA #5 ordering の SSOT (synthesis § 8.3 と整合)
- synthesis § 8.3 旧版 (`mission_margin = -mission_inf_gap`) は数式矛盾のため
  Round 21 改訂で `mission_signed_margin = min(slack_*)` に SSOT 昇格、 `mission_margin`
  は BACKWARD COMPAT 整理。 本 module の `compute_mission_signed_margin` が SSOT 実装。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping

from src.alpha_factory.canonical_metrics import CanonicalFiveResult

__all__ = [
    # DataClasses
    "MissionGapResult",
    # Constants
    "MISSION_SIGNED_MARGIN_INFEASIBLE_SENTINEL",
    "MISSION_INF_GAP_METRIC_KEYS",
    # Top-level entry
    "evaluate_mission_inf_gap",
    # Helpers
    "compute_mission_inf_gap_from_slacks",
    "compute_mission_margin",
    "compute_mission_signed_margin",
    "compute_constraint_violation",
    "extract_per_metric_shortfalls",
]


# ---------------------------------------------------------------------------
# Constants (synthesis § 6.4 / § 6.5 / § 8.3 厳密準拠)
# ---------------------------------------------------------------------------

# Note (詳細 Round 1 [C1] 反映): MISSION_GAP_INFEASIBLE_SENTINEL=+inf を撤廃。
# mission_inf_gap は純粋に synthesis § 6.4 式 (= max(max(0, -slack_m))) を返し、
# is_feasible=False 個体の序列化は新規 `constraint_violation` field で対応。
# 全個体に +inf を入れると Deb 2000 の infeasible 同士 violation 序列が成立しないため。

MISSION_SIGNED_MARGIN_INFEASIBLE_SENTINEL: Final[float] = float("-inf")
"""is_feasible=False 時の mission_signed_margin (archive CA #5 ordering 用 sentinel).
margin が -inf なら archive eviction で最低 priority (= 真っ先に追い出される).
Note: 全 infeasible 個体が -inf 同値になるため、 archive 内 infeasible 同士の優先順位は
constraint_violation 等 secondary key で tie-break する責務 (T067 lex 順序参照)."""

MISSION_INF_GAP_METRIC_KEYS: Final[tuple[str, ...]] = ("sharpe", "pnl", "dd", "tc")
"""synthesis § 6.4 確定値: mission_inf_gap は 4 指標のみ (win_rate 含まない).
canonical 5 worst gate は別 (T061 が担当)。 本 const は machine-readable な型強制で
slack_wr の混入を防ぐ."""


# ---------------------------------------------------------------------------
# Output DataClass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MissionGapResult:
    """Pareto 3 軸 f3 + archive eviction 用 mission gap / margin 結果.

    実運用 ordering 規約 (詳細 Round 1 [C1] / [S1] / [S2] 反映):
    - **Pareto 3 軸 f3 (NSGA-II minimize)**: `mission_inf_gap` を使う (純粋 § 6.4 式、 sentinel なし)
    - **NSGA-II constrained-domination (T065 実装、 Deb 2000)**:
        - feasible vs infeasible: `is_feasible` flag で feasible が dominate
        - infeasible vs infeasible: `constraint_violation` 小さい方が dominate
        - feasible vs feasible: `mission_inf_gap` 等 Pareto 軸で通常比較
    - **archive CA #5 (eviction lex 順序、 上位ほど残す)**: **`mission_signed_margin` を使う**
        (synthesis § 8.3 の `mission_margin = -mission_inf_gap` 命名は数式矛盾のため、
        実運用は signed margin で行う。 暫定 SSOT は本 module、 synthesis § 8.3 は
        T064 PR 完了後に改訂予定)
    - **観測 / 診断**: `per_metric_shortfall` を使う (always with `is_feasible` flag)

    Sentinel Comparison Convention (Round 2 [S3] / 詳細 Round 1 [C1] 反映):
    - mission_inf_gap: 値域 [0, +inf)、 sentinel なし。 Pareto front は他軸 (f1=net_pnl,
      f2=max_dd) と組合せた支配関係で決定。 infeasible 個体は constrained-domination
      (T065) で feasible 集団から確実に分離される
    - constraint_violation: 値域 [0, +inf)、 sentinel なし、 finite scalar。 feasible 個体は
      0.0、 infeasible 個体は max(0, -slack_m) の値 (mission_inf_gap と同値だが、 概念上は
      infeasible 序列化用のため別 field)。 NaN は ValueError raise (caller 責務)
    - mission_signed_margin = -inf: Python `<` 比較で常に最小、 archive eviction で最低 priority。
      全 infeasible が -inf 同値、 secondary key (T067 lex 順序、 例: -constraint_violation)
      で tie-break する責務
    - per_metric_shortfall: MappingProxyType (frozen dataclass の immutable 性を保つため、
      詳細 Round 1 [W2] 反映)。 NaN は ValueError、 +inf 寄与は upstream slack=-inf 由来

    Field 詳細:

    - **mission_inf_gap**: synthesis § 6.4 確定式 (Pareto f3 minimize 用、 純粋計算)
        - = `max(max(0, -slack_sharpe), max(0, -slack_pnl), max(0, -slack_dd), max(0, -slack_tc))`
        - 値域: [0, +inf)
        - 4 指標全達成 → 0.0、 1 指標以上未達 → > 0、 slack=-inf → +inf
        - **is_feasible に依存しない有限値計算** (詳細 Round 1 [C1] 反映、 sentinel +inf 撤廃)

    - **constraint_violation**: NSGA-II constrained-domination (Deb 2000) 用 violation 量
        - = mission_inf_gap (現案では同値、 将来 invariant violation count を加算する余地あり)
        - **値域: [0, +inf]** (詳細 Round 2 [W1] 反映: slack=-inf 由来で +inf を取り得る)
        - is_feasible=True → 0.0
        - is_feasible=False → > 0 (infeasible 個体間の序列化に使用、 T065 担当)
        - infeasible 個体間で比較可能なスカラー (詳細 Round 1 [C1] 反映)
        - **重要 (詳細 Round 2 [W2] 反映)**: 現仕様では 4 slack 由来のみ。 `is_feasible=False`
          の原因が slack 外 (例: synthesis § 6.6 の `session_close_drop_count > 0` /
          `negative_equity_drop_open_count > 0` のみで slack は問題なし) の場合、
          constraint_violation は 4 slack 計算値 (potentially 0 or 小さい値) になる。
          T065 (constrained-domination) では「invariant violation の有無を Deb 2000 比較に
          どう組込むか」 を明文化する必要 (T065 申し送り、 例: `constraint_violation +
          invariant_violation_penalty * Σ(strategic_* counts)` 等)

    - **mission_margin** (DEPRECATED-COMPAT: synthesis § 8.3 命名通り、 数式と命名が乖離。
      **実運用 ordering は mission_signed_margin / constraint_violation を使うこと**):
        - = -mission_inf_gap
        - 値域: (-inf, 0]、 達成超過余裕は表現できない (4 指標全達成個体は一律 0.0)
        - is_feasible=False → -mission_inf_gap (= negative finite or -inf)

    - **mission_signed_margin** (実運用 SSOT、 archive CA #5 ordering 用):
        - = min(slack_sharpe, slack_pnl, slack_dd, slack_tc)
        - 値域: feasible なら任意実数、 正値=4 指標全余裕、 負値=1 指標以上不足
        - is_feasible=False → -inf (MISSION_SIGNED_MARGIN_INFEASIBLE_SENTINEL)

    - **per_metric_shortfall**: 4 指標別 max(0, -slack_m) immutable mapping (diagnostic only)
        - keys: "sharpe" / "pnl" / "dd" / "tc"
        - 型: `MappingProxyType[str, float]` (frozen dataclass 保護、 詳細 Round 1 [W2])
        - **always interpret with `is_feasible` flag** (Round 2 [W3] 反映): infeasible 時も
          raw 計算値を返す (詳細 Round 1 [W1])、 strategic_* 時は slack 意味損なわれ可能性

    - **is_feasible**: T061 InvariantFlags.is_feasible を継承 (engine 連鎖)
    """

    mission_inf_gap: float
    constraint_violation: float
    mission_margin: float
    mission_signed_margin: float
    per_metric_shortfall: Mapping[str, float]
    is_feasible: bool


# ---------------------------------------------------------------------------
# Helpers (pure functions)
# ---------------------------------------------------------------------------


def _validate_slacks_dict(slacks: dict[str, float]) -> None:
    """slacks dict が必須 4 key を持ち、 値が finite or +-inf であることを検証.

    NaN 検出時は ValueError raise (caller 修正責務、 Round 2 [W2] fail-fast 方針)。
    +inf / -inf は許容 (T061 の signed slack で +inf=極端な余裕、 -inf=極端な不足を表現可能).
    """
    missing_keys = set(MISSION_INF_GAP_METRIC_KEYS) - set(slacks.keys())
    if missing_keys:
        raise ValueError(
            f"slacks missing required keys: {sorted(missing_keys)}. "
            f"Required: {MISSION_INF_GAP_METRIC_KEYS}"
        )
    for key in MISSION_INF_GAP_METRIC_KEYS:
        value = slacks[key]
        if math.isnan(value):
            raise ValueError(
                f"slacks[{key!r}] is NaN; engine composition bug indicator. "
                f"caller must fix upstream (T061 signed slack 計算)."
            )


def compute_mission_inf_gap_from_slacks(slacks: dict[str, float]) -> float:
    """4 指標 signed slack から mission_inf_gap を計算 (synthesis § 6.4 厳密).

    式: mission_inf_gap = max(max(0, -slacks[m]) for m in MISSION_INF_GAP_METRIC_KEYS)

    Args:
        slacks: T061 signed slack dict (必須 4 key: sharpe / pnl / dd / tc)
            slack_wr は無視 (synthesis § 6.4 で win_rate を含まない)

    Returns:
        mission_inf_gap >= 0
        - +inf: 1 指標以上が -inf (極端な不足)
        - 0.0: 4 指標全達成
        - 正値: 1 指標以上未達

    Raises:
        ValueError: slacks に必須 key 欠損 or NaN を検出した場合 (caller 修正責務)
    """
    _validate_slacks_dict(slacks)
    return max(max(0.0, -slacks[k]) for k in MISSION_INF_GAP_METRIC_KEYS)


def compute_mission_margin(mission_inf_gap: float) -> float:
    """synthesis § 8.3 命名通り mission_margin = -mission_inf_gap (BACKWARD COMPAT).

    実運用 ordering には mission_signed_margin を使うこと (本関数は backward compat 用).
    """
    return -mission_inf_gap


def compute_mission_signed_margin(slacks: dict[str, float]) -> float:
    """archive CA #5 ordering 用 signed margin (synthesis § 8.3 補完、 暫定 SSOT).

    式: mission_signed_margin = min(slacks[m] for m in MISSION_INF_GAP_METRIC_KEYS)

    Args:
        slacks: T061 signed slack dict (必須 4 key)

    Returns:
        signed margin (任意実数)
        - 4 指標全達成かつ余裕大: large positive
        - 1 指標 marginal: small positive
        - 1 指標未達: negative
        - 1 指標以上 -inf: -inf

    Raises:
        ValueError: slacks に必須 key 欠損 or NaN を検出した場合 (caller 修正責務)
    """
    _validate_slacks_dict(slacks)
    return min(slacks[k] for k in MISSION_INF_GAP_METRIC_KEYS)


def extract_per_metric_shortfalls(slacks: dict[str, float]) -> dict[str, float]:
    """4 指標別 shortfall dict を返す (diagnostic only、 Round 2 [W3] 反映).

    各 key で max(0, -slacks[m])。 表示時は always with is_feasible flag を使うこと.
    """
    _validate_slacks_dict(slacks)
    return {k: max(0.0, -slacks[k]) for k in MISSION_INF_GAP_METRIC_KEYS}


# ---------------------------------------------------------------------------
# Top-level entry
# ---------------------------------------------------------------------------


def compute_constraint_violation(
    slacks: Mapping[str, float], is_feasible: bool
) -> float:
    """NSGA-II constrained-domination (Deb 2000) 用 violation 量を計算.

    is_feasible=True → 0.0
    is_feasible=False → max(max(0, -slack_m) for m in 4 指標) (有限値、 sentinel なし)
        現案では mission_inf_gap と同値だが、 概念上は infeasible 序列化用のため別関数。
        将来 invariant violation count (e.g. session_close_drop_count) を加算する余地あり。

    Raises:
        ValueError: slacks に必須 key 欠損 or NaN を検出した場合
    """
    _validate_slacks_dict(slacks)
    if is_feasible:
        return 0.0
    return max(max(0.0, -slacks[k]) for k in MISSION_INF_GAP_METRIC_KEYS)


def evaluate_mission_inf_gap(result: CanonicalFiveResult) -> MissionGapResult:
    """T061 出力を mission_inf_gap engine で消費し、 MissionGapResult を返す.

    依存方向: T062 → T061 (logical pipeline、 canonical 5 → mission_inf_gap)。
    T061 の signed slack 4 指標 (sharpe / pnl / dd / tc) を直接消費、 slack_wr は無視。

    NaN fail-fast 全経路化 (詳細 Round 1 [C2] 反映):
    is_feasible に依存せず、 4 slack の NaN 検証を判定**前**に実施。 NaN は engine 合成
    bug indicator で全経路で fail-fast。

    sentinel 撤廃 (詳細 Round 1 [C1] 反映):
    is_feasible=False でも mission_inf_gap は純粋 § 6.4 式の有限値を返す。
    constraint_violation で infeasible 序列化を提供 (Deb 2000 用)。
    mission_signed_margin のみ -inf sentinel を維持 (archive eviction lex 順序の
    最低 priority マーク用)。

    Args:
        result: T061 評価結果

    Returns:
        MissionGapResult (frozen dataclass、 immutable per_metric_shortfall)

    Raises:
        ValueError: T061 出力に NaN slack を検出した場合 (caller=T061 修正責務、
            fail-fast 方針: selection loop 例外は run abort)
    """
    # NaN fail-fast 全経路化 (詳細 Round 1 [C2] 反映)
    slacks: dict[str, float] = {
        "sharpe": result.slack_sharpe,
        "pnl": result.slack_pnl,
        "dd": result.slack_dd,
        "tc": result.slack_tc,
    }
    _validate_slacks_dict(slacks)  # 全経路で NaN check 実施

    is_feasible = result.invariants.is_feasible
    mig = compute_mission_inf_gap_from_slacks(slacks)
    constraint_violation = compute_constraint_violation(slacks, is_feasible=is_feasible)
    mission_margin = compute_mission_margin(mig)
    if is_feasible:
        mission_signed_margin = compute_mission_signed_margin(slacks)
    else:
        # archive eviction で最低 priority マーク (T067 で secondary tie-break key 必要)
        mission_signed_margin = MISSION_SIGNED_MARGIN_INFEASIBLE_SENTINEL

    per_metric = extract_per_metric_shortfalls(slacks)
    return MissionGapResult(
        mission_inf_gap=mig,
        constraint_violation=constraint_violation,
        mission_margin=mission_margin,
        mission_signed_margin=mission_signed_margin,
        per_metric_shortfall=MappingProxyType(per_metric),
        is_feasible=is_feasible,
    )
```

### ルックアヘッドバイアスチェック

- N/A (T062 は T061 出力を集約するのみで、 strategy 評価 / lookback 操作なし)

### C3 / C7 適用

- **C3**: 該当なし (相関分析を新規導入しない)
- **C7**: 該当なし (T061 出力の slack 値を集約するのみ、 sample size に依存しない)

### パフォーマンスチェック

- O(4) 計算 (4 指標固定、 一定時間)、 1 評価 < 10us
- pop=192 × gen=64 × eval/Run = 12,288 評価/Run、 全 RUN ~ 0.1 sec (CPU 1 core)
- ボトルネックなし

### テスト計画 (施策 2 で詳述)

### リスク

- T061 マージ前は本 PR を merge しない (`from src.alpha_factory.canonical_metrics import CanonicalFiveResult` で T061 module を import)
- 既存 GA / archive / cross_pair に touch しないため Phase 1 単体では runtime に影響なし

---

## 施策 2: `tests/alpha_factory/test_mission_inf_gap.py` 新規作成

### 変更箇所

- ファイル: `tests/alpha_factory/test_mission_inf_gap.py` (新規)

### テスト計画

振る舞いベース test 名:

#### Constants
- `test_mission_inf_gap_has_no_sentinel_returns_finite_value_for_all_inputs`
  (詳細 Round 1 [C1] 反映: sentinel +inf 撤廃確認)
- `test_mission_signed_margin_infeasible_sentinel_is_negative_infinity`
- `test_mission_inf_gap_metric_keys_are_synthesis_six_four_strict_four`
  (sharpe / pnl / dd / tc、 win_rate 含まない)

#### compute_mission_inf_gap_from_slacks
- `test_compute_mission_inf_gap_zero_when_all_four_slacks_positive_or_zero`
- `test_compute_mission_inf_gap_returns_max_negative_slack_magnitude`
  (1 指標未達時、 max(0, -slack) で確定)
- `test_compute_mission_inf_gap_ignores_slack_wr_in_input`
  (slacks dict に slack_wr key を入れても結果に影響しない)
- `test_compute_mission_inf_gap_raises_on_missing_required_key`
- `test_compute_mission_inf_gap_raises_on_nan_value`
  (Round 2 [W2] fail-fast)
- `test_compute_mission_inf_gap_negative_inf_slack_yields_positive_inf_gap`

#### compute_mission_margin
- `test_compute_mission_margin_negates_mission_inf_gap`
- `test_compute_mission_margin_zero_when_all_achieved`
- `test_compute_mission_margin_returns_negative_inf_when_input_is_positive_inf`

#### compute_mission_signed_margin
- `test_compute_mission_signed_margin_returns_min_of_four_slacks`
- `test_compute_mission_signed_margin_positive_when_all_four_slacks_positive`
  (4 指標全余裕)
- `test_compute_mission_signed_margin_negative_when_any_slack_negative`
- `test_compute_mission_signed_margin_handles_positive_infinity_slacks`
  (極端な余裕は寄与なしで min は他の有限値で確定)
- `test_compute_mission_signed_margin_returns_negative_inf_when_any_slack_is_negative_inf`

#### compute_constraint_violation (詳細 Round 1 [C1] 反映、 Deb 2000 用)
- `test_compute_constraint_violation_returns_zero_when_feasible`
- `test_compute_constraint_violation_returns_finite_positive_when_infeasible`
  (sentinel ではなく有限値、 infeasible 個体間の序列化に使用可能)
- `test_compute_constraint_violation_matches_mission_inf_gap_when_infeasible`
  (現案: 同値、 将来 invariant violation count 加算で乖離可能)
- `test_compute_constraint_violation_raises_on_nan`

#### extract_per_metric_shortfalls
- `test_per_metric_shortfall_returns_dict_with_four_keys`
- `test_per_metric_shortfall_zero_for_achieved_metric`
- `test_per_metric_shortfall_positive_for_unachieved_metric`
- `test_per_metric_shortfall_raises_on_nan`

#### evaluate_mission_inf_gap (top-level、 Round 2 [S1] / 詳細 Round 1 [S4] 4 代表ケース、 unit test 統一)
- `test_evaluate_mission_inf_gap_perfect_run_yields_zero_gap_and_signed_margin_positive`
  (代表ケース 1: feasible 全達成、 mission_inf_gap=0、 constraint_violation=0、 mission_signed_margin > 0)
- `test_evaluate_mission_inf_gap_one_metric_short_yields_positive_gap_and_signed_margin_negative`
  (代表ケース 2: feasible 1 指標不足、 mission_inf_gap > 0、 constraint_violation=0 (feasible)、 mission_signed_margin < 0)
- `test_evaluate_mission_inf_gap_infeasible_yields_finite_gap_and_finite_constraint_violation_and_neg_inf_signed_margin`
  (代表ケース 3: infeasible、 mission_inf_gap=有限値、 constraint_violation=有限値、 mission_signed_margin=-inf。 詳細 Round 1 [C1] 反映: sentinel +inf 撤廃)
- `test_evaluate_mission_inf_gap_propagates_value_error_on_nan_slack_in_all_paths`
  (代表ケース 4: NaN、 caller responsibility、 全経路 fail-fast、 詳細 Round 1 [C2] 反映)

#### invariant 連鎖
- `test_evaluate_mission_inf_gap_propagates_t061_is_feasible_flag`
- `test_evaluate_mission_inf_gap_returns_frozen_dataclass`

#### Sentinel Comparison Convention (Round 2 [S3] 反映 + 詳細 Round 1 [C1] sentinel 撤廃反映)
- `test_mission_inf_gap_finite_value_sorts_normally_in_minimize`
  (sorted(items, key=lambda x: x.mission_inf_gap) で値順、 sentinel +inf なし)
- `test_constraint_violation_orders_infeasible_individuals_finite_scalar`
  (詳細 Round 1 [C1] 反映: infeasible 同士で violation 小さい方が前、 Deb 2000 同準拠)
- `test_mission_signed_margin_negative_infinity_sorts_to_end_in_archive_eviction`
  (sorted(items, key=lambda x: -x.mission_signed_margin) で -inf 個体は末尾)

#### per_metric_shortfall immutability (詳細 Round 1 [W2])
- `test_per_metric_shortfall_is_mapping_proxy_type_immutable`
  (MissionGapResult.per_metric_shortfall に対して __setitem__ で TypeError)

#### T065 constrained-domination 契約テスト (詳細 Round 1 [S3]、 pytest.mark.xfail)
- `test_infeasible_constraint_violation_ordering_contract_for_t065`
  (T065 実装後に xfail 解除する契約、 infeasible 同士 constraint_violation 小さい方が dominate)
  - **解除条件 (詳細 Round 2 [S3] 反映)**: T065 (NSGA-II + constrained-domination) PR がマージされたら
    xfail decorator を外す。 解除タイミングを明示するため `@pytest.mark.xfail(reason="T065 で
    constrained-domination 実装後に解除")` で reason 必須

#### MissionGapResult 不変条件 (詳細 Round 2 [S2] 追加)
- `test_invariant_infeasible_implies_signed_margin_is_negative_infinity`
  (`not is_feasible` → `mission_signed_margin == -inf`)
- `test_invariant_feasible_implies_constraint_violation_is_zero`
  (`is_feasible` → `constraint_violation == 0.0`)
- `test_invariant_mission_margin_equals_negative_mission_inf_gap`
  (`mission_margin == -mission_inf_gap`)

### リスク

- (テストのみ、 リスク軽微)

---

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | **standalone** (T061 マージ後前提、 単体実装可、 Phase 2 で 7 箇所同時更新を別 PR) |
| 判断根拠 | T062 PR は単体テストのみで既存 GA / archive 経路に touch しない |
| 競合リスク | T058 / T059 / T060 / T061 マージ済前提、 ただし他 module 直接 import は T061 のみ |
| 想定実装時間 | 短 (2 施策、 4 hour 想定) |

## 実装順序

T062 PR で 2 施策を 1 PR で着地。 Phase 2 (7 箇所同時更新) は T065-T067 と同時に別 PR (別 TODO)。

---

## DoD (Definition of Done)

T062 PR 完了基準:

### コード DoD

- [ ] `src/alpha_factory/mission_inf_gap.py` 新規作成 (MissionGapResult dataclass + 3 helper + extract + top-level entry + sentinel const)
- [ ] `tests/alpha_factory/test_mission_inf_gap.py` 新規作成 (上記 test 全 pass、 4 代表ケース doctest)
- [ ] `uv run pytest tests/alpha_factory/test_mission_inf_gap.py` 全 pass
- [ ] `uv run ruff check src/ tests/` clean
- [ ] `uv run mypy src/` clean
- [ ] GA / archive / cross_pair / swim_lane / config を変更しない (Phase 1 スコープ厳守)

### Phase 1 (T062 PR) C2 parallel-path 確認 DoD (詳細 Round 1 [W3] で 5 段階強化)

- [ ] **段階 1 (直 import `from ... import`)**: `grep -rn "from src.alpha_factory.mission_inf_gap" scripts/ src/ tests/` の結果が `src/alpha_factory/mission_inf_gap.py` (自身) と `tests/alpha_factory/test_mission_inf_gap.py` 以外で hit しない
- [ ] **段階 2 (`import ... as` alias)**: `grep -rn -E "import\s+src\.alpha_factory\.mission_inf_gap" src/ scripts/ tests/` が 自身 + tests のみ hit
- [ ] **段階 3 (relative import)**: `grep -rn -E "from\s+\.+\s*mission_inf_gap" src/ scripts/ tests/` が 自身 + tests のみ hit
- [ ] **段階 4 (再エクスポート)**: `grep -rn "mission_inf_gap" src/alpha_factory/__init__.py src/alpha_factory/*.py | grep -v "src/alpha_factory/mission_inf_gap.py:"` が 0 hit
- [ ] **段階 5 (runtime 配線シンボル)**: `grep -rn -E "evaluate_mission_inf_gap|MissionGapResult|compute_constraint_violation" src/alpha_factory/archive.py src/alpha_factory/cross_pair.py src/alpha_factory/swim_lane.py scripts/alpha_factory/run_ga.py` が 0 hit (Phase 2 まで配線禁止)

### Phase 2 (T065-T067 と同時、 別 PR) DoD (申し送り、 7 箇所同時更新)

- [ ] (新規) `src/alpha_factory/ga/nsga2_objectives.py`: Pareto 3 軸 f3 = `MissionGapResult.mission_inf_gap` (T065)
- [ ] **(新規、 必須) `src/alpha_factory/ga/constrained_domination.py`**: NSGA-II non-dominated sorting 前に feasible filter / Deb (2000) constrained-domination を実装 (T065)。 疑似コード (詳細 Round 2 [S1] 反映):
  ```python
  def constrained_dominates(p: Individual, q: Individual) -> bool:
      """Deb (2000) constrained-domination: True iff p dominates q."""
      # 1. feasible が infeasible を unconditionally dominate
      if p.is_feasible and not q.is_feasible:
          return True
      if not p.is_feasible and q.is_feasible:
          return False
      # 2. 両方 infeasible: constraint_violation 小さい方が dominate
      if not p.is_feasible and not q.is_feasible:
          return p.constraint_violation < q.constraint_violation
      # 3. 両方 feasible: 通常の Pareto dominance (3 軸 f1/f2/f3)
      return p.dominates_pareto(q)
  ```
  - **詳細 Round 2 [W2] 反映**: `constraint_violation` は 4 slack 由来のみのため、 invariant
    violation (synthesis § 6.6 の strategic_*) を別途加算するかは T065 詳細設計時に確定
    (例: `effective_constraint_violation = constraint_violation + 1.0 * count(strategic_*)`)
- [ ] (新規) `src/alpha_factory/ga/archive_eviction.py`: CA eviction lex #5 = `MissionGapResult.mission_signed_margin` を直接消費 (T067)
- [ ] `src/alpha_factory/archive.py`: archive admission が `MissionGapResult.is_feasible` 安全網 (T067)
- [ ] `src/alpha_factory/swim_lane.py`: tier1 evaluator が GA 経由で MissionGapResult 消費 (T065)
- [ ] `src/alpha_factory/diagnostics_sidecar.py`: per_metric_shortfall を archive metadata 記録 (T058 schema v2 接続) (T067)
- [ ] **synthesis 改訂 PR (別途)**: synthesis § 8.3 CA #5 を `mission_signed_margin` に改訂、 § 15 残論点追記 (T064 PR 完了後)

### 暫定 SSOT 宣言 (Round 2 [W1] 反映)

- [ ] `MissionGapResult.mission_signed_margin` は archive CA #5 ordering の **暫定 SSOT**
- [ ] synthesis § 8.3 の `mission_margin = -mission_inf_gap` 命名は数式矛盾、 T064 PR 完了後に synthesis 改訂 PR で修正予定
- [ ] それまで本詳細設計が runtime SSOT

---

## 関連 / 後段 TODO

- T058: Schema v2 contract (依存先、 設計 APPROVED)
- T059: EpochManager (依存先、 設計 APPROVED)
- T060: Partition + Fold generator (依存先、 設計 APPROVED)
- T061: canonical 5 engine (依存先、 設計 APPROVED、 直接 import)
- T063: Stage A evaluator (T061 + q_force ranking で消費、 mission_inf_gap は使わない)
- T064: Stage B/C-lite/C evaluator (T061 + T062 の MissionGapResult を内部 metadata で使用)
- T065-T066: NSGA-II + CPPS (T062 を Pareto f3 で消費、 constrained-domination 必須)
- T067: Loop closure (T062 を archive admission / eviction で消費、 CA #5 は mission_signed_margin)

---

## 学術引用 (詳細 Round 1 [W4] 反映、 full citation + DOI)

- **Deb, K. (2000). "An efficient constraint handling method for genetic algorithms." Computer Methods in Applied Mechanics and Engineering, 186(2-4), 311-338. https://doi.org/10.1016/S0045-7825(99)00389-8** — constrained-domination ルールの元論文。 T065 で実装すべき feasible-infeasible 関係定義の根拠
- **Deb, K., Pratap, A., Agarwal, S., & Meyarivan, T. (2002). "A fast and elitist multiobjective genetic algorithm: NSGA-II." IEEE Transactions on Evolutionary Computation, 6(2), 182-197. https://doi.org/10.1109/4235.996017** — NSGA-II の支配関係と crowding distance の元論文
- synthesis § 6.4 / § 6.5 / § 8.3 / § 15: mission_inf_gap / Pareto 3 軸 / archive eviction 確定値 (§ 8.3 の `mission_margin` 命名は数式矛盾、 § 15 に追記候補)
