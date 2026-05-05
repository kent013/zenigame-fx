# Round 1 Detailed Design Review

## 施策 1 (lookup table 化) 判定
REQUEST_CHANGES

[Critical]
- `microbenchmark` を通常 pytest に入れて `1M calls で per-call < 0.20 μs` を固定閾値 assert する案は、環境差で flaky になりやすく CI 安定性を落とします。現リポジトリにも perf 専用レーンは未整備です。  
  Fact: [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-2022-session_block_lookup_table/detailed-design.md#L163), [pyproject.toml](/Users/ishitoya/repository/zenigame-fx/pyproject.toml#L57)  
  Interpretation: C8 の「反証可能性」は必要ですが、unit test で絶対性能値を gate するのは不適。  
  反証可能仮説: 「同一プロセス内で lookup 実装の median per-call が現行 oracle 比で少なくとも 15% 以上速い」。  
  最小変更: benchmark は `tests` 本線から分離し、手動/専用ジョブ実行にする（unit は parity/validation のみ）。

[Warning]
- builder 検証の「4項目」と書きつつ、詳細擬似コードの実質検証は 3 本（range/overlap/covering）です。4番目（sum=24）を仕様文言だけでも明示しておくと C4 が崩れません。  
  Fact: [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-2022-session_block_lookup_table/detailed-design.md#L77), [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-2022-session_block_lookup_table/conceptual-design.md#L72)
- `per-call RuntimeError → import時 RuntimeError` への契約移動は妥当ですが、`compute_bucket_for_bar` で RuntimeError を期待する旧説明との不整合が残らないよう、docstring/テスト前提を完全同期させる必要があります。  
  Fact: [session_block.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/session_block.py#L304), [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-2022-session_block_lookup_table/detailed-design.md#L173)

[Suggestion]
- `cast(SessionBlockBucket, b)` は現行構造だと型チェッカ補助として有効です。不要化したいなら `None` 除去後に `assert` で絞る実装に変えると明示的です。

## テスト計画 評価
- parity/validation/partition violation の軸は適切で、24h 同値性の担保として十分です。  
  参照: [test_session_block.py](/Users/ishitoya/repository/zenigame-fx/tests/backtest/test_session_block.py#L74), [test_session_block.py](/Users/ishitoya/repository/zenigame-fx/tests/backtest/test_session_block.py#L446)
- `partition violation 4種` は「import時」を直接検証しようとすると実装が重くなるため、`_build_hour_to_bucket()` 単体検証中心で十分です（import時 fail-fast は統合1本で補完）。
- profile 再計測 DoD（tottime ≤ 0.40s）は妥当。  
  基準値確認: [profile_20260505_201359.txt](/Users/ishitoya/repository/zenigame-fx/.cache/alpha_factory/runs/profile/profile_20260505_201359.txt#L88)

## 全体判定
CHANGES_REQUESTED

## 主要指摘 / 推奨事項
1. Q1（validation 4項目）: 十分です。実質は 1-3 で成立し、4 は checksum 的補強です。仕様文言の明示だけ追加推奨。  
2. Q2（cast 必要性）: 現書き方では推奨です。`any(...)` では型が十分に narrowed されません。  
3. Q3（他関数の index 化）: 追加不要です。`compute_bucket_for_trade` は既に委譲し、`aggregate_session_blocks` 連鎖も自動で恩恵を受けます。  
   参照: [session_block.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/session_block.py#L332), [session_block.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/session_block.py#L337)
4. Q4（microbenchmark 配置）: 本線テストではなく分離推奨です。unit は機能同値、perf は別レーン。  
5. Q5（残 blocker）: blocker は 1 点のみ（microbenchmark の gate 方式）。それ以外は実装に進めるレベルです。  

補足（C1/C4確認）: 概念設計 Round2 APPROVED と profile 行番号、SSOT、既存テスト参照は確認済み。  
参照: [conceptual-review-round-2.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-2022-session_block_lookup_table/conceptual-review-round-2.md#L2), [session_block.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/session_block.py#L75), [test_session_block.py](/Users/ishitoya/repository/zenigame-fx/tests/backtest/test_session_block.py#L446), [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-2022-session_block_lookup_table/detailed-design.md#L104)