## Q10. 有効サンプルサイズの再検証（Q5 前提の stress test）
### 観察された事実 / 文献根拠 (Facts)
- F1: 1分足バー数（約112万）は「独立標本数」ではない。自己相関・ボラティリティクラスタリングで実効標本は減る（HAC/Newey-West 系の考え方）。
- F2: 実効標本は `n_eff = n / (1 + 2Σ_{k=1..L} ρ_k)` の近似で評価できるが、どの系列（バー収益・戦略収益・トレード損益）で計るかで値が大きく変わる。
- F3: 戦略評価では bar-level より trade-level の有効標本（`n_trades_eff`）が意思決定に直結する。Bailey & López de Prado 系でも「試行回数と有効観測数」の扱いが核心（2014, DSR/PBO 関連）。
- F4: Q5 の `n_eff≈250` は「日次独立近似」に寄りすぎで、intraday 戦略には過度に保守的だった可能性が高い。

### 解釈・推論 (Interpretations)
- I1 (from F1-F4): `n_eff` は単一値でなくレンジ運用が妥当。実務推奨は  
  `n_eff_used = min(n_eff_strategy_returns, n_trades_eff)`。  
- I2 (from F2, F3): 本件（3年・intraday）では現実的レンジは **1,000〜10,000** が第一候補。  
  `ln(n_eff)` は `6.9〜9.2`（250 の 5.52 より上振れ）。  
- I3 (from F4): Q5 の α=0.03-0.08 は「破綻」ではないが、`n_eff` 連動に更新すべき。  
  例: `α(n)=α_ref*sqrt(ln(n_eff)/ln(1000))`, `α_ref=0.05`, clamp `[0.02, 0.10]`。
- 反証可能性(I1-I3): 実測 `n_eff` が 300 未満または 30,000 超に偏るなら、上記レンジ前提は棄却。

### 暫定判定 (Verdict)
- **Q5 の数値は修正必要（Round 2 より Round 3 を優先）**。  
- ただし方針（複雑度制約必須）は維持。修正点は「`n_eff=250` 固定」ではなく「`n_eff` 推定レンジ連動」。

---

## Q11. DSR/PBO/Reality Check 実装コストの現実性
### 観察された事実 / 文献根拠 (Facts)
- F1: DSR は入力が比較的少なく、実装コストは軽い（Bailey & López de Prado, 2014）。
- F2: PBO の CSCV を全候補にフル適用すると計算爆発しやすい。`S=8` で 70 組合せは妥当だが、候補圧縮なしは重い（Bailey et al., 2014）。
- F3: Reality Check / SPA はブートストラップが重い（White, 2000; Hansen, 2005）。ただし候補を絞れば実用化可能。
- F4: 「再バックテストを毎回回す」設計が重いので、fold別PnL行列をキャッシュして統計だけ後段計算するのが定石。

### 解釈・推論 (Interpretations)
- I1 (from F1): DSR は **Phase 2 から必須**で現実的。`n_trials` は「Run 全評価数」ではなく「有効独立試行数」に圧縮推定（重複除去後候補数×係数）。
- I2 (from F2, F4): PBO は全候補でなく **top-M（例20）** に限定し、CSCV はキャッシュ行列で計算すべき。これで実装可能域に入る。
- I3 (from F3): RC/SPA は Phase 4 で十分。Phase 2-3 は block bootstrap CI + DSR/PBO-lite で代替可能。
- 反証可能性(I1-I3): top-M 化しても wall-clock が許容超過なら、RC/SPA hard gate は縮小または定期バッチ化が必要。

### 暫定判定 (Verdict)
- フル実装断念は不要。**段階実装で現実化可能**。  
- 最小セット:
1. Phase 2: DSR + fold符号反転 + block bootstrap CI  
2. Phase 3: PBO-lite（top-M, `S=6~8`）  
3. Phase 4: RC/SPA（`B=1000` 標準、重要判定 `B=3000`）  

---

## Q12. max_clause=1 開始は実質フラット化か
### 観察された事実 / 文献根拠 (Facts)
- F1: `max_clause=1` だと表面的には単一式に見えるが、内部を `directional` と `local_gate` に分離していれば表現バイアスは異なる。
- F2: フラット4式は entry/exit を独立に進化させるため、矛盾条件・過度自由度が発生しやすい。
- F3: Clause系は `composite score` と状態機械（閾値/hysteresis/time-stop）で売買を制御しやすい。
- F4: 探索空間比較は「同計算予算」定義がないと不公平。評価回数だけでなく式サイズ差も考慮が必要。

