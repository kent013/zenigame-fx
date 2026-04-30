**結論サマリ**
- Gap1: **(a) threshold-based** を採用（ただし horizon補正と `log_pf` 安定化を追加）。
- Gap2: **別案採用**（Stage B session-awareは維持、`trade_count` は全体評価、session別は比率/有効サンプルで扱う）。
- Gap3: **(β) 加重和** を採用（ハード制約の後段でソフト順序付け）。
- Gap4: **(iii) moving-average 条件** を採用（`mission=0` 3連続を前提）。
- Gap5: **(b) 3 Run 凍結** を採用（更新幅制限つき）。

---

### 1. Gap1（denom_m）
**採用: (a) threshold-based**

`scale-based (b)` は runごとに分母が動き、同じ個体でも順位が変わりやすい。  
`hybrid (c)` は柔軟だが、今は可動要素を増やすデメリットが大きい。  
よって threshold固定を基準に、期間差だけを決定論補正します。

**最終式（signed, 大きいほど良い）**
- `gap_sharpe = (sharpe_ann - S_min) / max(|S_min|, 1e-6)`
- `gap_net = (net_return - R_min) / max(|R_min|, 1e-6)`  
  `R_min = total_pnl_min / initial_cash` に統一
- `gap_dd = (DD_max_adj - max_dd) / max(DD_max_adj, 1e-6)`  
  `DD_max_adj = DD_60 * sqrt(T_days/60)`
- `gap_tc = slack_to_range(tc, [TC_min, TC_max]) / max(TC_min, 1e-6)`
- `gap_pf = (log_pf - 0.0) / log(2.0)`  
  `log_pf = log((GP+1e-6)/(GL+1e-6))`、clip推奨 `[-2, 2]`

`margin_inf = min(gap_sharpe, gap_net, gap_dd, gap_tc, gap_pf)`

**定量根拠**
- 分母固定で run間比較可能。
- `log(2)` 分母は「PF=2で gap=1」を意味し、解釈しやすい。

---

### 2. Gap2（session bucket trade_count）
**採用: Stage B session-awareを維持 + trade_count評価を再設計（別案）**

20日fold単位で bucket別絶対件数を要求すると疎すぎます。  
`trade_count` は **bucket別絶対閾値から外し**、次で扱います。

**最終設計**
- Stage B の `trade_count` は fold群合算（全session）で判定。
- session別は `coverage/share` 指標として扱う:
  - `share_i = trades_i / max(total_trades,1)`
  - 最低カバレッジ `share_i >= 0.15`（3bucketで極端偏在を防ぐ）
- `total_trades_B < 30` は session-aware 判定を `INCONCLUSIVE` にして重み再正規化。

**定量根拠**
- `F=6` folds なら test合計120日。  
  `0.3 trades/day` で total約36、sessionあたり約12。  
  絶対15件は厳しいが、share判定なら安定。

---

### 3. Gap3（eviction_score）
**採用: (β) 加重和**

`(γ) 乗算`は1因子が低いと過剰に0近傍へ潰れやすい。  
`(δ) 減算`はスケール依存が強く係数解釈が不安定。  
加重和が最も堅牢でデバッグ可能です。

**最終式（0〜1正規化後）**
- `score = 0.70*quality + 0.15*recency + 0.15*rarity + 0.05*cross_pair_bonus`
- 先にハード制約適用（`per_run_max/pattern_max_share/recency_floor`）
- その後 `score` 最低を evict

**補足**
- 係数は初期値。Round 9以降で固定のまま観測し、すぐはチューニングしない。

---

### 4. Gap4（緊急モード）
**採用: (iii) moving-average 条件**

`(ii)` 単調悪化は厳しすぎ、ノイズで非発動になりやすい。  
`(iii)` はトレンド検出として頑健。

**発動条件**
- `mission_pass == 0` が3 run連続
- かつ `MA3(best_margin_inf) < MA6(best_margin_inf) - 0.05`

**解除条件**
- 次runで `progress_pass >= 2` または `best_margin_inf` が `MA6` 以上に回復

**緊急アクション**
- 1 runのみ `warmstart_share: 0.20 -> 0.35`（その後自動復帰）

---

### 5. Gap5（calibrate凍結窓）
**採用: (b) 短期凍結 3 Run**

毎run更新は double counting を起こしやすい。  
3 run凍結なら、archive流入（約30体）とwarmstart反映を見てから更新できる。

**最終運用**
- `q_force_base`（強制通過ベース率）は3 run固定
- 4 run目にのみ更新
- 更新幅制限 `|Δq_force_base| <= 0.03`

---

## 6. 更新後の確定案（Round 8 反映）

| 項目 | 最終値 |
|---|---|
| canonical 5 | `sharpe_ann / net_return / max_dd / trade_count / log_pf` |
| margin_inf 分母 | threshold-based固定（上式） |
| Stage B session運用 | session-aware維持、trade_countは全体判定、sessionはshare評価 |
| Stage B low-sample | `total_trades_B < 30` は session評価 `INCONCLUSIVE` |
| eviction_score | 加重和 `0.70Q + 0.15R + 0.15D + 0.05X` |
| evictionハード | `per_run_max=10`, `pattern_max_share=0.25`, `recency_floor=12` |
| bypass | `K=clamp(10-n_mission-n_progress,2,4)` + 品質床 |
| 緊急モード発動 | `mission=0` 3連続 + `MA3(best_margin_inf) < MA6 - 0.05` |
| 緊急モード動作 | `warmstart_share 0.20 -> 0.35` を1 runのみ |
| calibrate凍結窓 | 3 run固定、4 run目更新、`Δ<=0.03` |

---

**INCONCLUSIVE（明示）**
- `total_trades_B>=30` が常時満たせるかは実データ依存。  
  満たせないrunが多い場合、Stage B の fold数/期間再設計が必要です。  
- `eviction_score` 係数は現時点で仮固定。まずは変更せず観測が必要です。