# Selection Cascade Port — fx 適用ロードマップ (最終確定版)

**最終更新**: 2026-04-29
**議論**: Codex gpt-5.4 / xhigh × 20 ラウンド (`round-1.md` 〜 `round-20.md`、 1-10 は前提誤りで `historical/` 隔離、 11-20 が確定議論)
**位置付け**: zenigame の selection cascade 思想 (T508/T509/T511/T513) を zenigame-fx に big-bang 導入する**設計上位文書**。 Codex Round 20 で全構成合意確定済み (異論なし)。
**ベースライン**: 本設計をベースラインとする。 既存 zenigame-fx 実装 (絶対閾値 AND 直列フィルタ + post-RUN MD-only sieve + pop=40 / gen=15 / max_workers=2) はベースラインにせず、 全削除・big-bang 置換。

---

## 0. この文書の読み方

- **5 分**: § 1 (Mission) → § 17 (用語) → § 18 (TODO)
- **設計理解**: § 2 (原則) → § 3 (アーキテクチャ) → § 5-8 (Stage / GA / Archive)
- **実装着手**: § 12 (Big-bang 移行) → § 18 (TODO)
- **議論経緯**: § 13 (Round 1-10 位置づけ) → 各 round-*.md 参照

---

## 1. Mission / 非交渉制約

### 1.1 Mission

zenigame-fx Alpha Factory の使命は **live_criteria** (`config/alpha_factory/default.yaml`) を全て満たす FX イントラデイ戦略ゲノム個体を 1 つ見つけ出すこと。

達成 = `live_criteria` の全指標 (Sharpe / Total PnL / Max DD / Trade Count 範囲) を同時に満たし、 cross-pair (ii-lite) 評価も通過した個体の出現。

### 1.2 絶対制約

- イントラデイ前提 (オーバーナイト保有設計禁止)
- ロング・ショート両方向許容
- スワップ・スプレッドを fitness に反映 (見かけ PnL ではなく net)

### 1.3 禁止事項

1. A・B・C 評価期間を強い根拠なしに延長 (過学習隠蔽)
2. 数値操作 (Sharpe / WR の見かけ向上)
3. GA ハック (fitness 関数歪曲)
4. live_criteria 緩和でステージ skip
5. やたら複雑な案
6. 取引回数削減で見かけ成績向上 (entry_threshold 過剰引き上げ等)
7. オーバーナイト前提
8. archive スキーマ伝搬漏れ (config → consumer の 4 段接続漏れ)

### 1.4 ザク導入方針 (Round 19-20 確定)

- 後方互換性・段階導入は不要、 big-bang
- これまでの実装はベースラインにすらしない
- NSGA-II と CPPS の切り替え機構 (fallback flag) は不要、 純 CPPS のみ
- 不要なものは削除

---

## 2. 設計原則 (5 原則)

zenigame で 9 つの崩壊事件を経て確立、 fx でも継承:

- **原則 0**: Lookahead bias / Leakage 徹底排除 (per-bar 確定値、 holdout 除外集計、 effective_from_utc 契約、 stage 間閾値再学習禁止)
- **原則 1**: 絶対閾値は破綻排除のみ、 選抜圧は相対 ranking
- **原則 2**: 難易度次元 (fx では session_bucket 主軸) を明示的に正規化
- **原則 3**: cycle 全滅を防ぐ強制流入 / 強制通過
- **原則 4**: canonical 5 worst aggregation で pass/fail 判定。 mean / RMS / spectral / weighted sum は tie-break / 順位補助限定

**役割分担**: worst (pass/fail 主基準) / majority (候補プリフィルタ) / spectral (順位補助) / weighted (tie-break) を明示分離。

---

## 3. 全体アーキテクチャ (7 段カスケード)

```
[Stage A] hard gate + q_force(top%) 抽出
   ↓ (A-pass のみ)
[Stage B] 5 fold pooled 主判定 + fold fail-fast 補助
   ↓ (B-pass のみ)
[Stage C-lite] 3 disjoint windows × canonical 5 worst (15 セル) + top 30% 強制通過
   ↓
[Stage C] 12w contiguous holdout + spread stress + cross-pair shadow validation
   ↓ (mission_pass / progress_pass / score_bypass の 3 層流入)
[AS / Archive] CA 72 + DA 48 = 120 entries、 epoch-aware
   ↓ (warmstart 20% ramp)
[Warmstart 注入] 次 Run の population 初期化 (CA:DA = 26:12 通常 / 19:19 emergency)
   ↓
[次 Run] Stage A から
```

**主選抜評価値 = Stage B pooled** (Round 19 で確定、 zenigame `optimize.py:2125,2141` 同等)。 A-fail は当世代の Pareto 圧計算からも除外、 親選択母集団からも除外。 archive にも入らない。

---

## 4. Dataset / Epoch / Partition 契約

### 4.1 Dataset

- **24m primary** (104w)、 35m は graduation lane audit に回す
- DB 取得済 (2023-04-23 〜 2026-04-21、 6 通貨ペア × 約 110 万 M1 bars)
- M1 24/7 fill (週末は実取引なし、 5 営業日/週で評価)

### 4.2 Epoch-rolling

- window=104w, stride=4w (月次相当), max_runs/epoch=6
- calibrate-gate history は `dataset_epoch_id` でスコープ分離 (epoch 跨ぎ再利用禁止)

### 4.3 Partition (時系列順、 古い → 新しい)

```
[B 62w] [A 8w] [emb 1w] [C-lite 6w] [emb 1w] [C-lite 6w] [emb 1w] [C-lite 6w] [emb 1w] [C 12w]
   62      8      1         6          1         6          1         6          1        12
```

