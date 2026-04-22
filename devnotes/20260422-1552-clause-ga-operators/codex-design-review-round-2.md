**指摘事項（重要度順）**
1. **`max_depth` hard cap が `gate_swap` で依然として破られます（Round 1 指摘1の本質が未解決）**  
事実: `gate_swap` は `local_gate` を無条件交換しており、幅チェックがありません（[detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/detailed-design.md:454), [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/detailed-design.md:470)）。一方で `max_depth` は clause 幅上限として定義されています（[detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/detailed-design.md:211)）。  
解釈: 例として `a: dir=4, gate=0` と `b: dir=3, gate=1`（いずれも幅4）で gate 交換すると、片方が幅5になります。`directional_swap` の修正は良いですが、演算子全体として hard cap 契約をまだ満たしていません。

2. **lint 違反候補がまだ残っています（Round 1 指摘3は未完了）**  
事実: 未使用 import が残っています。  
- 関数内未使用 import: [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/detailed-design.md:1188) (`ClauseConfig`)  
- 関数内未使用 import: [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/detailed-design.md:1285) (`mod`)  
- モジュール未使用 import: [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/detailed-design.md:1448) (`random`)  
- モジュール未使用 import: [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/detailed-design.md:1450) (`pytest`)  

**観点別評価**
1. Round 1 指摘1-4への対応  
- 1: `directional_swap` 単体は改善。ただし `gate_swap` 経路で同じ契約破綻が残るため十分ではない。  
- 2: alpha テスト分割は目的に合致しており妥当（`pen==raw` / `pen<raw` を直接検証）。  
- 3: 未使用要素は減ったが、上記 import が残存。  
- 4: `params_perturb` は `_signal_at` / `_signal_spec` 抽出で可読性・整合性ともに改善。  

2. directional_swap fallback（両子同時超過条件）  
- `or` 条件後に両側を個別 trim しており、**両子同時超過ケース自体は処理できています**（[detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/detailed-design.md:414), [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/detailed-design.md:427)）。  

3. 新 alpha テスト  
- 目的達成しています（`alpha=0` と `alpha>0` の期待関係を直接検証）。  

4. params_perturb リファクタ  
- ロジックは正しく、重複条件の解消もできています。  

5. 残る lint 候補  
- 上記4件が明確な候補です。  

REVISE