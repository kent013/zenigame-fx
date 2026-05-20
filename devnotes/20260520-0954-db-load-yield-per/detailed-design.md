# 詳細設計: DB ロード `yield_per` ストリーム化 (main RSS 削減 step C)

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
- バグ修正はテストファースト
- 全施策にテスト必須
- テスト命名: 振る舞いを説明する汎用的な名前
- テスト配置: 対象モジュールに対応するテストファイル
- uv 必須: `uv run pytest tests/alpha_factory/`
- ruff / mypy 通過
- Python 3.11 + numpy + pandas 環境 (devnotes 確認時点で `python3.11` venv が稼働、 skill 雛形の "3.13" は誤記の可能性あり、 本設計は 3.11 を前提とする)

## 概念設計リファレンス

devnotes/20260520-0954-db-load-yield-per/conceptual-design.md (APPROVED Round 2)

## 前提 (C4: 詳細設計時点で再 verify)

| 項目 | 状態 | 根拠 / 取り扱い |
|---|---|---|
| 対象 3 経路で `.all()` 使用 | **verified** | run_ga.py:531, 548 / aux_loader.py:584-592 |
| 全クエリで `order_by(bar_time.asc())` 指定済 | **verified** | 同上 |
| `SessionLocal` は単純 sessionmaker (autoflush=False) | **verified** | src/db/connection.py:14 |
| `PriceBarM1` 列: id/pair_id/bar_time/open_bid/high_bid/low_bid/close_bid/open_ask/high_ask/low_ask/close_ask/volume/complete | **verified** | src/db/models.py:54-69 |
| `PriceBar` 構造体: pair_name/bar_time/bid(Ohlc)/ask(Ohlc)/volume/complete | **verified** | src/domain/price.py:17-27 |
| SQLAlchemy 2.x + psycopg3 の `execution_options(yield_per=N)` で server-side cursor が有効化される | **verified via Context7 (2026-05-20)**: SQLAlchemy doc 確認済。 `yield_per` execution option は (1) ORM/Core 結果を batch iteration し全件メモリ展開を避ける、 (2) 内部で `stream_results=True` (server-side cursor) を自動付与する、 (3) `.all()` ではなく for loop での消費が必須。 `session.scalars(stmt)` / `session.execute(stmt)` の両方で動作。 | Context7: /sqlalchemy/sqlalchemy ORM Querying Guide + Core Connections |
| `aux_loader.load_aux_pair_bars_index` は **caller-owned session を受ける** | **verified** | aux_loader.py:557 (`db_session: Session` 引数) |
| `_load_lane_bars` は **関数内で SessionLocal() を context manager で生成** | **verified** | run_ga.py:523 |

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| C-1 | `_load_lane_bars` を column-tuple streaming に置換 | scripts/alpha_factory/run_ga.py | High |
| C-2 | `load_aux_pair_bars_index` を column-tuple streaming に置換 | src/alpha_factory/aux_loader.py | High |
| C-3 | semantic equivalence checker (sha256 digest) 追加 + 等価性テスト | src/alpha_factory/bars_digest.py (新規) / tests/alpha_factory/test_bars_digest.py (新規) | High |
| C-4 | phase marker RSS logger 追加 | scripts/alpha_factory/run_ga.py | Med |
| C-5 | smoke 計測 + 判定 | (実装後の検証 phase) | Med |

---

## C-1. `_load_lane_bars` を column-tuple streaming に置換

### 変更箇所
- ファイル: `scripts/alpha_factory/run_ga.py` (L477-590)

