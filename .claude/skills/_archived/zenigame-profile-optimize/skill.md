---
name: zenigame-profile-optimize
description: Alpha Factoryプロファイル→ボトルネック分析→設計→実装→マージ→再プロファイルの自動改善ループ
argument-hint: "[--mode auto|confirm|repeat] [--baseline_profile run_id] [--skip-profile]"
---

# Alpha Factory プロファイル最適化ループ

プロファイルRUN → ボトルネック分析 → 設計 → TODO登録 → 実装 → マージ → 再プロファイルの改善ループを実行する。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `mode` ($1) | No | 実行モード。auto=最大ボトルネックを確認なしで実装, confirm=分析後にユーザー確認を求める（デフォルト）, repeat=マージ後に自動で再実行 |
| `baseline_profile` ($2) | No | 起点プロファイルのrun_id（改善率計算の基準。省略時は今回実行するプロファイルを起点とする） |
| `--skip-profile` | No | プロファイルRUN実行をスキップし、直近のプロファイル結果を使用する |

**入力**: mode（auto/confirm/repeat）、baseline_profile（起点run_id）
**出力**: 最適化済みコード（mainにマージ済み）、改善率レポート

---

## アーキテクチャ: スキル連携によるループ実行

**重要: このスキルはメタループを制御し、設計・実装は既存スキルに委任する。cronや外部スケジューラーは使わない。mode=repeatではスキル内部でループする。**

```
フォアグラウンド（メインコンテキスト — ループ制御）:
  Phase 0: 停止判定
  Phase 1: プロファイルRUN実行（BG bash）→ 完了待機
  Phase 2: ボトルネック分析（本番外挿）
  Phase 3: ユーザー確認 / 自動選択
  Phase 4: /zenigame-alpha-design でスキル呼び出し（設計 + Codexレビュー）
  Phase 5: /zenigame-todo-add でTODO登録
  Phase 6: /zenigame-implement でスキル呼び出し（worktree実装 + Codexレビュー + マージ）
  Phase 7: 再プロファイル効果評価 + ループ判定
  → mode=repeat: 自動的にPhase 0に戻る（スキル内ループ）
  → mode=auto/confirm: ユーザー確認後にPhase 0に戻る
```

**ルール**:
- **Phase 4-5は既存スキル（`/zenigame-alpha-design`, `/zenigame-todo-add`）をSkillツールで呼び出す**
- **Phase 6は`/zenigame-implement`をAgent（run_in_background=true）で実行する**（長時間のため非同期）
- cronやloopスキルは**絶対に使わない**。mode=repeatはスキル内部のループで実現する
- プロファイルRUNはBash（run_in_background=true）+ TaskOutputで完了待機
- ユーザーへの進捗報告はPhase間の遷移時のみ（context節約）

---

## Phase 0: 停止判定

**重要: プロファイル結果は本番外挿した値で判断すること。** プロファイルは48pop×2gen×1workerの小規模実行であり、そのままの秒数で改善率や停止判定を行ってはならない。必ずPhase 2-2の外挿計算を適用し、本番スケール（192pop×60gen×6workers等）での推定時間で評価する。

以下のいずれかに該当する場合、**ループを停止**してユーザーに報告する:

1. **改善率の飽和**: 起点プロファイルからの**本番外挿**累積改善率が70%以上、かつ直近の改善が5%未満
2. **メンテナンスコスト超過**: Numba JIT化・キャッシュ層追加等が既に3層以上重なっており、追加の最適化がコード可読性を著しく損なう
3. **ボトルネックが外部要因**: DB I/O、LLM API呼び出し等、コード変更で改善できないものが**本番外挿で**支配的（全体の50%以上）
4. **最大ボトルネックの本番外挿での推定削減効果が3%未満**

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

## Phase 1: プロファイルRUN実行

`/zenigame-run-alpha-factory --profile` を呼び出す。

パラメータは固定（スキル側で自動設定）:
- `--pop-size 48 --generations 2 --workers 1`
- `--profile --profile-top 100 --profile-max-c 10`
- `--stage-c-windows 1 --bootstrap 1 --immigration 3`
- `--stochastic-eval` + 標準日付パラメータ
- `--load-winners` / `--load-candidates`（latest存在時）
- `--llm-mutation 0.05 --llm-cooldown 3`

