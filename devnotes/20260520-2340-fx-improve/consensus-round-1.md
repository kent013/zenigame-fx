**候補レバー判定（R83）**

| レバー | 判定 | 分類 | target_metric | failure_mode | causal_path | falsification | success_criterion |
|---|---|---|---|---|---|---|---|
| ① Stage B fold-CV に cost stress 前倒し | **MODIFY** | Structural | `stage_c_pass_count`、`holdout_total_pnl`、`holdout_trade_count` | Stage B pass が急減し探索停止に近づく（seed variance 増） | 上流で cost-fragile 個体を落とせれば Stage C 全滅を減らせる | 前倒し後も Stage C=0 かつ fail 主因が `trade_count<50` なら仮説棄却 | B pass を実用域で維持しつつ Stage C pass > 0 |
| ② 直近整合 selection 項追加 | **REJECT（R83では不採用）** | Structural（だが現時点で根拠不足） | `recent-fold sign consistency` と `stage_c_pass_count` の結合改善 | recency 過学習で一時改善→再現不能 | regime drift 対応を狙うが、今は drift と cost/frequency の寄与分解が未確定 | 分解前に導入すると因果不明のまま調整になる | ③で drift 優位が確認されるまで保留 |
| ③ B→C 汎化ギャップ診断の固定フォーマット化 | **APPROVE** | Structural | fail reason 分解率（cost由来 / 低頻度由来 / 混合）と再現性 | 診断が粗く意思決定に使えない | 「何が C 全滅を起こすか」を可観測化し、次の1変更を因果で選べる | 診断で主因が分離不能なら仕様見直し | B-pass 全件を reason code で分類し、主因比率を取得 |

---

**総合推薦（R83）**

- 反証可能仮説（1つ）  
`H83`: **R82のStage C全滅の主因は「短窓60日×spread1.5で取引回数が50未満へ崩れる頻度不足」であり、純粋なコスト耐性不足は二次要因。**

- 最小構造変更（1つ）  
**`Stage B→C gap diagnostic v1` の追加のみ**（ゲート閾値・GA探索空間は変更しない）。  
実装要点は「Stage C評価時に fail reason を固定コードで出す」こと。例: `COUNT_ONLY / PNL_ONLY / BOTH`、および `stress 1.0→1.5 のPnL差` と `trade_count` を必須出力。

この1変更は rejection rule に抵触せず、loop停止リスクが最小で、次サイクルで①を hard/soft どちらで入れるかを因果で決められます。

---

**cycle_focus 判断**

- **ga_improvements で確定: YES**
- ただし内容は **`R83 = 診断追加のみ`**。  
- **非採用**: live_criteria 緩和、評価期間延長、取引回数を意図的に減らす調整、recency項の先行投入。

---

**全体判定**

**CONSENSUS REACHED**