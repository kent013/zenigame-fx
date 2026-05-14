# 詳細設計: GA 並列ワーカーのメモリ過剰使用の改善（root cause 確定版）

## 改訂履歴

- **初版（2026-05-14）**: Phase 0 計測先行 → レバー A/B/C の段階設計（Codex 詳細設計レビュー Round 3 APPROVED）。
- **本版（2026-05-15）**: ライブ RUN（`run_20260514_144214`）の worker を直接実測し **root cause を確定**。初版のレバー A/B/C（`_PROC_AUX_CACHE` / `PriceBar __slots__` / mmap 共有ストア）は **いずれも的外れ**と判明したため、設計を実測ベースで全面改訂。`devnotes/.../detailed-design-v1.md` に初版を退避。

---

## 使命・制約（絶対遵守）

本タスクは live_criteria を直接動かさない**探索基盤の制約解除**（OOM/swap リスク除去・複数ペア swim-lane 拡張の前提確保）。`live_criteria` / stage gate 閾値 / dataset window / fitness 関数は一切変更しない。決定論契約 L1 selection / L2 row-order を厳守する。

---

## Phase 0 相当の調査結果（ライブ RUN 実測 — root cause 確定）

初版が「Phase 0 で計測する」としていた内容を、稼働中の RUN を使って実測した。

### Fact（観察事実）

1. **ライブ worker の vmmap**（`run_20260514_144214` の worker PID 55107、gen 17 時点）:
   - Physical footprint 7.5G（peak 9.2G）、RESIDENT 5.8G / DIRTY 5.4G / SWAPPED 2.0G
   - **システム malloc ゾーン（`MALLOC_SMALL/TINY/LARGE` 合計）は ~490MB しかない** — numpy の大配列はここに出るはずだが出ていない
   - **`VM_ALLOCATE` 領域が 7,241 個、各きっかり 1024K、`SM=PRV`（private）** — これが 5.1G resident + 2.0G swap の本体
2. **`PriceBar` 1 個の実測**: `tracemalloc` で 1,225 bytes/bar。dataset 全体 328,883 bars でも 1 コピー 384MB、2 worker で 0.75GB。
3. **再現テスト**: `list[tuple[datetime, Decimal]]` を大量生成 → `del` + `gc.collect()` しても RSS は起動時（16MB）に戻らず ~221MB に張り付く。
4. プロセスは `cpython-3.11.15`。
5. `evaluate_stage_b` の fold ループ（`stage_gate.py:1389-1393`）は `aux_bundle.align_to(test_bars)` をループ毎に生成し局所変数で捨てる（GC 対象、蓄積しない）。
6. `_bars_cache`（`primitives/_bars_cache.py`）は `MAX_ENTRIES=8` の LRU で上限あり。`_PROC_AUX_CACHE` / `AuxAlignmentCache` は安定オブジェクト（`bars_a/b/holdout`）キーで実質 3 エントリ上限。

### Interpretation（解釈・root cause）

**worker の 7GB は pymalloc アリーナの断片化**。

- CPython 3.11 は pymalloc アリーナサイズを 256K → **1MB** に変更済み。pymalloc アリーナは `obmalloc.c` が `VM_ALLOCATE`（mmap）で直接確保するため、システム `MALLOC_*` ゾーンには出ない。→ Fact 1 の「7,241 × 1024K の `VM_ALLOCATE` private 領域」は **pymalloc アリーナそのもの**。
- pymalloc アリーナに入るのは ≤512 byte の小オブジェクト = `Decimal` / `datetime` / 小 `tuple` / `PriceBar` / `Ohlc`。
- **メカニズム**: `run_backtest` が genome × fold × 世代ごとに `equity_curve: list[tuple[datetime, Decimal]]`（Stage B IS monitor で ~20万点、fold 約 33 本 × ~2万点）と `trades`（`Decimal` だらけ）を生成。1 genome の Stage B 評価だけで ~90万個の小オブジェクトを churn する。これらは評価後に GC されるが、**pymalloc はアリーナが 100% 空になるまで OS に返さない**（Fact 3 で実証）。churn が続くと、わずかな長寿命オブジェクトが各アリーナに散らばってアリーナをピン留めし、断片化として 7,000 個以上のアリーナが resident に残る。
- リーク（参照保持）ではなく **アロケータ断片化**。`gc.collect()` では解消しない（オブジェクトは回収済み、アリーナが返らない）。
- worker でのみ起きて main で起きないのは、実バックテスト（`run_backtest`）を回すのが worker だけだから。

