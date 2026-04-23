# T019 MockBroker 非 JPY-quote 通貨ペア対応 — 詳細設計

概念設計 `conceptual-design.md` に対する実装レベル詳細。

## 1. 変更ファイル一覧

| ファイル | 変更種別 | 行数目安 |
|---|---|---|
| `src/broker/mock.py` | 変更 | +20 / -5 |
| `src/broker/margin.py` | 変更（docstring + メッセージのみ） | +5 / -3 |
| `tests/broker/test_mock_multi_currency.py` | 新規 | +220 |
| `tests/_helpers.py` | 変更（多通貨 meta ヘルパ追加） | +35 |
| `tests/alpha_factory/test_cross_pair.py` | 追加 test（non-JPY anchor の実 backtest shadow）| +60 |
| `docs/alpha_factory/cross-pair.md` | 構造的制約節の更新 | +/- 10 |
| `docs/alpha_factory/terminology.md` | `pip_size` / `display_precision` 用語追加 | +15 |

新規 `src/alpha_factory/cross_pair.py` や `backtest/engine.py` への改修は**行わない**。

## 2. `InstrumentMeta` 拡張

```python
# src/broker/mock.py
@dataclass(frozen=True)
class InstrumentMeta:
    """MockBroker が個別銘柄について把握しておくべき最小情報。

    SSOT 境界:
        * `src/domain/instrument.py::CurrencyPair` は ingest / oanda 層 SSOT で、
          pip_location / minimum_trade_size / maximum_order_units を含む
          full pair catalog を保持する。
        * `InstrumentMeta` は broker / backtest 層 SSOT で、P&L 計算・margin 検証に
          最低限必要な情報のみを保持する。pip_size / display_precision は
          テスト・ログ・将来の slippage モデルでの利用を見越して**派生情報として
          保持**する（CurrencyPair.pip_size / CurrencyPair.display_precision からコピー可能）。

    Phase 4 note:
        * 本 Phase では home=quote を前提に動作する。Phase 4 で
          `home != quote` をサポートする際は、MockBroker 側で
          `fx_rate_provider` (新規引数) を受け取り quote→home 換算を実行する設計。
    """

    oanda_name: str
    base_currency: str
    quote_currency: str
    margin_rate: Decimal
    # 以下は後方互換のため default 付き追加（from_quote_currency で正しい値を自動設定する推奨経路）
    pip_size: Decimal = Decimal("0.0001")
    display_precision: int = 5

    def __post_init__(self) -> None:
        if self.pip_size <= 0:
            raise ValueError(f"pip_size must be > 0: {self.pip_size}")
        if self.display_precision < 0:
            raise ValueError(f"display_precision must be >= 0: {self.display_precision}")

    @staticmethod
    def default_pip_size_for_quote(quote_currency: str) -> Decimal:
        """quote currency から pip_size を自動決定する。

        JPY-quote は 0.01、その他（USD / CAD / CHF など）は 0.0001（OANDA 仕様）。
        """
        return Decimal("0.01") if quote_currency.upper() == "JPY" else Decimal("0.0001")

    @staticmethod
    def default_display_precision_for_quote(quote_currency: str) -> int:
        """quote currency から display_precision を自動決定する。

        JPY-quote は 3 桁、その他は 5 桁（OANDA 仕様）。
        """
        return 3 if quote_currency.upper() == "JPY" else 5
```

**デフォルト値の根拠とリスク**:

- dataclass のフィールド default は **USD-quote pair (EUR_USD 等) の標準値** (0.0001 / 5)。これは「全 FX ペアの最頻値」という静的一点を選んだもの。
- **JPY-quote pair (USD_JPY 等) で `pip_size` / `display_precision` が未指定** だと間違った default が設定されるリスクあり → **本 TODO 範囲で全 `InstrumentMeta(...)` 直接生成箇所を棚卸し、明示指定または factory 経路に統一する** （§4 参照、棚卸し対象は §3.1 で enumerate）。
- 将来の factory 経路誘導のため `default_pip_size_for_quote(quote_currency)` / `default_display_precision_for_quote(quote_currency)` 静的ヘルパを追加。呼び出し側は `pip_size=InstrumentMeta.default_pip_size_for_quote(pair.quote_currency)` で自動決定できる。

