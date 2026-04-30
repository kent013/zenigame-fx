# 詳細設計: negative equity 再発の根本修正（多層防御 + OANDA spec 文書化）

## 使命・制約（絶対遵守）

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1-7（評価期間延長 / 数値改善 / GA ハック / live_criteria 緩和 / 過度な複雑化 / 取引回数操作 / オーバーナイト前提）

### コーディングルール
- バグ修正はテストファースト
- 全施策にテスト必須
- uv 必須、ruff / mypy 通過

## 概念設計リファレンス

[devnotes/20260427-2122-negative-equity-followup/conceptual-design.md](./conceptual-design.md)（Round 3 APPROVED）

主要決定:
- L1 (`fill_pending` 冒頭) + L2 (`_open_position` 内) の **多層防御**
- 非有限値 / 非正値判定: `equity.is_finite() and equity > 0`
- L2 例外（`InsufficientEquityError`）は `fill_pending` ループ内で個別捕捉、bar 継続
- counter は **pop semantics**（複数 backtest 混線防止）
- `maintenance_margin_level_pct` config 化 / `available_margin >= required_margin` gate は別 TODO に分離
- OANDA 準拠は既存 `force_close_if_margin_call` で確保済み、本 TODO では runbook.md に文書化のみ

---

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | 多層防御（L1 + L2 + InsufficientEquityError + counter） | `src/broker/mock.py` / `src/broker/orders.py` (or 新規 `errors.py`) | High |
| 2 | engine.py で counter を pop して `backtest.finished` log に集計値追加 | `src/backtest/engine.py` | High |
| 3 | テスト整備 | `tests/broker/test_mock_broker.py` / `tests/backtest/test_engine.py` | High |
| 4 | OANDA spec 文書化 | `docs/alpha_factory/runbook.md` | Medium |

---

## 施策 1: 多層防御の実装

### 1-A. 新規 exception `InsufficientEquityError`

`src/broker/orders.py` 末尾に追加（既存ファイル末尾、新規ファイル作成は避ける）。

**Round 1 [Critical] 5 反映**: `ValueError` 継承だと既存の広域 `except ValueError` に誤捕捉される可能性 → **`Exception` 直系**にして domain 限定の例外として扱う:

```python
class InsufficientEquityError(Exception):
    """`_open_position` で equity_at_entry が非有限値または非正値の場合に raise。

    `fill_pending` のループ内で個別捕捉し、当該 signal を drop 扱いとして
    counter に加算してループ継続する設計（fail-closed の「停止」ではなく「拒否」）。
    L1 (`fill_pending` 冒頭 gate) を通り抜けた異常経路の最終防御として機能する。

    `Exception` 直系で `ValueError` 派生にしない理由（Round 1 [Critical] 反映）:
    既存コードに `except ValueError` を広域に書いた catcher があると、本例外が
    意図せず捕捉されて drop counter に加算されない silent な発生経路を生む。
    domain 限定の `InsufficientEquityError` として明示捕捉する。
    """
```

### 1-B. `_is_finite_decimal` helper

`src/broker/mock.py` 上部に追加:

```python
def _is_finite_decimal(value: Decimal) -> bool:
    """Decimal が有限値（NaN / Infinity でない）か判定。

    Decimal('NaN') / Decimal('Infinity') を `<= 0` 比較すると InvalidOperation を
    起こすため、比較演算前に本 helper でガードする。
    """
    return value.is_finite()
```

`Decimal.is_finite()` は標準ライブラリにあるため独自実装不要だが、可読性向上のため helper として export しておく（変更時の影響範囲を狭めるため）。

### 1-C. `MockBroker.__init__` への counter 追加

```python
class MockBroker:
    def __init__(self, ..., maintenance_margin_level_pct: Decimal = Decimal("100")):
        ...
        self._negative_equity_drop_count: int = 0  # 新規
```

### 1-D. `fill_pending` の L1 gate + L2 例外捕捉

現行コード（mock.py:172-221）の構造:
```python
def fill_pending(self, bar: PriceBar) -> list[Trade]:
    if bar.pair_name != self._meta.oanda_name:
        raise ValueError(...)
    
    # spread filter (既存)
    if (self._max_spread_bps is not None and ...):
        before = len(self._pending)
        self._pending = [...]  # spread 違反の open 系を drop
        ...
    
    pre_fill_equity = self._snapshot_at(bar).equity
    
    trades: list[Trade] = []
    for signal, leverage in self._pending:
        if signal.kind == "open_long":
            self._open_position(...)
        elif signal.kind == "open_short":
            self._open_position(...)
        elif signal.kind == "close_position":
            ...
        elif signal.kind == "close_all":
            ...
    self._pending.clear()
    return trades
```

