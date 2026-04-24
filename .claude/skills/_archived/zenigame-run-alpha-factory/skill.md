---
name: zenigame-run-alpha-factory
description: Alpha FactoryのGA実行（バックグラウンド）+ ログ監視 + 結果確認
argument-hint: "<run_alpha_factory.py args>"
---

# Alpha Factory GA実行

以下の手順でAlpha FactoryのGA最適化をバックグラウンド実行してください：

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `args` ($1..N) | Yes | run_alpha_factory.pyへの引数 |

## 前回Run設定の取得

ユーザーが「前回の設定で実行」「前回RUNと同じ」などを指定した場合、以下の手順で最新の設定を取得すること。

```bash
# 最新のRunレポートを特定（SSoT: 共通ヘルパー経由）
latest_n=$(uv run python scripts/alpha_factory/get_latest_run_number.py) || exit 1
latest_report=$(find reports/run-reports -maxdepth 2 -name "run-${latest_n}.md" -not -path '*/old/*' | head -1)
# → 例: reports/run-reports/run-1000-1099/run-1015.md

# そのレポートの「実行パラメータ」セクションを読む
```

取得した「実行パラメータ」テーブルの値からコマンドを組み立てて実行する。

---

## 重要ルール

- **バックグラウンド実行必須**（長時間実行のため）
- **設定ファイル**: 全パラメータのデフォルト値は `config/alpha_factory/default.yaml` に定義。カスタム設定は `--config path/to/override.yaml` で部分上書き可能。優先度: `default.yaml < env ALPHA_FACTORY_CONFIG < --config < CLIオプション`
- **LLM変異はデフォルトON**（引数に`--llm-mutation`が含まれていなくても、自動で`--llm-mutation 0.05 --llm-cooldown 3`を付与する）
  - ユーザーが明示的に「LLM OFF」等を指定した場合のみ付与しない
- **スプレッドコストはデフォルトON**（`default.yaml: use_spread_cost: true`）。無効化するには `--no-use-spread-cost` を明示する
- **日付引数は必ずコロン区切り**（`YYYY-MM-DD:YYYY-MM-DD`）。スペース区切りは不可
- **繰り返しモード**: ユーザーが「繰り返して」「ループして」「repeat」等を指示した場合、全ステップ完了後に自動で `/zenigame-improve-cycle` を呼び出す（繰り返しフラグ付き）

### default.yamlの主要デフォルト値変更履歴
| パラメータ | 旧値 | 新値 | Run | 理由 |
|-----------|------|------|-----|------|
| tc_min_rate | 1.0 | 1.67 | 276 | live_criteria準拠（50trades/30日）|
| tc_sweet_penalty | 0.15 | 0.0 | 276 | TC hard constraint化に伴い無効化 |
| primitive_active_set | null | (生成リスト) | 276 | 死にプリミティブ除外 |
| director.epoch_min_runs | (なし) | 5 | 297 | Director継続記憶（エポック管理）導入 |
| director.epoch_max_runs | (なし) | 10 | 297 | Director継続記憶（エポック管理）導入 |
| director.inertia_lambda | (なし) | 0.2 | 297 | 慣性clamp導入（エポック内重み安定化）|
| director.inertia_per_run_clamp | (なし) | 0.03 | 297 | per-Run重み変更幅制限 |
| director.inertia_per_epoch_clamp | (なし) | 0.10 | 297 | エポック累積乖離上限 |
| shadow_mg_tiebreak | (なし) | false | - | Shadow MG tie-break導入（デフォルトOFF、--config override.yamlで有効化） |
| shadow_mg_crowd_epsilon | (なし) | 0.10 | - | crowding距離近接判定の比率閾値 |

## コンテキスト圧縮対策

長時間実行中にコンテキスト圧縮が発生すると、task_id・run_id等の重要情報が失われる。これを防ぐため、**状態ファイル** `.cache/alpha_factory/current_run_state.json` を各ステップで更新する。

