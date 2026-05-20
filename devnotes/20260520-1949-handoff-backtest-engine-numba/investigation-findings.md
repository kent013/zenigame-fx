# 調査結果: backtest エンジン numba 化 (handoff §7 step 1-2)

作成 2026-05-20 (JST)。handoff.md の「調査先行」フェーズの実測ログ。
結論先取り: **per-bar の path 依存シミュレーション全体を 1 つの numba njit kernel に畳む**のが本筋。
strategy 側 composite は既に JIT 済 (T053) なので、残コストは **broker (約定/equity/margin) + engine ループ + equity-curve encode + datetime 変換**。

---

## 1. 移植元 zenigame の方式 (verified, 精読済)

`src/trading/alpha_factory/evaluation/_backtest_stock.py::run_single_stock` +
`src/trading/backtest/_exit_jit.py`。

- **columnar SoA**: `DayMinuteBars` が `high_array/low_array/close_array/open_array/volume_array`
  を numpy で保持。`_suffix_max_high = np.maximum.accumulate(...)` 等を事前ベクトル化。
- **核心は「exit scan-ahead JIT」**: position entry 直後に `compute_jit_exit` →
  `jit_scan_exit` (`@njit(cache=True)`) が **entry_idx+1 〜 末尾を 1 回の njit 呼び出しで走査**し
  exit bar を確定。保有中の per-bar Python exit チェック (check_exit/should_exit) を消す。
- entry 判定は Python (composite cache 参照 + candidate index 事前計算)。約定/コストは Python。
- → 「保有期間の per-bar Python ループ」を JIT 一括スキャンで消すのが速度の源泉。

注: zenigame は **株 universe / 単方向 long / 出来高 VPR/fill**。zenigame-fx は
**単一 FX ペア / long+short 両建可 / margin call / holding cost / session+EOD 強制クローズ /
spread filter**。event-driven 度が高くロジックは別物。**方式 (columnar+njit) のみ参考**。

---

## 2. 移植先 zenigame-fx の hot path (profile 実測)

`devnotes/20260520-1949-handoff-backtest-engine-numba/profile_run_backtest.py`。
Stage A real bars (EUR_JPY, 86,400 bars) × 30 genome、JIT warmup 2 本捨て。

- **クリーン wall: 5.5µs/bar (473ms/backtest)**。production Stage B が 60µs/bar なのは
  prepare×9 + 242k full IS-monitor の構造差 (handoff §1-1)。per-bar engine コスト自体は同じ経路。
- cProfile (instrumented, tottime 上位、相対比のみ意味あり):

| 関数 | tottime | cum | calls | 備考 |
|---|---|---|---|---|
| `run_backtest` (loop 本体) | 3.94s | 32.9 | 30 | engine orchestration (Python for ループ) |
| `MockBroker._snapshot_at` | 3.57s | 6.02 | **10.4M (≈4/bar)** | unrealized sum + equity + margin (Decimal) ← 最大 hot |
| `DslStrategy.on_bar` | 2.99s | 4.0 | 2.59M | composite jit は 0.77s のみ、残は Python wrapper |
| `_bars_cache._compute` | 2.0s | — | 28 | prepare 時の primitive 事前計算 (T030 済) |
| `fill_pending` | 1.82s | 7.77 | 2.59M | pre_fill_equity snapshot + open/close |
| `mark_to_market` | 1.68s | — | 2.59M | mid/spread を毎 bar Decimal 生成 |
| `equity_curve.append` | 1.30s | 3.49 | 2.59M | encode_epoch_ns(astimezone) + encode_equity |
| `aggregate_session_blocks` | 0.90s | 1.97 | 30 | 末尾 1 回、全 bar+trade を Python 走査 |
| `snapshot` / `sum`(Decimal) | 0.86/0.83 | — | 5.2M/5.4M | |
| `astimezone` | 0.795s | — | 4.8M | datetime→epoch_ns tz 変換 |
| `compute_composite_at_bar_jit` | 0.767s | — | 2.59M | **既に njit、安い** |

### 解釈 (Fact/Interpretation 分離)
- **Fact**: broker 4 関数 (`_snapshot_at`/`fill_pending`/`mark_to_market`/`snapshot`) で
  tottime ~7.9s。engine ループ 3.94s。equity encode 系 ~2.9s。datetime 系 ~1.1s。
  composite は既に njit で 0.77s。
- **Interpretation**: ボトルネックは handoff の診断通り **broker の約定シミュレーション部 +
  engine ループ + equity/datetime encode**。primitive/composite は触る必要なし。

---

## 3. 設計方向 (要 Codex 合議)

per-bar の path 依存シミュレーション (fill / mark / holding / margin / session / EOD / equity)
を **1 つの njit kernel** に畳む。

- **入力 (columnar, prepare で構築)**:
  - bid/ask OHLC 8 配列 (open/high/low/close × bid/ask)
  - composite 全 bar 配列 (現状は per-bar jit 呼び出し → kernel 投入前に全 bar 一括計算へ)
  - bar の hour 配列 / date-change boundary flag 配列 / epoch 配列 (datetime を事前 int 化)
  - スカラ: entry/exit_threshold, time_stop_min, units, leverage, margin_rate,
    initial_cash, max_spread_bps, holding_cost_per_day_bps, session_close hours, maintenance_pct
- **出力**: trade records (entry/exit idx, side, units, entry/exit price, pnl, reason, ...) +
  equity 配列。Python 側で 1 回だけ Trade オブジェクト / metrics / session_blocks に後処理。
- **消える per-bar Python**: _snapshot_at, fill_pending, mark_to_market, snapshot, on_bar wrapper,
  equity encode, astimezone, session bucket。

### 最大の設計判断 (handoff §6 / 絶対制約 §5)
**数値表現: scaled-int (pip 整数, exact, GA bit-identical 維持) vs float64 (numba 最速だが丸め)**。
- 正確性最優先 (ユーザー明言) + feasibility 逆流 (trade_count→selection) → scaled-int 寄り。
- ただし numba は float64 が最速。njit 内で path 依存約定/equity を int64 で書けるか
  (overflow / 除算丸めの扱い) が要検証。
- → `/zenigame-fx-alpha-design` 概念設計 → Codex(gpt-5.4) → 詳細設計 → Codex(gpt-5.3-codex) で詰める。

### 検証戦略 (不変)
golden: seed=9999 smoke で best=g2_i2 / fitness=-0.02894014223533147、各 gen の A/B pass
vector 一致。+ smoke wall before/after。+ 既存テスト全 pass (pre-existing 失敗 3 件は除外)。

---

## 4. 環境メモ
- numba 0.65.1 / numpy / Python 3.11 / 64GB RAM / 12 core / macOS。DB `zenigame-fx-db-1` healthy。
- profile script: `profile_run_backtest.py` (本ディレクトリ、devnote 内なので scripts/ 未移動)。