変更後:
```python
def fill_pending(self, bar: PriceBar) -> list[Trade]:
    if bar.pair_name != self._meta.oanda_name:
        raise ValueError(...)
    
    # spread filter (既存)
    if (self._max_spread_bps is not None and ...):
        ...
    
    pre_fill_equity = self._snapshot_at(bar).equity
    
    # L1: equity 非有限値 / 非正値での open 系 drop（fail-closed）
    # 注: 同 bar 内の close signal による equity recovery は意図的に取り逃がす
    # （conservative policy、設計 §2.3 参照）
    if not _is_finite_decimal(pre_fill_equity) or pre_fill_equity <= Decimal(0):
        before = len(self._pending)
        self._pending = [
            (sig, lev) for (sig, lev) in self._pending
            if sig.kind not in ("open_long", "open_short")
        ]
        self._negative_equity_drop_count += before - len(self._pending)
    
    trades: list[Trade] = []
    for signal, leverage in self._pending:
        if signal.kind == "open_long":
            try:
                self._open_position(
                    "long", cast(int, signal.units), bar.ask.open, bar.bar_time, leverage,
                    equity_at_entry=pre_fill_equity,
                )
            except InsufficientEquityError:
                # L2 が発火 = L1 を通り抜けた異常経路。drop 扱いで継続
                self._negative_equity_drop_count += 1
                continue
        elif signal.kind == "open_short":
            try:
                self._open_position(
                    "short", cast(int, signal.units), bar.bid.open, bar.bar_time, leverage,
                    equity_at_entry=pre_fill_equity,
                )
            except InsufficientEquityError:
                self._negative_equity_drop_count += 1
                continue
        elif signal.kind == "close_position":
            if signal.position_id is None:
                raise ValueError("close_position requires position_id")
            trade = self._close_one(signal.position_id, bar, exit_kind="open", reason="signal")
            if trade is not None:
                trades.append(trade)
        elif signal.kind == "close_all":
            trades.extend(self._close_all_internal(bar, exit_kind="open", reason="signal"))
    self._pending.clear()
    return trades
```

### 1-E. `_open_position` の L2 最終防御

現行コード（mock.py:312-340）:
```python
def _open_position(
    self,
    side: PositionSide,
    units: int,
    entry_price: Decimal,
    entry_time,
    leverage: int,
    *,
    equity_at_entry: Decimal,
) -> Position:
    notional = notional_home_currency(...)
    margin = required_margin(notional, leverage)
    pos = Position(...)
    ...
```

変更後:
```python
def _open_position(
    self,
    side: PositionSide,
    units: int,
    entry_price: Decimal,
    entry_time,
    leverage: int,
    *,
    equity_at_entry: Decimal,
) -> Position:
    # L2: defensive guard（L1 を通り抜ける経路があれば fail-fast）
    # `fill_pending` ループ内で InsufficientEquityError を捕捉して drop 扱いに統一
    if not _is_finite_decimal(equity_at_entry) or equity_at_entry <= Decimal(0):
        raise InsufficientEquityError(
            f"_open_position called with non-finite or non-positive equity: "
            f"{equity_at_entry}"
        )
    notional = notional_home_currency(...)
    margin = required_margin(notional, leverage)
    pos = Position(...)
    ...
```

### 1-F. counter の母集団定義（Round 1 [Warning] 6 反映）

`negative_equity_drop_count` の集計対象を**明文化**（runbook + 後段テストの test 名で）:

- **集計対象**: L1 gate（`fill_pending` 冒頭、equity 非有限値 / 非正値時）で drop された open 系 signal 件数 + L2 例外（`_open_position` 内）で reject された open 系 signal 件数
- **集計対象外**: spread filter で drop された signal（既存 `broker.submit.rejected_by_spread` 経路、別 counter で集計可だが本 TODO スコープ外）、session_close で drop された signal（T055 で導入済み別 counter `session_close_drop_*`）

つまり「**negative equity 起因のみ**」の drop counter であり、spread / session_close 起因とは独立。

### 1-G. `pop_negative_equity_drop_count` accessor (pop semantics)

