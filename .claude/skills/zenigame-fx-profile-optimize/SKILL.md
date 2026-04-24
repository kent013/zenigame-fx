---
name: zenigame-fx-profile-optimize
description: zenigame-fx Alpha Factory プロファイル→ボトルネック分析→設計→実装→マージ→再プロファイルの自動改善ループ
argument-hint: "[--mode auto|confirm|repeat] [--baseline_profile run_id] [--skip-profile] [--profile-args \"<run_ga.py args>\"]"
---

# zenigame-fx Alpha Factory プロファイル最適化ループ

プロファイル RUN → ボトルネック分析 → 設計 → TODO 登録 → 実装 → マージ → 再プロファイルの改善ループを実行する。

**FX 固有**: `run_ga.py` は `--profile` フラグを持たないため `python -m cProfile` で間接計測する。`--workers` も存在しない（実装上常に単一プロセス）。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `mode` ($1) | No | 実行モード。`auto`=最大ボトルネックを確認なしで実装, `confirm`=分析後にユーザー確認を求める（デフォルト）, `repeat`=マージ後に自動で再プロファイル |
| `baseline_profile` ($2) | No | 起点プロファイルの run_id（改善率計算の基準。省略時は今回実行するプロファイルを起点とする） |
| `--skip-profile` | No | プロファイル RUN 実行をスキップし、直近のプロファイル結果を使用する |
| `--profile-args` | No | プロファイル RUN に渡す `run_ga.py` 引数の override（既定は §Phase 1 参照） |

**入力**: mode / baseline_profile / profile-args
**出力**: 最適化済みコード（main にマージ済み）、本番外挿改善率レポート

---

## 使命・思考原則・禁止事項

`zenigame-fx-codex-review` SKILL.md で定義される使命・禁止事項・C1-C9 discipline を継承。重複記載しない。

FX 固有の絶対制約（イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映）を最適化によって壊してはならない。**数値精度 / 絶対制約の破壊は最大限避ける**。

---

## アーキテクチャ: スキル連携によるループ実行

**重要: このスキルはメタループを制御し、設計・実装は既存スキルに委任する。cron や外部スケジューラーは使わない。`mode=repeat` ではスキル内部でループする。**

```
フォアグラウンド（メインコンテキスト — ループ制御）:
  Phase 0: 停止判定
  Phase 1: プロファイル RUN 実行（BG bash, python -m cProfile）→ 完了待機
  Phase 2: ボトルネック分析（本番外挿）
  Phase 3: ユーザー確認 / 自動選択
  Phase 4: /zenigame-fx-alpha-design でスキル呼び出し（概念→Codex→詳細→Codex）
  Phase 5: /zenigame-fx-todo-add で TODO 登録
  Phase 6: /zenigame-fx-implement を Agent（run_in_background=true）で実行
  Phase 7: 再プロファイル効果評価 + ループ判定
  → mode=repeat: 自動的に Phase 0 に戻る（スキル内ループ）
  → mode=auto/confirm: ユーザー確認後に Phase 0 に戻る
```

**ルール**:
- Phase 4-5 は `/zenigame-fx-alpha-design` / `/zenigame-fx-todo-add` を Skill ツールで呼び出す
- Phase 6 は `/zenigame-fx-implement` を Agent（`run_in_background=true`）で実行（長時間のため非同期）
- cron / loop スキルは**絶対に使わない**。`mode=repeat` はスキル内部のループで実現する
- プロファイル RUN は Bash（`run_in_background=true`）+ TaskOutput / ファイル監視で完了待機
- ユーザーへの進捗報告は Phase 間の遷移時のみ（context 節約）

---

## Phase 0: 停止判定

**重要: プロファイル結果は本番外挿した値で判断すること。** プロファイルは小規模実行（§Phase 1）のため、そのままの秒数で改善率や停止判定を行ってはならない。必ず Phase 2-2 の外挿計算を適用し、本番スケール（`config/alpha_factory/default.yaml` の `ga.population_size / ga.generations` + `dataset.start / end` 窓）での推定時間で評価する。

