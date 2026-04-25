前提確認:
- 既存 Open TODO は空で、提示された Closed TODO（T021-030）とは実質重複しない案のみ選定しました。
- `active_clause=0` は実装上 placeholder 固定値です（現状は構造指標として機能していません）。
- `trade_count>0` なのに `total_pnl=0` は、Stage A 失敗個体で `total_pnl` が archive に未転記の経路が主因です（評価不整合というより記録不整合）。

1. **優先度: Critical — 評価・選抜の整合性修復（無取引優位の構造是正）**  
テーマ固有の効果評価:  
- `pnl_record_consistency = P(trade_count>0 かつ total_pnl!=0)` を 1.0 へ  
- `best_no_trade_rate`（取引個体が存在する世代で best が trade_count=0 になる率）を 0 へ  
実装難易度: 中  
実装規模: 中  
trade_count 影響予測: 増  
- 理由: 無取引個体が選抜優位になりにくくなり、実際に取引する個体へ探索圧が戻るため。

2. **優先度: Critical — active_clause の実測化（Clause が機能しているかを可視化）**  
テーマ固有の効果評価:  
- `active_clause_mean` が 0 固定から脱却  
- `clause_activation_entropy`（Clause発火多様性）を世代比較可能に  
実装難易度: 中  
実装規模: 中  
trade_count 影響予測: 不変  
- 理由: 主目的は観測精度向上。副作用で gate 診断が進み、間接的に増加はあり得る。

3. **優先度: High — ルックアヘッド再監査の“全経路”テスト化（compute / compute_all_bars / full-path）**  
テーマ固有の効果評価:  
- `lookahead_violation_count` を CI で常時 0 管理  
- `prepared vs unprepared`・`prefix vs full` の同値率 100%  
実装難易度: 中  
実装規模: 中  
trade_count 影響予測: 不変  
- 補足: 現コードには `_compute_full` という関数名の経路が無いので、backtest full-path を明示的に同値検証対象へ追加するのが実務上の穴埋めになります。

4. **優先度: High — プリミティブ多様性の縮退抑制（相関・冗長性を目的関数で抑える）**  
テーマ固有の効果評価:  
- `primitive_entropy` 上昇、`top4_share`（P7/F11/P9/P5 依存）低下  
- `redundancy_index`（高相関ペア比率）低下  
実装難易度: 高  
実装規模: 大  
trade_count 影響予測: 増  
- 理由: 同型シグナル集中が緩和され、発火パターンが増えるため。

5. **優先度: Medium — 死滅プリミティブ管理（Keep / Reparam / Retire の構造運用）**  
テーマ固有の効果評価:  
- 各 primitive の `survival_rate`、`conditional_contribution`（除去時Δfitness）、`sign_stability` を run 横断で管理  
- 「死滅」判定を感覚でなく統計基準化  
実装難易度: 中  
実装規模: 中  
trade_count 影響予測: 増  
- 理由: 過剰抑制ゲートや常時0近傍 directional を整理すると、実効発火が増えやすい。

6. **優先度: Medium — 新規プリミティブ群（FXイントラデイ向け、文献根拠あり）**  
テーマ固有の効果評価:  
- 既存32種に対する `marginal IC`、`low-corr incremental gain`、`OOS fold sign ratio` 改善  
実装難易度: 中  
実装規模: 中  
trade_count 影響予測: 増  
提案プリミティブ:  
- `RVJumpGap`（directional）: `RV - BV` でジャンプ成分を抽出し、方向性シグナル化  
- `HARVolRegimeGate`（gate）: HAR-RV 的な短中長ボラ成分で取引可能レジームを判定  
- `SessionActivityPulse`（gate）: 時間帯周期性・流動性集中（特に主要センター重複時間）をゲート化  
根拠:  
- ジャンプ分離: Barndorff-Nielsen & Shephard (2004)  
- HAR-RV: Corsi (2009)  
- FX日中季節性: Ito & Hashimoto (2006)  
- マイクロ構造と為替変動: Evans & Lyons (2002)  
- 実務面の流動性集中: BIS Triennial 2025

**参考リンク**  
- https://academic.oup.com/jfec/article/2/1/1/960705  
- https://academic.oup.com/jfec/article/7/2/174/856522  
- https://www.nber.org/papers/w12413  
- https://www.nber.org/papers/w7317  
- https://www.bis.org/statistics/rpfx25_fx.htm