```python
def pop_negative_equity_drop_count(self) -> int:
    """L1 + L2 で drop した open 系 signal の累計件数を返し、内部 counter を 0 に reset。

    pop semantics: 呼び出すたびに「前回 pop 以降の累計」を返す。
    複数 backtest 連続実行や broker 再利用時の混線を防ぐ。

    `run_backtest` は backtest 完了時に 1 回 pop して `backtest.finished` log の
    `negative_equity_drop_open_count` field に渡す。
    """
    n = self._negative_equity_drop_count
    self._negative_equity_drop_count = 0
    return n
```

### 波及変更
- `AGENTS.md`: なし（既存運用変更なし）
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/runbook.md`: 施策 4 で「OANDA 準拠の margin closeout 設計」セクション追加

### テスト計画

新規テスト（`tests/broker/test_mock_broker.py` に追加）:
- [x] `test_fill_pending_drops_open_signals_when_equity_is_zero` — equity=0 で open_long pending を drop、close 系は影響なし、drop count = 1
- [x] `test_fill_pending_drops_open_signals_when_equity_is_negative` — equity=-100 で open_short pending を drop、drop count = 1
- [x] `test_fill_pending_does_not_drop_when_equity_positive` — equity > 0 で通常 open、drop count = 0
- [x] `test_fill_pending_drops_open_signals_when_equity_is_nan` — equity=Decimal('NaN') で fail-closed drop（InvalidOperation を起こさず）
- [x] `test_fill_pending_drops_open_signals_when_equity_is_infinity` — equity=Decimal('Infinity') / Decimal('-Infinity') 両方で drop
- [x] `test_fill_pending_close_signal_not_dropped_under_negative_equity` — equity 負でも close_position は通常実行
- [x] `test_open_position_raises_insufficient_equity_error_for_zero_equity` — _open_position 直接呼び出しで equity=0 → InsufficientEquityError
- [x] `test_open_position_raises_insufficient_equity_error_for_nan_equity` — equity=NaN で InsufficientEquityError
- [x] `test_pop_negative_equity_drop_count_resets_counter` — 1 度 pop すると次回は 0、累積カウントは pop 間のみ
- [x] `test_pop_negative_equity_drop_count_zero_initially` — 初期値 0
- [x] `test_fill_pending_l2_exception_continues_loop` — L1 を bypass する人工テストで L2 が発火しても bar 処理は中断せず、close 系は実行される
- [x] **`test_fill_pending_close_all_signal_not_dropped_under_negative_equity`**（Round 1 [Warning] 7 反映）— equity 負で close_all signal は通常実行される（drop counter 非加算）
- [x] **`test_fill_pending_drop_count_independent_from_spread_reject`**（Round 1 [Warning] 7 反映）— spread filter による reject と negative equity drop が同時に発生するケースで、各 counter が独立して正しく集計される（spread counter は `_negative_equity_drop_count` に加算されない）

### リスク
- L2 例外を broker 外に漏らすと bar 処理が中断する → **L1 通り抜け経路があれば fill_pending で必ず捕捉する設計を厳守**
- `Decimal.is_finite()` の挙動が Python バージョン依存しないか確認（Python 3.11+ で stable）
- 既存テストで「破産シナリオで trade が生成される」を assert しているテストがある場合、契約変更（破産 → trade 0）に合わせて更新必須

---

## 施策 2: engine.py で counter を pop して log に集計

### 変更箇所
`src/backtest/engine.py` の `run_backtest` 末尾、`backtest.finished` log 出力箇所

### 現行コード（T055 後の状態）
```python
logger.info(
    "backtest.finished",
    instrument=config.instrument,
    bars=len(bars_list),
    trades=len(broker.trades),
    final_equity=str(broker.snapshot().equity),
    session_close_drop_open_count=session_close_drop_open_count,
    session_close_drop_pending_count=session_close_drop_pending_count,
    first_drop_open_bar_time=first_drop_open_bar_time,
)
```

### 変更後
```python
negative_equity_drop_open_count = broker.pop_negative_equity_drop_count()

