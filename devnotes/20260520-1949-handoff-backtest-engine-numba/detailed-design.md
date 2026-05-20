# 詳細設計: backtest エンジンの columnar-numpy + numba 化 (wall-time 削減)

概念設計: `conceptual-design.md`（Codex Round 2 APPROVED）。リファレンス: `handoff.md` /
`investigation-findings.md`。

## 使命・制約（絶対遵守）

### 使命
live_criteria 全指標同時充足 + (ii-lite) 通過。絶対制約: イントラデイ / long+short 両方向 /
スワップ・スプレッド反映。

### 本件の 1 行契約
**selection pressure を 1 bit も動かさない performance-only change。** 速度はこの制約下でのみ価値を持つ。

### 禁止事項（本件で特に関係）
評価期間延長 / 見た目数値改善 / GA ハック / live_criteria 緩和 / 過度な複雑化 /
取引回数削減 / オーバーナイト保有前提。本件は計算結果を変えないので全て非該当。

### コーディングルール
- 全施策にテスト必須（テストファースト、振る舞い説明的な命名、対象モジュール対応ファイル）。
- `uv run pytest tests/` / `uv run ruff check src/ tests/` / `uv run mypy src/` 通過。
- pre-existing 失敗 3 件（`test_v31_selection_key_includes_stage_b_priority` / `archive.py:350` mypy /
  `run_ga.py:196` E501）は本件と無関係、触らない。

---

## 1. 設計の核心と source-of-truth 確定 (C4)

### 1-1. 観察事実 (Fact, file:line で verified)
- **F1**: signal/composite は既に float64。`entry_threshold:float`/`exit_threshold:float`
  (`src/dsl/genome.py:84-85`)、prepared mid は float64 (`_bars_cache.py:62-90`)、composite は
  njit (`compute_composite_at_bar_jit`)。→ 本件で signal 値は不変、kernel 入力として渡すだけ。
- **F2**: Decimal が使われるのは broker の約定価格/PnL/equity/margin/spread/holding cost
  (`src/broker/mock.py`)。
- **F3**: equity は既に scaled-int64 (SCALE=8) で lossless 保存。**AF default
  (holding_cost=0) では equity 計算に除算が無い**（`equity_curve.py:68-88` の SCALE 契約）。
  equity = cash + unrealized、両者 `Decimal(units:int) * price_diff`（price ≤5 桁）。
- **F4 (config 確定)**: `max_spread_bps="10"` → **spread filter ACTIVE**、
  `holding_cost_per_day_bps="0"` → holding cost 無効、`leverage=3` / `units=10000` /
  `initial_cash="1000000"` / maintenance=100 (`mock.py:95` default)
  (`config/alpha_factory/default.yaml:25-41`)。
- **F5**: DslStrategy は無保有時のみ entry（ドテン禁止、`strategy.py:438-462`）→
  **同時保有ポジションは最大 1**（force close 時も close 後に flat）。

### 1-2. 解釈 (Interpretation)
- F5 により margin_used = 単一 position の entry_margin。F3+F4 により equity/PnL/cash は除算なし。
- → **trade_count に逆流し得る除算は 2 gate のみ**: spread filter（spread_bps）と
  margin call（margin_level）。両者は exact 整数 cross-multiply に還元でき（§2-2）、丸め不要。
- → 「Decimal を numba で再現」する必要はなく、**整数 cross-multiply で exact**にできる。

---

## 2. 数値表現と丸め契約（承認条件 1）

### 2-1. スケール定義
| スケール | 用途 | 値 | SoT |
|---|---|---|---|
| `PRICE_SCALE` | bid/ask OHLC、entry/exit price | 10^5（quote 桁 ≤5、JPY は ≤3 だが 10^5 で吸収） | OANDA display_precision (`mock.py:62-86`) |
| `CASH_SCALE` | cash / equity / pnl / unrealized | 10^8（既存 `SCALE_DECIMAL_PLACES`） | `equity_curve.py:77` |
| ratio | spread_bps / margin_level | **保持しない**（§2-2 で cross-multiply、商を作らない） | — |

