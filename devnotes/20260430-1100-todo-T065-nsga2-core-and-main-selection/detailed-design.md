# 詳細設計: T065 — NSGA-II core + 主選抜 (B-pooled)

## 使命・制約 (絶対遵守)

zenigame-fx Alpha Factory 使命: live_criteria 全指標同時充足 + (ii-lite) 通過。 絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。 禁止事項 1-7 (synthesis § 1.3) + 8 (archive スキーマ伝搬漏れ、 T058 対応済)。 コーディングルール: バグ修正テストファースト / 全施策テスト必須・振る舞いベース命名 / uv 必須 / ruff & mypy 通過 / Python 3.13。

## 概念設計リファレンス

`devnotes/20260430-1100-todo-T065-nsga2-core-and-main-selection/conceptual-design.md` (Round 4 で APPROVED、 Round 1 [Critical] 3 + [Warning] 5 + [Suggestion] 3、 Round 2 [Critical] 1 + [Warning] 2 + [Suggestion] 1、 Round 3 [Critical] 2 + [Warning] 1 + [Suggestion] 1、 Round 4 [Suggestion] 1 全反映)

## SSOT 注記 (Round 2 [Critical] / Round 3 [Suggestion] 反映)

シグネチャは概念設計 § 11.2 を SSOT とする。 本詳細設計内のシグネチャ・擬似コードは § 11.2 を引用元として完全同期、 deviation 禁止。 矛盾発見時は § 11.2 を優先し本詳細設計を更新する運用ルールを採用。

## 詳細 Round 1 review 反映 (Codex 詳細レビュー)

| 詳細 Round 1 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [C1] eligible==1 で `binary_tournament` の `rng.sample(..., k=2)` が ValueError、 D8 self-mating fallback と矛盾 | `select_parent_pair` 冒頭で `len(survivors)==0` で ValueError raise (call site ガード)、 `len(survivors)==1` で早期 return `(survivors[0], survivors[0])` 自己ペア fallback、 binary_tournament も `len(survivors) < 2` で ValueError raise (defense-in-depth、 詳細 Round 2 [W2] 厳密化) |
| [C2] sort_keys 4-tuple 不足: 同一 genome_hash 複数体で Mapping 反復順依存、 byte-for-byte 再現性破綻 | sort_keys を `(front_no, -crowding, genome_hash, index)` に拡張 (4-tuple)。 `eligible` 構築は `sorted(population.keys())` で安定順固定 |
| [W1] `select_parent_pair` docstring「max_retry+1 回抽出」 と擬似コード `range(max_retry)` の不一致 | docstring を「最大 `max_retry` 回追加抽出 (= 合計最大 `max_retry+1` 回 binary_tournament 呼出)」 と表記統一 |
| [W2] `non_dominated_sort` i/j 全探索で比較 2 倍 | `i < j` のみ比較し、 dominate 関係に応じて両側更新 (O(M*N(N-1)/2)) |
| [W3] `select_survivors` と `run_generation_selection` の eligible 抽出 / front / crowding 計算重複 | private helper `_compute_eligible_axes_violations_feasibility` / `_compute_front_assignments_and_crowding` に抽出、 両 entry から DRY |
| [W4] C2 grep DoD 段階 1 で `tests` 含む点が曖昧 | 段階 1 コマンドで `--exclude-dir tests` 等を明示、 期待 0 件の機械判定条件を確定化 |
| [W5] 「全 6 sub-suite」 と「13 sub-suite」 の記述不整合 | 全箇所を「**13 sub-suite**」 で統一 |
| [S1] INVARIANT_VIOLATION_PENALTY=1.0e6 の事前上界根拠 | `constraint_violation` 実データ上界 (4 slack 由来 max(0, -slack_*) の sum、 typically <= 数十、 上界目安 1.0e2) を 1 行で明記、 1.0e6 ≫ 1.0e2 で支配性確保 |
| [S2] テスト追加: survivors==1 self-mating / 同一 genome_hash 複数体 deterministic / non_dominated_sort 空入力 | テスト計画に 3 件追加 |
| [S3] Phase 2 申し送りに「旧 selection 経路の削除対象シンボル一覧」 明示 | Phase 2 申し送り表に項目 #9 追加: 旧 selection 経路 (stage_gate.py / archive.py / cross_pair.py の selection 関連シンボル) の削除対象を grep で確定 |

---

## 施策一覧 (Phase 1: T065 PR、 Phase 2 は別 PR)

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | `nsga2_selection.py` 新規 (3 dataclass + 1 const + 7 public helper + 3 private helper + 1 top-level entry + 1 seed helper) | `src/alpha_factory/ga/nsga2_selection.py` (新規) | Critical |
| 2 | `tests/alpha_factory/ga/test_nsga2_selection.py` 新規 (constrained-domination / Pareto axis / non-dominated sort / crowding / survivor / tournament / determinism / edge cases / contract violation / 全 **13 sub-suite**) | (新規) | Critical |

**Phase 1 (T065 PR) スコープ = 上記 2 施策**。 既存 GA loop / archive / cross_pair / swim_lane / run_ga.py への組込は **Phase 2 (T066 / T067 / T070 / T071 と同時)** で実施。 T065 PR 単独 merge で runtime に影響なし (既存 ga loop は新規 module を import しないため)。

**Phase 1 が触らない**:
- `src/alpha_factory/stage_gate.py` / `archive.py` / `cross_pair.py` / `swim_lane.py` / `scripts/run_ga.py`
- `config/alpha_factory/default.yaml`
- `docs/alpha_factory/*.md`

---

## 施策 1: `nsga2_selection.py` 新規作成

### 変更箇所

- ファイル: `src/alpha_factory/ga/nsga2_selection.py` (新規)、 配置先 `src/alpha_factory/ga/` ディレクトリ自体新規作成
- `src/alpha_factory/ga/__init__.py` (新規、 空)

### 波及変更

- `AGENTS.md`: なし (Phase 2 で synthesis 改訂 PR と同時に追記候補)
- `config/alpha_factory/default.yaml`: なし (Phase 2 で GA core パラメータ追加: pop_size, generations, crossover_rate, mutation_rate, INVARIANT_VIOLATION_PENALTY)
- `docs/alpha_factory/*.md`: なし (Phase 2 で `ga-architecture.md` 新設候補)
- 既存 import 経路: 0 件 touch (新規 module で他 module から import されない)

### 変更後コード骨子

