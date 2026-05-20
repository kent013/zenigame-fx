**全体判定: APPROVED**

残る Critical / Warning はありません。Round 3 の overflow preflight 自滅は、runtime sentinel + Decimal 再実行に分離されたことで解消されています。施策2 / 施策5 の REQUEST_CHANGES も解消です。

**施策別判定**
`施策1 columnar`: APPROVE  
`施策2 njit kernel`: APPROVE  
`施策3 run_backtest 差し替え`: APPROVE  
`施策4 golden parity`: APPROVE  
`施策5 fallback/preflight`: APPROVE

**最終確認**
Fact: overflow は preflight hard gate ではなく、乗算直前 sentinel で検出し、該当 backtest のみ Decimal engine で再実行する設計になりました。  
Interpretation: performance-only contract と observable behavior contract の両方を保てます。

Fact: margin / spread の整数比較、post-fill equity 再計算、per-index composite 呼び、holding_cost fallback、prepared/single-signal scope が設計契約として明文化されています。  
Interpretation: selection-invariant を壊しやすい主要経路は設計上カバー済みです。

実装時の承認条件は、設計書どおり `golden parity` を最終 arbiter にすることです。特に `trades`、`equity_scaled`、`signal intent`、GA smoke の pass/fail vector は bit-identical 必須です。