合計 104w = 24m。 Stage A は時間軸では B より後 (recent proxy)、 cascade 順 (A→B→C-lite→C) は維持。 個体 genome のみ stage 横断、 評価値は stage ごとに独立計算。

### 4.4 Stage B fold (rolling-origin)

- train 36w + emb 1w + test 5w + step 5w → **5 folds**
- 5 fold pooled が**主判定**、 fold 単位は fail-fast 補助
- session block sample (1 営業日 × 1 bucket = 8h):
  - Stage B pooled = 125 blocks/bucket
  - Stage C-lite single window (6w) = 30 blocks/bucket
  - Stage C (12w) = 60 blocks/bucket

---

## 5. Stage A/B/C-lite/C 仕様

### 5.1 Stage A: Hard gate + q_force (top%)

- 評価期間: 末尾 8w (recent proxy)
- 評価指標: canonical 5 worst gate_score (= 1 / (1 + max(0, -slack_m)))
- 通過判定: 世代内 gate_score 降順で **top q_force%** が hard pass
- q_force 動的式: `clamp(0.15 + 0.15 × max(0, 0.10 - feasible_ratio_ema)/0.10, 0.15, 0.30)`
- trade_count は absolute でなく `trade_rate` で評価 (絶対値判定なし、 hard floor は trades>=2 の破綻排除のみ)
- 役割: A-pass のみ Stage B 進出。 A-fail は Pareto 圧計算からも除外、 当世代廃棄

### 5.2 Stage B: WF-OOS gate (5 fold pooled 主判定)

- 評価期間: 62w を 5 fold rolling-origin で分割
- 主判定: 5 fold 連結 pooled OOS の canonical 5 worst aggregation
- 補助判定: 各 fold で invariant fail-fast (1 fold でも違反なら infeasible 確定)
- 役割: A-pass の中から canonical 5 worst <= 0 の B-pass を抽出。 GA 主選抜 (Pareto 3 軸) は B-pooled 指標で計算
- IS monitor 撤廃 (旧逆ピラミッド除去)

### 5.3 Stage C-lite: 3 disjoint windows × 15 セル worst

- 評価期間: 6w × 3 disjoint temporal windows
- 評価指標: 各 window で canonical 5 worst → 5 指標 × 3 windows = 15 セル worst
- 通過判定: 全窓 AND (mission_pass) または **top 30% 強制通過** (sample size 不足時の cycle 健全性確保)
- progress_pass = 2/3 windows pass (majority、 中間ゲート)

### 5.4 Stage C: Final mission gate

- 評価期間: 12w contiguous holdout (最末尾)
- 評価指標: live_criteria 4 指標全達成 + spread stress (×1.5) + cross-pair shadow validation (5 通貨)
- 通過判定: live_criteria AND + stress pass + cross_pair pass = mission_pass
- 役割: 最終 mission 認証。 通過個体は archive 流入の最優先層

### 5.5 stage 別評価値の不混在

- Stage A の gate_score は **Stage A 専用ランキング**にのみ使用
- Stage B 以降の Pareto 3 軸 / canonical 5 worst は **Stage B 以降専用**
- A 値と B 値を直接同じランキングで混ぜない (gap G5 確定)

---

## 6. canonical 5 + Pareto 3 数式仕様

### 6.1 各指標の signed slack

```python
slack_sharpe = (sharpe_ann - S_min) / max(|S_min|, 1e-6)        # lower bound
slack_pnl    = (net_pnl - R_min) / max(|R_min|, 1e-6)            # R_min = total_pnl_min / initial_cash
slack_dd     = (DD_max_adj - max_dd) / max(DD_max_adj, 1e-6)    # DD_max_adj = DD_60 * sqrt(T_days/60)
slack_tc     = slack_to_range(tc, [TC_min, TC_max]) / max(TC_min, 1e-6)
slack_wr     = (session_block_win_rate_worst - WR_min) / max(WR_min, 1e-6)
```

### 6.2 SR_session_worst (HAC 補正)

```python
# block PnL series (1 営業日 × 1 session bucket = 8h)
for b in {Tokyo, London, NY}:
    r_{b,t} = sum of trade PnL within block t in bucket b
    mu_b = mean(r_{b,t})
    gamma_b(k) = lag-k autocovariance
    # Bartlett HAC (long-run variance)
    sigma2_LR_b = gamma_b(0) + 2 * sum_{k=1..q}((1 - k/(q+1)) * gamma_b(k))
    SR_b = mu_b / sqrt(max(sigma2_LR_b, eps))

SR_session_worst = min_b(SR_b)   # 3 bucket worst
```
- q = 5 (1 週間相当 lag)、 smoke 後再校正
- Lo (2002) の serial correlation 警告に対応

### 6.3 session_block_win_rate_worst

```python
for b in {Tokyo, London, NY}:
    for t in blocks of bucket b:
        if trade_count_block > 0:
            win_{b,t} = 1 if pnl_net_block > 0 else 0
        else:
            win_{b,t} = 0.5   # neutral (trade=0 を 0 除外/0 lose にしない)
    WR_b = mean(win_{b,t})

session_block_win_rate_worst = min_b(WR_b)
```

### 6.4 集約