### 波及変更
- `AGENTS.md`: なし
- `.claude/skills/`: なし
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/*.md`: なし
- 関連テスト: `tests/scripts/test_alpha_factory_run_ga.py` の `_MockSession` を column-tuple select にも対応させる (後述 C-1.テスト計画)

### 現行コード (run_ga.py L477-555)

```python
def _bar_row_to_price_bar(row: PriceBarM1, pair_name: str) -> PriceBar:
    return PriceBar(
        pair_name=pair_name,
        bar_time=row.bar_time,
        bid=Ohlc(open=row.open_bid, high=row.high_bid, low=row.low_bid, close=row.close_bid),
        ask=Ohlc(open=row.open_ask, high=row.high_ask, low=row.low_ask, close=row.close_ask),
        volume=row.volume,
        complete=row.complete,
    )

def _load_lane_bars(...) -> LaneBarsBundle:
    ...
    with SessionLocal() as session:
        pair = session.scalars(select(CurrencyPair).where(...)).one_or_none()
        ...
        rows_b = session.scalars(
            select(PriceBarM1)
            .where(...)
            .order_by(PriceBarM1.bar_time.asc())
        ).all()
        bars_stage_b_full = [_bar_row_to_price_bar(r, instrument) for r in rows_b]
        ...
        rows_hold = session.scalars(select(PriceBarM1).where(...).order_by(...)).all()
        bars_holdout = [_bar_row_to_price_bar(r, instrument) for r in rows_hold]
    ...
```

### 変更後コード

```python
# モジュールトップ付近、_LOAD_BARS_BATCH_SIZE を新設
_LOAD_BARS_BATCH_SIZE: Final[int] = 10_000  # smoke で 5_000 とも比較する

_PRICE_BAR_M1_COLUMNS = (
    PriceBarM1.bar_time,
    PriceBarM1.open_bid,
    PriceBarM1.high_bid,
    PriceBarM1.low_bid,
    PriceBarM1.close_bid,
    PriceBarM1.open_ask,
    PriceBarM1.high_ask,
    PriceBarM1.low_ask,
    PriceBarM1.close_ask,
    PriceBarM1.volume,
    PriceBarM1.complete,
)


def _construct_price_bar(
    *,
    pair_name: str,
    bar_time: datetime,
    open_bid: Decimal,
    high_bid: Decimal,
    low_bid: Decimal,
    close_bid: Decimal,
    open_ask: Decimal,
    high_ask: Decimal,
    low_ask: Decimal,
    close_ask: Decimal,
    volume: int,
    complete: bool,
) -> PriceBar:
    """Row tuple / ORM row どちらからでも PriceBar を組み立てる共通関数."""
    return PriceBar(
        pair_name=pair_name,
        bar_time=bar_time,
        bid=Ohlc(open=open_bid, high=high_bid, low=low_bid, close=close_bid),
        ask=Ohlc(open=open_ask, high=high_ask, low=low_ask, close=close_ask),
        volume=volume,
        complete=complete,
    )


# 既存の _bar_row_to_price_bar は後方互換のため残す (ORM row 受け取り経路)
def _bar_row_to_price_bar(row: PriceBarM1, pair_name: str) -> PriceBar:
    return _construct_price_bar(
        pair_name=pair_name,
        bar_time=row.bar_time,
        open_bid=row.open_bid,
        high_bid=row.high_bid,
        low_bid=row.low_bid,
        close_bid=row.close_bid,
        open_ask=row.open_ask,
        high_ask=row.high_ask,
        low_ask=row.low_ask,
        close_ask=row.close_ask,
        volume=row.volume,
        complete=row.complete,
    )


def _stream_bars(
    session: Session,
    *,
    pair_id: int,
    pair_name: str,
    start: datetime,
    end: datetime,
    batch_size: int = _LOAD_BARS_BATCH_SIZE,
) -> list[PriceBar]:
    """server-side cursor で column tuple を streaming し、 PriceBar list を構築する.

    実装契約:
      - select は ORM entity ではなく必要列のみを指定する (identity map に
        載せない = caller-owned session の汚染を防ぐ)
      - execution_options(yield_per=batch_size) で server-side cursor 経由の
        streaming を発動する (SQLAlchemy 2.x doc 準拠)
      - 構築後の PriceBar list 以外には何も保持しない
    """
    stmt = (
        select(*_PRICE_BAR_M1_COLUMNS)
        .where(PriceBarM1.pair_id == pair_id)
        .where(PriceBarM1.bar_time >= start)
        .where(PriceBarM1.bar_time < end)
        .order_by(PriceBarM1.bar_time.asc())
        .execution_options(yield_per=batch_size)
    )
    # Round 1 [Warning] 1: server-side cursor は try/finally で必ず close する
    # (途中例外時に caller-owned session で cursor を引きずらないため)。
    # 契約: row は SQLAlchemy Row。 属性アクセス (row.bar_time 等) のみ使用する
    # (row[0] / _mapping は使わない — テストダブルは属性アクセス互換で足りる)。
    bars: list[PriceBar] = []
    result = session.execute(stmt)
    try:
        for row in result:
            bars.append(
                _construct_price_bar(
                    pair_name=pair_name,
                    bar_time=row.bar_time,
                    open_bid=row.open_bid,
                    high_bid=row.high_bid,
                    low_bid=row.low_bid,
                    close_bid=row.close_bid,
                    open_ask=row.open_ask,
                    high_ask=row.high_ask,
                    low_ask=row.low_ask,
                    close_ask=row.close_ask,
                    volume=row.volume,
                    complete=row.complete,
                )
            )
    finally:
        result.close()
    return bars


def _load_lane_bars(
    instrument: str,
    dataset: DatasetConfig,
    stage_windows: StageWindowsConfig,
) -> LaneBarsBundle:
    """DB から Stage A/B/C の 3 区間 bars + meta を取得する (T087, T108)。

    T108: server-side cursor 経由の column-tuple streaming に置換。 ORM entity
    を経由しないため identity map に bar が積み上がらず、 ロード中の二重保持を
    回避する。
    """
    stage_a_n_bars = stage_windows.stage_a_window_days * _BARS_PER_DAY
    with SessionLocal() as session:
        pair = session.scalars(
            select(CurrencyPair).where(CurrencyPair.oanda_name == instrument)
        ).one_or_none()
        if pair is None:
            raise RuntimeError(f"currency_pair for {instrument} not found")
        meta = _meta_from_pair(pair)
        pair_id = pair.id

        logger.info("run_ga.bars_load.phase_start", phase="stage_b_full")
        bars_stage_b_full = _stream_bars(
            session,
            pair_id=pair_id,
            pair_name=instrument,
            start=dataset.start,
            end=dataset.end,
        )
        logger.info(
            "run_ga.bars_load.phase_done",
            phase="stage_b_full",
            bar_count=len(bars_stage_b_full),
        )
        if not bars_stage_b_full:
            raise RuntimeError(
                f"no bars for {instrument} in [{dataset.start}, {dataset.end})"
            )

        holdout_end = dataset.end + timedelta(
            days=stage_windows.stage_c_holdout_days
        )
        logger.info("run_ga.bars_load.phase_start", phase="holdout")
        bars_holdout = _stream_bars(
            session,
            pair_id=pair_id,
            pair_name=instrument,
            start=dataset.end,
            end=holdout_end,
        )
        logger.info(
            "run_ga.bars_load.phase_done",
            phase="holdout",
            bar_count=len(bars_holdout),
        )

    if not bars_holdout:
        raise RuntimeError(
            f"no holdout bars for {instrument} in "
            f"[{dataset.end}, {holdout_end}); "
            f"holdout fetch failed and fallback slice is no longer supported "
            f"(would violate stage partition disjoint contract; T087)"
        )

    if stage_a_n_bars >= len(bars_stage_b_full):
        raise RuntimeError(
            f"dataset too short for disjoint stage A/B: "
            f"stage_a_n_bars={stage_a_n_bars} >= "
            f"len(bars_stage_b_full)={len(bars_stage_b_full)} "
            f"(instrument={instrument}, dataset=[{dataset.start}, {dataset.end})). "
            f"Extend dataset or reduce stage_a_window_days."
        )
    bars_stage_a = bars_stage_b_full[-stage_a_n_bars:]
    bars_stage_b = bars_stage_b_full[:-stage_a_n_bars]

    logger.info("run_ga.lane_bars_loaded", ...)  # 既存のまま
    return LaneBarsBundle(...)  # 既存のまま
```

### ルックアヘッドバイアスチェック
- N/A (primitive 変更ではない)

### パフォーマンスチェック
- N/A (primitive 変更ではない)。 ただし streaming オーバーヘッドの追加は許容範囲内 (詳細設計 § C-5 で smoke 時間を計測)

### `_stream_bars` の Row 互換契約 (Round 1 [Warning] 3 反映)

`_stream_bars` / `_stream_aux_pair_bars` は **row への属性アクセスのみ**
(`row.bar_time`, `row.open_bid`, ...) を使う契約とする。 `row[0]` (index
access) / `row._mapping` は使わない。 これにより:
- 本番: SQLAlchemy `Row` は column label 属性アクセスをサポート (`select(
  PriceBarM1.bar_time, ...)` → `row.bar_time`)
- テスト: 属性アクセス互換の軽量ダブル (`SimpleNamespace` 等) で足りる

この契約を docstring に明記し、 契約テスト (下記) で固定する。

### テスト計画
- [ ] **必須**: 既存テスト `test_load_lane_bars_disjoint_stage_a_b` の `_MockSession` に `execute(stmt)` 経路を追加する。 execute は column-tuple select を受け、 属性アクセス互換の Row ダブル (`SimpleNamespace(bar_time=..., open_bid=..., ..., complete=...)`) の iterable を返す `_ExecuteResult` を yield する。 `_ExecuteResult` は `__iter__` と `close()` を実装する (try/finally close 契約に対応)
- [ ] **新規** `test_stream_bars_uses_attribute_access_only` — Row ダブルが属性アクセスのみで消費されることを契約テスト化 (`__getitem__` を raise する Row ダブルでも動くことを確認)
- [ ] **新規** `test_load_lane_bars_streams_via_yield_per` — `_stream_bars` の stmt に `yield_per` execution option が含まれること、 `result.close()` が呼ばれることを mock spy で検証
- [ ] **新規** `test_stream_bars_closes_result_on_exception` — iteration 中に例外が出ても `result.close()` が呼ばれることを検証 (Round 2 [Suggestion] 2)
- [ ] **新規** `test_load_lane_bars_equivalent_to_legacy_via_digest` — 同じ fixture で旧 `.all()` 経由 (参照実装) と新 streaming の `bars_digest` が一致することを確認 (C-3 digest 関数を利用)
- [ ] 既存テスト全 pass: `uv run pytest tests/scripts/test_alpha_factory_run_ga.py`

### リスク
- **mock test の断絶**: `_MockSession` が `scalars()` ベース。 `execute()` 経路の追加が必要 (上記 C-1.テスト計画)。 ただし currency_pair lookup は引き続き `session.scalars()` を使うため、 ダブル支援が必要。
- **psycopg3 server-side cursor の挙動差**: 異常系 (接続切断、 cursor timeout) で `.all()` と挙動が違う可能性。 fallback 無し方針 (fail-fast) で問題ない (production 運用想定)。

---

## C-2. `load_aux_pair_bars_index` を column-tuple streaming に置換

### 変更箇所
- ファイル: `src/alpha_factory/aux_loader.py` (L556-605)

### 波及変更
- `AGENTS.md`: なし
- `.claude/skills/`: なし
- `config/alpha_factory/default.yaml`: なし
- 関連テスト: `tests/alpha_factory/test_aux_loader.py` の DB mock があれば修正

### 現行コード (抜粋)

```python
def load_aux_pair_bars_index(
    *,
    db_session: Session,
    pairs: Sequence[str],
    period: tuple[datetime, datetime],
) -> dict[str, dict[datetime, PriceBar]]:
    out: dict[str, dict[datetime, PriceBar]] = {}
    for pair_id in pairs:
        pair = db_session.scalars(
            select(CurrencyPair).where(CurrencyPair.oanda_name == pair_id)
        ).one_or_none()
        ...
        rows = (
            db_session.scalars(
                select(PriceBarM1).where(...).order_by(...)
            ).all()
        )
        index: dict[datetime, PriceBar] = {}
        for r in rows:
            key = _normalize_bar_time(r.bar_time)
            if key in index:
                raise ValueError(...)
            index[key] = _bar_row_to_price_bar(r, pair_id)
        out[pair_id] = index
    return out
```

### 変更後コード

```python
# モジュールトップで run_ga と同じ batch size を共有 (一貫性のため)
_LOAD_BARS_BATCH_SIZE: Final[int] = 10_000

_PRICE_BAR_M1_COLUMNS = (
    PriceBarM1.bar_time,
    PriceBarM1.open_bid,
    PriceBarM1.high_bid,
    PriceBarM1.low_bid,
    PriceBarM1.close_bid,
    PriceBarM1.open_ask,
    PriceBarM1.high_ask,
    PriceBarM1.low_ask,
    PriceBarM1.close_ask,
    PriceBarM1.volume,
    PriceBarM1.complete,
)


def _stream_aux_pair_bars(
    db_session: Session,
    *,
    pair_db_id: int,
    pair_name: str,
    start: datetime,
    end: datetime,
    batch_size: int = _LOAD_BARS_BATCH_SIZE,
) -> dict[datetime, PriceBar]:
    """server-side cursor で column tuple streaming し、 dict を構築する.

    caller-owned session を渡すが、 ORM entity ではなく列のみ取得するため
    identity map に bar が乗らない → caller 側に副作用を残さない。
    """
    stmt = (
        select(*_PRICE_BAR_M1_COLUMNS)
        .where(PriceBarM1.pair_id == pair_db_id)
        .where(PriceBarM1.bar_time >= start)
        .where(PriceBarM1.bar_time < end)
        .order_by(PriceBarM1.bar_time.asc())
        .execution_options(yield_per=batch_size)
    )
    # Round 1 [Warning] 1: caller-owned session のため、 V15 fail-fast (重複
    # minute) の早期 raise でも cursor を残さないよう try/finally で close する。
    index: dict[datetime, PriceBar] = {}
    result = db_session.execute(stmt)
    try:
        for row in result:
            key = _normalize_bar_time(row.bar_time)
            if key in index:
                # V15: 同 minute に複数 row → fail-fast (異常データ)
                raise ValueError(
                    f"aux_pair_bars duplicate bar_time after normalize "
                    f"for pair={pair_name} bar_time={key.isoformat()}"
                )
            index[key] = PriceBar(
                pair_name=pair_name,
                bar_time=row.bar_time,
                bid=Ohlc(
                    open=row.open_bid,
                    high=row.high_bid,
                    low=row.low_bid,
                    close=row.close_bid,
                ),
                ask=Ohlc(
                    open=row.open_ask,
                    high=row.high_ask,
                    low=row.low_ask,
                    close=row.close_ask,
                ),
                volume=row.volume,
                complete=row.complete,
            )
    finally:
        result.close()
    return index


def load_aux_pair_bars_index(
    *,
    db_session: Session,
    pairs: Sequence[str],
    period: tuple[datetime, datetime],
) -> dict[str, dict[datetime, PriceBar]]:
    """aux pair の M1 bars を bar_time index で取得する (T108: streaming 化)."""
    out: dict[str, dict[datetime, PriceBar]] = {}
    for pair_name in pairs:
        pair = db_session.scalars(
            select(CurrencyPair).where(CurrencyPair.oanda_name == pair_name)
        ).one_or_none()
        if pair is None:
            out[pair_name] = {}
            logger.warning(
                "aux_loader.aux_pair_bars.pair_not_found",
                pair=pair_name,
            )
            continue
        out[pair_name] = _stream_aux_pair_bars(
            db_session,
            pair_db_id=pair.id,
            pair_name=pair_name,
            start=period[0],
            end=period[1],
        )
    return out
```

### ルックアヘッドバイアスチェック
- N/A (primitive ではない)

### パフォーマンスチェック
- N/A

### テスト計画
- [ ] **必須**: 既存 aux_loader テストで dict 内容が同等であることを確認
- [ ] **新規** `test_load_aux_pair_bars_index_streams_via_yield_per` — `db_session.execute` が呼ばれ、 stmt の execution_options に `yield_per` が含まれることを mock で検証
- [ ] **新規** `test_load_aux_pair_bars_index_no_identity_map_pollution` — caller-owned session の identity map にロード後も `PriceBarM1` entity が登録されていないことを確認 (ORM entity 経路は廃止された契約)
- [ ] **新規** `test_load_aux_pair_bars_index_v15_fail_fast_preserved` — 同 minute 重複時 ValueError が出ることを確認 (regression 防止)
- [ ] **新規** `test_stream_aux_pair_bars_closes_result_on_v15_raise` — V15 重複検知の早期 ValueError 時にも `result.close()` が呼ばれることを検証 (Round 2 [Suggestion] 2)
- [ ] 既存テスト全 pass: `uv run pytest tests/alpha_factory/test_aux_loader.py`

### リスク
- caller-owned session に対する execute 副作用: column tuple select は identity map に積まないため、 caller 側の他処理 (ORM entity 取得など) に影響しない。 ただし transaction state は共有するため、 ORM 経路と混在するクエリで race condition は想定外。

---

## C-3. semantic equivalence checker (sha256 digest)

### 変更箇所
- 新規ファイル: `src/alpha_factory/bars_digest.py`
- 新規テスト: `tests/alpha_factory/test_bars_digest.py`

### 波及変更
- `AGENTS.md`: なし
- 既存コードからの呼び出しは C-1/C-2 のテストファイル内のみ (production code への組み込みは行わない、 検証用 utility)

### 設計

```python
# src/alpha_factory/bars_digest.py
"""bars の semantic equivalence 検証用 sha256 digest (T108).

streaming 化前後で bars 内容が同一であることを確認するために使う検証 utility。
canonical serialization: TSV 1 行 1 bar、 datetime は UTC ISO 8601、 Decimal は
str() でそのまま (正規化なし)、 bool は "true"/"false"。
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC

from src.domain.price import PriceBar


# Round 1 [Suggestion] 4: pair_name を canonical field に含め、 同一バー値で
# 通貨ペアだけ異なるケースも区別できるようにする。
_FIELD_ORDER = (
    "pair_name",
    "bar_time",
    "open_bid",
    "high_bid",
    "low_bid",
    "close_bid",
    "open_ask",
    "high_ask",
    "low_ask",
    "close_ask",
    "volume",
    "complete",
)


def _bar_to_tsv_line(bar: PriceBar) -> str:
    """1 bar を canonical TSV 1 行に直列化する."""
    bt = bar.bar_time
    if bt.tzinfo is None:
        bt = bt.replace(tzinfo=UTC)
    else:
        bt = bt.astimezone(UTC)
    fields = (
        bar.pair_name,
        bt.isoformat(),
        str(bar.bid.open),
        str(bar.bid.high),
        str(bar.bid.low),
        str(bar.bid.close),
        str(bar.ask.open),
        str(bar.ask.high),
        str(bar.ask.low),
        str(bar.ask.close),
        str(bar.volume),
        "true" if bar.complete else "false",
    )
    return "\t".join(fields)


def bars_digest(bars: Iterable[PriceBar]) -> str:
    """bars の semantic equivalence sha256 digest を返す (hex)."""
    hasher = hashlib.sha256()
    for bar in bars:
        hasher.update(_bar_to_tsv_line(bar).encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()
```

### テスト計画

- [ ] `test_bars_digest_identical_inputs_match` — 同じ bar list で digest 一致
- [ ] `test_bars_digest_order_sensitive` — 順序が変わると digest 不一致 (= L2 row order 検証に使える)
- [ ] `test_bars_digest_decimal_preserves_precision` — `Decimal("1.234560")` と `Decimal("1.23456")` の digest が**別物**になることを確認 (= 桁落ち検出可能)
- [ ] `test_bars_digest_complete_field_distinguishes` — complete=True/False で digest が異なる (Round 2 [Warning] 2 反映)
- [ ] `test_bars_digest_naive_datetime_treated_as_utc` — tz-naive な datetime は UTC として扱う (現行 PriceBarM1 は tz-aware だが防御的)

### リスク
- 桁落ち: PostgreSQL `Numeric(12,6)` で取得した Decimal は通常 trailing zero ありで返ってくる。 これを `str()` するとそのまま `"1.234560"` 形式になる。 `.all()` でも `.execute()` でも同じ Decimal が来るので差は出ない (要 fixture 確認)。

---

## C-4. phase marker RSS logger

### 変更箇所
- ファイル: `scripts/alpha_factory/run_ga.py`

### 波及変更
- なし (logger 追加のみ)

### 設計

`_load_lane_bars` 内および aux_bundle 構築直後に phase marker をログ出力する。
psutil でメイン RSS を取り、 logger.info で記録する:

```python
# モジュールトップ付近 (parallel_eval から既に import 済み)
import psutil


def _log_phase_marker(phase: str, **extra: Any) -> None:
    """main プロセス RSS を phase marker として記録する (T108)."""
    error_type: str | None = None
    try:
        rss_mb = psutil.Process().memory_info().rss / 1024 / 1024
    except Exception as exc:  # Round 1 [Suggestion] 5: 例外型も残す
        rss_mb = -1.0
        error_type = type(exc).__name__
    logger.info(
        "run_ga.phase_rss_marker",
        phase=phase,
        main_rss_mb=rss_mb,
        error_type=error_type,
        **extra,
    )
```

挿入箇所:
- `after_pair_resolve`: `pair = ...` の直後
- `after_stage_b_full_load`: `bars_stage_b_full = _stream_bars(...)` 直後
- `after_holdout_load`: `bars_holdout = _stream_bars(...)` 直後
- `after_aux_bundle_built`: `aux_bundle = build_aux_bundle_from_db(...)` 直後
- `before_ga_loop`: GA loop に入る直前

### テスト計画
- [ ] `test_phase_rss_marker_emits_main_rss_mb` — `_log_phase_marker` 呼び出し時に logger event "run_ga.phase_rss_marker" + `main_rss_mb >= 0` field を含む
- [ ] `test_phase_rss_marker_records_error_type_on_psutil_failure` — psutil が例外を投げた場合に `main_rss_mb == -1.0` かつ `error_type` が記録される (Round 2 [Suggestion] 1)

### リスク
- psutil が WARN を出すケース (sandbox 環境等) は -1.0 で代替し fail せず continue。

---

## C-5. smoke 計測 + 判定 (実装後の検証 phase, 設計に含む)

### 実行コマンド (再現性のため明記)

```bash
# baseline (現行 main; 既に 2026-05-20 09:23-09:33 で計測済)
# RSS log: tmp/smoke-logs/smoke_mem_20260520_092357.rss.log
# main peak: 10.7 GB

# after (実装後の同条件)
RUN_ID="smoke_t108_$(date +%Y%m%d_%H%M%S)"
PYTHONFAULTHANDLER=1 uv run python scripts/alpha_factory/run_ga.py \
  --config config/alpha_factory/default.yaml \
  --population-size 24 \
  --generations 5 \
  --max-workers 2 \
  --max-tasks-per-child 12 \
  --seed 9999 \
  --no-report \
  --run-id "$RUN_ID" > tmp/smoke-logs/$RUN_ID.log 2>&1 &
```

並行して RSS 監視を **親 PID 起点の子プロセスツリー集計**で行う (Round 1
[Warning] 2 反映: 無関係 Python プロセスを除外し判定ノイズを排除する)。
phase marker logger (C-4) が main RSS を構造化ログに残すので、 ps サンプリングは
worker 込みの総 RSS の補助計測として使う:

```bash
# 1) run_ga 親 PID を取得
GA_PID=$(pgrep -f "run_ga.py.*$RUN_ID" | head -1)
# 2) 親 + 子孫プロセスのみ集計 (psutil で children(recursive=True))
(while kill -0 "$GA_PID" 2>/dev/null; do
  uv run python - "$GA_PID" <<'PY' >> tmp/smoke-logs/$RUN_ID.rss.log
import sys, time, psutil
pid = int(sys.argv[1])
try:
    p = psutil.Process(pid)
    procs = [p] + p.children(recursive=True)
    total = sum(c.memory_info().rss for c in procs) / 1024 / 1024
    mx = max((c.memory_info().rss for c in procs), default=0) / 1024 / 1024
    print(f"{time.strftime('%H:%M:%S')} n={len(procs)} total_mb={total:.1f} max_mb={mx:.1f}")
except psutil.NoSuchProcess:
    pass
PY
  sleep 5
done) &
```

判定には **C-4 phase marker logger の `main_rss_mb`** を一次情報として使い、
ps ツリー集計は worker 込み総 RSS の傍証とする。 これで「無関係 Python
プロセスの RSS を誤計上する」collider 的ノイズを避ける。

### 判定 (概念設計 § 期待効果 マトリクスに従う)

| 判定 | 条件 | 必要 smoke n | 次アクション |
|---|---|---|---|
| Step C 合格 | main peak 削減 ≥ 1.0 GB | n=1 で可 | 後続 A/E に進む |
| 部分成功 | 0.5 ≤ 削減 < 1.0 GB | n≥3 median delta | A/E 検討、 本施策完了扱い |
| INCONCLUSIVE | < 0.5 GB | n≥3 で再判定 | A/E 直行 |
| REJECTED | 削減なし or 悪化 / テスト fail | n=1 | revert |

### バッチサイズ実験 (smoke n=1 比較)

baseline (10,000) で Step C 合格判定が出なかった場合のみ、 batch size 5,000 で
1 度だけ再 smoke する。 それ以外の batch size 探索は行わない (concept design
Stop/Go)。

---

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | **standalone** |
| 判断根拠 | C-1/C-2 はそれぞれ独立 (run_ga と aux_loader)、 C-3 は新規ファイル、 C-4 は logger 追加のみ。 全体として並行 PR 化は不要だが、 1 PR (1 TODO) で C-1〜C-5 を統合して進めるのが自然。 ロード経路の挙動変更は外向き API を変えないため、 別ブランチでの作業中も main は安定。 |
| 競合リスク | aux_loader の他改修 (例: 別 TODO で aux_pair_bars_index を numpy 化) と同時並行されると merge conflict 発生しうる。 そのため A 候補は本施策 merge 後に着手。 |
| 想定実装時間 | **中** (実装 2-3h + smoke 検証 1h + テスト 1-2h = 半日〜1 日) |