以下のいずれかに該当する場合、**ループを停止**してユーザーに報告する:

1. **改善率の飽和**: 起点プロファイルからの**本番外挿**累積改善率が 70% 以上、かつ直近の改善が 5% 未満
2. **メンテナンスコスト超過**: Numba JIT 化・キャッシュ層追加等が既に 3 層以上重なっており、追加の最適化がコード可読性を著しく損なう
3. **ボトルネックが外部要因**: DB I/O（PriceBarM1 loader）、OANDA API 等、コード変更で改善できないものが**本番外挿で**支配的（全体の 50% 以上）
4. **最大ボトルネックの本番外挿での推定削減効果が 3% 未満**

停止時の報告フォーマット:
```
## プロファイル最適化ループ停止

- 起点プロファイル: {baseline_run_id}（プロファイル{baseline_time}秒 → 本番外挿{extrapolated_time}秒）
- 最終プロファイル: {latest_run_id}（プロファイル{latest_time}秒 → 本番外挿{extrapolated_time}秒）
- 本番外挿での累積改善率: {improvement}%
- 停止理由: {reason}
- 実施した最適化: {list of TODOs}
```

---

## Phase 1: プロファイル RUN 実行

`run_ga.py` に `--profile` フラグは無いため、`python -m cProfile` で外側から計測する。

### 1-1. 既定パラメータ（override しない場合）

**GA 設定（小規模）**:
- `--population-size 8 --generations 1` → 16 genome
- `--seed 42` （決定論）

**データ窓（短期）**:
- `--instrument EUR_JPY`
- `--start 2026-03-01T00:00:00Z --end 2026-03-15T00:00:00Z`（14 日 / ~20000 M1 bars）
- Stage B/C の窓は `config/alpha_factory/default.yaml` の `stage_gate.stage_b.window_months / stage_c.holdout_days` に従うため、Stage A 通過を狭めて C 到達個体を減らす場合は `--skip-profile` モードで直近 profile を再利用する

### 1-2. 起動コマンド

```bash
mkdir -p .cache/alpha_factory/runs/profile
run_id="profile_$(date +%Y%m%d_%H%M%S)"
prof_out=".cache/alpha_factory/runs/profile/${run_id}.prof"
txt_out=".cache/alpha_factory/runs/profile/${run_id}.txt"
log_out=".cache/alpha_factory/runs/profile/${run_id}.log"

nohup uv run python -m cProfile -o "${prof_out}" \
  scripts/alpha_factory/run_ga.py \
  --run-id "${run_id}" \
  --population-size 8 --generations 1 --seed 42 \
  --instrument EUR_JPY \
  --start 2026-03-01T00:00:00Z --end 2026-03-15T00:00:00Z \
  > "${log_out}" 2>&1 &
```

`--profile-args "..."` が指定された場合は GA 設定・データ窓を override する。

### 1-3. 完了待機

Bash（`run_in_background=true`）で起動し、`pgrep -f "run-id ${run_id}"` の消失 or `"[done] run_id=${run_id}"` の出現で完了検知。

### 1-4. pstats テキスト化

```bash
uv run python -c "
import pstats
p = pstats.Stats('${prof_out}')
p.strip_dirs().sort_stats('cumulative').print_stats(80)
p.strip_dirs().sort_stats('tottime').print_stats(80)
p.strip_dirs().sort_stats('cumulative').print_callers(40)
" > "${txt_out}"
```

`--skip-profile` 指定時はこの Phase をスキップし、直近のプロファイル結果を使用する:
```bash
ls -t .cache/alpha_factory/runs/profile/profile_*.txt | head -1
```

完了後、`.prof` / `.txt` / GA 出力の `reports/run-reports/run-{N}/summary.json` のパスを記録する。

---

## Phase 2: ボトルネック分析（本番外挿付き）

### 2-1. プロファイル結果の読み込み

`.cache/alpha_factory/runs/profile/{run_id}.txt` を読み込む。

### 2-2. 本番スケールへの外挿