```python
gate_worst_gap     = max_m max(0, -slack_m)      # canonical 5 全体 worst
gate_pass         <=> gate_worst_gap == 0

mission_inf_gap   = max(                          # Pareto 3 軸 f3 minimize 用、 値域 >= 0
    max(0, -slack_sharpe),
    max(0, -slack_pnl),
    max(0, -slack_dd),
    max(0, -slack_tc),
)
# Note: slack_wr は mission_inf_gap に含めない (canonical 5 gate 専用)

mission_signed_margin = min(                      # archive CA #5 ordering 用、 値域 (-inf, +inf)
    slack_sharpe,
    slack_pnl,
    slack_dd,
    slack_tc,
)
# 達成個体 (>=0) では「最低マージン」、 未達個体 (<0) では「最大不足分の符号反転」 を単一スカラーで一貫順序付け
# Pareto search では mission_inf_gap (minimize)、 archive CA ordering では mission_signed_margin (大きいほど良) を使う

log_pf_clip = clip(log((GP + 1e-6) / (GL + 1e-6)), -2, 2)   # archive lexicographic 末端 tie-break のみ
```

### 6.5 Pareto 3 軸 (search 専用)

- f1: maximize `net_pnl_after_cost`
- f2: minimize `max_dd`
- f3: minimize `mission_inf_gap`

ガイドライン: gate (canonical 5 worst) と search (Pareto 3 軸) を**直接同じランキングに混ぜない**。 統計的相関は許容するが分離は維持。

注: `mission_inf_gap` は Pareto search 用 (minimize、 値域 >= 0)、 archive CA #5 ordering は別 field `mission_signed_margin` を使用 (§ 8.3 / § 17)。 用途分離を維持。

### 6.6 invariant fail-fast (selection から完全排除)

- `session_close_drop_count > 0` (intraday 制約違反)
- `negative_equity_drop_open_count > 0` (資本破綻)

これらは検出されたら即 `is_feasible = False`、 GA selection・archive 全段階から排除。

### 6.7 補助 metric

- `spread_consumption_ratio`: tie-break + monitor (gate 圏外、 hard 化禁止 — 禁止 6 違反の温床)
- `cross-pair shadow score`: validation axis + archive metadata (selection 圧から除外)

---

## 7. NSGA-II + CPPS (2-state push/pull)

### 7.1 GA core

| 項目 | 値 |
|---|---|
| algorithm | NSGA-II + 純 CPPS (fallback flag なし) |
| population_size | **192 baseline / 256 promotion** (条件: front1_card<20 連続 2 Run 等) |
| generations | **64 baseline / 48 fallback** (FSM が比率閾値遷移なら再校正不要、 gen>=N 強制遷移使う場合のみ要再校正) |
| max_workers | `clamp(floor(0.75 × physical_cores), 4, 16)` + RAM 制約 |
| objectives | (max net_pnl, min max_dd, min mission_inf_gap) |
| selection | NSGA-II rank + 標準 crowding (3 軸正規化) |
| tie-break | rank 同 → crowding 同 → **genome_hash 決定論的** |
| parent selection | binary tournament + CA:DA 比率サンプリング (state 依存) |
| compute budget | baseline 12,288 / expanded 16,384 eval/Run |

### 7.2 Push/Pull FSM (2-state、 zenigame `push_pull_fsm.py:45` 同等)

| state | 役割 | CA/DA 配分 (pop=192) |
|---|---|---|
| **push** | infeasible 領域許容、 探索重視 | CA 84 / DA 108 |
| **pull** | feasible 領域収束、 mission 達成寄り | CA 120 / DA 72 |

遷移条件 (push → pull、 一方向):
- `feasible_ratio_ema >= θ_switch` (θ は INCONCLUSIVE、 zenigame 実装値を踏襲後 smoke 再校正)
- 強制遷移: gen=64 の場合 `gen >= 44` 安全弁 (gen=48 fallback では再校正)

注: 3-state 以上 (Round 14 で提案した explore/bridge/pull/refine) は撤回。 fx 拡張として将来候補だが初版は不採用。

### 7.3 CA/DA 配分とパラメータ scaling

pop=256 promotion 時の比率 (端数 round 規約):
- push: CA 112 / DA 144
- pull: CA 160 / DA 96

端数規約: `CA = round(pop × ratio)`、 `DA = pop - CA` (合計を pop に一致させる)。

### 7.4 offspring → CA/DA 振り分け

1. 親 + 子 をプール (= 2 × pop)
2. NSGA-II rank + crowding で survivor 抽出 (= pop 体)
3. survivor を state 依存比率で CA/DA に再配分
4. CA 不足時は `mission_inf_gap` 低い順で補充
5. DA 不足時は `novelty` 高い順で補充
6. 品質床: `invariant_feasible AND margin_inf percentile <= 70`

### 7.5 GA operators

- crossover_rate: 0.7 (Clause tree crossover、 zenigame `breeding.py:211,255` 参照)
- mutation_rate: 0.3 (subtree mutation)
- 自己交配回避: parent 同一 hash で N 回回避リトライ (上限超過なら mutation のみ)
- plateau-aware mutation_rate bump は不採用 (新 selection 圧で plateau 自体が起きにくい想定、 INCONCLUSIVE で smoke 後再判定)

### 7.6 初期 population (Run 1) と Run 間境界

- **Run 1**: archive 空のため warmstart 不可、 fresh 100% (Clause grammar sampling)
- **Run 2+**: warmstart 20% (ramp) + fresh 80%
- 各 Run = 64 generations、 Run 終了で population 破棄、 archive のみ persist
- epoch 内 max 6 Run、 epoch 切替で `dataset_epoch_id` 更新

### 7.7 失敗 genome 扱い (zenigame `core.py:1026,1085` 同等)

- backtest crash / NaN / Inf → `margin_inf = +inf` の infeasible 確定
- 全個体 fail → run abort (silent legacy degrade 禁止)

---

