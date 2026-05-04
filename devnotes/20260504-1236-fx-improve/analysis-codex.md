# RUN run_20260504_032451 (run-27) Codex 独立分析

## 前提
- `P1` 提供データ（archive集計・run比較）が正しいことを前提にする: **verified(入力内整合の範囲)**  
- `P2` Stage A 判定が `trade_sharpe_raw` と `threshold=0.0` に依存すること: **partially verified**（「max=0.001134」と「A通過0」が同時成立しており、判定式/別ゲートの未確認点あり）
- `P3` archive `NaN/0.0` は「保存経路の問題」であり「評価経路の問題」と同一とは限らない: **verified(C2準拠の仮置き)**
- `P4` run-26/run-27 比較は設定差（pop/gen）が大きく、単純比較は交絡を含む: **verified**
- `P5` mission は「live_criteria同時充足 + cross-pair(ii-lite)通過」: **verified**

## 観察事実 (Facts)
- run-27 は `n=640` 個体、`A/B/C pass=True = 0`、graduation=0。
- `best fitness_pen=-0.007865...`、`best fitness_raw=0.001134`。
- best 個体は `trade_count=3526`、上位は generation 11-15 で停滞。
- `instrument/lane` は全個体 `EUR_JPY/tier1_EUR_JPY` のみ。
- archive列 `archive_role/source_stage/sharpe` が全 NaN、`total_pnl/max_drawdown_pct` は全0.0。
- trade_count は `>=1500` が 90.2%、`0` は 1.4%（9個体は `fitness_pen=-1e9`）。
- `trade_sharpe_raw`: mean -0.0811, std 0.105, max 0.001134, 99.8% が 0以下。
- `active_clause` は全個体1、`n_nodes` 平均2.4（世代進行で減少）。
- run-26 比較で run-27 は best悪化（0.005352→-0.007866）、max raw Sharpe悪化（0.0099→0.0011）。

## 解釈・推論 (Interpretations)
- `I1`（Stage A固着=構造限界）: **一部支持だが確定不可**。  
  反証可能性(C9): Stage A判定ログで「失敗理由内訳（閾値未達/露出不足/他条件）」を個体単位で集計。もし閾値未達が主因でなければ I1 は棄却。
- `I2`（max_clause=1, n_nodes=2.4で表現力不足）: **現データだけでは過主張**。  
  反証可能性: 同一seed帯で `max_clause` だけを 1→2/3 に変えた A/B テスト。Stage A通過率・bestの改善がなければ棄却。  
  補足: run-26の方が良い値を出しており、単純に「複雑化不足」とは断定不能。
- `I3`（過剰取引がノイズ増幅）: **弱支持**。  
  反証可能性: trade_count分位ごとの raw Sharpe を同条件比較（同primitive/同世代）。低頻度帯も負なら「過剰取引主因」説は弱まる。  
  C7: n=640 で分布観察は妥当、ただし因果は未確定。
- `I4`（archive伝搬漏れ=loop_closure不到達）: **未確定**。  
  反証可能性: 評価時のメモリ上メトリクスと parquet 出力の差分監査。差分のみなら「観測系バグ」、評価値自体欠損なら「実行系バグ」。
- `I5`（cross-pair shadow不可）: **支持**（事実）。  
  ただし run-27段階では Stage A全滅のため、直近の一次ボトルネックではない。mission観点では中期の必須ブロッカー。
- `I6`（dual-path副作用）: **証拠不足でINCONCLUSIVE (C8)**。  
  反証可能性: legacy経路ON/OFFで同一入力リプレイし、stage判定・fitness差を比較。

### 追加で棄却/修正すべき点（Claude自己分析への指摘）
- 「全個体 `trade_sharpe_raw <= 0` でA失敗」は、提示値 `max=0.001134` と矛盾。**判定指標の取り違え/丸め/別ゲート存在**の可能性が高い。  
- `NaN列` から即「死にコード」と断定は **C2違反リスク**。保存スキーマ不一致でも同症状は起こる。  
- `max_clause拡張` を即 Critical に置くのは、**仕組み未検証のまま値を弄る**リスク。

## 次サイクル候補
- [Critical] **Stage A判定契約の監査を最優先**（判定式・入力指標・失敗理由内訳・archive出力の一致確認）。  
  目的: 「評価系が正しい」ことを先に反証不能化し、閾値/探索空間調整の前提を固める。
- [Warning] **archive伝搬漏れの切り分け修正**（実行系 vs 観測系）。  
  目的: 誤診防止。loop_closure到達可否はログ事実で確認。
- [Warning] **表現力拡張は小幅ABで検証**（`max_clause 1→2` など最小変更）。  
  目的: 大改造禁止に従い、Stage A通過率の因果を確認。
- [Warning] **cross-pair(ii-lite)を設計上有効化する準備**（複数instrumentデータ供給経路）。  
  目的: mission最終条件の未達要因を早期に解消。ただし直近は Stage A監査後。

## 全体判定
**CRITICAL_DRIFT**

---

### 質問への直答（要約）
1. **反証可能**: I1-I6すべて反証可能。現時点で明確に棄却寄りは `I2`（断定過剰）, `I4`（死にコード断定過剰）, `I6`（証拠不足）。  
2. 優先順位（mission寄与）: `Stage A判定契約監査` > `archive切り分け` > `小幅な表現力AB` > `cross-pair有効化`。  
3. 先人の知恵:  
   - Bailey et al. (2014) *The Probability of Backtest Overfitting*（見かけ改善の罠）  
   - López de Prado (2018) *Advances in Financial Machine Learning*（検証設計・リーク管理）  
   - Poli, Langdon, McPhee (2008) *A Field Guide to Genetic Programming*（早熟収束/表現力）  
   - zenigame内の同種実例は本回答では**要確認**（実ファイル未照合）。  
4. 見落とし候補: 「Stage A失敗理由の内訳不足」「評価値と保存値の分離」「判定式の符号/比較演算子/丸め誤差」。  
5. C1-C9観点のover-claim: 上記 `I2/I4/I6` が主。特に C1, C2, C8 の逸脱リスクがある。