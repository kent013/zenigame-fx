# Synthesis 改訂 PR: mission_signed_margin SSOT 昇格 + mission_margin BACKWARD COMPAT 化

**作成日時**: 2026-04-30 10:45 JST
**対象**: `devnotes/20260428-2300-cascade-port-debate/synthesis.md`
**改訂範囲**: § 6.4 / § 6.5 / § 8.3 / § 15 / § 17 / § 21 (計 6 章、 docs-only、 実装影響なし)
**起源**: T062 (mission-inf-gap engine) 詳細設計で発見、 T063 / T064 完了で改訂条件成立
**位置付け**: M3 (T065 NSGA-II + 主選抜) 着手前に確定すべき synthesis SSOT 修正

---

## 1. 改訂理由 (Why)

### 1.1 発見した矛盾 (T062 詳細設計時)

synthesis § 8.3 archive eviction CA 順序の項 #5:

> 5. mission_margin (= -mission_inf_gap、 達成超過余裕)

の **数式と命名が乖離している**。

- `mission_inf_gap = max(max(0, -slack_sharpe), max(0, -slack_pnl), max(0, -slack_dd), max(0, -slack_tc))` (§ 6.4)
- 値域: `mission_inf_gap >= 0`
- したがって `-mission_inf_gap <= 0` (常に非正)

この値で「達成超過余裕 (= 全 4 指標を live_criteria より上回ったマージン)」 を意味させようとしているが、 値域 <= 0 では「達成超過」 を表現できない。 mission 達成個体 (gap=0) と未達個体 (gap>0) を区別するシグナルとしては機能するが、 達成超過の度合いは表現できない (常に 0 で頭打ち)。

### 1.2 archive CA eviction での求められる semantic

archive CA = Convergence Archive は mission 達成寄り個体を保持する。 lex 順序の #1-4 (mission_pass / progress_pass / not_score_bypass / C_pass_depth) は pass/fail 系列の指標。 #5 では達成済個体の中での「マージン」 順序付けが本来の役割。

要件:
- 達成個体 (全 slack >= 0) では「最低マージン (4 指標で最も厳しい指標の余裕)」 が大きい順に上位
- 未達個体 (どれかの slack < 0) では「最大不足分」 が小さい順 (= mission_inf_gap 小さい順) に上位
- 達成個体と未達個体を **同一スカラーで一貫順序付け**

これを満たすのが **signed inf-norm slack**:

```
mission_signed_margin = min(slack_sharpe, slack_pnl, slack_dd, slack_tc)
```

- 達成個体: `>= 0` で大きいほど良い (4 指標の最低マージン)
- 未達個体: `< 0` で大きいほど良い (= 0 に近いほど良い、 不足分が小さい)
- 単一スカラーで完全順序

### 1.3 T062 詳細設計内での先行決定

T062 詳細設計 (`devnotes/20260430-0030-todo-T062-mission-inf-gap-engine/detailed-design.md`) で既に:

- `mission_signed_margin` を MissionGapResult の field として実装
- archive CA #5 用途は「synthesis § 8.3 改訂候補」 として明示し、 T062 PR では T065/T067 で消費する旨を記載

ここで synthesis 側を改訂し、 T062 の先行決定を SSOT として昇格させる。

---

## 2. 改訂方針 (What)

### 2.1 用途分離原則

| Field | 用途 | 値域 | 役割 |
|---|---|---|---|
| `mission_inf_gap` | Pareto f3 minimize、 Deb 2000 constraint_violation 計算 | `>= 0` | search (進化圧)、 minimize 方向で良 |
| `mission_signed_margin` | archive CA #5 ordering | `(-inf, +inf)`、 通常 [-1.5, +0.5] | archive 内達成度マージン、 大きいほど良 |
| `mission_margin` (旧) | **BACKWARD COMPAT のみ**、 用途消滅 | `(-inf, 0]` | Round 21 以前の synthesis での命名、 廃止 |