**圧縮復帰手順**: コンテキスト圧縮後に状態が不明になった場合、まずこのファイルを `Read` して現在の状態を復元してから作業を再開すること。

**状態ファイルの書き込みタイミング**:
- ステップ2（バックグラウンド実行開始直後）
- ステップ4（完了検出時）
- ステップ7（ゲノムアーカイブ分析完了後）
- ステップ8（improve-cycle呼び出し前）

**状態ファイルのフォーマット**:
```json
{
  "skill": "run-alpha-factory",
  "step": "3_monitoring",
  "task_id": "bg_xxxx",
  "run_id": "run_YYYYMMDD_HHMMSS",
  "log_file": ".cache/alpha_factory/runs/run_YYYYMMDD_HHMMSS.log",
  "run_args": "--pop-size 48 --generations 30 ...",
  "repeat_mode": true,
  "run_number": 45,
  "started_at": "2026-02-19T21:00:00",
  "last_updated": "2026-02-19T21:15:00"
}
```

**Writeツールで更新**する（Bashのechoは使わない）。

**`--profile` 実行時の例外**: プロファイル実行は一時的なパフォーマンス計測であり、本番RUNの状態を上書きしてはならない。`--profile` 付きで実行する場合、`current_run_state.json` の書き込みを**すべてスキップ**すること。

**`--profile` 実行時のパラメータルール**（ユーザー指示がない限り以下を固定で使用すること）:
- **`--pop-size 48` 必須**: プロファイルに十分な集団サイズ。ユーザー指示がない限り変更しない。
- **`--generations 2` 必須**: プロファイルの目的はボトルネック特定であり、多数世代は不要。B-passが確認できる程度の2世代で十分。
- **`--workers 1` 必須**: マルチワーカーだとcProfileがメインプロセスの待機時間しか計測できず、実際のボトルネックが見えない。必ず `--workers 1` で実行すること。
- **`--stage-c-windows 1` 必須**: Stage C経路のプロファイルは1ウィンドウで十分。
- **`--profile-max-c 10` 必須**: Stage C候補が多数ある場合（seed投入時など）、全個体評価は非常に遅い。上位10個体に制限してプロファイル時間を大幅短縮。`--profile` 有効時のみ作用し、通常RUNには影響しない。
- **`--load-winners` / `--load-candidates` 推奨**: B-pass / C-pass経路のプロファイルも取得するため、前回の勝者/候補をseedとして投入する。
- **`reuse_fails` は上がらない**: プロファイル時は `build_carried_forward` がスキップされ、候補の使用カウントに影響しない。

**`--smoke-test` 実行時の例外**: スモークテストは動作確認用であり、本番RUNの状態を上書きしてはならない。`--smoke-test` 付きで実行する場合：
- `current_run_state.json` の書き込みを**すべてスキップ**すること
- ステップ5〜8（結果確認・ゲノムアーカイブ分析・改善サイクル）は**スキップ**する
- 出力先は `.cache/alpha_factory/runs/smoke/` 配下
- 完了後、Stage C通過数・B候補数をユーザーに簡潔に報告して終了

**`--smoke-test` 実行時の推奨パラメータ**:
```
--smoke-test \
--pop-size 48 --generations 3 --workers 6 \
--stage-c-windows 1 \
--dsr --cost-stress --entry-delay-test \
--stochastic-eval \
--date-pool 2025-01-06:2026-02-14 \
--is-dates 2025-10-01:2025-12-31 \
--oos-dates 2026-01-05:2026-01-30 \
--load-winners .cache/alpha_factory/runs/winners_latest.json \
--load-candidates .cache/alpha_factory/runs/candidates_latest.json \
--llm-mutation 0.05 --llm-cooldown 3
```
- **cProfileなし**: `--profile` との違い。純粋な動作確認。
- **pop-size=48**: Stage Cまで進むために必要な最小限の集団サイズ。
- **generations=3**: 動作確認には十分。
- **workers=6**: マルチワーカーの動作も確認。
- **stage-c-windows=1**: Stage C経路の確認は1ウィンドウで十分。
- **Post-Processing ON**: smokeテストではコードパスの動作確認が目的のため、`--dsr --cost-stress --entry-delay-test` をONにする。OFFだとバグに気づけない。
- **`reuse_fails` は上がらない**: スモークテスト時は `build_carried_forward` がスキップされる。
- **`*_latest.json` は更新されない**: 本番のローリング運用に影響しない。
- **報告書（`*_report.md`）は生成されない**: 動作確認では不要。

