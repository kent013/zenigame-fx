# 詳細設計: composite per-bar 計算の Numba JIT 化（dict → ndarray, fused kernel）

## 使命・制約（絶対遵守）

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1. A・B・C 評価期間を根拠なしに延長
2. 見た目の数値改善
3. GA ハック
4. live_criteria 緩和
5. 過度な複雑化
6. 取引回数削減で成績を見せる
7. オーバーナイト保有前提

### コーディングルール
- **バグ修正はテストファースト**: 再現最小テスト → FAIL 確認 → 修正 → PASS
- **全施策にテスト必須**（テストなしは実装完了としない）
- **テスト命名**: 振る舞いを説明する汎用的な名前（Run 名・日付・セッション固有の識別子 NG）
- **テスト配置**: 対象モジュールに対応するテストファイル
- **uv 必須**: `uv run pytest tests/alpha_factory/`
- **ruff / mypy 通過**: `uv run ruff check src/ tests/` / `uv run mypy src/`
- Python 3.13 + numpy + pandas 環境

## 概念設計リファレンス

[devnotes/20260427-1723-composite-numba-jit/conceptual-design.md](./conceptual-design.md)

主要決定事項（概念設計の Round 3 APPROVED 版から）:
- 期待効果: on_bar cumtime 削減 40-65%（保守目標 40%、stretch 65%）
- 数値契約: aggregate `np.allclose(atol=1e-6, rtol=0)`、T037 active_clause は exact `!= 0.0` parity
- ベンチマーク条件: warm cache / cold cache / `--max-workers 6` の 3 条件分離
- データ表現: unique_signal_matrix + index indirection（occurrence ベースは禁止）
- gate side は weight を持たない（既存 `compute_gate` 仕様維持）

---

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | 依存追加 (numba) + Python 互換マトリクス verify | pyproject.toml | High |
| 2 | composite kernel (Numba njit fused) 追加 | src/dsl/composite.py | High |
| 3 | PreparedSignals 拡張 (flat ndarray) + 配列長/clauses 空検証 | src/dsl/strategy.py | High |
| 4 | on_bar prepared path 切替 | src/dsl/strategy.py | High |
| 5 | テスト整備（同値性、T037 parity、ゼロ近傍、配列長不一致、clauses 空） | tests/dsl/ | High |
| 6 | Numba JIT cache ディレクトリ管理 | (新規確認) | Medium |
| 7 | bars_scale_a 実測スクリプト | devnotes/{dir}/bars-scale-measure.py | Medium |

---

## 施策 1: 依存追加 (numba)

### 変更箇所
- `pyproject.toml` の `dependencies` に numba を追加

