# 詳細設計: Run 90 施策 (multi-pair training 最小 spike, cycle 8)

## 使命・制約
cross-pair 汎化個体を得る。EUR_JPY 単一学習は anchor 取引枯渇 (pair_failure) + anchor 低性能 (mean 0.087<<0.15) で 0 汎化。fitness を複数ペアで評価し全ペアで機能する戦略を進化。default OFF で挙動不変。閾値緩和・取引回数操作なし。

## 根本原因 (falsification 済)
cross-pair 0 汎化 = (1)大半 anchor 取引枯渇 pair_failure=2 (2)取引する 7 個体も anchor mean 0.087<<0.15。EUR_JPY 単一学習の構造限界。

## 施策: multi-pair training (最小 spike、Codex consensus APPROVED)

### スコープ (Codex 推奨に収束)
- **Stage A fitness のみ multi-pair 化** (Stage B/C は現状維持 = 効果帰属を明確化、差分評価)。
- pairs: **EUR_JPY + USD_JPY** (2 ペア)。
- 集約: **min-across-pairs** (全ペアで機能を強制 = anchor 枯渇個体は最低 fitness_pen が低く淘汰)。診断用に mean も観測列で併記 (選抜本体は min)。
- run: **pop=48, generations=20, max_workers=2** (R89 比軽量、コスト/効果見積 spike)。

### ★ Codex Critical 3 件反映
1. **`_run_pair_sharpe` 直接転用不可** (metric_unavailable→0.0 が Stage A sentinel/penalty 契約と不整合)。各ペアで **`evaluate_stage_a` を呼び fitness_pen を算出**し min 集約。Stage A 評価系で統一。
2. **anchor 学習 bars は `_load_lane_bars` 相当 (Stage A/B 区間)** をロード (T114 の `_load_holdout_only` は Stage C 専用で流用不可)。
3. **24GB worker×pair メモリ高リスク** (spawn + LaneEvalContext broadcast で worker ごと複製)。spike は max_workers=2 + 2 ペアに限定。

### 変更箇所
1. config `MultiPairTrainingConfig.enable: bool = False` + `pairs: list[str] = []` + `aggregate: Literal["min","mean"] = "min"` + `scope: Literal["stage_a"] = "stage_a"` (default OFF=単一=現挙動 bit-exact)。CLI `--multi-pair-training` 等。
2. run_ga: enable 時、`pairs` の各 anchor の Stage A/B bars を `_load_lane_bars` でロードし LaneEvalContext に追加 (multi-pair bars map)。
3. parallel_eval `evaluate_genome`: enable 時、Stage A を各ペアで評価 (evaluate_stage_a×pairs) し fitness_pen を min 集約して a_result の fitness とする。default OFF では現行単一経路 (bit-exact)。Stage B/C は EUR_JPY (target) のみ現状維持。
4. 観測列: per-pair fitness_pen + 集約 min/mean を archive/diagnostics に記録 (効果帰属)。
5. メタ過学習ガード: out-of-run 固定期間で best 個体の anchor 性能再現を確認 (R90 後)。

### default bit-exact 保証
multi_pair_training.enable=False で evaluate_genome は現行単一 Stage A 経路 (集約なし)。selection_score/rng/population 不変。既存テスト全 pass + OFF 回帰テスト明示。

### spike 完了条件 (Codex Suggestion、先に固定)
- `pair_failure=0` 比率が R89 (7/2142≈0.3%) から有意上昇。
- `cross_pair_mean_sharpe` max が 0.15 方向へ (anchor で機能する兆候)。
- wall-time / peak RSS が許容内 (24GB、~7h×N の N を実測)。
3 軸で full 展開 (全 anchor / Stage B 拡張) の可否判断。

### テスト計画
- [ ] enable=False で evaluate_genome 単一 Stage A 経路 bit-exact (既存 run_ga_parallel pass)。
- [ ] enable=True で Stage A が pairs 分評価され min 集約 (fitness=min(per-pair fitness_pen))。
- [ ] anchor bars が _load_lane_bars (A/B 区間) でロードされる (holdout_only でない)。
- [ ] config default OFF / pairs 検証。

### リスク
中-大。Stage A 評価が ×pairs で速度低下 (spike で実測)。メモリ (worker×pair broadcast、max_workers=2 で抑制)。default OFF で bit-exact。段階分割 (spike→full) でリスク制御。

## Run 90 実行パラメータ (最小 spike)
| パラメータ | 値 |
|-----------|-----|
| --multi-pair-training | 有効 |
| pairs | EUR_JPY, USD_JPY |
| aggregate | min |
| scope | stage_a |
| population/generations | 48/20 (軽量 spike) |
| max_workers | 2 |
| seed | 68 |

> R90: pair_failure=0 比率上昇 / cross_pair_mean_sharpe max の 0.15 接近 / wall-time・RSS 実測。効果あれば cycle 9 で full (全 anchor / Stage B 拡張)。

## Codex consensus: MODIFY → 反映済 (収束)。design-review は実装差分で実施。