```python
"""T065: NSGA-II core + 主選抜 (B-pooled) — synthesis § 7.1 / § 6.5 確定式の単一実装.

詳細:
- 概念設計: devnotes/20260430-1100-todo-T065-nsga2-core-and-main-selection/conceptual-design.md
- synthesis § 7.1 (NSGA-II + 純 CPPS)、 § 6.5 (Pareto 3 軸)、 § 7.5 (operators)、 § 7.7 (failure handling)
- T063 依存: stage_a_pass (a_pass_indices)、 default-deny 契約
- T064 依存: BCEvaluationResult (b_pooled_cf, pareto_axis_usable, pooled_dd_per_fold_max)
- T062 依存: MissionGapResult (mission_inf_gap, constraint_violation, is_feasible)
- T061 依存: InvariantFlags (session_close_drop_count, negative_equity_drop_open_count, is_feasible)

Phase 1 (本 TODO): 単体実装 + テストのみ、 GA / archive / cross_pair 未変更.
Phase 2 (別 PR): T066 / T067 / T070 / T071 と同時、 8 箇所同時更新 (Phase 2 申し送り参照).

References:
- Deb, K. (2000). An efficient constraint handling method for genetic algorithms.
  Computer Methods in Applied Mechanics and Engineering, 186(2-4), 311-338.
  https://doi.org/10.1016/S0045-7825(99)00389-8
- Deb, K., Pratap, A., Agarwal, S., & Meyarivan, T. (2002). A fast and elitist
  multiobjective genetic algorithm: NSGA-II. IEEE Transactions on Evolutionary
  Computation, 6(2), 182-197. https://doi.org/10.1109/4235.996017
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import types
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from alpha_factory.canonical_metrics import InvariantFlags
from alpha_factory.mission_inf_gap import MissionGapResult
from alpha_factory.stage_bc_evaluator import BCEvaluationResult


__all__ = [
    "INVARIANT_VIOLATION_PENALTY",
    "ParetoAxis",
    "IndividualEvaluation",
    "GenerationSelectionResult",
    "make_selection_seed",
    "extract_pareto_axis",
    "compute_effective_constraint_violation",
    "constrained_dominates",
    "non_dominated_sort",
    "crowding_distance",
    "select_survivors",
    "binary_tournament",
    "select_parent_pair",
    "run_generation_selection",
]

# Constants
INVARIANT_VIOLATION_PENALTY: float = 1.0e6
"""invariant 1 件で slack 由来 violation を支配する大値 (synthesis § 6.6 / 概念設計 § 5.2).

INCONCLUSIVE (smoke 後再校正候補、 概念設計 § 13.1):
- invariant violation 個体が rank 末尾に確実に行く (mass 配分検証)
- all-infeasible front でも数値安定 (oscillation / overflow なし)
- finite violation 域で penalty による monotone ordering が崩れない (slack 1 / invariant 1 比較等)
"""


# ----------------------------------------------------------------------------
# dataclasses (frozen で immutable)
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class ParetoAxis:
    """Pareto 3 軸 (synthesis § 6.5)、 finite domain 必須.

    f1 = net_pnl_after_cost (max)、 f2 = pooled_dd_per_fold_max (min)、 f3 = mission_inf_gap (min).
    """
    net_pnl: float
    max_dd: float
    mission_inf_gap: float


@dataclass(frozen=True)
class IndividualEvaluation:
    """T063 / T064 / T062 / T061 の per-individual 結果統合.

    - stage_a_pass: T063 a_pass_indices に含まれるか (default-deny 契約)
    - bc_result: T064 evaluate_bc_for_a_pass の出力 (a_pass のみ非 None、 a_fail は None 必須)
    - mission_gap: T062 evaluate_mission_inf_gap の出力 (全個体)
    - invariant_flags: T061 InvariantFlags (全個体)
    - genome_hash: deterministic tie-break 用 (SHA-256 hex32 等、 caller 責務で生成)

    index 一意性契約 (詳細 Round 2 [W3] 反映):
    - `index` は population dict の key と一致 (`population[idx].index == idx`)
    - 同一 generation 内で一意 (caller 責務)、 重複時は upstream pipeline 異常
    - sort_keys 4-tuple の最終 tie-break 鍵として使用 (詳細 Round 1 [C2])。 重複は禁止
    """
    index: int
    genome_hash: str
    stage_a_pass: bool
    bc_result: BCEvaluationResult | None
    mission_gap: MissionGapResult
    invariant_flags: InvariantFlags


@dataclass(frozen=True)
class GenerationSelectionResult:
    """per-generation 主選抜結果.

    - front_assignments: eligible のみ {idx: front_no (1-origin)}
    - crowding_distances: eligible のみ {idx: float (+inf at front size <= 2 or endpoints)}
    - survivor_indices: 長さ <= pop_size、 rank → -crowding → genome_hash の lex 昇順
    - parent_pairs: 長さ pop_size 固定 (Round 1 [W2] / Round 4 [Critical] / Round 3 [Critical 2])、
      offspring pop_size 体生成想定。 (idx, idx) は self-mating fallback (mutation only)
    - excluded_indices: A-fail (stage_a_pass=False) or B-invariant-fail (pareto_axis_usable=False)
    - sample_size_warnings: 操作上の warning 列 (eligible_set_empty 等)
    """
    front_assignments: types.MappingProxyType[int, int]
    crowding_distances: types.MappingProxyType[int, float]
    survivor_indices: tuple[int, ...]
    parent_pairs: tuple[tuple[int, int], ...]
    excluded_indices: frozenset[int]
    sample_size_warnings: tuple[str, ...]


# ----------------------------------------------------------------------------
# RNG seed helper (Round 1 [C1] / Round 2 [Suggestion 1])
# ----------------------------------------------------------------------------

def make_selection_seed(run_id: str, gen_no: int) -> int:
    """run 跨ぎ deterministic な seed を blake2b で生成.

    Python `hash()` は process salt で run 跨ぎ不安定なため不採用。 blake2b 8-byte digest を
    int.from_bytes (big endian, unsigned) で 64-bit 整数化、 random.Random(seed) に渡す前提。

    payload は json.dumps([run_id, gen_no, "selection"], separators=(",", ":")) で構造化
    シリアライズし、 delimiter 衝突 (run_id 内 "|" 等) を回避 (Round 2 [Suggestion 1]).
    """
    payload_str = json.dumps([run_id, gen_no, "selection"], separators=(",", ":"))
    digest = hashlib.blake2b(payload_str.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)


# ----------------------------------------------------------------------------
# Pareto axis 抽出 (Round 1 [C3] / [S3])
# ----------------------------------------------------------------------------

def extract_pareto_axis(
    bc_result: BCEvaluationResult,
    mission_gap: MissionGapResult,
) -> ParetoAxis:
    """T064 BCEvaluationResult + T062 MissionGapResult から Pareto 3 軸を抽出.

    f1 = bc_result.b_pooled_cf.net_pnl_after_cost (max)
    f2 = bc_result.pooled_dd_per_fold_max (min, concat DD でない、 synthesis § 5.2 / T064 [C2])
    f3 = mission_gap.mission_inf_gap (min, T062 確定式)

    finite check (Round 1 [C3]): 3 軸全てに math.isfinite assert、 non-finite で ValueError raise.
    `b_pooled_cf is None` (= invariant_fail at any fold) は事前 caller 責務でフィルタすべき
    (run_generation_selection が pareto_axis_usable=True のみ通す)。 ここで b_pooled_cf=None は
    contract 違反として ValueError raise.
    """
    if bc_result.b_pooled_cf is None:
        raise ValueError(
            "extract_pareto_axis requires bc_result.b_pooled_cf to be non-None. "
            "pareto_axis_usable=True 個体のみ T065 へ進入する契約 (T064)"
        )
    net_pnl = bc_result.b_pooled_cf.net_pnl_after_cost
    max_dd = bc_result.pooled_dd_per_fold_max
    mig = mission_gap.mission_inf_gap
    if not math.isfinite(net_pnl):
        raise ValueError(f"net_pnl must be finite, got {net_pnl!r}")
    if not math.isfinite(max_dd):
        raise ValueError(f"max_dd must be finite, got {max_dd!r}")
    if not math.isfinite(mig):
        raise ValueError(f"mission_inf_gap must be finite, got {mig!r}")
    return ParetoAxis(net_pnl=net_pnl, max_dd=max_dd, mission_inf_gap=mig)


# ----------------------------------------------------------------------------
# effective constraint violation (Round 1 [C2])
# ----------------------------------------------------------------------------

def compute_effective_constraint_violation(
    mission_gap: MissionGapResult,
    invariant_flags: InvariantFlags,
) -> float:
    """T062 constraint_violation + INVARIANT_VIOLATION_PENALTY × invariant_count.

    Deb 2000 constrained-domination の single scalar violation を構築.

    finite domain 制約 (Round 1 [C2]):
    - constraint_violation +inf で ValueError raise (運用 bug indicator)
    - invariant_count < 0 で ValueError raise

    invariant_count = session_close_drop_count + negative_equity_drop_open_count
        (synthesis § 6.6 invariant fail-fast 原因)
    """
    cv = mission_gap.constraint_violation
    if not math.isfinite(cv):
        raise ValueError(
            f"T062 constraint_violation must be finite, got {cv!r}. "
            f"+inf 由来 (slack=-inf) は upstream T061/T062 で fail-fast すべき。 "
            f"T065 は finite domain でのみ動作 (defense-in-depth)"
        )
    inv_count = (
        invariant_flags.session_close_drop_count
        + invariant_flags.negative_equity_drop_open_count
    )
    if inv_count < 0:
        raise ValueError(f"invariant_count must be non-negative, got {inv_count}")
    return cv + INVARIANT_VIOLATION_PENALTY * float(inv_count)


# ----------------------------------------------------------------------------
# constrained-domination (Deb 2000)
# ----------------------------------------------------------------------------

def _pareto_dominates(p: ParetoAxis, q: ParetoAxis) -> bool:
    """Pareto 3 軸 dominance (f1 max, f2 min, f3 min). feasible 同士のみ呼ぶ."""
    not_worse = (
        p.net_pnl >= q.net_pnl
        and p.max_dd <= q.max_dd
        and p.mission_inf_gap <= q.mission_inf_gap
    )
    if not not_worse:
        return False
    strictly_better = (
        p.net_pnl > q.net_pnl
        or p.max_dd < q.max_dd
        or p.mission_inf_gap < q.mission_inf_gap
    )
    return strictly_better


def constrained_dominates(
    p_axis: ParetoAxis,
    q_axis: ParetoAxis,
    *,
    p_violation: float,
    q_violation: float,
    p_feasible: bool,
    q_feasible: bool,
) -> bool:
    """Deb 2000 constrained-domination.

    Step 1: feasible vs infeasible は feasible が unconditionally dominate.
    Step 2: both infeasible → p_violation < q_violation で dominate.
    Step 3: both feasible → Pareto 3 軸 dominance.
    """
    if p_feasible and not q_feasible:
        return True
    if not p_feasible and q_feasible:
        return False
    if not p_feasible:  # both infeasible
        return p_violation < q_violation
    return _pareto_dominates(p_axis, q_axis)


# ----------------------------------------------------------------------------
# Non-dominated sort (Deb et al. 2002 fast non-dominated sort)
# ----------------------------------------------------------------------------

def non_dominated_sort(
    eligible_indices: Iterable[int],
    axes: Mapping[int, ParetoAxis],
    violations: Mapping[int, float],
    feasibility: Mapping[int, bool],
) -> dict[int, int]:
    """Fast non-dominated sort (Deb et al. 2002) with Deb 2000 constrained-domination.

    O(M*N(N-1)/2) where M = number of objectives (3) and N = |eligible|.
    詳細 Round 1 [W2]: i<j のみ比較、 dominate 関係に応じて両側更新で冗長を半減.

    Returns {idx: front_no (1-origin)}. front_no=1 は最優、 大きいほど劣後.
    空入力 (eligible_indices 空) なら空 dict を返す.
    """
    eligible = list(eligible_indices)
    n = len(eligible)
    if n == 0:
        return {}

    fronts: list[list[int]] = [[]]
    domination_count: dict[int, int] = {idx: 0 for idx in eligible}
    dominated_set: dict[int, list[int]] = {idx: [] for idx in eligible}

    # i < j で 1 回比較し、 dominate 関係に応じて両側更新 (Round 1 [W2] 反映で半減)
    for i in range(n):
        p = eligible[i]
        for j in range(i + 1, n):
            q = eligible[j]
            p_dominates_q = constrained_dominates(
                axes[p], axes[q],
                p_violation=violations[p], q_violation=violations[q],
                p_feasible=feasibility[p], q_feasible=feasibility[q],
            )
            if p_dominates_q:
                dominated_set[p].append(q)
                domination_count[q] += 1
                continue
            q_dominates_p = constrained_dominates(
                axes[q], axes[p],
                p_violation=violations[q], q_violation=violations[p],
                p_feasible=feasibility[q], q_feasible=feasibility[p],
            )
            if q_dominates_p:
                dominated_set[q].append(p)
                domination_count[p] += 1

    for p in eligible:
        if domination_count[p] == 0:
            fronts[0].append(p)

    front_no: dict[int, int] = {}
    current_front = 0
    while fronts[current_front]:
        next_front: list[int] = []
        for p in fronts[current_front]:
            front_no[p] = current_front + 1
            for q in dominated_set[p]:
                domination_count[q] -= 1
                if domination_count[q] == 0:
                    next_front.append(q)
        current_front += 1
        fronts.append(next_front)

    return front_no


# ----------------------------------------------------------------------------
# Crowding distance (NSGA-II 標準、 Round 1 [W5] / [C3])
# ----------------------------------------------------------------------------

def crowding_distance(
    front_indices: Iterable[int],
    axes: Mapping[int, ParetoAxis],
) -> dict[int, float]:
    """Standard NSGA-II crowding distance, 3 軸正規化.

    Round 1 [W5]: front_size <= 2 なら全員 +inf.
    軸範囲 0 (max == min) なら当該軸の crowding 寄与 0 (zenigame sorting.py:97-104 同等).
    finite 軸保証下で `inf - inf` の経路を断つ (Round 1 [C3]).
    """
    front_list = list(front_indices)
    crowding: dict[int, float] = {idx: 0.0 for idx in front_list}

    if len(front_list) <= 2:
        for idx in front_list:
            crowding[idx] = math.inf
        return crowding

    for axis_name in ("net_pnl", "max_dd", "mission_inf_gap"):
        sorted_front = sorted(front_list, key=lambda i: getattr(axes[i], axis_name))
        crowding[sorted_front[0]] = math.inf
        crowding[sorted_front[-1]] = math.inf

        a_min = getattr(axes[sorted_front[0]], axis_name)
        a_max = getattr(axes[sorted_front[-1]], axis_name)
        a_range = a_max - a_min
        if a_range == 0:
            continue   # 軸範囲 0 寄与は 0

        for k in range(1, len(sorted_front) - 1):
            prev_v = getattr(axes[sorted_front[k - 1]], axis_name)
            next_v = getattr(axes[sorted_front[k + 1]], axis_name)
            crowding[sorted_front[k]] += (next_v - prev_v) / a_range

    return crowding


# ----------------------------------------------------------------------------
# Survivor selection (deterministic)
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
# Private helpers (DRY、 詳細 Round 1 [W3] 反映)
# ----------------------------------------------------------------------------

def _validate_t064_contract(population: Mapping[int, IndividualEvaluation]) -> None:
    """T064 contract 違反 2 ケースで ValueError raise.

    Round 1 [W1] (a_pass=True なら bc_result is not None) +
    Round 2 [W2] (a_fail なら bc_result is None) の 2 ケースを fail-fast.
    """
    for idx, ev in population.items():
        if ev.stage_a_pass and ev.bc_result is None:
            raise ValueError(
                f"T064 contract violation at idx={idx}: a_pass=True but bc_result is None"
            )
        if (not ev.stage_a_pass) and ev.bc_result is not None:
            raise ValueError(
                f"T064 contract violation at idx={idx}: a_fail but bc_result is not None"
            )


def _compute_eligible_axes_violations_feasibility(
    population: Mapping[int, IndividualEvaluation],
) -> tuple[
    list[int],                        # eligible_indices (sorted で安定順)
    dict[int, ParetoAxis],            # axes
    dict[int, float],                 # violations
    dict[int, bool],                  # feasibility
    set[int],                         # excluded_indices
]:
    """eligible 抽出 + axes/violations/feasibility 計算 (詳細 Round 1 [C2] / [W3]).

    eligible は `sorted(population.keys())` で安定順固定 (Round 1 [C2] determinism).
    """
    eligible: list[int] = []
    axes: dict[int, ParetoAxis] = {}
    violations: dict[int, float] = {}
    feasibility: dict[int, bool] = {}
    excluded_indices_set: set[int] = set()
    # sorted で安定順 (Round 1 [C2])
    for idx in sorted(population.keys()):
        ev = population[idx]
        if (
            ev.stage_a_pass
            and ev.bc_result is not None
            and ev.bc_result.pareto_axis_usable
        ):
            eligible.append(idx)
            axes[idx] = extract_pareto_axis(ev.bc_result, ev.mission_gap)
            violations[idx] = compute_effective_constraint_violation(
                ev.mission_gap, ev.invariant_flags,
            )
            feasibility[idx] = (
                ev.mission_gap.is_feasible
                and ev.invariant_flags.is_feasible
            )
        else:
            excluded_indices_set.add(idx)
    return eligible, axes, violations, feasibility, excluded_indices_set


def _compute_front_assignments_and_crowding(
    eligible: Sequence[int],
    axes: Mapping[int, ParetoAxis],
    violations: Mapping[int, float],
    feasibility: Mapping[int, bool],
) -> tuple[dict[int, int], dict[int, float]]:
    """non_dominated_sort + crowding distance の連鎖 (詳細 Round 1 [W3] DRY).

    Returns (front_no, crowding).
    """
    front_no = non_dominated_sort(eligible, axes, violations, feasibility)
    crowding: dict[int, float] = {}
    fronts_grouped: dict[int, list[int]] = {}
    for idx, fn in front_no.items():
        fronts_grouped.setdefault(fn, []).append(idx)
    for _fn, members in fronts_grouped.items():
        crowding.update(crowding_distance(members, axes))
    return front_no, crowding


def _build_sort_keys(
    eligible: Iterable[int],
    front_no: Mapping[int, int],
    crowding: Mapping[int, float],
    population: Mapping[int, IndividualEvaluation],
) -> dict[int, tuple[int, float, str, int]]:
    """sort_keys 4-tuple (front_no, -crowding, genome_hash, index) の事前計算 (Round 1 [C2])."""
    return {
        idx: (
            front_no[idx],
            -crowding[idx],
            population[idx].genome_hash,
            population[idx].index,
        )
        for idx in eligible
    }


# ----------------------------------------------------------------------------
# Survivor selection (deterministic、 DRY helper 経由)
# ----------------------------------------------------------------------------

def select_survivors(
    population: Mapping[int, IndividualEvaluation],
    *,
    target_size: int,
) -> tuple[int, ...]:
    """rank → -crowding → genome_hash → index の lex 昇順で deterministic survivor 抽出.

    rng 不要 (概念 Round 1 [W3])、 完全 deterministic.
    返り値: tuple[int, ...]、 長さ <= target_size、 eligible が target_size 未満なら全 eligible 返却.
    eligible の定義: stage_a_pass=True AND bc_result is not None AND pareto_axis_usable=True.

    入口契約: T064 contract 違反 2 ケースで ValueError raise (概念 Round 1 [W1] / Round 2 [W2]).
    """
    if target_size < 1:
        raise ValueError(f"target_size must be >= 1, got {target_size}")

    _validate_t064_contract(population)
    eligible, axes, violations, feasibility, _excluded = (
        _compute_eligible_axes_violations_feasibility(population)
    )
    if not eligible:
        return ()

    front_no, crowding = _compute_front_assignments_and_crowding(
        eligible, axes, violations, feasibility,
    )
    sort_keys = _build_sort_keys(eligible, front_no, crowding, population)
    sorted_eligible = sorted(eligible, key=lambda i: sort_keys[i])
    return tuple(sorted_eligible[: target_size])


# ----------------------------------------------------------------------------
# Binary tournament (crowded-comparison operator only、 Round 1 [S1] / Round 2 [Critical])
# ----------------------------------------------------------------------------

def binary_tournament(
    survivors: Sequence[int],
    sort_keys: Mapping[int, tuple[int, float, str, int]],
    *,
    rng: random.Random,
) -> int:
    """survivor 抽出済集団から crowded-comparison operator で 1 体抽出.

    sort_keys は run_generation_selection 内で 1 回事前計算した
    {idx: (rank, -crowding, genome_hash, index)} の 4-tuple を渡す (詳細 Round 1 [C2] 反映、
    最終 tie-break として `index` (= IndividualEvaluation.index) を追加し
    deterministic 完全保証)。 tournament 内では tuple lex 比較のみ
    (constrained-domination の再評価はしない、 概念 Round 2 [Critical]).

    入口契約: len(survivors) >= 2 必須 (rng.sample(k=2) のため、 select_parent_pair で
    survivors==1 ガード済).

    Returns: 勝者 idx.
    """
    if len(survivors) < 2:
        raise ValueError(f"binary_tournament requires len(survivors) >= 2, got {len(survivors)}")
    a, b = rng.sample(list(survivors), k=2)
    return a if sort_keys[a] < sort_keys[b] else b


def select_parent_pair(
    survivors: Sequence[int],
    evaluations: Mapping[int, IndividualEvaluation],
    sort_keys: Mapping[int, tuple[int, float, str, int]],
    *,
    rng: random.Random,
    max_retry: int = 3,
) -> tuple[int, int]:
    """自己交配回避リトライ込みの parent pair 抽出.

    survivor 数による分岐 (詳細 Round 1 [C1] 反映):
    - len(survivors) == 0: 呼出元責務として ValueError raise (空 survivor は run_generation_selection
      の入口で検出され、 ここには到達しない契約)
    - len(survivors) == 1: 早期 return `(survivors[0], survivors[0])` で self-mating fallback
      (binary_tournament の rng.sample(k=2) で ValueError を回避)
    - len(survivors) >= 2: p1 を 1 回 + p2 を最大 max_retry 回追加抽出
      (= 合計最大 max_retry+1 回 binary_tournament 呼出、 詳細 Round 1 [W1] 反映)

    超過なら `(p1, p1)` で mutation only fallback (caller 責務、 Phase 2 breeding 経路).
    """
    if len(survivors) == 0:
        raise ValueError("select_parent_pair requires non-empty survivors")
    if len(survivors) == 1:
        only_idx = survivors[0]
        return (only_idx, only_idx)

    p1 = binary_tournament(survivors, sort_keys, rng=rng)
    for _ in range(max_retry):
        p2 = binary_tournament(survivors, sort_keys, rng=rng)
        if evaluations[p2].genome_hash != evaluations[p1].genome_hash:
            return (p1, p2)
    return (p1, p1)


# ----------------------------------------------------------------------------
# Top-level entry (per generation)
# ----------------------------------------------------------------------------

def run_generation_selection(
    population: Mapping[int, IndividualEvaluation],
    *,
    pop_size: int,
    rng: random.Random,
) -> GenerationSelectionResult:
    """per-generation 主選抜の top-level entry.

    入口契約検証:
    - pop_size >= 1 (ValueError if not)
    - population 非空 (ValueError if empty)
    - T064 contract: stage_a_pass=True なら bc_result is not None (ValueError)
    - T064 contract: stage_a_pass=False なら bc_result is None (ValueError)

    Returns: GenerationSelectionResult (eligible が空なら survivor_indices=(), parent_pairs=(),
    excluded_indices = population.keys(), sample_size_warnings = ("eligible_set_empty",)).
    """
    if pop_size < 1:
        raise ValueError(f"pop_size must be >= 1, got {pop_size}")
    if not population:
        raise ValueError("population must be non-empty")

    _validate_t064_contract(population)
    eligible, axes, violations, feasibility, excluded_indices_set = (
        _compute_eligible_axes_violations_feasibility(population)
    )

    sample_size_warnings: list[str] = []

    if not eligible:
        return GenerationSelectionResult(
            front_assignments=types.MappingProxyType({}),
            crowding_distances=types.MappingProxyType({}),
            survivor_indices=(),
            parent_pairs=(),
            excluded_indices=frozenset(excluded_indices_set),
            sample_size_warnings=("eligible_set_empty",),
        )

    front_no, crowding = _compute_front_assignments_and_crowding(
        eligible, axes, violations, feasibility,
    )
    sort_keys = _build_sort_keys(eligible, front_no, crowding, population)

    sorted_eligible = sorted(eligible, key=lambda i: sort_keys[i])
    survivor_indices = tuple(sorted_eligible[: pop_size])

    if len(eligible) < pop_size:
        sample_size_warnings.append(
            f"eligible_size_{len(eligible)}_below_pop_size_{pop_size}"
        )
    if len(eligible) < 30:
        sample_size_warnings.append("eligible_below_operational_threshold")
    if len(eligible) < 10:
        sample_size_warnings.append("eligible_critically_low")
    if len(eligible) == 1:
        sample_size_warnings.append("single_eligible_individual")
    if not any(feasibility.values()):
        sample_size_warnings.append("no_feasible_individuals")

    parent_pairs: list[tuple[int, int]] = []
    for _ in range(pop_size):
        pair = select_parent_pair(
            survivor_indices, population, sort_keys, rng=rng, max_retry=3,
        )
        parent_pairs.append(pair)

    return GenerationSelectionResult(
        front_assignments=types.MappingProxyType(dict(front_no)),
        crowding_distances=types.MappingProxyType(dict(crowding)),
        survivor_indices=survivor_indices,
        parent_pairs=tuple(parent_pairs),
        excluded_indices=frozenset(excluded_indices_set),
        sample_size_warnings=tuple(sample_size_warnings),
    )
```

