# マージ分析: Run 10

## 合意事項（両者一致）

- **Run 10 は CRITICAL_DRIFT 状態**: best 個体 trade_count=3 / sharpe=18.49 / total_pnl=18860（live_criteria の total_pnl・trade_count 未達）。
- **Stage A overpass + Stage B 全滅**: archive 5856 行中 A=4291 (73%) / B=0 / C=0 を 60 世代維持。Stage A gate が低頻度・低分散個体を素通しさせている。
- **best 構造の極端な単純化**: n_nodes=2, active_clause=0、最小複雑度に収束。多様性枯渇の兆候。
- **禁止事項 6（取引回数削減で見かけ改善）の予備軍**: trade_count=3 で sharpe を稼ぐ挙動は典型的な逸脱パターン。直接違反は未確定だが運用上は危険信号。

## Claude 独自の発見

- 前回 Run との比較で best_fitness は急上昇（0 → 18.48）。これは「進化が機能している」のではなく「Stage A 通過個体が少数の高スループット低取引数戦略に偏った」結果。
- holdout 37832 bars が用意されているのに Stage B/C に届いていない。

## Codex 独自の発見

- **H1 (高 Sharpe = 戦略品質改善)** を明確に棄却。
- **H2 (GA 進化で実運用条件に近づく)** も棄却。「A 最適化のみ進行、使命非収束」。ゲート間ミスマッチが主因。
- **構文多様性の計測**（generation 別 unique 式数 / primitive 使用エントロピー）が次のヒントになる。

## 矛盾・要議論

なし（両者の方向性は一致）。

## 統合改善提案（優先度順）

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | 期待効果 |
|---|------|--------|------|--------------|-------------|---------|
| 1 | Stage A に最低取引密度制約を導入（feasibility constraint で trade_count=0 個体を selection_score で淘汰） | Critical | 両者一致 | trade_count, total_pnl | trade_count=3 に集中、A→B 遷移率ゼロ | A 通過個体が「実用的な取引頻度」を持つよう構造的に保証、B-pass 出現を期待 |
| 2 | B 全滅理由の reason_codes 集計（個体単位で sharpe/cost/trade 不足の内訳を保存） | Critical | Codex | 観測可能性 | B 失敗の内訳が見えない | 次サイクル以降の根本原因特定が容易になる |
| 3 | active-clause / clause 発火カウンタの runtime 計測 | High | Codex Warning | 多様性 | active_clause=0 への収束 | 単純式偏重の早期検知 |

提案 1 は **TODO T031 (regime-participation-constraint Phase 1)** に直接対応。提案 2 は T035、提案 3 は T037 に対応。