- price は scaled-int64（例 EUR_JPY 162.345 → 16234500）。units は int。
- pnl = units × (exit_scaled − entry_scaled) は PRICE_SCALE 単位の整数。CASH_SCALE へは
  **×(CASH_SCALE/PRICE_SCALE)=×10^3**（`SCALE_RATIO=1000`）で lossless 変換（price≤5桁前提、
  §5 で overflow 検証）。
- equity_scaled (CASH_SCALE) は既存 `encode_equity` と bit 一致（後処理で EquityCurve 構築）。
- **スケール混在の禁止**: 比較・加減算は必ず同一スケールに揃える。price(1e5) と
  cash/equity(1e8) を直接比較しない（Round 1 [Critical 1] の修正）。

### 2-2. 除算の exact 化（単純 // 禁止 → cross-multiply、スケール整合済）
現行 Decimal 演算と「比較結果」が一致すればよい gate は、商を作らず整数 cross-multiply する。
**全項のスケール次元を明示し一致させる**（Round 1 [Critical 1] 反映）:

| 演算 | 現行 Decimal (`mock.py`) | kernel（exact 整数比較、スケール整合） |
|---|---|---|
| margin call | `margin_level=equity/margin_used*100 < maint`; margin_used=`notional/leverage`(margin.py:24, quantize 無し) | `equity_scaled*100*leverage*maint_den  <  maint_num*units*entry_price_scaled*SCALE_RATIO`（左辺: 1e8 次元、右辺: units×1e5×1e3=1e8 次元 → **両辺 1e8 で整合**） |
| spread filter | `spread_bps=(ask.c−bid.c)/mid*10000 > max`; mid=`(ask.c+bid.c)/2` | `(ask.c−bid.c)*20000*max_den  >  max_num*(ask.c+bid.c)`（両辺とも price 1e5 次元、係数のみ） |
| mid<=0 防御 | `if mid_close>0` (L280) | `(ask.c+bid.c) > 0` |

導出（margin, maint=100/leverage=3 default）: `equity/(notional/lev)*100 < maint` ⟺
（margin_used>0）`equity*lev*100 < maint*notional`。実 quantity を scaled に置換
（equity_real=equity_scaled/1e8, notional_real=units*entry_price_scaled/1e5）し両辺 ×1e8:
`equity_scaled*lev*100 < maint*units*entry_price_scaled*(1e8/1e5)` = `…*SCALE_RATIO`。

- **不変性の論拠（gap 論拠より強い finite-granularity 証明）**:
  - 価格は ≤5 桁（JPY ≤3）の有限小数 → entry/exit/equity/cash/unrealized/notional は全て
    **1e-5 の整数倍**（pnl=units×price_diff、units は int）。equity は実際 ≤5 桁。
  - margin call (maint=100, leverage=3): 比較は exact rational で `equity*3 < notional` ⟺
    `equity < notional/3`。Decimal 経路は二段: ① `required_margin=round28(notional/3)` ②
    `margin_level=round28(equity/required_margin*100)` を `<100` 判定（実質 `equity<required_margin`）。
    notional は scaled-int `p` で `notional=units*p/PRICE_SCALE`（units=10000, price≤5桁）。
    `notional/3` が **3 で割り切れる（終端）場合は Decimal も exact** で両経路一致。**非終端の場合**、
    `notional/3` は循環小数で、有限小数である `equity`（cash+unrealized も units×price_diff 由来で
    1e-5 の整数倍、units=10000 default では実際 0.1 刻みのさらに粗い grid）とは**厳密一致し得ない**。
    かつ equity grid 間隔（≥1e-5）は Decimal 二段丸め幅（~notional×10^-28 ≈ 3e-22）より 16 桁以上
    大きいので、equity が `notional/3` と `round28(notional/3)` の間（幅 3e-22）に落ちることも無い。
    → divergence 集合は**空**。**∴ bit-identical**。
  - spread filter (max=10): exact `spread_bps=(ask−bid)*20000/(ask+bid)`。閾値 10 と一致するのは
    `(ask−bid)*2000=(ask+bid)` の時のみで、その時 `(ask−bid)/mid=0.001` が終端し Decimal も exact。
    非一致時の gap ≥ 1/(ask+bid) ~ 1.6e-8 >> 丸め 10^-24 → 反転なし。**∴ bit-identical**。
