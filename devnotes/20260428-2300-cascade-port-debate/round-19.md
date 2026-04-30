**1. G1〜G20 診断（zenigame 実装参照つき）**

| Gap | 判定 | zenigame 根拠 | fx 最終仕様（提案） |
|---|---|---|---|
| G1 Stage A gate 性質 | 実gap（明文化不足） | Stage A は hard pass 後に top ratio 抽出。[stage_a_gate.py](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/stage_a_gate.py):66, [optimize.py](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/optimize.py):950 | `hard gate + q_force(top比率)` の両立を仕様固定 |
| G2 canonical5 worst の stage 閾値 | 実gap | Stage A は gate_score 専用関数、C-lite/C は別 gap 系統。[fitness.py](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/evaluation/fitness.py):461, [live_criteria_gap.py](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/evaluation/live_criteria_gap.py) | Stage別閾値を分離（A=proxy閾値、B/C-lite/C=mission連動） |
| G3 A-fail 個体の扱い | 実gap | B評価対象は A-pass のみ。[optimize.py](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/optimize.py):1006, [optimize.py](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/optimize.py):1195 | A-fail は当世代 B/Archive 不可。親選択母集団からも除外 |
| G4 q_force の意味 | 曖昧だが補足でOK | `stage_b_ratio` は「Bへ送る比率」。[stage_a_gate.py](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/stage_a_gate.py):7 | q_force=「A-pass集合内 top 比率」で固定 |
| G5 Pareto 3軸の評価値ソース | 実gap | 世代内主選抜は passed_b ベース。[optimize.py](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/optimize.py):2125, [optimize.py](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/optimize.py):2141 | `A-proxy を主選抜に使わない`。主選抜は B-pooled 指標で統一 |
| G6 GA operators | 実gap | 実装は tournament+crossover+mutation。[breeding.py](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/breeding.py):211, [breeding.py](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/breeding.py):255 | 率・演算子・自己交配回避回数を仕様化 |
| G7 Parent selection | 非gap（既決可） | binary tournament 実装あり。[breeding.py](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/breeding.py):211 | NSGA-II tournament + CA/DA 比率サンプルで確定 |
| G8 Run1 初期母集団 | 実gap | run開始時に初期生成、warmstartは別注入。[ _runner.py ](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/runner/_runner.py):673 | Run1 は fresh 100%、Run2+ は warmstart 併用 |
| G9 Determinism 契約 | 実gap | seed固定 RNG。[core.py](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/core.py):114 | 同率 tie 最終キー（genome_hash）を追加し完全決定化 |
| G10 失敗 genome 扱い | 非gap（既決可） | 失敗は +inf / all-fail abort。[core.py](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/core.py):1026, [core.py](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/core.py):1085 | 同方針で固定 |
| G11 backtest engine 出力拡張 | 実gap | zenigame側に直接該当なし | fx engine に session block PnL / bucket / block trade_count を追加 |
| G12 DSL/primitive 変更 | INCONCLUSIVE | 参照可能だが fx固有設計依存 | big-bang初版は最小差分、拡張 primitive は次イテレーション |
| G13 timezone/DST/holiday | 実gap | 株式設計は流用不可 | FX専用 session境界（UTC基準）を contract 化 |
| G14 cost model 時変性 | INCONCLUSIVE | zenigame spread 前提と差異 | 初版は固定+監視、epoch再校正は smoke 後判断 |
| G15 aux依存整合 | 曖昧だが補足でOK | fx固有 preflight が主 | HARD_REQUIRED を Stage算出項目と1:1対応に明文化 |
| G16 PBO/DSR/SPA | 実gap | DSR実装あり。[ _dsr.py ](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/runner/_dsr.py):126, [fitness.py](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/evaluation/fitness.py):553 | DSR先行実装、PBO/SPA は明示的に「未実装」タグで段階追加 |
| G17 graduation lane method | 実gap | zenigameに同型なし | fx独自に multi-pair batch 評価仕様を新設 |
| G18 A→B乖離 fail 条件 | 実gap | 既存は監視中心 | hard fail ではなく `warn→q_force引上げ` で開始 |
| G19 Run/Epoch/Population 境界 | 非gap（既決） | Runごとに optimize 実行/終了境界あり。[ _runner.py ](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/runner/_runner.py):952 | Round18 記述で十分 |
| G20 clean-up 範囲 | 実gap（実ファイル突合が必要） | 旧経路が残ると二重意味 | 削除対象リストを「コード存在確認ベース」で確定実施 |