### 2.1 frozen dataclass で `__post_init__` を使う注意点

`@dataclass(frozen=True)` で `__post_init__` は許可されるが、属性への再代入は不可。上記は validate のみで値変更していないので問題なし。

## 3. `MockBroker.__init__` 変更

```python
# src/broker/mock.py
class MockBroker:
    def __init__(
        self,
        instrument_meta: InstrumentMeta,
        *,  # ← keyword-only: 位置引数による誤用を防ぐ
        home_currency: str | None = None,  # None → meta.quote_currency を採用（per-pair home モード）
        maintenance_margin_level_pct: Decimal = Decimal("100"),
    ) -> None:
        resolved_home = (
            home_currency if home_currency is not None
            else instrument_meta.quote_currency
        )

        # Phase 4 契約予約: home != quote かつ fx_rate_provider 未導入 → fail-fast
        if instrument_meta.quote_currency != resolved_home:
            raise NotImplementedError(
                f"MockBroker phase 2 requires quote==home. "
                f"got quote={instrument_meta.quote_currency}, home={resolved_home}. "
                "Phase 4 will introduce fx_rate_provider for quote→home conversion."
            )
        self._meta = instrument_meta
        self._home = resolved_home
        # 以降は現状どおり
```

**keyword-only 化の根拠**: Round 1 Codex review 推奨修正。位置引数 `MockBroker(meta, "JPY")` を封じ、明示的な `home_currency="JPY"` を強制する。既存呼び出し（§3.1 で棚卸し済）は全て引数無指定 (`MockBroker(instrument_meta=meta)`) なので影響なし。

### 3.1 既存 `MockBroker(` 呼び出し箇所（grep 結果・全網羅）

`rg 'MockBroker\(' src/ scripts/ tests/ --type py` 実測（20 箇所、本 TODO 影響なし全て引数無指定）:

- `src/backtest/walk_forward.py:112` — `MockBroker(instrument_meta=meta)` ✓
- `src/backtest/ensemble.py:107` — `MockBroker(instrument_meta=meta)` ✓
- `src/backtest/grid_search.py:57` — `MockBroker(instrument_meta=meta)` ✓
- `src/ga/fitness.py:64` — `MockBroker(instrument_meta=meta)` ✓
- `scripts/paper_trade.py:94` — `MockBroker(instrument_meta=meta)` ✓
- `src/alpha_factory/cross_pair.py:142` — `MockBroker(instrument_meta=meta)` ✓
- `src/alpha_factory/stage_gate.py:277,387,407,516,581` — `MockBroker(instrument_meta=meta)` ✓（5 件）
- `scripts/backtest_run.py:92` — `MockBroker(instrument_meta=meta)` ✓
- `tests/paper_trading/test_orchestrator.py:41,71,96` — `MockBroker(instrument_meta=usd_jpy_meta())` ✓（3 件）
- `tests/backtest/test_engine_clause.py:150-446` — `MockBroker(instrument_meta=usd_jpy_meta())` ✓（12 件）
- `tests/backtest/test_engine.py:35,60,85` — `MockBroker(instrument_meta=usd_jpy_meta())` ✓
- `tests/broker/test_mock_broker.py:13` — `MockBroker(instrument_meta=usd_jpy_meta(), maintenance_margin_level_pct=Decimal("100"))` ✓（既存 kwargs）

**結論**: 全 20 箇所で `home_currency` は明示指定なし → T019 の per-pair home default で挙動不変。`keyword-only` 化も既存コードを壊さない。

### 3.2 既存 `InstrumentMeta(` 呼び出し箇所（grep 結果・全網羅）

`rg 'InstrumentMeta\(' src/ scripts/ tests/ --type py` 実測（本 TODO の transcription-leak リスクあり、pip_size/display_precision 伝搬が必要）:

| ファイル・行 | quote_currency | pip_size / precision の扱い |
|---|---|---|
| `tests/_helpers.py:13` | JPY 固定（usd_jpy_meta） | **明示指定必須** (pip_size=0.01, display_precision=3) |
| `tests/alpha_factory/test_cross_pair.py:74` | JPY 固定捏造 (`_dummy_meta`) | **明示指定必須** (pip_size=0.01, display_precision=3) |
| `tests/alpha_factory/test_cross_pair.py:777` | JPY 固定 (`_make_stage_c_inputs`) | **明示指定必須** (pip_size=0.01, display_precision=3) |
| `tests/alpha_factory/test_swim_lane.py:83` | JPY 固定 (`_stub_meta`) | **明示指定必須** (pip_size=0.01, display_precision=3) |
| `scripts/ga_run.py:77` | `pair.quote_currency` (DB 値) | **factory 経路**: `pip_size=InstrumentMeta.default_pip_size_for_quote(pair.quote_currency)` |
| `scripts/alpha_factory/run_ga.py:231` (`_meta_from_pair`) | `pair.quote_currency` | 同上 |
| `scripts/walk_forward.py:97` | `pair.quote_currency` | 同上 |
| `scripts/grid_search.py:94` | `pair.quote_currency` | 同上 |
| `scripts/ensemble.py:103` | `pair.quote_currency` | 同上 |
| `scripts/backtest_run.py:86` | `pair.quote_currency` | 同上 |
| `scripts/paper_trade.py:64` | `pair.quote_currency` | 同上 |

**転記漏れ防止策**:
- `_helpers.py` のヘルパ 4 種 (`usd_jpy_meta` / `eur_jpy_meta` / `eur_usd_meta` / `usd_cad_meta`) で明示指定。
- `_dummy_meta` / `_make_stage_c_inputs` / `_stub_meta` は test-only、JPY 固定なので静的に `pip_size=Decimal("0.01"), display_precision=3` を書き込む。
- scripts/ 7 箇所はすべて `CurrencyPair` からの factory pattern。`InstrumentMeta.default_pip_size_for_quote(pair.quote_currency)` + `InstrumentMeta.default_display_precision_for_quote(pair.quote_currency)` で自動派生に揃える（本 TODO で 1 回刻みで書き換え）。
- 上記を完遂しないと JPY-quote 本番 backtest で pip_size=0.0001 が**沈黙して**乗る → ログ / 将来 slippage で数値バグを招く（zenigame の転記漏れパターン 1・3 そのもの）。

## 4. `tests/_helpers.py` 更新（多通貨 meta ヘルパ）

```python
def usd_jpy_meta(margin_rate: str = "0.04") -> InstrumentMeta:
    return InstrumentMeta(
        oanda_name="USD_JPY",
        base_currency="USD",
        quote_currency="JPY",
        margin_rate=Decimal(margin_rate),
        pip_size=Decimal("0.01"),       # 新規（明示）
        display_precision=3,             # 新規（明示）
    )


def eur_jpy_meta(margin_rate: str = "0.04") -> InstrumentMeta:
    return InstrumentMeta(
        oanda_name="EUR_JPY",
        base_currency="EUR",
        quote_currency="JPY",
        margin_rate=Decimal(margin_rate),
        pip_size=Decimal("0.01"),
        display_precision=3,
    )


def eur_usd_meta(margin_rate: str = "0.03") -> InstrumentMeta:
    return InstrumentMeta(
        oanda_name="EUR_USD",
        base_currency="EUR",
        quote_currency="USD",
        margin_rate=Decimal(margin_rate),
        pip_size=Decimal("0.0001"),
        display_precision=5,
    )


def usd_cad_meta(margin_rate: str = "0.04") -> InstrumentMeta:
    return InstrumentMeta(
        oanda_name="USD_CAD",
        base_currency="USD",
        quote_currency="CAD",
        margin_rate=Decimal(margin_rate),
        pip_size=Decimal("0.0001"),
        display_precision=5,
    )
```

`make_bar` は既に `pair_name` 引数を受け取るので USD_JPY 以外にも使い回せる。変更不要。

## 5. `notional_home_currency` docstring 改訂