## 8. Archive / Sieve / Warmstart / Emergency

### 8.1 Archive 構成

| 項目 | pop=192 baseline | pop=256 promotion |
|---|---:|---:|
| archive_total | **120** | 160 |
| CA / DA | 72 / 48 | 96 / 64 |
| 記憶半減期 | ≈ 10.4 Run | ≈ 11.1 Run |

### 8.2 Inflow (archive admission、 T909 担当)

3 層流入:
1. **mission_pass** (Stage C 全達成): 無制限
2. **progress_pass** (C-lite 2/3 windows pass): worst_gap 昇順優先
3. **score_bypass** (上記不足分): worst_gap 昇順 top-K

| 項目 | pop=192 | pop=256 |
|---|---|---|
| target_inflow / Run | 8 (= 0.04 × pop) | 10 |
| per_run_max | 12 (= 0.06 × pop) | 16 |
| bypass K (通常) | `clamp(8 - n_mission - n_progress, 2, 6)` | `clamp(10 - …, 2, 6)` |
| bypass K (emergency) | `clamp(10 - n_mission - n_progress, 4, 8)` | `clamp(12 - …, 4, 8)` |

bypass 候補: **Stage B 評価済 + invariant_feasible + margin_inf percentile <= 70** (品質床)。 A-only proxy 個体は archive に入れない。

### 8.3 Eviction (T909 担当、 CA/DA 別 lexicographic)

CA eviction 順序 (上位ほど残る):
1. mission_pass
2. progress_pass
3. not_score_bypass
4. C_pass_depth (Stage C 通過の度合い)
5. mission_signed_margin (= min(slack_sharpe, slack_pnl, slack_dd, slack_tc)、 4 指標の signed slack inf-norm、 大きいほど良)
6. shadow_robustness_score (cross-pair 通過強度)
7. recency
8. log_pf_clip (末端 tie-break)

DA eviction 順序:
1. novelty
2. diversity_coverage (session/family の希少性寄与)
3. progress_pass
4. not_score_bypass
5. quality_floor_margin
6. recency
7. log_pf_clip

ハード制約: `per_run_max=12` / `pattern_max_share=0.25` / `recency_floor=12 (last 3 runs)`。

### 8.4 Warmstart 注入 (T910 担当)

- warmstart_share = **20%** (38 体 for pop=192、 51 体 for pop=256)
- ramp: run1=0%, run2=10%, run3=15%, run4+=20% (epoch 序盤の供給不足対応)
- 通常 CA:DA = 26:12 (CA 寄り)、 emergency 1:1 = 19:19
- max_per_source_run=2、 max_per_session_pattern=2、 max_family=2
- 緩和順 (制約充足不能時): session_pattern → source_run → family
- max_reuse=3、 cooldown=2 Run、 rolling=10 Run
- epoch-aware filter: prev_epoch 由来は最大 20% (Stage A quick recheck 通過時のみ)、 epoch_age >= 2 は warmstart 対象外

### 8.5 Emergency Mode

- 発動: `mission_pass=0` が 3 連続 AND `MA3(best_margin_inf) < MA6(best_margin_inf) - 0.05`
- 動作: warmstart_share 20% → **25%** (1 run のみ)、 CA:DA = 1:1
- prev_epoch 制約 20% 上限は維持 (緊急時も緩めない)
- 解除: `progress_pass >= 2` OR `best_margin_inf >= MA6`

35% 案は供給不足リスクで不採用。

### 8.6 Calibrate-gate

- 凍結窓 3 Run、 4 Run 目で更新
- 更新幅制限 `|Δ| <= 0.03`
- スコープキー: `dataset_epoch_id` (epoch 跨ぎ再利用禁止)

### 8.7 A→B 乖離 監視 (warn-only)

`corr(A_proxy_score, B_pooled_score)` を毎 Run 記録。 閾値超過で:
- 監視 log warning
- q_force 自動引き上げ (上限・戻し条件は明文化必須):
  - 上限: `q_force_max = 0.40` (固定上限、 暴走防止)
  - 引き上げ単位: 0.02 / 連続乖離 Run
  - 戻し条件: 乖離が `corr >= 0.5` に回復したら 0.02 / Run で戻す
  - hard fail なし、 警告 + 自動補正のみ

---

## 9. Schema v2 契約 (dataset_epoch_id 全経路必須)

### 9.1 Schema v2 で追加必須なフィールド

- `dataset_epoch_id` (str): epoch-rolling 識別子
- `archive_role` (enum): mission_pass / progress_pass / score_bypass
- `source_stage` (enum): A / B / C-lite / C
- `schema_version` (int): 2

### 9.2 全経路で必須化 (lint 実装、 fail-closed)

- archive entry (CA + DA) Parquet schema
- calibrate-gate history JSONL
- warmstart filter (epoch mismatch で除外)
- monitor / report 出力
- audit (DSR/PBO/SPA) report

禁止事項 8 (伝搬漏れ) の最重要ポイント。 schema lint で必須フィールド欠落 → fail。 これは zenigame には存在しない fx 新設で、 zenigame に逆輸入候補。

### 9.3 Migration policy

big-bang のため migration なし。 v1 archive は読まない (削除前提)。 v2 で空 archive から start。

---

## 10. Observability / Audit

### 10.1 監視項目 (T915 担当)

- A→B 乖離メトリクス (毎 Run 記録、 q_force 自動引き上げ trigger)
- session entropy (archive 内 session_pass_pattern 分布の Shannon entropy、 週次)
- archive churn (直近 3 Run の eviction 率)
- bypass 比率 (archive 流入のうち bypass 経由の割合)
- feasible_ratio_ema (Push/Pull FSM 主切替指標)
- front1 cardinality (Pareto front rank 1 サイズ、 pop promotion trigger)
- inflow / per_run_max / warmstart_share の設定通り動作確認