logger.info(
    "backtest.finished",
    instrument=config.instrument,
    bars=len(bars_list),
    trades=len(broker.trades),
    final_equity=str(broker.snapshot().equity),
    session_close_drop_open_count=session_close_drop_open_count,
    session_close_drop_pending_count=session_close_drop_pending_count,
    first_drop_open_bar_time=first_drop_open_bar_time,
    negative_equity_drop_open_count=negative_equity_drop_open_count,
)
```

### テスト計画
- [x] `test_run_backtest_negative_equity_drop_count_in_summary` — 破産シナリオで `backtest.finished` log の `negative_equity_drop_open_count` が正確な件数を持つ

### 波及変更
- なし（broker accessor 経由で取得、broker API は維持）

---

## 施策 3: テスト整備

施策 1 / 2 の test 計画でカバー。配置:
- `tests/broker/test_mock_broker.py`: 11 件追加
- `tests/backtest/test_engine.py`: 1 件追加

---

## 施策 4: OANDA spec 文書化

### 変更箇所
`docs/alpha_factory/runbook.md` に新規セクション追加（既存内容は維持）。

### 追加内容（概略）
```markdown
## OANDA 準拠の margin closeout 設計（既存実装の文書化）

zenigame-fx の MockBroker は OANDA v20 / OANDA Japan の強制ロスカット仕様に準拠する。

### OANDA 仕様（参考: developer.oanda.com/rest-live-v20）
- `marginCloseoutPercent ≥ 1.0`（=維持率 100% 以下）で margin closeout 発動
- 発動時は全保有 position を成行で順次強制決済
- OANDA Japan は JFSA 規制下で同等仕様

### 本実装での対応
- 閾値: `MockBroker.__init__(maintenance_margin_level_pct=Decimal("100"))`
- 発動経路: `force_close_if_margin_call` (mock.py:278) を `engine.run_backtest` per-bar で呼び出し
- 発動時挙動: `_close_all_internal(reason="margin_call")` で全 position close
- 発注価格: 当該 bar の bid/ask（成行相当）

### 多層防御の追加（本 TODO で追加）
- 上記は「保有中 position」に対する強制ロスカット（OANDA 準拠）
- 「保有 0 + cash マイナス時の新規 entry block」は OANDA spec とは独立の構造的バグ対策
- L1: `fill_pending` 冒頭で equity 非有限値 / 非正値時に open 系 pending drop
- L2: `_open_position` で `InsufficientEquityError` raise（最終防御）

### 別 TODO 候補（本 TODO スコープ外）
- `available_margin >= required_margin` gate（過大 notional の entry reject）
- `maintenance_margin_level_pct` の config 化
```

### 波及変更
- なし（runbook 追記のみ）

### テスト計画
- なし（ドキュメント更新）

---

## ルックアヘッドバイアスチェック
primitive 変更なし、該当なし。

## パフォーマンスチェック
- L1 の `pre_fill_equity` は既に `_snapshot_at(bar)` で取得されているため追加コストなし
- L1 判定は per-bar に走るが、`is_finite()` + `<= 0` 比較は Decimal 上で軽量
- L2 は `_open_position` 1 回 / signal で発火、追加コストはほぼ無視できる

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | **incremental**（局所変更、他施策との競合少） |
| 判断根拠 | (1) 変更が src/broker/mock.py + src/broker/orders.py + src/backtest/engine.py + tests + docs の局所、(2) 数値計算に触らない fail-closed gate 追加、(3) T053 / T054 / T055 と independent |
| 競合リスク | 低。drop_pending_open（T055 で改修済）と同階層の処理だが衝突なし |
| 想定実装時間 | **短〜中**（実装 1 時間 + テスト 1.5 時間 + 動作確認 30 分） |

---

## 検証要件まとめ

| # | 項目 | 合格基準 |
|---|---|---|
| V1 | 既存テスト全パス | `uv run pytest tests/alpha_factory/ tests/backtest/ tests/dsl/ tests/broker/ -x` |
| V2 | 数値同値性 | 同一 seed / config / bars で「破産しない genome」の trade / equity_curve / final_equity が baseline と完全一致 |
| V3 | 破産シナリオ test | equity が 0 / 負 / NaN / Infinity の各ケースで fill_pending が open 系 pending を drop し、close 系は影響なし、counter が正確 |
| V4 | warning 件数の劇的減少 | 実 RUN ログで `trade_return.invalid_equity_at_entry` が消えるか「適切な量」（数件以下）に収まる |
| V5 | ruff / mypy | `uv run ruff check src/ tests/` PASS, `uv run mypy src/` PASS |
| V6 | broker → engine 通信 | `pop_negative_equity_drop_count` の pop semantics（呼び出しで reset、複数 backtest 混線しない）unit test |
| V7 | L2 例外の捕捉 | L1 を bypass する人工テストで L2 が発火しても bar 処理は中断せず、close 系 signal は影響なく実行される |
