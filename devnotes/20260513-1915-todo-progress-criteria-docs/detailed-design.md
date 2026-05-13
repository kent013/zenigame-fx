# docs: progress_criteria 明文化 詳細設計

## 実装方針

### 新規 `docs/alpha_factory/progress-criteria.md`

セクション構成:
1. 背景・経緯 (= 30 ラウンド Codex 議論の closeout)
2. 4 段階 (Z-1 10k / Z-2 20k / Z-3 30k / Z-4 50k) の定義
3. 各段階の判定指標 (= archive 列、 Stage C 集計値)
4. 撤退条件との連動 (= 10 RUN で Z-2 達成なしなら警戒、 等)
5. live_criteria=50k との関係 (= mission 不変、 progress は中間)

### 既存 docs 更新

- `docs/alpha_factory/stage-gates.md`: Stage C 評価集団の statistics と progress_criteria への参照追加
- `docs/alpha_factory/mission-score.md`: progress_criteria との cross-link
- `docs/alpha_factory/README.md`: index に追加

## 受入基準

- [ ] `docs/alpha_factory/progress-criteria.md` 新規作成 (~150-200 行)
- [ ] 4 段階の数値定義と根拠 (= archive 実測 p95/p99) 明示
- [ ] 撤退条件との連動セクション
- [ ] cross-link 整備
- [ ] code touch なし、 yaml touch なし (= docs only)

## ロールバック条件

- code touch 検出
- 既存 docs の cross-link 切れ

## コミット計画

- 1 コミット: `docs(alpha_factory): progress_criteria 明文化 (Z-1 10k / Z-2 20k / Z-3 30k / Z-4 50k)`
