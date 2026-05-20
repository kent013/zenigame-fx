# 概念設計: backtest エンジンの columnar-numpy + numba 化 (wall-time 削減)

リファレンス: `handoff.md` / `investigation-findings.md`（同ディレクトリ、profile 実測済）。
Codex 概念レビュー Round 1 (`conceptual-review-round-1.md`, CHANGES_REQUESTED) 反映済。

## 0. 本件の性質 (1 行契約)

**本件は selection pressure を一切変更しない performance-only change である。**
GA の選抜順序を 1 bit も動かさないこと（速いことではなく不変であること）が成功条件。
速度向上はその制約の中でのみ価値を持つ。

## 背景・課題

production GA Run の wall は ~6-7.6h、内訳は Stage A 7,342s / **Stage B 45,507s (83%)** /
Stage C 1,733s（Run 82 実測、単発なので一般化は保留）。根本原因は **backtest エンジンが純
Python の per-bar ループ over Decimal オブジェクト**であること。姉妹 zenigame は同じ分足でも
**numpy columnar 配列 + numba `@njit`** で <1h（exit scan-ahead JIT が源泉）。

profile 実測（Stage A 86.4k bars × 30 genome）でボトルネックを確定:

- broker 約定部 ~7.9s（`_snapshot_at` が **4 回/bar** で最大 hot / `fill_pending` /
  `mark_to_market` / `snapshot`、全て Decimal）
- engine ループ orchestration 3.94s（Python for ループ）
- equity/datetime encode ~4.0s（`equity_curve.append` + `astimezone` + session bucket）
- composite は **既に njit で 0.77s と安い**（T030/T053 対応済、対象外）

「worker を増やす」はユーザー却下済。**per-bar を速くして解く**方針。

## 重要な前提の確定 (C4: source of truth 付き)

| 前提 | 状態 | source of truth |
|---|---|---|
| signal/composite は既に float64（本件で不変） | **verified** | `entry_threshold:float`/`exit_threshold:float` (`src/dsl/genome.py:84-85`)、prepared path の mid は float64 (`src/alpha_factory/primitives/_bars_cache.py:62-90`)、composite は njit (`src/dsl/composite.py:compute_composite_at_bar_jit`) |
| **Decimal 丸め一致が必要なのは broker。ただし selection parity は broker 入力である composite/signal vector も対象** | **verified** | 約定価格/PnL/equity/margin/spread/holding cost が Decimal (`src/broker/mock.py`)。entry/exit 判定は composite(float)≥threshold(float) で既に float (`src/dsl/strategy.py:452-462`)。signal 値は変えないが、配列化（per-bar jit→一括）で値がずれないことを golden で検証する |
| trade_count に逆流するのは broker の境界判定 | **verified** | spread filter (`mock.py:192-196`)、negative-equity drop (`mock.py:218`)、margin_level<maintenance (`mock.py:333`) の 3 gate が約定数を左右 |
| backtest は RNG 不使用 | verified (handoff §8、再 grep で確認予定) | engine/strategy/eval/mock grep |
| event 適用順序 | **verified（下記 §「event ordering contract」）** | `src/backtest/engine.py:147-199` |

→ **この確定が設計を単純化する**: signal 側（float64）は触らず kernel 入力として渡すだけ。
exact 一致が必要なのは broker simulation 部のみ。

## 改善アイデア

**broker per-bar simulation を 1 つの numba `@njit` kernel に畳む（scaled-int 表現）。**

- **事前ベクトル化（prepare 段、Python/numpy）**:
  - bid/ask OHLC を **scaled-int 8 配列**に（PriceBar list → columnar、price_scale 適用）
  - composite 全 bar 配列（float64、現状 per-bar jit → 全 bar 一括計算へ。**値は不変**）
  - datetime を int 配列に: `bar_hour[]` / `is_eod[]`（次 bar と date 不一致）/ epoch（equity 用）
- **njit kernel（逐次だが C 速度、scaled-int 演算）**: §「event ordering contract」の順序で
  fill/mark/holding/margin/session/EOD/equity を実行。出力は trade records 配列 + equity 配列。
- **後処理（Python、1 回のみ）**: trade records → `Trade` / metrics / session_blocks。

これにより per-bar Python（`_snapshot_at`/`fill_pending`/`mark_to_market`/`snapshot`/
on_bar wrapper/equity encode/astimezone/session bucket）が消える。

### 数値表現の決定: scaled-int のみ（本線）
- **本番採用候補は scaled-int のみ。** 理由は speed ではなく **selection invariance**。
  float64 は約定条件・margin 判定・trade_count の境界で 1 回でもずれると feasibility 逆流で
  GA 選抜が変わる。→ **float64 は parity-study 専用の別 investigation branch 扱い**とし本線から外す。
- **単一 pip 整数では不足。複数スケールを分ける**:
  `price_scale`（価格、pip/pipette 粒度）/ `cash_scale`（cash/PnL/equity、quote 通貨 minor unit）/
  `ratio_scale`（spread_bps / margin_level / holding 日割の比率）。
- **除算は「分子分母を保持し最後に丸める」か、固定小数点スケールで丸め点を統一**する。
  単純 `//` では Decimal 一致を保証しない。対象除算: `mid=(bid+ask)/2`（0.5 pip 端数）/
  `spread_bps=(ask-bid)/mid*10000` / `margin_level=equity/margin*100` /
  `holding=notional*per_day_bps*(bar_min/1440)/10000`。
  → 各演算の `入力単位 / 中間単位 / 出力単位 / 丸めモード / 丸めタイミング / 例外時処理` を
  **詳細設計で表形式に固定**（承認条件 1）。

