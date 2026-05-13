# docs: progress_criteria 明文化 (Z-1 10k / Z-2 20k / Z-3 30k / Z-4 50k、 live=50k 不変)

## 背景

30 ラウンド Codex 議論で確立した「漸進的目標水準」 を docs/alpha_factory/ に明文化されていない。 archive 実測で Stage C 評価集団 (n=1,284) の total_pnl max=25,580 円、 mission target=50,000 とのギャップが大きい。 段階的な mid-target を明示することで進捗追跡の指標化が必要。

## 目的

漸進的 progress_criteria を docs に明文化:
- **Z-1**: 10k (= 最初の milestone、 archive p95 近辺)
- **Z-2**: 20k (= 持続性ありの 1 戦略)
- **Z-3**: 30k (= 複数 RUN で確認可能な水準)
- **Z-4**: 50k (= live_criteria 達成、 mission)

live_criteria.total_pnl_min=50000 は不変 (= 真の mission)、 progress_criteria は中間目標。

## 期待効果

- 各 RUN report で progress_criteria 達成段階を明示可能
- 撤退条件 (handoff § 撤退条件) の判定根拠が明確化
- 全体ロードマップの可視化

## スコープ

- `docs/alpha_factory/progress-criteria.md` 新規 (or `stage-gates.md` に section 追加)
- 既存 docs (`mission-score.md` 等) への cross-link
- 行動不変 (= docs only、 code touch なし)

## 非目的

- live_criteria 閾値変更
- progress_criteria を fitness / gate に反映 (= 別 PR で観測経路から検討)

## 参考

- `devnotes/20260513-1402-handoff-pr1-pr2-postdebate/handoff.md` § 12 段 TODO 順 6
- `tmp/codex-debate-round2/` (Z debate Round 4-5)