**実行方法**: Bash（run_in_background=true）で起動し、TaskOutputで完了待機。

`--skip-profile` 指定時はこのPhaseをスキップし、直近のプロファイル結果を使用する:
```bash
ls -t .cache/alpha_factory/runs/profile/profile_run_*.txt | head -1
```

完了後、`.prof` と `.txt` のパスを記録する。

---

## Phase 2: ボトルネック分析（本番外挿付き）

### 2-1. プロファイル結果の読み込み

`.cache/alpha_factory/runs/profile/profile_run_{run_id}.txt` を読み込む。

### 2-2. 本番スケールへの外挿

直近の本番RUNレポートから実行パラメータを取得:
```bash
latest_n=$(uv run python scripts/alpha_factory/get_latest_run_number.py) || exit 1
latest_report=$(find reports/run-reports -maxdepth 2 -name "run-${latest_n}.md" -not -path '*/old/*' | head -1)
```

外挿計算:
```
profile_evals = profile_pop × profile_gen  (例: 48 × 2 = 96)
prod_evals = prod_pop × prod_gen           (例: 192 × 60 = 11520)
scale_factor = prod_evals / profile_evals  (例: 120)
worker_factor = prod_workers               (例: 6)

# Stage A/B: 並列化されるため worker_factor で割る
stage_ab_extrapolated = profile_stage_ab_time × scale_factor / worker_factor

# Stage C: 候補数に依存（profile-max-c=10 → 本番は候補数次第）
# 本番のC候補数はB-PASS率 × pop_size × gen で推定
stage_c_extrapolated = profile_stage_c_time × (prod_c_candidates / profile_c_candidates)

# 固定コスト: Universe構築、preload等（スケールしない）
fixed_cost = profile_fixed_cost
```

### 2-3. 多視点分析

以下の視点でプロファイル結果を分析する:

#### 視点1: 関数レベルホットスポット
- cumtime上位10関数を特定
- 各関数の呼び出し回数 × per-call時間を分解
- **tottime（自己時間）とcumtime（累積時間）を明確に区別**し、削減対象はtottimeであることを意識する

#### 視点2: モジュールレベル集約
- プリミティブ別（market, session, core, condition等）の合計時間
- parser.py（シグナル合成）の比率
- backtest_bridge.py（バックテスト実行）の比率

#### 視点3: NumPy/SciPy呼び出しパターン
- numpy.median, numpy.mean, corrcoef等の高頻度呼び出し
- Pythonループ内でのNumPy呼び出し（ベクトル化候補）
- 既にNumba化されている関数の割合

#### 視点4: I/O・外部依存
- DB呼び出し（psycopg2 execute）の比率
- LLM API呼び出し時間
- ファイルI/O

#### 視点5: 過去の最適化との比較
- 過去のプロファイルで改善された関数が再び上位に来ていないか
- 新たに出現したボトルネック
- **既存TODOで対応済みのボトルネックかどうか確認**（TODO.mdを参照）

### 2-4. 改善候補の優先順位付け

各ボトルネックについて以下を評価:
```
| # | ボトルネック | 本番推定時間 | 全体比率 | 改善手法 | 推定削減率 | 推定削減時間 | 実装難易度 | ROI |
```

ROI = 推定削減時間 / 実装難易度（1-5スケール）

**既存設計済みTODO（TODO.md）との照合**: ボトルネックに対応するTODOが既に存在する場合はそのIDを記載し、新規設計を省略する。

---

## Phase 3: ユーザー確認（mode=confirm時）

分析結果と改善候補をユーザーに提示し、どれを実装するか確認する。

```
## プロファイル分析結果

### 本番外挿（{prod_pop} pops × {prod_gen} gens × {prod_workers} workers）
- Stage A推定: {time}秒（{pct}%）
- Stage B推定: {time}秒（{pct}%）
- Stage C推定: {time}秒（{pct}%）
- その他: {time}秒（{pct}%）
- 合計推定: {time}秒

### 改善候補（ROI順）
{改善候補テーブル}

どれを実装しますか？（番号指定、または「全部」「上位N件」）
```