### 設計判断詳細

#### D1: dataclass を frozen にする理由

- T062 / T063 / T064 の dataclass と同一規約。 GA 内で immutable 一貫性を保証
- Phase 2 で multi-process / async に拡張する場合の race condition 防止
- 不変条件を docstring に明記、 `__post_init__` での invariant 検証は不採用 (pure dataclass、 検証は caller 責務)

#### D2: `MappingProxyType` で dict を immutable wrap

- `front_assignments` / `crowding_distances` は外部から変更可能だと dataclass の immutable 性が破綻
- T062 `per_metric_shortfall` と同様の手法 (T062 詳細 Round 1 [W2] 同等)

#### D3: non_dominated_sort のアルゴリズム選定

- Deb et al. 2002 fast non-dominated sort: 詳細 Round 1 [W2] 反映で `i < j` 比較に変更、 **計算量 O(M*N(N-1)/2)** (= 旧 O(M*N²) の半分)。 dominate 関係の対称性を保ちつつ比較数を半減
- pop=192-256、 M=3 → 約 100K 比較 / 世代 → 64 世代 / Run × 6 Run / epoch ≈ 40M 比較 / epoch
- 純 Python 実装で十分 (1 epoch あたり数秒以内、 smoke で要 profile)
- Phase 2 で profiling → 必要なら Numba JIT 検討 (Decision Pending、 § 残論点 R2)

