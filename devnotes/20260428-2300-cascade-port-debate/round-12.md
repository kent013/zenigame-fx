C9（反証先行）で結論を先に出します。  
Round 11 の `70w Stage B + 6fold` は、`Stage A=recent 8w` を同時に満たすと必ず overlap が出るため、そのままでは不採用です。  
Round 12 の B 最終案は、`Stage B評価区間を 62w に縮めて 5fold` にし、`Stage A 8w を非重複で分離` します。

---

1. **反論1（Stage A 位置）**
採用は **(d) の強化版** です。

- 旧 `Stage B zone 70w` を内部的に分割  
  - `Stage B eval = 62w`  
  - `Stage A recent proxy = 8w`  
- これで `Stage A` と `Stage B test` の overlap を **0** にします。

時系列配置（24m=104w）:
- `w00-w62`: Stage B eval
- `w62-w70`: Stage A (8w)
- `w70-w71`: embargo
- `w71-w77`: C-lite1
- `w77-w78`: embargo
- `w78-w84`: C-lite2
- `w84-w85`: embargo
- `w85-w91`: C-lite3
- `w91-w92`: embargo
- `w92-w104`: Stage C (12w)

補足:
- Stage順は A→B だが、時間は B→A（A がより recent）。  
- これは lookahead ではなく「recent viability を先に見る設計」。  
- 反証条件: A-pass 高いのに B-pass が長期で極端に低い（例: <5%）なら A を過度に recent 偏重と判定し、A窓の再設計を行う。

---

2. **反論2（test=5w の量的根拠）**
あなたの指摘どおり、私の前回「35 blocks/bucket」は `7日換算` で、実運用の独立サンプルとしては過大でした。修正します。

前提（C4）:
- 24/7 fill でも、週末は実質非取引で独立情報が薄い
- 有効営業日を `5日/週` で数える

計算:
- 1 fold test = `5w = 25営業日`
- session bucket = 3（Tokyo/London/NY）
- `session block` を「1営業日×1bucket=1 block」とすると  
  - **per bucket per fold = 25 blocks**
  - 5fold 集約で **125 blocks/bucket**
  - 全bucket合計 **375 blocks**

結論:
- fold単体の per bucket `n=25` は C7 的に弱い
- しかし 5fold pooled の per bucket `n=125` は十分

---

3. **反論3（fold単位 vs 全fold集約）**
採用は **(ii) 全fold集約を主判定**。  
ただし fold情報を捨てず、二層判定にします。

- 主判定: 5fold の test を時系列連結した pooled OOS で canonical 5 worst aggregation
- 補助判定: foldごとの fail-fast/invariant は個別に必須通過（1 foldでも infeasible なら即fail）

理由:
- Lo (2002): serial correlation 下で比率指標の分散推定に注意が必要
- C7: fold単体 bucket n=25 で win-rate/Sharpe を hard 判定すると不安定
- Tashman (2000): rolling-origin は複数 test の統合評価が本筋

---

4. **反論4（rolling vs fixed dataset）**
採用は **epoch-rolling 24m**（固定でも毎run rollingでもない中間）。

- `window_length = 104w`
- `roll_stride = 4w`（月次相当）
- 同一epoch内は fixed
- `max_runs_per_epoch` を上限設定（例 6）して、使い回し過多を防止

理由:
- fixed 24m を何十runも回すと Bailey 系の selection inflation/PBO リスク増
- 毎run rolling は比較不能化と calibrate-gate history 汚染を招く
- epoch固定なら比較可能性と新陳代謝を両立

必須設計:
- calibrate-gate history 適用キーに `dataset_epoch_id` を含める（epoch跨ぎ再利用禁止）

---

5. **反論5（Stage C rotation）**
**tier1 では明示 rotation は当面不採用**、代わりに epoch-rolling で実質回転させます。

- 同一epoch内: Stage C は固定 12w（評価基準を固定）
- epoch更新ごと（4wシフト）: Stage C も4wずつ移動し、結果として rotation 相当

理由:
- 現 partition で 3×C-lite(6w) と StageA(8w) を維持すると、C用に追加poolを確保する余地が小さい
- 複雑化（禁止事項5）より、まず epoch-rolling + run上限制御が筋

INCONCLUSIVE:
- 将来、同一epoch内 run 密度が高すぎる場合は T454型の明示 rotation を再導入検討

---

6. **反論6（Stage A trade_count 評価）**
採用は **(a) trade_rate**（絶対 trade_count は使わない）。

- Stage A は 8w の proxy。ここで `trade_count_min=50` のような絶対値判定は不適切
- 評価軸を `trade_rate = trades / trading_day` に置換
- hard floor は「ゼロ取引除外」程度に限定（例: `trades>=2`）
- 本格的な trade_count 適合（live_criteria）は Stage B pooled 以降で判定

理由:
- 8w は短く、絶対件数判定は window長依存で歪む
- 原則1（絶対閾値は破綻排除のみ）に整合

---

7. **論点B 確定案（Round 12）**

**Partition（24m=104w）**
- `B_eval 62w` + `A_recent 8w` + `emb 1w` + `C-lite 6w` + `emb 1w` + `C-lite 6w` + `emb 1w` + `C-lite 6w` + `emb 1w` + `C 12w`

**Stage B folds**
- `train 36w / embargo 1w / test 5w / step 5w`
- fold数 = 5（test disjoint）

**判定レベル**
- Stage A: recent proxy、`trade_rate`中心（軽量）
- Stage B: 5fold pooled canonical5（主判定）+ fold fail-fast（補助）
- C-lite: 6w×3 disjoint
- Stage C: final holdout 12w contiguous

**量的基準（session block, 営業日5/週換算）**
- B fold単体: 25 blocks/bucket（C7注意）
- B pooled(5fold): 125 blocks/bucket
- C-lite単体(6w): 30 blocks/bucket
- C本番(12w): 60 blocks/bucket

---

**参照論点（学術）**
- Lo (2002): Sharpe の標準誤差は自己相関に依存、単純年率化は危険
- Tashman (2000): rolling-origin による複数OOS評価の重要性
- Bailey et al. (PBO/DSR): 固定サンプルの反復最適化は偽発見率を押し上げる

---

INCONCLUSIVE を明示:
- `roll_stride=4w` と `max_runs_per_epoch=6` の最適値は F-1 smoke 実測で最終化
- Stage C 明示rotationの要否は、epoch内 run密度と C-pass 劣化パターンの観測後に確定