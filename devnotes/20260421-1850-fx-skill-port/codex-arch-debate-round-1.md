## Q1. 軸 1 — Clause 構造は FX に有効か?
### 観察された事実 / 文献根拠 (Facts)
- F1: GP/シンボリック回帰は表現力と引き換えに探索空間が急増し、`bloat` と過学習が主要課題になる（Koza, 1992, *Genetic Programming*; Poli, Langdon, McPhee, 2008, *A Field Guide to Genetic Programming*; Luke & Panait, 2006, *A comparison of bloat control methods for genetic programming*）。
- F2: 金融時系列の進化的ルールは IS で好成績でも OOS で劣化しやすく、コスト反映で優位が縮小しやすい（Allen & Karjalainen, 1999, *Using Genetic Algorithms to Find Technical Trading Rules*; Neely et al., 1997 の FX-GP 論文はタイトル要確認）。
- F3: 非定常系列では「条件に応じて局所モデルを切替える」構造が有効で、gating/mixture-of-experts は理論的裏付けがある（Jacobs et al., 1991, *Adaptive Mixtures of Local Experts*; Jordan & Jacobs, 1994, *Hierarchical Mixtures of Experts and the EM Algorithm*）。
- F4: FX はセッション・指標発表・流動性低下時のスプレッド急拡大など状態依存性が強く、単一ロジック常時適用は不利になりやすい（Evans & Lyons, 2002, *Order Flow and Exchange Rate Dynamics*; 実務知見として一般的）。

### 解釈・推論 (Interpretations)
- I1 (from F1, F3, F4): Clause（directional × local_gate × weight）は、FX の「局所レジーム切替」を明示的に表現できるため、フラット 4 式より構造的バイアスとして有利。
- 反証可能性(I1): 同一複雑度制約下で、Clause 型がフラット型に対して OOS Sharpe/DSR で一貫優位を示せなければ I1 は棄却。
- I2 (from F1, F2): Clause は自由度増加により、1銘柄時系列ではむしろ過学習を悪化させるリスクがある。
- 反証可能性(I2): `max_clause`, `max_depth`, 複雑度ペナルティ導入後も OOS 劣化が続くなら、Clause 自体が不要/有害の可能性が高い。
- I3 (from F4): FX 特有制約（ニュース回避、セッション終端クローズ、スプレッド閾値）を「gate」として実装しやすいのは Clause の実務上の利点。
- 反証可能性(I3): 同等機能をフラット式の外側ルールで簡潔に実現でき、性能差がなければ Clause 優位は消える。

### 暫定判定 (Verdict)
- Claude の暫定推奨に対する評価: **CONDITIONAL**
- Confidence: **MEDIUM**
- 主要な懸念事項
- Clause 導入時に複雑度管理を設計しないと、FX 1銘柄学習で `bloat` が先に勝つ可能性が高い。
- 「Clause が必要」ではなく「レジーム分割が必要」であり、実装手段は Clause 固定でなくてもよい。

---

## Q2. 軸 2 — 銘柄特化 GA は妥当か?
### 観察された事実 / 文献根拠 (Facts)
- F1: 資産横断で Value/Momentum の共通性があるという証拠は強い（Asness, Moskowitz, Pedersen, 2013, *Value and Momentum Everywhere*）。
- F2: 通貨市場でも共通ファクター・通貨モメンタムの存在が報告される（Menkhoff et al., 2012, *Currency Momentum Strategies*; Lustig, Roussanov, Verdelhan, 2011, *Common Risk Factors in Currency Markets*）。
- F3: 一方で GA/GP 実装研究は計算上の都合で単一市場・単一系列最適化が多い（Allen & Karjalainen, 1999; Neely 系列の FX 論文は詳細タイトル要確認）。
- F4: 多数の候補戦略から最良を選ぶプロセス自体が強いデータスヌーピングを生み、OOS 分割があっても過学習リスクは残る（White, 2000, *A Reality Check for Data Snooping*; Bailey et al., 2014, *The Probability of Backtest Overfitting*）。

### 解釈・推論 (Interpretations)
- I1 (from F3): 現行エンジンが単一 instrument 前提なら、(i) は実装到達性が最も高く、初期マイルストーンとして合理的。
- 反証可能性(I1): 実装容易でも、再現 run で champion の符号が頻繁反転するなら「動くが使えない」ため合理性は崩れる。
- I2 (from F1, F2): FX 6ペアでも共通ドライバー（USD 要因、リスクオン/オフ）があり、完全分離最適化は情報共有を捨てる。
- 反証可能性(I2): universal/横断 fitness が per-instrument より一貫して悪ければ、情報共有の便益は小さい。
- I3 (from F4): Stage B + Alpha Sieve は必要条件だが十分条件ではない。選抜回数が多い限り false discovery は残る。
- 反証可能性(I3): DSR/PBO/Reality Check で統計的優位が安定して出るなら、十分性の懸念は緩和。

### 暫定判定 (Verdict)
- Claude の暫定推奨に対する評価: **CONDITIONAL**
- Confidence: **MEDIUM**
- 主要な懸念事項
- 「6ペアは少数だから特化でよい」は因果ループを切断しやすい。間接経路（USD 共通因子、三角裁定制約）を無視しない検証が必要。
- per-instrument を採るなら、必ず universal ベースラインを同時運用して反証可能性を担保すべき。

