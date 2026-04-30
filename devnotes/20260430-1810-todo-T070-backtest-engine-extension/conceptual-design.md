# 概念設計: T070 — Backtest engine 拡張 (session bucket / spread_cost / session block PnL)

**作成日時**: 2026-04-30 17:59 JST (Round 2 改訂: 18:15 JST、 Round 3 改訂: 18:30 JST、 Round 4 改訂: 18:45 JST)
**設計者**: Claude
**M5 開始**: 1/3 (T070 / T071 / T072 で M5 完了)
**前提**: synthesis Round 21 改訂後 (`devnotes/20260428-2300-cascade-port-debate/synthesis.md`)、 main@`f5e6fc2`
**改訂履歴**: Round 1 [C1-C3] / [W1-W3] / [S1-S3] / [F13-F18] + Round 2 [C4-C5] / [W4-W6] / [S4-S6] / [F19-F21] + Round 3 [C6-C7] / [W7-W9] / [S7-S9] / [F22-F23] 全反映
**前提検証** (C4):
- synthesis § 4.4 「session block sample (1 営業日 × 1 bucket = 8h)」 が確定文 ✓
- synthesis § 6.2 SR_session_worst が「block PnL series (1 営業日 × 1 session bucket = 8h) for b in {Tokyo, London, NY}」 で計算される確定文 ✓
- synthesis § 6.3 session_block_win_rate_worst が「session block PnL > 0」 を win 判定する確定文 ✓
- synthesis § 18.2 T913 「Backtest engine 拡張: session bucket label per bar + session block PnL series + block trade_count 出力」 が確定文 ✓
- T064 conceptual-design § 401-403 で「TradeRecord は spread cost を分離していない、 Phase 2 (T070) で `TradeRecord.spread_cost` field 追加 + apply_spread_stress 正式実装」 が確定文 ✓
- T064 conceptual-design § 459 で「Phase 2 後段で `TradeRecord.spread_cost` field 追加 → apply_spread_stress 正式実装」 が T070 担当 ✓
- 既存 `src/alpha_factory/primitives/_indicators.py:51-55` の `_SESSION_RANGES_UTC` (Tokyo 00-09 / London 07-16 / NY 12-21) は **9h 重複あり windows、 primitives indicator 用**。 T070 の **8h covering partition (synthesis § 4.4)** とは別責務、 T070 では touch しない ✓

## 1. ゴール

synthesis § 4.4 / § 6.2 / § 6.3 / § 18.2 T913 を厳密準拠した backtest engine 拡張 (Phase 1 = library + 既存 dataclass 拡張、 caller 配線は Phase 2):

1. **Trade.spread_cost / Trade.holding_cost field 追加**: pnl 構成成分の正本記録 (Round 2 [C4] 反映で holding_cost も追加)、 `apply_spread_stress` (T064 申し送り) を正式版に置換可能化
2. **SessionBlockBucket (Tokyo / London / NY) 8h covering partition**: synthesis § 4.4 厳密準拠、 24h を 3 partition で過不足なくカバー
3. **bar -> bucket 計算 関数**: bar.bar_time UTC hour から決定論的に bucket を割当
4. **SessionBlock 集計**: 1 営業日 (UTC date) × 1 bucket = 1 SessionBlock、 block 内の trade_count / pnl_net / pnl_before_costs / spread_cost_total / holding_cost_total を集計
5. **apply_spread_stress 正式実装**: T064 で `NotImplementedError` で skeleton 化された関数を、 spread_cost field を活用して正式実装

T913 (synthesis § 18.2) の calibrate-gate scope 相当は T070 が直接対応するが、 「DST/holiday boundary contract」 は **T072 (T914) 担当** で別 TODO に分離。 T070 では UTC 基準・DST 無視 (= primitives 既存方針と整合) でまず確定し、 T072 で contract 化。

## 2. C2 parallel-path 5 段階 grep + Consumer Inventory

T070 は既存 backtest path (`src/backtest/engine.py` / `src/broker/orders.py` の Trade / `src/alpha_factory/primitives/_indicators.py` の SESSION_RANGES) を拡張する。 並列実装の有無 + 下流 consumer を点検:

### 2.1 並列実装検証 (5 段階)

| 段階 | 検査 | 結果 |
|---|---|---|
| 直 import | `from src.broker.orders import Trade` | `src/backtest/engine.py:11`、 `src/broker/mock.py` 系のみ |
| alias | `import Trade as` | 不在 |
| relative | `from .orders import Trade` | `src/broker/__init__.py` で再 export 確認 |
| 再エクスポート | `__init__.py` 経由 | broker パッケージで Trade を re-export |
| runtime シンボル | `getattr(... "Trade"` | 不在 |

→ Trade 系 path は単一系統。 spread_cost 追加で全 caller に default で通る。

### 2.2 Consumer Inventory (Trade / session bucket / session block を読む経路)

| Consumer | ファイル | 読む対象 | T070 影響 |
|---|---|---|---|
| `BacktestResult.trades: list[Trade]` | `src/backtest/engine.py:77` | trades 全 field | Trade.spread_cost 追加で問題なし (default=0) |
| `MockBroker.trades` | `src/broker/mock.py` | Trade の build / append | T070 で spread_cost 計算ロジック追加 |
| `apply_spread_stress` (T064 skeleton) | `src/alpha_factory/stage_bc_evaluator.py` (T064 PR で配置予定) | trades の spread_cost を読み pnl 補正 | T070 で正式実装 |
| canonical_5_engine (T061) | `src/alpha_factory/canonical_metrics.py` (T061 PR で配置予定) | SessionBlock 配列を入力に SR_session_worst / WR_worst 計算 | T070 PR で SessionBlock 構造を提供 |
| primitives `_SESSION_RANGES_UTC` | `src/alpha_factory/primitives/_indicators.py:51-55` | bar -> 9h 重複 indicator | T070 では touch しない (= 別責務、 重複あり windows) |
| 既存 backtest_runner | `scripts/alpha_factory/run_ga.py` 等 | BacktestResult 単独利用 | T070 影響なし (Phase 2 で session_block 利用配線) |

