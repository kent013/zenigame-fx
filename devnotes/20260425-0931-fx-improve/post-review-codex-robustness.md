1. **優先度: Critical**  
提案: **Stage B「統計可観測性ハード契約」導入（Metric Completeness Gate）**  
内容: `fold_sign_ratio` / `dsr` / `n_folds` / `n_trials` のいずれか欠損(`n=0`含む)なら `passed=False` を強制し、`reason_code=stats_unavailable` を標準化。加えて archive/report 側で「欠損率」を世代別に常時監査。  
テーマ固有の効果評価: Run 7-9 の最大論点である「Stage A 通過後も WF/DSR 未記録」を fail-open から fail-closed に反転でき、過学習判定の空洞化を停止。Stage B=0 の理由が“弱さ”か“測定不能”かを分離可能。  
実装難易度: 中  
実装規模: 中  
trade_count 影響予測: 不変（副次的に増の可能性）  
T025/T027との差分: T025は追加OOS検証、T027はStage A閾値調整。本提案は**計測欠損を通過不能化する契約層**で別物。

2. **優先度: Critical**  
提案: **Stage B に DSR+PBO の二重ハードゲート化（pool統計前提）**  
内容: 個体単体ではなく「Stage A通過プール」の SR 分布から DSR を計算し hard 適用。さらに top-M に CSCV PBO-lite を実行し、`DSR hard AND PBO hard` の複合通過に変更。  
テーマ固有の効果評価: 「単発1-2 trade 高Sharpe」の見かけ優位を統計的に剥離し、Stage B/C 連続0通過の原因を“過学習候補の淘汰”として明示化。  
実装難易度: 高  
実装規模: 大  
trade_count 影響予測: 増（単発取引依存個体が落ち、安定的に取引する個体が相対的に残る）  
T025/T027との差分: T025はStage C後Sieve、T027はStage Aのみ。本提案は**Stage B中核の統計ゲート強化**。

3. **優先度: High**  
提案: **WF-OOS の多窓・非連続化（Regime-Stratified WF）**  
内容: 単一路線の rolling fold から、短期/中期の複数 test 窓と gap 付き非連続 fold を併用。通過条件を「中央値」だけでなく「最悪fold下限 + fold間分散上限 + 有効fold数下限」に再設計。  
テーマ固有の効果評価: レジーム偏在で偶然当たった個体を抑制し、B通過率0固定とA通過率の過大変動を構造的に縮小。  
実装難易度: 高  
実装規模: 大  
trade_count 影響予測: 不変（副次的に増の可能性）  
T025/T027との差分: T025はStage C後の単一追加OOS。本提案は**Stage BのWF設計そのもの**の拡張。

4. **優先度: High**  
提案: **Alpha Sieve の「時間分散OOS」化 + 通過基準校正ブリッジ**  
内容: 90日単窓を複数非連続OOS窓へ拡張し、`majority pass + worst-window floor` を導入。さらに Stage CスコアとSieve実OOS成績の信頼度曲線を定期更新し、通過基準を“予測整合性”で校正。  
テーマ固有の効果評価: single instrument 時の cross-pair skip で失われた OOS 検証を時間軸で補完し、過学習候補の見逃しを削減。  
実装難易度: 中  
実装規模: 中  
trade_count 影響予測: 不変  
T025/T027との差分: T025の**上位拡張**だが、単純な閾値変更ではなく OOS設計と校正層の追加。

5. **優先度: High**  
提案: **GAに多様性保全目的を明示追加（Anti-Collapse Evolution）**  
内容: fitness 単独最適化をやめ、`performance + novelty` の二目的化。primitive 構成エントロピー下限、同型クローン距離ペナルティ、family別ニッチ割当で縮退を抑制。  
テーマ固有の効果評価: 観測済みの primitive 縮退（20→7-10種）を構造的に抑え、特定型の過学習増殖を防止。Stage A/B/C 通過率の“世代内崩壊”を緩和。  
実装難易度: 中  
実装規模: 中  
trade_count 影響予測: 増（無取引クローン集中を抑えるため）  
T025/T027との差分: ゲート閾値ではなく**探索ダイナミクス**の改善。

6. **優先度: Medium**  
提案: **レジーム持続リスク・センチネル導入（Half-life/Transition監査）**  
内容: ボラ/トレンド/流動性レジームを離散化し、優位性の持続半減期・遷移エントロピー・レジーム別劣化率を算出。短命レジーム依存が強い個体は Stage B/C で追加減点または fail。  
テーマ固有の効果評価: 「今だけ効く」戦略の流入を事前に抑え、継続運用時の崩壊リスクを低減。migration trigger の根拠統計にも直結。  
実装難易度: 中  
実装規模: 中  
trade_count 影響予測: 不変  
T025/T027との差分: しきい値調整ではなく**レジーム安定性の新規診断軸**追加。