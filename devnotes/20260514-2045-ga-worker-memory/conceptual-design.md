# 概念設計: GA 並列ワーカーのメモリ過剰使用の改善

## Phase -1: 前提検証結果（C1 Design-first / C4 前提明示）

Codex Round 1 が実施できなかった docs / devnotes / git log の照合を先行実施した。結果:

| 検証項目 | 結果 (Fact) | 出典 |
|---|---|---|
| spawn 採用理由 | 原設計 §4.3 は「zenigame と同じ `multiprocessing.Pool` (spawn context) を採用」とのみ記載。**fork を積極排除した理由の記述は無い**（検討されていないだけ）。macOS spawn の `__main__` ガード対応の言及あり（§6 リスク表）。 | `devnotes/20260427-1114-ga-parallel-workers/conceptual-design.md` §4.3, §6 |
| 決定論契約 | L1 selection（`fitness_pen` / `best_name` / `live_criteria_passed`）と L2 row-order は「必須保証」。L3 bit equivalence は「非保証」。同値性テスト `tests/scripts/test_run_ga_parallel.py` が既に存在。 | 同 §4.0 / §7 |
| 原設計のメモリ試算 | §6.1 で 1 worker **~320-370MB** と試算。前提は「EUR_JPY 6ヶ月 M1 ≈ 260,000 bars」「PriceBar ≈ 200-400 bytes/bar」。**原設計自身が運用ガードとして「`max_rss_mb_per_worker` が 2.1GB を超えたら `max_workers` を下げる」「2.1GB 超で SharedBarStore タスクを起票」と明記**していた。 | 同 §6.1 |
| `_check_memory_budget` 現行式 | `recommended_max = (available_mb - 4096) // 400`。単一係数 400MB/worker の線形モデル。 | `scripts/alpha_factory/run_ga.py:1344-1369` |
| `AuxAlignmentCache` の寿命 | `reset()` メソッドは存在。`parallel_eval.py` の process-local `_PROC_AUX_CACHE` 経由でも `_reset_proc_aux_cache()` が定義済みだが RUN 中の呼び出し経路が無い。 | `src/alpha_factory/aux_loader.py:241-267` / `parallel_eval.py:230-235` |
| aux re-align の導入時期 | `aux_bundle` の Stage B fold ごと re-align は **T057（commit `ea56484`）で原設計（T052, commit `deb6b20`）の後に追加**。原設計 §6.1 のメモリ試算は T057 の aux re-align・`aux_pair_bars_index` を含んでいない。 | `git log -S` |

> 実装タスク化時には、Phase -1 各行の出典へ確定 commit hash / 行番号を付与し直して固定すること（Codex Round 2 Warning #8 反映）。本表の行番号は概念設計時点のスナップショット。

**前提検証からの結論（Interpretation）**: 実測 `max_rss_mb_per_worker` 5.5〜8.7GB は、原設計 §6.1 が自ら定めた運用ガード閾値（2.1GB）を約 3〜4 倍超過しており、**原設計の「SharedBarStore タスク起票条件」は既に充足されている**。また原設計のメモリ試算（370MB）は T057 の aux re-align を勘定していないため、乖離の一因が T057 由来である可能性が高い（要計測確定）。

## 背景・課題

### 観察事実 (Fact)

- `config/alpha_factory/default.yaml` の `ga.max_workers` は 2。コメントの想定は「1 worker ~400MB × 2 + main ≈ 1.2GB」。
- `src/alpha_factory/config.py:152` / `scripts/alpha_factory/run_ga.py:1348` も「1 worker ~400MB」前提で `_check_memory_budget` の推奨値式 (`(available_mb - 4096) // 400`) を組んでいる。
- 一方、本スキルの Codex レビュー env note は「24GB × 6 ワーカー（1 ワーカー最大約 3GB）」と記載。コードベース内で per-worker メモリ前提が 400MB / 3GB と分裂している。
- 実測 `summary.json` → `max_rss_mb_per_worker`（直近 10 Run, run-70〜run-79）: 5,562〜8,718 MB。run-76 が最大 8,718 MB。
- `run-79.md` の dataset: EUR_JPY M1 bars `bars=328883`、`bars_holdout=60232`、population=96 / generations=60。

### 構造的観察 (Fact)