#### D4: crowding_distance の +inf 規約

- 端 2 個 (各軸 sort 時の最小・最大) に +inf 加算: zenigame `sorting.py:99-104` 同等
- front_size <= 2 で全員 +inf: Round 1 [W5] 反映、 「すべて端」 解釈で diversity 保護
- 軸範囲 0 で 0 寄与: zenigame `sorting.py:97-104` 同等、 NaN 防御

#### D5: select_survivors の rng 不要

- crowded-comparison operator (rank → -crowding → genome_hash) で完全 deterministic
- Round 1 [W3] / 概念設計 § 11.2 SSOT
- rng は parent selection (binary tournament の 2 体無作為抽出) でのみ必要

#### D6: 入口契約 ValueError の境界

- T064 contract 違反 (a_pass=True なら bc_result is not None、 a_fail なら bc_result is None) → ValueError
- finite domain 違反 (Pareto 軸 non-finite、 constraint_violation +inf) → ValueError
- pop_size < 1、 population 空 → ValueError
- eligible が空 / pop_size 未満 → warning + 部分結果返し (silent ではない、 caller 責務)

#### D7: invariant_flags.is_feasible の整合性

T061 InvariantFlags の `is_feasible` 属性は `session_close_drop_count == 0 AND negative_equity_drop_open_count == 0` と等価 (T061 詳細設計)。 T065 は `is_feasible` 属性で feasibility を判定、 count での再計算は不要 (DRY)。

