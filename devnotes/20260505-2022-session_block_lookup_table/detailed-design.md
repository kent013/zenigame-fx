# 詳細設計: `compute_bucket_for_bar` の hour-indexed O(1) lookup table 化

## 使命・制約 (絶対遵守)

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1. A・B・C 評価期間延長 / 2. 見た目数値改善 / 3. GA ハック / 4. live_criteria 緩和 / 5. 過度な複雑化 / 6. 取引回数削減 / 7. オーバーナイト保有

### コーディングルール
- `uv run pytest tests/backtest/`
- `uv run ruff check src/ tests/`
- Python 3.13 + numpy

## 概念設計リファレンス

[devnotes/20260505-2022-session_block_lookup_table/conceptual-design.md] (Round 2 APPROVED)

非 blocker 補正: 現行は **3 要素走査** (`BLOCK_BUCKET_RANGES_UTC.items()` の dict iter)、 24 時間ループではない。

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | `_HOUR_TO_BUCKET` lookup table 構築 + `compute_bucket_for_bar` を index 参照に置換 | `src/backtest/session_block.py` | High |

## 施策 1: lookup table 化 + index 参照化

### 変更箇所
- ファイル: `src/backtest/session_block.py`
  - line 75-79 周辺: `BLOCK_BUCKET_RANGES_UTC` 直後に `_build_hour_to_bucket()` + `_HOUR_TO_BUCKET` を追加
  - line 304-329: `compute_bucket_for_bar` 本体を `_HOUR_TO_BUCKET[bar_time.hour]` に置換、 docstring 更新