```python
# src/broker/margin.py
def notional_home_currency(units: int, price_quote_per_base: Decimal, quote_is_home: bool) -> Decimal:
    """home currency 建ての想定元本を返す。

    Phase 2 (T019 時点): broker の per-pair home モード下では常に quote_is_home=True が
    期待値。`home != quote` を真に扱う quote→home 換算は Phase 4 で
    `fx_rate_provider` 引数（別 TODO、MockBroker 側に追加予定）として導入予定。
    """
    if not quote_is_home:
        raise NotImplementedError(
            "quote != home currency requires fx_rate_provider (Phase 4)"
        )
    return Decimal(abs(units)) * price_quote_per_base
```

関数シグネチャ / 計算式は変更せず、docstring + エラー文言のみ改訂。**命名統一**: `fx_rate_provider` に一本化（conceptual-design §8 / mock.py エラーメッセージ / margin.py エラーメッセージの全箇所）。

## 6. 新規テスト `tests/broker/test_mock_multi_currency.py`

### 6.1 テストケース一覧

1. `test_eur_usd_long_close_pnl_sign` — EUR_USD long → 価格上昇 → P&L > 0
2. `test_eur_usd_short_close_pnl_sign` — EUR_USD short → 価格下降 → P&L > 0
3. `test_usd_cad_roundtrip` — USD_CAD long + close、cash 増減が想定どおり
4. `test_explicit_home_currency_jpy_keeps_usd_jpy` — `MockBroker(usd_jpy_meta(), home_currency="JPY")` で旧挙動が保たれる
5. `test_explicit_home_currency_matches_quote_for_eur_usd` — `MockBroker(eur_usd_meta(), home_currency="USD")` も受理される
6. `test_mismatched_home_quote_raises_not_implemented` — `MockBroker(eur_usd_meta(), home_currency="JPY")` で `NotImplementedError` / メッセージに "Phase 4" / "fx_rate_provider" が含まれる
7. `test_pip_size_default_and_custom` — default (0.0001/5) と明示指定 (0.01/3) が両方通る、0 / 負値は ValueError
8. `test_scale_invariance_initial_cash_usd_jpy` — 同価格系列で initial_cash=1_000_000 と 10_000_000 で Sharpe 差 < 1e-6（margin 非拘束条件、margin_call が発生しないこと）
9. `test_scale_invariance_initial_cash_eur_usd` — 同じく EUR_USD で
10. `test_scale_invariance_units_usd_jpy` — 同価格系列で units=10_000 と 100_000 で Sharpe 差 < 1e-6
11. `test_scale_invariance_units_eur_usd` — 同じく EUR_USD で
12. `test_cross_pair_multi_currency_shadow_no_pair_failure` — cross_pair.evaluate_cross_pair で target=EUR_JPY + anchors (EUR_USD, USD_JPY) を実 backtest 経由で走らせ、`reason_codes` に `pair_failure:…NotImplementedError` が含まれないこと

### 6.2 Scale 不変性の正しい定式化（Round 1 review 反映）

**重要な訂正**: 「`initial_cash` のみ変更」で `equity returns` が同一になるわけではない。`equity_curve[t] = cash + unrealized_pnl(t)` で、cash は定数 C、unrealized は units と price 差に依存し C に依らない。したがって `equity[t] = C + f(units, price)` となり、returns `(equity[t] - equity[t-1]) / equity[t-1] = Δf / (C + f(t-1))` は `C` に**依存する**。

正しい scale 不変性検証は次の 2 アプローチのどちらか:

#### (S1) trade-based Sharpe 比較（推奨）

`compute_metrics(trades, equity_curve).sharpe` は `src/backtest/metrics.py` 実装を読んで確定させる。現実装は **trades の pnl 系列** から Sharpe を計算する想定（概念: trade-level returns）。これは `initial_cash` 非依存だが `units` にはスケールする（pnl が比例）。

- scale ケース A: `initial_cash=1_000_000`, `units=10_000`
- scale ケース B: `initial_cash=1_000_000`, `units=10_000`（同一）

は当然一致。ここで検証したいのは「**home 通貨の数値スケール変更**」であるため、次の (S2) がより適切。

#### (S2) initial_cash と units を同倍率で同時スケール