- **非 default の安全弁**: maintenance≠100 / max_spread が非整数 Decimal の場合は num/den 分解で
  cross-multiply するが、上記終端性証明が崩れ得るため **§5 preflight で「default 係数か」を判定し、
  非 default は現行 Decimal 経路へフォールバック**（kernel は production scope 専用）。
- 最終的に §7 golden が全 production データで bit-identity を実証する（最終 arbiter）。

### 2-3. holding cost（default 無効、但し設計に残す）
`holding_cost_per_day_bps>0` 時は除算経路（日割 bps）が生き equity 桁数前提が崩れ得る。
本 kernel は **default scope（holding_cost=0）を対象**とし、`holding_cost_per_day_bps>0` の
config では **kernel を使わず現行 Decimal engine にフォールバック**する（fail-safe 分岐、
`run_backtest` 冒頭で判定）。これにより holding cost の Decimal 日割丸めを再現する責務を負わない。

---

## 3. event ordering contract（承認条件 2、`engine.py:147-199` から read/write 明示）

per-bar i。state: `cash`(CASH_SCALE int) / `pos`(0 or 1 件: side/units/entry_scaled/entry_margin_num)
/ `pending`(next-bar 約定予定 signal) / `last_close_spread_num,den`(前 bar)。

| step | 処理 | read | write |
|---|---|---|---|
| 0 | `session_closed = hour[i] ∈ session_hours` | hour[i] | — |
| 1 | session_closed なら pending open を drop | pending | pending |
| 2 | spread filter: `last_close_spread`>max なら pending open drop（前 bar 値） | pending,last_spread | pending |
| 3 | **pre-fill** equity gate: `equity_pre = cash + unrealized(close価格)`（fill 前、`mock.py:213` の `_snapshot_at(bar).equity` に対応）。`<=0` で pending open drop（+counter） | cash,pos,bid/ask close[i] | pending,drop_cnt |
| 4 | fill: open→ask.o[i]/bid.o[i]、close→bid.o[i]/ask.o[i] で約定 | pending,bid/ask[i] | pos,cash,trades |
| 5 | mark_to_market: 当 bar mid から `last_close_spread` 更新 | bid/ask close[i] | last_spread |
| 6 | margin call: **fill 後** に `equity_post = cash + unrealized(close価格)` を再計算し、`equity_post_scaled*100*lev*maint_den < maint_num*units*entry*SCALE_RATIO`(§2-2) なら close（bid/ask close[i]） | pos,cash,bid/ask close[i] | pos,cash,trades |
| 7 | session_closed かつ保有 → close（close 価格、reason=eod） | pos,bid/ask close[i] | pos,cash,trades |
| 8 | snapshot→composite[i] で entry/exit 判定→signals。session_closed の open は drop、他は submit（pending へ） | pos,composite[i],thresholds | pending |
| 9 | EOD: `is_eod[i]`（次 bar date 不一致）かつ保有 → close（close 価格） | pos,bid/ask close[i] | pos,cash,trades |
| 10 | equity 記録（curve buffer へ） | cash,pos,bid/ask close[i] | equity_buf[i] |
| post | ループ後保有残 → close(last bar, end_of_run) | pos | cash,trades |

### 同一 bar 競合の優先順位（現行コード順 = 不変）
margin call(6) → session close(7) → EOD(9)。step 6 で close すると pos=0 になり 7/9 は no-op。
**この順序を kernel でも厳守**（concept §承認条件2）。entry は step 8 で pending 化され step 4
で**次 bar**約定（entry_delay=1 相当、現行と同一）。

### pre-fill / post-fill equity の 2 回計算（Round 1 [Critical 2] 反映）
現行は `fill_pending` 冒頭で `pre_fill_equity = _snapshot_at(bar).equity`（fill **前**）を gate に
使い（`mock.py:213`）、`force_close_if_margin_call` は `_snapshot_at(bar)`（fill **後**、cache は
fill で invalidate 済）を使う（`mock.py:330`）。kernel も **step3=pre-fill / step6=post-fill** で
equity を別々に計算する。両者とも `cash + unrealized(close 価格基準)`（`_unrealized` は
exit_kind="close"、`mock.py:483-486`）。

