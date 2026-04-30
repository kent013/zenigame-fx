**1. 適用順序の判定**

**推奨: (II) `Phase A並行 + B/C並行 + D + E + F`**

理由:
- 24ヶ月データ取得(A-1)は待ち時間が発生しやすく、直列(I)だと遊休が大きい。
- B/Cはインターフェース先行で実装可能（実データは後で差し替え）。
- IIIは統合リスクが高く、IVはEの前提（Dの出力契約）が不安定。

反証条件:
- A-1が即日完了し、データ待ちが実質ゼロなら(I)との差は小さい。
- B/Cを並行実装してもI/F契約が何度も崩れるなら、むしろ(I)の方が速い。

---

**2. Phase内の依存グラフ（要点）**

必須依存:
- `A-1 -> A-4 -> F-1`
- `B-1 -> B-2 -> C-1/C-2/C-3/C-4`
- `B-3 -> C-1/C-2/C-3/C-4`
- `B-4 -> B-5 -> C-2/C-3`
- `B-1/B-2/B-5 -> D-1`
- `D-1 -> D-2 -> D-3/D-4`
- `C-1..C-4 + D-1..D-4 -> E-2`
- `E-1 -> E-2 -> E-3 -> E-4`
- `E-2/E-3 -> E-5`
- `E-2/E-4 -> E-6`
- `A/B/C/D/E完了 -> F-1`
- `F-1 -> F-2 -> F-3 -> F-4`

並行可能:
- `A-2/A-3` は `A-1` と並行
- `B-6` は `C-4` と並行（最終統合はC-4時点）
- `E-7` は `E-1..E-4` の後半と並行

---

**3. Critical path（wall-time最小化）**

推定（1人換算、実装+テスト）:
- A: 2〜4日（A-1はINCONCLUSIVE: 取得元依存）
- B: 3〜5日
- C: 4〜6日
- D: 3〜5日
- E: 4〜6日
- F: 2〜3日

合計:
- 直列(I): **18〜29日**
- 推奨(II): **12〜19日**（A待ちをB/Cで吸収できる前提）

実効クリティカルパス:
`A-1 -> A-4 -> C-2 -> D-1 -> D-2 -> E-2 -> E-3 -> F-1`

---

**4. risk-ordered top 5（phase内項目）**

1. `B-1/B-2`（denom_m・log_pf・max_dd_adj整合）  
緩和: 指標ごとに単調性テスト（閾値超過でgapが必ず増える）を先に自動化。

2. `C-2`（Stage B WF + session share運用）  
緩和: `total_trades_B<30 => INCONCLUSIVE` 分岐を先に実装し、誤判定を止める。

3. `D-1/D-2`（3軸Pareto + one-switch）  
緩和: 単目的margin_infのA/Bテストフラグを残し、退避経路を確保。

4. `E-3`（eviction制約の衝突）  
緩和: 事前に「制約充足チェック関数」を作り、違反時の緩和順を固定。

5. `E-6`（calibrate凍結窓とΔ制限）  
緩和: 更新イベントを4runごとに限定し、更新ログを必須化。

---

**5. 最小スマートな smoke 構成（F-1最短到達）**

最小実装範囲:
- A: `A-1, A-4`
- B: `B-1, B-2, B-3, B-4, B-5`
- C: `C-1, C-2, C-3, C-4`（旧ロジック削除は後回し可）
- D: `D-1, D-2, D-3`（D-4は簡易固定でも可）
- E: `E-1, E-2, E-3`（E-4は初回runでno-op許容、E-5/6/7は後追い）
- F: `F-1`

これで「1 run が端から端まで回る」ことを最速確認できます。

---

**6. fail-fast 設計の保証（Phase gate）**

- Phase A gate: 24ヶ月データで HARD_REQUIRED 欠損ゼロ、coverage基準達成。
- Phase B gate: canonical 5 のgap計算が単体テストで全指標単調。
- Phase C gate: A/B/C-lite/C の入出力契約固定、1世代分を例外なく通過。
- Phase D gate: feasible_ratio と switch 判定ログが世代ごとに出る。
- Phase E gate: archive制約違反ゼロ、warmstart 8体選定成功率100%。
- Phase F gate: 1 run完走、FM1〜FM5の観測ログが揃う。

---

**7. Phase完了基準（DoD）**

- Phase A DoD: preflightが24ヶ月前提でpass、holdout除外集計が可能。
- Phase B DoD: `margin_inf` と `denom_m` 仕様固定、再現可能な計算結果。
- Phase C DoD: 新Stageロジックのみで選抜が実行される（旧閾値経路未使用）。
- Phase D DoD: 3軸Pareto + push/pullがrun中に機能し、fallbackフラグが有効。
- Phase E DoD: inflow/eviction/warmstart/cooldownが一巡し、制約矛盾なし。
- Phase F DoD: 5 run連続でクラッシュなし、archive健全性メトリクスが出る。

---

INCONCLUSIVE:
- A-1の実データ取得時間と欠損率は実測まで確定不能。
- max_workers=2での実行時間は、初回smoke後のプロファイルで再見積もりが必要。