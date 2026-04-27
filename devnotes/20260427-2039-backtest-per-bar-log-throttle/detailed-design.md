# 詳細設計: backtest per-bar info ログの throttle（呼び出し完全削除 + 集計サマリ化）

## 使命・制約（絶対遵守）

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1-7（A・B・C 評価期間延長 / 数値改善 / GA ハック / live_criteria 緩和 / 過度な複雑化 / 取引回数操作 / オーバーナイト前提）

### コーディングルール
- バグ修正はテストファースト
- 全施策にテスト必須
- テスト命名: 振る舞いを説明する汎用的な名前
- uv 必須: `uv run pytest tests/backtest/`
- ruff / mypy 通過

## 概念設計リファレンス

[devnotes/20260427-2039-backtest-per-bar-log-throttle/conceptual-design.md](./conceptual-design.md)（Round 3 APPROVED）

主要決定:
- per-bar `logger.info(...)` 呼び出し 3 箇所を **完全削除**（DEBUG 降格でもなく削除）
- `run_backtest` の local int カウンタ + 初回 bar_time 記録に置換
- `backtest.finished` に集計フィールド 3 つ追加
- 進捗観測 INFO（`backtest.finished` / `ga.run.done` / `stage_gate.effective_threshold`）は維持

---

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | per-bar log 呼び出し削除 + 集計カウンタ追加 | `src/backtest/engine.py` / `src/broker/mock.py` | High |
| 2 | テスト整備 | `tests/backtest/` (新規 + 既存更新) | High |

---

## 施策 1: per-bar log 呼び出し削除 + 集計カウンタ追加

### 変更箇所

#### 1-A. src/backtest/engine.py

##### 現行コード (L120-185)
```python
    for i, bar in enumerate(bars_list):
        session_closed_bar = bar.bar_time.hour in config.session_close_utc_hours

        # 0. session close bar なら pending の open 系シグナルを先頭で drop
        if session_closed_bar:
            n_dropped = broker.drop_pending_open(reason="session_close.reject_pending_open")
            if n_dropped:
                logger.info(
                    "backtest.session_close.drop_pending",
                    n_dropped=n_dropped,
                    bar_time=bar.bar_time.isoformat(),
                )

        # ... (中略) ...

        # 5. strategy 判断
        snapshot = broker.snapshot()
        signals = strategy.on_bar(bar, snapshot)
        for signal in signals:
            if session_closed_bar and signal.kind in ("open_long", "open_short"):
                logger.info(
                    "backtest.session_close.drop_open_from_strategy",
                    genome_signal=signal.kind,
                    bar_time=bar.bar_time.isoformat(),
                )
                continue
            broker.submit(signal, leverage=config.leverage)

        # ... (中略) ...

    logger.info(
        "backtest.finished",
        instrument=config.instrument,
        bars=len(bars_list),
        trades=len(broker.trades),
        final_equity=str(broker.snapshot().equity),
    )
```

##### 変更後コード
```python
    # ループ前に集計カウンタを初期化
    session_close_drop_open_count: int = 0
    session_close_drop_pending_count: int = 0
    first_drop_open_bar_time: str | None = None

    for i, bar in enumerate(bars_list):
        session_closed_bar = bar.bar_time.hour in config.session_close_utc_hours

        # 0. session close bar なら pending の open 系シグナルを先頭で drop
        if session_closed_bar:
            n_dropped = broker.drop_pending_open()
            if n_dropped:
                session_close_drop_pending_count += n_dropped
                # logger 呼び出しなし（per-bar 完全削除、サマリで集計）

        # ... (中略) ...

        # 5. strategy 判断
        snapshot = broker.snapshot()
        signals = strategy.on_bar(bar, snapshot)
        for signal in signals:
            if session_closed_bar and signal.kind in ("open_long", "open_short"):
                session_close_drop_open_count += 1
                if first_drop_open_bar_time is None:
                    first_drop_open_bar_time = bar.bar_time.isoformat()
                # logger 呼び出しなし
                continue
            broker.submit(signal, leverage=config.leverage)

        # ... (中略) ...

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

#### 1-B. src/broker/mock.py

##### 現行コード (L155-175)
```python
    def drop_pending_open(self, reason: str = "session_close") -> int:
        """session close bar で submit 済 open_long/open_short pending を drop する."""
        before = len(self._pending)
        self._pending = [
            (sig, lev) for (sig, lev) in self._pending
            if sig.kind not in ("open_long", "open_short")
        ]
        dropped = before - len(self._pending)
        if dropped:
            logger.info("broker.drop_pending_open", reason=reason, n=dropped)
        return dropped
```

##### 変更後コード
```python
    def drop_pending_open(self) -> int:
        """session close bar で submit 済 open_long/open_short pending を drop する.

        呼び出し元（engine.run_backtest）が return 値で件数を集計する設計。
        broker 内では log を出さない（per-bar 呼び出しの hot path コスト削減）。
        """
        before = len(self._pending)
        self._pending = [
            (sig, lev) for (sig, lev) in self._pending
            if sig.kind not in ("open_long", "open_short")
        ]
        return before - len(self._pending)
```

**Round 1 [Warning] 2 反映: `reason` 引数を削除**（log 用途で渡されていた引数で、log 削除後は未使用化 → `ARG001` 抵触回避）。呼び出し元 `src/backtest/engine.py:127` も同時に `reason="..."` を削除する。将来 reason 別カウントが必要になったら呼び出し側で渡す形に再設計する（YAGNI、現状は不要）。

### 波及変更
- `AGENTS.md`: なし（per-bar log は元々運用書類で使っていない）
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/*.md`: なし

