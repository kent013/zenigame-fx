**全体判定: CHANGES_REQUESTED**

Critical はありません。Round 2 の spread 係数欠落は解消されています。  
ただし overflow preflight に新しい矛盾が残っているため、APPROVED にはまだできません。

**Findings**
[Warning] 保守 `equity_bound_scaled` を margin 左辺に使うと、提示された AF smoke 条件でも preflight が落ちます。  
Fact: §5 では `equity_bound_scaled ≈ 2.4e17 < 9.22e18` と評価しています。  
Fact: preflight step 4 は `equity_bound_scaled*100*leverage*maint_den < 2^63−1` を検査すると書いています。  
Fact: default では `2.4e17 * 100 * 3 = 7.2e19` で、`9.22e18` を超えます。  
Interpretation: 設計どおりだと、典型 smoke 条件でも kernel が Decimal fallback になり、wall-time 削減の production scope を自分で潰します。  
修正案: preflight は「静的に安全なら kernel 確定」程度に使い、保守上界超過だけで即 fallback しない設計にしてください。kernel 内では乗算前に `abs(equity_post) <= INT64_MAX // (100*leverage*maint_den)` を sentinel 判定し、超過時は overflow status を返して caller が Decimal engine で再実行するのが妥当です。

[Suggestion] §5 の冒頭側に古い `equity_scaled worst ~ initial` 記述が残っています。  
Fact: 後段では利益累積で initial bounded ではないと修正済みです。  
Interpretation: 同じ節内で上界の前提が二重化しており、実装者が古い 3e16 評価を採用するリスクがあります。  
修正案: margin overflow 評価は `actual runtime equity sentinel` と `Decimal rerun fallback` に一本化し、initial_cash bounded の説明は削除してください。

**確認事項への回答**
1. margin finite-granularity 証明は default 条件では承認可能です。二段丸めへの言及も十分です。  
2. preflight 条件は `leverage==3` 追加で契約は明確になりました。ただし overflow 判定だけは、保守上界を hard fallback 条件にすると適用範囲が狭すぎます。  
3. 残る Critical はありません。残る Warning は overflow preflight の 1 件です。

**施策別判定**
`施策1 columnar`: APPROVE  
`施策2 njit kernel`: REQUEST_CHANGES  
`施策3 run_backtest 差し替え`: APPROVE  
`施策4 golden parity`: APPROVE  
`施策5 fallback/preflight`: REQUEST_CHANGES

上記 Warning を反映すれば、設計として APPROVED 判定でよいです。