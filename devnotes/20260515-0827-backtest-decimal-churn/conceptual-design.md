# 概念設計: backtest hot path の Decimal churn 削減 (T105)

## 前提検証（C4 — verified / unverified の明示）

Codex Round 1 が未確認とした前提を、本改訂でコード調査により verify した。

| 前提 | 状態 | 根拠 |
|---|---|---|
| `equity` は `cash + unrealized` で、両者とも除算を含まない | **verified** | `src/broker/mock.py` `_snapshot_at`: `equity = self._cash + unrealized`。`unrealized` は `_unrealized_pnl` → `_realized_pnl` = `Decimal(units) * (price_diff)`（積のみ）。`_cash` は `+= raw_pnl`（積）と holding cost 減算。 |
| 除算経路（`required_margin = notional / leverage`、holding cost の bps/時間按分）は `equity` に含まれない | **verified** | `required_margin` の結果 `margin` は `equity` ではなく `margin_used` 側。holding cost は `engine.py:147` で `if config.holding_cost_per_day_bps > 0` ガード下、`config/alpha_factory/default.yaml:41` は `"0"` → AF RUN では holding cost 経路自体が dead。 |
| → AF 設定下では `equity` の小数桁数は price quote の桁数（JPY pair ~3、その他 ~5）に bounded | **verified（AF 設定下）** | 上記 2 点の帰結。`holding_cost_per_day_bps > 0` を有効化した場合は除算経路が生き、この bound は崩れる（後述の fail-closed guard で対応）。 |
| `MockBroker` / `margin.py` に `equity` 確定の `quantize` / 明示丸めは無い | **verified** | `src/broker/` 全体に `quantize` / `ROUND_` 不在。 |
| `trade_sharpe_raw`（GA fitness 本命）は `equity_curve` 非依存 | **verified** | `src/backtest/metrics.py` `_trade_returns(trades)` = `t.pnl / t.equity_at_entry`、`Trade` 由来。`equity_curve` 非参照。 |
| `equity_curve` の consumer 範囲 | **verified** | `compute_metrics`（metrics.py）/ `equity_curve_to_bar_equity_series`（canonical_adapter.py、既に `float(eq)` 化）/ `stage_gate.py`（typed param 2 箇所 + access 多数）/ `cross_pair.py` / `ga/fitness.py` / `ensemble.py`（`combined_equity` を自前構築）/ `grid_search.py` / `walk_forward.py` / `report.py`。`paper_trading` は `BacktestResult` 非依存（**未消費**）。 |
| churn の量的支配項が `equity_curve` であること | **unverified（仮説）** | retained object 数では有力だが、`MockBroker` 内部の transient Decimal churn 量は未計測（Codex Round 1 [Warning] 反映 → 「第一候補」に降格、後述）。 |

## 背景・課題

### root cause（確定済み）

`devnotes/20260514-2045-ga-worker-memory/` でライブ RUN を vmmap + 実測調査し、GA worker の per-worker RSS 肥大（5.5〜8.7GB）の root cause = **pymalloc アリーナの断片化**を確定済み。`run_backtest` が生成する `Decimal` / `datetime` / 小 `tuple` の大量 churn が ≤512 byte 小オブジェクトとして pymalloc アリーナを断片化させ、pymalloc は **アリーナが 100% 空になるまで OS に返さない**ため残存する。緩和策 `maxtasksperchild`（commit `a1ed996`）は worker 定期リサイクルで peak を頭打ちする**対症療法**。本 T105 は churn 発生源を構造的に断つ**根本対応**。

### Decimal churn 連鎖（コード調査で確認した Fact）

