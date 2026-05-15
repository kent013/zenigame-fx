全体判定: **CHANGES_REQUESTED**

**前提 (C4)**
- Verified: 提示 diff 上で、約定・margin・手数料の計算ロジック自体は変更されていません。
- Verified: `EquityCurve` 導入後も gate-feeding 指標の Decimal 経路を維持する意図と shadow/tie-break/parity テストは提示されています。
- Unverified: 実測 RSS 改善量と archive 系の全 downstream 追従は、提示差分のみでは最終確証に至りません。

[Warning] `max_drawdown` 整数経路で `np.int64` 演算オーバーフロー余地  
- Fact: [metrics.py](/Users/ishitoya/repository/zenigame-fx/.claude/worktrees/t105-decimal-churn/src/backtest/metrics.py:169) のループで `equity_scaled` は `np.int64` 由来で、`dd_scaled = peak_scaled - equity_scaled` も `np.int64` で実行される可能性があります。  
- Interpretation: 極端値で subtraction が wrap すると `max_drawdown` と `max_drawdown_pct` が誤るため、selection 決定論に影響し得ます。  
- 修正案: ループ先頭で `eq_scaled = int(equity_scaled)` に変換し、`peak_scaled`/`dd_scaled` を Python `int` のみで計算してください。合わせて int64 境界近傍値の回帰テストを 1 本追加してください。

[Suggestion] `validate_equity_scale_contract` warning 化の運用安全性  
- Fact: [equity_curve.py](/Users/ishitoya/repository/zenigame-fx/.claude/worktrees/t105-decimal-churn/src/backtest/equity_curve.py:128) は holding cost 有効時を warning のみとし、実 fail-closed は per-bar `encode_equity` に委譲しています。  
- Interpretation: lossless 保証自体は維持されていますが、設定起因の不整合検知が遅延し、GA 実行中に同種失敗が反復する運用リスクは残ります。  
- 修正案: 互換性維持のため default は warning のままにしつつ、`strict` モードや preflight probe を追加して fail-fast を選べるようにしてください。

[Suggestion] fixture 修正コメントの厳密性  
- Fact: [test_stage_gate.py](/Users/ishitoya/repository/zenigame-fx/.claude/worktrees/t105-decimal-churn/tests/alpha_factory/test_stage_gate.py:95) の説明「`bars_per_day<=24` は挙動不変」は、24 の非約数ケースでは成立しません。  
- Interpretation: テストの意図理解で将来の誤読を誘発する可能性があります。  
- 修正案: コメントを「24 の約数では不変」に修正するか、条件分岐で旧挙動を厳密再現してください。

補足評価:
- lossless/bit-exact 方針は全体として妥当です。
- consumer 追従は主要経路で実施されており、禁止事項 8 の重大漏れは現時点で観測していません。
- 性能面は方向性正しいですが、実効は post-merge 計測待ちで **INCONCLUSIVE** です。