home 通貨の実質的な「スケール変更」は、initial_cash と units の両方を k 倍すること（= 口座が 10 倍大きく、注文 volume も 10 倍）。

- ケース A: `initial_cash=C`, `units=U`
- ケース B: `initial_cash=k*C`, `units=k*U`（k=10）

このとき `equity_curve` は全時点で k 倍、trade-level pnl も k 倍。**returns ratio (pnl/initial_cash)** と **Sharpe (無次元)** は不変になる。

テスト実装（疑似）:

```python
def _run_scaled(meta, units_scale: int, cash_scale: int):
    broker = MockBroker(instrument_meta=meta)
    broker.deposit(Decimal(1_000_000 * cash_scale))
    # 数本の price bars で open → close → open → close を hand-craft
    # open_long units=10_000 * units_scale
    # 1 bar 後 close_position
    # 3-5 回 trade 発生させる
    trades = [...]
    equity = [...]
    return compute_metrics(trades, equity).sharpe

sharpe_1 = _run_scaled(eur_usd_meta(), units_scale=1, cash_scale=1)
sharpe_10 = _run_scaled(eur_usd_meta(), units_scale=10, cash_scale=10)
assert abs(sharpe_1 - sharpe_10) < 1e-6
```

#### (S3) 補助: equity returns 比較（同時 scale ケースで）

同時 scale (S2) のケースで equity curve の returns 系列が**一致**することを別 test で assert。これは Sharpe が返らない extreme ケース（trade 0 件）でも実装の linear scaling 性を確認できる。

#### テスト数の整理

テストケース番号 8-11 を以下に置き換え:

- **8**. `test_scale_invariance_sharpe_usd_jpy` — USD_JPY で (S2): `initial_cash × units` を 10 倍スケール、Sharpe diff < 1e-6（margin_call が発生しないことを assert 追加）
- **9**. `test_scale_invariance_sharpe_eur_usd` — 同じく EUR_USD で
- **10**. `test_scale_invariance_equity_returns_usd_jpy` — 同じく USD_JPY で (S3): equity returns 系列一致（要素ごと rel_tol=1e-9）
- **11**. `test_scale_invariance_equity_returns_eur_usd` — 同じく EUR_USD で

**margin 非拘束条件の明示確認**: 各 test で `assert all(t.exit_reason != "margin_call" for t in trades)` を入れ、margin 制約の副作用で差分が出ていないことを保証する（Round 1 推奨修正 #1）。

### 6.3 Cross-pair shadow no pair_failure test

```python
def test_cross_pair_multi_currency_shadow_no_pair_failure(...):
    bars_map = {
        "EUR_JPY": make_bars_monotonic("EUR_JPY", ..., pair_name="EUR_JPY"),
        "EUR_USD": make_bars_monotonic("EUR_USD", ..., pair_name="EUR_USD"),
        "USD_JPY": make_bars_monotonic("USD_JPY", ..., pair_name="USD_JPY"),
    }
    meta_map = {"EUR_JPY": eur_jpy_meta(), "EUR_USD": eur_usd_meta(), "USD_JPY": usd_jpy_meta()}

    result = evaluate_cross_pair(
        genome=_simple_genome(),
        target="EUR_JPY",
        pair_bars=bars_map,
        pair_meta=meta_map,
        backtest_config=_minimal_config("EUR_JPY"),
        primitive_evaluator=ConstantPrimitiveEvaluator(),
        cross_pair_config=CrossPairConfig(),
    )

    failures = [rc for rc in result.reason_codes if "NotImplementedError" in rc]
    assert failures == []
    # 意味ある Sharpe: 3 pair とも finite (None でも OK だが trade 発生なら nonzero)
    for pair, sh in result.metrics["sharpe_per_pair"].items():
        assert math.isfinite(sh)
```

bars は単純な上昇系列で、`ConstantPrimitiveEvaluator` (既存、`tests/dsl/conftest.py`) が signal>threshold を常に生むので trade が発生。

## 7. 既存テスト影響調査（事前実施済）