| 箇所 | churn の内容 |
|---|---|
| `src/backtest/engine.py:180` | `equity_curve.append((bar.bar_time, broker.snapshot().equity))` を bar ごと。型 `list[tuple[datetime, Decimal]]`。Stage B IS monitor 約 20 万 bars、fold backtest 約 33 本 × 約 2 万 bars。1 genome の Stage B 評価で `equity_curve` 由来だけで約 90 万要素（tuple + datetime + Decimal）。**しかも `BacktestResult.equity_curve` として backtest 寿命中ずっと retain される**。 |
| `src/broker/mock.py` | `MockBroker` が cash / equity / margin / pnl 演算を全て Decimal で実行。per-bar の transient Decimal 中間オブジェクトを生成（churn 量は未計測）。 |
| `src/broker/orders.py` | `Trade` が Decimal × 6。件数は `live_criteria.trade_count_max` で上限（数千）。 |

## 改善アイデア

backtest engine 内の Decimal 演算を **「精度 load-bearing」と「精度非要求（時系列蓄積・統計集計用）」に切り分け**、後者を numpy 配列化して小オブジェクト churn を構造的に削減する。

### 精度 load-bearing（Decimal 維持・本 T105 では触らない）

金額の正しさに直結する領域: 約定価格計算（`fill_pending`）/ margin・leverage 判定 / 手数料・スプレッド・holding cost 計算 / `Trade.pnl` 等の確定値。

### 改善方針: `equity_curve` を lossless scaled-int64 numpy 配列へ（第一候補施策）

`equity_curve: list[tuple[datetime, Decimal]]` を、`run_backtest` が bar 数を起動時に知っている（`bars_list = list(bars)`）ことを利用して **専用ラッパー型 `EquityCurve`** に置き換える。内部は **事前確保した numpy 配列 2 本**:

- `bar_time_epoch: np.ndarray[int64]` — `bar_time` を epoch 整数（ns）に（datetime → epoch は lossless）
- `equity_scaled: np.ndarray[int64]` — equity を**固定スケール整数** `equity × 10^k` に

蓄積される実体が「90 万個の小オブジェクト（tuple/datetime/Decimal）」→「numpy 連続バッファ 2 本」になり、`BacktestResult` が retain する小オブジェクトが消える。

#### lossless の定義（Codex Round 1 [Critical 1] 反映 — 保存表現と比率計算を分離）

**「保存表現が lossless」と「比率計算が bit-exact」は別物**。本設計の正確な主張:

- **保存表現**: `encode(equity_decimal) → scaled-int64 → decode → equity_decimal` の往復が **lossless**（後述の guard で保証）。
- **`final_equity` / `max_drawdown`（絶対額）/ peak・dd 比較**: scaled-int64 上の整数比較・整数減算で計算でき、現行 Decimal 計算と **bit-exact 一致**。
- **`max_drawdown_pct` (`dd / peak * 100`) / `calmar`（比率計算を含む）**: 整数のままでは bit-exact にならない。→ **scaled-int64 から `decode` で `Decimal` を復元し、現行と完全に同一の Decimal 演算経路（同一 context・同一丸め規約）で算出する**。`dd` / `peak` が lossless に復元できるため、この経路で bit-exact が成立する。
- **`_bar_returns`（v1 sharpe 用、既に `float` 化済み・GA fitness 非本命）**: 各 bar で `decode` して Decimal を復元し現行と同一経路（`float((eq-prev)/prev)`）で算出 → bit-exact。復元は `compute_metrics` 内の transient（`BacktestResult` には retain されない）。

→ **検証は shadow test 必須**: 旧実装（`list[tuple[datetime, Decimal]]`）と新実装を同一入力で二重計算し、`compute_metrics` の全出力フィールド（特に gate-feeding の `max_drawdown` / `max_drawdown_pct` / `final_equity` / `calmar`）が完全一致することを確認する。

#### スケール係数 `k` の根拠と fail-closed guard（Codex Round 1 [Critical 2] / [Warning 1] 反映）