### pending signal の単一性不変条件（Round 1 [Warning 4] 反映）
`DslStrategy.on_bar` は 0 または 1 件の signal しか返さない（`strategy.py:438-463`、entry/exit/
session/time_stop の各分岐が単一要素 list か空 list を return、ドテン禁止）。kernel は
`pending` を単一 slot で表現するが、**run_backtest が kernel 呼び出し前に
`assert all(len(on_bar 相当)<=1)` 契約を満たすことを前提**とする。将来 strategy が複数 signal を
返す設計に変わる場合は kernel scope 外（フォールバック）とし、`run_backtest` で
unprepared/multi-signal を検出したらフォールバックする。本 kernel の対象は現行 DslStrategy のみ。

---

## 4. 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | columnar scaled-int bar 表現 + prepare 変換 | `src/backtest/columnar.py`(新) | 高 |
| 2 | njit simulation kernel（broker sim を畳む） | `src/backtest/_sim_kernel.py`(新) | 高 |
| 3 | `run_backtest` 差し替え（kernel 呼び出し + 後処理） | `src/backtest/engine.py` | 高 |
| 4 | golden parity 検証ハーネス + テスト | `tests/backtest/test_sim_kernel_parity.py`(新) | 高 |
| 5 | holding_cost>0 / unprepared フォールバック分岐 | `src/backtest/engine.py` | 中 |

---

## 施策 1: columnar scaled-int bar 表現 + prepare 変換

### 変更箇所
- 新規 `src/backtest/columnar.py`: `ColumnarBars` dataclass（frozen）+ `bars_to_columnar(bars)`。

### 設計
```python
@dataclass(frozen=True)
class ColumnarBars:
    # 全て read-only numpy。長さ n_bars。
    bid_o: np.ndarray; bid_h: np.ndarray; bid_l: np.ndarray; bid_c: np.ndarray  # int64 (PRICE_SCALE)
    ask_o: np.ndarray; ask_h: np.ndarray; ask_l: np.ndarray; ask_c: np.ndarray  # int64
    hour: np.ndarray            # int8  bar_time.hour (UTC)
    is_eod: np.ndarray          # bool  次 bar と date 不一致（末尾 True）
    epoch_ns: np.ndarray        # int64 equity curve 用（encode_epoch_ns を一括）

def bars_to_columnar(bars: list[PriceBar]) -> ColumnarBars:
    # Decimal→scaled-int は exact (× PRICE_SCALE 後 int 化、端数は fail-closed)。
    # hour/is_eod/epoch_ns を 1 パスで構築（per-bar astimezone を排除）。
```
- price scaled 化は `encode_equity` 同様 fail-closed（`scaled != int(scaled)` で raise）。
- `is_eod[i] = (i==n-1) or bars[i+1].bar_time.date() != bars[i].bar_time.date()`（現行 L189-190 と同義）。

### 波及変更
- `AGENTS.md`: なし（内部実装）。`.claude/skills/*`: なし。`config`: なし。`docs`: 後述 runbook に 1 行追記検討。

### ルックアヘッドバイアスチェック
- [x] 未来バー参照なし（is_eod は i+1 の date のみ、現行と同一の境界判定）
- [x] 当日確定値先取りなし（spread filter は前 bar、現行同一）

### パフォーマンスチェック
- [x] 変換は backtest 開始時 1 回 O(n)。内側ループで numpy 関数を呼ばない。
- [x] SoA。Stage B で fold ごとに bars が異なるため変換も fold ごと（現行 prepare と同頻度）。

### テスト計画
- `test_bars_to_columnar_roundtrip`: scaled-int → Decimal 復元が元 PriceBar と exact 一致。
- `test_bars_to_columnar_is_eod_boundary`: date 跨ぎ・末尾で is_eod が正しい。
- `test_bars_to_columnar_fractional_price_fail_closed`: PRICE_SCALE 超過桁で raise。

### リスク
- PRICE_SCALE=10^5 が全 pair で十分か（JPY=3桁/非JPY=5桁）。pip catalog で検証（テストで担保）。

