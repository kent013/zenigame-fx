全体判定: **APPROVED**

**前提**
- Fact: Round 2 差分では `for equity_scaled_raw in equity_curve.equity_scaled:` の直後に `equity_scaled = int(equity_scaled_raw)` が追加されています。
- Fact: 以降の `peak_scaled` / `dd_scaled` / `max_dd_scaled` は Python `int` 同士の比較・減算になります。
- Interpretation: Round 1 の `np.int64` silent wrap リスクは解消されています。

[修正確認] `int()` 変換による wrap 回避は正しいです。  
Fact: `peak_scaled - equity_scaled` が Python 任意精度整数で実行されるため、`2^62 - (-2^62) = 2^63` のように int64 上限を超える drawdown でも wrap しません。  
Interpretation: `decode_equity(max_dd_scaled)` は `int` を受けて Decimal 化するだけなので、個別 equity 点が int64 内に収まっている限り、drawdown 絶対額が int64 を超えても計算契約上は問題ありません。

[修正確認] 回帰テストは今回のリスクに対して十分です。  
Fact: `peak=+2^62 / trough=-2^62` は、各 equity 点は int64 表現可能だが差分 `dd=2^63` が int64 範囲を超えるケースです。  
Interpretation: これは Round 1 指摘の failure mode を直接踏むテストなので、wrap 回避の固定として適切です。

[Suggestion] `validate_equity_scale_contract` の strict モード見送りは許容です。  
Fact: lossless 保証は `encode_equity` の per-bar guard で維持されています。  
Interpretation: warning 化の残リスクは運用上の早期検知粒度であり、今回の実装正確性をブロックするものではありません。

[確認] fixture コメント修正は妥当です。  
Fact: 「24 の約数では旧挙動と一致、それ以外でも strictly increasing」という説明に修正されています。  
Interpretation: Round 1 のコメント不正確性は解消されています。

残リスクは performance 実測のみです。実装正確性、bit-exact 契約、決定論契約の観点では APPROVED でよいです。