### 波及変更
- `AGENTS.md`: なし
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/*.md`: なし (内部実装変更で動作不変)

### 現行コード (line 304-329)

```python
def compute_bucket_for_bar(bar_time: datetime) -> SessionBlockBucket:
    """UTC hour から SessionBlockBucket を決定論的に割当.

    SSOT: 概念設計 §5.1. BLOCK_BUCKET_RANGES_UTC 駆動.

    Raises:
        ValueError: bar_time.tzinfo is None / 非 UTC offset.
        RuntimeError: BLOCK_BUCKET_RANGES_UTC が 24h covering を満たさない場合.
    """
    if bar_time.tzinfo is None:
        raise ValueError(f"bar_time must be timezone-aware (UTC), got naive: {bar_time}")
    offset = bar_time.utcoffset()
    if offset != timedelta(0):
        raise ValueError(f"bar_time must be UTC offset, got offset={offset}: {bar_time}")
    hour = bar_time.hour
    for bucket, (start, end) in BLOCK_BUCKET_RANGES_UTC.items():
        if start <= hour < end:
            return bucket
    raise RuntimeError(
        f"hour {hour} not covered by BLOCK_BUCKET_RANGES_UTC "
        f"(= partition contract violation): {BLOCK_BUCKET_RANGES_UTC}"
    )
```

### 変更後コード

```python
# BLOCK_BUCKET_RANGES_UTC 直後に追加 (line 79 の後)

def _build_hour_to_bucket() -> tuple[SessionBlockBucket, ...]:
    """import 時に hour-indexed lookup table を構築 + partition contract を検証する.

    検証項目 (concept design Round 2 §_build_hour_to_bucket 検証対象):
    1. 各 (start, end) で 0 <= start < end <= 24 (range validity)
    2. bucket 同士で重複なし (range 排他性)
    3. 24 要素 (hours 0-23) 全 covering
    (4. total length sum = 24 — 上記 1-3 から自動的に成立する checksum 冗長検証、
        実装上は 1-3 で実質的に担保される)

    Raises:
        RuntimeError: partition contract 違反時 (startup invariant、 import 時 fail-fast)。
    """
    table: list[SessionBlockBucket | None] = [None] * 24
    for bucket, (start, end) in BLOCK_BUCKET_RANGES_UTC.items():
        if not (0 <= start < end <= 24):
            raise RuntimeError(
                f"BLOCK_BUCKET_RANGES_UTC partition contract violation: "
                f"bucket={bucket} range=({start}, {end}) (要求: 0 <= start < end <= 24)"
            )
        for h in range(start, end):
            if table[h] is not None:
                raise RuntimeError(
                    f"BLOCK_BUCKET_RANGES_UTC partition contract violation: "
                    f"hour {h} 重複 (既存={table[h]} 新={bucket})"
                )
            table[h] = bucket
    if any(b is None for b in table):
        missing = [h for h, b in enumerate(table) if b is None]
        raise RuntimeError(
            f"BLOCK_BUCKET_RANGES_UTC partition contract violation: "
            f"hours {missing} not covered (24h covering 違反): {BLOCK_BUCKET_RANGES_UTC}"
        )
    return tuple(cast(SessionBlockBucket, b) for b in table)


_HOUR_TO_BUCKET: Final[tuple[SessionBlockBucket, ...]] = _build_hour_to_bucket()
```

```python
# compute_bucket_for_bar 本体置換 (line 304-329)

def compute_bucket_for_bar(bar_time: datetime) -> SessionBlockBucket:
    """UTC hour から SessionBlockBucket を決定論的に割当.

    SSOT: 概念設計 §5.1. BLOCK_BUCKET_RANGES_UTC 駆動。
    cycle 2 profile-optimize: 3 要素 dict iter から hour-indexed tuple O(1) lookup へ。
    partition contract 検証は import 時に `_build_hour_to_bucket()` で行う
    (= startup invariant、 per-call check 不要)。

    Raises:
        ValueError: bar_time.tzinfo is None / 非 UTC offset.
        (RuntimeError は import 時に発火し、 本関数 call 時には発火しない。
         partition contract violation は startup で early-fail される。)
    """
    if bar_time.tzinfo is None:
        raise ValueError(
            f"bar_time must be timezone-aware (UTC), got naive: {bar_time}"
        )
    offset = bar_time.utcoffset()
    if offset != timedelta(0):
        raise ValueError(
            f"bar_time must be UTC offset, got offset={offset}: {bar_time}"
        )
    return _HOUR_TO_BUCKET[bar_time.hour]
```

### Import (line 上部)
- `cast` を `typing` から import 済かを確認、 未 import なら追加

### ルックアヘッドバイアスチェック
- [x] 未来バー参照なし (hour 単一参照)
- [x] 当日確定値の先取りなし
- [x] 該当なし (partition function、 strategy/indicator ではない)

### パフォーマンスチェック
- [x] hour-indexed tuple lookup は O(1)
- [x] startup での builder cost は 1 回のみ (24 hour iteration、 ms 以下)
- [x] メモリ: 24 要素 tuple ~200 bytes

### テスト計画

#### 既存テスト走破
- [x] `tests/backtest/test_session_block.py` 全 case (特に line 446 周辺の 24h covering / no-overlap test)

#### 新規テスト追加 (test 内 self-contained oracle で parity)
- [ ] `test_compute_bucket_for_bar_lookup_table_parity` — `_HOUR_TO_BUCKET[h]` と現行 dict iter ロジック (test 内 oracle) で全 24 時間 + 異なる minute/second の datetime で出力一致
- [ ] `test_compute_bucket_for_bar_validation_unchanged` — naive datetime / 非 UTC offset で `ValueError` が現行と同じ条件・メッセージで発火
- [ ] `test_build_hour_to_bucket_detects_invalid_partition` — モックの BLOCK_BUCKET_RANGES_UTC で 4 種類の violation (range invalid / 重複 / 未 covering / mixed) を import 時 RuntimeError として検出
- [ ] `test_build_hour_to_bucket_returns_tuple_of_24` — 正常 case で len 24 + 全要素 SessionBlockBucket

#### microbenchmark (Round 1 Critical 対応: 本線 unit から分離)

unit test には絶対値 assert を置かない (環境差で flaky)。 代わりに:

- [ ] **本線 unit test**: 同一プロセス内 **相対比較** で「lookup 版の median per-call が現行 oracle 比で **15%+ 高速**」 を assert (反証可能仮説)
  - oracle = test 内 self-contained dict iter 実装
  - lookup = `_HOUR_TO_BUCKET[hour]` 経由
  - 同一 input set で median timing 比較 (timeit 経由 or `time.perf_counter_ns`)
  - 環境差を吸収するため絶対値ではなく ratio で gate
- [ ] **分離 benchmark** (optional): `benchmarks/test_session_block_perf.py` (新規ディレクトリ) or `pytest -k benchmark` skip 経由で 1M calls 絶対値計測 (手動 / 専用ジョブで実行、 CI 本線では走らせない)

#### profile 再計測 (Phase 7 で実施)
- [ ] `compute_bucket_for_bar` tottime が 0.703s → ≤0.40s (43% 削減 = first hypothesis 下限)

### リスク
- **import 副作用**: `_build_hour_to_bucket()` が module import 時に走る。 builder は SSOT (`BLOCK_BUCKET_RANGES_UTC`) のみ参照、 循環 import なし。 `calendar.py` → `session_block` の既存 import chain は影響なし
- **契約変更**: per-call RuntimeError → import 時 RuntimeError。 production で predictable に early-fail (= 改善)、 但し既存 docstring の `Raises: RuntimeError` 記述は import 時に移ったことを明記
- **defensive path**: 万一 hour が 0-23 範囲外 (例: timezone aware だが非 UTC offset で `bar_time.hour` の意味が変わる場合) は IndexError → これは既存 ValueError check (`offset != timedelta(0)`) で前段で捕捉される設計、 追加 defensive 不要

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | **incremental** |
| 判断根拠 | 1 ファイル (`src/backtest/session_block.py`) の 1 関数変更 + 既存 test 走破。 cycle 1/3 (T088) と独立 |
| 競合リスク | なし (session_block.py 単独、 _indicators.py / DSL / broker と独立) |
| 想定実装時間 | 短 (1-2 時間、 lookup table + parity test + microbenchmark) |

## 実装順序

1. `_build_hour_to_bucket()` + `_HOUR_TO_BUCKET` 追加 (line 80 後ろ、 cast import 確認)
2. parity test 先行作成 → 現行 vs lookup table で同一出力を assert
3. `compute_bucket_for_bar` 本体を `_HOUR_TO_BUCKET[bar_time.hour]` 参照に置換、 docstring 更新
4. partition violation 検出の新規テスト追加 (4 種類 violation case)
5. 本線 unit に **相対比較 ratio assert** test 追加 (lookup 版が oracle 比 15%+ 高速、 ratio < 0.85)。 絶対値計測は `benchmarks/` 側 (CI 非 gate、 手動/専用ジョブで実行)
6. 全テスト走破: `uv run pytest tests/backtest/` + ruff + mypy
7. profile 再走 (Phase 7) で削減効果確認

## 全体使命チェック

| 禁止事項 | 抵触 | 根拠 |
|---|---|---|
| 1. 評価期間延長 | なし | 不変 |
| 2. 見た目数値改善 | なし | 出力完全同値 |
| 3. GA ハック | なし | 不変 |
| 4. 閾値緩和 | なし | 不変 |
| 5. 過度な複雑化 | なし | 1 ファイル + builder 関数 1 個 + lookup table 1 個 |
| 6. 取引回数削減 | なし | 不変 |
| 7. オーバーナイト保有 | なし | 不変 |

cycle 2/3 detailed-design は mission alignment OK。 出力完全同値、 性能のみ向上。