---

## 施策 2: njit simulation kernel

### 変更箇所
- 新規 `src/backtest/_sim_kernel.py`: `@njit(cache=True)` の `simulate(...)`。
  zenigame `_exit_jit.py` の「columnar + njit(cache=True) + fallback decorator」**方式のみ**参考
  （コード共有なし、AGENTS.md 遵守）。

### 設計（pseudocode、§3 の順序を厳守）
```python
@njit(cache=True)
def simulate(
    bid_o, bid_h, bid_l, bid_c, ask_o, ask_h, ask_l, ask_c,  # int64 PRICE_SCALE
    hour, is_eod,                                            # int8, bool
    composite,                                               # float64 [n] (signal、不変)
    entry_threshold, exit_threshold, time_stop_min,          # float, float, int
    units, leverage, maint_num, maint_den,                   # int, int, int, int
    max_spread_num, max_spread_den,                          # int, int (=10,1 default)
    initial_cash_scaled,                                     # int64 CASH_SCALE
    session_hours_mask,                                      # bool[24]
    bar_minutes,                                             # int (epoch 差分 or time_stop 用)
    epoch_ns,                                                # int64[n] time_stop 経過判定
    # out 配列（呼び出し側で事前確保）
    out_entry_idx, out_exit_idx, out_side, out_entry_px, out_exit_px, out_pnl, out_reason,
    out_equity_scaled,                                       # int64[n]
):
    cash = initial_cash_scaled   # CASH_SCALE
    has_pos = False; pos_side = 0; pos_entry = 0; pos_entry_epoch = 0
    pending_kind = 0  # 0 none /1 open_long /2 open_short /3 close
    last_spread_num = -1; last_spread_den = 1   # 前 bar、初回未設定
    n_trades = 0
    for i in range(n):
        session_closed = session_hours_mask[hour[i]]
        # step1-2: pending open drop
        if session_closed and pending_kind in (1,2): pending_kind = 0
        if pending_kind in (1,2) and last_spread_den>0:
            # spread_bps=(ask−bid)*20000/(ask+bid) > max_num/max_den（§2-2、20000 係数を保持）
            if last_spread_num*20000*max_spread_den > max_spread_num*last_spread_den:
                pending_kind = 0
        # step3: pre-fill equity gate（fill 前、単一 pos、除算なし）
        equity_pre = cash + _unrealized(has_pos, pos_side, units, pos_entry, bid_c[i], ask_c[i])
        if pending_kind in (1,2) and equity_pre <= 0: pending_kind = 0; drop_cnt+=1
        # step4: fill（次 bar 約定の実体）
        if pending_kind==1 and not has_pos: open long @ ask_o[i] ...
        elif pending_kind==2 and not has_pos: open short @ bid_o[i] ...
        elif pending_kind==3 and has_pos: close @ exit_price; record trade
        pending_kind = 0
        # step5: spread 更新（当 bar close）
        s = ask_c[i]+bid_c[i]
        if s>0: last_spread_num=(ask_c[i]-bid_c[i]); last_spread_den=s  # bps 比は §2-2 で展開
        # step6: margin call（fill 後 equity 再計算、exact 整数 cross-multiply、§2-2 スケール整合）
        equity_post = cash + _unrealized(has_pos, pos_side, units, pos_entry, bid_c[i], ask_c[i])
        if has_pos and equity_post*100*leverage*maint_den < maint_num*units*pos_entry*SCALE_RATIO:
            close @ close px; reason=margin
        # step7: session close
        if session_closed and has_pos: close @ close px; reason=eod
        # step8: strategy（composite は float、現行と同一比較）
        if has_pos: exit 判定（time_stop: epoch 差 / hysteresis: composite<exit_threshold）→ pending_kind=3
        else: entry 判定（composite>=entry_threshold→open_long pending 等）; session_closed open は drop
        # step9: EOD
        if is_eod[i] and has_pos: close @ close px; reason=eod
        # step10: equity 記録
        out_equity_scaled[i] = cash + _unrealized(...)   # CASH_SCALE
    # post: 端数決済
    if has_pos: close @ last close; reason=end_of_run
    return n_trades, drop_cnt
```
- `_unrealized` / pnl: `units*(exit_scaled - entry_scaled)`（long）/ 符号反転（short）、PRICE_SCALE
  単位 → ×10^3 で CASH_SCALE。**除算なし**。