### 波及変更
- `AGENTS.md`: なし（運用手順は `uv sync` で吸収。skill 文書は次サイクルで update-docs）
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし（profile-optimize の skill 内 SKILL は既に Numba 言及あり）
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/*.md`: なし（次サイクルで `update-docs` skill により陳腐化チェック）

### 現行コード
```toml
dependencies = [
    ...
    "numpy>=1.26",
    "pandas>=2.2",
    ...
]
```

### 変更後コード
```toml
dependencies = [
    ...
    "numpy>=1.26",
    "pandas>=2.2",
    "numba>=0.61",  # JIT for composite per-bar kernel (devnotes/20260427-1723-composite-numba-jit)
    ...
]
```

### バージョン要件の verify（Round 1 Critical 2 反映）

実装の **最初の step** として以下を実施し、**互換性が取れない場合は本 TODO を中断**してフォールバック案を選定する:

1. ローカル環境（macOS、Python 3.13）で `uv add 'numba>=0.61' && uv sync` を試行
2. import smoke test: `uv run python -c "import numba; print(numba.__version__, numba.config.IS_OSX)"`
3. njit smoke test: `uv run python -c "import numba; import numpy as np; @numba.njit(cache=True)\ndef f(x): return np.sum(x); print(f(np.arange(10, dtype=np.float64)))"`

**Python 3.13 互換が取れない場合のフォールバック**:
- a) Python 3.11/3.12 への requires-python 固定（pyproject.toml の `requires-python` を更新）
- b) Numba optional + pure Python fallback（`try: import numba; except ImportError: ...`）— 複雑化のため非推奨、a) を優先
- 選定結果は detailed-design.md の本セクションに追記し、Round 2 で再レビュー対象にする

### テスト計画
- [x] import smoke test を実装初期に実行（マニュアル）
- [x] njit smoke test（マニュアル）
- pytest fixtures は不要（既存テストが numba ありで通れば OK）
- [x] verify 結果を本設計書に追記して Round 2 レビュー対象

### リスク
- numba パッケージサイズが大きい（~30MB）→ install 時間増加。許容
- LLVM 系 transitive deps が衝突する可能性 → 実装環境で verify
- **Python 3.13 + Numba が即時動作しない場合の中断条件**: 上記 a/b いずれも採用できないと判定された時点で本 TODO は **暫定 close（次サイクルへ繰越し）**、`docs/alpha_factory/TODO.md` の Conditional に「Numba 互換性確認後に再開」として残す

---

## 施策 2: composite kernel (Numba njit fused) 追加

### 変更箇所
- `src/dsl/composite.py` に Numba njit kernel 関数を追加（既存純 Python 関数は **削除しない**）

### 波及変更
- `AGENTS.md`: なし
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし（次サイクル update-docs）
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/*.md`: なし

### 現行コード
（`src/dsl/composite.py` 全体 — 純 Python 実装。`compute_dir_score`, `compute_gate`, `compute_clause_score`, `compute_composite`）

### 変更後コード（追加部分のみ）

```python
# src/dsl/composite.py の末尾に追加

import numpy as np
import numba


@numba.njit(cache=True, fastmath=False)
def compute_composite_at_bar_jit(
    idx: int,
    clause_weights: np.ndarray,        # float64[n_clauses]
    dir_weights_flat: np.ndarray,      # float64[total_dir_occurrences]
    dir_offsets: np.ndarray,           # int64[n_clauses+1]
    dir_signal_idx: np.ndarray,        # int64[total_dir_occurrences]
    gate_offsets: np.ndarray,          # int64[n_clauses+1]
    gate_signal_idx: np.ndarray,       # int64[total_gate_occurrences]
    unique_signal_matrix: np.ndarray,  # float64[n_unique_signals, n_bars]
    out_clause_scores: np.ndarray,     # float64[n_clauses] - preallocated buffer
) -> float:
    """Numba njit 版 composite 計算（per-bar fused kernel）。

    純 Python 実装と同じ演算順序を保ち、`np.allclose(atol=1e-6, rtol=0)` を満たす。
    out_clause_scores は **毎 bar に全 clause 分上書き**する（途中スキップ禁止）。
    T037 active_clause 判定は呼び出し側で exact `!= 0.0` で行う（kernel 内では判定しない）。
    """
    n_clauses = clause_weights.shape[0]
    n_unique, n_bars = unique_signal_matrix.shape

    # Note: idx の範囲ガードは既存純 Python 実装と同じ semantics で扱う:
    #   v = arr[idx] if 0 <= idx < len(arr) else 0.0
    # ここでは matrix[row, idx] を読むので 0 <= idx < n_bars をチェック。
    bars_in_range = (0 <= idx) and (idx < n_bars)

    composite_num = 0.0
    composite_denom = 0.0

    for ci in range(n_clauses):
        # 1) dir_score = Σ(w × x) / Σ|w|
        d_start = dir_offsets[ci]
        d_end = dir_offsets[ci + 1]
        dir_num = 0.0
        dir_denom = 0.0
        for k in range(d_start, d_end):
            w = dir_weights_flat[k]
            if bars_in_range:
                v = unique_signal_matrix[dir_signal_idx[k], idx]
                # math.isfinite と同じ semantics: NaN, +inf, -inf を 0.0 に
                if not (v == v) or v == np.inf or v == -np.inf:
                    v = 0.0
            else:
                v = 0.0
            dir_num += w * v
            dir_denom += abs(w)
        if dir_denom == 0.0:
            dir_score = 0.0
        else:
            dir_score = dir_num / dir_denom

        # 2) gate = Π gate_j （weight は使わない: 既存 compute_gate 仕様）
        g_start = gate_offsets[ci]
        g_end = gate_offsets[ci + 1]
        gate = 1.0
        for k in range(g_start, g_end):
            if bars_in_range:
                v = unique_signal_matrix[gate_signal_idx[k], idx]
                if not (v == v) or v == np.inf or v == -np.inf:
                    v = 0.0
            else:
                v = 0.0
            gate *= v

        # 3) clause_score = dir_score × gate を毎 bar 全 clause 上書き
        cs = dir_score * gate
        out_clause_scores[ci] = cs

        # 4) composite = Σ(cw × cs) / Σ|cw|
        cw = clause_weights[ci]
        composite_num += cw * cs
        composite_denom += abs(cw)

    if composite_denom == 0.0:
        return 0.0
    return composite_num / composite_denom
```

### clauses 空時の例外契約（Round 1 Critical 1 反映）

**既存 `compute_composite()` は `clauses` 空で `ValueError` を raise**する。新 kernel は per-bar に呼ばれる per-genome 不変条件のため、**kernel 側では検証しない**（n_clauses 0 だと早期 return で 0.0 になり silent bug 化する）。

代わりに **`prepare()` 時点で `len(self._genome.clauses) == 0` を検出して `ValueError` を raise** する（施策 3 で実装）。これにより:
- prepared path: prepare 時に raise → kernel が呼ばれない
- unprepared path: 既存 `compute_composite` が per-bar で raise（既存挙動）
- 結果として **両 path で同じ `ValueError` 契約**を維持

### 演算順序の保持（純 Python 実装との対応）

純 Python の `compute_composite` は以下の順序で計算する:
- 各 clause: `cs = compute_clause_score(clause, vals) = compute_dir_score(...) * compute_gate(...)`
- `compute_dir_score`: `for sig in signals: num += sig.weight * values[sig.name]; denom += abs(sig.weight)`
- `compute_gate`: `for sig in signals: g *= values[sig.name]`
- `compute_composite`: `num += clause.weight * cs; denom += abs(clause.weight)`

kernel は **同じ順序**で計算する（clauses 順 → directional 順 → gate 順 → composite 集計）。`fastmath=False` により Numba は再結合最適化を行わない。

### `math.isfinite` vs `np.isfinite` の semantics
- `math.isfinite(x)` は NaN/+inf/-inf で False を返す
- kernel では `not (v == v)` (NaN 判定) または `v == np.inf` または `v == -np.inf` で同じ判定を実装
- これは `math.isfinite` の不採用ではなく、Numba njit 内で同等 semantics を構造的に再現

### テスト計画
新規テスト（tests/dsl/test_composite_jit.py に配置）:

- [x] `test_jit_kernel_matches_python_impl_on_random_genomes` — property-based: 100 個の random genome × 100 random bar idx で純 Python `compute_composite` と kernel の結果が `np.allclose(atol=1e-6, rtol=0)` を満たす
- [x] `test_jit_kernel_handles_nan_and_inf_inputs` — NaN, +inf, -inf 入力で 0.0 置換され、aggregate が 0.0 になる
- [x] `test_jit_kernel_zero_weight_returns_zero` — 全 clause weight = 0 で composite が 0.0
- [x] `test_jit_kernel_zero_dir_weight_clause_zero` — clause 内 dir_weight 全 0 で当該 clause score 0.0
- [x] `test_jit_kernel_empty_gate_acts_as_passthrough` — gate signal 0 個の clause で gate=1.0
- [x] `test_jit_kernel_idx_out_of_range_returns_zero` — idx < 0 / idx >= n_bars で全 signal 値が 0 として扱われる
- [x] `test_jit_kernel_clause_score_buffer_overwritten_every_bar` — 同じ buffer を 2 bar 連続で再利用して、2 bar 目の値が正しく上書きされる
- [x] `test_jit_kernel_active_clause_parity_zero_threshold` — exact `!= 0.0` で純 Python `compute_clause_score` と判定一致
- [x] **`test_jit_kernel_zero_neighborhood_signed_zero_parity`**（Round 1 Warning 2 反映）— 決定的ケースで T037 exact parity を検証:
  - case A: `+0.0` と `-0.0` が混在する weights × values で純 Python と kernel の `clause_score != 0.0` 判定が一致
  - case B: 極小値 `1e-320`（subnormal）入力で aggregate allclose を満たしつつ T037 判定が一致
  - case C: `0.0 - 0.0` で対消失する weights × values（cancellation 狙い）で純 Python と kernel の判定一致
- [x] **`test_jit_kernel_clauses_empty_handled_in_prepare_not_kernel`**（Round 1 Critical 1 反映）— kernel に直接 n_clauses=0 を渡すケースが本番で発生しないこと（prepare() で先に ValueError）を担保するため、施策 3 のテストとセットで検証

### リスク
- Numba 初回コンパイルで **module import 時間が +1〜3 秒**（cache=True で 2 回目以降即時）
- `cache=True` の cache 場所が worker 並列で衝突する可能性（施策 6 で対応）
- `np.inf` / `np.isfinite` の Numba 対応版挙動は要 verify（実装時に確認）

---

## 施策 3: PreparedSignals 拡張 (flat ndarray)

### 変更箇所
- `src/dsl/strategy.py:41-80`（`PreparedSignals` NamedTuple）
- `src/dsl/strategy.py:200-257`（`prepare()` メソッド）

### 波及変更
- なし（PreparedSignals は internal API、外部 caller なし）

### 現行コード
```python
class PreparedSignals(NamedTuple):
    arrays: dict[SignalCacheKey, np.ndarray]
    clauses: tuple[
        tuple[
            tuple[tuple[str, np.ndarray], ...],  # directional entries
            tuple[tuple[str, np.ndarray], ...],  # gate entries
        ],
        ...,
    ]
    genome: Genome
```

### 変更後コード

```python
class PreparedSignals(NamedTuple):
    """prepare() で構築される precompute state (Cycle 2 / T029 + Numba JIT 拡張)。

    既存 fields (arrays, clauses, genome) は保持（unprepared path や identity check 用）。
    新規 fields は Numba kernel 用の flat ndarray 群。
    """

    arrays: dict[SignalCacheKey, np.ndarray]
    clauses: tuple[
        tuple[
            tuple[tuple[str, np.ndarray], ...],
            tuple[tuple[str, np.ndarray], ...],
        ],
        ...,
    ]
    genome: Genome

    # === Numba kernel 用 flat ndarray ===
    clause_weights: np.ndarray         # float64[n_clauses]
    dir_weights_flat: np.ndarray       # float64[total_dir_occurrences]
    dir_offsets: np.ndarray            # int64[n_clauses+1]
    dir_signal_idx: np.ndarray         # int64[total_dir_occurrences]
    gate_offsets: np.ndarray           # int64[n_clauses+1]
    gate_signal_idx: np.ndarray        # int64[total_gate_occurrences]
    unique_signal_matrix: np.ndarray   # float64[n_unique_signals, n_bars]
    clause_score_buffer: np.ndarray    # float64[n_clauses] - preallocated, reused per bar
```

### `prepare()` の変更

```python
def prepare(self, bars: list[PriceBar]) -> None:
    """backtest 全バーを事前計算して flat ndarray + 既存 dict 構造を構築。
    （ここに既存の docstring を保持しつつ拡張）
    """
    # 既存の reset
    self._prepared = None
    self._bar_count = 0
    self._active_clause_indices.clear()

    if not hasattr(self._evaluator, "evaluate_all_bars"):
        return

    # === Round 1 Critical 1 反映: clauses 空の ValueError 契約維持 ===
    if not self._genome.clauses:
        raise ValueError(
            "Genome.clauses must not be empty (compute_composite contract)"
        )

    n_bars = len(bars)

    # === 既存 logic: arrays + clause_entries 構築 ===
    arrays: dict[SignalCacheKey, np.ndarray] = {}
    clause_entries: list[
        tuple[
            tuple[tuple[str, np.ndarray], ...],
            tuple[tuple[str, np.ndarray], ...],
        ]
    ] = []

    for clause in self._genome.clauses:
        dir_entries: list[tuple[str, np.ndarray]] = []
        for sig in clause.directional:
            key = _signal_cache_key(sig)
            if key not in arrays:
                arr = np.asarray(
                    self._evaluator.evaluate_all_bars(bars, sig),
                    dtype=np.float64,
                )
                # Round 1 Critical 3 反映: 配列長不一致を fail-fast
                # Round 2 Warning 反映: list/Series 戻り値も np.asarray で正規化してから shape 検証
                if arr.shape != (n_bars,):
                    raise ValueError(
                        f"evaluate_all_bars returned shape {arr.shape}, "
                        f"expected ({n_bars},) for signal {sig.name}"
                    )
                arrays[key] = arr
            dir_entries.append((sig.name, arrays[key]))

        gate_entries: list[tuple[str, np.ndarray]] = []
        for sig in clause.local_gate:
            key = _signal_cache_key(sig)
            if key not in arrays:
                arr = self._evaluator.evaluate_all_bars(bars, sig)
                if arr.shape != (n_bars,):
                    raise ValueError(
                        f"evaluate_all_bars returned shape {arr.shape}, "
                        f"expected ({n_bars},) for signal {sig.name}"
                    )
                arrays[key] = arr
            gate_entries.append((sig.name, arrays[key]))

        clause_entries.append((tuple(dir_entries), tuple(gate_entries)))

    # === 新規: flat ndarray 構築 ===
    n_clauses = len(self._genome.clauses)
    # n_bars は上で取得済み

    # unique signal matrix: arrays dict を行スタック
    # 順序を deterministic にするため key 順でソート
    unique_keys = sorted(arrays.keys())
    key_to_row = {k: i for i, k in enumerate(unique_keys)}
    n_unique = len(unique_keys)
    unique_signal_matrix = np.empty((n_unique, n_bars), dtype=np.float64)
    for k, row_idx in key_to_row.items():
        # arrays[k] は evaluate_all_bars の戻り値。dtype は float (numpy native)
        # float64 に明示変換（kernel との dtype 整合のため）
        unique_signal_matrix[row_idx, :] = np.ascontiguousarray(
            arrays[k], dtype=np.float64
        )

    # clause-level flat structures
    clause_weights = np.array(
        [c.weight for c in self._genome.clauses], dtype=np.float64
    )

    # dir/gate offsets + weights + signal_idx (CSR)
    dir_offsets_list = [0]
    dir_weights_list: list[float] = []
    dir_signal_idx_list: list[int] = []
    gate_offsets_list = [0]
    gate_signal_idx_list: list[int] = []

    for clause in self._genome.clauses:
        for sig in clause.directional:
            dir_weights_list.append(sig.weight)
            dir_signal_idx_list.append(key_to_row[_signal_cache_key(sig)])
        dir_offsets_list.append(len(dir_weights_list))
        for sig in clause.local_gate:
            gate_signal_idx_list.append(key_to_row[_signal_cache_key(sig)])
        gate_offsets_list.append(len(gate_signal_idx_list))

    dir_weights_flat = np.array(dir_weights_list, dtype=np.float64)
    dir_offsets = np.array(dir_offsets_list, dtype=np.int64)
    dir_signal_idx = np.array(dir_signal_idx_list, dtype=np.int64)
    gate_offsets = np.array(gate_offsets_list, dtype=np.int64)
    gate_signal_idx = np.array(gate_signal_idx_list, dtype=np.int64)
    clause_score_buffer = np.empty(n_clauses, dtype=np.float64)

    self._prepared = PreparedSignals(
        arrays=arrays,
        clauses=tuple(clause_entries),
        genome=self._genome,
        clause_weights=clause_weights,
        dir_weights_flat=dir_weights_flat,
        dir_offsets=dir_offsets,
        dir_signal_idx=dir_signal_idx,
        gate_offsets=gate_offsets,
        gate_signal_idx=gate_signal_idx,
        unique_signal_matrix=unique_signal_matrix,
        clause_score_buffer=clause_score_buffer,
    )
```

### 重要な設計判断
- `unique_signal_matrix` は **deterministic な行 index**（`sorted(arrays.keys())`）
- 既存 `arrays` dict は保持 → unprepared path や T029 不変条件への影響なし
- `clause_score_buffer` を preallocate → per-bar の np.empty allocation を避ける
- dtype を **明示 float64 / int64** に統一 → Numba kernel との contract が崩れないことを保証

### テスト計画
新規テスト（tests/dsl/test_strategy.py に追加）:

- [x] `test_prepared_signals_unique_signal_matrix_dedupes_shared_primitives` — 同じ `(name, params)` を 2 clause に出すと unique_signal_matrix の行数が 2 ではなく 1 になる
- [x] `test_prepared_signals_dir_offsets_csr_form` — dir_offsets が CSR 形式（offsets[ci+1] - offsets[ci] = 当該 clause の dir signal 数）
- [x] `test_prepared_signals_clause_weights_dtype_float64` — dtype 契約
- [x] `test_prepare_on_evaluator_without_evaluate_all_bars_returns_no_op` — 既存挙動の保持
- [x] **`test_prepare_raises_on_clauses_empty`**（Round 1 Critical 1 反映）— `Genome.clauses == ()` で `prepare()` が `ValueError` を raise する
- [x] **`test_prepare_raises_on_evaluate_all_bars_length_mismatch`**（Round 1 Critical 3 反映）— `evaluate_all_bars` が `len(bars)` と異なる長さの ndarray を返す mock evaluator を使い、`prepare()` で `ValueError` を raise する。bars 5 個 + ndarray 長 4 / 6 の両ケース

### メモリ概算（Round 1 Warning 3 反映）

`PreparedSignals` は `arrays` dict（既存）と `unique_signal_matrix`（新規）で**同等データを 2 重保持**する。具体的なメモリ式:

```
mem(prepared) ≈ arrays_size + unique_matrix_size
              = n_unique × n_bars × 8B (arrays dict)
              + n_unique × n_bars × 8B (unique_signal_matrix, contiguous copy)
              ≈ 2 × n_unique × n_bars × 8B + α (offsets / weights / clause_score_buffer 数十 B)
```

実例（Stage A, n_unique=10, n_bars=61300）: 2 × 10 × 61300 × 8B = **~9.4 MB / genome**
実例（Stage B 想定, n_unique=10, n_bars=39万）: ~60 MB / genome

**6 ワーカー × 当該 prepared 同時保持時のメモリ余裕**: 6 × 60 MB = 360 MB（worker 当たり 3GB 制約に対して 12% 占有）→ 許容内だが、n_unique が増えると圧迫する可能性あり。
- **n_unique 上限の運用ガード（後続）**: 現状 Genome 仕様上 clause 当たり directional 1-N + local_gate 0-N、N の絶対上限は config 側で制限していない。本 TODO のスコープ外だが「将来 n_unique 急増の場合は arrays dict を捨てて unique_matrix のみ保持する path」を別 TODO 候補として `docs/alpha_factory/TODO.md` Conditional に登録する判断は次サイクルで検討（本 TODO では複雑化を避けるため arrays dict は維持）

### リスク
- `evaluate_all_bars` 戻り値の dtype が float64 でない場合の `np.ascontiguousarray(..., dtype=np.float64)` で copy が発生 → メモリ +1×（許容内、Stage A で ~10 MB / genome）
- worker 並列で `unique_signal_matrix` を持つ `PreparedSignals` を pickle するコスト → 元々 `arrays` dict も pickle されているため、追加分は ~1× 程度（実装後に確認）
- 上記の通り **arrays + unique_signal_matrix で同データ 2 重保持**だが、複雑化を避けるため arrays は維持（pickle 形式変更を伴うため）

---

## 施策 4: on_bar prepared path 切替

### 変更箇所
- `src/dsl/strategy.py:285-324`（`on_bar` の prepared path）

### 波及変更
- なし

### 現行コード
（src/dsl/strategy.py:285-324、prepared path で values_per_clause dict 構築 + compute_composite + compute_clause_score 観測ループ）

### 変更後コード

```python
# 各 clause の primitive 値を評価
if prepared is not None:
    # fast path: Numba JIT fused kernel
    composite = compute_composite_at_bar_jit(
        idx,
        prepared.clause_weights,
        prepared.dir_weights_flat,
        prepared.dir_offsets,
        prepared.dir_signal_idx,
        prepared.gate_offsets,
        prepared.gate_signal_idx,
        prepared.unique_signal_matrix,
        prepared.clause_score_buffer,
    )
    # T037: per-clause score buffer から exact `!= 0.0` で集計
    # (compute_clause_score の重複呼び出しを排除)
    for ci in range(prepared.clause_score_buffer.shape[0]):
        if prepared.clause_score_buffer[ci] != 0.0:
            self._active_clause_indices.add(ci)
else:
    # unprepared path (live feed / paper trading) - 既存実装をそのまま維持
    values_per_clause: list[dict[str, float]] = []
    for clause in self._genome.clauses:
        vals: dict[str, float] = {}
        for sig in clause.directional:
            vals[sig.name] = self._evaluator.evaluate(
                self._bars, idx, sig
            )
        for sig in clause.local_gate:
            vals[sig.name] = self._evaluator.evaluate(
                self._bars, idx, sig
            )
        values_per_clause.append(vals)
    composite = compute_composite(self._genome.clauses, values_per_clause)
    for ci, (clause, vals) in enumerate(
        zip(self._genome.clauses, values_per_clause, strict=True)
    ):
        if compute_clause_score(clause, vals) != 0.0:
            self._active_clause_indices.add(ci)
```

### 重要な設計判断
- prepared path は **kernel の戻り値 + buffer 読み取り**だけ。`compute_clause_score` の重複呼び出しを完全排除
- unprepared path は **既存実装をそのまま維持**（Numba 化のリスクを後段に隔離）
- import: `from src.dsl.composite import compute_composite, compute_clause_score, compute_composite_at_bar_jit` （unprepared path は既存 functions を使うため両方残す）

### テスト計画
- [x] `test_on_bar_prepared_path_uses_jit_kernel_results` — 既存 `test_dsl_strategy.py` の出力が同値
- [x] `test_on_bar_active_clause_indices_parity_with_python_impl` — 同一 genome × bars で active_clause_indices set が純 Python 実装と完全一致
- [x] `test_on_bar_unprepared_path_unchanged` — unprepared path は既存挙動

### リスク
- **idx 範囲ガード**の semantics: 既存 prepared path は `if 0 <= idx < len(arr)` で per-array、kernel は per-matrix-row（同 n_bars 前提）。すべての arr が n_bars 長前提なので等価（prepare() で `evaluate_all_bars` が全 bars に対し ndarray を返す前提）。**property test で確認**

---

## 施策 5: テスト整備

### tests/dsl/test_composite_jit.py（新規）
施策 2 のテスト計画に列挙。pytest.parametrize で genome × bar idx 組合せをカバー。

### tests/dsl/test_strategy.py（既存追加）
施策 3, 4 のテスト計画に列挙。

### tests/dsl/test_dsl_strategy_flat_cache.py（既存維持）
- 既存テストが新実装でも通ること（PreparedSignals 拡張で field 追加されたが既存 fields は保持）

### Property-based equivalence test（新規 tests/dsl/test_composite_jit_property.py）
- `hypothesis` ライブラリで random genome × random unique_signal_matrix を生成
- 純 Python `compute_composite` + `compute_clause_score` の組と JIT kernel の結果が `np.allclose(atol=1e-6, rtol=0)` を満たし、T037 active_clause が **exact 一致**することを検証
- ゼロ近傍ケース（`atol < |composite| < 1e-6`）が出た場合、T037 parity が破れるサンプルを sticky DB に保存して詳細設計書のリスク欄に記載

### 実行
```bash
uv run pytest tests/dsl/ -x -v
uv run pytest tests/alpha_factory/ tests/backtest/ tests/dsl/ -x  # 全パス確認
```

---

## 施策 6: Numba JIT cache ディレクトリ管理

### 背景
- `cache=True` で Numba は `__pycache__/<module>/<func>.nbi/` および `.nbc/` を生成
- worker 並列（`--max-workers 6`）で複数 process が同時に書き込むと cache 衝突の可能性

### 対応方針
1. **読み取り中心の cache**: 初回書き込みは 1 process でしか起きないため、worker fork 後の再 import で cache hit する
2. **cache が壊れた場合の復旧**: 詳細設計時点では Numba 標準の `__pycache__` 配下を使用（明示的に別 dir 指定はしない、シンプルさ優先）
3. **CI / 検証 run での cold start リスク**: 計測条件として §7 で warm/cold を分離（概念設計と整合）

### 変更箇所
- なし（コード変更不要、Numba 標準動作で十分）。実装時に worker 並列での cache hit 挙動を実測 verify

### リスク
- multi-process で cache 競合が出た場合は施策追加（NUMBA_CACHE_DIR を per-worker に分けて重複コンパイルを許容、など）。本 TODO のスコープ外、Phase 7 で実測リスクとして report

---

## 施策 7: bars_scale_a 実測スクリプト

### 背景
概念設計 §1.2 で「bars_scale_a を実測 bar 数比で再計算」と決めた。Phase 7 効果評価時に必要。

### 変更箇所
- `devnotes/20260427-1723-composite-numba-jit/measure_bars_scale.py`（新規）

### 内容
profile RUN の archive Parquet と本番 (default.yaml) 設定の Stage A window から、実 bar 数を集計するスクリプト。本番 RUN は実行せず、profile RUN の bars/backtest と本番設定を計算するのみ。

### リスク
- スクリプト本体は本 TODO のクリティカルパスではない（Phase 7 で結果を使うが、概略は概念設計の暫定値で代替可能）

---

## 実装モード

| 項目 | 内容 |
|------|------|
| **推奨モード** | **standalone**（worktree で実装、main マージ後に効果評価） |
| **判断根拠** | (1) 数値契約 + 既存 archive Parquet 同値性検証が必要で incremental だと中間状態でテストが落ちるリスク、(2) Numba 依存追加は pyproject.toml 変更でキャッシュ動作も影響するため一括変更が安全、(3) `compute_composite_at_bar_jit` + `PreparedSignals` 拡張 + `on_bar` 切替の 3 つは結合度が高く分離不可 |
| **競合リスク** | (a) T037 active_clause 集計仕様変更は別 TODO で並走しないこと、(b) `prepare()` まわりの T029 不変条件に触るため Cycle 関連 TODO（cycle 9-12）と並走時は要 review |
| **想定実装時間** | 中（kernel 実装 + 数値契約テスト + Numba 環境セットアップ + cProfile 再計測） |

---

## 検証要件まとめ

| # | 項目 | 合格基準 |
|---|------|---------|
| V1 | 既存 unit test 全パス | `uv run pytest tests/alpha_factory/ tests/backtest/ tests/dsl/ -x` 全 PASS |
| V2 | 同値性 (aggregate) | 純 Python と kernel の compute 結果が `np.allclose(atol=1e-6, rtol=0)` |
| V3 | T037 exact parity | `compute_clause_score != 0.0` semantics が一致（exact `!= 0.0`、ゼロ近傍は T037 優先） |
| V4 | 既存テスト更新なし | `test_dsl_strategy_flat_cache.py` 等が変更なしで通る |
| V5 | archive Parquet diff | 同 seed・同 config の baseline run と最新 run で per-genome `fitness_pen, sharpe, trade_count, stage_a_pass` が `allclose(atol=1e-6, rtol=0)` |
| V6 | 再プロファイル warm cache | on_bar cumtime 削減率 40% 以上 |
| V7 | 再プロファイル cold cache | 削減率を計測（合格基準ではなくリスク評価指標） |
| V8 | bars_scale_a 実測 | profile actual bars/backtest と本番 stage_a 想定 bars の比を Phase 7 で確定 |
| V9 | ruff / mypy | `uv run ruff check src/ tests/` PASS, `uv run mypy src/` PASS |
| V10 | clauses 空 ValueError 契約（Round 1 Critical 1） | prepared / unprepared 両 path で同じ ValueError |
| V11 | 配列長不一致 ValueError（Round 1 Critical 3） | `prepare()` が fail-fast |
| V12 | Numba × Python 互換性（Round 1 Critical 2） | 実装初期に互換マトリクス verify、不可なら fallback 採用 |
| V13 | ゼロ近傍 T037 parity（Round 1 Warning 2） | 決定的ケース（+0.0 / -0.0 / 1e-320 / cancellation）で active_clause 判定が純 Python と完全一致 |
| V14 | on_bar 内訳の同一指標再計測（Round 1 Warning 1） | Phase 7 で `line_profiler` または別途 cProfile snippet で values_per_clause 構築コストと composite 計算コストを分離計測し、設計書の改善見積りと突き合わせ |

---

## 補足: ルックアヘッドバイアスチェック

primitive 変更**なし**（composite per-bar 計算のみ変更）のため項目該当なし:
- [x] 未来バー参照なし（kernel は idx と precomputed matrix だけを参照）
- [x] 当日確定値の先取りなし
- [x] rolling window 方向: primitive 側で既に過去方向（compute_all_bars 不変）
- [x] 正規化: 既存 dir_score / gate / composite のまま

## 補足: パフォーマンスチェック

- [x] `compute_all_bars()` 既存実装維持（prepare 時 1 回のみ）
- [x] 内側ループ内 NumPy 関数呼び出しなし（kernel は素の for ループで Numba JIT）
- [x] SoA: unique_signal_matrix は per-row contiguous (numpy default C-order, axis=1 アクセス)
- [x] キャッシュ: `clause_score_buffer` は preallocated, prepare 時 1 回のみ allocate