`rg 'MockBroker\(' src/ scripts/ tests/ --type py` と `rg 'InstrumentMeta\(' src/ scripts/ tests/ --type py` を実施し、§3.1 / §3.2 に全結果を記載した。**全箇所 home_currency 明示指定なし** → keyword-only 化 + default=None 導入でも破壊的変更なし。

追加で grep すべきパターン:
- `rg 'home_currency\s*=' src/ scripts/ tests/ --type py` → 本 TODO 設計ドキュメント以外ヒットなし（T019 前）

**`tests/alpha_factory/test_cross_pair.py::_dummy_meta`**: 現状 quote_currency="JPY" 固定。pip_size/display_precision 明示指定に更新する必要あり（§3.2 記載）。

**`tests/alpha_factory/test_swim_lane.py::_stub_meta`**: 同上、quote_currency="JPY" 固定、pip_size 明示指定に更新。

**`tests/alpha_factory/test_cross_pair.py::_make_stage_c_inputs` (line 777)**: USD_JPY で quote="JPY"、明示指定追加。

**scripts/** 7 箇所（`ga_run.py`, `run_ga.py`, `walk_forward.py`, `grid_search.py`, `ensemble.py`, `backtest_run.py`, `paper_trade.py`）: 全て `CurrencyPair` からの factory pattern。`InstrumentMeta.default_pip_size_for_quote(pair.quote_currency)` + `InstrumentMeta.default_display_precision_for_quote(pair.quote_currency)` の自動派生で統一する（本 TODO で一括書き換え）。

## 8. docs 更新

### `docs/alpha_factory/cross-pair.md`

「Phase 2 構造的制約」節を以下に更新（解消範囲を限定表現で明記）:

```
**Phase 2 構造的制約 — 非 JPY-quote の backtest 完走制約は T019 で解消**:
旧実装では `MockBroker` が `quote != JPY` (home=JPY 固定) で
`NotImplementedError` を raise していたため、ANCHOR_PAIRS 定義 6 target すべてで
少なくとも 1 つの非 JPY-quote anchor が含まれる現状、実 backtest 経由で意味ある
shadow 統計が取れなかった。T019 で MockBroker に **per-pair home モード** を
導入 (default: `home_currency=meta.quote_currency`) し、非 JPY-quote ペアでも
backtest が完走するようになった。これにより cross-pair shadow は全 6 target で
意味ある `mean_sharpe / std_sharpe / pair_failure` 統計を archive に残せる。

**T019 で解消した範囲（限定）**:
- 非 JPY-quote ペア (EUR_USD / USD_CAD 等) の backtest 完走制約
- cross-pair shadow の構造的 pair_failure:NotImplementedError

**T019 で解消されない範囲（Phase 4 TODO）**:
- `home != quote` (例: JPY 口座で EUR_USD を JPY 建てで評価) の quote→home 換算
- 複数通貨建て cash の統合会計（graduation lane マルチ pair 統合口座など）

Sharpe 集約の解釈: **per-pair home Sharpe 集約** であり、各 pair は独自の
home currency (= quote currency) 建ての equity curve で評価される。Sharpe は
無次元 (return mean / return std) で scale 不変性が保証されるため
(T019 test が直接検証: initial_cash × units 同時 10 倍スケールで Sharpe 不変)、
pair 間で home 通貨が異なっても集約は統計的に健全。

Phase 4 の真の quote→home 換算 (例: JPY 口座で EUR_USD を JPY 建てで評価) が
必要になった場合は、MockBroker に `fx_rate_provider` 引数を追加する設計を予約済
(devnotes/20260424-0517-mock-broker-multi-currency/conceptual-design.md §8)。
```

### `docs/alpha_factory/terminology.md`

`### pip_size` と `### display_precision` を追加:

```
### pip_size
`<a id="pip-size"></a>` pip_size — `InstrumentMeta.pip_size: Decimal` (T019 追加)。
通貨ペアの 1 pip 単位。JPY-quote は 0.01、USD-quote (EUR_USD 等) は 0.0001、
USD_ZAR 等も 0.0001 (OANDA 仕様)。slippage モデル・spread ログの pip 換算に利用。
CurrencyPair (src/domain/instrument.py) の pip_size と派生的に揃うが、
broker 層 SSOT として InstrumentMeta に独立保持する。

### display_precision
`<a id="display-precision"></a>` display_precision — `InstrumentMeta.display_precision: int`
(T019 追加)。価格表示の小数点以下桁数。JPY-quote は 3、USD-quote は 5。ログ表示・
デバッグ用途のみで P&L 計算には影響しない。
```

### `docs/alpha_factory/cross-pair.md` の関連 TODO セクションの更新

`MockBroker 非 JPY-quote 対応` を「実装済 T019」に移動。

## 9. 実装順序

1. `src/broker/mock.py` - `InstrumentMeta` に `pip_size`/`display_precision` + `__post_init__` validation + `default_pip_size_for_quote` / `default_display_precision_for_quote` 静的ヘルパ追加
2. `src/broker/mock.py` - `MockBroker.__init__` を keyword-only 化 + `home_currency: str | None = None` + resolve ロジック + エラーメッセージ更新
3. `src/broker/margin.py` - docstring + エラーメッセージ更新（`fx_rate_provider` 命名統一）
4. `tests/_helpers.py` - `usd_jpy_meta` / `eur_jpy_meta` / `eur_usd_meta` / `usd_cad_meta` 明示 pip_size/precision
5. `tests/alpha_factory/test_cross_pair.py` - `_dummy_meta` / `_make_stage_c_inputs` に pip_size/precision 明示追加（JPY 固定: 0.01/3）
6. `tests/alpha_factory/test_swim_lane.py` - `_stub_meta` に pip_size/precision 明示追加（JPY 固定: 0.01/3）
7. scripts/ 7 箇所 (`ga_run.py`, `alpha_factory/run_ga.py`, `walk_forward.py`, `grid_search.py`, `ensemble.py`, `backtest_run.py`, `paper_trade.py`) の `InstrumentMeta(...)` に `pip_size=InstrumentMeta.default_pip_size_for_quote(pair.quote_currency)` と `display_precision=InstrumentMeta.default_display_precision_for_quote(pair.quote_currency)` を追加
8. `tests/broker/test_mock_multi_currency.py` - 新規テスト 12 件（§6.1 対応、scale invariance は §6.2 に従った S2+S3 形式）
9. `tests/alpha_factory/test_cross_pair.py` - 新規 multi-currency shadow test (§6.3)
10. `pytest tests/broker/ tests/alpha_factory/test_cross_pair.py -v` で確認
11. `pytest tests/ -v` で 798+ passed 維持確認
12. `mypy src/broker/` / `ruff check src/broker/ tests/broker/ tests/alpha_factory/` clean
13. docs 更新（cross-pair.md / terminology.md）
14. `rg -n 'MockBroker\(|InstrumentMeta\(|home_currency\s*=' src/ scripts/ tests/ --type py` で最終確認

## 10. 受け入れ基準 check-list（実装時 verify）

- [ ] 既存 798 passed 維持
- [ ] EUR_USD / USD_CAD backtest 完走
- [ ] Scale 不変性 4 test (initial_cash × 2pair + units × 2pair) assert 通過
- [ ] cross-pair shadow で pair_failure:NotImplementedError が消えた
- [ ] mypy / ruff clean
- [ ] docs 更新（cross-pair.md / terminology.md / conceptual & detailed design）
- [ ] コミットメッセージ: `feat(broker): T019 MockBroker non-JPY-quote support`

## 11. リスク最終確認

| リスク | 対策 |
|---|---|
| 既存 `MockBroker(meta, home_currency="JPY")` explicit 呼び出しが壊れる | `resolved_home == meta.quote_currency=="JPY"` で通過。実装時に `rg MockBroker\(` で grep 確認 |
| `InstrumentMeta` に default 付き field を追加したので frozen dataclass の `__post_init__` validation が既存 pickled 等に影響 | 現状 pickle 使用箇所なし（dataclass 直接インスタンス化のみ）。問題なし。 |
| 新規 test が slow (backtest × N 回) | `pytest tests/broker/test_mock_multi_currency.py` 単体で秒オーダー想定（短 bars 使用）。問題なし |

---

以上。