### 10.2 Audit layer (T916 担当、 段階導入)

| Audit | 状態 | 実装 |
|---|---|---|
| DSR (Bailey & López de Prado 2014) | **先行実装** | zenigame `_dsr.py:126` 同等 |
| PBO (Bailey CSCV 2015) | **未実装タグ** | schema scaffold のみ、 smoke 後段階追加 |
| SPA (Hansen 2005) | **未実装タグ** | schema scaffold のみ、 smoke 後段階追加 |

archive / report 層に置く (early gate ではない)。

---

## 11. Graduation Lane Batch 仕様 (T917 担当)

### 11.1 起動条件

以下を全て満たすと batch 起動:
- `graduates >= 24` (mission_pass + cross_pair pass の累積数)
- `>= 3 epoch にまたがって蓄積` (epoch 多様性確保)
- 直近 epoch で `mission_pass` が連続観測

### 11.2 評価ロジック (Phase 4 で詳細実装)

- tier1 graduates の union を 6 anchor pair (EUR_JPY/USD_JPY/EUR_USD/AUD_JPY/USD_CAD/USD_ZAR) で再 backtest
- multi-pair 集約: 各 pair の canonical 5 worst → pair worst 集約 (= worst-pair 評価) または mean 集約 (= 平均評価)
- graduation_pass = multi-pair worst で live_criteria 全達成
- batch 単位で実行、 tier1 と並列せず (lane_parallelism=1 維持)

詳細は Phase 4 で別 TODO 化、 初版は scaffold (起動条件判定) のみ。

---

## 12. Big-bang 移行 / 削除一覧

### 12.1 削除対象

**並走機構・fallback 系** (一切残さない):
- one-switch / fallback flag 系すべて (NSGA-II ↔ CPPS 切替なし)
- 「A 指標と B 指標を混在させて主選抜」 経路
- multi-state FSM (3-state 以上の遷移ロジック、 refine フラグ)
- schema v1 archive read/write 分岐 (v2 一本化)

**旧 config キー** (default.yaml 全面置換):
- `swim_lane.tier1.population_size=30` (lane=1 で意味消失)
- `swim_lane.graduation.seed_strategy: "union_of_tier1_graduates"` (Phase 4 で別設計)
- `ga.feasibility.{entry_count_min, apply_from_generation, enable_fallback_when_all_infeasible}` (bypass 品質床に置換)
- `improve_cycle.{plateau_cycles, plateau_mutation_bump, mutation_rate_max}` (plateau 機構廃止)
- `stage_gate.stage_a.{target_pass_rate, alpha, threshold, min_exposure_trade_count, calibrate.*}` (動的 q_force に置換)
- `stage_gate.stage_b.{wf_*, median_oos_sharpe_min, positive_fold_min, dsr_min, fold_trade_count_min}` (新 fold 仕様に置換)
- `stage_gate.stage_c.{spread_stress_*, feasibility_apply}` (新 Stage C 仕様に置換)

**旧 script**:
- 旧 `scripts/alpha_factory/run_alpha_sieve.py` (post-RUN MD-only 廃止、 archive 連動に置換)
- 旧 `scripts/alpha_factory/calibrate_gate.py` (3 Run freeze + epoch scope 仕様に置換)

### 12.2 全面置換対象

- `stage_gate.stage_a/b/c` 全ブロック → fresh schema (canonical 5 worst, mission_inf_gap, partition, fold)
- `ga.{population_size, generations, fitness_metric, max_workers}` → fresh 値
- `cross_pair.*` → validation axis のみ、 selection 圧から除外
- archive Parquet schema → schema_version=2

### 12.3 縮退保持対象 (削除しない)

- `factor_shadow` (T036): metadata 最小機能で残す (cross-pair 監視で使用、 enabled=false)
- aux 関連 config (T057): preflight 整合のため維持
- `dataset.{instrument, start, end}`: 24m epoch-rolling で動的更新
- `backtest.{initial_cash, leverage, units, max_spread_bps, holding_cost_per_day_bps}`: 維持
- `live_criteria.*`: Stage C mission gate として維持

### 12.4 切替戦略

- 開発中は新実装を `new_cascade` 名前空間で実装
- T918 smoke (1 Run E2E) + 5 Run 連続検証通過で切替
- 切替コミットで旧 stage / 旧 GA / 旧 sieve を**同日削除**
- dual-path 並走なし (分岐バグ温床)

ロールバック条件: smoke で FM1/FM4 が強く出る場合のみ 1 サイクル延期、 旧実装は「実行不可の参照コード」 として一時凍結のみ (再有効化はしない)。

---

## 13. Round 1-10 の記録的位置づけ

`historical/old-rounds-1-10/` に隔離。 **実装根拠としては無効**。