## 実行手順

### 1. 前提条件の確認

```bash
ls -lh .cache/minute_bars/ | head -10
ls -lh .cache/trading_calendar.json
```

**カレンダーが存在しない場合**：
```bash
uv run python scripts/trading/export_trading_calendar.py
```

### 2. バックグラウンド実行

`run_in_background=True` を使用してBashツールで実行。

```bash
uv run python scripts/trading/run_alpha_factory.py {{args}} --llm-mutation 0.05 --llm-cooldown 3
```

**LLM変異チャネル**: fix_b(50%), improve_b(30%), rescue_a(20%)、緊急時のみ emergency_seed が発動。
APIキーは `.env` の `ANTHROPIC_API_KEY` を使用。

実行後、`task_id`を記録してください。

起動直後に `TaskOutput(block=False)` でログファイル名を確認し、**ユーザーに報告する**：
```
✅ Run開始
- task_id: <task_id>
- ログファイル: .cache/alpha_factory/runs/<run_id>.log
  → tail -f .cache/alpha_factory/runs/<run_id>.log で確認可能
```

### 3. ログ監視ループ（完了まで繰り返す）

ログファイルはRunごとに個別生成: `.cache/alpha_factory/runs/{run_id}.log`
（`run_id` は `run_YYYYMMDD_HHMMSS` 形式。起動直後のログ出力で確認可能）

以下のサイクルを **完了検出まで繰り返す**:

**① TaskOutput で状態確認（非ブロッキング）**
```python
TaskOutput(task_id=<task_id>, block=False, timeout=60000)
```
- タスクが終了していれば結果が返る
- まだ実行中なら `status: running` 等が返る

**② ログの直近部分でエラーのみ検出**
```bash
tail -n 100 .cache/alpha_factory/runs/{run_id}.log | grep -E 'ERROR|Traceback|Exception|Stage A: 0/' | tail -5
```
grepにヒットしなければ正常進行中。**正常時はユーザーへのコメント出力を一切行わない**（context節約のため）。

**③ エラー・異常を検出した場合のみ対処**

| ログパターン | 対処 |
|-------------|------|
| `ERROR` / `Traceback` / `Exception` | プロセスが死んでいる可能性。テスト駆動で修正（下記）→ TaskStopで停止 → 再実行 |
| `Stage A: 0/N passed` が3世代以上連続 | ログ全体を確認。バグの可能性あり → テスト駆動で修正（下記）→ 再実行 |
| ログが止まっている（タイムスタンプが古い） | プロセスがハングの可能性 → `ps aux | grep run_alpha_factory` で確認 |

**重要: context節約ルール**
- 正常進行中は**何も出力しない**（ログ内容のユーザー報告・進捗コメントは不要）
- エラー検出時のみユーザーに報告する
- `tail -n 100` の全出力をcontextに読み込まない（grepでフィルタしてから読む）

**バグ修正の手順（テスト駆動）**:
1. エラーメッセージ・トレースバックから原因を特定
2. **エラーを再現するテストケースを先に書く**（AGENTS.mdのテスト命名・配置ルール準拠）:
   - テスト名は**振る舞いを説明する汎用的な名前**にする（例: `test_clip_entry_threshold_upper_bound`）
   - Run名（`run_20260219`等）、日付、セッション固有の識別子をテスト名に含めない
   - テストは対象モジュールに対応するテストファイルに配置する（例: `nsga2.py` → `tests/alpha_factory/test_nsga2.py`）
   - 既存のテストファイルがあればそこに追加する