**mode=auto時**: ROI最大の1件を自動選択
**mode=repeat時**: ROI最大の1件を自動選択し、マージ後に自動で再プロファイル

---

## Phase 4: 設計（/zenigame-alpha-design スキル呼び出し）

選択されたボトルネックについて、`/zenigame-alpha-design` スキルを呼び出す。

```
Skill(skill="zenigame-alpha-design", args="{topic}の説明。プロファイルデータ、改善手法、変更対象ファイル・行番号、期待削減率を含める")
```

**引数に含める情報**:
- ボトルネックの定量的説明（プロファイルデータ: tottime、呼び出し回数、全体比率）
- 改善手法の方向性（Phase 2の分析結果から）
- 変更対象ファイルと行番号
- 期待削減率のレンジ

スキルが概念設計→Codexレビュー→詳細設計→Codexレビューを実行し、設計ファイルとTODO登録コマンドを返す。

---

## Phase 5: TODO登録（/zenigame-todo-add スキル呼び出し）

Phase 4の完了報告に含まれるTODO登録コマンドを実行する。

```
Skill(skill="zenigame-todo-add", args="{topic} speed \"{summary}\" devnotes/{dir} P0 incremental")
```

---

## Phase 6: 実装（/zenigame-implement をAgentでバックグラウンド実行）

Phase 5で登録されたTODO IDを使って `/zenigame-implement` を **Agent（run_in_background=true）** で実行する。実装は長時間かかるため、フォアグラウンドでブロックしない。

```
Agent(prompt="/zenigame-implement {TODO_ID}", run_in_background=true, description="T{ID} implement")
```

Agentがworktree作成→実装→テスト→Codexレビュー→コミット→TODOクローズ→mainマージを実行する。

**完了通知を待ってから** Phase 7に進む。通知が来るまでユーザーに進捗を報告して待機する。

---

## Phase 7: 再プロファイル後の効果評価 & 判定

マージ完了後、再プロファイルRUN（Phase 1）を実行し、**必ず以下の手順で本番外挿での効果を評価してから**次のループ判定を行う:

### 7-1. 本番外挿での効果評価（必須）

Phase 2-2の外挿計算を**起点プロファイルと最新プロファイルの両方に**適用し、本番スケールでの改善効果を算出する:

```
# 起点プロファイルの本番外挿時間
baseline_extrapolated = extrapolate(baseline_profile)

# 最新プロファイルの本番外挿時間
latest_extrapolated = extrapolate(latest_profile)

# 本番外挿での改善率
improvement = (baseline_extrapolated - latest_extrapolated) / baseline_extrapolated × 100%
```

報告フォーマット:
```
## 再プロファイル効果評価

### プロファイル結果（生値）
- 起点: {baseline_time}秒
- 最新: {latest_time}秒
- プロファイル上の改善: {profile_improvement}%

### 本番外挿（{prod_pop} pops × {prod_gen} gens × {prod_workers} workers）
- 起点外挿: {baseline_extrapolated}秒（{baseline_extrapolated/60:.1f}分）
- 最新外挿: {latest_extrapolated}秒（{latest_extrapolated/60:.1f}分）
- **本番推定改善: {improvement}%（{saved_time}秒 = {saved_time/60:.1f}分短縮）**

### 対象関数の変化
| 関数 | 起点cumtime | 最新cumtime | 削減率 |
```

**注意**: プロファイルの生値（48pop×2gen）での秒数を改善効果として報告してはならない。必ず本番外挿した値で判断・報告すること。

### 7-2. ループ判定

**mode=repeat**: 7-1の評価結果を報告後、**自動的に**Phase 0（停止判定）→ Phase 1に戻る。ユーザー確認は行わない。
**mode=auto**: 7-1の評価結果を報告後、「再度プロファイルRUNを実行しますか？」とユーザーに確認
**mode=confirm**: 7-1の評価結果を報告後、「再度プロファイルRUNを実行しますか？」とユーザーに確認

---

## 高速化メソドロジー（過去の実績から抽出）