経緯: 2026-04-28 開始の Round 1-10 で「`pop=40 / gen=15 / max_workers=2 / canonical 5 = profit_factor / dataset 6 ヶ月」 を hard constraint として議論を組み立てたが、 ユーザ指摘でこれら全て config default に過ぎず、 議論は前提誤り上に成立していたと判明。

残す価値: 「config default を hard constraint と扱った」 「fx 単一通貨ペアの semantic 誤解」 「現状逆ピラミッドから compute 線形外挿」 という 3 つの誤りパターンの監査ログ。 同種誤り再発防止の参照資料。

正しい議論は Round 11-20 (本 synthesis のソース)。

---

## 14. zenigame 実装対応表 (file:line)

zenigame 側の実装ファイルへの対応を明示。 fx 実装時に直接参照すべき箇所:

| 機構 | zenigame ファイル | 行 |
|---|---|---|
| Stage A Adaptive Gate (T151/T402/T511) | `src/trading/alpha_factory/ga/nsga2/stage_a_gate.py` | 7 (stage_b_ratio), 66 (gate logic) |
| GA optimize loop | `src/trading/alpha_factory/ga/nsga2/optimize.py` | 950 (Stage A pass), 1006/1195 (B-eval gating), 2125/2141 (主選抜 B-based) |
| canonical 5 worst gate_score | `src/trading/alpha_factory/evaluation/fitness.py` | 461 (calc_stage_a_gate_score) |
| live_criteria_gap helper | `src/trading/alpha_factory/evaluation/live_criteria_gap.py` | (T510/T512 集約済) |
| Push/Pull FSM | `src/trading/alpha_factory/ga/nsga2/push_pull_fsm.py` | **45 (2-state)** |
| CA/DA Two-Archive | `src/trading/alpha_factory/ga/nsga2/archives.py` | (T509) |
| breeding (parent selection, crossover, mutation) | `src/trading/alpha_factory/ga/nsga2/breeding.py` | 211 (tournament), 255 (crossover) |
| Sieve filter (4 層流入) | `src/trading/alpha_factory/alpha_sieve/filter.py` | (T492 + T499) |
| Archive admission/eviction | `src/trading/alpha_factory/alpha_sieve/archive_updater.py` | 123 (admit), `_evict_lowest_score` |
| Sieve archive injection (CA/DA 分離) | `src/trading/alpha_factory/alpha_sieve/sieve_archive.py` | 361 (is_injection_eligible), `select_injection_candidates_with_split` |
| GENOMES_SCHEMA | `src/trading/alpha_factory/ga/genome_archive.py` | 540 (schema 定義、 dataset_epoch_id 不在) |
| DSR | `src/trading/alpha_factory/runner/_dsr.py` | 126 |
| Run loop | `src/trading/alpha_factory/runner/_runner.py` | 673 (Run 開始時 init), 952 (Run 終了境界) |
| determinism (RNG seed) | `src/trading/alpha_factory/ga/nsga2/core.py` | 114 (seed 固定), 1026/1085 (failure handling) |

---

## 15. INCONCLUSIVE と再校正計画

仮固定値 + smoke 後再校正:

| 項目 | 仮固定 | 再校正条件 |
|---|---|---|
| Push/Pull 切替 `feasible_ratio_ema` 閾値 | TBD (zenigame 値踏襲) | smoke で feasible discovery curve 観測 |
| HAC `q` (Bartlett kernel lag) | 5 | q=3/7/10 比較 |
| `trade=0 block` 中立 0.5 | 0.5 | 0 除外 / 0 lose 比較 |
| `eviction_score` 加重 (lex 順序内の係数) | 確定済 lex 順序維持 | 5 run 観測まで固定 |
| 緊急モード `MA3 < MA6 - 0.05` | -0.05 | 5 run 観測で再校正 |
| `archive=120` | 120 | 80/100/160 比較 |
| `inflow 0.04 / per_run_max 0.06` | pop 比例 | A/B 乖離との相関 |
| `prev_epoch 20% 許容` | 20% | 0%/30% 比較 |
| `stride=4w` | 4w | 8w/12w 比較 |
| `pop 192 → 256 promotion 閾値` (`front1<20 連続 2 Run`) | 仮 | 実測で調整 |
| `max_workers` 飽和点 | TBD | smoke で `eval/sec/core` 測定 |
| `q_force_max = 0.40` (A→B 乖離時上限) | 0.40 | 暴走時に 0.35 へ縮小検討 |
| `shadow_robustness_score` の重み式 | TBD | 運用ログで再同定 |
| `mission_signed_margin` denom 正規化 | 4 slack を未正規化で min | smoke 後に live_criteria scale 比較で再校正検討 (通過率 vs 強度のバランス) |

PBO/SPA 実装時期は smoke 後 (DSR 先行)、 cost model epoch 再校正は smoke 後判定、 DST/holiday 詳細境界は T914 で contract 化。

---

## 16. Risk Top 5 と緩和策

| 順位 | リスク | 緩和 |
|---|---|---|
| 1 | A-pass / B-pooled 乖離で探索誤誘導 | A→B 乖離メトリクス毎 Run 記録、 q_force 自動引き上げ (上限 0.40)、 戻し条件あり |
| 2 | epoch_id 伝搬漏れで cross-epoch 汚染 | schema lint で必須フィールド欠落 fail (fail-closed) |
| 3 | 緊急時 warmstart 供給不足 | 35% 廃止、 25% 固定、 ramp 整合、 prev_epoch 20% 維持 |
| 4 | archive bypass 偏重で品質低下 | bypass = B 評価済 + 品質床 (invariant_feasible AND margin_inf p<=70) |
| 5 | DA 多様性形骸化 | DA eviction で novelty/coverage 主キー化、 entropy 週次監視 |

---

## 17. 用語・判定辞書

| 用語 | 定義 |
|---|---|
| canonical 5 | gate (pass/fail) で worst aggregation する 5 指標: `SR_session_worst / net_pnl_after_cost / max_dd / trade_count / session_block_win_rate_worst` |
| Pareto 3 軸 | search (進化圧) で使う 3 軸: `max net_pnl / min max_dd / min mission_inf_gap` |
| mission_inf_gap | live_criteria 4 指標の inf-norm shortfall (= max(0, -slack_*) の最大)。 Pareto 3 軸 f3 minimize 用、 値域 >= 0、 win_rate は含まない |
| mission_signed_margin | live_criteria 4 指標の signed slack inf-norm (= min(slack_sharpe, slack_pnl, slack_dd, slack_tc))。 archive CA #5 ordering 用、 値域 (-inf, +inf)。 達成個体 (全 slack >= 0) では「最低マージン」、 未達個体 (どれかの slack < 0) では「最大不足分の符号反転」 を単一スカラーで一貫順序付け、 大きいほど良。 T062 MissionGapResult に実装 |
| mission_margin | **BACKWARD COMPAT** (Round 11-20 議論時の旧称、 = -mission_inf_gap 定義は値域 <= 0 で「達成超過」 を表現できず数式と用途乖離あり)。 新規参照は `mission_signed_margin` を使用、 § 8.3 改訂で SSOT 移行済 (Round 21) |
| SR_session_worst | session block (8h) の HAC Bartlett q=5 補正 Sharpe を 3 bucket それぞれで計算した最悪値 |
| session_block_win_rate_worst | 1 営業日 × 1 bucket の block PnL > 0 を「win」 とした勝率の 3 bucket 最悪値、 trade=0 block は 0.5 neutral |
| slack_to_range | trade_count [L, U] range の signed slack。 v<L、 v>U、 範囲内それぞれで連続値 |
| q_force | Stage A 強制通過率 (top-N%)。 動的 `clamp(0.15 + 0.15 × max(0, 0.10 - feasible_ratio_ema)/0.10, 0.15, 0.30)`、 A→B 乖離時上限 0.40 |
| invariant fail-fast | session_close_drop>0 / negative_equity_drop_open>0 で is_feasible=False、 selection 全段階から排除 |
| mission_pass | Stage C 全達成 (live_criteria + spread stress + cross-pair shadow) の archive 流入第 1 層 |
| progress_pass | C-lite 2/3 windows pass の archive 流入第 2 層 |
| score_bypass | mission/progress 不足時の worst_gap 昇順 top-K 強制流入。 Stage B 評価済 + 品質床必須 |
| log_pf_clip | `clip(log((GP+1e-6)/(GL+1e-6)), -2, 2)`。 archive lexicographic 末端 tie-break |
| dataset_epoch_id | epoch-rolling 識別子。 archive / calibrate / warmstart / monitor / audit 全経路で必須 |
| CA / DA | Convergence Archive (mission 達成寄り) / Diversity Archive (多様性寄り)。 進化母集団 + 外部 archive の両方で分離 |
| push / pull | CPPS の 2-state FSM。 push = 探索 (infeasible 許容)、 pull = 収束 (feasible 寄り) |
| front1 cardinality | Pareto rank 1 のサイズ。 pop promotion (192→256) trigger に使用 |

---

## 18. TODO 実装計画 (T901 〜 T918)

### 18.1 依存関係

```
先行必須: T901 → T902 → T903
評価系:   T904 → T905 → T906 → T907
GA中核:   T908 → T909 → T910 → T911
運用制御: T912 → T915
基盤拡張: T913 → T914
監査/展開: T916 → T917 → T918
```

並行可能: 評価系と GA 中核 (T903 完了後)、 監査/展開は他全 Phase と並行可。

### 18.2 TODO 詳細

| TODO | 内容 |
|---|---|
| **T901** | Schema v2 contract: `dataset_epoch_id`, `archive_role`, `source_stage`, `schema_version=2` を archive / history / run / eval / report 全経路必須化、 schema lint 実装 |
| **T902** | Epoch / Window Manager: 24m rolling, stride=4w, max_runs/epoch=6 |
| **T903** | Partition + fold generator: B 62w + A 8w + C-lite 6w×3 + C 12w + embargo splitter、 Stage B 5 fold rolling-origin (train 36w / emb 1w / test 5w / step 5w) 固定 |
| **T904** | canonical 5 engine: HAC Bartlett q=5 Sharpe + session block PnL aggregation + slack_to_range + log_pf_clip |
| **T905** | mission_inf_gap engine: live_criteria 4 指標の inf-norm shortfall |
| **T906** | Stage A evaluator: hard gate + q_force 動的計算 (上限 0.40 含む)、 trade_rate 中心 |
| **T907** | Stage B evaluator: A-pass only、 5 fold pooled 主判定 + fold fail-fast 補助 / Stage C-lite + C evaluator: 3 disjoint windows + 12w holdout + spread stress + cross-pair validation |
| **T908** | NSGA-II core: rank + standard crowding + deterministic tie-break (genome_hash) + pop=192/256 scaling + 端数規約 (round) |
| **T909** | CPPS 2-state FSM (push/pull、 feasible_ratio_ema 切替) + CA/DA archive **admission / eviction** + 動的 CA/DA 比率 (push 84/108、 pull 120/72) |
| **T910** | Warmstart engine: **injection / reuse / cooldown** + epoch filter (prev_epoch 20% only) + ramp (run1=0% → run4+=20%) + max_per_source_run/session_pattern/family + emergency 25% |
| **T911** | Failure handling: NaN/Inf/crash → margin_inf=+inf infeasible 確定、 全 fail run abort |
| **T912** | Calibrate-gate scope: epoch key + 3 Run freeze + Δ<=0.03 / Emergency mode trigger (mission=0 3 連続 + MA3<MA6-0.05) |
| **T913** | Backtest engine 拡張: session bucket label per bar + session block PnL series + block trade_count 出力 |
| **T914** | Timezone / DST / holiday session boundary contract: FX 専用 UTC 基準 + 祝日カレンダ + 週末 gap 処理 |
| **T915** | Observability: A/B 乖離 / entropy / inflow / archive churn / front1 cardinality / feasible_ratio_ema 監視、 q_force 自動引き上げ (上限・戻し条件) |
| **T916** | Audit layer: DSR 先行実装 (zenigame `_dsr.py:126` 同等) + PBO/SPA は schema scaffold + 「未実装」 タグ |
| **T917** | Graduation lane batch evaluator scaffold: 起動条件 (graduates>=24 + 3 epoch + mission 連続) + multi-pair 集約 sketch (詳細実装は Phase 4 別 TODO) |
| **T918** | Big-bang cleanup + smoke: 旧 path 削除 + 1 run E2E smoke + 5 run 連続検証 |

### 18.3 T918 Smoke DoD (Codex Round 20 確定)

以下を全て満たすと smoke 完了:

- 1 Run 完走 (クラッシュ無し、 NaN/Inf fail-soft 動作)
- A-pass only B-eval をログで検証 (A-fail が B/親選択へ入らない)
- 主選抜が **B-pooled 指標のみ**で計算されている
- archive 書込の全レコードで `dataset_epoch_id` 必須 (欠落=fail)
- inflow / per_run_max / warmstart_share が設定通り
- CA/DA 配分が state ごとに一致 (pop=192 push 84/108、 pull 120/72)
- invariant fail-fast (session_close_drop, negative_equity_drop_open) が有効
- 連続 5 Run で epoch 汚染なし (prev_epoch 20% 制約順守)

---

## 19. fx → zenigame 逆輸入候補

zenigame 側合意済み。 fx で出した改善のうち zenigame に持ち帰る価値があるもの (4 件、 Codex Round 20 推奨):

1. **`dataset_epoch_id` 全経路契約 + schema lint**: zenigame の T54 history scope を一般化、 epoch 跨ぎ汚染を fail-closed で防ぐ
2. **`session_block_win_rate`**: trade-level win_rate より運用安定性に効く (lane 跨ぎ semantic 一貫性、 多重比較に頑健)
3. **HAC 補正 Sharpe の標準化**: Lo (2002) serial correlation 警告対応、 M1 bar 直列の SE 安定化
4. **A/B 乖離監視 + 自動 q_force 調整**: 監視のみの zenigame 実装に対し、 fail-soft 自動補正経路を追加

---

## 20. Next Action Top 3

1. **T901 を最優先実装**: 全経路 `dataset_epoch_id` 契約を schema lint で固定 (= fail-closed)
2. **T902 / T903** で epoch manager + partition splitter 実装
3. **T904 / T905** で canonical 5 engine + mission_inf_gap engine を単一 API 化
4. **T908 / T909** で NSGA-II + CPPS 2-state を一気に build
5. **T918 smoke** で 1 Run 完走 + DoD 全項目クリア → big-bang 切替コミット

---

## 21. 議論履歴サマリー

| Round | 主題 | 確定内容 |
|---|---|---|
| 1-10 | (前提誤り、 historical/ 隔離) | pop=40/gen=15 等を hard constraint と誤認、 議論ベース崩壊 |
| 11 | fresh design 提案 + 議論順序 B→C→D→A→E→F→G | lane=1, dataset 24m, canonical 5 = session-based |
| 12 | 論点 B (partition + fold) | 24m=104w partition、 5 fold pooled、 train 36w/test 5w、 epoch-rolling 4w |
| 13 | 論点 C (canonical 5 + mission_inf_gap) | Sharpe_session HAC、 session_block_win_rate、 mission_inf_gap = 4 指標 max |
| 14 | 論点 D (CPPS 構造) | NSGA-II + 3-state FSM (← Round 19 で 2-state に修正)、 CA/DA 動的比率 |
| 15 | 論点 A (pop/gen/max_workers) | pop=192/256, gen=64, lane=1, max_workers 自動 |
| 16 | 論点 E (Loop) + F (P2) | archive=120、 warmstart 20% ramp、 P2 = session 3 固定 |
| 17 | cross-cutting + 論点 G | A-proxy/B-pooled 分離 (← Round 19 で B-pooled 統一に修正)、 emergency 25%、 dataset_epoch_id 全経路必須 |
| 18 | synthesis 暫定 | 章立て、 TODO、 next action |
| 19 | gap 診断 + zenigame コード参照 (8 件修正) | FSM 2-state、 主選抜 B-pooled、 PBO/SPA 未実装、 fold=5、 schema 新設、 factor_shadow 縮退、 A→B warn-only、 端数規約 |
| 20 | 最終 consensus | 全構成合意確定、 異論なし、 smoke DoD 確定、 逆輸入 4 候補 |
| 21 | (T064 完了後 / 2026-04-30) synthesis 改訂 | T062 詳細設計で発見した `mission_margin` 命名矛盾 (= -mission_inf_gap、 値域 <= 0 で「達成超過」 表現不能) を解消、 `mission_signed_margin` (= min(slack_*)) を新設し archive CA #5 SSOT 化、 `mission_margin` は BACKWARD COMPAT 整理。 § 6.4 / § 6.5 / § 8.3 / § 15 / § 17 改訂、 実装影響なし (T062 で先行実装済)。 改訂 PR: `devnotes/20260430-1045-synthesis-revise-mission-signed-margin/` |

詳細は `round-11.md` 〜 `round-20.md` 参照。 旧議論は `historical/old-rounds-1-10/`。 Round 21 改訂の rationale は `devnotes/20260430-1045-synthesis-revise-mission-signed-margin/rationale.md` 参照。
