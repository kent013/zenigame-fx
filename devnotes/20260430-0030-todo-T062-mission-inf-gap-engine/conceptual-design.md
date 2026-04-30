# 概念設計: T062 — mission_inf_gap engine

**Round 1 修正反映** (Codex CHANGES_REQUESTED → CHANGES_APPLIED): +inf sentinel の Pareto 排除保証は constrained-domination (Deb 2000) を T065 側で実装する前提で再定義 / synthesis § 8.3 の `mission_margin = -mission_inf_gap` と「達成超過余裕」 命名の矛盾を分離 (mission_margin は synthesis 命名通り保持、 archive CA #5 の signed margin は新規 `mission_signed_margin` で計算) / per_metric_shortfall infeasible 時の diagnostic-only 明記 / NaN→ValueError の caller 責務明文化 / zenigame との semantic equivalence 主張削除 / Deb et al. 2002 引用追加。

## 2026-04-30 注記: synthesis Round 21 改訂済

本概念設計策定時 (2026-04-30 00:30 JST) は synthesis § 8.3 の CA #5 が `mission_margin = -mission_inf_gap` で、 命名と数式が乖離していた。 そのため概念設計内では「synthesis 改訂候補」 として `mission_signed_margin` を新設し、 archive CA #5 用の暫定 SSOT として位置付けていた (Round 1 / Round 2 議論結果)。 **2026-04-30 10:45 JST に synthesis Round 21 改訂 PR (`devnotes/20260430-1045-synthesis-revise-mission-signed-margin/`) が成立**し、 synthesis § 8.3 で CA #5 = `mission_signed_margin = min(slack_*)` が SSOT に昇格、 `mission_margin` は BACKWARD COMPAT 整理に確定。 本概念設計内の「synthesis 改訂候補」 「T064 PR 完了後に synthesis 改訂 PR を別途」 等の表記は **改訂済の事実反映として「改訂済 (synthesis Round 21)」 と読み替える**。 設計内容 (mission_signed_margin の定義、 用途、 archive CA #5 ordering 用) は不変。

## 背景・課題

synthesis § 6.4 / § 6.5 で確定した **mission_inf_gap** は GA NSGA-II の **Pareto 3 軸 f3 (minimize)** として selection 圧の中核を担う。 T061 (canonical 5 engine) で計算した signed slack 5 指標のうち **win_rate を除く 4 指標** (sharpe / pnl / dd / tc) を inf-norm shortfall で集約した値。

具体的な責務:

1. **mission_inf_gap 計算**: synthesis § 6.4 厳密式 `mission_inf_gap = max(max(0, -slack_sharpe), max(0, -slack_pnl), max(0, -slack_dd), max(0, -slack_tc))`
2. **margin 系 helper**: T065-T066 (NSGA-II 母集団選抜) と T067 (archive admission) で必要な「達成余裕」 系 metric (`mission_margin = -mission_inf_gap` 等)
3. **fail-fast 受け継ぎ**: T061 の `InvariantFlags.is_feasible=False` なら mission_inf_gap = +inf (selection から確実に排除)
4. **deterministic / pure**: GA selection / archive consumer から呼ぶため副作用なし

T062 は **engine (= pure 計算モジュール) のみ**を提供する。 NSGA-II Pareto front 計算 / archive admission への組込は T065-T066 / T067 (Phase 2) の責務。

## 前提検証 (C4) — current HEAD `main@ea56484` 基準

| 前提 | verified | 出典 |
|---|---|---|
| `mission_inf_gap = max(max(0, -slack_sharpe/pnl/dd/tc))` (win_rate 含まない) | ✓ | synthesis § 6.4 |
| Pareto 3 軸 f3 (search 専用): minimize mission_inf_gap | ✓ | synthesis § 6.5 |
| canonical 5 worst gate と Pareto 3 軸を**直接同じランキングで混ぜない** | ✓ | synthesis § 6.5 ガイドライン |
| T061 が signed slack 5 を返す (slack_sharpe / slack_pnl / slack_dd / slack_tc / slack_wr) | ✓ | T061 詳細設計 APPROVED |
| invariant fail-fast (is_feasible=False) で selection 全段階から排除 | ✓ | synthesis § 6.6 |
| `mission_margin = -mission_inf_gap` を archive eviction lex 順序で使用 (CA #5: `mission_margin (= -mission_inf_gap、 達成超過余裕)`) | ✓ | synthesis § 8.3 |
| zenigame の `compute_signed_slack_margin` (`live_criteria_gap.py`) は 5 指標 signed slack の `min` を返す (margin_inf)。 fx 側は **win_rate 除外** で 4 指標化 | ✓ | zenigame `live_criteria_gap.py:170-209` |
| 既存 zenigame-fx は mission_inf_gap 相当の helper を持たない | ✓ | grep `mission_inf_gap` `find /Users/ishitoya/repository/zenigame-fx/src -name "*.py"` で hit なし |

## 改善アイデア

### 設計方針

**「T061 出力を入力に取る薄い engine」 + margin 系 helper**:

1. **入力契約**: T061 `CanonicalFiveResult` の `slack_sharpe / slack_pnl / slack_dd / slack_tc` を消費 (4 指標のみ、 slack_wr は無視)
2. **engine 本体**: synthesis § 6.4 厳密式で mission_inf_gap を計算
3. **invariant 連鎖**: `CanonicalFiveResult.invariants.is_feasible=False` なら mission_inf_gap = +inf (sentinel) で selection 排除
4. **出力契約**: `MissionGapResult` dataclass で mission_inf_gap + 4 指標別 shortfall + invariant 連鎖 flag

### Module 構造

```
src/alpha_factory/mission_inf_gap.py (新規、 T062 PR スコープ)
├── DataClasses
│   ├── MissionGapResult — mission_inf_gap + mission_margin + mission_signed_margin + 4 指標別 shortfall + is_feasible 連鎖
│   └── (T061 の CanonicalFiveResult を入力として使用)
├── Constants
│   ├── MISSION_GAP_INFEASIBLE_SENTINEL = float("inf")
│   ├── MISSION_SIGNED_MARGIN_INFEASIBLE_SENTINEL = float("-inf")
│   └── MISSION_INF_GAP_METRIC_KEYS = ("sharpe", "pnl", "dd", "tc")  # win_rate 除外
├── Helpers (pure functions)
│   ├── compute_mission_inf_gap_from_slacks(slacks: dict[str, float]) -> float
│   ├── compute_mission_margin(mission_inf_gap: float) -> float  # synthesis § 8.3 命名通り = -mission_inf_gap
│   ├── compute_mission_signed_margin(slacks: dict[str, float]) -> float  # 4 指標 signed slack の min (archive CA #5 実用 ordering 用)
│   └── extract_per_metric_shortfalls(slacks: dict[str, float]) -> dict[str, float]
└── Top-level entry
    └── evaluate_mission_inf_gap(result: CanonicalFiveResult) -> MissionGapResult
```

### 入力契約

T062 は T061 `CanonicalFiveResult` を直接受け取る (依存方向: T062 → T061):

```python
def evaluate_mission_inf_gap(result: CanonicalFiveResult) -> MissionGapResult:
    """T061 出力を mission_inf_gap (Pareto f3) に変換.

    Args:
        result: T061 評価結果。 slack_sharpe / slack_pnl / slack_dd / slack_tc を消費。
            slack_wr は **無視** (synthesis § 6.4: win_rate を含まない)。
            result.invariants.is_feasible=False なら mission_inf_gap = +inf を強制。

    Returns:
        MissionGapResult (frozen dataclass)
    """
```

### 出力契約

```python
@dataclass(frozen=True)
class MissionGapResult:
    """Pareto 3 軸 f3 用 mission_inf_gap 結果 + archive eviction 用 margin 系.

    field:
    - mission_inf_gap: synthesis § 6.4 確定式の値 (Pareto f3 minimize 用)
        - is_feasible=True かつ 4 指標全達成 → 0.0
        - is_feasible=True かつ 1 指標以上未達 → max(0, -slack_m) > 0
        - is_feasible=False → +inf (MISSION_GAP_INFEASIBLE_SENTINEL)

    - mission_margin: synthesis § 8.3 命名 (= -mission_inf_gap)
        - **重要 (Round 1 [Critical] 2 反映)**: 値域は常に <= 0 (mission_inf_gap >= 0 のため)。
          synthesis § 8.3 の「達成超過余裕」 という命名は数式と乖離している。 4 指標全達成時は
          一律 0.0 で、 達成超過の大きさを表現できない。 archive CA #5 で実用 ordering を
          したい場合は `mission_signed_margin` を使うこと。 本 field は synthesis 命名 backward
          compat 用。
        - is_feasible=False → -inf

    - mission_signed_margin: archive CA #5 で実用 ordering する signed margin
        - = `min(slack_sharpe, slack_pnl, slack_dd, slack_tc)` (4 指標 signed slack の min)
        - 値域: feasible なら任意実数 (正値=4 指標全余裕、 負値=1 指標以上不足)
        - 4 指標全達成かつ余裕大なら large positive、 1 指標 marginal なら small positive、
          1 指標未達なら negative
        - is_feasible=False → -inf (MISSION_SIGNED_MARGIN_INFEASIBLE_SENTINEL)

    - per_metric_shortfall: 4 指標別 max(0, -slack_m) dict
        - 診断用 (observability / archive metadata、 Round 1 [Warning] 1 反映: diagnostic-only)
        - infeasible 時も値は計算されるが、 strategic_* infeasible なら slack の意味が損なわれる
          可能性があるため downstream は infeasible flag と組合せて参照すること

    - is_feasible: T061 InvariantFlags.is_feasible を継承
        - False の場合 mission_inf_gap=+inf、 mission_margin=-inf、 mission_signed_margin=-inf
        - **重要 (Round 1 [Critical] 1 反映)**: +inf sentinel **だけでは** Pareto rank 末端化を
          保証しない (f1=net_pnl, f2=max_dd で他より優れていれば非支配になり得る)。
          T065 (NSGA-II) 側で **constrained-domination (Deb 2000)** を実装し、 feasible
          個体は infeasible 個体を unconditionally dominate するルールを適用する責務 (T065 PR DoD)。
          T062 は +inf 信号を提供するのみで、 排除保証は T065 が実装する。
    """
    mission_inf_gap: float
    mission_margin: float
    mission_signed_margin: float
    per_metric_shortfall: dict[str, float]  # keys: sharpe / pnl / dd / tc
    is_feasible: bool
```

### 数式仕様 (synthesis § 6.4 厳密準拠)

#### synthesis ↔ T062 数式 差分ゼロ確認表 (Round 1 修正反映)

| # | synthesis § 6 / § 8 式 | T062 実装式 | 差分 | 補足 |
|---|---|---|---|---|
| 1 | `mission_inf_gap = max(max(0, -slack_sharpe), max(0, -slack_pnl), max(0, -slack_dd), max(0, -slack_tc))` | 同上 (4 指標 inf-norm) | **ゼロ** | slack_wr 含まない |
| 2 | f3 minimize objective | `mission_inf_gap` を直接 NSGA-II 軸として使用 | **ゼロ** | 値域 [0, +inf] (+inf = infeasible) |
| 3 | invariant fail-fast → selection 排除 (synthesis § 6.6) | is_feasible=False で mission_inf_gap=+inf | **拡張 + T065 連携** | T062 は +inf 信号を提供のみ。 排除保証は T065 で **constrained-domination (Deb 2000)** 実装が必須 (Round 1 [Critical] 1 反映) |
| 4 | `mission_margin = -mission_inf_gap` (synthesis § 8.3) | 同上 | **ゼロ (synthesis 命名通り保持)** | 値域 <= 0、 達成超過余裕を表現できない (synthesis § 8.3 自身の semantic 矛盾。 Round 1 [Critical] 2 反映で別途 mission_signed_margin を新設、 archive CA #5 実用 ordering 用) |
| 5 | (新規、 synthesis § 8.3 補完) `mission_signed_margin = min(slacks for m in 4 指標)` | 同上 | **synthesis 補完 (Round 2 議論候補)** | feasible 時に達成超過の大きさを表現可能、 archive CA #5 実用 ordering 用。 synthesis 改訂候補として synthesis § 15 残論点に追記候補 |

#### compute_mission_inf_gap_from_slacks

```python
MISSION_INF_GAP_METRIC_KEYS: Final[tuple[str, ...]] = ("sharpe", "pnl", "dd", "tc")
# synthesis § 6.4: win_rate を含まない (canonical 5 gate 専用)

def compute_mission_inf_gap_from_slacks(slacks: dict[str, float]) -> float:
    """4 指標 signed slack から mission_inf_gap を計算.

    式: mission_inf_gap = max(max(0, -slacks[m]) for m in MISSION_INF_GAP_METRIC_KEYS)

    slacks に必須 key (sharpe/pnl/dd/tc) が欠損した場合は ValueError raise (caller 側責務、
    本関数の no-raise 契約は外: 入力 dict の field 欠損は engine の bug indicator)。
    slack 値が +inf / -inf / NaN の場合:
    - +inf (大きな余裕): max(0, -inf) = 0 → 寄与なし
    - -inf (極端な不足): max(0, +inf) = +inf → mission_inf_gap = +inf
    - NaN: ValueError raise (合成エラー、 caller が修正すべき)
    """
```

### 重要な設計判断

**1. T061 への直接依存**

- **採用**: `evaluate_mission_inf_gap(result: CanonicalFiveResult)` で T061 出力を受け取る
- **理由**: T061 と T062 は logical pipeline (canonical 5 → mission_inf_gap)、 同じ trade list を 2 回 evaluate するのは無駄
- **代替案 (棄却)**: T062 が trade list / bars / thresholds を直接受け取り、 内部で T061 を呼ぶ → T061 の責務分離が壊れる

**2. mission_inf_gap = +inf sentinel (is_feasible=False 時) + constrained-domination 連携 (Round 1 [Critical] 1 反映)**

- **採用**: `MISSION_GAP_INFEASIBLE_SENTINEL = float("inf")`
- **+inf だけでは Pareto rank 末端化を保証しない**:
  - 多目的最小化では、 ある個体の f3=+inf でも、 f1 (max net_pnl) / f2 (min max_dd) で他より十分良ければ非支配になり得る
  - +inf は「その軸で最悪」 を意味するだけ
- **T065 (NSGA-II) 側での constrained-domination 実装が必須** (Phase 2 申し送り):
  - Deb (2000) "An efficient constraint handling method for genetic algorithms" の constrained-domination ルール:
    1. feasible 個体は infeasible 個体を unconditionally dominate する
    2. infeasible 個体同士は constraint violation (= mission_inf_gap or 別途集計) が小さい方が dominate
    3. feasible 個体同士は通常の Pareto dominance
  - これにより infeasible 個体が Pareto front 上位に残る経路を完全に排除
- **T062 の責務**: +inf 信号 + is_feasible flag を提供するのみ。 排除保証は T065 が実装
- **代替案 (棄却)**: is_feasible=False を完全に別経路で渡す → T062 出力で複数経路を扱う必要、 経路分散リスク

**3. win_rate 除外の SSOT 化**

- **採用**: `MISSION_INF_GAP_METRIC_KEYS = ("sharpe", "pnl", "dd", "tc")` を T062 内 const、 synthesis § 6.4 の確定値を型で固定
- **理由**: 4 指標を直接列挙することで、 T061 の slack_wr を誤って混ぜる経路を防ぐ。 synthesis 確定値の machine-readable 表現

**4. mission_margin / mission_signed_margin 二段構造 (Round 1 [Critical] 2 反映)**

- **synthesis § 8.3 矛盾の認識**:
  - synthesis § 8.3 は CA #5 を `mission_margin (= -mission_inf_gap、 達成超過余裕)` と定義
  - 数式上 `mission_margin = -mission_inf_gap` は常に <= 0 (mission_inf_gap >= 0 のため)
  - 4 指標全達成個体は一律 0.0 で「達成超過余裕」 を表現できない (= synthesis 命名と数式が矛盾)
- **採用**:
  - `mission_margin = -mission_inf_gap` (synthesis § 8.3 命名通り、 backward compat)
  - `mission_signed_margin = min(slack_sharpe, slack_pnl, slack_dd, slack_tc)` (4 指標 signed slack の min、 達成超過余裕を**実際に**表現する signed margin)
  - archive eviction CA #5 ordering は **`mission_signed_margin` を使う**ことを T067 申し送り
- **synthesis 改訂候補 (Round 2 残論点)**: synthesis § 8.3 / § 15 を「CA #5 = mission_signed_margin」 に改訂すべきか? 実装で signed margin を導入したことを synthesis 側に反映するか? T064 PR 完了後に synthesis 改訂 PR を別途出す
- **代替案 (棄却)**: synthesis 命名通りの `mission_margin` のみ提供 → CA #5 で feasible 個体間の超過余裕で tie-break できず、 archive 多様性確保に失敗

**5. per_metric_shortfall の出力**

- **採用**: 4 指標別 shortfall dict を `MissionGapResult` に含める
- **理由**: T071 observability / archive metadata で「どの指標が不足しているか」 を診断したい。 mission_inf_gap だけだと argmax 情報が失われる
- **冗長性**: 計算量は O(4)、 軽微

**6. T061 との分離維持**

- **採用**: T061 では mission_inf_gap を計算しない (synthesis § 6.4 「slack_wr は mission_inf_gap に含めない」 制約を T062 で実装)
- **T061 の出力**: signed slack 5 (sharpe / pnl / dd / tc / wr) + canonical 5 worst gap
- **T062 の出力**: mission_inf_gap (4 指標 inf-norm) + mission_margin + per_metric_shortfall

## 期待効果

### live_criteria 達成への構造的貢献

- **Pareto 3 軸 f3 の SSOT 化**: GA NSGA-II が同じ engine を呼び、 metric 計算の分散を排除
- **win_rate 除外の machine-readable 強制**: T061 から slack_wr を誤って混ぜる経路を const + 4 指標列挙で防ぐ
- **invariant fail-fast の連鎖**: T061 の is_feasible=False が +inf sentinel に変換され、 GA selection / archive 全段階から確実に排除
- **mission_margin の SSOT**: archive eviction (T067) で同じ値を消費、 計算分散を排除

### 副次効果

- **T065-T066 (NSGA-II + CPPS) 実装簡素化**: Pareto 3 軸 f3 を `MissionGapResult.mission_inf_gap` で直接取得可能
- **T067 (Loop closure) 実装簡素化**: archive eviction CA #5 (mission_margin) を `MissionGapResult.mission_margin` で直接取得可能
- **observability**: per_metric_shortfall で「使命達成のボトルネック指標」 を診断可能 (T071 観測)

## 実装方針 (概要)

### コンポーネント変更 (Phase 1: T062 PR)

| ファイル | 変更内容 |
|---|---|
| `src/alpha_factory/mission_inf_gap.py` | **新規作成**。 MissionGapResult dataclass + helper 関数 + top-level entry |
| `tests/alpha_factory/test_mission_inf_gap.py` | **新規**。 数式 unit test + invariant 連鎖 test + sentinel test |

**Phase 1 (T062 PR) スコープは上記 2 施策のみ**。 既存 GA / archive / cross_pair への組込は **Phase 2 (T065-T067 と同時)** で実施。 T062 PR 単独では既存経路に touch しない。

### Phase 2 (T065-T067 と同時、 別 PR) 申し送り

T062 完了後、 GA / archive consumer が T062 engine を消費する形に置換する必要がある。

**Phase 2 で同時更新が必要な箇所** (周辺 consumer 含む、 Round 1 [Suggestion] 3 反映で T065 constrained-domination 必須化):

| # | ファイル / 箇所 | 変更内容 | 担当 TODO |
|---|---|---|---|
| 1 | (新規) `src/alpha_factory/ga/nsga2_objectives.py` | Pareto 3 軸 f3 = `MissionGapResult.mission_inf_gap` を直接消費 | T065 |
| 2 | **(新規) `src/alpha_factory/ga/constrained_domination.py`** | **Round 1 [Critical] 1 反映の必須項目**: NSGA-II non-dominated sorting 前に feasible filter / constrained-domination (Deb 2000) を実装。 feasible 個体は infeasible を unconditionally dominate、 infeasible 同士は mission_inf_gap (= constraint violation) 小さい方が dominate | T065 |
| 3 | (新規) `src/alpha_factory/ga/archive_eviction.py` | CA eviction lex #5 = **`MissionGapResult.mission_signed_margin`** を直接消費 (synthesis § 8.3 の `mission_margin` 命名は数式矛盾のため、 実用 ordering には signed margin を使う、 Round 1 [Critical] 2 反映) | T067 |
| 4 | `src/alpha_factory/archive.py` | archive admission が `MissionGapResult.is_feasible` を直接消費 (= GA 側で constrained-domination 適用済前提だが安全網) | T067 |
| 5 | `src/alpha_factory/swim_lane.py` | tier1 evaluator が GA 経由で MissionGapResult を消費 | T065 |
| 6 | `src/alpha_factory/diagnostics_sidecar.py` | per_metric_shortfall を archive metadata に記録 (T058 schema v2 接続) | T067 |
| 7 | `devnotes/.../synthesis.md` (synthesis 改訂候補) | § 8.3 CA #5 を `mission_signed_margin` に改訂、 § 15 残論点に追記 | T064 PR 完了後に synthesis 改訂 PR を別途 |

**周辺 consumer chain 検証 checklist (T060/T061 で起きた漏れと同型を予防)**:

- [ ] T061 `CanonicalFiveResult` → T062 `evaluate_mission_inf_gap` 接続 (依存方向)
- [ ] T062 `MissionGapResult.mission_inf_gap` → NSGA-II Pareto front 計算 (T065)
- [ ] T062 `MissionGapResult.mission_margin` → archive eviction CA #5 (T067)
- [ ] T062 `MissionGapResult.is_feasible` → archive admission / GA selection 全段階の安全網
- [ ] `archive.py:GENOMES_SCHEMA` (T058 schema v2) に `mig_value`, `mig_margin`, `mig_per_metric_shortfall` (or 4 個別 column) 追加
- [ ] log: NSGA-II selection / archive eviction 位置で mission_inf_gap / mission_margin の 1 行 INFO ログ (T071 observability)

### C2 parallel-path 確認 (Phase 1 DoD、 T061 同様 4 段階強化)

旧経路と新経路の物理的分離を以下 4 段階で grep 検証:

1. **直 import**: `grep -rn "from src.alpha_factory.mission_inf_gap" scripts/ src/` → 自身 + tests のみ
2. **再エクスポート**: `grep -rn "mission_inf_gap" src/alpha_factory/__init__.py src/alpha_factory/*.py | grep -v "src/alpha_factory/mission_inf_gap.py:"` → 0 hit
3. **alias / wrapper**: `grep -rn -E "from .* import .* as.*[Mm]ission|^.* = mission_" src/ scripts/` → 0 hit
4. **runtime 配線**: `grep -rn -E "evaluate_mission_inf_gap|MissionGapResult" src/alpha_factory/archive.py src/alpha_factory/cross_pair.py src/alpha_factory/swim_lane.py scripts/alpha_factory/run_ga.py` → 0 hit (Phase 2 まで配線禁止)

## C3 / C7 適用

- **C3 (Collider bias)**: 該当なし (相関分析を新規導入しない)
- **C7 (Sample size)**: 該当なし (T061 出力の slack 値を集約するのみ、 sample size に依存しない)

## 制約・前提

- **T061 マージ後前提**: T062 は `from src.alpha_factory.canonical_metrics import CanonicalFiveResult` で T061 module を import。 T061 マージ前は本 PR を merge しない
- **synthesis § 6.4 確定値厳密準拠**: `MISSION_INF_GAP_METRIC_KEYS = ("sharpe", "pnl", "dd", "tc")` は const、 yaml override 不要
- **invariant 連鎖**: T061 の is_feasible=False は T062 で +inf sentinel に変換、 caller の見落とし防止
- **mission_margin は engine 計算**: T067 で再計算しない、 T062 出力を直接消費

## スコープ外

- T058 / T059 / T060 / T061: 依存先 (Schema v2 / EpochManager / Partition+Fold / canonical 5 engine)
- T063: Stage A evaluator (T061 engine を q_force ranking で消費、 mission_inf_gap は使わない: Stage A は canonical 5 worst gate のみ)
- T064: Stage B/C-lite/C evaluator (T061 engine を消費、 mission_inf_gap は内部 metadata として使用)
- T065-T066: NSGA-II + CPPS (T062 engine を Pareto f3 で消費)
- T067: Loop closure (T062 engine を archive admission / eviction で消費)

## 学術引用 / 先行知見 (Round 1 [Warning] 4 / 5 反映、 full citation 化)

- **Deb, K., Pratap, A., Agarwal, S., & Meyarivan, T. (2002). "A fast and elitist multiobjective genetic algorithm: NSGA-II." IEEE Transactions on Evolutionary Computation, 6(2), 182-197.**: NSGA-II の支配関係と crowding distance の元論文。 +inf を含む解の crowding distance 計算は **要確認** (zenigame 既存実装参照)
- **Deb, K. (2000). "An efficient constraint handling method for genetic algorithms." Computer Methods in Applied Mechanics and Engineering, 186(2-4), 311-338.**: constrained-domination ルールの元論文。 T065 で実装すべき feasible-infeasible 関係定義の根拠
- synthesis § 6.4 / § 6.5 / § 8.3 / § 15: mission_inf_gap / Pareto 3 軸 / archive eviction 確定値 (§ 8.3 の `mission_margin` 命名は数式矛盾、 § 15 に追記候補)
- zenigame `evaluation/live_criteria_gap.py` (`compute_signed_slack_margin`): 5 指標 signed slack + min 集約。 fx 側は **win_rate 除外 + max(0, -slack)** で 4 指標 inf-norm 化。 **「semantic 同等」 という主張は撤回** (Round 1 [Warning] 3 反映): zenigame の `min(slacks)` (signed margin) と fx の `max(max(0, -slack))` (inf-norm shortfall) は可行解同士の序列付け能力が異なる。 fx 側で signed margin が必要な場合は別途 `mission_signed_margin` で計算 (本設計で導入)
- T061 詳細設計 APPROVED: signed slack 5 計算の上位 contract

## Round 1 → Round 2 の改訂点 (Codex review 反映サマリ)

| Round 1 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [C1] +inf sentinel だけで Pareto rank 末端化を保証しない (多目的最小化で f1/f2 が他より良ければ非支配になり得る) | T062 は +inf 信号 + is_feasible flag を提供のみ、 排除保証は **T065 (NSGA-II) で constrained-domination (Deb 2000) 実装が必須** と明文化。 Phase 2 申し送りに必須項目 (constrained_domination.py 新規) を追加 |
| [C2] `mission_margin = -mission_inf_gap` は常に <= 0 で「達成超過余裕」 を表現できない | synthesis § 8.3 の命名と数式の矛盾を認識。 `mission_margin` は synthesis 命名通り保持 (backward compat)、 archive CA #5 実用 ordering 用に **`mission_signed_margin = min(slack_sharpe/pnl/dd/tc)`** を新設。 synthesis 改訂候補として T064 PR 完了後に synthesis § 8.3 / § 15 改訂 PR を別途 |
| [W1] per_metric_shortfall の infeasible 時の意味未確定 | docstring に「diagnostic only、 strategic_* infeasible 時は slack 意味が損なわれる可能性、 downstream は infeasible flag と組合せ参照」 を明記 |
| [W2] NaN→ValueError の障害境界未記述 | docstring に「caller (T065/T067) は **fail-fast 方針**、 selection loop 例外は run abort」 を明文化。 NaN 発生は engine 合成 bug indicator で run continuity より修正優先 |
| [W3] zenigame との「semantically 同等」 は言い過ぎ | 学術引用節で「semantic 同等の主張は撤回、 ordering 能力が異なる」 と明記 |
| [W4] 学術引用が内部文書参照に寄り過ぎ、 NSGA-II 引用なし | Deb et al. (2002) NSGA-II + Deb (2000) constrained-domination を full citation で追加 |
| [S1] mission_margin を shortfall 系の名称に寄せる or 別 signed margin 導入 | option 2 採用: synthesis 命名通り `mission_margin` は保持、 別 `mission_signed_margin` を新設 |
| [S2] Phase 2 申し送りに NSGA-II non-dominated sorting 前の feasible filter 必須化 | 申し送り表 #2 として `constrained_domination.py` 新規を必須項目化 |
| [S3] CA #5 の比較対象を確定 (未達の少なさ vs 達成余裕の大きさ) | **達成余裕の大きさ** (signed margin) と確定。 archive 多様性確保のため feasible 個体間の超過余裕で tie-break する必要あり |

## 残論点 (Round 2 以降で議論可能)

1. **synthesis § 8.3 改訂タイミング**: T064 PR 完了後に synthesis 改訂 PR を出す。 影響範囲は § 8.3 (CA #5)、 § 15 (再校正計画)、 § 17 (用語)
2. **+inf sentinel と crowding distance の数値安定性**: NSGA-II 内部の crowding distance 計算で +inf を含む解の扱い (Deb et al. 2002 の standard implementation で先頭・末尾 boundary 解は infinite crowding distance になる仕様、 これと sentinel +inf の干渉)。 T065 詳細設計時に確認
3. **mission_signed_margin の denom 正規化**: 4 指標 signed slack の min を取るが、 indicators 間 scale 差を吸収する正規化が要るか? 現案では T061 で既に signed slack 化済 (1e-6 floor で正規化済) なので、 そのまま min 取って OK の想定
4. **constrained-domination の degenerate case**: 全個体 infeasible の世代発生時の挙動 (T065 詳細設計時に確認)
