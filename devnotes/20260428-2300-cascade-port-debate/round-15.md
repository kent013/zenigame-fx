結論を更新します。  
Round 11 の `pop=256 固定` は、現時点では強すぎます。論点 A は **`lane_parallelism=1 維持`、`pop は 192 を基準に 256 へ昇格`、`gen=64 基準`、`max_workers は実機自動決定`** が最適です。`pop=128` は不採用です。

1. **反論1（lane_parallelism=1 と tier1 6通貨）**
最終選択は **tier1 は α（EUR_JPY 単一lane）** です。  
理由は、あなたが固定条件に置いた「anchor=EUR_JPY + cross-pair shadow 5通貨」と整合させるためです。

- `lane_parallelism=1` の意味: 同時並列しないだけでなく、tier1 の selection 圧は EUR_JPY のみ
- 6通貨は tier1 の selection lane にしない
- 5通貨は shadow validation 軸として毎Run評価
- lane間順序/頻度は tier1 では不要（単一laneのため）
- archive は単一（anchor専用）

2. **反論2（pop=256 vs 192 vs 128）**
最終は **`192 baseline, 256 promote, 128 reject`**。

定量:
- 総評価回数  
  - `128x64=8,192`  
  - `192x64=12,288`  
  - `256x64=16,384`
- feasible 比率 0.12 時の feasible 個体数  
  - `pop128 -> 約15`  
  - `pop192 -> 約23`  
  - `pop256 -> 約31`

判断:
- `128` は DA/CA 両立に薄すぎる（Pull期 DA が痩せる）
- `192` は探索/収束の最低実用ライン
- `256` は改善余地があるが +33% compute を払うので、常用固定ではなく昇格条件付き

昇格条件（192→256）:
- `front1_cardinality < 20` が 2 run 連続
- または `mission_pass=0` が 3 run 連続かつ多様性指標低下

3. **反論3（gen=64 vs 48）**
最終は **`gen=64 基準、48は時間制約時の縮退`**。

- `gen=64` なら 3-state の滞在に余裕
- `gen=48` は -25% 評価で速いが、bridge が短くなり遷移安定性が落ちる

48に落とす条件:
- smoke後、`p90 wall-time` が運用上限を超える場合のみ

48用FSM再校正（必須）:
- `explore>=10gen`
- `bridge>=10gen`
- `pull=残り`
- 強制遷移点を 64gen版から前倒し

4. **反論4（max_workers）**
最終は **実機依存で自動決定**。Round 11 の「下限8」は撤回します。

推奨式:
- `max_workers = clamp(floor(0.75 * physical_cores), 4, 16)`
- さらに RAM 制約で上書き  
  `workers <= floor(0.8 * free_ram / ram_per_worker_smoke)`

INCONCLUSIVE:
- `ram_per_worker` は smoke 実測まで未確定

5. **反論5（graduation lane 起動）**
最終は **(c) batch**。

- tier1 run の後段バッチとして実行
- 起動条件例  
  - `graduates >= 24`  
  - かつ `>=3 epoch` にまたがって蓄積  
  - かつ直近 epoch で mission_pass が連続観測
- tier1 と同時並列はしない（lane_parallelism=1 方針維持）

6. **反論6（wall-time INCONCLUSIVE）**
最終は **「wall-time は smoke 前は INCONCLUSIVE、ただし compute budget は先に固定」**。

事前固定するもの:
- baseline budget: `12,288 eval/run (192x64)`
- expanded budget: `16,384 eval/run (256x64)`

smoke後に確定するもの:
- `p50/p90 wall-time`
- `max_workers` 実効上限
- 48縮退の要否

7. **反論7（tier1 1lane vs 6lane）**
最終は **(α)**。  
`(β)(γ)` は将来の再設計候補だが、現時点では固定条件と設計複雑度の両面で不採用。

- 過学習リスクは「6lane化」ではなく  
  `shadow監視 + epoch rolling + Stage C/C-lite + archive品質床` で管理
- selection 圧を増やす前に、まず anchor で mission 個体を作る

8. **論点A 確定案（最終）**
- `lane_parallelism = 1`
- `tier1 = EUR_JPY single lane`（archive単一、shadow 5通貨はvalidationのみ）
- `pop = 192 (default)`、`256 (promotion mode)`、`128 不採用`
- `gen = 64 (default)`、`48 (time-constrained fallback, FSM再校正必須)`
- `max_workers = clamp(floor(0.75*physical_cores), 4, 16)` + RAM上限
- `graduation lane = batch起動`
- `compute target`: wall-timeは smoke まで INCONCLUSIVE、評価回数budgetは先に固定

これで A/B/C/D は整合します。次の確定対象は E（Sieve→Archive→Warmstart の量）を、上記 `pop=192 baseline` 前提で再スケールするのが最短です。