→ T070 は library + Trade + SessionBlock 計算関数 の追加が中心、 既存 backtest runner / primitives は touch しない。

## 3. アーキテクチャ概要

### 3.1 機能分割 (新設 1 module + 既存 1 dataclass 拡張 + 既存 engine 軽微変更)

```
src/backtest/
├── engine.py          ← 既存、 BacktestResult.session_blocks 追加 + run_backtest 末尾で aggregate
└── session_block.py   ← 新設 (T070 中核)
    ├── SessionBlockBucket (Literal["tokyo", "london", "ny"])
    ├── BLOCK_BUCKET_RANGES_UTC  (8h covering partition、 T070 SSOT)
    ├── compute_bucket_for_bar()      (pure function、 bar -> bucket)
    ├── compute_bucket_for_trade()    (pure function、 trade -> bucket、 exit_time 基準)
    ├── SessionBlock                  (dataclass, immutable)
    ├── aggregate_session_blocks()    (pure function、 trades + bars -> SessionBlock 配列)
    └── apply_spread_stress()         (pure function、 T064 申し送り解消)

src/broker/
├── orders.py          ← 既存、 Trade dataclass に spread_cost + holding_cost field 追加 (Round 3 [C7] 反映)
└── mock.py            ← 既存、 _close_one で spread_cost 計算 + holding_cost 転記

src/alpha_factory/
└── (T064 配置予定) stage_bc_evaluator.py の apply_spread_stress を Phase 2 で T070 関数に置換
```

### 3.2 Session bucket partition (synthesis § 4.4 / § 6.2 SSOT)

UTC 24 時間を 3 covering partition (8h × 3、 重複なし) で分割:

| Bucket | UTC 時間範囲 | 想定主要マーケット |
|---|---|---|
| `tokyo` | `00:00 - 08:00` (= JST 09:00-17:00) | Tokyo session |
| `london` | `08:00 - 16:00` | London session |
| `ny` | `16:00 - 24:00` (= 0:00 翌日) | NY session 後半 |

設計判断:
- synthesis § 4.4 「8h × 3 = 24h」 を覆う covering partition (重複なし) を採用
- 既存 `_SESSION_RANGES_UTC` (primitives) の 9h 重複 windows とは**別責務**で並列管理
- 「Tokyo open / London open / NY open」 のような市場慣行 (= 13:00 UTC からの NY 等) は採用しない (= synthesis 厳密 8h covering を SSOT)
- DST / holiday は T072 (T914) で対応、 T070 では UTC 単純基準

### 3.3 bar -> bucket 計算 (決定論的、 pure function)

```python
def compute_bucket_for_bar(bar_time: datetime) -> SessionBlockBucket:
    """UTC hour から bucket を決定論的に割当.

    SSOT:
        00 <= hour < 08 → "tokyo"
        08 <= hour < 16 → "london"
        16 <= hour < 24 → "ny"

    Args:
        bar_time: timezone-aware UTC datetime (= bar.bar_time).

    Returns:
        SessionBlockBucket ("tokyo" / "london" / "ny").

    Raises:
        ValueError: bar_time が naive (tzinfo=None) の場合.
    """
```

### 3.4 SessionBlock 集計 (synthesis § 6.2 / § 6.3 SSOT、 Round 1 [C1] / Round 2 [C5] 反映で会計契約確定)

1 営業日 (UTC date) × 1 bucket = 1 SessionBlock:

```
session_block (date=2024-01-15, bucket="tokyo")
  bar_count: 480           # 8h × 60min = 480 bars (M1)
  trade_count: 5
  pnl_net: -12.5           # = sum(Trade.pnl - Trade.spread_cost) (= 全 cost 控除済 net)
  pnl_before_costs: -8.0   # = sum(Trade.pnl + Trade.holding_cost) (= raw price-diff sum)
  spread_cost_total: 4.0   # block 内 trade の spread_cost 合計
  holding_cost_total: 0.5  # block 内 trade の holding_cost 合計
```

#### 3.4.0 会計契約 SSOT (Round 2 [C5] 反映、 既存 broker 挙動と整合)

**既存 broker 挙動の事実認識** (`src/broker/mock.py` 検証済):
- `apply_bar_holding_cost`: bar 単位で `self._cash` から `total_cost` を控除 + 各 position の `_holding_cost_by_position[pos.id]` に累積
- `_close_one`: `raw_pnl = exit_price - entry_price 系の生 pnl`、 `cost_accum = _holding_cost_by_position[pos.id]`、 `net_pnl = raw_pnl - cost_accum`、 `self._cash += raw_pnl`、 `Trade.pnl = net_pnl`
- 既存挙動で `Trade.pnl` は既に **net of holding_cost** (= 既存 T009 でこの形に確立済)
- spread cost は既存 broker では `max_spread_bps` による **signal reject** のみで、 fill された trade の pnl から控除されない (= 既存挙動)

**T070 SSOT (会計契約、 Round 3 確定)**:
1. **broker.cash 操作は既存挙動を維持** (= T070 で broker.cash の動きは破壊変更しない)
2. **Trade.pnl** = 既存「holding_cost 控除済 net pnl」 (= raw_pnl - holding_cost_accum) のまま
3. **Trade.holding_cost** (T070 新規) = 既存 `_holding_cost_by_position[pos.id]` を Trade に転記、 **cash 操作なし** (= 監査用)
4. **Trade.spread_cost** (T070 新規) = entry/exit 時の bid/ask spread 推定値、 **cash 操作なし、 既存 Trade.pnl にも未反映** (= 既存挙動と整合)
5. SessionBlock 集計式 (= F19 二重計上防御):
   - `pnl_net = sum(t.pnl - t.spread_cost for t in trades_in_block)` (= holding は既に Trade.pnl に net、 spread は別途控除)
   - `pnl_before_costs = sum(t.pnl + t.holding_cost for t in trades_in_block)` (= raw price-diff sum、 cost 加え戻し)
   - `spread_cost_total = sum(t.spread_cost for t in trades_in_block)`
   - `holding_cost_total = sum(t.holding_cost for t in trades_in_block)`