**2. 追加 gap（こちらで特定）**
- `T509=multi-state` は事実不一致。現行 zenigame 実装は push/pull の2状態。[push_pull_fsm.py](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/push_pull_fsm.py):45  
- `dataset_epoch_id` が genome archive schema に無い。[genome_archive.py](/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/genome_archive.py):540  
- `PBO/SPA 実装済み` 前提は不成立。DSRのみ実装確認。  
- Stage B fold数は現 partition (B=62w, 36/1/5/5) だと 5 folds。6 folds前提が残ると矛盾。  
- CA/DA 再スケール時の端数処理規約（四捨五入/切捨て）未定。

**3. Big-bang 削除対象の最終確認**
- 追加削除推奨:
  - one-switch/fallback 系 flag と分岐コード（CPPS一本化）
  - 「A指標とB指標を混在して主選抜する」経路
  - schema v1 前提の archive read/write 分岐（v2へ一本化）
- あなたの削除対象リストは概ね妥当。  
- ただし `factor_shadow` は「完全削除」より「metadata最小機能として縮退保持」の方が整合的（cross-pair監視で使うため）。

**4. NSGA-II + 純 CPPS（fallbackなし）への影響**
- 重要修正:
  - 「zenigame同等」を優先するなら FSM は **2-state**（push/pull）に合わせるべき。
  - 3-state以上を使うなら「fx拡張」と明記し、同等表現は外すべき。
- 推奨:
  - big-bang初版は 2-state 同等で導入し、state増加は別タスク化。

**5. 逆輸入候補（fx → zenigame）**
- `session_block_win_rate`（trade勝率より運用安定性に効く）
- HAC補正 Sharpe の標準採用
- `dataset_epoch_id` の全経路lint
- A-proxy/B-pooled 乖離の明示監視（自動 q_force 調整）

**6. synthesis 章立て最終形（12章 + 補足）**
1. Mission / 禁止事項 / 非交渉制約  
2. 設計原則（gate/search分離・worst aggregation）  
3. 全体アーキテクチャ（7段カスケード）  
4. Dataset/Epoch/Partition 契約  
5. Stage A/B/C-lite/C 仕様  
6. canonical5 と Pareto3 数式仕様  
7. NSGA-II + CPPS（FSM/CA-DA/offspring）  
8. Archive/Sieve/Warmstart/Emergency  
9. Schema v2 契約（dataset_epoch_id 必須）  
10. Observability / Audit（DSR, PBO, SPA 状態）  
11. Graduation lane（batch起動条件と判定）  
12. Big-bang migration（削除対象・移行順・ロールバック無し）  
13. Round1-10 の記録的位置づけ  
14. zenigame 実装対応表（file/line）  
15. INCONCLUSIVE と再校正計画  
16. Risk Top 5 と緩和  
17. 用語集（A-pass, progress_pass, mission_inf_gap など）  
18. TODO T901-T918 マッピング

**7. TODO T901-T918 更新（統合案）**
- T901: schema v2（dataset_epoch_id, archive_role, source_stage）  
- T902: epoch manager（24m/4w/6run）  
- T903: partition + fold generator（B=5fold固定）  
- T904: canonical5 engine（HAC Sharpe/session block）  
- T905: mission_inf_gap/slack_to_range  
- T906: Stage A（hard+q_force）  
- T907: Stage B（A-pass only, pooled主判定）  
- T908: NSGA-II core（deterministic tie-break含む）  
- T909: CPPS FSM（**2-state or fx拡張明記**）  
- T910: CA/DA archive admission/eviction  
- T911: warmstart（epoch filter, reuse/cooldown）  
- T912: failure handling（NaN/Inf/crash）  
- T913: emergency + calibrate freeze  
- T914: backtest engine拡張（session bucket/block）  
- T915: observability（A/B divergence, entropy, inflow）  
- T916: audit layer（DSR実装、PBO/SPA追加）  
- T917: graduation lane batch evaluator  
- T918: big-bang cleanup（旧path削除 + smoke）

**8. 最終 consensus（現時点）**
- 合意:
  - A/B/C/E/F/G の骨格、24m primary、lane=1、archive epoch-aware、big-bang移行
- 異論あり:
  - `FSMをmulti-stateでzenigame同等` という表現（実装事実は2-state）
  - `主選抜をA-proxyで回す` 方針（zenigame同等はB-based）
- INCONCLUSIVE:
  - PBO/SPAの導入時期
  - DST/holiday詳細境界
  - cost model の epoch再校正有無
  - primitive拡張範囲（初版でどこまで入れるか）