本番パラメータを `config/alpha_factory/default.yaml` から取得:
```bash
prod_pop=$(uv run python -c "import yaml; c=yaml.safe_load(open('config/alpha_factory/default.yaml')); print(c['ga']['population_size'])")
prod_gen=$(uv run python -c "import yaml; c=yaml.safe_load(open('config/alpha_factory/default.yaml')); print(c['ga']['generations'])")
prod_start=$(uv run python -c "import yaml; c=yaml.safe_load(open('config/alpha_factory/default.yaml')); print(c['dataset']['start'])")
prod_end=$(uv run python -c "import yaml; c=yaml.safe_load(open('config/alpha_factory/default.yaml')); print(c['dataset']['end'])")
```

プロファイル RUN の `summary.json` から実通過数を取得:
```
profile_pop × (profile_gen + 1) = profile_total_evals
profile_a_pass = sum(per_generation[*].stage_a_pass)
profile_b_pass = sum(per_generation[*].stage_b_pass)
profile_c_pass = sum(per_generation[*].stage_c_pass)
```

外挿計算（Stage ごと・バー数スケールも加味）:
```
prod_total_evals = prod_pop × (prod_gen + 1)
evals_scale = prod_total_evals / profile_total_evals

# Stage A: 全個体で 1 backtest/個体
#   bars_stage_a は config.stage_gate.stage_a.window_days 固定 → bars スケールは 1 倍
stage_a_extrapolated = profile_stage_a_time × evals_scale

# Stage B: A 通過数に依存 + wf fold 数に依存
#   A 通過率は profile_a_pass/profile_total_evals。本番は同率と仮定
#   bars_stage_b は config.stage_gate.stage_b.window_months 固定 → bars スケールは 1 倍
stage_b_extrapolated = profile_stage_b_time × (prod_total_evals × profile_a_pass_rate / profile_b_pass_if_zero_guard)

# Stage C: B 通過数に依存 (base + stress の 2 backtest / 通過個体)
stage_c_extrapolated = profile_stage_c_time × (prod_total_evals × profile_b_pass_rate / profile_c_pass_if_zero_guard)

# 固定コスト: Universe 構築、DB からの bars ロード等（pop/gen スケールしない）
fixed_cost = profile_fixed_cost
```

pass 率が 0 / 分母ゼロの場合は `0` 固定ではなく `上限外挿` を選ぶ（保守的評価）:
- A 通過 0 なら「Stage B/C は本番でも 0 ならば問題なし」ではなく、「通過するケースで支配的になるリスクあり」と注記
- 実測値無しに decided に外挿しないこと（Phase 2-5 の inconclusive フラグを立てる）

### 2-3. 多視点分析

以下の視点でプロファイル結果を分析する:

#### 視点 1: 関数レベルホットスポット
- cumtime 上位 15 関数を特定
- 各関数の呼び出し回数 × per-call 時間を分解
- **tottime（自己時間）と cumtime（累積時間）を明確に区別**し、削減対象は tottime であることを意識する

#### 視点 2: モジュールレベル集約
- primitive 別（`directional_generic.py` / `modulator_generic.py` / `pair_specific.py`）の合計時間
- `_indicators.py`（EMA/ATR/RSI/ADX 等の共通 helper）の比率
- `src/dsl/`（composite / eval / strategy）の比率
- `src/backtest/engine.py` の bar loop overhead の比率
- `src/broker/mock.py`（mark_to_market / fill_pending / submit）の比率

#### 視点 3: NumPy 呼び出しパターン
- numpy.asarray / cumsum / where / tanh 等の高頻度呼び出し
- Python ループ内での NumPy 呼び出し（ベクトル化候補）
- 既に Numba 化されている関数の割合（現状 FX は Numba 未導入）

#### 視点 4: I/O・外部依存
- SQLAlchemy ORM 呼び出し（PriceBarM1 loader）
- 構造化ログ（`structlog.info`）呼び出し回数 — **`backtest.session_close.drop_open_from_strategy` 等のイントラデイログは bar 毎に出る可能性あり、per-bar info ログは要削減**
- 例外構築コスト