## event ordering contract（現行、`engine.py:147-199` から列挙）

per-bar i（fill は前 bar の submit を当 bar で約定 = entry_delay 1 相当）:

1. `session_closed = bar.hour ∈ session_close_utc_hours`
2. session_closed なら pending の open 系を drop
3. `fill_pending`: spread filter（**前 bar** close spread）→ pre_fill_equity gate
   （非有限/≤0 で open drop）→ open は ask.open/bid.open、close は bid.open/ask.open で約定
4. `mark_to_market`: last_bar 更新 + 当 bar mid から last_close_spread_bps 更新
5. holding_cost>0 なら `apply_bar_holding_cost`（cash 即時控除 + position 別累計）
6. `force_close_if_margin_call`: margin_level<maintenance_pct → close（bid.close/ask.close）
7. session_closed かつ保有あり → `close_all(reason="eod")`（close 価格）
8. snapshot → `strategy.on_bar` → signals。session_closed の open 系は drop、他は submit
9. EOD: 次 bar の date 不一致 → `close_all(reason="eod")`（close 価格）
10. equity 記録
- ループ後: 保有残あれば `close_all(last_bar, "end_of_run")`

各イベントの read/write state（cash/positions/pending/last_bar/spread_bps/holding累計）と、
**同一 bar で margin call と session/EOD が競合する場合の優先順位**を詳細設計で明文化（承認条件 2）。

## コーナーケース一覧（詳細設計で期待動作を確定 = 承認条件 3）

`same-bar fill+stop` / `negative equity intrabar` / `session close と signal が同一 bar` /
`spread filter hit` / `pending order then forced close` / `short の holding_cost` /
`margin call と session/EOD の同一 bar 競合` / `mid<=0 防御` / `端数決済（end_of_run）`。

## 期待効果

- **Stage B 支配の run で wall 大幅短縮**を狙う（zenigame で <1h 実績はあるが、本 repo での
  倍率は外挿せず）。正式 KPI は **A/B/C 各 stage の median wall reduction（複数 run 測定）**。
- live_criteria 達成への貢献: wall 短縮で同一計算予算での探索試行回数が増える = 探索効率向上。
  評価の中身（期間・閾値・取引回数）は一切不変（performance-only）。

## 非機能要件（明文化）

- trade_count を減らして速くする設計は採らない。
- session/EOD 強制クローズ・long+short 両方向・スワップ/スプレッド反映を完全維持。
- 主契約は「public signature 維持」ではなく **observable behavior contract 維持**
  （同一入力に対し trade log / equity curve / constraint flags が bit 一致）。

## 検証戦略（golden parity、比較粒度拡張 = 承認条件 5）

best individual 一致だけでは tie-break 変化を見逃す。以下を golden 比較:

- 全 genome の主要メトリクス / trade log（entry/exit idx・price・pnl・reason）/ equity curve /
  constraint flags（feasibility・pass/fail vector）/ selection input tensor
- **上流 signal も比較**: per-bar composite value / entry・exit boolean / submitted order intent
  （signal 差分が偶然 selection に出なかったケースを見逃さないため）
- seed=9999 smoke で best=g2_i2 / fitness_pen=-0.02894014223533147 / stage_c=False、
  各 gen の A/B pass count・pass/fail vector 一致。

## overflow 上界（詳細設計で worst-case 計算 = 承認条件 4）

price 自体より cross-multiplication が危険: `notional=units*price_scale` /
`equity*ratio_scale` / `bps*notional` / `cumulative equity/PnL`。最大価格・最大ロット・
最大バー数・最大保有期間・最大累積 PnL から int64 上界を先に計算。debug build で overflow
sentinel を入れ reference 実行と比較。

## 実装方針（概要）

1. **columnar scaled-int bar 表現の新設**（`src/backtest/` 新モジュール）。先例: T030
   `_bars_cache` / T107 aux_pair columnar 化。
2. **njit simulation kernel 新設**: 入力 columnar(scaled-int) + composite(float64) + scalar
   params、出力 trade/equity 配列。zenigame `_exit_jit.py` を方式参考（コード共有なし）。
3. **engine.run_backtest 差し替え**: observable behavior contract 維持、内部を kernel +
   後処理に置換。stage_gate caller は無改修を目指す。
4. **段階移植**: kernel と golden 一致確立 → engine 差し替え → broker per-bar API を吸収。
5. 初回スコープを **single pair / fixed config / single-thread reference parity** に絞る。

## 制約・前提

- **GA 結果完全不変（絶対）**: §検証戦略の golden 全項目一致。崩れたら reject。
- **金額計算の正確性**: scaled-int で PnL/drawdown/Sharpe を現行 Decimal と exact 一致。
- backtest は RNG 不使用（再確認予定）。
- 環境: numba 0.65.1 / numpy / Python 3.11 / 64GB RAM / 12 core / macOS。
  メモリは T106/T107 で解決済。本件は speed 目的。
- composite/primitive（T030/T053）は対象外。

## スコープ外

- worker 数変更 / 評価期間延長 / 閾値緩和 / 取引回数削減。
- primitive / composite 再実装（既に numpy/numba）。
- Stage B IS-monitor skip（feasibility 逆流でブロック済）。
- live feed / paper trading の unprepared path の numba 化。
- **float64 表現**（parity-study の別 branch 扱い、本線から分離）。
- **stateful な strategy callback**: 対象戦略を「columnar input から scalar signal を返す
  pure function 群」に限定。