### 初版レバーの再評価（C8 — 的外れの明示）

| 初版レバー | 再評価 | 根拠 |
|---|---|---|
| A: `_PROC_AUX_CACHE` ライフサイクル管理 | **空振り** | 蓄積する cache は存在しない（Fact 5/6） |
| B: `PriceBar` / `Ohlc` `__slots__` | **ほぼ空振り** | bars は 384MB/worker しかない（Fact 2）。7GB の主因ではない |
| C: mmap SoA 共有ストア | **ほぼ空振り** | 同上、削減できるのは 384MB だけ |

初版の「まず計測」判断自体は正しかった（これを検出できた）。レバーの当て先が全て bars/cache に偏っていたのが誤り。

---

## 施策一覧（改訂版）

| # | 施策名 | 変更ファイル | 種別 |
|---|--------|------------|------|
| 1 | **`maxtasksperchild` による worker 定期リサイクル** | `parallel_eval.py` / `config.py` / `run_ga.py` / `config/alpha_factory/default.yaml` | 本タスクで実装 |
| 2 | per-worker メモリ前提コメントの実態修正 | `config.py` / `config/alpha_factory/default.yaml` | 本タスクで実装（施策 1 に付随） |
| 3 | バックテスト hot path の `Decimal` churn 削減（本丸） | `backtest/engine.py` ほか | **別タスク（follow-up）** |

---

## 施策 1: `maxtasksperchild` による worker 定期リサイクル

### 方針
`multiprocessing.Pool` の `maxtasksperchild` を設定し、worker が一定タスク数を処理したら**プロセスごと退役→新規 spawn** させる。退役時に断片化したアリーナは OS に完全返却される。新 worker は同じ initargs で `_init_worker` を再実行するため状態は同一。

これは pymalloc 断片化に対する**標準的かつ低リスクな緩和策**（CPython 公式の Pool 機能）。本丸（施策 3 = `Decimal` churn そのものの削減）は backtest engine 改修を要する別タスクだが、施策 1 だけで peak RSS を「断片化が溜まり切る前」に頭打ちできる。

### 1-1. `GenomeEvaluator` に `maxtasksperchild` を配線

#### 変更箇所
`src/alpha_factory/parallel_eval.py` `GenomeEvaluator.__init__`（L546-577）

#### 変更内容
- keyword-only 引数 `max_tasks_per_child: int | None = None` を追加（default `None` = **既存挙動と完全互換** = Pool に `maxtasksperchild=None` を渡す = リサイクルなし）。
- `max_workers > 1` のとき `mp_ctx.Pool(...)` の引数に `maxtasksperchild=max_tasks_per_child` を追加。
- `__init__` 冒頭で `max_tasks_per_child is not None and max_tasks_per_child < 1` を `ValueError` で弾く。
- `self._max_tasks_per_child` に保持（observability / テスト用）。

```python
def __init__(
    self,
    max_workers: int,
    stage_gate_cfg: StageGateConfig,
    cross_pair_cfg: CrossPairConfig,
    prim_evaluator: RegistryEvaluator,
    lane_contexts: Mapping[str, LaneEvalContext],
    *,
    max_tasks_per_child: int | None = None,
) -> None:
    if max_workers < 1:
        raise ValueError(f"max_workers must be >= 1: {max_workers}")
    if max_tasks_per_child is not None and max_tasks_per_child < 1:
        raise ValueError(
            f"max_tasks_per_child must be >= 1 or None: {max_tasks_per_child}"
        )
    ...
    self._max_tasks_per_child = max_tasks_per_child
    if max_workers > 1:
        mp_ctx = multiprocessing.get_context("spawn")
        self._pool = mp_ctx.Pool(
            processes=max_workers,
            initializer=_init_worker,
            initargs=(...),
            maxtasksperchild=max_tasks_per_child,  # None = 従来通りリサイクルなし
        )
```

#### 1-1b. `evaluate_population` に `chunksize=1` を明示（Codex impl-review Round 2 [Critical] 反映）
`maxtasksperchild` は `Pool` の**タスク単位**でカウントされる。`pool.map` の default chunking では 1 タスク = 複数 genome の chunk（例: population 96 / 2 worker → chunksize≈12）になり、`max_tasks_per_child` が genome 数と大きく乖離してリサイクルが意図の数十倍遅延する（pymalloc 断片化の頭打ち効果が live RUN で効かない）。
→ `evaluate_population` の `pool.map(_eval_genome_worker, args)` を **`chunksize=1`** にし、1 タスク = 1 genome に固定する。これにより `max_tasks_per_child` は「何 genome 評価ごとに worker を退役させるか」を直接表し、自動導出式 `2*population_size//max_workers`（約 2 世代ごと）が設計通りに機能する。`pool.map` は `chunksize` に依らず入力順で結果を返すため L2 row-order は不変。

