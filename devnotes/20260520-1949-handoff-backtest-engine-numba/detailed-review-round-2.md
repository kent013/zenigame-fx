**全体判定: CHANGES_REQUESTED**

Critical はありません。Round 1 の主要欠陥は概ね潰れています。  
ただし、実装に入る前に直すべき Warning が 2 件残っています。

**Findings**
[Warning] spread filter の pseudocode が §2-2 と矛盾しています。  
Fact: §2-2 は `(ask−bid)*20000*max_den > max_num*(ask+bid)` ですが、施策2 pseudocode は `last_spread_num*max_spread_den > max_spread_num*last_spread_den` になっています。  
Interpretation: pseudocode どおり実装すると spread bps の `20000` 係数が落ち、open pending drop の判定が大幅に変わります。  
修正案: pseudocode を明示的に次へ統一してください。

```python
if last_spread_num * 20000 * max_spread_den > max_spread_num * last_spread_den:
    pending_kind = 0
```

[Warning] overflow 上界の「equity は initial_cash オーダーに bounded」は成り立ちません。  
Fact: margin/equity gate は損失側の破産経路を閉じますが、利益累積 cash/equity の上限は保証しません。  
Interpretation: 実データでは問題になりにくくても、int64 安全性の設計根拠としては不足です。  
修正案: preflight の equity 上界を `initial_cash_scaled + n_bars * units * (max_price_scaled - min_price_scaled) * SCALE_RATIO` のような保守上界で計算し、その上で margin 左辺 `equity_bound*100*leverage*maint_den` を検査してください。上界が過大で落ちる場合は Decimal fallback でよいです。

[Suggestion] margin finite-granularity 証明は default 条件では概ね妥当です。  
Fact: `maint=100` では Decimal 判定は実質 `equity < round28(notional/leverage)` で、kernel は `equity < notional/leverage` の exact rational 比較です。  
Interpretation: equity grid と Decimal 丸め幅の差が十分大きい限り、比較反転は起きません。ただし「equity は 1e-5 整数倍」より、`units=10000` default では実際にはより粗い 0.1 grid です。証明は壊れませんが、記述は精密化した方がよいです。  
修正案: `scaled integer p` ベースで `notional = units*p/PRICE_SCALE` と置き、`leverage=3` の剰余ごとに「有限化する場合は exact、非終端の場合は equity grid との最小距離が Decimal 丸め幅より大きい」と書くと反証余地が減ります。

[Suggestion] preflight 条件に `leverage` 前提を明示してください。  
Fact: §2-2 の証明本文は `leverage=3 default` に依存した説明です。  
Interpretation: 実装が任意 integer leverage を受けるなら証明を一般化する必要があります。production scope 固定なら `leverage == 3` を preflight に入れる方が設計契約として明瞭です。

**施策別判定**
`施策1 columnar`: APPROVE  
`施策2 njit kernel`: REQUEST_CHANGES  
`施策3 run_backtest 差し替え`: APPROVE  
`施策4 golden parity`: APPROVE  
`施策5 fallback`: APPROVE

**確認事項への回答**
1. margin finite-granularity 証明は、`maint=100` / quantize 無し / default leverage 前提では十分条件として概ね妥当です。ただし第二段の `margin_level` 除算丸めも含めた grid gap の説明に補強余地があります。  
2. preflight は方向性として妥当です。`leverage` 前提と利益累積を含む overflow 上界を追加すれば過不足はかなり減ります。  
3. 残る Critical はありません。上記 2 Warning を反映すれば APPROVED でよいです。