実装時に以下のパターンを参照すること。過去のAlpha Factory高速化で実証済みの手法:

### パターン1: NumPy内部ループ排除
- **症状**: numpy.median/mean/std が100万回以上呼ばれている
- **対策**: 配列全体にベクトル化（stride_tricks.sliding_window_view + np.median(axis=1)）
- **実績**: Phase 4で5-10%改善
- **確認先**: `devnotes/20260310-2307-primitive-numpy-vectorization/`

### パターン2: Numba JIT化
- **症状**: Pure Pythonのforループで逐次依存あり（ベクトル化不可）
- **対策**: `@numba.njit(cache=True)` で機械語コンパイル
- **実績**: T387 parser.py _ema: 76s→5s（93%削減）、T389 searchsorted: 77s→5s、T420 clause-composite: 46s→18s（60%削減）
- **注意**: 初回コンパイルコスト（cache=Trueで2回目以降は即時）。ndarrayのみ使用可、dict/listは制限あり。3層以上重なるとメンテナンスコスト注意
- **確認先**: `devnotes/20260322-parser-jit-hotloop/`, `devnotes/20260324-2330-profile-opt-clause-composite-jit/`

### パターン3: 算法レベル改善
- **症状**: O(N log N) や O(N²) が大量呼び出し
- **対策**: two-pointer、incremental update、前計算テーブル等
- **実績**: T389 searchsorted → two-pointer（O(log N) → O(1) amortized）
- **確認先**: `devnotes/20260322-volume-quantile-jit/`

### パターン4: キャッシュ・プリコンピュート
- **症状**: 同じ(code, date)の組み合わせで同じ計算を繰り返している
- **対策**: LRU cacheまたはバッチプリコンピュート、DayMinuteBarsのlazy cachedフィールド
- **実績**: Phase 2 MinuteBarCache: 30-40%削減、T418 pm_start_idx lazy cache: 83s→<1s
- **注意**: メモリ使用量とのトレードオフ。キャッシュ無効化の正確性
- **確認先**: `devnotes/20260216-0943-alpha-factory-optimization/`, `devnotes/20260324-2211-profile-opt-pm-start-cache/`

### パターン5: ライブラリ置換
- **症状**: 汎用ライブラリの高級APIが内部で不要な処理をしている
- **対策**: scipy.stats.spearmanr → 自前rank計算、pandas-ta → ta-lib/NumPy直接
- **実績**: T345 spearmanr: 6.7ms→軽量化、Phase 1 ATR: pandas-ta→Numba 214x
- **確認先**: `devnotes/20260216-profiling/`

### パターン6: DB/I/O最適化
- **症状**: psycopg2 executeが高頻度 or pool_pre_ping=True
- **対策**: AUTOCOMMIT、バッチクエリ、pre-ping無効化、コネクション再利用
- **実績**: T381 ping+dict.clear最適化
- **確認先**: T270実装コミット

### パターン7: NumPy dispatch overhead削減（小配列×高頻度）
- **症状**: 300要素程度の小配列に対するNumPy操作が30万回以上呼ばれ、関数dispatch overheadが支配的
- **対策**: 複数のNumPy操作をNumba @njit fused kernelに統合し、1回のコンパイル済みループで全演算を実行
- **実績**: T420 _compute_clause_composite: 15-20 NumPy ops → 1 JIT call、tottime 46s→18s（60%削減）
- **注意**: shape固定でNumba type specialization分岐を回避。出力バッファ事前確保でタプル返却を最小化
- **確認先**: `devnotes/20260324-2330-profile-opt-clause-composite-jit/`

### やってはいけないこと
- **数値精度を犠牲にしない**: 最適化前後でnp.allclose(atol=1e-6)を必ず検証
- **過度な抽象化**: 最適化のために新しい抽象層を追加しすぎない（3層以上は要注意）
- **推測による最適化**: cProfileデータなしに「ここが遅いはず」で手を動かさない
- **既存テストを壊さない**: `uv run pytest tests/alpha_factory/ -x` が全パスすること
- **tottimeとcumtimeを混同しない**: 削減対象はtottime（自己時間）。cumtimeの大部分がサブコール時間の場合、本関数のJIT化では改善されない