- `k` の根拠: 前提検証より、AF 設定下で `equity` の小数桁数は price quote 桁数（≤5）に bounded。安全側に **`k = 10`** を採る（実際の必要桁の 2 倍マージン）。`k` を「`equity` が取りうる最小量子」基準で決め、price 桁数だけに依存しない設計にする。
- **fail-closed `encode` guard**: `encode(equity)` は (1) `scaled = equity.scaleb(k)` を Python `int` として生成し `scaled == int(scaled)`（整数性）を検証、(2) `abs(scaled) <= 2^63 - 1`（overflow）を検証、(3) いずれか不成立なら **`RuntimeError` で fail-closed**（silent precision loss を構造的に排除）。これにより、`holding_cost_per_day_bps > 0` 有効化等で `equity` の桁数前提が崩れた場合は静かに壊れず即座に検知される。
- overflow 上界式（devnotes に固定）: `max_abs_equity_bound × 10^k < 2^63`。`max_abs_equity_bound` は初期資金ではなく、**設定上取りうる最大ポジション notional × 最大有利変動 + 初期資金** を含む保守上界で定義する。例: 初期資金 100 万 + 想定上限利益。`k=10` なら `max_abs_equity_bound < 9.2 × 10^8` まで許容（initial_cash 100 万に対し十分）。詳細設計で具体値を確定。

### `MockBroker` 内部 churn・`Trade` の扱い（Codex Round 1 [Warning 2] 反映）

- 「`equity_curve` が churn の量的支配項」は **第一候補の仮説**であり falsification 未了。**受け入れ条件**: `equity_curve` 改修後に worker RSS（median / p95）と backtest throughput（genome/s）を再計測し、残差が大きければ Phase 1 で `MockBroker` 内部 transient Decimal churn の計測へ進む。
- `MockBroker` 内部 churn の float 化は精度 load-bearing 領域のため安易に行わない（別タスク・別設計サイクル）。
- `Trade` は件数上限ありで churn 寄与小 → 本 T105 スコープ外。

## 期待効果

- **直接効果**: 1 backtest あたり最大候補の churn 源（`equity_curve` 約 90 万小オブジェクト/genome、かつ backtest 寿命中 retain）を numpy 連続バッファ化。pymalloc アリーナ断片化の発生源を構造的に削減し、`maxtasksperchild`（対症療法）依存度を下げ per-worker RSS のベースラインを下げる。
- **lossless 設計のため、ステージゲート・live_criteria 判定は不変**（gate-feeding 指標を bit-exact 維持。shadow test で verify）。
- **使命への寄与（間接）**: 探索基盤の制約解除（OOM/swap リスク除去、複数ペア swim-lane 拡張の前提、population/generations を増やせる余地）。live_criteria を直接動かすものではない。

### 期待効果の検証方法（Codex Round 1 [Suggestion] 反映 — sample size 固定）

同一 seed・同一 dataset・同一 worker 数で、改修前後それぞれ **n ≥ 5 の worker lifecycle** を比較し、(1) per-worker RSS の median / p95、(2) swap 発生有無、(3) genome/s（throughput）を記録する。メモリ改善は run-to-run ばらつきがあるため n を固定して比較する。

## 実装方針（概要）

| 対象 | 変更概要 |
|---|---|
| 新規 `EquityCurve` 型 + scaled-int 変換ヘルパ | numpy 配列 2 本を包む専用型。`encode` / `decode`（fail-closed guard 付き）、access API（`final_equity()` / drawdown 計算用 iterator 等）を限定提供。consumer が生 numpy を直接触らない |
| `src/backtest/engine.py` | `equity_curve` を `EquityCurve` の事前確保バッファへ index 代入。`BacktestResult.equity_curve` の型変更 |
| `src/backtest/metrics.py` | `compute_metrics` の `equity_curve` 引数を `EquityCurve` 対応に。`max_drawdown` / `final_equity` は整数経路、`max_drawdown_pct` / `calmar` / `_bar_returns` は `decode` → 現行同一 Decimal 経路 |
| `src/alpha_factory/canonical_adapter.py` | `equity_curve_to_bar_equity_series` を `EquityCurve` 対応に（既に `float(eq)` 化しているため影響小） |
| `src/alpha_factory/stage_gate.py` | typed param（2 箇所）+ access 多数を `EquityCurve` API 経由に追従 |
| consumer 追従 | `ga/fitness.py` / `cross_pair.py` / `ensemble.py`（`combined_equity` 構築経路）/ `grid_search.py` / `walk_forward.py` / `report.py`。詳細設計で全箇所を列挙し 4 段接続漏れを排除 |