3. テストがFAILすることを確認: `uv run pytest tests/alpha_factory/test_xxx.py::test_name -x`
4. コードを修正
5. テストがPASSすることを確認
6. 全テスト実行: `uv run pytest tests/alpha_factory/ -x`

**バグを発見・修正した場合**: `reports/run-reports/**/run-{N}.md` のバグ修正セクションに以下を記録する：
- 発見したバグの内容（エラーメッセージ・症状）
- 原因
- 再現テスト（追加したテスト名）
- 修正内容（変更ファイル・行）

**④ 待機してから①に戻る**

`TaskOutput(task_id, block=True, timeout=300000)` で最大5分ブロックしてから①に戻る。
タスクが完了していれば即座に返る。まだ実行中なら5分後にタイムアウトして再チェック。

### 4. 完了検出

以下のキーワードが出現したら完了：
- `"GA complete:"`
- `"=== Step 5: Generating report ==="`

**`--profile` 実行時**: ステップ5〜8（結果確認・ゲノムアーカイブ分析・改善サイクル）は**スキップ**する。プロファイル結果（`.prof` / `.txt`）の場所をユーザーに報告して完了。出力先は `.cache/alpha_factory/runs/profile/` 配下。

### 5. 結果確認

```bash
ls -lt .cache/alpha_factory/runs/run_*_summary.json | head -3
cat .cache/alpha_factory/runs/run_*_summary.json | tail -1 | python -m json.tool
ls -la .cache/alpha_factory/runs/winners_*.json
ls -la .cache/alpha_factory/runs/candidates_*.json
```

確認項目：Stage C通過数、B候補数、Rolling検証結果、`winners_latest.json` / `candidates_latest.json` の生成

### 6. 結果報告

```
## Alpha Factory GA実行完了

### 実行パラメータ
- 集団サイズ: [pop_size]
- 世代数: [generations]
- date-pool: [date-pool]
- Stage B日付: [dates-b]
- OOS日付: [oos-dates]
- 前回勝者seed: [load-winnersパス or なし]

### 実行結果
- Stage C通過数: [winners]
- Stage B候補保存数: [candidates]
- Rolling検証: [rolling結果]
- 判定: [SUCCESS/MARGINAL/FAIL]
- 勝者JSON: [winners_latest.jsonパス or 生成なし]
- B候補JSON: [candidates_latest.jsonパス or 生成なし]

### ベスト戦略
[summary.jsonまたはreport.mdから抜粋]

### 次のステップ
- [Stage C通過者がいれば、次回Run時に --load-winners で投入可能]
- [Stage C=0でもB候補があれば、次回Run時に --load-candidates で投入可能]
```

### 7. ゲノムアーカイブ分析

Run完了後、**`/zenigame-analyze-genome-archive` スキルを呼び出して**ゲノムアーカイブの深層分析を実施する。

```
/zenigame-analyze-genome-archive {run_id}
```

このスキルが以下の9ステップの分析を自動実行する:
- 基本統計（総個体数、A/B/C-PASS数、Best B-Sharpe）
- GA進化効果（offspring vs random A-PASS率）
- コスト構造（gross/trade vs cost/trade）
- 構造多様性（ユニーク組み合わせ数、収束度）
- パラメータ分布（time_stop, max_pos, entry_threshold等）
- トレード回数 vs Sharpe相関
- 日付窓効果（月別B-Sharpe）
- 世代別進化（A-PASS率・B-Sharpe推移）
- Top個体詳細（上位10個体のシグナル構成・パフォーマンス）

**手法ドキュメント**: `docs/alpha-factory/analysis-methodology.md` に単位・計算式・注意事項を定義済み。