#### 視点 5: O(N²) / 二重ループパターン
- **`compute_all_bars` を毎バー呼ぶアンチパターン**が primitive 層で発生していないか（`_make_compute_single` 経由で毎点評価時に N² 化する設計リスク）
- DslStrategy.on_bar → evaluator.evaluate が 1 genome 1 backtest で N×S 回呼ばれる。evaluator 側がキャッシュ済でなければ N² になる
- walk_forward fold 内での bars_to_mid_ohlc 再計算

#### 視点 6: 過去の最適化との比較
- 過去のプロファイルで改善された関数が再び上位に来ていないか
- 新たに出現したボトルネック
- **既存 TODO で対応済みのボトルネックかどうか確認**（`docs/alpha_factory/TODO.md` を参照）

### 2-4. 改善候補の優先順位付け

各ボトルネックについて以下を評価:
```
| # | ボトルネック | 本番推定時間 | 全体比率 | 改善手法 | 推定削減率 | 推定削減時間 | 実装難易度 | ROI |
```

ROI = 推定削減時間 / 実装難易度（1-5 スケール）

**既存設計済み TODO（`docs/alpha_factory/TODO.md`）との照合**: ボトルネックに対応する TODO が既に存在する場合はその ID を記載し、新規設計を省略する。

### 2-5. INCONCLUSIVE 明示

n<30 のサンプル、pass 率 0、外挿分母ゼロガードが発動した場合は `INCONCLUSIVE` としてマーク（`AGENTS.md` C7/C8 原則）。decided に寄せない。

---

## Phase 3: ユーザー確認（mode=confirm 時）

分析結果と改善候補をユーザーに提示し、どれを実装するか確認する。

```
## プロファイル分析結果

### プロファイル (pop={profile_pop}, gen={profile_gen}, bars={profile_bars})
- 総時間: {profile_total_time}秒
- Stage A: {time}秒 ({pct}%) / 実評価 {n_a_evals} 個体
- Stage B: {time}秒 ({pct}%) / 実評価 {n_b_evals} 個体
- Stage C: {time}秒 ({pct}%) / 実評価 {n_c_evals} 個体
- 固定コスト（bars loader 等）: {time}秒

### 本番外挿 (pop={prod_pop}, gen={prod_gen}, window={prod_window_days}日)
- Stage A 推定: {time}秒 ({pct}%)
- Stage B 推定: {time}秒 ({pct}%)
- Stage C 推定: {time}秒 ({pct}%)
- その他: {time}秒 ({pct}%)
- 合計推定: {time}秒 ≈ {time/60:.1f}分

### 改善候補（ROI順）
{改善候補テーブル}

### INCONCLUSIVE 項目
{データ不足で判断保留の項目}

どれを実装しますか？（番号指定、または「全部」「上位N件」）
```

- **mode=auto 時**: ROI 最大の 1 件を自動選択
- **mode=repeat 時**: ROI 最大の 1 件を自動選択し、マージ後に自動で再プロファイル

---

## Phase 4: 設計（/zenigame-fx-alpha-design スキル呼び出し）

選択されたボトルネックについて、`/zenigame-fx-alpha-design` スキルを呼び出す。

```
Skill(skill="zenigame-fx-alpha-design", args="{topic} {既存概念設計があれば path}")
```

**引数の `topic` に含める情報**:
- ボトルネックの定量的説明（プロファイルデータ: tottime / 呼び出し回数 / 全体比率 / 本番外挿時間）
- 改善手法の方向性（Phase 2 の分析結果から）
- 変更対象ファイルと行番号
- 期待削減率のレンジ
- **FX 絶対制約を壊さない担保**（イントラデイ / ロング・ショート / swap・spread 反映）

スキルが概念設計 → Codex レビュー → 詳細設計 → Codex レビューを実行し、`devnotes/{timestamp}-{topic}/` 以下に設計ファイルを生成する。

---

## Phase 5: TODO 登録（/zenigame-fx-todo-add スキル呼び出し）

Phase 4 の完了報告に含まれる devnotes ディレクトリ名を使って TODO を登録する。

```
Skill(skill="zenigame-fx-todo-add", args="\"{title}\" primitives \"{summary}\" {devnotes_dir} --priority High --mode incremental")
```

