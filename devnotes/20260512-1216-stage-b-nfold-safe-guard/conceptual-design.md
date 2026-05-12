# 概念設計: Stage B `n_fold_effective` safe floor guard

作成: 2026-05-12 12:16 JST
親議論: [`devnotes/20260512-1000-cross-repo-debate/round-1-verdict.md`](../20260512-1000-cross-repo-debate/round-1-verdict.md) (P1 Quick win)

## 背景・課題

Run 60 best `g34_i33` は Stage A `fp=0.5418` (Run 57-74 中の最高近傍) を記録したが、 cycle 9 best-genome-comparison.md にて `n_fold_effective=4` (config `wf_min_safe_folds=5` 未満) と判明。 Walk-Forward 評価が統計的安全水域を下回ったまま Stage A pass → archive admit → selection で best として浮上、 後段の sharpe 0.58 mission 接近の **artifact** であった可能性が極めて高い。

現在のコードベース ([stage_gate.py:1197](../../src/alpha_factory/stage_gate.py#L1197), [stage_gate.py:1206-1230](../../src/alpha_factory/stage_gate.py#L1206-L1230)) において:
- `n_fold == 0` → `no_folds`
- `n_fold == 1` → `insufficient_folds`
- `n_fold >= 2` → median_oos / positive_ratio check のみ
- **`n_fold_effective < wf_min_safe_folds` (=5) の hard guard 無し**

`wf_min_safe_folds=5` は [stage_gate.py:414-417](../../src/alpha_factory/stage_gate.py#L414-L417) で「起動時 fail-closed 用 statistical safety floor」と明示されているが、 個体評価層 (`evaluate_stage_b`) では参照されていない。 起動時 preflight ([swim_lane.py:502](../../src/alpha_factory/swim_lane.py#L502)) で `lane_max_folds < wf_min_folds` (=2 default) を見るのみで、 個別個体の `n_fold_effective` が unavailable 増で 5 を割っても通過する余地が残る。

## 目的 / 仮説

**仮説**: Stage B の `evaluate_stage_b()` 末尾の判定に `n_fold_effective < wf_min_safe_folds` の hard guard を一行追加することで、 Run 60 型 artifact (fold 不足個体の高 sharpe 偶発浮上) を排除でき、 GA selection の探索リソースが「統計的に安全に Stage B 評価された個体」のみに集中する。

**北極星**: 使命 (live_criteria 全達成個体 1 つ発見) への寄与は **中** (artifact 排除による探索効率改善であり、 直接 sharpe を 0.58→1.0 に押し上げる施策ではない)。 ただし「fold 4 個体を best と誤認識」状態は判定の信頼性そのものを損ね、 改善ループ全体を misguide するため、 **必須の地ならし**。

## 設計方針

### 採用案: Stage B 内 hard guard 1 行追加

[stage_gate.py:1197](../../src/alpha_factory/stage_gate.py#L1197) で `n_fold_effective` を計算した直後、 reason 判定ブロック (L1206-1230) に以下を追加:

```python
# 統計的安全水域に満たない fold 数で Stage B 通過させない
if n_fold_effective < stage_config.wf_min_safe_folds:
    reasons.append("n_fold_below_safe_floor")
```

設置位置は `n_fold == 1` 分岐 (L1208) の後、 `else` 分岐 (L1216) と並列。 median_oos / positive_ratio 評価との重複は許容 (どの reason がついても passed=False となる構造)。

### 不採用案
- **Stage A gate に追加** (Codex 当初案): Stage A は単一 60 日窓 backtest で fold 概念無し → 適用不可。
- **swim_lane preflight 強化** (`wf_min_folds_required` を 5 に引き上げ): lane 全体が落ちて Stage B skip となり、 個体粒度の判定情報を失う。 個体評価層で reason 記録する方が観測性が高い。
- **artifact を別 reason 名で記録するのみ (gate には反映せず)**: 観測性のみ上げて selection 圧は変えない案。 archive admit が継続するため selection で best として浮上する問題は解決しない。 棄却。

## archive スキーマ伝搬

`stage_b_result.reasons` に `n_fold_below_safe_floor` が追加されると、 既存の reason ベースの記録 (`archive.parquet` の `stage_b_failure_reason`) に自動伝搬する想定。 別途 boolean 列を増やす必要は無い。 **禁止事項 8 (archive スキーマ伝搬漏れ)** には抵触しない見込み (詳細設計で要確認)。

## 期待効果

- Run 60 / 類似 artifact 個体の Stage B fail → archive `stage_b_pass=False` 記録 → GA selection で best 競合から除外。
- 18 RUN history を本パッチで再評価した場合、 sharpe top の見え方が改善されることが期待される (要 archive 後段確認、 本 TODO 範囲外)。
- 改善ループの判定信頼性向上。 「fold 不足の偶発高 sharpe」を best と誤評価しなくなる。

## 禁止事項チェック

| 禁止事項 | 抵触有無 | 理由 |
|---------|---------|------|
| 1. 期間延長 | なし | Stage 期間に手を入れない |
| 2. 見栄え改善 | なし | むしろ artifact を排除し見栄え悪化方向 |
| 3. GA ハック | なし | gate に正当な統計安全水域を反映するのみ |
| 4. live_criteria 緩和 | なし | live_criteria に手を入れない |
| 5. 過剰複雑化 | なし | 1 行追加 |
| 6. 取引回数削減 | なし | trade_count に影響なし |
| 7. オーバーナイト | なし | 関係なし |
| 8. archive スキーマ伝搬漏れ | 詳細設計で確認 | reason 配列は既存伝搬経路想定 |

## 検証計画 (詳細設計の test 部で具体化)

- Unit: `evaluate_stage_b(n_fold_effective=4, wf_min_safe_folds=5)` → `passed=False` かつ `"n_fold_below_safe_floor" in reasons`
- Unit: `n_fold_effective=5, wf_min_safe_folds=5` → 既存 median/positive 判定の通常経路 (guard 未発動)
- Unit: `n_fold == 1` (既存 insufficient_folds) と本 guard の併発時、 reasons に両方記録されること (passed=False は不変)
- 回帰: 既存 stage_gate test 群 (n_fold_effective ≥ 5 の path) が全通過

## 次ステップ

- 詳細設計を [`detailed-design.md`](./detailed-design.md) に書く (差分 patch + test specification)
- Codex レビュー (zenigame-fx-codex-review) を 1 round
- TODO に登録 (theme=`stage-gate`, priority=`High`, mode=`incremental`)
