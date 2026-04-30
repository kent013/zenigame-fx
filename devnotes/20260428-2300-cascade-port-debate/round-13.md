前提を固定します。  
`canonical 5` は **gate専用**、`Pareto 3軸` は **search専用**で分離し、混ぜません。以下、反論 1〜6 への確定回答です。

1. **反論1（Sharpe_session 定義）**
採用は **(b)** です。  
ただし計算素材は session block series（= (a) の素材）を使い、最後に `bucket worst` を取ります。

- block定義: `1営業日 × 1session bucket(8h)`
- bucketごとに block PnL series `r_{b,t}` を作る
- 各bucketで Lo系（HAC）Sharpe:
  - `mu_b = mean(r_{b,t})`
  - `gamma_b(k) = lag-k 自己共分散`
  - `sigma2_LR,b = gamma_b(0) + 2 * sum_{k=1..q}(1-k/(q+1))*gamma_b(k)`  （Bartlett）
  - `SR_b = mu_b / sqrt(max(sigma2_LR,b, eps))`
- **Sharpe_session = min_b SR_b**（3 bucket の worst）

補足:
- `q` は初期 `q=5`（1週間相当ラグ）を推奨。  
- Lo (2002) の「SRのSE補正」の厳密形は実装時に要確認（INCONCLUSIVE）。運用上は上記HAC Sharpeで十分整合的。

2. **反論2（session_block_win_rate semantic）**
採用は block粒度 **(i)**、trade=0 は **0.5（neutral）** です。

- block粒度: `1営業日 × 1bucket`
- blockの勝敗:
  - `trade_count_block > 0` なら `win = 1[pnl_net_block > 0]`
  - `trade_count_block = 0` なら `win = 0.5`
- bucket別勝率: `WR_b = mean(win_{b,t})`
- **session_block_win_rate = min_b WR_b**（worst bucket）

理由:
- `0除外` は sparse戦略を過大評価しやすい
- `0を敗北` は過剰売買を誘発しやすい
- `0.5` は中立で、trade_count軸と役割分担できる

3. **反論3（mission_inf_gap 定義）**
採用は **(γ)**。対象は live_criteria の4指標のみです。  
`session_block_win_rate` は mission_inf_gap に入れません（gate専用）。

対象:
- `Sharpe_session`（下限）
- `net_pnl_after_cost`（下限）
- `max_dd`（上限）
- `trade_count`（範囲 `[L_tc, U_tc]`）

正規化shortfall:
- 下限指標 `m`: `gap_m = max(0, (L_m - v_m)/s_m)`
- 上限指標 `m`: `gap_m = max(0, (v_m - U_m)/s_m)`
- 範囲指標 `tc`: `gap_tc = max(0, (L_tc-v_tc)/s_tc, (v_tc-U_tc)/s_tc)`

**mission_inf_gap = max(gap_sharpe, gap_pnl, gap_dd, gap_tc)**

4. **反論4（trade_count range）**
`slack_to_range` を採用します（zenigame T508思想を踏襲）。

- `slack_tc(v)=`
  - `v<L`: `(v-L)/s_tc`
  - `L<=v<=U`: `min((v-L)/s_tc, (U-v)/s_tc)`
  - `v>U`: `(U-v)/s_tc`
- `gap_tc = max(0, -slack_tc(v))`

これで `min/max` の片側落ちを防げます。

5. **反論5（profit_factor の tie-break 位置）**
採用は **(d) 主体**です。  
`profit_factor` は **archive admission/eviction の同点解消**でのみ使います。

- 使う場所: archiveの lexicographic 末端タイブレーク
- 使わない場所: NSGA-II objective/crowding、Stage gate本体
- (a)(b) は「完全同値時の最終キー」としてのみ許容

6. **反論6（gate/search 分離整合）**
整合しています。これが正しいです。

- **Gate**: canonical 5 worst で pass/fail（A/B/C-lite/C）
- **Search**: Pareto 3軸（`net_pnl`, `max_dd`, `mission_inf_gap`）で進化圧
- gate fail 個体でも push phase では生存可、pull phase で feasible 側へ寄せる

反証条件:
- `corr(mission_inf_gap, gate_worst)` が恒常的に極端（例 >0.95）なら実質分離できていない
- pushで非feasibleがほぼ全滅（探索死）または pullでfeasible収束しない（収束死）なら再設計

7. **論点C 確定案（数式定義）**

- `canonical5 = {SR_session_worst, net_pnl_after_cost, max_dd, trade_count, session_block_win_rate_worst}`
- 各指標の signed slack `slack_m` を定義
  - lower: `(v-L)/s`
  - upper: `(U-v)/s`
  - range: 上記 `slack_to_range`
- `gate_worst_gap = max_m max(0, -slack_m)`  
- `gate_pass <=> gate_worst_gap == 0`

Pareto objective:
- `f1 = maximize net_pnl_after_cost`
- `f2 = minimize max_dd`
- `f3 = minimize mission_inf_gap`（4指標のみ）

関係:
- gateは `f3` と独立（ただし統計的に相関はあり得る）
- `session_block_win_rate` は gateでのみ効かせ、search objective へは入れない

---

**量的補足（Round12構造と整合）**
- Stage B pooled（5fold）: `125 blocks/bucket`  
- Stage C-lite（6w単体）: `30 blocks/bucket`  
- Stage C（12w）: `60 blocks/bucket`  
- Lo/HAC Sharpe の安定性は B pooled > C > C-lite。C-liteのSR解釈は弱め（INCONCLUSIVE寄り）で扱うのが安全です。