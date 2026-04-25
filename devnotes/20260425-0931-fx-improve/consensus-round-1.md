## Section A: 各施策の判定（Round 1）

1. **無取引ペナルティの構造的導入**  
判定: **APPROVE**  
分類: **Structural**  
target_metric: `trade_count=0` 個体比率（現状 75%）を **Run 10 で 30%未満**  
failure_mode: 無取引個体が引き続き上位を占有し、Stage A/B/C が 0 件のまま  
causal_path: 現在は `trade_count=0 -> fitness_pen=0` が相対優位。`trade_count=0` を「低優先（または不適格）」に構造化すれば、探索圧が「実際に取引する個体」へ移る  
falsification: 変更後も上位 10 個体の過半が `trade_count=0` なら仮説棄却  
success_criterion: 上位 10 個体で `trade_count>0` が過半、かつ Stage A 通過が 1 件以上

2. **PnL 集計経路の数値整合性監査**  
判定: **MODIFY**（Run 10 は「監査のみ」、ロジック改修は次ラウンド）  
分類: **Structural**  
target_metric: `trade_count>0 かつ total_pnl=0` の比率（現状 100%）の原因特定  
failure_mode: 監査せず進めて、目的関数の歪みを見逃す  
causal_path: PnL 計算/集約の不整合があると、Sharpe/fitness が無効化され探索が崩壊  
falsification: 既知の期待値を持つテストケースで `total_pnl != 0` を再現でき、実ランでも整合ログが取れれば「経路破綻」仮説を棄却  
success_criterion: 監査ログで「どの段で 0 化したか」を特定、または破綻なしを証明

3. **primitive 多様性の世代追跡**  
判定: **MODIFY**（Run 10 本体には未組込、計測だけ最小化）  
分類: **Principled Parametric**（観測強化）  
target_metric: 世代ごとの primitive 組合せエントロピー、最頻組合せ比率（現状 22%）  
failure_mode: 偏在原因を未特定のままパラメータを触って過学習  
causal_path: 早期収束で探索空間が狭まり、無取引優位と相互増幅  
falsification: 無取引優位が解消後も偏在が継続するなら、主因は多様性不足ではない  
success_criterion: Run 10 で偏在推移を可視化し、次の介入要否を判定可能にする

4. **cross-pair shadow の実測検証**  
判定: **REJECT（本ラウンド）**  
分類: **Structural**（ただし現時点では守備範囲外）  
target_metric: 通貨ペア間の汎化ギャップ  
failure_mode: 現在の単一ラン停止問題を未解決のまま検証軸を増やし、原因分離不能  
causal_path: いまは「取引が成立しない/評価が崩れている」段階で、shadow 検証は下流  
falsification: 単一ペアで Stage A 通過が安定化した後に実施  
success_criterion: Run 10 では対象外（前提未達）

---

## Section B: 実施順序と Run 10 組み込み

1. **Run 10 の最小変更は 1 件に限定**: 「無取引個体を構造的に下位化（または不適格化）」のみ本組込  
2. 同時に **PnL 監査ログを追加（挙動非変更）**  
3. 3,4 は保留し、Run 10 結果で再判定

FX 制約チェック:
- イントラデイ前提: 変更で保持  
- ロング/ショート両方向: 変更で制限しない  
- スワップ/スプレッド fitness 反映: 現行反映経路を監査対象に含める  
- 禁止事項 1/2/4/6/7: いずれも未実施

---

## Section C: 保留事項（次 Run 用）

反証可能仮説: **「Run 9 崩壊の主因は “無取引が目的関数上で優位” な構造欠陥」**  
最小変更: **`trade_count=0` を構造的に劣後させる 1 変更のみ**  
次 Run 判定:
- 成功なら: PnL 監査結果に基づき集計修正へ進む  
- 失敗なら: 仮説棄却し、PnL 経路修正を優先して再実行

---

## Section D: TODO vs GA 改善のバランス

結論: **`ga_improvements` 一択で妥当**。  
理由: 現在 TODO 0 件で、今回の主要施策は「GA 目的関数の構造修正 + 数値整合監査（バグ切り分け）」で improve-cycle 守備範囲内。