### 2.2 backward compat 方針

- `mission_margin` という名前を消去せず、 「BACKWARD COMPAT、 mission_signed_margin に統合」 と明記
- 新規参照は `mission_signed_margin` 一本化
- T062 既存実装は `mission_signed_margin` field をそのまま、 alias / 旧名残しの shim は不要

### 2.3 改訂しない箇所

- § 6.4 の `mission_inf_gap` 数式は不変 (Pareto f3 用途は維持)
- § 6.5 Pareto 3 軸 f3 = `mission_inf_gap` は不変
- § 7 NSGA-II / § 8.4 warmstart / § 16 Risk Top 5 等で `mission_inf_gap` を引用している箇所は不変
- 実装層 (T062 の MissionGapResult, T064 の cf_result.canonical_five) も touch 不要

---

## 3. 改訂内容詳細 (5 章)

### 3.1 § 6.4 集約

**Before**:
```
mission_inf_gap = max(max(0, -slack_sharpe), max(0, -slack_pnl), max(0, -slack_dd), max(0, -slack_tc))
```

**After (補足を 1 段落追加)**:
```
mission_inf_gap = max(max(0, -slack_sharpe), max(0, -slack_pnl), max(0, -slack_dd), max(0, -slack_tc))   # Pareto f3 minimize 用、 値域 >= 0

mission_signed_margin = min(slack_sharpe, slack_pnl, slack_dd, slack_tc)                                  # archive CA #5 ordering 用、 値域 (-inf, +inf)
```

加えて用途分離コメントを 2 行追記。

### 3.2 § 6.5 Pareto 3 軸 (search 専用)

**変更**: f3 の補足に「`mission_inf_gap` は Pareto search 用途、 archive CA #5 ordering は別 field `mission_signed_margin` を使用 (§ 8.3)」 と 1 行追記。

### 3.3 § 8.3 Eviction CA 順序

**Before**:
```
5. mission_margin (= -mission_inf_gap、 達成超過余裕)
```

**After**:
```
5. mission_signed_margin (= min(slack_sharpe, slack_pnl, slack_dd, slack_tc)、 4 指標の signed slack inf-norm)
```

