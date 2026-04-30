**更新点（Round 5 から）**
- 維持: `3層流入 + bypass`, `CA/DA外部archive分離`, `warmstart 0.20 (CA5/DA3)`, `cooldown制御`。
- 更新: `K=3固定`はやめ、**目標流入数に合わせた動的K**へ変更。  
- 更新: eviction を「品質だけ」ではなく **run偏り・pattern多様性・鮮度**の3軸で確定。

---

### 1. 反論1（流入階層）  
**採用: (b) 3層**  
`mission_pass + progress_pass + score_bypass`。  
`transition_pass` は不採用。`session-majority` は独立層にせず progress 層の補助条件に使う。

**具体**
- `mission_pass`: Stage Cで live_criteria + validation axis通過。
- `progress_pass`: C-liteで `window 2/3 pass` を満たす個体。
- `score_bypass`: 上記不足分を品質順で補充。
- `session-majority`: progress層内の優先順位（2/3 session pass を優先）として使用。

**反証条件**
- progress層を入れても mission到達率が上がらず、低品質流入だけ増える場合は2層へ縮退。

---

### 2. 反論2（archive eviction）  
**採用制約: (ii) + (iii) + (v) をハード採用、(iv) をソフト保護、(i) は不採用**

**量的設計（archive=100, CA50/DA50）**
- `per_run_max = 8`（単一run由来の支配防止）
- `recency_floor = 12`（直近3runから最低12体は保護、目安4/run）
- `session_pass_pattern` は DA で多様性保護:
  - 同一pattern上限 `max_pattern_share = 0.25`（25体）
  - 希少patternは最低1体保護（存在する場合）
- `cross_pair_pass_tag` は保護対象ではなく `eviction_score` にボーナス（残りやすくする）

**evict順序**
1. まずハード制約違反候補（run過密、pattern過密）を対象化  
2. 次に `eviction_score` 最低から除去  
3. recency_floor を割る除去は禁止

**反証条件**
- recency_floorで新陳代謝が止まり、質が劣化する。
- per_run_maxが厳しすぎて高品質runの成果を取り込めない。

---

### 3. 反論3（warmstart多様性制約）  
**採用: (i)+(ii)+(iii)**

**設定（8体注入）**
- `max_family = 2`
- `max_per_source_run = 2`
- `max_per_session_pattern = 2`
- 充足不能時の緩和順:
  1. session_pattern
  2. source_run
  3. family（最後にのみ緩和）

**反証条件**
- 制約が厳しすぎて8体を安定供給できない。
- 緩和後に同系統集中が再発する。

---

### 4. 反論4（score_bypass K）  
**結論: K=3固定は不採用。動的K採用。**

**推奨**
- 目標流入 `target_inflow = 10`（許容8〜12）
- `K = clamp(target_inflow - n_mission - n_progress, 2, 4)`
- 実務上の中央値は3に収束する想定

**理由**
- mission/progress が多いrunで `K=3固定`は低品質混入を増やす。
- mission/progress が少ないrunでは `K=3` では流入不足を起こす。

**反証条件**
- 動的Kでrun間の流入品質が不安定化する場合は `K=3固定`へ戻す。

---

### 5. 反論5（cooldown）  
**採用: `max_reuse=2`, `cooldown=1` をそのまま採用**

**運用定義**
- 同一entryは直近10runで最大2回まで注入
- 注入後は次runで再注入不可（cooldown=1）

**反証条件**
- 良質entryの再利用不足で学習速度が落ちるなら `max_reuse=3` を検討。
- 逆に系統支配が出るなら cooldown を2へ延長。

---

### 6. 反論6（cycle全滅時）  
**採用: (a) を主採用。 (c) は緊急モードのみ。 (b) は不採用**

**通常**
- mission=0, progress=0 でも bypass で `8〜12` 体は流入させる。

**緊急モード（限定）**
- 連続3runで `mission=0` かつ `best_margin_inf` 悪化が続く場合のみ発動
- 次runのみ warmstart比率を一時増加（例 `0.20 -> 0.35`）
- 32体固定注入までは上げない（遺伝的硬直リスクが高い）

**反証条件**
- bypass主体でarchiveが低品質化し、Stage C到達率が低下し続ける場合は緊急モード条件を厳格化。

---

### 7. 反論7（regime_pass_pattern利用）  
**採用: (i) と (iii)、(ii) は不採用**

- (i) evictionで pattern 過密を抑制
- (iii) DA 選抜で CA と異なる pattern を優先
- (ii) warmstartで「各pattern最低1体」は強制しない（注入制約が硬くなりすぎる）

**反証条件**
- pattern多様性が維持されず同質化するなら、(ii)を「ソフト優先」に昇格。

---

### 8. Loop closure 確定案（最終マッピング）

| 項目 | 確定値 |
|---|---|
| Archive構成 | `CA50 + DA50 = 100` |
| Run流入目標 | `target_inflow=10`（許容8〜12） |
| 流入階層 | `mission_pass` → `progress_pass` → `score_bypass` |
| progress定義 | `C-lite window 2/3 pass`（session-majorityは優先度） |
| bypass数 | `K=clamp(10-n_mission-n_progress, 2, 4)` |
| Warmstart比率 | `0.20`（8体） |
| Warmstart内訳 | `CA5 + DA3` |
| Warmstart制約 | `max_family=2`, `max_per_source_run=2`, `max_per_session_pattern=2` |
| 再利用制約 | `max_reuse=2 (rolling10run)`, `cooldown=1` |
| Evictionハード制約 | `per_run_max=8`, `pattern_max_share=0.25`, `recency_floor=12/last3runs` |
| Evictionソフト優先 | `cross_pair_pass_tag` ボーナス、quality優先 |
| 全滅時 | 通常は(a) bypass補充、3run連続悪化で一時的緊急モード |

---

**定量メモ**
- `archive=100`, `inflow=10/run` なら理論上 10run で全更新相当。  
- `per_run_max=8` により単一runの占有上限は 8%。  
- warmstart使用は `8/run` なので、reuse/cooldown制約下でも archive を十分回せる。

この構成で、loop closure は「枯渇防止」と「汚染防止」を両立できます。Round 7 はこの最終案に対する cross-cutting 一貫性検査（Stage定義との矛盾、lookahead経路、過度な硬直化）を行うのが次の最短手です。