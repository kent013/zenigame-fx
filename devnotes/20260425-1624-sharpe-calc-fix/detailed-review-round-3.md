**指摘（重大度順）**

1. **Warning** `_get_sharpe_version` / accessor の `row.get(...) or "v1_bar_annualized"` は、`None` だけでなく `""` も v1 扱いになります。  
   意図が「`None` のみ補完」なら、`or` ではなく `is None` 判定にしてください（データ汚染の隠蔽を防げます）。

2. **Warning** `calibrate_gate` の `valid_sharpes.append(float(v))` は `NaN/Inf` を通す可能性があります。  
   `math.isfinite(...)` で弾くと、監視値の異常混入耐性が上がります。

**判定**

- Round 2 の4指摘に対する主修正（None補完、ゼロ除算防止、`invalid_count` の関数内完結、unknown version 可視化）は方向性として妥当です。  
- **Critical は現時点で見当たりません。**

**確認前提**

- 実ファイル差分ベースの再実行テストは未確認です（提示スニペットベースのレビュー）。