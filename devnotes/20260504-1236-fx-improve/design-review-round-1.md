**前提検証（C4）**
- Verified: 入力・出力仕様、Run-27 の観測値、C1 の目的、禁止事項・絶対制約。
- Verified: `active_clause unique=[1]` は `max_clause=1` 制約と整合。
- Unverified: `n_nodes std` の世代差（P3条件の数値本体）は未提示。
- Unverified: `alpha` が個体ごとに不変か（設計上は `default.yaml` 単一値想定）。

**反証先行（C9）**
- P2反証: `trade_sharpe_raw > 0` 個体が約1-2体規模のため、`K>=5` は成立しにくい。
- P3反証: `active_clause unique==1` は設定起因で説明でき、探索崩壊の証拠として独立性が弱い。
- P1反証失敗: `raw max=0.001134 < 0.005` は明確に成立。

**施策別判定**
- C1（Stage A root cause diagnostic script）: **REQUEST_CHANGES**

**Q1回答**
- (a) heuristic 妥当性:  
  - `raw<0.005` は「一次スクリーニング」としては妥当。  
  - `killed>=5` は母集団サイズ依存が強く要補正。  
  - `std drop>0.5 && active_clause unique==1` は現設定では交絡が強く、現状のままは不適切。
- (b) `size_norm`逆算精度: 実用上は概ね問題なし。`alpha>0` ガード、`np.isfinite`、許容誤差付き比較を入れれば十分。
- (c) 出力 spec（md+json）: 方向性は十分。ただし Run-29意思決定には「判定根拠の分母・条件集合・非評価理由」を json に追加したい。
- (d) Run-27分類予測: **P1優勢**。P2は否定的、P3は現設計だと **INCONCLUSIVE**（設定制約と分離不能）。

**Q2 改善提案**
- [Critical] P3判定が `max_clause=1` 環境で実質的に非識別。  
  修正案: `config.max_clause<=1` のとき P3を自動 `N/A` とし、`non_evaluable_reason` を json に出力。
- [Warning] P2の `K>=5` は母集団サイズ・世代数で閾値意味が変わる。  
  修正案: `K>=max(3, ceil(0.01*N_valid))` のように比率併用へ変更。
- [Warning] sentinel除外が指標ごとに不統一だと NaN/極値が混入しうる。  
  修正案: 共通 `valid_mask`（finite、sentinel除外、必須列存在）を全集計で再利用。
- [Suggestion] 判定の信頼度（High/Medium/Low）と反証結果を md/json に明示。
- [Suggestion] `best fitness_pen` 世代停滞長（plateau length）を補助指標として追加。

**Q3 考慮漏れへの回答**
- sentinel個体の内訳追加集計: **追加推奨**。ただし root cause断定には使わず「データ品質セクション」で分離（C6）。
- gen11-15停滞可視化: **追加推奨**。探索dynamicsの補助証拠として有効。
- `--baseline run_id` 比較: 今ラウンドでは **非推奨**（スコープ肥大）。まず単一run診断を堅牢化後に別施策化。

**全体判定**
- **CHANGES_REQUESTED**

**次ラウンド申し送り（収束用）**
- 反証可能仮説（1つ）: 「`max_clause=1` では現行P3条件は識別力を持たず、P3判定の多くは設定由来の擬陽性である」。
- 最小変更（1つ）: 「`max_clause<=1` 時に P3 を `N/A` 化し、json に `non_evaluable_reason` を追加する」。  
この1点が入れば、C1は **APPROVE** に寄せられます。