#### D8: select_parent_pair の self-mating fallback `(p1, p1)`

caller (Phase 2 breeding) で `p1 == p2` を「mutation only」 のシグナルとして扱う合意。 T065 自身は (p1, p1) を warning なしで返す。 Phase 2 breeding で `if pair[0] == pair[1]: mutation_only(genome[pair[0]])` 経路を実装。

---

## 施策 2: テスト計画 (test_nsga2_selection.py)

### テストファイル: `tests/alpha_factory/ga/test_nsga2_selection.py`

### 2.1 PR DoD 必須 (handoff § 3.2 + 概念設計 § 7.2)

- `test_a_fail_individual_excluded_from_nsga_selection`
- `test_b_invariant_fail_individual_excluded_from_pareto_axis_source`

### 2.2 ParetoAxis / extract_pareto_axis (Round 1 [S3] / [C3])

- `test_extract_pareto_axis_uses_t064_b_pooled_cf_net_pnl_after_cost`
- `test_extract_pareto_axis_uses_pooled_dd_per_fold_max_not_concat_dd`
- `test_extract_pareto_axis_uses_t062_mission_inf_gap`
- `test_extract_pareto_axis_rejects_b_pooled_cf_max_dd_as_f2_source` (negative test)
- `test_extract_pareto_axis_raises_value_error_when_b_pooled_cf_is_none`
- `test_extract_pareto_axis_raises_value_error_on_non_finite_net_pnl`
- `test_extract_pareto_axis_raises_value_error_on_non_finite_max_dd`
- `test_extract_pareto_axis_raises_value_error_on_non_finite_mission_inf_gap`

