**Round 1 からの更新**
- 維持: `フル案(A')` は重すぎる、`one-switch` は有効、`exec_score系をPareto軸に乗せない`。
- 更新: 論点1/2/4確定後は、`中間案(B'')`をさらに明確化。  
  **採用方針は「B''（3軸Pareto + one-switch）+ CA/DAは外部archiveで分離」**です。

---

### 1. 反論1（3軸Pareto vs 単目的）への回答

**採用: (B'')**  
`(E)` 単目的 `margin_inf` のみは不採用。

**根拠**
- `margin_inf` は worst 指標が切り替わると勾配方向が飛びやすく、単目的だと探索が一点集中しやすい。
- `net/dd` を残すと、feasible 近傍での「利益増 vs DD抑制」の方向性が明示される。
- `n=40` の3目的で非劣解集合サイズは経験的に数体〜10体程度を維持しやすく、crowding と合わせて多様性を残せる。単目的だと毎世代トップ1周辺に圧縮されやすい。

**反証条件**
- 3軸化しても rank1 多様性が増えず、`margin_inf` 単目的と OOS 成績・再現性が同等以下なら `(E)` へ縮退再検討。

---

### 2. 反論2（CA/DA）への回答

**採用: (iii)**  
`CA/DA 分離は有効`だが、**進化母集団を分割しない**。  
`pop=40` は維持し、`external archive` を CA/DA 分離する。

**判断**
- (i) `pop=40` をそのまま CA20/DA20 に分けるのは薄い。
- (ii) `pop=60` は計算1.5倍で `max_workers=2` では運用速度を落としやすい。
- (iii) 外部archive分離なら small feasible region 対策（Li et al. の意図）を取り込みつつ、計算増を抑えられる。

**推奨値**
- `archive_total=100`
- `CA=50`, `DA=50`（初期）
- 1 run あたり archive 流入 `8〜12` 体

**反証条件**
- CA/DA 分離しても feasible 発見率が上がらず、DA が実質ノイズ保管庫になる場合は単一archiveへ戻す。

---

### 3. 反論3（Push/Pull switch）への回答

**採用: (a) feasible_ratio 条件**（`b` は安全弁として併用、`c` は不採用）

**理由**
- (a) は run 難易度に対してスケールフリーで頑健。
- (b) 固定世代切替は早すぎ/遅すぎの両リスク。
- (c) `margin_inf` 閾値は正規化変更に敏感で壊れやすい。

**具体**
- `switch if feasible_ratio_ema >= 0.15 for 2 consecutive generations`
- 安全弁: `gen >= 10` なら強制 pull へ
- one-switch（再遷移なし）

**反証条件**
- feasible_ratio ベースで切替が遅延し、終盤でも infeasible が多数残る。
- 逆に早すぎて探索多様性が崩れる。

---

### 4. 反論4（exec_floor転用）への回答

**採用: 部分採用（ii） + 限定採用（iii）**
- (ii) `top強制通過率` の世代進行制御は有効。
- (iii) `trade_count floor` の段階制御は「下限のみ」限定で有効。
- 旧 exec_floor（execution指標の多段階制約）は不採用。

**推奨**
- 強制通過率: `q_force(g)` を `0.25 -> 0.15` に線形減衰
- trade_count 下限: push 期は緩く、pull 期で mission下限に近づける  
  例: push `>=0.5*TC_min`, pull `>=0.8*TC_min`

**反証条件**
- 段階制御で overtrading/undertrading が増える。
- 強制通過率を動かすと最終 Stage C 通過率が悪化する。

---

### 5. 反論5（warmstart CA/DA分離注入）への回答

**採用: 分離注入を採用**

**推奨値**
- `warmstart_share=0.20`（40体中8体）
- 内訳: `CA 5` + `DA 3`（mission寄りに少しバイアス）
- CA 選抜: `margin_inf` 最小 + feasibility 優先
- DA 選抜: session-regime カバレッジ + family 多様性優先

**反証条件**
- 分離注入で新規 family 流入が減り、run 間で同系統が自己増殖するなら `4+4` か share 縮小へ。

---

### 6. CPPS scope 確定案（最終マッピング）

| 機構 | 採否 | 最終設定 |
|---|---|---|
| 3軸 Pareto `(net, dd, margin_inf)` | 採用 | NSGA-II系 rank + crowding |
| 単目的 `margin_inf` のみ | 不採用 | ablation 比較対象としてのみ保持 |
| one-switch push→pull | 採用 | `feasible_ratio_ema>=0.15` を主条件 |
| 多状態FSM push/pull | 不採用 | pop=40/gen=15 では過剰 |
| 進化母集団の CA/DA 分離 | 不採用 | pop分割は薄すぎる |
| 外部archive の CA/DA 分離 | 採用 | `CA50/DA50`, total=100 |
| 旧exec_floor（execution metric段階制約） | 不採用 | 論点2確定により対象消失 |
| 強制通過率の段階制御 | 採用 | `0.25 -> 0.15` 減衰 |
| trade_count下限の段階制御 | 条件付き採用 | push緩・pull厳（下限のみ） |
| warmstart CA/DA 分離注入 | 採用 | share=0.20, `CA5 + DA3` |
| population / generations | 維持 | `pop=40`, `gen=15` |

---

この論点3の確定は、**「フルCPPSを縮約して、探索圧は残しつつ運用コストを固定する」**方針です。  
次の論点5（Loop closure）は、この設定を前提に `archive流入規則・eviction・warmstart汚染防止` を閉じれば整合します。