### 解釈・推論 (Interpretations)
- I1 (from F1-F3): `max_clause=1` は「完全フラット同値」ではない。  
  同値回避の必須要素: `Σ|w|` 正規化、gate bounded化、hysteresis (`θ_on > θ_off`)。
- I2 (from F4): 同計算予算は **評価回数×平均ノード数** の積で合わせるのが妥当。  
  例: `BudgetCU = eval_count * mean_nodes` を各設定で一致。
- I3 (from F2, F3): `max_clause=1` で十分高性能なら「Clause構造無意味」ではなく「追加Clause不要」が結論。設計は生きる。
- 反証可能性(I1-I3): `max_clause=2` が同BudgetCUで OOS 指標を改善できず、active_clause が恒常的に1なら、上限2以上は凍結すべき。

### 暫定判定 (Verdict)
- `max_clause=1` 開始は妥当。ただし以下を初日実装必須:
1. directional/gate 分離
2. 正規化付き重み合成
3. 閾値ヒステリシス
4. session/time-stop/コスト制約  
- これを満たさない `max_clause=1` は実質フラット化であり、採用不可。

---

## Q13. (ii-lite) shadow → hard gate 化の判定基準
### 観察された事実 / 文献根拠 (Facts)
- F1: shadow は「落とす」ためではなく「予測力検証」のためにある。通過率だけでは有効性判定できない。
- F2: gate の良し悪しは calibration（通過率の健全性）と discrimination（通過群が将来良いか）で評価すべき。
- F3: hard 化後の劣化リスクに備え、rollback ルールを事前固定しないと事後最適化になる。

### 解釈・推論 (Interpretations)
- I1 (from F1, F2): hard 化条件は「安定性 + 予測力」の同時充足が必要。  
- I2 (from F3): hard 化失敗時は即 shadow へ戻す自動トリガーが必要。
- 反証可能性(I1-I2): 長期 shadow で discrimination が出ないなら、hard 化せず常設 shadow または仕様改定。

### 暫定判定 (Verdict)
- hard 化判定（提案）:
1. ウォームアップ: **30 run 以上** かつ **各target 5 run 以上**。  
2. 通過率: 直近20 run の median が **30-70%**、rolling std **<=15pp**。  
3. 予測力: shadow通過群の事後OOS Sharpe中央値が不通過群より **+0.15以上**、検定 `p<0.10`（小標本想定）。  
- rollback:
1. hard化後10 run 以内に target Sharpe が shadow期基準比 **25%以上低下** が2窓連続。  
2. または gate 通過率が **<10%** または **>90%** に10 run 連続。  
  上記で shadow に戻す。
- 判定不能時:
1. 60 run でも discrimination 不成立なら **永久shadow** で運用し、hard化は凍結。

---

## Q14. 6ペアの選択戦略（アンカー定義の具体化）
### 観察された事実 / 文献根拠 (Facts)
- F1: 流動性・スプレッド品質は EUR_USD, USD_JPY が高く、USD_ZAR は構造が異なる（実務的に既知）。
- F2: アンカーは「同基軸/同決済」の情報共有を狙うが、6ペア集合では完全対称に組めない。
- F3: USD_ZAR は高ボラ・広スプレッドで、共通因子共有より個別要因の比重が大きい。
- F4: アンカー設計が有効なら、通過判定と将来OOSの相関が改善するはず。

### 解釈・推論 (Interpretations)
- I1 (from F1-F3): 初期は anchor 3（target+2）で十分。hard監査で全6に拡張が妥当。
- I2 (from F1, F3): improve-cycle 主力は `EUR_USD -> USD_JPY -> EUR_JPY -> AUD_JPY -> USD_CAD -> USD_ZAR` の順が合理的。
- I3 (from F4): アンカー感度が低ければ設計簡素化できる（全6固定 or ルール簡略化）。
- 反証可能性(I1-I3): アンカー変更で OOS 差がほぼゼロ（例 `|ΔSharpe|<0.05`）なら、アンカー最適化は過剰。

### 暫定判定 (Verdict)
- target別アンカー（提案）:
1. EUR_JPY: {EUR_USD, USD_JPY}
2. USD_JPY: {USD_CAD, EUR_JPY}
3. EUR_USD: {EUR_JPY, USD_CAD}
4. AUD_JPY: {USD_JPY, EUR_USD}
5. USD_CAD: {USD_JPY, EUR_USD}
6. USD_ZAR: {USD_CAD, USD_JPY}
- USD_ZAR 方針: **除外しない**。ただし初期は主力から外し、後段 robustness/stress 用に使う。

