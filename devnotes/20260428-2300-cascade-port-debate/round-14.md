結論から先に確定します。  
論点 D は **`NSGA-II + CPPS(軽量)`** で行きます。`4-state` は今回は不採用、**`3-state + refineフラグ`** にします。理由は `gen=64` で状態数を増やしすぎると閾値調整自由度が増え、禁止事項 5（過剰複雑化）に寄るためです。

## 1. 反論1（CA/DA 分割比率）
採用は **(b) 動的比率** です。

- `Explore`: `CA=112, DA=144`
- `Bridge`: `CA=128, DA=128`
- `Pull`: `CA=160, DA=96`
- `RefineフラグON時`: `CA=176, DA=80`（Pull内サブモード）

配置基準（biology）:
- CA適性: `mission_inf_gap` 小、`invariant_feasible=True`、`rank` 良
- DA適性: `novelty` 大、`session/family coverage` 改善、ただし品質床は満たす

定量根拠:
- `pop=256` で `feasible_ratio=0.03` は約8体、`0.12` は約31体。  
- Pullで `CA=160` にすると feasible 近傍の選択圧を十分確保できる。

## 2. 反論2（Push/Pull FSM 状態数）
採用は **3-state**（`explore -> bridge -> pull`）です。  
`refine` は独立stateにせず Pull内フラグで実装。

遷移条件:
- `explore -> bridge`: `gen>=12` かつ `feasible_ratio_ema >= 0.03`、または強制 `gen>=24`
- `bridge -> pull`: `gen>=24` かつ `feasible_ratio_ema >= 0.12`、または強制 `gen>=44`
- `pull内 refineフラグ`: `n_mission_pass>=4` かつ `gen>=48`

INCONCLUSIVE:
- `0.03 / 0.12` は F-1 smoke の feasible discovery curve で再校正対象。

## 3. 反論3（crowding distance）
採用は **(i) 標準 crowding** です。

- NSGA-II本体は標準（3 objective正規化距離）
- `session/family` 多様性は DA選抜と archive eviction で担保
- crowdingに (ii)(iii) を混ぜるのは「二重で多様性を課す」ので初期は避ける

定量:
- `N=512`（親+子）で標準NSGA-IIは十分軽い
- pairwise多様度を本体に入れると調整点が増えて不安定化しやすい

## 4. 反論4（offspring の CA/DA 振り分け）
採用は **(α) ベース + 軽量(δ)** です。

実装:
1. 親+子をプール（512）
2. NSGA-II rank+crowding で survivor 256 を選抜（標準互換）
3. survivor を state依存ルールで `CA/DA` に再配分
4. CA不足なら `mission_inf_gap` 低い順で補充、DA不足なら `novelty` 高い順で補充

`(β)` の lineage固定は探索固定化を招くため不採用。

## 5. 反論5（archive epoch reset）
採用は **partial reset（epoch aware）** です。全clearはしません。

ルール:
- 全entryに `dataset_epoch_id` を保持
- warmstart抽選は原則 `current_epoch` のみ
- `prev_epoch` は `Stage A quick recheck` 通過時のみ最大20%まで許可
- `epoch_age >= 2` は warmstart対象外（保管のみ or purge）

これで stale 注入を抑えつつ、完全リセットの記憶損失を回避します。

## 6. 反論6（lexicographic eviction を CA/DA で分離）
採用は **分離** です。共通順序は使いません。

CA eviction順序:
1. `mission_pass`
2. `progress_pass`
3. `not_score_bypass`
4. `C_pass_depth`
5. `mission_margin`
6. `shadow_robustness`
7. `recency`
8. `profit_factor`（最終tie-break）

DA eviction順序:
1. `novelty`
2. `diversity_coverage`（session/familyの希少性寄与）
3. `progress_pass`
4. `not_score_bypass`
5. `quality_floor_margin`
6. `recency`
7. `profit_factor`（最終tie-break）

## 7. 論点D 確定案（実装可能仕様）

GAコア:
- `pop=256`, `gen=64`
- objectives: `maximize net_pnl_after_cost`, `minimize max_dd`, `minimize mission_inf_gap`
- selection: NSGA-II rank + standard crowding

CPPS軽量実装:
1. `state` に応じて CA/DA 比率を設定
2. 親選択は `CA:DA` 比率サンプリング（exploreはDA寄り、pullはCA寄り）
3. 交叉・突然変異で offspring 生成
4. 親+子を評価
5. NSGA-IIで survivor 256
6. survivor を CA/DA 再配分
7. 外部 archive(CA_ext/DA_ext) に admission（品質床あり）
8. archive eviction は CA/DA 別lexicographic
9. 次世代へ

品質床（DA含む）:
- `invariant_feasible=True`
- `margin_inf percentile <= 70`（既確定事項）

計算量目安:
- 1世代あたり `N=512` の non-dominated sort は実用範囲
- 64世代でも GA本体計算は律速になりにくく、律速は backtest evaluator 側

---

**zenigame T509 との差分（fx向け最適化）**
- `exec_floor` は不採用
- CA/DA を `epoch-aware` にし stale 注入を抑制
- 4-stateではなく 3-state + refineフラグで簡素化
- crowding拡張は初期不採用、DA/Archiveで多様性を扱う

---

INCONCLUSIVE（Round 15で再検証）:
- `CA/DA 比率` の最適値（112/144 など）は実測で微調整余地あり
- `feasible_ratio_ema` 閾値 `0.03/0.12` の妥当性
- `prev_epoch 20%` 許容が有利か（0%が良い可能性あり）