- spread filter の cross-multiply は last_spread を `(num,den)` で保持し step2 で
  `num*20000*max_den > max_num*den*?` の形に展開（§2-2 の `(ask−bid)*20000 > max*(ask+bid)`）。
  実装では bps 比較を「前 bar の (ask_c−bid_c) と (ask_c+bid_c)」で持ち越す。
- exit_price 規則: open exit=bid.o(long)/ask.o(short)、close exit=bid.c(long)/ask.c(short)
  （`mock.py:471-475` と同一）。

### 波及変更
- `AGENTS.md`: §に「backtest kernel (numba) 概要 + holding_cost>0 はフォールバック」を 1 段落追記。
- `docs/alpha_factory/runbook.md`: backtest 高速化の注記（任意）。config/skill: なし。

### ルックアヘッドバイアスチェック
- [x] spread filter は前 bar 値持ち越し（step5 で当 bar 更新、step2 で前 bar 使用 = 現行同一）
- [x] fill は前 bar submit の当 bar 約定（entry_delay=1、未来参照なし）
- [x] composite[i] は当 bar 確定値（signal 不変）

### パフォーマンスチェック
- [x] kernel は単一 njit ループ、内部で Python/numpy 呼び出しなし。`cache=True` で JIT 再利用。
- [x] out 配列は呼び出し側で事前確保（churn なし）。

### テスト計画（テストファースト）
- `test_sim_kernel_margin_call_integer_equivalence`: margin call 境界で cross-multiply が
  Decimal `margin_level<maint` と一致（境界値・直前直後）。
- `test_sim_kernel_spread_filter_integer_equivalence`: spread filter 境界で一致。
- `test_sim_kernel_long_short_pnl`: long/short の pnl が `_realized_pnl`（`mock.py:478-481`）と exact 一致。
- `test_sim_kernel_event_ordering_margin_then_session`: 同一 bar 競合で margin→session→eod 順。
- corner cases（§6）各 1 テスト。

### リスク
- numba njit の type 安定性（int64 overflow）→ §5 で上界検証 + debug sentinel。

---

## 施策 3: run_backtest 差し替え

### 変更箇所
- `src/backtest/engine.py:95` `run_backtest`。observable behavior contract 維持
  （戻り値 `BacktestResult`: trades / equity_curve / session_blocks 不変）。

### 設計
1. 冒頭の intraday 制約検証（L114-122）は維持。
2. `holding_cost>0` または `prepare 不可`（unprepared path）なら**現行 Decimal 経路にフォールバック**
   （施策 5）。
3. それ以外: `strategy.prepare(bars)` で composite 配列取得 → `bars_to_columnar(bars)` →
   `simulate(...)` → out 配列を Python で後処理:
   - trade records → `list[Trade]`（Decimal は scaled-int から exact 復元）
   - `out_equity_scaled` → `EquityCurve`（`encode_equity` と bit 一致を検証）
   - `aggregate_session_blocks(bars_list, trades, mode="test")` は現行のまま（後処理 1 回）。
4. `backtest.finished` log の各 counter（drop 系）は kernel 出力から組み立て。

### composite 配列の取得（Round 1 [Warning 5] 反映: v1 は per-index 同一 njit 呼びのみ）
- **v1 では bulk 再定式化をしない**。kernel 投入前に、現行と**同一の** `compute_composite_at_bar_jit`
  を全 idx でループ呼びして composite 配列を作る（prepared flat 配列を入力に、`fastmath=False` /
  `parallel=False` 固定）。同一関数・同一入力・同一順序のため float bit 一致が構造的に保証される。
- bulk ベクトル化（一括 kernel 化）は golden 合格**後**の段階最適化に回す（本 TODO scope 外）。
- signal parity（per-bar composite / entry・exit boolean / order intent）を golden で実証。

### 波及変更
- `AGENTS.md`: 施策 2 と共通の追記。`stage_gate.py` caller: 無改修（signature 不変）。