---

## 【最終仕様確定】

### A. ゲノム構造仕様
- max_clause:
1. 初期値: `1`（ウォームアップ 10 run）
2. 運用標準: `2`
3. 上限: `3`（昇格試験合格時のみ）
- max_depth: `5`（合成式深さ）
- 必須内部構造:
1. directional signal 加重和（`Σ w_i x_i / Σ|w_i|`）
2. local_gate（`[0,1]` に有界化、sigmoid系）
3. clause_weight 正規化合成
4. composite score のヒステリシス閾値（entry/exit）
5. session close/time_stop
6. spread/slippage フィルタ
7. long/short 対称制御（パラメータは分離可）

### B. Stage A/B/C 仕様
- Stage A:
1. 期間: 直近 `60` 営業日（高速スクリーニング）
2. 通過率目標: `15%`（10-20% 許容）
3. ペナルティ: `α_A = 0.03`（`n_eff` 連動で 0.02-0.05）
- Stage B:
1. 期間: 過去 `18` か月
2. WF: train `120` 日 / test `20` 日 / step `20` 日 / embargo `1` 日
3. 通過基準: median OOS Sharpe `>=0.20`、正のfold比率 `>=60%`、DSR `>=0`（初期は monitor 可）
- Stage C:
1. holdout + live_criteria 判定
2. 追加チェック: (ii-lite) gate、spread×1.5 stress、session跨ぎ禁止遵守、trade数レンジ（50-5000）

### C. (ii-lite) Cross-pair 評価仕様
- 評価ペア集合:
1. 通常: target + アンカー2（Q14の表）
2. 監査: 週次または昇格時に全6ペア
- 集約関数:
1. 主目的: `F = mean(Sharpe_i) - 0.5*std(Sharpe_i)`
2. 監査: `min(Sharpe_i)`、流動性重み付き mean
- 通過基準:
1. `Sharpe_target_cross >= 0.8 * Sharpe_target_single`
2. `mean Sharpe_cross >= 0.15`
3. `min Sharpe_cross >= -0.20`
- shadow→hard 化:
1. 30 run 以上 + 各target 5 run 以上
2. 通過率 median 30-70%、std <=15pp
3. 通過群の事後OOS優位 +0.15、`p<0.10`

### D. 統計検定インフラ
- 必須（最小セット）:
1. DSR
2. fold符号反転率
3. block bootstrap による Sharpe CI
- 後回し可:
1. RC/SPA フル実装（Phase 4）
- 簡易代替:
1. PBO-lite（top-M=20、`S=6~8`）
2. RC前の監視は bootstrap p-value で代替

### E. Phase 別実装スコープ確定
- Phase 2 MVP（必須）:
1. Clauseエンジン（max_clause=1開始）
2. Stage A/B/C 最小パイプライン
3. archive（instrument, complexity, gate metrics）
4. (ii-lite) shadow 評価
5. DSR + sign反転 + bootstrap CI
- Phase 3:
1. max_clause=2 標準化、3の昇格試験
2. 共通因子（DSL/評価フィルタ）段階導入
3. PBO-lite 実装
- Phase 4:
1. (ii-lite) hard gate 化
2. RC/SPA
3. rollback 自動化
4. (b)×(i)→(ii) 移行トリガー自動判定

### F. 移行トリガー（最終版）
- (b)×(i) → (ii) hard 移行:
1. `PBO>0.5` AND (`DSR<0` 3連続 OR fold負比率>=0.4)
2. または `RC/SPA p>0.10` 3連続 + DSR改善なし
- shadow/hard/rollback:
1. shadow開始: Run 1 から常時
2. hard化: C項の3条件を満たした時
3. rollback: Sharpe 25%低下2窓連続、または通過率崩壊（<10% or >90%）
- ウォームアップ Run 数:
1. hard判定開始: `max(30 run, 各pair 5 run)`

### G. 残課題（実測でしか決まらない項目）
- `n_eff` の実測レンジ（bar/trade 両軸）
- α の最終キャリブレーション（`n_eff` 連動係数）
- アンカー感度（pairごとの効果差）
- USD_ZAR の実運用コストモデル妥当性
- RC/SPA の計算予算上限（実行時間基準）

以上を最終仕様として実装へ渡せる粒度です。