6. **不変条件 (代数的に検算)**:
   - `pnl_before_costs - spread_cost_total - holding_cost_total = sum(t.pnl + t.holding_cost) - sum(t.spread_cost) - sum(t.holding_cost) = sum(t.pnl - t.spread_cost) = pnl_net` ✓
   - つまり `pnl_before_costs == pnl_net + spread_cost_total + holding_cost_total` が成立
7. **二重計上防御** (Round 2 [F19]): `Trade.holding_cost` は既存 cash 操作 (`apply_bar_holding_cost` で控除済) の **再記録のみ**、 close 時に追加で cash を弄らない (= 既存 `_close_one` の `self._cash += raw_pnl` 挙動を破壊しない)
8. **apply_spread_stress 代数**: `new_pnl = trade.pnl - trade.spread_cost * (multiplier - 1)`
   - multiplier=1 で no-op (`new_pnl = trade.pnl - 0 = trade.pnl`) ✓
   - multiplier=2 で `new_pnl = trade.pnl - trade.spread_cost` (= 元 pnl から spread を 1 倍だけ余計に控除) ✓
   - これは「spread が現在の 2 倍だった場合の pnl」 を再現

#### 3.4.1 帰属規約 (Round 1 [C1] 反映、 SSOT 統一)

**全 cost を trade.exit_time bucket に一括帰属** する設計を採用:
- trade.pnl: trade.exit_time 側 bucket に全額帰属
- trade.spread_cost: 同上
- trade.holding_cost: 同上

bar-level holding_cost_per_bar は T070 SSOT 集計では使用しない (= 旧 §5.2 の `holding_cost_per_bar: Mapping[datetime, Decimal]` 引数を削除)。 代わりに **`Trade.holding_cost` field** で trade lifetime 累積を読み、 block 集計時に exit bucket 一括帰属。

これにより:
- entry/exit が異なる bucket の trade も exit bucket 一括 (= Round 1 [F16] 防御)
- empty block (trade_count=0) は全 cost 0、 neutral

#### 3.4.2 既存 cash 操作と Trade field 記録の責務分離

trade lifetime 中の bar holding cost は既存 engine `apply_bar_holding_cost` で **bar 単位 cash 控除** されている (= 既存挙動)。 T070 で新設する `Trade.holding_cost` field はこの値を **記録 (= 監査用)** するだけで、 close 時に追加 cash 操作を行わない。 既存 `_close_one` の `self._cash += raw_pnl` 挙動を維持。

spread cost も同様: T070 で `Trade.spread_cost` を記録するが、 既存 broker は spread を pnl 控除していないため、 close 時の cash 操作は変更なし (= 「Trade.spread_cost は監査・stress 用」 として概念で固定)。

これは Phase 2 で broker 側が spread を pnl に直接反映する経路を導入する場合は別契約 (= T070 では未対応、 Phase 2 で再設計)。

### 3.5 Trade dataclass 拡張 (Round 2 [C4] / [C5] 反映、 既存挙動整合)

```python
@dataclass(frozen=True)
class Trade:
    # ... (既存 field 全て維持)
    spread_cost: Decimal = Decimal(0)   # ← T070 追加 (記録のみ、 既存 pnl に未反映)
    holding_cost: Decimal = Decimal(0)  # ← T070 追加 (= holding_cost_accum 転記、 既存 pnl に既反映済)
```

**SSOT 契約 (Round 2 [C5] 反映、 既存挙動と整合)**:
- `Trade.pnl` は **既存挙動を維持: holding_cost 控除済 net pnl** (= raw_pnl - holding_cost_accum)
- `Trade.holding_cost` は `_holding_cost_by_position[pos.id]` の値を **Trade 構築時に転記** (= 既に Trade.pnl に控除されている holding cost の正本値)
- `Trade.spread_cost` は entry/exit spread 推定値を記録、 **既存 Trade.pnl には未反映** (= 既存 broker 挙動と整合)
- 不変条件: `Trade.pnl + Trade.holding_cost = raw_pnl (= price-diff pnl)`、 `Trade.spread_cost` は raw_pnl に含まれない

これにより:
- 既存 cash 操作の二重計上を防御 (Round 2 [F19] 解消)
- `apply_spread_stress(trades, multiplier)`: `new_pnl = trade.pnl - trade.spread_cost * (multiplier - 1)` が **既存挙動の上に整合する代数** で成立
- T064 stage_bc_evaluator の spread stress 評価が代数的に正しい

`_close_one` 改造ポイント (詳細設計で式確定、 Round 4 [W11] 反映で表記統一):
1. 既存挙動の `raw_pnl = self._realized_pnl(pos, exit_price)` を維持
2. 既存挙動の `cost_accum = self._holding_cost_by_position.pop(pos.id, Decimal(0))` を維持
3. 既存挙動の `net_pnl = raw_pnl - cost_accum` を維持
4. **T070 追加**: `spread_cost = (entry_spread + exit_spread を units * mid_price で換算)` を計算 (詳細式は実装で確定)
5. **T070 追加**: `Trade(pnl=net_pnl, spread_cost=spread_cost, holding_cost=cost_accum, ...)` で Trade 構築
6. 既存挙動の `self._cash += raw_pnl` を維持 (= T070 で cash 操作変更なし)

### 3.6 apply_spread_stress 正式実装 (T064 申し送り完了)

T064 で:
```python
def apply_spread_stress(trades, multiplier):
    raise NotImplementedError(
        "apply_spread_stress requires TradeRecord.spread_cost field "
        "added by T070 backtest engine extension"
    )
```