### テスト計画
- `test_run_backtest_result_parity_*`: 既存 engine テストが全 pass（観測挙動不変）。
- golden（施策 4）。

### リスク
- composite 一括化が per-bar 呼びと float bit 一致しないと selection が動く → golden で必ず検証。

---

## 施策 4: golden parity 検証ハーネス（承認条件 5）

### 内容
- `tests/backtest/test_sim_kernel_parity.py` + `devnotes/.../golden_parity.py`（手動大規模実行用）。
- real Stage A/B bars × 多数 random genome（seed 固定）で、**現行 Decimal engine** と
  **kernel engine** を両方走らせ、以下を bit 比較:
  - trades: entry/exit idx・price・pnl・reason・holding_cost・spread_cost
  - equity curve: epoch_ns + equity_scaled 配列が完全一致
  - per-bar composite value / entry・exit boolean / submitted order intent（signal parity）
  - constraint flags（feasibility / pass/fail vector）
- smoke E2E: `--population-size 24 --generations 5 --seed 9999 --no-report` で
  **best=g2_i2 / fitness_pen=-0.02894014223533147 / stage_c=False**、各 gen の A/B pass count・
  pass/fail vector 一致。

### リスク
- divergence 発見時: §2-2 の cross-multiply が Decimal と稀に不一致 → 該当演算のみ Decimal 丸め
  再現にフォールバック。**golden が最終 arbiter**。

---

## 施策 5: holding_cost>0 / unprepared フォールバック

### 内容
- `run_backtest` 冒頭で `config.holding_cost_per_day_bps>0` または strategy が prepare 非対応なら
  現行 Decimal ループを使う（kernel は default scope 専用）。
- これにより holding cost の Decimal 日割丸め・live feed path を kernel で再現する責務を負わない。

### テスト計画
- `test_run_backtest_holding_cost_uses_decimal_path`: holding_cost>0 で kernel を bypass。

---

## 5. overflow 上界計算（承認条件 4、Round 1 [Critical 1]/[Warning 6] スケール整合後で再計算）

int64 上限 = `INT64_MAX = 2^63−1` ≈ **9.22e18**。**典型値**（AF default、JPY pair price ~300）の
per-operation 上界:
- `price_scaled` = 300×10^5 = 3e7。`units`=1e4。実 equity は initial ~1e6 オーダー → `equity_scaled` ~1e14。
- **margin call**（§2-2）: 左辺 `equity_scaled*100*lev*maint_den` ~ 1e14×100×3×1 = 3e16、
  右辺 `maint_num*units*entry_price_scaled*SCALE_RATIO` ~ 100×1e4×3e7×1e3 = 3e16。両辺 < 9.22e18。
- **spread filter**: 左辺 ~1e5×2e4×1 = 2e9、右辺 ~10×6e7 = 6e8。余裕大。
- **unrealized**: units×price_diff_scaled×SCALE_RATIO ~ 1e4×3e7×1e3 = 3e14 < int64。

ただし利益累積で equity は initial に bounded されない（Round 2 [W]）。**静的な保守上界
（`initial + n_bars×units×price振れ×SCALE_RATIO` ~ 2.4e17）を hard fallback gate にすると、
`2.4e17×100×3 = 7.2e19 > int64` となり典型 smoke でも fallback してしまい本末転倒**（Round 3 [W]）。
→ 静的上界は**安全側の hard gate にしない**。代わりに:

### overflow 対策: kernel 内 runtime sentinel + caller の Decimal 再実行（Round 3 反映）
- kernel は margin 乗算の**直前**に sentinel 判定:
  `abs(equity_post_scaled) > INT64_MAX // (100*leverage*maint_den)` なら以降の乗算を行わず
  **overflow status を返して即 return**（trade は途中まで、status flag を立てる）。
- `run_backtest`（caller）は kernel の overflow status を検知したら、その backtest だけ
  **現行 Decimal engine で再実行**（observable behavior 不変）。実データでは発火しない想定だが、
  発火しても結果の正しさは Decimal 経路が保証。
- spread / unrealized / pnl も同様に乗算前 sentinel（典型値では発火しない）。
- debug build では sentinel を assert で強制し、golden で reference と全数比較。