- `src/domain/price.py`: `PriceBar` は frozen dataclass だが `__slots__` 無し。1 bar が保持するのは `pair_name:str` / `bar_time:datetime` / `bid:Ohlc` / `ask:Ohlc` / `volume:int` / `complete:bool`。`Ohlc` も `__slots__` 無し frozen dataclass で `Decimal` を 4 個保持。1 PriceBar = 親 1 + datetime 1 + Ohlc 2 + Decimal 8 ≈ Python オブジェクト 12 個。
- `src/alpha_factory/parallel_eval.py:566-577`: `multiprocessing.get_context("spawn")` の `Pool` を使い、`_init_worker` の `initargs` で `lane_contexts`（各 lane の `bars_a` / `bars_b` / `bars_holdout` のフル tuple + `aux_bundle`）を worker ごとに pickle で完全コピーして配布。spawn なので fork の copy-on-write 共有は効かない。
- `aux_bundle`（`AuxBundle`）は `aux_pair_bars_index: dict[str, dict[datetime, PriceBar]]` を持ち、cross-pair 用ペアの M1 bar を `PriceBar` の dict として保持する。`evaluate_stage_b` には raw `aux_bundle` がそのまま渡され fold ごとに再 align される。
- `parallel_eval.py:230` の `_PROC_AUX_CACHE: dict[int, AuxAlignmentCache]` は process-local。内側 `AuxAlignmentCache._cache` は `id(bars)` キーで `AlignedAuxBundle` をキャッシュ。RUN 中の破棄経路が無い。
- 比較対象: 姉妹プロジェクト zenigame の `src/trading/alpha_factory/evaluation/shared_bar_store.py` は分足を SoA numpy 配列で 50 byte/bar の mmap ファイルに連続配置し、全 worker が read-only attach（ゼロコピー共有）。

### 仮説 (Interpretation)

GA worker のメモリ肥大の構造的根因は次の掛け算と推定する:

1. bar 表現の低メモリ密度: `PriceBar`（Decimal×8 / `__slots__` 無し）は zenigame の SoA 50 byte/bar に対し重い。
2. spawn による無共有複製: bars / aux を worker 数だけフルコピーし RUN 中保持。
3. 寿命蓄積: `_PROC_AUX_CACHE` が stage / fold ごとの整列結果を RUN 寿命で単調蓄積している可能性。

ただし「実測 7GB のうち各要素が何 GB を占めるか」「resident（OS 視点）と Python object bytes のどちらが支配的か」は未計測であり、現時点では **INCONCLUSIVE**。値を弄る前に内訳を確定させる。

## 成功条件（Warning #1 反映 — 明文化）

本改善の成功は以下 4 本で判定する:

1. **評価不変**: 同一 seed・同一 config・同一 dataset で、**4 条件比較**（baseline `max_workers=1` / baseline `max_workers=2` / changed `max_workers=1` / changed `max_workers=2`）の全組で genome ranking / stage pass-fail / live_criteria 判定 / cross-pair 判定が完全一致（= L1/L2 決定論契約の維持。Codex Round 2 Warning #5 反映）。
2. **swap / OOM 解消**: 24GB マシンで `max_workers=2` 実行時に swap / OOM が発生しない（実測 `max_rss_mb_per_worker` を原設計の運用ガード水準 2.1GB に近づける、最低でも実測値を有意に下げる）。
3. **実行時間の非劣化**（Codex Round 2 Warning #4 反映 — 2 段で評価）: (3a) **CPU-only 比較**（swap が発生しない小規模 RUN）で総実行時間が許容範囲内（cache eviction / mmap 化の CPU トレードオフを許容する閾値を Phase 0 後に設定）。(3b) **実運用 wall-clock**（フル RUN）は swap 回避により悪化しない、改善が見込まれる。
4. **pair 拡張の前提確保**: 複数通貨ペア swim-lane 化時の per-worker メモリ試算が、4 項モデル（後述）で 24GB に収まる見通しを立てられる。

## 改善アイデア

「重い表現 × 無共有複製 × 寿命蓄積」を、**計測で内訳を確定 → 効果の大きいレバーから順に適用**する段階構成で解消する。いきなり大規模なアーキテクチャ改修には踏み込まない。

### Phase 0: メモリ内訳の計測（必須・先行）

**二層計測**（Critical #3 反映）。OS 視点の実害と Python object 内訳を分離して取る:

- **層 1（主指標）— OS resident メモリ**: worker プロセスの `RSS`、可能なら `USS`（共有ページを除いた専有量。`psutil.Process().memory_full_info()`）も取得。shared store 導入後の評価には共有ページ控除が必須のため。成果物は「resident bytes」。
- **層 2（補助）— Python object 内訳**: `tracemalloc` スナップショット差分または主要コンテナの再帰サイズ集計で、① target pair bars（`bars_a/b/holdout`）② `aux_bundle`（特に `aux_pair_bars_index`）③ `_PROC_AUX_CACHE` ④ backtest engine 作業セット ⑤ その他 に分解。成果物は「Python object bytes」。
- 計測ポイント: `_init_worker` 直後 / Stage A 後 / Stage B 後（fold 蓄積後）/ Stage C 後 / 世代境界。`_PROC_AUX_CACHE` は entry 数とサイズの推移も記録（Warning #5 の判断材料）。
- **計測マトリクス**（Warning #4 反映）: 「対象 pair 代表例（少なくとも EUR_JPY）× aux あり / なし × `max_workers` 1 / 2」。aux 有無の差分で T057 由来の寄与を切り分ける。
- 実装は決定論を壊さない・既存ロジックを変えない計測専用コードとし、環境変数または CLI フラグで opt-in。
- **成果物の表は 2 種に分離**（Codex Round 2 Warning #3 反映）: (i) **プロセス単位の RSS / USS**（OS 視点、要素別に割らない）、(ii) **要素別 object bytes**（Python object 内訳）。resident メモリの要素別帰属は直接は取れないため、計測マトリクスの差分実験（aux あり/なしの RSS 差など）で推定する、と明記する。これが Phase 1 のレバー選択の根拠。

### Phase 1: 内訳に応じた構造レバー（Phase 0 結果でゲート）

Phase 0 の内訳に応じて以下から選択適用する。優先順位は **A → B → C**（Warning #3 反映: fork は本線でなく実験枝）。各レバーは独立に効果検証可能で、各々に決定論ゲート（後述）を必須通過とする。

- **レバー A — `_PROC_AUX_CACHE` のライフサイクル管理**: Phase 0 で `_PROC_AUX_CACHE` の単調蓄積が確認された場合に適用。**全消去（世代境界 reset）はせず**、まず Phase 0 の cache size 計測結果に基づき (a-1) stage 単位の bounded eviction か (a-2) LRU 上限か を比較検討する（Warning #5 反映: 全消去は再整列の CPU コストを増やすため）。整列結果の「値」は変えず破棄タイミング / 上限のみ変更する。
- **レバー B — bar 表現の軽量化**: Phase 0 で `PriceBar` / `Ohlc` 自体の占有比率が高い場合のみ適用（Warning #4 反映）。`PriceBar` / `Ohlc` に `__slots__` を付与し `__dict__` を除去。`PriceBar` は src/ 配下 36 ファイルが参照するため外部 API（フィールド名・frozen 性・`spread_close`）は不変、動的属性付与に依存する箇所がないことを事前 grep で確認。B 単独で 14〜22 倍の乖離を埋めるとは想定しない（限定的軽量化策）。
- **レバー C — bars の worker 間共有**: Phase 0 で「target / aux の bar フルコピーが resident の支配項」かつ A・B で成功条件 2 に届かない場合のみ着手。本命は **(c-1) zenigame の `SharedBarStore` 相当の mmap SoA 共有ストア導入**（原設計 §6.1 の起票条件は既に充足、Phase -1 参照）。**(c-2) spawn → fork 切替は本線ではなく実験枝**に降格 — macOS と依存ライブラリ（numpy / pandas / pyarrow / Objective-C runtime）の fork safety が未検証であり、検証コストと再現リスクが高いため、c-1 が技術的に行き詰まった場合の代替としてのみ残す。

### per-worker メモリ前提の一本化（全 Phase 共通）

`config.py` / `default.yaml` / `run_ga.py` / 本スキルに散在する per-worker メモリ前提（400MB vs 3GB）を一本化する。**単一係数の線形モデル（`worker_budget // 400`）は shared store 導入時に破綻する**（Critical #7 反映）ため、`_check_memory_budget` を以下の **4 項モデル**へ改める前提で設計する:

```
required_mb = base_main_mb + shared_mb + private_worker_mb * N + headroom_mb
```

- `base_main_mb`: main プロセスのベースフットプリント
- `shared_mb`: mmap 共有ストア等、worker 間で共有されるメモリ（shared store 未導入なら 0）
- `private_worker_mb`: 1 worker 専有メモリ（Phase 0 で USS ベースで実測）
- `headroom_mb`: OS / DB / ログ / 同時走行プロセス（Codex / 分析 BG）用マージン。固定値ではなく「最低 4GB または物理メモリの一定割合の大きい方」等の初期ルールを Phase 0 後に確定する（Codex Round 2 Warning #7 反映）。

各係数は Phase 0 実測値で初期化し、`default.yaml` の `@upper_bound` コメント・本スキルの env note も同一の根拠ある数値に整合させる。

## 期待効果

