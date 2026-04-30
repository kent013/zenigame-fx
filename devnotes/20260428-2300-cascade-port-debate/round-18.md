**1. synthesis章立て提案**
1. `Mission / Scope / Non-Negotiables`
2. `Why Fresh Redesign (Round 1-10 との差分と破棄理由)`
3. `Fixed Constraints (A〜Fの確定事項一覧)`
4. `Data Contract (epoch, dataset_epoch_id, leakage guard)`
5. `Cascade Spec (A/B/C-lite/C の時系列配置と判定責務)`
6. `Metric Taxonomy (canonical5 gate vs Pareto3 search 分離)`
7. `GA Core (NSGA-II + CPPS 3-state, CA/DA動的比率)`
8. `Loop Closure (archive, inflow, warmstart, bypass, eviction)`
9. `Emergency + Calibrate-Gate`
10. `Observability / Audit (A-B乖離, entropy, PBO/DSR/SPA scaffold)`
11. `Implementation Plan (T901-T918, DoD, parallelizable phases)`
12. `INCONCLUSIVE & Smoke Recalibration Plan`

**2. Round 1-10 の扱い**
削除は非推奨です。`historical/` に隔離して「前提誤りを含むため実装根拠としては無効」の明示注記を付けて残すのが最適です。  
残す価値は「誤読パターンと再発防止知見」の監査ログです。

**3. 次の judgement points（最終承認項目）**
1. `pop=192 baseline / 256 promotion` を正式採用するか
2. `lane_parallelism=1 (EUR_JPY anchor)` を当面固定するか
3. `search=A proxy / archive admission=B pooled` のハイブリッドを採用するか
4. `warmstart emergency 25% (35%不採用)` を正式化するか
5. `score_bypass は B評価済み個体のみ` を厳格運用するか
6. `dataset_epoch_id 必須契約` を fail-closed にするか

**4. やってはいけないリスト**
- gate指標とsearch指標を同じランキングで混ぜる
- shadow pair を selection objective に入れる
- epoch_id なしデータを archive/history に保存する
- A-only proxy 個体を bypass で archive に入れる
- 緊急時に prev_epoch 制約を緩めて帳尻を合わせる
- C-lite/B の sample不足状態で bucket数を増やす
- smoke前に値チューニングで辻褄合わせをする

**5. next action top 3**
1. `T901` を最優先で実装し、全経路 `dataset_epoch_id` 契約を固定
2. `T902/T903` で epoch manager と partition splitter を確定
3. `T904/T905` で canonical5 / mission_inf_gap / HAC Sharpe を単一API化

**6. 最終 sanity check**
重大な論理矛盾はありません。  
注意点は3つだけです。`gen=48 fallback 時のFSM再校正`、`pop256時のE系パラメータ自動スケーリング明文化`、`A時系列がBより後であることの明示`（誤実装防止）です。

**7. フリー領域（見落とし候補）**
- コストモデルの時変性（spread/swap regime drift）を epochごとに再検証する契約
- 再現性契約（seed固定、同一入力で同一選抜結果）
- timezone/DST・休日境界での session bucket ずれ検査
- `A→B乖離` が増えたときの自動フェイル条件（監視だけで終わらせない）