`theme` は対象モジュールに応じて `primitives` / `stage-gate` / `ga-architecture` / `infrastructure` 等から選択（`zenigame-fx-todo-add` SKILL.md の許容リスト参照）。

---

## Phase 6: 実装（/zenigame-fx-implement を Agent でバックグラウンド実行）

Phase 5 で登録された TODO ID を使って `/zenigame-fx-implement` を **Agent（`run_in_background=true`）** で実行する。実装は長時間かかるため、フォアグラウンドでブロックしない。

```
Agent(
  prompt="/zenigame-fx-implement {TODO_ID}",
  run_in_background=true,
  description="T{ID} implement"
)
```

Agent が worktree 作成 → 実装 → テスト → Codex レビュー → コミット → TODO クローズ → main マージを実行する。

**完了通知を待ってから** Phase 7 に進む。通知が来るまでユーザーに進捗を報告して待機する（ScheduleWakeup 等でのポーリングは禁止）。

---

## Phase 7: 再プロファイル後の効果評価 & 判定

マージ完了後、再プロファイル RUN（Phase 1）を実行し、**必ず以下の手順で本番外挿での効果を評価してから**次のループ判定を行う:

### 7-1. 本番外挿での効果評価（必須）

Phase 2-2 の外挿計算を**起点プロファイルと最新プロファイルの両方に**適用し、本番スケールでの改善効果を算出する:

```
baseline_extrapolated = extrapolate(baseline_profile)
latest_extrapolated   = extrapolate(latest_profile)
improvement = (baseline_extrapolated - latest_extrapolated) / baseline_extrapolated × 100%
```

報告フォーマット:
```
## 再プロファイル効果評価

### プロファイル結果（生値）
- 起点: {baseline_time}秒
- 最新: {latest_time}秒
- プロファイル上の改善: {profile_improvement}%

### 本番外挿 (pop={prod_pop}, gen={prod_gen}, window={prod_window_days}日)
- 起点外挿: {baseline_extrapolated}秒 ({baseline_extrapolated/60:.1f}分)
- 最新外挿: {latest_extrapolated}秒 ({latest_extrapolated/60:.1f}分)
- **本番推定改善: {improvement}% ({saved_time}秒 = {saved_time/60:.1f}分短縮)**

### 対象関数の変化
| 関数 | 起点cumtime | 最新cumtime | 削減率 |
| ...  | ...         | ...          | ...    |

### 使命関連の副作用チェック
- Stage A/B/C 通過率の変化: {baseline_rates} → {latest_rates}
- best fitness_pen の変化: {baseline_best} → {latest_best}
- 数値精度: np.allclose(baseline_arr, latest_arr, atol=1e-6) ✅/❌
```

**注意**: プロファイルの生値での秒数を改善効果として報告してはならない。必ず本番外挿した値で判断・報告すること。使命関連の副作用（pass 率・best fitness・数値精度）を確認せずに merge された変更は revert を検討する。

### 7-2. ループ判定

- **mode=repeat**: 7-1 の評価結果を報告後、**自動的に** Phase 0（停止判定）→ Phase 1 に戻る。ユーザー確認は行わない
- **mode=auto**: 7-1 の評価結果を報告後、「再度プロファイル RUN を実行しますか？」とユーザーに確認
- **mode=confirm**: 7-1 の評価結果を報告後、「再度プロファイル RUN を実行しますか？」とユーザーに確認

---

## 高速化メソドロジー（zenigame 側の実績 + FX 固有パターン）

実装時に以下のパターンを参照すること。`.` は zenigame 側での実証パターン、`⚡` は FX アーキテクチャ固有のパターン。

### パターン1: NumPy 内部ループ排除（・）
- **症状**: numpy.median / mean / std が 100 万回以上呼ばれている
- **対策**: 配列全体にベクトル化（`stride_tricks.sliding_window_view` + `np.median(axis=1)`）
- **zenigame 実績**: Phase 4 で 5-10% 改善
- **FX 対応先**: `src/alpha_factory/primitives/_indicators.py` の rolling_* 系