---

## Q3. 中間案: 銘柄非依存ゲノム × ペア横断 fitness 集約
### 観察された事実 / 文献根拠 (Facts)
- F1: 「同一ゲノムを複数ペアで評価し fitness 集約」は本質的に universal 評価であり、(ii) の軽量版に近い。
- F2: ただし Portfolio GA (iii) と違い、資金制約・同時ポジション相関・執行競合を内生化しない点で別物。
- F3: 複数環境同時評価は過学習耐性を上げる一方、計算量はほぼ `N_pairs` 倍になる。
- F4: 集約関数は選好（平均重視か最悪ケース重視か）を直接埋め込むため、探索結果を一次的に変える。

### 解釈・推論 (Interpretations)
- I1 (from F1, F2): 中間案は「(ii) と同じか?」への答えは「ほぼ同じだが、ポートフォリオ実行制約を持たない点で (iii) とは明確に違う」。
- 反証可能性(I1): portfolio 制約を導入しても結果がほぼ不変なら、(ii)/(iii) の差は小さい。
- I2 (from F3): 計算コスト増は、OOS 分散低下・DSR 改善が観測されるなら正当化される。
- 反証可能性(I2): 同計算予算で比較して優位がなければ、横断評価の費用対効果は低い。
- I3 (from F4): `mean` は平均性能偏重、`min` は頑健性偏重、`portfolio sharpe` は相関構造依存で、選択結果は大きく変わる。
- 反証可能性(I3): 集約関数を変えても champion 群が安定なら、目的関数依存性は小さい。

### 暫定判定 (Verdict)
- Claude の暫定推奨に対する評価: **SUPPORT（補助線として）**
- Confidence: **HIGH**
- 主要な懸念事項
- 中間案を「保険」ではなく昇格条件に組み込まないと、per-instrument の自己強化ループを断ち切れない。
- 集約関数の設計を曖昧にすると、結果の解釈が不能になる。

---

## Q4. Stage A/B/C のサンプルサイズ問題
### 観察された事実 / 文献根拠 (Facts)
- F1: 1分足は観測数が多く見えても自己相関・ボラクラスタリングで実効サンプルサイズは大きく低下する（時系列統計の一般原則）。
- F2: 戦略探索では「試した回数」が増えるほど見かけの Sharpe が上振れし、補正なし評価は危険（Bailey et al., 2014, *The Probability of Backtest Overfitting*）。
- F3: Deflated Sharpe Ratio は非正規性・複数試行バイアスを補正するため、GA 文脈で有用（Bailey & López de Prado, 2014, *The Deflated Sharpe Ratio*）。
- F4: データ漏洩を抑えた時系列検証（purging/embargo, combinatorial variants）は単純 split より頑健（López de Prado, 2018, *Advances in Financial Machine Learning*）。
- F5: 複数ルール比較には White Reality Check / SPA が実務的に重要（White, 2000; Hansen, 2005）。

### 解釈・推論 (Interpretations)
- I1 (from F1-F5): 1銘柄 OOS でも検出力を確保するには、単発 Stage B では不十分で、反復 walk-forward + DSR/PBO/Reality Check が必要。
- 反証可能性(I1): これら補正後も安定優位（例: DSR 正、PBO 低、fold 間一貫）なら、1銘柄でも実運用可能性は上がる。
- I2 (from F2-F5): false discovery 抑制策が弱いなら、(b)×(i) は「最適化器として強いが検証器として弱い」構造になる。
- 反証可能性(I2): 反復 OOS で符号反転率が低く、コスト後優位が維持されるなら懸念は後退。
- I3 (from F1-F5): (ii)/(iii) への移行閾値は、性能水準より「統計的一貫性の欠如」で決めるべき。
- 反証可能性(I3): 一貫性が確保できるなら移行は不要。

### 暫定判定 (Verdict)
- Claude の暫定推奨に対する評価: **CONDITIONAL**
- Confidence: **MEDIUM**
- 主要な懸念事項
- 1銘柄評価では、`試行数管理` をしない限り Stage B/C が形式化しやすい。
- 閾値未定義のまま運用すると、都度都合の良い解釈に流れる。

---

## 【総合判定】
- 総合評価: **(b) × (i) は「初期実装としては採用可」、ただし恒久設計としては CONDITIONAL**。
- 採用条件:
1. Clause 導入と同時に複雑度制約（`max_clause`, `max_depth`, 複雑度ペナルティ）を必須化。
2. per-instrument Champion 昇格時に、必ず「横断 fitness 集約（中間案）」を追加ゲートとして実施。
3. 評価指標を Sharpe 単独にせず、DSR・PBO・Reality Check（または SPA）を運用指標に入れる。
4. 移行トリガーを事前固定する。例として、連続 run で DSR が非正、PBO 高止まり、fold 符号反転多発なら (ii) へ移行。portfolio 制約起因の乖離が大きければ (iii) を検討。
- 推奨方針: **「(b) × (i) で開始し、(ii-lite) を常設ベンチマークとして並走」**。これが falsification-first の要件を最も満たす。