T070 で正式実装:
```python
def apply_spread_stress(
    trades: tuple[Trade, ...],
    multiplier: Decimal,
) -> tuple[Trade, ...]:
    """各 trade の spread_cost を multiplier 倍にして pnl を再計算した tuple を返す.

    Stress 適用式:
        new_pnl = trade.pnl - trade.spread_cost * (multiplier - 1)
    (= 元の spread_cost が multiplier 倍に膨れた場合の trade pnl を再現)

    Args:
        trades: 元の trade tuple (immutable).
        multiplier: spread cost 倍率 (>= 1.0、 1.0 で no-op).

    Returns:
        新 Trade tuple (元 tuple は不変、 frozen dataclass 性質を維持).

    Raises:
        ValueError: multiplier < 1.0 の場合.
    """
```

T070 (Phase 1) で **library 単独実装**、 caller 配線 (T064 stage_bc_evaluator) は Phase 2。

## 4. データモデル (Phase 1 範囲)

### 4.1 SessionBlockBucket (新規)

```python
SessionBlockBucket = Literal["tokyo", "london", "ny"]
```

### 4.2 BLOCK_BUCKET_RANGES_UTC (新規 SSOT)

```python
BLOCK_BUCKET_RANGES_UTC: Final[dict[SessionBlockBucket, tuple[int, int]]] = {
    "tokyo":  (0, 8),    # [0, 8) UTC hour
    "london": (8, 16),   # [8, 16)
    "ny":     (16, 24),  # [16, 24)
}
```

不変条件:
- 各 range は半開区間 `[start, end)`
- 24h 全体を過不足なくカバー (重複・空白なし)
- T070 で SSOT 固定、 T072 で DST / holiday 対応時にも本 range 自体は変えない (= 局所例外として別 layer で扱う)

### 4.3 SessionBlock (新規、 Round 1 [C1] / [S1] / [S3] 反映)

```python
@dataclass(frozen=True)
class SessionBlock:
    """1 営業日 (UTC date) × 1 bucket = 1 block (synthesis § 4.4 SSOT).

    Attributes:
        business_date: UTC date (date object). T072 で営業日定義の精緻化予定.
        bucket: tokyo / london / ny.
        bar_count: block 内 bar 数 (M1 想定で 8h = 480 bars だが、 末日や週末で減ることあり).
        trade_count: block 内 trade 数 (= trade.exit_time が本 block に属する trade、
            Round 1 [C1] 反映で全 cost を exit bucket 一括帰属).
        pnl_net: block 内 trade の全 cost 控除済 net 合計 (= sum(t.pnl - t.spread_cost),
            holding は既に Trade.pnl に控除済、 spread は block 集計時に別途控除. §3.4.0 SSOT 参照).
        pnl_before_costs: pnl_net + spread_cost_total + holding_cost_total
            (= 控除前 gross. Round 1 [S3] 反映で `pnl_gross` から命名変更、
             分解方向 (cost を加え戻す) を明示).
        spread_cost_total: block 内 trade の spread_cost 合計.
        holding_cost_total: block 内 trade の holding_cost 合計
            (Round 1 [C1] 反映: bar 配賦ではなく trade lifetime 集計を exit bucket 一括帰属).
    """

    business_date: date
    bucket: SessionBlockBucket
    bar_count: int
    trade_count: int
    pnl_net: Decimal
    pnl_before_costs: Decimal
    spread_cost_total: Decimal
    holding_cost_total: Decimal

    # Round 1 [S1] 反映: T061 / T072 が neutral / boundary を機械的に判定するための派生情報
    @property
    def is_empty_trade_block(self) -> bool:
        """trade_count == 0 (= synthesis § 6.3 0.5 neutral 対象)."""
        return self.trade_count == 0

    @property
    def is_partial_bar_block(self) -> bool:
        """bar_count < 8h × 60min (= 末日・週末・holiday で 8h を満たさない block).
        T072 で正確な期待 bar_count を計算する場合は本 property を上書きする可能性あり。
        T070 SSOT は M1 前提で `expected_bar_count = 480`."""
        return self.bar_count < 480
```

不変条件:
- `bar_count >= 0`
- `trade_count >= 0`
- `pnl_before_costs == pnl_net + spread_cost_total + holding_cost_total` (= 全 cost を加え戻すと gross)
- `spread_cost_total >= 0` (= cost は非負)
- `holding_cost_total >= 0`

### 4.4 Trade (既存拡張、 Round 2 [C5] 反映で既存挙動整合)

```python
@dataclass(frozen=True)
class Trade:
    # 既存 field
    position_id: int
    instrument: str
    side: PositionSide
    units: int
    entry_price: Decimal
    entry_time: datetime
    exit_price: Decimal
    exit_time: datetime
    pnl: Decimal
    exit_reason: ExitReason
    equity_at_entry: Decimal = Decimal(0)
    # T070 追加 (Round 2 [C5] 反映で既存挙動整合)
    spread_cost: Decimal = Decimal(0)   # 記録のみ、 既存 pnl 未反映 (既存 broker は spread を pnl 控除していない)
    holding_cost: Decimal = Decimal(0)  # _holding_cost_by_position[pos.id] の転記 (既存 pnl に既反映)
```

不変条件:
- `spread_cost >= 0`
- `holding_cost >= 0`
- `pnl` は既存挙動: **holding_cost 控除済 net pnl** (= raw_pnl - holding_cost) を維持
- **既存挙動整合 contract**: `pnl + holding_cost = raw_pnl` (price-diff pnl)、 `spread_cost` は別途記録
- block 集計式 (§3.4.0 SSOT):
  - `pnl_net = sum(t.pnl - t.spread_cost)` (block level で spread 控除を実施)
  - `pnl_before_costs = sum(t.pnl + t.holding_cost)` (cost 加え戻し)
  - 検算: `pnl_before_costs - spread_cost_total - holding_cost_total = pnl_net` ✓

## 5. API シグネチャ (§ 11.2 SSOT 規約: 本節が正本)

### 5.1 compute_bucket_for_bar / compute_bucket_for_trade (Round 1 [S2] 反映)

bar 用と trade 用で基準時刻が異なるため、 関数を**分離**:

```python
def compute_bucket_for_bar(bar_time: datetime) -> SessionBlockBucket:
    """UTC hour から SessionBlockBucket を決定論的に割当 (bar の業務時刻ベース).

    SSOT (synthesis § 4.4 8h covering partition):
        [0, 8)  UTC → "tokyo"
        [8, 16) UTC → "london"
        [16, 24) UTC → "ny"

    Args:
        bar_time: timezone-aware UTC datetime.

    Returns:
        SessionBlockBucket.

    Raises:
        ValueError: bar_time.tzinfo is None / 非 UTC.
    """


def compute_bucket_for_trade(trade: Trade) -> SessionBlockBucket:
    """trade 帰属 bucket を決定論的に算出 (= trade.exit_time 基準).

    Round 1 [C1] 反映: trade の全 cost (pnl / spread_cost / holding_cost) を
    exit_time bucket に一括帰属する SSOT を関数名で明示.

    Args:
        trade: Trade dataclass.

    Returns:
        SessionBlockBucket (compute_bucket_for_bar(trade.exit_time) と同義).
    """
```

### 5.2 aggregate_session_blocks (Round 1 [C1] / [W1] 反映、 Round 2 で signature 単純化)

```python
def aggregate_session_blocks(
    bars: Sequence[PriceBar],
    trades: Sequence[Trade],
) -> tuple[SessionBlock, ...]:
    """bars と trades から SessionBlock 配列を構築する (pure function).

    SSOT: 概念設計 §3.4.

    Round 1 [C1] 反映: holding_cost_per_bar 引数を削除、 cost は全て trade level
    (Trade.spread_cost / Trade.holding_cost) で持つため、 caller が bar 配賦を
    別経路で管理する余地を排除 (= F14 防御).

    Round 1 [W1] 反映: date universe = bars に存在する UTC date 集合 (calendar
    date 全体ではない、 holiday/欠損日は T072 で判定強化). 各 (date, bucket) について
    必ず block を生成 (= empty block 含む、 synthesis § 6.3 0.5 neutral 維持).

    Args:
        bars: backtest 期間中の全 bar (時系列順、 UTC tz-aware).
        trades: backtest で生成された全 trade.

    Returns:
        SessionBlock の tuple. (date, bucket) で sort、 date universe は bars が
        触れた UTC date 集合 × 3 bucket. trade_count==0 / bar_count==0 の block も含む
        (= synthesis § 4.4 で「trade=0 block は 0.5 neutral」 と扱うため).

    Raises:
        ValueError: bar_time が naive / 非 UTC.
        ValueError: trade.exit_time が naive / 非 UTC.
    """
```

### 5.3 apply_spread_stress (T064 skeleton 置換)

```python
def apply_spread_stress(
    trades: Sequence[Trade],
    multiplier: Decimal,
) -> tuple[Trade, ...]:
    """各 trade の spread_cost を multiplier 倍にして pnl を再計算した tuple を返す.

    Stress 適用式:
        delta_spread = trade.spread_cost * (multiplier - Decimal(1))
        new_pnl = trade.pnl - delta_spread
        new_spread_cost = trade.spread_cost * multiplier

    Args:
        trades: 元 trade sequence (frozen=True dataclass のため shallow copy で OK).
        multiplier: spread cost 倍率 (>= 1.0、 1.0 で no-op).

    Returns:
        新 Trade tuple (元 tuple は不変).

    Raises:
        ValueError: multiplier < 1.0.
    """
```

### 5.4 broker / engine 側の spread_cost 計算 link

`MockBroker._close_one` で trade を構築する際、 `entry_price` と `exit_price` の spread から `spread_cost` を計算 (= 既存 max_spread_bps 同様の計算式)。 詳細設計で実装ロジックを確定。 (Round 4 [W11] 反映で `_close_position` から `_close_one` に表記統一)

## 6. 関連 module 変更点

### 6.1 src/backtest/session_block.py (新規)

- §4.1 SessionBlockBucket
- §4.2 BLOCK_BUCKET_RANGES_UTC
- §4.3 SessionBlock dataclass
- §5.1 compute_bucket_for_bar
- §5.2 aggregate_session_blocks
- §5.3 apply_spread_stress

### 6.2 src/broker/orders.py (既存拡張、 Round 3 [C7] 反映で holding_cost も明記)

- §4.4 Trade に `spread_cost: Decimal = Decimal(0)` 追加 (記録のみ、 既存 pnl 未反映)
- §4.4 Trade に `holding_cost: Decimal = Decimal(0)` 追加 (= `_holding_cost_by_position[pos.id]` の転記、 既存 pnl に既反映済)

### 6.3 src/broker/mock.py (既存最小変更、 Round 2 [C5] 反映で既存挙動維持)

- 既存 `_close_one` の **cash 操作 / pnl 計算は変更しない** (= broker.cash 動きの破壊変更を回避)
- 追加変更: Trade 構築時に `spread_cost` / `holding_cost` field を計算 + 注入
- 計算手順 (詳細設計で式確定):
  1. 既存維持: `raw_pnl = self._realized_pnl(pos, exit_price)`
  2. 既存維持: `cost_accum = self._holding_cost_by_position.pop(pos.id, Decimal(0))`
  3. 既存維持: `net_pnl = raw_pnl - cost_accum`
  4. **T070 追加**: `spread_cost = entry/exit spread を units * notional 換算で算出` (詳細式は実装で確定)
  5. **T070 追加**: `Trade(pnl=net_pnl, spread_cost=spread_cost, holding_cost=cost_accum, ...)` で Trade 構築
  6. 既存維持: `self._cash += raw_pnl`
- 既存 `apply_bar_holding_cost` 挙動は変更なし (= bar 単位 cash 控除を継続)
- 既存 `_holding_cost_by_position` counter は既に存在、 T070 で新規追加不要 (= Trade.holding_cost に転記するだけ)
- 既存 `max_spread_bps` reject 経路は維持 (= spread_cost field 追加と独立)
- entry/exit spread 推定の元データ (PriceBar の bid/ask 等) が現状取得可能か、 詳細設計で検証必須 (= 取得不可なら spread_cost=0 で記録、 Phase 2 で broker 改造)