### パターン2: Numba JIT 化（・）
- **症状**: Pure Python の for ループで逐次依存あり（ベクトル化不可）
- **対策**: `@numba.njit(cache=True)` で機械語コンパイル
- **zenigame 実績**: parser._ema 76s→5s、searchsorted 77s→5s、clause-composite 46s→18s
- **注意**: 初回コンパイルコスト（`cache=True` で 2 回目以降は即時）。ndarray のみ使用可。3 層以上重なるとメンテナンスコスト注意
- **FX 対応先**: `_indicators.py` の EMA/ATR/ADX/RSI recurrence ループ、`src/dsl/composite.py` の compute_composite

### パターン3: 算法レベル改善（・）
- **症状**: O(N log N) や O(N²) が大量呼び出し
- **対策**: two-pointer、incremental update、前計算テーブル等
- **zenigame 実績**: searchsorted → two-pointer（O(log N) → O(1) amortized）

### パターン4: キャッシュ・プリコンピュート（・⚡）
- **症状**: 同じ入力で同じ計算を繰り返している
- **対策**: LRU cache またはバッチプリコンピュート
- **zenigame 実績**: MinuteBarCache 30-40% 削減、pm_start_idx lazy cache 83s→<1s
- **FX 固有**: `_make_compute_single(compute_all_bars)` は 1 点評価ごとに全長配列を再計算する O(N²) アンチパターン。`DslStrategy` に `prepare(bars)` フックを追加して 1 backtest につき 1 回だけ `compute_all_bars` を計算・cache する

### パターン5: ライブラリ置換（・）
- **症状**: 汎用ライブラリの高級 API が内部で不要な処理をしている
- **対策**: scipy.stats.spearmanr → 自前 rank、pandas-ta → 自前 NumPy
- **zenigame 実績**: spearmanr 軽量化、ATR pandas-ta→Numba 214x

### パターン6: ログ出力削減（⚡ FX 固有）
- **症状**: per-bar `logger.info(...)` が 1 backtest に 10000+ 回出る（`backtest.session_close.drop_open_from_strategy` / `drop_pending` 等）
- **対策**: DEBUG レベル降格 or 集計サマリ化。backtest 完了後に 1 行サマリ出力
- **対象ファイル**: `src/backtest/engine.py` / `src/broker/mock.py`

### パターン7: NumPy dispatch overhead 削減（・）
- **症状**: 小配列に対する NumPy 操作が 30 万回以上呼ばれ、関数 dispatch overhead が支配的
- **対策**: 複数の NumPy 操作を Numba `@njit` fused kernel に統合
- **zenigame 実績**: clause-composite 15-20 NumPy ops → 1 JIT call、46s→18s

### パターン8: DB/I/O 最適化（・）
- **症状**: SQLAlchemy ORM loader が bars 全量を dataclass 化するコスト
- **対策**: `with_entities` での列限定取得、バッチ取得、値オブジェクト化の遅延化
- **FX 対応先**: `scripts/alpha_factory/run_ga.py::_load_lane_bars`

### やってはいけないこと

- **数値精度を犠牲にしない**: 最適化前後で `np.allclose(atol=1e-6)` を必ず検証
- **FX 絶対制約を壊さない**: イントラデイ強制クローズ / ロング・ショート両方向 / swap・spread 反映を壊す最適化は却下
- **Stage A/B/C 通過判定ロジックを変えない**: 「速くなった」だけでなく「同じ判定結果を再現する」必要がある
- **過度な抽象化**: 最適化のために新しい抽象層を追加しすぎない（3 層以上は要注意）
- **推測による最適化**: cProfile データなしに「ここが遅いはず」で手を動かさない
- **既存テストを壊さない**: `uv run pytest tests/alpha_factory/ tests/backtest/ tests/dsl/ -x` が全パスすること
- **tottime と cumtime を混同しない**: 削減対象は tottime（自己時間）。cumtime の大部分がサブコール時間の場合、本関数の JIT 化では改善されない
- **pass 率 0 のプロファイルで Stage B/C 側改善を「効果なし」と判定しない**: サンプル数不足なら INCONCLUSIVE