### startup preflight（kernel 適用条件、静的・軽量。overflow は上記 sentinel に委譲）
`run_backtest` 冒頭で以下を満たす時のみ kernel を使う（不成立は現行 Decimal engine）:
1. `holding_cost_per_day_bps == 0`（§2-3）
2. maintenance == 100 かつ max_spread が整数 bps（§2-2 終端性証明の前提）
3. **leverage == 3**（§2-2 証明は leverage の素因数に依存。他 leverage は証明一般化までフォールバック）
4. strategy が prepared path（DslStrategy）かつ on_bar が単一 signal 契約を満たすこと
※ overflow は preflight の hard gate にせず、kernel 内 runtime sentinel + Decimal 再実行で扱う。

---

## 6. コーナーケース一覧と期待動作（承認条件 3）

| ケース | 期待動作（現行と一致） |
|---|---|
| same-bar fill+stop | step4 で fill 後、同 bar step6 margin / step7 session / step9 eod の順で close され得る |
| negative equity intrabar | step3 で `equity<=0` → 当 bar の open pending を drop（+counter）。close は実行 |
| session close と signal が同一 bar | step7 で強制 close、step8 の open 系 signal は drop（counter）、close 系は submit |
| spread filter hit | step2 で前 bar spread>max なら open pending drop（close は通す） |
| pending order then forced close | step4 fill 後に step6/7/9 で即 close もあり得る（現行同一） |
| short の holding_cost | holding_cost>0 は施策 5 でフォールバック（kernel scope 外） |
| margin call と session/EOD 同一 bar | step6→7→9 順。step6 で close すれば pos=0 で 7/9 no-op |
| mid<=0 防御 | `(ask_c+bid_c)<=0` で spread 更新せず（step5）、前 bar 値維持（`mock.py:283` 同義） |
| 端数決済（end_of_run） | ループ後保有残を last bar close で決済 |
| 0 trade genome | trades 空・equity 一定（initial_cash）で正常終了 |

---

## 7. 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | **standalone** |
| 判断根拠 | engine/broker の per-bar 中核を作り替えるため他施策と高 conflict。golden 確立まで隔離 worktree で進め、bit-identical を確認してから main へ。施策 1→2→4(golden)→3→5 の順で段階。 |
| 競合リスク | engine.py / broker は多数 caller が依存。signature 不変で blast-radius を限定。 |
| 想定実装時間 | 長（kernel + golden 検証が中心、丸め一致の実証が肝） |

---

## 8. Round 1 指摘の解決状況
1. **composite 一括化（W5）**: 解決。v1 は per-index 同一 njit 呼びのみ（§施策3 composite 取得）。
   bulk 化は golden 後の scope 外最適化。
2. **margin 二段丸め（W3）→ 解決**: finite-granularity 証明（§2-2）で、equity が 1e-5 整数倍 ×
   `notional/leverage` 非終端（leverage=3）のため divergence 集合は空。maint=100 default 前提、
   非 default は preflight でフォールバック（§5）。golden が最終実証。
3. **margin スケール（C1）→ 解決**: `*SCALE_RATIO`(=1e3) で両辺 1e8 次元に整合（§2-2/§5）。
4. **same-bar margin equity 再計算（C2）→ 解決**: step6 で post-fill equity 再計算（§3）。
5. **pending 複数 signal（W4）→ 解決**: 単一性不変条件 + multi-signal はフォールバック（§3）。
6. **overflow（W6/Round3 W）→ 解決**: 典型値 ~3e16 < 9.22e18。静的保守上界は hard gate にせず
   （自滅回避）、kernel 内 runtime sentinel（乗算前 `abs < INT64_MAX//係数`）+ 超過時 caller が
   Decimal 再実行（§5）。

### 残る検証 TODO（実装時）
- equity 記録 `out_equity_scaled[i]` が現行 `encode_equity(snapshot.equity)` と全 bar bit 一致するか
  （step10 の close vs open 価格・unrealized 符号）。golden（施策4）で実証。
- F4/F5（config / 単一ポジション）は実装着手時に最新 main で再 grep 確認（Codex C4 INCONCLUSIVE 指摘）。