**重要: 単位に注意**
- net_return / gross_return は **%単位**（`1.08` = 1.08% = 10,800円）
- sharpe は **Raw（非年率化）**
- win_rate は **比率 [0, 1]**（`0.51` = 51%）

### 8. 繰り返しモード（自動改善ループ）

ユーザーが「繰り返して」「ループして」「repeat」等を指示した場合、**ステップ7（ゲノムアーカイブ分析）完了後に自動で改善サイクルを起動する**。

**起動方法**:
```
/zenigame-improve-cycle {run_id} --repeat
```

- `{run_id}` は今回完了したRunのrun_id
- `--repeat` フラグを引数に含めることで、improve-cycle側でも繰り返しが継続される
- これにより **Run → 改善 → Run → 改善 → ...** の自動ループが実現する

**ループ停止条件**:
- ユーザーが明示的に「止めて」「stop」等を指示した場合のみ

---

## 引数の例

### スモークテスト（動作確認用・本番影響なし）
```
--smoke-test \
--pop-size 48 --generations 3 --workers 6 \
--stage-c-windows 1 \
--dsr --cost-stress --entry-delay-test \
--stochastic-eval \
--date-pool 2025-01-06:2026-02-14 \
--is-dates 2025-10-01:2025-12-31 \
--oos-dates 2026-01-05:2026-01-30 \
--load-winners .cache/alpha_factory/runs/winners_latest.json \
--load-candidates .cache/alpha_factory/runs/candidates_latest.json
```

**注意**: smokeテストではPost-Processing ON（`--dsr --cost-stress --entry-delay-test`）を維持する。これらのコードパスの動作確認が目的のため、OFFにするとバグ検出ができなくなる。

`--smoke-test` の効果:
- 出力先: `.cache/alpha_factory/runs/smoke/` に隔離
- 報告書（`*_report.md`）は生成されない
- `*_latest.json` は更新されない
- `carried_forward` は無効（`reuse_fails` に影響しない）
- cProfileなし（`--profile` との違い）
- ロックファイルは `alpha_factory_smoke.lock`（通常/profileと併走可能）

**注意**: `--profile` と `--smoke-test` は同時指定不可。

### 小規模テスト（デバッグ・動作確認用）
```
--pop-size 20 --generations 5 \
--dates-a 2026-01-06:2026-01-10 \
--dates-b 2026-01-06:2026-01-24 \
--is-dates 2026-01-06:2026-01-24 \
--oos-dates 2026-01-27:2026-02-07
```

### 標準構成（確率的評価・現行デフォルト）
```
--pop-size 48 --generations 30 \
--stochastic-eval \
--date-pool 2025-01-06:2026-02-14 \
--is-dates 2025-10-01:2025-12-31 \
--oos-dates 2026-01-05:2026-01-30 \
--workers 6
```

`--stochastic-eval` 有効時の動作:
- Stage A: 毎世代 **11-17日** のランダム窓（date-poolからサンプリング）
- Stage B: 毎世代 **22-30日** のランダム窓（date-poolから**独立に**サンプリング）
- `--dates-a` / `--dates-b` 引数は省略可（date-poolまたはis-datesをフォールバック）

### ローリング運用（前回勝者をseed）
```
--pop-size 48 --generations 30 \
--stochastic-eval \
--date-pool 2025-01-06:2026-02-14 \
--is-dates 2025-10-01:2025-12-31 \
--oos-dates 2026-01-05:2026-01-30 \
--workers 6 \
--load-winners .cache/alpha_factory/runs/winners_latest.json
```

### ローリング運用（B候補をseed、Stage C=0の場合のfallback）
```
--pop-size 48 --generations 30 \
--stochastic-eval \
--date-pool 2025-01-06:2026-02-14 \
--is-dates 2025-10-01:2025-12-31 \
--oos-dates 2026-01-05:2026-01-30 \
--workers 6 \
--load-candidates .cache/alpha_factory/runs/candidates_latest.json
```