### ルックアヘッドバイアスチェック
primitive 変更なし → 該当なし

### パフォーマンスチェック（Round 1 Suggestion 反映: ns 単位の断定を削除、相対比較で説明）

- per-bar logger.info の **完全削除**で structlog event_dict 構築 + isoformat() 評価が消える（hot path 最適化として妥当）
- カウンタ更新は Python int +=1（logger 呼び出しと比較して大幅に軽量）
- `first_drop_open_bar_time is None` の判定は per-bar に走るが、is-None 判定はカウンタ更新と同等に軽量
- 数値目標は事前見積りせず、実装後に before/after の log 行数で測定

### テスト計画

#### 削除されるテストカバレッジの確認
- 既存テストで `backtest.session_close.drop_open_from_strategy` / `backtest.session_close.drop_pending` / `broker.drop_pending_open` を assert しているケースがあるか grep
  - 概念設計 §0 P5 で「存在しない」を verified（再確認は実装時 `grep -rn "backtest\.session_close\|broker\.drop_pending_open" tests/`）
  - 既存テストが log 行を期待していなければ更新不要

#### 新規テスト（tests/backtest/test_engine.py に追加）

- [x] **`test_run_backtest_session_close_drop_open_count_in_summary`**
  - mock strategy が session_close bar 帯（session_close_utc_hours の bar）で open_long signal を出す → `backtest.finished` log の `session_close_drop_open_count` が **正確な件数**を持つ
  - `first_drop_open_bar_time` が **最初の発生 bar_time** を ISO 8601 で持つ
  - drop が一度も起きないなら `first_drop_open_bar_time = None`
- [x] **`test_run_backtest_session_close_drop_pending_count_in_summary`**
  - submit → session_close bar 到来 → drop_pending → 集計 → backtest.finished に正確な `session_close_drop_pending_count` が含まれる
- [x] **`test_run_backtest_no_per_bar_drop_log_emitted`**
  - `caplog` で INFO/DEBUG レベルを capture し、`backtest.session_close.drop_open_from_strategy` / `backtest.session_close.drop_pending` / `broker.drop_pending_open` event が **0 行**であることを確認
- [x] **`test_drop_pending_open_returns_count_without_logging`** (tests/broker/test_mock.py)
  - `MockBroker.drop_pending_open()` が return 値で件数を返し、log 呼び出しを行わないことを `caplog` で確認

#### 既存テスト
- 既存の数値同値性（`tests/backtest/test_engine.py` 系）が変更なしで通る（カウンタ追加は数値計算に触らない）

### リスク
- log assertion を持つテストが万一 grep で hit したら更新が必要
- `backtest.finished` の追加 fields が consumer（report 生成等）で表示されない場合、ユーザーが「何が変わった？」と感じる可能性 → 詳細設計 V7 で consumer grep + 互換確認

---

## 施策 2: テスト整備

施策 1 のテスト計画でカバー。新規追加箇所:
- `tests/backtest/test_engine.py`: 集計フィールドのテスト 3 件
- `tests/broker/test_mock.py` または同等: drop_pending_open の return 値テスト 1 件

---

## 検証要件まとめ

| # | 項目 | 合格基準 |
|---|---|---|
| V1 | 既存テスト全パス | `uv run pytest tests/alpha_factory/ tests/backtest/ tests/dsl/ -x` |
| V2 | 数値同値性 | 同一 seed / config / bars で `BacktestResult.trades / equity_curve / final_equity` が baseline と完全一致 |
| V3 | log assertion 互換 | 既存テストで該当 log を assert しているものがあれば更新（`caplog` 使用） |
| V4 | INFO 行数削減（主軸） | 同条件 backtest で per-bar drop 系 INFO 行が **0 行**、`backtest.finished` の 1 行のみ |
| V5 | 集計値の正確性 | drop_open / drop_pending の累計 + `first_drop_open_bar_time` が実発生件数 / 初回 bar_time と一致 |
| V6 | ruff / mypy | `uv run ruff check src/ tests/` PASS, `uv run mypy src/` PASS |
| V7 | consumer 互換 + 呼び出し元固定化（Round 1 W1 反映で「実測」必須化） | (a) **実装時に** `backtest.finished` を消費する src/scripts/tests を grep で列挙し、追加 fields が ignore されることを **実 RUN ログで確認**。(b) `drop_pending_open` 呼び出し元 grep で固定化（実装時点で `engine.run_backtest` のみと verify 済み）。(c) consumer 互換テストを 1 本以上追加（report 生成系の output が変化しないことを smoke test で担保） |
| V8 | 進捗観測の維持 | 小規模 RUN（pop=2, gen=1）で INFO レベルに `backtest.finished` / `ga.run.done` 等が従来通り出る |

---

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | **incremental**（局所変更、他施策との競合なし） |
| 判断根拠 | (1) 変更が src/backtest/engine.py + src/broker/mock.py の 2 ファイル局所、(2) 数値計算に触らない observability 整理、(3) T053/T054 と independent |
| 競合リスク | なし（per-bar 経路は他 TODO で触られていない） |
| 想定実装時間 | **短**（実装 30 分 + テスト 30 分 + 動作確認 15 分） |
