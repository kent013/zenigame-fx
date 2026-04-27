# 概念設計: backtest per-bar info ログの throttle（DEBUG 降格 + 集計サマリ化）

## 0. 前提検証表

| # | 前提 | 状態 | 根拠 |
|---|---|---|---|
| P1 | `backtest.session_close.drop_open_from_strategy` が **per-bar info ログ**として出力されている | **verified** | `src/backtest/engine.py:159-163` の `logger.info` 呼び出し |
| P2 | 同様の per-bar info ログとして `backtest.session_close.drop_pending` が存在 | **verified** | `src/backtest/engine.py:129-132`（n_dropped > 0 時のみ条件付き） |
| P3 | `broker.drop_pending_open` 内にも `logger.info("broker.drop_pending_open", ...)` がある | **verified** | `src/broker/mock.py:172`（n_dropped > 0 時のみ条件付き） |
| P4 | 既存の `backtest.finished` ログは backtest 完了時 1 回のみで、現状 `instrument / bars / trades / final_equity` を出力 | **verified** | `src/backtest/engine.py:179-185` |
| P5 | 既存テストで上記 per-bar ログを assert しているテストは無い | **verified** | `grep -rn "backtest\.session_close" tests/ 2>/dev/null` で hit なし |
| P6 | per-bar ログは数値計算・broker 状態・signal 評価には影響しない（observability のみ） | **verified** | コード読解：`logger.info` の戻り値を捨てている |

## 1. 背景・課題

### 1.1 観測事実（Facts）

ユーザー RUN（2026-04-27 20:38、run-25）の log tail で以下が観測:

- `backtest.session_close.drop_open_from_strategy` の info ログが 1 backtest あたり **数百〜数千行**出ている（log line 例: `bar_time=2026-01-04T23:01:00+00:00 genome_signal=open_long`）
- 1 個体 1 backtest で `backtest.finished bars=183403 trades=539` のような完了 line と、その前後で大量の per-bar drop log
- 本番 RUN は **pop=96 × gen=60 = 5856 個体 × Stage A backtest + Stage A pass × Stage B backtest** の評価で発生
- 1 個体あたり数十〜数千の per-bar drop ログ × 数千個体 = **本番 1 RUN で数百万行〜10M+ 行**オーダーの info ログが stdout / log file に流れる可能性

### 1.2 解釈（Interpretations）

- per-bar の `bar_time` 単位 info ログは **本番運用では debug 用途**であり、INFO レベルで毎回出すのは観点違い
- log I/O コスト（stdout flush, file write, structlog 経由の format）が本番 wall-clock に乗っている可能性が高い（cProfile 上は `_native.py:163 meth (structlog)` が 0.107s として観測されたが、stdout flushing コストは pytest 内 cProfile では小さく出る傾向あり、実 RUN では `logger.info` 呼び出しの format + I/O が重い）
- log ファイルサイズが膨らみ、ログ閲覧時の SN 比が低下している（ユーザーが「IO デカすぎ」と指摘した状況と整合）

### 1.3 副次観点

T053（composite Numba JIT 化）後の profile では `backtest.session_close.drop_open_from_strategy` ログ生成は cProfile cumulative time で見えにくいが、**stdout / file への I/O は cProfile で十分計測されない**（kernel I/O に支配される）。実 RUN の wall-clock 削減という観点では、per-bar info ログを抑えるのは効果が見込める。

---

## 2. 改善アイデア

### 2.1 主軸 — per-bar logger 呼び出しを **完全削除**、集計カウンタ + サマリ 1 行

> **ユーザー指示反映**: per-bar の詳細情報そのものが運用上不要。`logger.debug(...)` でも **kwargs dict 構築 + bound logger 経由のイベント生成コスト**が per-bar に走る（数 10 万回 / backtest）。これを 0 にするには **logger 呼び出しを削除**し、Python int の += 1 だけ残す。

#### 変更概要

per-bar の `logger.info(...)` 呼び出し **3 箇所を完全削除**（DEBUG 降格でもなく削除）:
- `src/backtest/engine.py:129-132` `backtest.session_close.drop_pending`
- `src/backtest/engine.py:159-163` `backtest.session_close.drop_open_from_strategy`
- `src/broker/mock.py:172` `broker.drop_pending_open`