CA 順序内の他項目 (#1-4, #6-8) は不変。

### 3.4 § 15 INCONCLUSIVE と再校正計画

**追記** (テーブル末尾に 1 行):
```
| `mission_signed_margin` denom 正規化 | 4 slack を未正規化で min | smoke 後に live_criteria scale 比較で再校正検討 |
```

### 3.5 § 17 用語・判定辞書

**Before** (mission_inf_gap の 1 entry のみ):
```
| mission_inf_gap | live_criteria 4 指標の inf-norm shortfall。 Pareto 3 軸 f3 で使用、 win_rate は含まない |
```

**After** (3 entry に整理):
```
| mission_inf_gap | live_criteria 4 指標の inf-norm shortfall (= max(0, -slack_*) の最大)。 Pareto 3 軸 f3 minimize 用、 値域 >= 0、 win_rate は含まない |
| mission_signed_margin | live_criteria 4 指標の signed slack inf-norm (= min(slack_*))。 archive CA #5 ordering 用、 値域 (-inf, +inf)、 達成個体の最低マージン + 未達個体の不足度を単一スカラーで一貫順序付け |
| mission_margin | **BACKWARD COMPAT** (Round 11-20 議論時の旧称、 = -mission_inf_gap 定義は数式と用途乖離あり)。 新規参照は `mission_signed_margin` を使用 |
```

### 3.6 § 21 議論履歴サマリー

**追記** (テーブル末尾に Round 21 行):
```
| 21 | (T064 完了後) synthesis 改訂 | T062 詳細設計で発見した `mission_margin` 命名矛盾を解消、 `mission_signed_margin` を新設 (実用 SSOT、 archive CA #5)、 `mission_margin` は BACKWARD COMPAT 整理。 § 8.3 / § 17 / § 6.4 / § 6.5 / § 15 改訂、 実装影響なし (T062 で先行実装済) |
```

---

## 4. 改訂しないことの確認 (No-touch リスト)

| 章 | 内容 | 理由 |
|---|---|---|
| § 1 Mission | live_criteria 4 指標 | 不変 |
| § 6.6 invariant fail-fast | session_close_drop / negative_equity_drop_open | 不変 |
| § 6.7 補助 metric | spread_consumption_ratio / cross-pair shadow score | 不変 |
| § 7 NSGA-II / CPPS | objectives = (max net_pnl, min max_dd, min mission_inf_gap) | 不変、 Pareto f3 用途 |
| § 8.4 warmstart / § 8.5 emergency / § 8.6 calibrate-gate | mission_pass / progress_pass / score_bypass の 3 層流入 | 不変 |
| § 9-11, § 12 big-bang 移行 | 全 unchanged |
| § 13-14 zenigame 参照 | 不変、 zenigame 側は別 codebase |
| § 16 Risk Top 5 | A/B 乖離 / epoch 汚染 / warmstart / archive bypass / DA 多様性 | 不変 |
| § 18 TODO 一覧 (T901-T918) | 不変 (zenigame 側番号、 fx 側 T058-T075 は別管理) |
| § 19 fx → zenigame 逆輸入候補 | 不変 |
| § 20 Next Action Top 3 | 不変 |

---

## 5. 改訂後の整合性検証

### 5.1 T062 詳細設計との整合

T062 詳細設計内 (`devnotes/20260430-0030-todo-T062-mission-inf-gap-engine/detailed-design.md`) の「synthesis § 8.3 改訂候補」 言及を「**改訂済 (synthesis Round 21)**」 に更新。 T062 の MissionGapResult.mission_signed_margin field 定義は不変。

### 5.2 T064 詳細設計との整合

T064 詳細設計内 (`devnotes/20260430-0230-todo-T064-stage-bc-evaluator/detailed-design.md`) の「synthesis § 8.3 改訂は T064 PR 完了後」 言及を「**改訂済**」 に更新。 T064 実装本体は touch 不要。

### 5.3 T065 (NSGA-II) 着手時に依拠する確定値

T065 概念設計で archive eviction lex 順序を引用する場合、 改訂済 synthesis § 8.3 (CA #5 = mission_signed_margin) を SSOT として参照する。 これにより T065 → T066 → T067 の archive 系設計が一貫する。

### 5.4 コードベースとの整合 (現状 0 件 touch)

設計フェーズのみで src/ 未着手のため、 改訂による code change は 0。 T065 PR 統合 (Phase 2) で T062 の MissionGapResult.mission_signed_margin を archive admission/eviction 経路で消費する際、 synthesis § 8.3 の確定値に従う。

---

## 6. PR 構成

```
- devnotes/20260430-1045-synthesis-revise-mission-signed-margin/
  - rationale.md (本文書)
  - diff-summary.md (改訂前後 diff の human-readable 整理、 必要に応じて作成)
- devnotes/20260428-2300-cascade-port-debate/
  - synthesis.md (5 章改訂、 + Round 21 記述追加)
- devnotes/20260430-0030-todo-T062-mission-inf-gap-engine/
  - detailed-design.md (synthesis 改訂済 reference 1 箇所更新)
- devnotes/20260430-0230-todo-T064-stage-bc-evaluator/
  - detailed-design.md (synthesis 改訂済 reference 1 箇所更新)
```

---

## 7. 完了判定

- [x] synthesis.md § 6.4 / § 6.5 / § 8.3 / § 15 / § 17 / § 21 改訂
- [x] T062 detailed-design.md の「改訂候補」 → 「改訂済」 更新
- [x] T064 detailed-design.md の「改訂候補」 → 「改訂済」 更新
- [x] rationale.md 作成 (本文書)

実装影響: 0、 docs-only PR。 T065 概念設計の前提が確定する。