### 2.3 compute_effective_constraint_violation (Round 1 [C2])

- `test_compute_effective_constraint_violation_zero_when_fully_feasible`
- `test_compute_effective_constraint_violation_invariant_violation_dominates_slack`
- `test_compute_effective_constraint_violation_raises_value_error_on_inf_constraint_violation`
- `test_compute_effective_constraint_violation_raises_value_error_on_negative_invariant_count`
- `test_compute_effective_constraint_violation_session_close_drop_count_increases_violation`
- `test_compute_effective_constraint_violation_negative_equity_drop_open_count_increases_violation`

### 2.4 constrained_dominates (Deb 2000)

- `test_constrained_dominates_feasible_vs_infeasible_returns_true`
- `test_constrained_dominates_infeasible_vs_feasible_returns_false`
- `test_constrained_dominates_both_feasible_uses_pareto_three_axes`
- `test_constrained_dominates_both_infeasible_smaller_violation_dominates`
- `test_constrained_dominates_equal_violation_returns_false`
- `test_constrained_dominates_equal_pareto_axes_returns_false`

### 2.5 non_dominated_sort

- `test_non_dominated_sort_three_axis_separates_pareto_fronts`
- `test_non_dominated_sort_constrained_domination_propagates`
- `test_non_dominated_sort_single_individual_returns_front_one`
- `test_non_dominated_sort_all_non_dominated_returns_one_front`
- `test_non_dominated_sort_total_order_assigns_sequential_fronts`
- `test_non_dominated_sort_empty_input_returns_empty_dict` (詳細 Round 1 [S2])

### 2.6 crowding_distance (Round 1 [W5] / [C3])

- `test_crowding_distance_three_axis_normalized_endpoints_inf`
- `test_crowding_distance_front_size_one_returns_inf`
- `test_crowding_distance_front_size_two_all_inf`
- `test_crowding_distance_zero_range_axis_contributes_zero`
- `test_crowding_distance_uniform_distribution_equal_internal_distances`

### 2.7 select_survivors (Round 1 [W3])

- `test_select_survivors_uses_rank_then_crowding_then_genome_hash`
- `test_select_survivors_excludes_a_fail_and_b_invariant_fail`
- `test_select_survivors_does_not_require_rng_argument` (signature 検証)
- `test_select_survivors_returns_empty_tuple_when_all_excluded`
- `test_select_survivors_returns_full_eligible_when_below_target_size`
- `test_select_survivors_raises_value_error_on_t064_contract_violation_a_pass_no_bc`
- `test_select_survivors_raises_value_error_on_t064_contract_violation_a_fail_with_bc`
- `test_select_survivors_raises_value_error_on_target_size_below_one`

### 2.8 binary_tournament (Round 2 [Critical] crowded-comparison only)

- `test_binary_tournament_deterministic_with_seeded_rng`
- `test_binary_tournament_uses_crowded_comparison_operator_not_constrained_domination` (Round 2 [Warning])
- `test_binary_tournament_lower_rank_wins_over_higher_rank`
- `test_binary_tournament_higher_crowding_wins_when_rank_equal`
- `test_binary_tournament_smaller_genome_hash_wins_when_rank_and_crowding_equal`

### 2.9 select_parent_pair

- `test_select_parent_pair_avoids_self_mating_within_max_retry`
- `test_select_parent_pair_falls_back_to_self_when_pool_exhausted`
- `test_select_parent_pair_uses_sort_keys_for_tournament_not_re_evaluating`
- `test_select_parent_pair_deterministic_with_seeded_rng`
- `test_select_parent_pair_single_survivor_returns_self_pair` (詳細 Round 1 [C1] / [S2])
- `test_select_parent_pair_empty_survivors_raises_value_error`
- `test_select_parent_pair_duplicate_genome_hash_falls_back_to_self_pair` (詳細 Round 1 [S2])

### 2.10 run_generation_selection (top-level)

- `test_run_generation_selection_eligible_set_empty_warns_and_returns_empty`
- `test_run_generation_selection_eligible_below_pop_size_warns`
- `test_run_generation_selection_single_eligible_uses_self_mating_fallback`
- `test_run_generation_selection_all_infeasible_uses_violation_ordering`
- `test_run_generation_selection_parent_pairs_length_equals_pop_size` (Round 1 [W2])
- `test_run_generation_selection_excluded_indices_complement_eligible`
- `test_run_generation_selection_raises_value_error_on_pop_size_below_one`
- `test_run_generation_selection_raises_value_error_on_empty_population`
- `test_run_generation_selection_raises_value_error_on_t064_contract_violation_a_pass_no_bc`
- `test_run_generation_selection_raises_value_error_on_t064_contract_violation_a_fail_with_bc`

### 2.11 Determinism (Round 1 [C1] / 詳細 Round 1 [C2])