#### 決定論への影響: なし
- リサイクルされた worker は Pool が保持する同一 initargs で `_init_worker` を再実行 → `ensure_registered()` + module-global 再設定で**状態は完全同一**。
- `evaluate_genome` は純粋関数。`pool.map` は worker のリサイクル有無・`chunksize` に関わらず**入力順で結果を返す**（L2 row-order 保持）。
- `_PROC_AUX_CACHE` はリサイクル後の新 worker で空から再構築されるが、整列結果の**値は同一**（CPU 再計算のみ、L1/L2 不変）。
- → L1 selection / L2 row-order 契約は維持される。決定論テストで verify する。

### 1-2. config 配線

#### `src/alpha_factory/config.py`
- `GAConfig` に `max_tasks_per_child: int | None = None` を追加。
- `__post_init__` に検証追加: `if self.max_tasks_per_child is not None and self.max_tasks_per_child < 1: raise ValueError(...)`。
- `_build_ga` に `max_tasks_per_child=(int(v) if (v := raw.get("max_tasks_per_child")) is not None else None)` を追加。

#### `scripts/alpha_factory/run_ga.py`
- CLI `--max-tasks-per-child`（`type=int, default=None`）を追加。
- `_args_to_overrides` の `"ga"` dict に `"max_tasks_per_child": args.max_tasks_per_child` を追加（`None` は `_deep_merge` が skip するため yaml 値を clobber しない）。
- `GenomeEvaluator` 構築（L1846）の直前で**実効値を導出**:
  - `cfg.ga.max_tasks_per_child` が非 None → その値
  - None → **自動導出**: `max(1, (2 * cfg.ga.population_size) // max(1, cfg.ga.max_workers))`
    （= 各 worker を「およそ 2 世代ごと」にリサイクルする。pop 96 / mw 2 → 96、pop 40 / mw 2 → 40）
  - 起動時に `logger.info("ga.max_tasks_per_child", value=..., source="config"|"auto")` を 1 行出力（observability）。
- `GenomeEvaluator(..., max_tasks_per_child=effective_value)` を渡す。
- `max_workers == 1`（sequential、pool is None）のときは `maxtasksperchild` は無意味（Pool が無い）→ 導出値は持つが未使用、ログには出す。

#### `config/alpha_factory/default.yaml`
- `ga.max_tasks_per_child:` キーを追加。値は `null`（= 自動導出）。コメントで「pymalloc アリーナ断片化対策の worker リサイクル間隔。null = 2*population_size//max_workers で自動導出。devnotes/20260514-2045-ga-worker-memory/ 参照」を明記。

### 1-3. パラメータ伝搬の 4 段接続チェック（禁止事項 8）
`config (yaml) → GAConfig → run_ga 実効値導出 → GenomeEvaluator → Pool` の全段を接続する。archive スキーマ（GENOMES_SCHEMA）には影響しない（GA hyper-param であり genome 単位の記録対象ではない）。`summary.json` への記録は任意だが、observability のため `parallel_config.max_tasks_per_child`（実効値）を既存 `parallel_config` ブロック配下に追加する（トップレベルキー集合は不変）。

### テスト計画（施策 1）
- `tests/alpha_factory/test_parallel_eval.py`:
  - `test_genome_evaluator_rejects_invalid_max_tasks_per_child`: `max_tasks_per_child=0` で `ValueError`
  - `test_genome_evaluator_recycles_workers_after_max_tasks`: `max_workers=2, max_tasks_per_child=2` で構築 → `pool_pids` を記録 → 多数 genome を `evaluate_population` → `pool_pids` が変化（= リサイクル発生）したことを確認
  - `test_genome_evaluator_no_recycle_when_none`: `max_tasks_per_child=None` で `pool_pids` が評価前後で不変（既存挙動）
- `tests/scripts/test_run_ga_parallel.py`:
  - 既存テストヘルパに `max_tasks_per_child` 引数を追加（default None で既存テスト不変）
  - `test_parallel_determinism_preserved_with_worker_recycling`: `max_tasks_per_child` を population より小さい値（例 3）にして `max_workers=2` で実行 → `max_workers=1` と **best.name / fitness / selection_score / live_criteria / L2 数値 column が完全一致**（リサイクルが決定論を壊さないことの verify）
  - `test_summary_records_max_tasks_per_child`: `parallel_config.max_tasks_per_child` が summary に出力され、トップレベルキー集合は現行と一致