## 制約・前提

- **決定論契約 L1/L2 の維持**: equity_curve 表現変更は worker 数非依存。lossless + Decimal 復元経路により gate 判定が変わらないことを shadow test（旧/新 二重計算、全 `compute_metrics` 出力一致）+ 「同一 seed・同一 dataset で改修前後の archive の `max_drawdown_pct` / stage pass-fail / live_criteria 判定が完全一致」で verify。
- **金額計算の正しさを変えない**: 精度 load-bearing 領域（約定・margin・手数料）は Decimal のまま。本 T105 は触らない。
- **スワップ・スプレッド反映の維持**: `spread_cost` / `holding_cost` 計算経路は不変。
- **公開構造の変更**: `BacktestResult.equity_curve` の型変更。consumer 全箇所（上記）を追従。`EquityCurve` ラッパー型で access API を限定し、生 numpy indexing の散在を防ぐ。`paper_trading` は `BacktestResult` 非消費（verified）。
- スケール `k` と overflow 上界は詳細設計で具体値を固定し、`encode` の fail-closed guard で実行時にも保証する。

## 詳細設計への申し送り（Codex 概念設計レビュー Round 2 — APPROVED 時の残存指摘）

詳細設計で必ず落とすこと（Codex の承認条件）:

1. **overflow 上界の単位系確定**: `max_abs_equity_bound` を `units` / quote・home currency / 同時保有ポジション数上限 / dataset 内 max・min price から具体的に導出する。実行時 `encode` guard は最後の防壁として残す。
2. **serialized parity**: shadow test は `BacktestMetrics` の数値 equality だけでなく、summary / archive に出る **serialized value（文字列化後）** も比較対象にする（`Decimal("1.23") == Decimal("1.2300000000")` は数値 equal でも文字列表現が異なり archive diff / L1·L2 比較で差分が出るリスク）。
3. **UTC epoch 変換契約**: `bar_time` → epoch 変換は **整数 arithmetic** で行う（float 経由禁止）。入力は UTC aware / monotonic / non-null を guard。復元 API は UTC datetime として復元する契約を明記。
4. **前提の明記**: 「AF 現行設定では holding cost 0。非ゼロ化時は `encode` guard が fail-closed し T105 の追加設計が必要」を詳細設計の前提に明記。
5. **効果検証レポートの一体化**: `median/p95 RSS` / `genome/s` / `stage pass-fail 完全一致` / `archive serialized diff` を同一レポートで確認。numpy 化で retained 小オブジェクトは減るが `compute_metrics` の transient decode churn は残る点も観測する。

## スコープ外

- `MockBroker` 内部 per-bar Decimal 演算の float 化（精度 load-bearing。受け入れ条件未達なら別タスク）。
- `Trade` / `Position` の Decimal 表現変更（件数上限ありで churn 寄与小。別タスク）。
- `PriceBar` / `Ohlc` の Decimal 表現変更（src/ 36 ファイル参照の大規模波及。`devnotes/20260514-2045-ga-worker-memory/` でも明示スコープ外）。
- `compute_metrics` 出力 `BacktestMetrics` の型変更（Decimal のまま。consumer 影響を最小化）。
- `maxtasksperchild` 自体の調整（実装済み・別管理）。
- `holding_cost_per_day_bps > 0` 有効化時の equity 桁数拡大への対応（現状 fail-closed guard で検知のみ。有効化が必要になった時点で別設計）。
