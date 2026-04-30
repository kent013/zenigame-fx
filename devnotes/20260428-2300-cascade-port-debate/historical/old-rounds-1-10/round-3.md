**前提（C9: 反証先行）**
- まず崩しに行く仮説は「FX固有指標を worst に増やすほど selection が良くなる」です。  
- `pop=40` では、worst 対象を増やすと通過率が急減し、forced-pass 依存になって判定が不安定化しやすいです。  
- 近似で各指標の単独通過率を `p=0.6` と置くと、同時通過は `p^m`。`m=4: 0.13 (期待5.2体) / m=5: 0.08 (3.1体) / m=6: 0.05 (1.9体)`。6指標化は extinction リスクが高いです。

---

### 1. canonical 5 vs 4 vs 5(置換) の結論

**結論: (c) を採用**  
`win_rate` を外し、**profit_factor に置換した canonical 5**で行きます。  
最終形は `sharpe / net_return / max_dd / trade_count / profit_factor`。

**理由**
- (a) canonical 4 は mission faithful だが、PnL形状（損益非対称）を拾う軸が弱い。
- (b) win_rate 維持は、単一通貨ペアでは「小利多勝・大損少数」を見逃しやすい。
- (d) expectancy（提示式）は net_pnl と冗長で、独立軸として弱い。
- profit_factor は Sharpe の補完軸として機能しやすい（歪度・損益比の情報を追加）。

**反証条件**
- profit_factor を入れても Stage C の live_criteria 達成率が上がらず、run間再現性も改善しない。
- 逆に win_rate を戻した方が cross-pair shadow で安定する。

---

### 2. spread_consumption_ratio の結論（α/β/γ/δ）

**結論: (γ) tie-break を採用**（(δ) monitor は併用）  
`hard/soft constraint` にはしません。

**理由**
- 絶対制約「spread を fitness に反映」は、**既に net_return/Sharpe（コスト控除後）で満たす**。  
- ここに hard/soft を重ねると、禁止6（取引回数削減で見かけ改善）を誘発しやすい。
- tie-break なら、同ランク内でコスト効率を優先しつつ主目的を壊しにくい。

**禁止6との両立設計**
- tie-break は `trade_count` が canonical 条件を満たす個体同士でのみ適用。
- lexicographic順は `worst_gap -> trade_count_gap -> spread_consumption_ratio`。  
  先に取引回数健全性を固定してから spread を使う。

**反証条件**
- tie-break では spread劣化個体が残り、Stage C spread stress 失敗率が高止まりする。
- その場合のみ soft constraint への昇格を再検討（hard は最後）。

---

### 3. session_close_drop_count の結論

**結論: invariant breach として fail-fast**  
`session_close_drop_count > 0` は `is_feasible=False`。

**理由**
- イントラデイ前提に対する直接違反シグナル。  
- これは「性能指標」ではなく「設計制約の順守」問題。

**注意（C1）**
- まず実装定義を固定すること。  
  指標が「正常な日次クローズ処理」まで数えているなら定義バグなので先に計測定義を修正。

**反証条件**
- 指標定義の監査で、`drop_count` が純粋な違反でなく正常処理カウントを含むと判明した場合。

---

### 4. negative_equity_drop_open_count の結論

**結論: canonical には昇格しない。invariant/hard constraint 側に置く。**  
第一候補は **fail-fast（>0で infeasible）**。  
実装ノイズ懸念があるなら暫定で `ratio = negative_equity_drop_open_count / max(1, trade_count)` に上限を置く hard constraint。

**理由**
- これは「収益性」ではなく「実行可能性・資本制約」の破綻指標。  
- canonical 化すると simulator/accounting の癖を最適化する危険がある。
- 9311件級はチューニング対象でなく排除対象。

**反証条件**
- 指標が実際には資本破綻でなく、会計タイミング由来の擬似イベントだと監査で判明した場合。
- fail-fast で探索が全滅する場合は、定義修正または閾値緩和ではなく資本/約定モデルを先に再設計。

---

### 5. cross-pair shadow の結論

**結論: Stage C/AS の validation axis で確定**  
Stage A/B/C-lite の selection objective には入れません。

**理由**
- 早段で入れると単一ペアのedge探索を弱め、計算負荷も増える。  
- 最終妥当性チェックとして分離するのが役割整合的。

**反証条件**
- Stage C で cross-pair 落ちが常態化し、A/B/C-lite の選抜と最終目的が恒常的に乖離する場合。  
  そのときのみ C-lite 後段への限定導入を再検討。

---

### 6. Objective Taxonomy 確定表

| 指標 | 最終分類 | 適用ステージ | 備考 |
|---|---|---|---|
| sharpe | `worst_aggregation` | A/B/C-lite | canonical |
| net_return (cost/swap反映後) | `worst_aggregation` | A/B/C-lite | canonical |
| max_drawdown | `worst_aggregation` | A/B/C-lite | canonical |
| trade_count | `worst_aggregation` | A/B/C-lite | canonical（範囲条件） |
| profit_factor (win_rate置換) | `worst_aggregation` | A/B/C-lite | canonical 5番目 |
| win_rate | `monitor_only` | A/B/C-lite/AS | 参考値に降格 |
| spread_consumption_ratio | `tie_break` + `monitor_only` | A/B/C-lite | hard/softには入れない |
| session_close_drop_count | `invariant_fail_fast` | 全ステージ | `>0` で infeasible |
| negative_equity_drop_open_count | `invariant_fail_fast`（暫定で hard_constraint 可） | 全ステージ | 原則 `>0` で infeasible |
| spread stress pass/fail | `validation_axis` | C | 最終実運用耐性 |
| cross-pair shadow 指標 | `validation_axis` | C/AS | 早段 objective へは入れない |
| live_criteria 4指標 | `hard_constraint` | C | mission gate |

---

この確定案で重要なのは、**収益性の序列（worst）と実行可能性の規約（invariant/hard）を混ぜない**ことです。混ぜると、禁止6と同時に selection の因果が壊れます。次ラウンドはこの taxonomy を前提に、`gap正規化式` と `tie-break順序` の数式を固定すると実装に落とし込めます。