### 6.4 src/backtest/engine.py (既存変更、 Round 1 [C3] 反映で transport SSOT 確立)

Round 1 [C3] 解消のため、 SessionBlock の生成を **engine 内で 1 回のみ実施** し、 結果を `BacktestResult` に同梱する経路を T070 SSOT として確立:

- `BacktestResult.session_blocks: tuple[SessionBlock, ...]` を新規 field 追加 (default_factory で空 tuple)
- `run_backtest()` 末尾で `BacktestResult.session_blocks = aggregate_session_blocks(bars_list, broker.trades)` を計算して結果に同梱
- caller (T061 / T064 / Phase 2 配線) は `result.session_blocks` を読むのみ、 **再計算は禁止** (= F14 防御、 contract 化)
- `aggregate_session_blocks` 自体は public function で残し、 unit test や非 engine 経路 (= run_backtest を経由しない) でも利用可能

backward-compat:
- `BacktestResult.session_blocks` は default `tuple()` のため、 既存 caller (= session_blocks を読まない) は影響なし
- 既存 `BacktestResult(config=..., trades=..., equity_curve=...)` の positional / keyword 構築は破壊されない (= field 順序末尾に追加)

### 6.5 T064 stage_bc_evaluator.py (Phase 2 申し送り)

T064 で skeleton 化された `apply_spread_stress` を Phase 2 で T070 の `src/backtest/session_block.py::apply_spread_stress` に置換。 T064 caller は import path を変更するだけで完結。

T064 の `evaluate_stage_c` で `stress_pass = StagePassStatus.PENDING` で placeholder している箇所を、 T070 完了後に正式 `stress_pass` 計算に置換 (Phase 2)。

### 6.6 T061 canonical_metrics.py (Phase 2 申し送り)

T061 で `SR_session_worst` / `session_block_win_rate_worst` を計算する関数は、 T070 で構築した `SessionBlock` 配列を入力として受け取る前提。 T061 PR と T070 PR の merge 順序は **T070 先行 必須** (= T061 が SessionBlock を import するため)。

## 7. C3 Collider bias / C7 Sample size / C9 Falsification-first

### 7.1 C3 Collider bias

T070 自体は集計層のため、 因果解釈は本タスク内では行わない (= 「リスク 0」 の断定ではなく、 conditioning の置き方の影響は後段 evaluator/audit で再評価対象、 Round 1 [W3] 反映)。 SessionBlock の neutral 扱い (trade=0) は後段の比較分析で conditioning 設計を必要とする旨を T061 / T071 申し送り。

### 7.2 C7 Sample size

`SessionBlock.bar_count` が小さい block (= 末日・週末で 8h 未満) は将来 T072 で「無効 block」 として除外する判定が入る可能性あり (DST/holiday)。 T070 では bar_count を field として保持するだけ、 除外判定は別 layer (T061 / T072) で行う。

### 7.3 C9 Falsification-first

T070 が壊れる経路を **先に列挙**:

| 失敗モード | 検出方法 | 対処 |
|---|---|---|
| F1: bar_time が naive (tz不明) で bucket 誤判定 | `compute_bucket_for_bar` で `bar_time.tzinfo is None` チェック | ValueError raise |
| F2: bar_time が非 UTC tz | `bar_time.utcoffset() != timedelta(0)` チェック | ValueError raise |
| F3: bucket 重複・空白 (range 不整合) | `BLOCK_BUCKET_RANGES_UTC` を Final immutable + unit test で 24h covering 確認 | const で SSOT 固定 |
| F4: trade.exit_time と entry_time が異なる bucket で集計が歪む | docstring で「exit_time bucket に集計」 を SSOT 化、 unit test で確認 | 設計上の選択を明示 |
| F5: multiplier < 1.0 で apply_spread_stress 暴走 | `apply_spread_stress` 入口で check | ValueError raise |
| F6: SessionBlock の pnl_before_costs != pnl_net + spread + holding | `__post_init__` で invariant 確認 (Round 2 [W4] で命名統一済) | ValueError raise |
| F7: empty block (bar_count=0 or trade_count=0) を出さず win_rate 計算が漏れる | `aggregate_session_blocks` で全 (date × bucket) combination を生成 | docstring で「empty block も含む」 を SSOT |
| F8: trade.spread_cost / holding_cost を MockBroker が埋め忘れる (Round 3 [W8] で `_close_one` に表記統一) | `_close_one` 全 path で spread_cost 計算 + holding_cost 転記、 unit test で検証 | engine path を 1 箇所化 |
| F9: 既存 Trade caller (test fixture 等) が positional 引数で Trade(...) を構築していた場合に default 引数追加で壊れる | `spread_cost` を最後 field に置く + default=Decimal(0) | dataclass 順序設計 |
| F10: ~~holding_cost_per_bar の unit ずれ~~ (Round 2 [W4]: holding_cost は trade level に統合済、 本 F10 は無効化) | aggregate_session_blocks の signature から bar level holding_cost 引数を削除 (Round 2 [C1] / [C5]) | 削除済 |
| F11: T072 (DST/holiday) と T070 SSOT の衝突 | T070 は UTC 単純基準で固定、 T072 は別 layer で対応 (block 例外を別途 mark) | 責務分離 |
| F12: SessionBlock.business_date の定義揺れ (UTC date vs JST date vs broker tz date) | T070 SSOT として **UTC date** を採用 (= synthesis 整合)、 docstring 明記 | T072 で再校正検討 |
| F13 (Round 1 追加 / Round 3 [S9] 修正): spread_cost / holding_cost が `_close_one` で同時算出されない | spread_cost は entry/exit spread 推定の記録、 holding_cost は `_holding_cost_by_position` 転記、 invariant: `Trade.pnl + Trade.holding_cost == raw_pnl` (§3.4.0 SSOT) を unit test で検証。 spread_cost は raw_pnl と独立に記録されることを明示 (= 「pnl 内訳の正本」 ではなく「監査・stress 用の独立記録」) | §3.4.0 / §3.5 SSOT |
| F14 (Round 1 追加): caller が aggregate_session_blocks を再計算、 holding_cost_per_bar 有無で指標差 | engine 内で 1 回計算 + BacktestResult.session_blocks に同梱、 caller は読むのみ | §6.4 SSOT |
| F15 (Round 1 追加): date universe 差で neutral block 数が evaluator ごとに変わる | aggregate_session_blocks の date universe = bars の touched UTC date set で SSOT 固定 | §5.2 |
| F16 (Round 1 追加): entry/exit 跨ぎ trade で spread/holding 混在配賦 | 全 cost を trade level (Trade.spread_cost / Trade.holding_cost) に持ち、 exit bucket 一括帰属 | §3.4.1 / §3.5 SSOT |
| F17 (Round 1 追加): Trade.spread_cost が log/report/archive に出ない | Phase 2 申し送り §9.2 #12 で「spread_cost / holding_cost をログ・レポート・archive に露出」 を明示 | Phase 2 申し送り |
| F18 (Round 1 追加): _SESSION_RANGES_UTC と BLOCK_BUCKET_RANGES_UTC が将来別々に変更され属人化 | docstring で責務分離 (9h overlap 用 / 8h covering 用) を明記 + 命名で独立性を担保 | §3.2 / §6 docstring SSOT |
| F19 (Round 2 追加): close 時に holding_cost を pnl 反映 + cash 再控除で二重計上 | §3.4.0 SSOT 「Trade.holding_cost は記録のみ、 cash 操作なし」 で防御、 既存 `_close_one` 挙動を破壊しない | §3.4.0 / §3.5 |
| F20 (Round 2 追加): Trade.spread_cost / holding_cost が log/report/archive に出ない | Phase 2 申し送り §9.2 #11 で「log / report / archive 露出」 を明示 | Phase 2 申し送り |
| F21 (Round 2 追加): caller が旧再計算経路を保持して指標差分 | `BacktestResult.session_blocks` を SSOT 化、 caller 再計算禁止を契約 + lint で監視 (Round 2 [S6] 反映) | §6.4 SSOT |
| F22 (Round 3 追加): spread_cost を「正本内訳」 vs 「監査記録」 で実装者間解釈が分岐 | §3.4.0 SSOT で「spread_cost は raw_pnl と独立に記録される監査・stress 用 field、 既存 pnl 未反映」 を 1 節集中明記 (Round 3 [S7] / [F22] 反映) | §3.4.0 SSOT |
| F23 (Round 3 追加): orders.py への holding_cost 追加漏れで mock.py だけ更新で静かに壊れる | §6.2 / §9.1 / モジュール図 §3.1 で orders.py / mock.py 両方への追加を明記 (Round 3 [C7] / [F23] 反映)、 invariant test で `Trade.holding_cost field 存在 + default=0` を確認 | §3.1 / §6.2 / §9.1 |