### LLM変異OFF
```
--pop-size 48 --generations 30 \
--stochastic-eval \
--date-pool 2025-01-06:2026-02-14 \
--is-dates 2025-10-01:2025-12-31 \
--oos-dates 2026-01-05:2026-01-30 \
--workers 6 --llm-mutation 0
```

### 検証モード（定期的な品質検証用）
```
--pop-size 96 --generations 60 \
--stochastic-eval \
--date-pool 2025-01-06:2026-02-14 \
--date-a-window 14:23 \
--date-b-window 45:65 \
--is-dates 2025-01-06:2025-11-28 \
--oos-dates 2025-12-01:2026-02-14 \
--stage-c-windows 3 \
--workers 6 \
--bootstrap 0 \
--immigration 3 \
--load-winners .cache/alpha_factory/runs/winners_latest.json \
--load-candidates .cache/alpha_factory/runs/candidates_latest.json \
--cost-stress --dsr --entry-delay-test --volume-participation-check
```

**目的**: 5-10 Runに1回、C-PASS個体の堅牢性を包括検証。通常Runの2-3倍の時間がかかる。

### プロファイリング有効
```
--pop-size 48 --generations 2 \
--stochastic-eval \
--date-pool 2025-01-06:2026-02-14 \
--date-a-window 14:23 \
--date-b-window 45:65 \
--is-dates 2025-01-06:2025-12-31 \
--oos-dates 2026-01-05:2026-02-14 \
--stage-c-windows 1 \
--workers 1 \
--bootstrap 1 \
--immigration 3 \
--load-winners .cache/alpha_factory/runs/winners_latest.json \
--load-candidates .cache/alpha_factory/runs/candidates_latest.json \
--llm-mutation 0.05 --llm-cooldown 3 \
--profile --profile-top 100 --profile-max-c 10
```

**注意**: `--workers 1` はプロファイリング必須。マルチワーカーではcProfileが子プロセスの処理を計測できない。`--profile-max-c 10` でStage C評価個体数を制限し、プロファイル時間を短縮。

詳細は [docs/alpha-factory-profiling.md](docs/alpha-factory-profiling.md) を参照。

## 確率的評価オプション

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--stochastic-eval` | OFF | 確率的評価を有効化 |
| `--date-pool` | dates-bと同じ | 日付サンプリングプール (YYYY-MM-DD:YYYY-MM-DD) |
| `--date-a-window` | 11:17 | Stage A日数ウィンドウ MIN:MAX |
| `--date-b-window` | 22:30 | Stage B日数ウィンドウ MIN:MAX |
| `--stage-c-windows` | 3 | Stage Cマルチウィンドウ数 |
| `--stage-c-max-per-combo` | 5 | Stage Cコンボ内最大評価数（0=無制限） |

**データプール拡張時（~245営業日）の推奨値**: `--date-a-window 14:23 --date-b-window 30:45`

## Warmstartオプション（T078）

前RunのParquetアーカイブから上位ゲノムを初期集団に注入するオプション。Gen0-8の冷間始動問題を解消し、収束を早める。

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--warmstart-auto` | OFF | 最新RunのParquetアーカイブから自動的にWarmstartを実行 |
| `--warmstart-run-id` | なし | 特定のrun_idを指定してWarmstartを実行（省略時は最新を自動検出、`--warmstart-auto`必須） |
| `--warmstart-top-n` | `20` | Warmstartで注入する上位個体数（Stage B-Sharpe降順） |
| `--warmstart-min-b-sharpe` | `0.0` | WarmstartのB-Sharpe下限フィルタ（この値未満は除外） |
| `--warmstart-max-per-combo` | `8` | 同一シグナル組成の最大個体数（0=制限なし）。R145で追加 |
| `--warmstart-min-b-trade-count` | `0` | Stage B trade_count下限フィルタ（0=無効）。低頻度個体のseed混入防止。R195で追加 |

**使用例（前RunのB通過上位20個体を注入）**:
```
--warmstart-auto --warmstart-top-n 20 --warmstart-min-b-sharpe 0.05
```

