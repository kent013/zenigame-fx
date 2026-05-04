# 詳細設計: Run 29 施策 (cycle 2)

**作成日時**: 2026-05-04 14:42 JST
**前提**: improvement-plan.md (consensus Round 1 APPROVED)
**北極星**: live_criteria 充足 FX イントラデイ戦略個体を 1 つ見つけ出す

## 使命・制約 (絶対遵守)

- イントラデイ前提 / ロング・ショート両方向 / スワップ・スプレッド net 反映
- 禁止事項 #1-#8 全遵守
- **特に C1 で禁止事項 #6 (取引回数削減で見栄え向上) を構造的に解消**

## 施策一覧

| # | 施策名 | 変更ファイル | target_metric |
|---|---|---|---|
| C1 | Stage A min_exposure_trade_count を live_criteria 同期 | `config/alpha_factory/default.yaml` 1 行 | Stage A 通過母集団の median trade_count >= 50 |

---

## C1: Stage A min_exposure_trade_count を 1 → 50 (live_criteria.trade_count_min と同期)

### target_metric / failure_mode / causal_path / falsification / success_criterion

- **target_metric**: Stage A 通過母集団 median trade_count >= 50 (= live_criteria 適格)
- **failure_mode**: Run-28 Stage A pass 個体 median trade_count=55 / fold 内 trade=7 < fold_trade_count_min=10 / 88% Stage B fail with `trade_count_below_min`
- **causal_path**: Stage A min_exposure=1 → low-trade individual 通過 → Stage B fold 内 trade 不足 → fail
- **falsification (= 事前登録、 改善ループの discipline)**:
  - (a) Stage A pass 数 ≈ 142 不変 → 経路独立性 bug (= entry_count_min と min_exposure_trade_count の経路分離)
  - (b) Stage A pass 急減 + fold 不足解消後も `median_oos_sharpe<min` 支配 → root cause = signal 品質、 H1 棄却
  - (c) total_trade_count>=50 でも fold 最小取引数改善せず → 時間集中が真因 (= 取引が特定 fold に偏在)
- **success_criterion**:
  1. Stage A pass median trade_count >= 50 (= must)
  2. `trade_count_below_min` 件数大幅減 (= 125 → < 10 想定)
  3. fail 理由分布が `trade_count_below_min` から `median_oos_sharpe<min` 主体へシフト

### 変更箇所

**ファイル**: [config/alpha_factory/default.yaml:94](config/alpha_factory/default.yaml#L94)

```yaml
# Before:
    min_exposure_trade_count: 1

# After:
    min_exposure_trade_count: 50  # cycle 2: 1 → 50 (live_criteria.trade_count_min=50 と SSOT 同期)。 詳細: devnotes/20260504-1432-fx-improve-c2/
```

### 波及変更

- AGENTS.md: 不要 (= 既存 invariant `1 <= min_exposure_trade_count < live_criteria.trade_count_min` が「<」 invariant のため修正必要)
- **`docs/alpha_factory/stage-gates.md`**: 既存記述あれば更新 (= live_criteria 同期の説明追加)
- **`src/alpha_factory/config.py`** の invariant: `min_exposure_trade_count < live_criteria.trade_count_min` → `<=` に変更必要

### config invariant 確認 (= 重要、 設計差し戻し回避)

`config/alpha_factory/default.yaml:93` のコメント:
> 不変条件: 1 <= min_exposure_trade_count < live_criteria.trade_count_min

= 現状 invariant は **strict less than** (`<`)。 50 → 50 の同値設定が許容されない可能性。 config loader (= `src/alpha_factory/config.py`) の validation 確認必要。

**修正案**:
- 案 A: invariant を `<=` に緩和 + 同期させる (= live_criteria 同期 = 同じ値を許容)
- 案 B: min_exposure_trade_count を 49 (= live_criteria.trade_count_min - 1) に設定し、 strict less than 維持
- **推奨**: 案 A (= live_criteria 同期 SSOT)、 invariant の緩和で「Stage A 通過 = live_criteria 適格」 の構造を作る

### Before / After

```yaml
# config/alpha_factory/default.yaml:91-94 (Before)
    # T034: trade_count<min_exposure_trade_count の個体は no_exposure reason +
    # NO_EXPOSURE_FITNESS sentinel で淘汰する (selection_score tie-break で
    # 「無取引優位」を構造的に解消)。default 1 = 「1 trade 未満 = 取引未成立」。
    # 不変条件: 1 <= min_exposure_trade_count < live_criteria.trade_count_min。
    min_exposure_trade_count: 1
```

```yaml
# config/alpha_factory/default.yaml:91-94 (After)
    # T034: trade_count<min_exposure_trade_count の個体は no_exposure reason +
    # NO_EXPOSURE_FITNESS sentinel で淘汰する (selection_score tie-break で
    # 「無取引優位」を構造的に解消)。
    # cycle 2 (2026-05-04): 1 → 50 (= live_criteria.trade_count_min と SSOT 同期)。
    # Stage A 通過 = live_criteria 適格 = mission 達成基準と整合。
    # 不変条件: 1 <= min_exposure_trade_count <= live_criteria.trade_count_min。
    min_exposure_trade_count: 50
```

### invariant 検証 (= src/alpha_factory/config.py)

config loader の validation を Read で確認、 strict less than (`<`) なら `<=` に緩和。

### テスト計画

1. **config invariant test**: `min_exposure_trade_count == live_criteria.trade_count_min` ケースが受容されるか
2. **stage_gate.evaluate_stage_a unit test**: trade_count=49 で no_exposure / 50 で通過判定 (= 境界テスト)
3. **既存テスト**: `tests/alpha_factory/test_stage_gate.py` で min_exposure_trade_count パラメータを使うテストの fixture 更新

### ルックアヘッドバイアス / パフォーマンス

- ルックアヘッドバイアス: 不変 (config 値変更のみ)
- パフォーマンス: 不変 (= 判定 1 行の比較)

### リスク

- **Risk 1**: Stage A pass 数が 142 → ?? に急減、 GA selection が elite で停滞 (= trade_count >=50 個体が少ない可能性)
  - 反証 (a) で観察、 もし pass 急減で stage B 評価母数が < 5 なら Run-30 で別仮説 (= primitive 表現力 / signal 品質) へ進む
- **Risk 2**: config invariant 違反で起動不能
  - 事前に config loader を Read して strict less than → less or equal に緩和
- **Risk 3**: 既存テストが invariant 違反で fail
  - test fixtures を新 invariant に合わせて更新

## Run 29 実行パラメータ

| パラメータ | 値 | R-28 からの変更 |
|---|---|---|
| population_size | 40 | 不変 |
| generations | 15 | 不変 |
| max_clause | 1 | 不変 |
| max_depth | 4 | 不変 |
| max_workers | 2 | 不変 |
| stage_a.threshold | -0.0172 | 不変 (= cycle 1 calibrate-gate 適用) |
| stage_a.alpha | 0.03 | 不変 |
| **stage_a.min_exposure_trade_count** | **50** | **1 → 50** ← 唯一の変更 |
| その他 default.yaml | 不変 | — |

## 保留事項 (= 実装フェーズで確認)

| # | 論点 | 検証 |
|---|---|---|
| H1 | config invariant `<` → `<=` の緩和が必要か | `src/alpha_factory/config.py` の Read で確認 |
| H2 | 既存テスト fixture の更新範囲 | `tests/alpha_factory/test_stage_gate.py` を grep で確認 |
| H3 | docs 更新範囲 | `docs/alpha_factory/stage-gates.md` の min_exposure 記述を grep で確認 |