代わりに `run_backtest` の local int カウンタ + 初回 bar_time だけ更新:
```python
session_close_drop_open_count: int = 0
session_close_drop_pending_count: int = 0
first_drop_open_bar_time: str | None = None  # 初回のみ記録
```

backtest 完了時の `backtest.finished` イベントに集計フィールドを追加（既存フィールドを維持しつつ拡張）:
- `session_close_drop_open_count`
- `session_close_drop_pending_count`
- `first_drop_open_bar_time`（drop が 0 件なら `None`）

`broker.drop_pending_open` は **戻り値（n_dropped）を呼び出し側で使ってカウント**する設計に統一（既に return を持つ）。

#### per-bar の比較演算は残るが logger コストは消える

- `if session_closed_bar and signal.kind in ("open_long", "open_short"):` の判定そのものは drop ロジックの仕様で必要、削除しない（これを消すと session_close.drop が動かなくなる）
- 削除するのは **logger 呼び出しと event_dict 構築コスト**のみ
- カウンタ更新（`int += 1`）は数 ns、logger 呼び出し（kwargs format + structlog event_dict）は数 μs → 1000 倍以上の削減効果

#### INFO で残すもの（進捗観測の最低限、変更しない）

- `backtest.finished`（1 個体 1 backtest につき 1 行、集計値追加）
- `ga.run.done`（GA 完了時 1 行）
- `stage_gate.effective_threshold`（startup 1 行、T054 で追加済）
- 既存の WARN / ERROR レベル log（`stage_b.fold_failure` 等）

### 2.2 設計判断の根拠

- **観測（observability）は捨てない**: 詳細はカウントとして集計、必要時に DEBUG レベルで切替可能
- **構造化ログのレベル切替で運用が完結**: 開発時は `LOG_LEVEL=DEBUG` で詳細確認、本番は INFO のまま
- **数値計算には触らない**: 数値同値性 / Stage A/B/C 通過判定 / archive Parquet 全カラム不変

### 2.3 zenigame 側の参考パターン

zenigame の高速化メソドロジー パターン6（ログ出力削減、FX 固有として既に skill 内に明示）に該当。実証パターンとして「DEBUG 降格 + 1 行サマリ集計」がメソドロジー化されている。

---

## 3. 期待効果

### 3.1 機能目標（必須）

- per-bar `drop_open_from_strategy` / `drop_pending` の info ログ出力が消え、DEBUG ログとしてのみ記録される
- `backtest.finished` の 1 行で `session_close_drop_open_count / session_close_drop_pending_count` がサマリ可視化される
- 既存テストが全パス、archive Parquet の per-genome 値が **bit-exact 不変**

### 3.2 性能目標（**副次、INCONCLUSIVE**）

**Codex Warning 4 反映で「INFO 行数削減」を主軸、wall-clock は参考指標に格下げ**:

- 主軸: 本番 RUN の **INFO ログ行数の大幅削減**（実装後に before/after 計測、数値目標は実装時に決定）
- 参考: log I/O 削減による wall-clock 改善（INCONCLUSIVE: cProfile では捕捉しきれない領域。本指標を合否基準にしない）

### 3.3 使命への貢献

- 直接的な live_criteria 数値操作なし（observability の整理）
- 本番 RUN の log SN 比向上 → 異常検知が容易になる → 機能不全の早期発見（T054 のような pipeline 健全性問題を再発させた場合の検知速度向上）

---

## 4. 実装方針（概要）

### 4.1 変更箇所

- `src/backtest/engine.py` (L120-185 周辺):
  - per-bar `logger.info(...)` 呼び出しを **削除** (2 箇所)
  - 集計カウンタ `session_close_drop_open_count` / `session_close_drop_pending_count` / `first_drop_open_bar_time` を関数 local に追加
  - `backtest.finished` の info ログに集計値を追加
- `src/broker/mock.py` (L172 周辺):
  - `logger.info("broker.drop_pending_open", ...)` 呼び出しを **削除**（`return n_dropped` は維持、呼び出し側で集計）

### 4.2 集計の実装