- **直接効果**: per-worker resident メモリの実測値を下げ、24GB マシンで swap せず安定動作。4 項モデルに基づき `max_workers` の妥当上限を算出可能にする。
- **使命への寄与（間接）**: 本改善は live_criteria 指標を直接動かすものではない。寄与は「探索基盤の制約解除」— (1) OOM / swap による RUN 中断・実行時間劣化リスクの除去、(2) AGENTS.md が目標とする複数通貨ペア（AUD_JPY / EUR_JPY / USD_JPY / EUR_USD / USD_CAD / USD_ZAR）への swim-lane 拡張は現状 7-8GB/worker では物理的に不可能であり、その scaling 前提を作る、(3) population / generations を増やせる余地を生む。使命達成の必要条件ではないが、探索のスループットと安定性の enabler と位置づける。
- 計測（Phase 0）自体が「データに真摯に向き合え」の実践であり、以降のチューニングの判断基盤になる。

## 実装方針（概要）

| 対象コンポーネント | 変更概要 | Phase |
|---|---|---|
| `parallel_eval.py`（計測コード） | RSS/USS + object 内訳の二層計測 opt-in フック（決定論・既存ロジック不変） | 0 |
| `parallel_eval.py` `_PROC_AUX_CACHE` | bounded eviction または LRU 上限（Phase 0 計測でゲート、全消去はしない） | 1-A |
| `domain/price.py` `PriceBar` / `Ohlc` | `__slots__` 付与（Phase 0 で占有比率高なら、外部 API 不変） | 1-B |
| `parallel_eval.py` Pool 生成 / bars 配布 | （Phase 0 でゲート）mmap SoA 共有ストア導入（本命）/ fork は実験枝 | 1-C |
| `config.py` / `default.yaml` / `run_ga.py` | per-worker メモリ前提の 4 項モデル一本化・`_check_memory_budget` 改修 | 0→共通 |

## 決定論ゲート（Critical #5 反映 — 全レバー共通の必須通過条件）

各レバー（A / B / C）の実装完了は、以下を**必須ゲート**として通過することを条件とする:

- 同一 seed・同一 config・同一 dataset で **4 条件**（baseline `max_workers=1` / baseline `max_workers=2` / changed `max_workers=1` / changed `max_workers=2`）を実行し、全組で **genome ranking / stage A・B・C pass-fail / live_criteria 判定 / cross-pair (ii-lite) 判定が完全一致**すること（改善前後の差分と worker 数差分の両方を検証 — Codex Round 2 Warning #5 反映）。
- 既存の同値性テスト `tests/scripts/test_run_ga_parallel.py` を基盤に、各レバーで変更したメモリ経路を通過する条件を追加する。
- 1 つでも不一致が出たレバーは実装完了としない（INCONCLUSIVE のまま別タスク化も可）。

## 制約・前提

- **決定論契約の維持**: L1 selection / L2 row-order は worker 数・メモリ実装に依存しない契約（`parallel_eval.py` docstring / 原設計 §4.0）。計測コードも共有ストアも cache 変更も、この契約を壊さない。上記決定論ゲートで verify する。
- **look-ahead bias 防止の維持**: `aux_loader.align_to` の `bar.bar_time >= effective_from_utc` 契約、`AuxAlignmentCache` の整列ロジックは挙動不変に保つ。レバー A はキャッシュの破棄タイミング / 上限のみ変更し、整列結果の値は変えない。
- **`PriceBar` 外部 API 不変**: src/ 配下 36 ファイルが参照。フィールド名・frozen 性・`spread_close` プロパティを変えない。
- **Phase 1-C の着手条件（厳密化、Suggestion #2/#6 反映）**: 以下を全て満たす場合のみ着手し、満たさなければ別タスク起票に回す:
  - Phase 0 で「target / aux bar のフルコピーが resident の支配項」が定量的に確認されている
  - レバー A・B 適用後も成功条件 2（swap / OOM 解消）に届かない
  - 本タスクのスコープ内で `live_criteria` / stage gate 閾値 / dataset window を一切変更しない（変更が必要なら別タスク）
- **段階性**: Phase 0 の計測結果なしに Phase 1-C へ進まない。「仕組みが機能していない段階で値を弄るな」。

## スコープ外

- backtest engine 全体の SoA 化（`list[PriceBar]` → numpy SoA への全面移行）。36 ファイル波及の大規模改修であり本タスクでは扱わない（将来別タスク）。
- `Decimal` → `float` への値型変更（精度・約定計算の正しさに関わるため別途独立検討）。
- zenigame の動的ヘッドルーム計算・chunksize 自動調整の移植（zenigame-fx は単一 instrument 中心でデータ規模が異なるため、Phase 0 計測後に要否判断）。
- `max_workers` のデフォルト値そのものの変更（Phase 0 で実態根拠が出てから別途判断。本タスクは「前提の 4 項モデル化と一本化」までで、値の決定は含めない）。
- spawn → fork 切替の本格実装（実験枝に降格。c-1 が行き詰まった場合のみ別途検証タスクとして起票）。