- `test_run_generation_selection_same_seed_same_result_byte_for_byte`
- `test_run_generation_selection_different_seed_different_result`
- `test_make_selection_seed_uses_blake2b_not_python_hash`
- `test_make_selection_seed_run_id_change_changes_seed`
- `test_make_selection_seed_gen_no_change_changes_seed`
- `test_make_selection_seed_run_id_with_pipe_does_not_collide` (概念 Round 2 [Suggestion 1] delimiter 衝突)
- `test_make_selection_seed_returns_unsigned_64bit_integer`
- `test_run_generation_selection_population_iteration_order_does_not_affect_result` (詳細 Round 1 [C2]、 sorted で eligible 安定順)
- `test_run_generation_selection_duplicate_genome_hash_uses_index_as_final_tiebreak` (詳細 Round 1 [C2] / [S2])
- `test_run_generation_selection_sort_keys_is_4_tuple_with_index_last` (詳細 Round 1 [C2])
- `test_individual_evaluation_index_must_match_population_dict_key` (詳細 Round 2 [W3] / [S1] index 一意性契約 test)
- `test_run_generation_selection_population_with_inconsistent_index_value_raises_value_error` (詳細 Round 2 [S1] index 重複時の禁止動作)

### 2.12 GenerationSelectionResult immutability

- `test_generation_selection_result_front_assignments_is_mapping_proxy`
- `test_generation_selection_result_crowding_distances_is_mapping_proxy`
- `test_generation_selection_result_excluded_indices_is_frozenset`
- `test_generation_selection_result_parent_pairs_is_tuple`
- `test_generation_selection_result_survivor_indices_is_tuple`

### 2.13 sample_size_warnings 列挙 (Round 1 [W4] operational)

- `test_run_generation_selection_eligible_below_thirty_emits_operational_threshold_warning`
- `test_run_generation_selection_eligible_below_ten_emits_critically_low_warning`
- `test_run_generation_selection_eligible_zero_emits_set_empty_warning`
- `test_run_generation_selection_no_feasible_individuals_emits_warning`
- `test_run_generation_selection_warning_codes_independent_of_c7_correlation_guard` (Round 1 [W4])

総テスト数: 約 60 件。 fixtures (`conftest.py`) で `make_individual_eval`、 `make_bc_result`、 `make_mission_gap`、 `make_invariant_flags` 等の builder を共通化。

---

## C2 parallel-path 5 段階 grep DoD (T062-T064 で確立した手順)

T065 は新規 module で既存への組込なしのため、 「再エクスポート」 「runtime 配線シンボル」 段階は Phase 2 で初めて該当する。 Phase 1 (T065 PR) では:

### 段階 1 (直 import) — 詳細 Round 1 [W4] 反映: tests を除外して機械判定可能に

```bash
# tests を除外して 「テスト以外で 0 件」 を機械判定
grep -rn --exclude-dir=tests -E "^from alpha_factory\.ga\.nsga2_selection import|^import alpha_factory\.ga\.nsga2_selection" \
  src/alpha_factory scripts
```
期待: **0 件**。 テスト経路 (`tests/alpha_factory/ga/test_nsga2_selection.py`) は exclude-dir=tests で除外済。 別途 tests 配下の hit 確認は:
```bash
grep -rn -E "^from alpha_factory\.ga\.nsga2_selection import|^import alpha_factory\.ga\.nsga2_selection" \
  tests/alpha_factory/ga/
```
期待: テストファイル (`test_nsga2_selection.py`) でのみ hit。

### 段階 2 (alias import)

```bash
grep -rn -E "^import alpha_factory\.ga\.nsga2_selection as|^from alpha_factory\.ga\.nsga2_selection import .* as" \
  src/alpha_factory tests scripts
```
期待: 0 件 (Phase 1 では alias 不使用)。

### 段階 3 (relative import)

```bash
grep -rn -E "from \. import nsga2_selection|from \.nsga2_selection import" \
  src/alpha_factory
```
期待: 0 件 (T065 PR では `src/alpha_factory/ga/__init__.py` 空 + 他 module から relative import なし)。

### 段階 4 (再エクスポート)

```bash
grep -rn -E "nsga2_selection|run_generation_selection|constrained_dominates|extract_pareto_axis" \
  src/alpha_factory/__init__.py src/alpha_factory/ga/__init__.py
```
期待: 0 件 (Phase 1 では再エクスポートしない、 直接 module import のみ)。

### 段階 5 (runtime 配線シンボル)

```bash
grep -rn -E "run_generation_selection|GenerationSelectionResult|extract_pareto_axis|constrained_dominates|non_dominated_sort|select_survivors|binary_tournament|select_parent_pair|make_selection_seed" \
  src/alpha_factory/stage_gate.py src/alpha_factory/archive.py src/alpha_factory/cross_pair.py \
  src/alpha_factory/swim_lane.py scripts/alpha_factory/run_ga.py
```
期待: 0 件 (Phase 2 まで配線禁止)。

DoD: 上記 5 段階 grep で Phase 1 期待値 (テスト以外 0 件) を確認、 失敗時は本 TODO 不完了。

---

## Phase 2 (T066 / T067 / T070 / T071 と同時、 別 PR) DoD 申し送り (9 箇所、 詳細 Round 2 [W1] 反映)

| # | ファイル / 箇所 | 担当 | 内容 |
|---|---|---|---|
| 1 | `src/alpha_factory/ga/__init__.py` で `from .nsga2_selection import ...` | T066 | T066 push_pull_fsm.py / T067 archive admission から import 可能化 |
| 2 | (新規) `scripts/alpha_factory/run_ga.py` per-generation chain | T066 | T063 evaluate_generation → T064 evaluate_bc_for_a_pass → T062 evaluate_mission_inf_gap → **T065 run_generation_selection** → T066 push_pull_state_advance → archive admission |
| 3 | (新規) `src/alpha_factory/ga/push_pull_fsm.py`: T065 survivors を CA:DA に partition | T066 | push 84/108 / pull 120/72 比例で source partition 分割、 T065 binary_tournament へ partition 別に渡す |
| 4 | `config/alpha_factory/default.yaml`: GA core パラメータ追加 | T066 | `ga.population_size: 192`, `ga.generations: 64`, `ga.crossover_rate: 0.7`, `ga.mutation_rate: 0.3`, `ga.invariant_violation_penalty: 1.0e6`, `ga.tournament_max_retry: 3` を T058 schema v2 準拠で追加 |
| 5 | `src/alpha_factory/archive.py`: A-fail / B-invariant-fail を archive admission 全段階から排除 + default-deny test | T067 | T065 GenerationSelectionResult.excluded_indices を消費、 archive 流入 (mission_pass / progress_pass / score_bypass) で除外 |
| 6 | (新規) `src/alpha_factory/observability/selection_metrics.py`: front1 cardinality / feasible_ratio_ema / violation distribution / parent_pair self-mating ratio 観測 | T071 | T065 GenerationSelectionResult を消費、 schema v2 metric として emit |
| 7 | (新規) `tests/integration/test_ga_run_with_t065_selection.py`: per-generation chain integration test | T066 | T063 → T064 → T062 → T065 chain の end-to-end smoke (1 世代 1 個体 toy) |
| 8 | (新規) `docs/alpha_factory/ga-architecture.md` 新設、 NSGA-II + constrained-domination の新仕様 | T066 | 旧 selection 経路全廃 + T065 仕様 (B-pooled SSOT, Pareto 3 軸, constrained-domination, A-fail/B-invariant-fail 除外, deterministic tie-break, blake2b seed) を反映 |
| 9 | 旧 selection 経路の削除対象シンボル一覧 (詳細 Round 1 [S3] 反映) | T066 | Phase 2 着手前に grep で確定し、 全廃漏れ防止。 候補: `stage_gate.py:evaluate_stage_a` / `evaluate_stage_b` / `evaluate_stage_c` / `archive.py` の旧 admission 関数群 / `cross_pair.py` の旧 selection 統合 / `swim_lane.py` の selection 関連 / `scripts/run_ga.py` の per-generation selection 経路。 Phase 2 PR で `git rm` または empty replace し、 grep で残存ゼロを DoD に含める |

