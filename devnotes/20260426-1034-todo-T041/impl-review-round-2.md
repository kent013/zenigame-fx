- [Suggestion] `tests/alpha_factory/test_config.py:201` の検証は「0 より大きい」ことのみを見ています。設計が `max_spread_bps=10` を合意しているので、`Decimal("10")` との一致まで固定しておくと、将来的な誤差しきい値変更を早期に検知しやすくなります。

確認メモ: `max_spread_bps=10` は Stage C を設計通り動作させるための必須値であり、live_criteria の緩和には当たりません。`_build_backtest` は既存の Decimal 変換がそのまま効いており整合しています。新規テストは YAML→Config 伝搬を確実に守る形になっており、T042/T043 とは疎結合で単独完結していると判断しました。

全体判定: APPROVED