```python
# engine.run_backtest 内、ループ前に初期化
session_close_drop_open_count: int = 0
session_close_drop_pending_count: int = 0
first_drop_open_bar_time: str | None = None

# ループ内 (drop_pending 検出時) - logger 呼び出しなし
n_dropped = broker.drop_pending_open(reason="session_close.reject_pending_open")
if n_dropped:
    session_close_drop_pending_count += n_dropped

# ループ内 (drop_open_from_strategy) - logger 呼び出しなし
if session_closed_bar and signal.kind in ("open_long", "open_short"):
    session_close_drop_open_count += 1
    if first_drop_open_bar_time is None:
        first_drop_open_bar_time = bar.bar_time.isoformat()
    continue

# ループ後、backtest.finished に集計値を追加して 1 行で出力
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

`src/broker/mock.py:172` の `logger.info("broker.drop_pending_open", ...)` も同様に削除（`return n_dropped` は維持）。

---

## 5. 制約・前提

### 5.1 数値・絶対制約

- 本変更は **observability のみ**で、backtest 数値・broker 状態・signal 評価には触らない
- T053 / T054 の数値同値性 bit-exact 検証結果を破壊しない
- イントラデイ / ロング・ショート / swap・spread 反映の絶対制約は不変

### 5.2 後方互換

- 既存テストで「該当 info ログが出ること」を assert しているテストは **存在しない**（P5 verified）
- ログ assertion を持つテストが万一あれば、`caplog.set_level(logging.DEBUG)` で対応可能であることを担保
- `backtest.finished` への新フィールド追加は schema 拡張（既存 consumer は追加 fields を ignore できる）
- **Codex Warning 8 反映**: report 生成 / archive flush / run_report.md 生成等の `backtest.finished` consumer に対して「追加 field を ignore できるか」を **詳細設計で grep + 検証要件化**する。consumer 影響が出る場合は consumer 側も追加対応（追加 field を表示 or 無視）

### 5.3 禁止事項の遵守

- 数値操作なし（禁止 2）
- 評価期間延長なし（禁止 1）
- 取引回数の見せ方変更なし（禁止 6、本変更は trades count を可視化する方向で「隠す」変更ではない）

### 5.4 並行経路の確認 (C2)

`drop_pending_open` は engine.py からだけでなく broker.mock.py 内の他経路から呼ばれる可能性がある。**broker.mock.py の `logger.info` も同時降格**する（§4.1）。grep で確認済み（`src/broker/mock.py:172` のみ）。

---

## 6. スコープ外

- structlog 全体の log level 戦略再設計
- 他モジュール（calibrate-gate / stage_gate / archive flush / parallel_eval）の per-call ログ調整 — それぞれ別 TODO で扱う
- ログフォーマット変更（json / colorize 等）
- log file rotation 設定

---

## 7. 検証計画（概要、詳細設計で具体化）

| # | 項目 | 合格基準 |
|---|---|---|
| V1 | 既存テスト全パス | `uv run pytest tests/alpha_factory/ tests/backtest/ tests/dsl/ -x` |
| V2 | 数値同値性 | 同一 seed / config / bars で baseline と最新の `BacktestResult.trades / equity_curve / final_equity` が完全一致 |
| V3 | log assertion 互換 | log を assert しているテストがあれば `caplog.set_level(logging.DEBUG)` で挙動再現 |
| V4 | log INFO 行数削減（主軸） | 同条件 backtest で per-bar INFO 行数が **0 行**、`backtest.finished` に集計値が含まれる。DEBUG レベルでも per-bar 行は出ない（呼び出し自体が削除されているため） |
| V5 | 集計値の正確性 | drop_open / drop_pending の累計が、テスト内 broker / engine から観測した実際の drop 件数と一致するテスト追加。`first_drop_open_bar_time` が初回発生 bar_time と一致 |
| V6 | ruff / mypy | `uv run ruff check src/ tests/` PASS, `uv run mypy src/` PASS |
| V7 | consumer 互換 + 呼び出し元固定化（Codex W8 + Round 3 W 反映） | (a) `backtest.finished` を消費する経路（report 生成 / archive flush 等）を grep で列挙し、追加 fields が ignore されることを確認。(b) `broker.drop_pending_open` の呼び出し元一覧を grep で固定化（現状 `engine.run_backtest` のみ）。将来呼び出し元が増えた場合は呼び出し側で集計を持つ運用ルールを README/AGENTS.md に明記 |
| V8 | 進捗観測の維持（ユーザー指示） | 本番 RUN 模擬（pop=2, gen=1 程度の最小規模）で、INFO レベル log に backtest 完了行 / GA 進捗行が**従来通り**出ることを確認 |