**注意**: `--warmstart-auto` が有効な場合、`winner_genomes` として注入されるため `--load-winners` より優先度が高い。アーカイブが見つからない場合はコールドスタートにフォールバック。

## GA Directorオプション（T258）

LLM駆動のプリミティブ選択重み制御。Run開始前にLLMが過去統計からプリミティブの重みを決定する。

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--director-mode` | `active` | Directorモード（`off`=無効, `shadow`=ログのみ/weight未適用, `active`=weight適用） |

- `active`: LLMが重みを計算し、GA（operators/population/immigration）に実適用
- `shadow`: LLMが重みを計算しログ記録するが、GAには反映しない（効果検証用）
- `off`: Director完全無効

**使用例**:
```
--director-mode shadow    # ログのみで効果を事前検証
--director-mode off       # Director無効化
```

その他のDirector設定（model, window_runs, guardrails等）は `config/alpha_factory/default.yaml` の `director` セクションで制御。

## Market Impactオプション（T019）

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--market-impact` | OFF | VPR依存slippageモデルを有効化。`effective_bps = base_bps + impact_coeff * sqrt(VPR)` |
| `--market-impact-base-bps` | `3.0` | ベースslippage（bps）。VPRが0に近いときのフロア |
| `--market-impact-coeff` | `15.0` | sqrt(VPR)係数。大きいほどVPRに対するslippage感度が高い |

エントリーバーとエグジットバーそれぞれの出来高に基づいてスリッページを個別計算する。デフォルトOFFでは従来の固定slippage（10bps）を使用。

### 部分約定シミュレーション (T023)

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--partial-fill` | OFF | 部分約定シミュレーションを有効化 |
| `--fill-capacity` | `0.03` | 約定可能VPR閾値（0.03=3%）。`fill_rate = min(1.0, fill_capacity / vpr)` |

VPR Cap適用後の注文数量に約定率を適用。`fill_rate < 1.0` の場合は `filled_qty = int(quantity * fill_rate)` を100株単位に切り下げ。1ロット未満はエントリースキップ。`--partial-fill` フラグなしでは無効（fill_capacity=0.0）。

### 最小出来高閾値 (T186)

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--min-bar-volume` | `100` | 最小出来高閾値（株数）。エントリーシグナルバーの出来高がこの値未満の場合スキップ。0=無効 |

VPR Capチェックの前に適用。薄商いバーでの約定不確実性を排除する。

## Stage C後処理オプション（Post-Processing）

Stage C通過個体に対する追加検証。GA最適化には影響せず、事後評価のみ。

**⚠️ 運用方針: 通常RunではPost-Processing OFF（高速モード）**

Post-Processing（cost-stress, dsr, entry-delay-test, volume-participation-check）は
C-PASS個体数に比例して大きな計算コストが発生する（Run 64実績: GA本体80分 vs Post-Processing 151分）。
通常のGA探索Runでは**全てOFFにして高速ループを優先**し、
5-10 Runに1回の頻度で「検証Run」としてPost-Processingを有効化する。

| モード | Post-Processing | 想定時間（96pop×60gen） | 用途 |
|--------|----------------|----------------------|------|
| **高速モード（デフォルト）** | 全OFF | ~80分 | 通常の探索ループ |
| **検証モード** | 全ON | ~230分 | 定期的な品質検証 |

