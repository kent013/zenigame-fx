1. **Regime Participation Constraint（RPC）を GA の実行可能性制約として導入**
優先度: **Critical**  
概要: fitness の前段で「時間帯×ボラ regime の各セルで最低参加率」を満たさない個体を `infeasible` 扱いにし、`trade_count=0` を構造的に淘汰する（penalty 調整ではなく制約化）。  
テーマ固有の効果評価: 東京/ロンドン/NY 各帯で“無反応個体”が生き残れなくなるため、時間帯別レジーム分岐が探索の前提になる。ATRRegimeGate も「通す/止める」より「どの regime で参加するか」に再定義できる。  
実装難易度: 中  
実装規模: 中  
trade_count 影響予測: **増**

2. **Single Instrument でも動く Factor Shadow Plane（FSP）を新設**
優先度: **Critical**  
概要: `skipped_single_instrument` を廃止し、外生因子（USD broad、EUR-USD 共通因子、金利差 proxy）を使う疑似 cross-pair シャドウ評価面を常時生成。実ペア1本でも cross-pair 妥当性を評価可能にする。  
テーマ固有の効果評価: ii-lite アンカー戦略を「複数ペア実行時のみ有効」から脱却。run 形態依存の盲点を除去し、regime ごとの因子感応度監査が可能。  
実装難易度: 高  
実装規模: 大  
trade_count 影響予測: **増**（無根拠な全停止を抑制）

3. **Common Factor 分解を評価関数の一次要素へ昇格（Total→Factor+Idio）**
優先度: **High**  
概要: 損益・Sharpe を「共通因子寄与」「ペア固有寄与」に分解し、片側だけ良く見える個体を低評価化。`total_pnl=0` 近傍でも因子反応ゼロ個体を明確に識別。  
テーマ固有の効果評価: USD 共通ショックでの見かけ性能を剥がし、EUR-USD 相関局面などでの真の有効性を判別。cross-pair 改善と直結。  
実装難易度: 中  
実装規模: 中  
trade_count 影響予測: **不変〜増**

4. **Regime-Conditional Pareto Selection（単一スカラー fitness 依存を廃止）**
優先度: **High**  
概要: 世代選抜を「総合値」ではなく「時間帯別・ボラ別・factor別」の多目的 Pareto に変更。どれか1条件で無取引優位になる経路を潰す。  
テーマ固有の効果評価: NY overlap だけ/低ボラだけ等の偏り個体が独占しにくくなり、レジーム横断の生存圧が働く。  
実装難易度: 高  
実装規模: 大  
trade_count 影響予測: **増**

5. **Universal Backbone + Pair Adapter の二層遺伝子設計**
優先度: **Medium**  
概要: universal GA（共通構造）と pair-specific GA（適応部）を分離し、さらに regime ごとに adapter を切替。全停止しやすい汎用個体の暴走を抑える。  
テーマ固有の効果評価: 「普遍性」と「ペア固有性」を両立し、特定通貨ペアでのみ無取引化する崩壊モードを局所化できる。  
実装難易度: 高  
実装規模: 大  
trade_count 影響予測: **増**

6. **Opportunity Head / Execution Head の二段モデル化（発火保証つき）**
優先度: **Medium**  
概要: まず「機会検知（発火）」を最適化し、その後に方向・サイズを最適化。発火 head に regime 別最低 recall を課すことで、取引ゼロ収束を設計上不可能にする。  
テーマ固有の効果評価: ATRRegimeGate を単純遮断器から「機会抽出器」に役割転換でき、時間帯レジームでの参加率を維持しやすい。  
実装難易度: 中  
実装規模: 中  
trade_count 影響予測: **増**

以上は既存の T016/T017/T025/T027 の単純拡張ではなく、**評価軸・探索空間・表現形式**を変える構造改善です。