各申し送りに対する Phase 2 PR の DoD:
- T065 で定義した 8 関数 + 3 dataclass + 1 const + 1 helper を import 経由で利用 (再実装禁止)
- C2 5 段階 grep で Phase 2 配線完了確認 (上記 grep DoD の段階 4-5 で hit が想定通り出現)
- T065 PR の単体テスト全 60 件は touch せず、 integration test (#7) を別途追加

---

## 残論点 / Decision Pending (smoke 後再校正候補)

### R1: INVARIANT_VIOLATION_PENALTY 値の確定

- 仮: `1.0e6`
- 事前上界根拠 (詳細 Round 1 [S1] 反映): T062 `constraint_violation` は 4 slack 由来の `max(0, -slack_*)` の sum (or 同等)、 typical 値域 [0, 数十]、 上界目安 1.0e2。 1.0e6 ≫ 1.0e2 のため invariant 1 件が slack 由来 violation の任意組合せを支配する。 invariant 件数が万単位になることは intraday FX で実用上想定外 (1 個体 backtest で session_close_drop が万件発生 = データ pipeline 異常 → upstream fail-fast)
- smoke 観測 DoD (概念 Round 1 [S2]):
  - invariant violation 個体が rank 末尾に確実に行く (mass 配分検証)
  - all-infeasible front でも数値安定 (oscillation / overflow なし)
  - finite violation 域で penalty による monotone ordering が崩れない (slack 1 / invariant 1 比較等)
- synthesis § 15 残論点に追記候補 (Phase 2 で対応)

### R2: non_dominated_sort のパフォーマンス

- O(M*N^2) で pop=192-256、 1 epoch で約 80M 比較
- 純 Python 実装で smoke 完走を確認、 必要なら Numba JIT (T053 composite-numba-jit と同様パターン)
- INCONCLUSIVE (smoke 後 profile で再判定)

### R3: crowding ε 厚 tie-break (zenigame T333)

- Phase 1 では採用しない (genome_hash で deterministic 確保)
- smoke で「selection 多様性低下」 観測時に検討
- INCONCLUSIVE

### R4: binary tournament k=2 vs k=3

- synthesis § 7.1「binary tournament」 確定で k=2
- k=3 は INCONCLUSIVE (smoke 後検討、 採用優先度低)

### R5: parent_pairs を pop_size or 2*pop?

- pop_size 固定 (Round 1 [W2])、 offspring pop_size 体生成想定
- 2*pop 案 (rank+crowding 淘汰前提) は不採用、 fx は per-generation pop_size 体抽出
- Phase 2 breeding 仕様で確定済の前提

### R6: zenigame `optimize.py:2125,2141` の主選抜実装差分

- handoff § 4.2 で B-pooled 主選抜は zenigame `optimize.py:2125,2141` 同等
- Phase 2 で T066 整合時に当該箇所を実 grep で確認、 fx 側 implementation との差分明示
- INCONCLUSIVE (Phase 2 で要確認)

---

## zenigame コード参照 (詳細設計時の流用判断材料)

| 機構 | zenigame ファイル | 行番号 | fx 流用方針 |
|---|---|---|---|
| crowding_distance | `src/trading/alpha_factory/ga/nsga2/sorting.py` | 60-125 | 3 軸正規化 + ε 端 +inf を踏襲、 軸範囲 0 寄与 0 (line 97-104) を踏襲 |
| Selection (front sort + tie-break) | `src/trading/alpha_factory/ga/nsga2/selection.py` | 36-159, 293-353 | front sort は流用、 MG tie-break (T333) は **採用しない** (synthesis Round 19 確定) |
| Binary tournament | `src/trading/alpha_factory/ga/nsga2/breeding.py` | 211, 255 | 2 体抽出構造を流用、 比較は crowded-comparison operator (Round 2 [Critical]) |
| GA optimize loop | `src/trading/alpha_factory/ga/nsga2/optimize.py` | 950, 1006/1195, 2125/2141 | Phase 2 (T066) で整合時に参照 |
| Determinism (RNG seed) | `src/trading/alpha_factory/ga/nsga2/core.py` | 114 | `random.Random` 使用、 seed は blake2b ベース (Round 1 [C1]) で stable 化 (zenigame の `int` seed と同等準拠) |
| constrained-domination | (zenigame 未実装) | — | **fx で正式新設** (Deb 2000 純準拠) |

---

## 完了判定 (詳細設計 APPROVED 条件)

- [ ] § 施策 1 で `nsga2_selection.py` の全シグネチャ (3 dataclass + 1 const + 7 helper + 1 entry + 1 seed helper) が概念設計 § 11.2 と完全一致
- [ ] § 施策 2 でテスト計画が 13 sub-suite × 約 60 件、 PR DoD 必須 2 件含む
- [ ] § C2 5 段階 grep DoD で期待 0 件 (テスト以外) が明示
- [ ] § Phase 2 申し送り **9 箇所** が具体ファイル名 + 担当 TODO 名で列挙
- [ ] § 残論点 6 件が Decision Pending タグ付き、 smoke 後再校正条件明示
- [ ] Codex 詳細レビュー APPROVED (Round 1-3 で Critical / Warning / Suggestion 全反映)

---

## 補足: synthesis Round 21 改訂後の整合性

本詳細設計は synthesis Round 21 (2026-04-30 改訂) 後の確定値に基づく:

- archive CA #5 = `mission_signed_margin` (T066-T067 責務、 T065 では参照しない)
- `mission_inf_gap` は Pareto f3 minimize 用 (T065 で消費)
- `constraint_violation` は T062 確定式 (NSGA-II constrained-domination 用、 T065 で消費 + finite domain 制約)
- `mission_margin` は BACKWARD COMPAT (T065 では参照しない)

Phase 2 で archive admission/eviction を実装する際、 synthesis § 8.3 (Round 21 改訂) の lex 順序 (CA #5 = mission_signed_margin) を SSOT として依拠する。 T065 は Pareto search の責務に閉じ、 archive 系には touch しない。