## 8. 期待効果

### 8.1 synthesis § 4.4 / § 6.2 / § 6.3 厳密準拠

- session block PnL series: synthesis § 6.2 SR_session_worst の入力を提供
- session_block_win_rate_worst: synthesis § 6.3 の win 判定を block 単位で実施
- apply_spread_stress: synthesis § 6.4 集約に必要な spread stress 経路を確立

### 8.2 副次効果

- T064 申し送り (`spread_cost field 不在`) を解消、 cascade port 全体の整合性向上
- T061 canonical 5 engine の入力 SSOT を確立
- 既存 `_SESSION_RANGES_UTC` (primitives 9h windows) と SessionBlockBucket (8h covering) を**責務分離**で並列管理、 既存 indicator への影響なし

## 9. Phase 1 / Phase 2 申し送り

### 9.1 Phase 1 (T070 PR で同時更新、 Round 2 [C4] / [W6] / [S5] 反映で網羅化)

| # | 箇所 | 変更内容 |
|---|---|---|
| 1 | `src/backtest/session_block.py` | 新設 (SessionBlockBucket / SessionBlock / compute_bucket_for_bar / compute_bucket_for_trade / aggregate_session_blocks / apply_spread_stress) |
| 2 | `src/broker/orders.py` | Trade に **spread_cost + holding_cost** field 追加 (Round 2 [C4] 反映) |
| 3 | `src/broker/mock.py` | _close_one で **spread_cost 計算 + holding_cost 転記** + Trade 注入 (Round 2 [C4]) |
| 4 | `src/backtest/engine.py` | `BacktestResult.session_blocks: tuple[SessionBlock, ...]` field 追加 + run_backtest 末尾で aggregate_session_blocks 計算 + 同梱 (Round 1 [C3]) |
| 5 | `tests/backtest/test_session_block.py` | F1-F18 unit test (Round 2 [W6] で F13-F18 を必須化) |
| 6 | `tests/broker/test_orders.py` 拡張 | Trade の **spread_cost + holding_cost** default + invariant test |
| 7 | `tests/broker/test_mock.py` 拡張 | _close_one が spread_cost / holding_cost を Trade に乗せる test、 二重計上なし test (F19) |
| 8 | `tests/backtest/test_engine.py` 拡張 | run_backtest 末尾で session_blocks が同梱される test |
| 9 | `docs/alpha_factory/stage-gates.md` | T070 セクション追記 (session block / spread_cost / holding_cost / apply_spread_stress) |

### 9.2 Phase 2 (cascade port 切替 commit、 synthesis § 12.4)

| # | 箇所 | 変更内容 | 担当 |
|---|---|---|---|
| 7 | T064 stage_bc_evaluator (PR 配置時) | apply_spread_stress を NotImplementedError から T070 関数 import に置換、 命名 `TradeRecord` → `Trade` 統一 (Round 1 [W2]) | T064 / Phase 2 |
| 8 | T061 canonical_metrics (PR 配置時) | `BacktestResult.session_blocks` を入力に SR_session_worst / WR_worst を計算 | T061 / Phase 2 |
| 9 | T072 DST/holiday boundary | block_bucket_ranges への DST 例外、 holiday 時 block の特別扱い | T072 |
| 10 | run_ga.py / 既存 backtest_runner | `BacktestResult.session_blocks` の利用配線 (再計算禁止、 § 6.4 SSOT 遵守) | Phase 2 |
| 11 | run report 出力 / archive 経路 | `Trade.spread_cost` / `holding_cost` / `SessionBlock.pnl_before_costs` 等を log / report / archive に露出 (Round 1 [F17] 反映) | Phase 2 |
| 12 | T064 設計改訂 (任意) | `TradeRecord` 表記を `Trade` に統一 (Round 1 [W2] 反映、 命名一貫性) | T064 詳細設計改訂 |

