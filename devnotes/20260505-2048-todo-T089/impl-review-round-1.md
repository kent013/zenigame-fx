**前提（C4）**
- 根拠は、提示された `detailed-design.md`（Round 3 APPROVED）、差分抜粋、テスト/ruff/mypy結果のみです。
- コマンド実行・実ファイル全文確認は未実施です（ご指定制約に従遵守）。
- 反証優先（C9）で「同値性崩れ」「partition 契約崩れ」「perf gate 妥当性」を重点確認しました。

[Session Block](/Users/ishitoya/repository/zenigame-fx/src/backtest/session_block.py) 判定: **APPROVED**
- [Critical] なし
- [Warning] なし
- [Suggestion] `BLOCK_BUCKET_RANGES_UTC` は型上 `Final` でも実行時は mutable なので、将来の誤更新リスクをさらに下げるなら `MappingProxyType` 等で実行時不変化を検討するとより堅牢です。
- Fact: `_build_hour_to_bucket` 追加、`_HOUR_TO_BUCKET` 構築、`compute_bucket_for_bar` の O(1) 参照化、docstring更新、`cast` import 追加は設計書記載と一致。
- Fact: range validity / overlap / not covered を import 時に fail-fast する実装になっている。
- Fact: `compute_bucket_for_bar` は tz 検証後に `bar_time.hour`（0..23）で tuple index 参照するため、旧 per-call dict iter と同じ割当結果を返す構造。
- Interpretation: 設計一致性・正確性・import副作用安全性（外部I/Oなし、循環参照誘発要素なし）は満たしています。

[Test Session Block](/Users/ishitoya/repository/zenigame-fx/tests/backtest/test_session_block.py) 判定: **APPROVED**
- [Critical] なし
- [Warning] なし
- [Suggestion] perf test は毎回 `lookup→oracle` 固定順なので、将来の環境差による偏りをさらに減らすなら計測順の交互化を検討余地あり（現状でも median/25 samples で十分実務的）。
- Fact: 設計書列挙の 5 件（parity / validation_unchanged / detects_invalid_partition / returns_tuple_of_24 / perf gate）が全て存在。
- Fact: partition invalid は range invalid・重複・未covering・mixed を検出するケースがある。
- Fact: perf は絶対時間ではなく ratio 比較、validation overhead を双方に含める oracle、median + sample_count で flake 緩和の方針を満たす。
- Interpretation: テスト網羅性と perf gate 設計は要求に整合しています。

**禁止事項チェック（観点8）**
- 評価期間延長、見た目数値操作、GAハック、閾値緩和、過度複雑化、取引回数削減誘導、オーバーナイト前提化に該当する変更は差分上確認されません。

**全体判定: APPROVED**