- `uv run pytest tests/alpha_factory/test_parallel_eval.py tests/scripts/test_run_ga_parallel.py` / `uv run ruff check src/ tests/` / `uv run mypy src/`

### リスク（施策 1）
- **spawn overhead**: リサイクルのたびに新 worker が initargs（`lane_contexts` = bars 実体を含む）を再 unpickle する。自動導出値（~2 世代ごと）なら、N 回の評価に対し 1 回の spawn コストで償却される。N を極端に小さくすると spawn thrash になるため、`__post_init__` での下限 1 は許すが、運用上は自動導出 or population 規模の値を推奨（default.yaml コメントに明記）。
- **`chunksize=1` の dispatch 数増加**（Codex impl-review Round 3 [Suggestion] 反映）: `chunksize=1` で `pool.map` の task dispatch 数が population_size に等しくなる（default chunking 比で増加）。backtest 1 genome の評価コストが十分重い現状では IPC overhead は無視できるが、将来 smoke 用の極軽量評価経路を追加する場合は wall-time 監視対象として残す。
- `pool_pids`（`Pool._pool` private API 経由）はリサイクルで pid が入れ替わるが、`measure_peak_rss_mb` は呼び出し時点で動的取得する設計のため整合する（best-effort RSS 計測、correctness には無関係）。

---

## 施策 2: per-worker メモリ前提コメントの実態修正

`config.py:152` / `config/alpha_factory/default.yaml:63` / `scripts/alpha_factory/run_ga.py:1348` の「1 worker ~400MB」前提コメントは、実測（5.5〜8.7GB、root cause = pymalloc 断片化）と乖離している。本施策では:

- 上記 3 箇所のコメントを「実測 per-worker RSS は pymalloc 断片化により数 GB 規模になり得る。`maxtasksperchild`（施策 1）で頭打ちする。正確な per-worker 試算は施策 3 完了後に再評価」と実態整合させる。
- **`max_workers` の default 値（2）は変更しない**。`_check_memory_budget` の `// 400` 式の本格修正（初版の 4 項モデル）は施策 3 とセットで別タスクに送る（本タスクのスコープは施策 1 の付随コメント修正まで）。

### テスト計画（施策 2）
コメントのみの変更のためテストなし。`ruff` / `mypy` 通過のみ確認。

---

## 施策 3: バックテスト hot path の `Decimal` churn 削減（本丸・別タスク）

root cause の本丸。`run_backtest` / `compute_metrics` が生成する `equity_curve: list[tuple[datetime, Decimal]]` や `trades` の `Decimal` churn を構造的に減らす。候補方向（別タスクの概念設計で詰める）:

- `equity_curve` を `list[tuple[datetime, Decimal]]` → numpy 構造化配列 / 並列 ndarray 化（datetime は int64 epoch、equity は固定スケール int64 or float64）
- backtest engine 内部の中間 `Decimal` 演算を、精度が要求される箇所（約定価格・手数料）と要求されない箇所（集計・統計）に分離し、後者を float / numpy 化

これは backtest engine の広範な改修（`PriceBar` を消費する 36 ファイル波及の懸念あり）で correctness リスク（金額計算の精度）を伴うため、**独立した設計サイクル（概念設計 → Codex レビュー → 詳細設計）が必要**。本タスクでは扱わない。施策 1 で peak を頭打ちした上で、施策 3 を別タスクとして起票する。

---

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | incremental（施策 1 → 施策 2、いずれも小さく独立） |
| 競合リスク | 施策 1 は `parallel_eval.py` / `config.py` / `run_ga.py` を触るが、いずれも局所的な引数追加。並行する他タスクとの干渉は低い |
| 想定実装時間 | 施策 1: 短〜中 / 施策 2: 短 |

## 実装順序

1. 施策 1: `GenomeEvaluator` の `maxtasksperchild` 配線 → config / CLI / yaml 配線 → テスト
2. 施策 2: コメント実態修正
3. 決定論テスト（`test_run_ga_parallel.py`）+ `ruff` + `mypy` 全通過を確認
4. Codex で実装差分レビュー（`parallel_eval.py` は L1/L2 決定論クリティカルなため必須）
5. 施策 3 を別タスクとして起票（`/zenigame-fx-todo-add`）