## 10. 制約 / 非目標 (T070 範囲外)

| 項目 | 担当 |
|---|---|
| DST / holiday boundary contract | T072 (T914) |
| canonical 5 engine 計算 | T061 (T904) |
| stage_bc_evaluator 配線 | T064 (T907) で配線 (Phase 2) |
| primitives `_SESSION_RANGES_UTC` (9h 重複) | 既存、 T070 では touch しない (別責務) |
| cross-pair shadow 計算 | T064 で実装済 (5/5 cells) |

## 11. 削除対象 (Big-bang)

T070 では削除なし。 既存 Trade dataclass / engine.py / mock.py への破壊変更なし (= 純粋追加)。

## 12. テスト方針 (Phase 1、 Round 2 [W6] / Round 3 [W9] 反映で Phase 1 / Phase 2 境界を明確化)

### 12.1 Phase 1 unit test (T070 PR で必須)

- `tests/backtest/test_session_block.py` 新規:
  - F1, F3, F6, F7, F11, F12, F15, F18, F22 (= pure function 範囲): bucket 割当、 invariant、 docstring contract、 partition 重複、 covering、 v.s. primitives 9h、 spread 解釈 SSOT
  - happy path: 8h × 3 covering 確認、 trade exit_time での bucket 割当、 empty block 生成
- `tests/broker/test_orders.py` 拡張:
  - F23: Trade.spread_cost / Trade.holding_cost default=Decimal(0) test (= field 追加漏れ防止)
  - 既存 positional 構築 path が壊れていないことを確認
- `tests/broker/test_mock.py` 拡張:
  - F8: _close_one が spread_cost / holding_cost を Trade に転記 test
  - F13: invariant `Trade.pnl + Trade.holding_cost == raw_pnl` test
  - F19: 二重計上なし test (= 既存 cash 動きが Trade.holding_cost 追加で変わらない検証)
- `tests/backtest/test_engine.py` 拡張:
  - F4, F16: run_backtest 末尾で `BacktestResult.session_blocks` が同梱される test
  - block invariant (`pnl_before_costs == pnl_net + spread_cost_total + holding_cost_total`) test

### 12.2 Phase 2 integration test 申し送り

- F2 (UTC tz validation): bar_time が naive で aggregate_session_blocks 通過しないか integration で確認
- F5 (multiplier < 1 raise): apply_spread_stress 単体 unit でも書けるが Phase 2 caller (T064) で end-to-end
- F9 (positional 構築互換): 既存 caller への影響不在を Phase 2 で確認 (= grep で全 construction 箇所検証)
- F10 (廃止)
- F14, F21 (再計算禁止): Phase 2 で T061 / T064 配線時の lint / review check で防御
- F17, F20 (log/report 露出): Phase 2 で run_report / archive 配線時に同時実装

外部通信なし (= pure function + dataclass test 中心)。

## 13. 主要な設計判断サマリー (Round 1 反映後)

1. **8h × 3 covering partition**: synthesis § 4.4 厳密準拠、 既存 9h 重複 windows (primitives) とは別責務で並列管理
2. **trade exit_time で全 cost 一括帰属** (Round 1 [C1]): pnl / spread_cost / holding_cost を全て exit bucket に集計、 entry/exit 跨ぎ trade の混在配賦を回避
3. **empty block も生成 + is_empty_trade_block / is_partial_bar_block property** (Round 1 [S1]): synthesis § 6.3 「trade=0 block は 0.5 neutral」 を後段で機械判定可能化
4. **Trade に spread_cost + holding_cost field 追加、 既存挙動整合 contract** (Round 2 [C5] / Round 4 [W12] 反映): `_close_one` で `holding_cost` は既存 `_holding_cost_by_position` 転記、 `spread_cost` は entry/exit spread を独立記録 (Trade.pnl 未反映)。 §3.4.0 SSOT 参照
5. **apply_spread_stress は T070 で正式実装** (T064 申し送り完了): `new_pnl = trade.pnl - trade.spread_cost * (multiplier - 1)` で代数的に正しい stress 計算 (= spread_cost が既存 pnl 未反映なので multiplier=1 で no-op)
6. **DST / holiday は T072 で contract 化**: T070 は UTC 単純基準で SSOT 固定
7. **BacktestResult.session_blocks 新設、 transport SSOT を engine 内に固定** (Round 1 [C3]): caller 再計算禁止、 holding_cost_per_bar 引数を削除
8. **date universe = bars touched UTC date set** (Round 1 [W1]): aggregate_session_blocks 内 SSOT、 holiday 拡張は T072
9. **business_date は UTC date**: synthesis 整合 + T072 で再校正検討
10. **bar 用 / trade 用の bucket 計算関数を分離** (Round 1 [S2]): compute_bucket_for_bar と compute_bucket_for_trade、 基準時刻の混乱を防止
11. **pnl_gross → pnl_before_costs に命名変更** (Round 1 [S3]): 分解方向 (cost を加え戻す) を明示、 invariant 設計を容易に
12. **命名統一: T064 TradeRecord → Trade** (Round 1 [W2]): cascade port 命名一貫性、 T064 詳細設計改訂を Phase 2 申し送り
13. **collider bias は本タスク内では未評価** (Round 1 [W3]): 集計層のため断定せず、 conditioning は後段 evaluator/audit で再評価
14. **Phase 2 caller 配線は T061 / T064 / T072 / run_ga / log/report 露出 + 命名統一の 6 経路**: Phase 2 で同時に進める