**検証Runの実行方法**: 通常Runの引数に以下を追加するだけ。
```
--cost-stress --dsr --entry-delay-test --volume-participation-check
```

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--cost-stress` | OFF | コストストレステストを有効化（1.5x/2.0xスリッページ耐性を評価） |
| `--cost-stress-multipliers` | `1.5,2.0` | コストストレス倍率（カンマ区切り） |
| `--dsr` | OFF | Deflated Sharpe Ratio計算を有効化（多重検定考慮の統計的有意性評価） |
| `--entry-delay-test` | OFF | エントリー遅延テストを有効化（シグナル遅延耐性を検証） |
| `--entry-delay-bars` | `2` | エントリー遅延テストのバー数（2=2分遅延相当） |

## Validate-only モード（検証専用実行）

GAをスキップし、過去RunのwinnersファイルをロードしてPost-Processingのみ実行するモード。
3 Run前のwinnersに対して堅牢性検証だけを走らせるといった使い方が可能。

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--validate-only` | OFF | Validate-onlyモードを有効化（GA実行をスキップ） |
| `--validate-winners` | なし | 検証対象のwinners JSONパス（必須） |

**使用例**:
```bash
uv run python scripts/trading/run_alpha_factory.py \
  --validate-only \
  --validate-winners .cache/alpha_factory/runs/winners_run_20260222_050640.json \
  --cost-stress --dsr --entry-delay-test --volume-participation-check \
  --oos-dates 2025-12-01:2026-02-14 \
  --is-dates 2025-01-06:2025-11-28 \
  --dates-b 2025-01-06:2026-02-14 \
  --stochastic-eval --date-pool 2025-01-06:2026-02-14 \
  --workers 6
```

**注意事項**:
- `--validate-winners` は過去の任意の `winners_run_*.json` を指定可能
- `--profile` / `--smoke-test` とは排他（併用不可）
- 日付パラメータ（`--oos-dates` 等）は Post-Processing に必要（Cost Stress等がOOS期間でバックテスト再実行するため）
- 実行時間はPost-Processing部分のみ（winners 700個体で約150分）

**Skill実行時の振る舞い**: validate-onlyモード時はステップ2のGA実行がスキップされ、ステップ5-6（結果確認・報告）に直接進む。ステップ7（ゲノムアーカイブ分析）は新たなアーカイブが生成されないためスキップ。

## プロファイリングオプション

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--profile` | OFF | cProfileによるプロファイリングを有効化 |
| `--profile-top` | 50 | プロファイル結果の上位表示件数 |
| `--profile-max-c` | 10 | プロファイル時のStage C評価最大個体数（0=無制限。`--profile` 有効時のみ作用） |

## ログ監視のポイント

### 正常な進捗例
```
[INFO] nsga2: Generation 1/30
[INFO] nsga2: Stage A: 20/48 passed
[INFO] nsga2: Stage B: 5/20 passed
[INFO] nsga2: Stage C: 2/5 passed
[INFO] serialization: Winners saved: 2 genomes to .cache/alpha_factory/runs/winners_run_xxx.json
```

**ローリング運用時**: `Rolling population: N winners, ...` でseed投入を確認。

### エラー例と対処
- `ERROR: No trading calendar found` → `export_trading_calendar.py`を実行
- `ERROR: Failed to load minute bars` → データの存在確認
- `ERROR: LLM API rate limit exceeded` → `.env`のAPIキー確認

## 実行時間の目安

| 設定 | pop-size | generations | Workers | Post-Proc | 実行時間 |
|------|----------|-------------|---------|-----------|----------|
| 小規模テスト | 20 | 5 | 1 | OFF | 5-10分 |
| 標準（高速） | 48 | 30 | 6 | OFF | 20-40分 |
| 大規模（高速） | 96 | 60 | 6 | OFF | 60-90分 |
| 大規模（検証） | 96 | 60 | 6 | 全ON | 150-250分 |

## トラブルシューティング

- **バックグラウンド実行が失敗** → `run_in_background=True`を確認
- **ログが更新されない** → `ps aux | grep run_alpha_factory` でプロセス確認
- **Stage C通過数が0** → 日付範囲・銘柄データを確認、`--bootstrap 3 --immigration 3`を追加

## 参考情報

- 詳細ドキュメント: [docs/alpha-factory.md](docs/alpha-factory.md)
- 実行ログ: `.cache/alpha_factory/runs/alpha_factory.log`
- 結果: `.cache/alpha_factory/runs/<run_id>/`
