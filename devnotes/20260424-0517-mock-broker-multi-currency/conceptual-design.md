# T019 MockBroker 非 JPY-quote 通貨ペア対応 — 概念設計

## 1. 背景と現在地

T016 (cross-pair shadow) 実装時、`MockBroker` は `InstrumentMeta.quote_currency != home_currency` （= home は JPY 固定）で `NotImplementedError` を raise する制約を持っていた。この制約により、以下のアンカーマッピング（T016 SSOT: `src/alpha_factory/cross_pair.py::ANCHOR_PAIRS`）では全 6 target で少なくとも 1 つの非 JPY-quote pair が必ず含まれ、実 backtest 経由の cross-pair shadow 評価が**構造的に** `pair_failure:…:NotImplementedError` となる。

| target | anchors | 非 JPY-quote を含むか |
|---|---|---|
| EUR_JPY | EUR_USD, USD_JPY | ○ |
| USD_JPY | USD_CAD, EUR_JPY | ○ |
| EUR_USD | EUR_JPY, USD_CAD | ○ |
| AUD_JPY | USD_JPY, EUR_USD | ○ |
| USD_CAD | USD_JPY, EUR_USD | ○ |
| USD_ZAR | USD_CAD, USD_JPY | ○ |

T016 の unit test は monkeypatch で `_run_pair_sharpe` を差し替え集約ロジックを検証しており、実 backtest 経由の意味ある shadow 統計は本 TODO (T019) 依存となっていた。

## 2. 目的

- **MockBroker を非 JPY-quote 通貨ペアでも動作させる** ことで、cross-pair shadow が全ペアで構造的 `pair_failure` を起こさず意味のある統計を返せる状態にする。
- **backtest engine 本体には触れない**。broker 側の抽象化だけで吸収する（スコープ最小化、regression 最小化）。
- **既存 USD_JPY / EUR_JPY テスト（798 passed baseline）を壊さない**。

## 3. スコープ

### In scope
- `src/broker/mock.py::MockBroker` の generalisation
- `src/broker/margin.py::notional_home_currency` の挙動拡張
- `InstrumentMeta` の最小拡張（pip_size / display_precision 等）
- 新規テスト `tests/broker/test_mock_multi_currency.py`
- docs: `docs/alpha_factory/cross-pair.md` の構造的制約節更新、`terminology.md` の pip 系追記

### Out of scope
- 実際の quote→home 通貨換算レート接続（例: EUR_USD を JPY home で評価する際の USDJPY レート注入）
  - 理由: (i) 換算レート時系列 ingest は別系統のデータ整備を要し、スコープが膨らむ。
  - (ii) cross-pair shadow は「各 pair 単独 backtest の Sharpe を集約する」構造であり、**home currency を `quote_currency` と一致させる解釈** （= pair ごとに暗黙の home を切り替える）で Sharpe は健全に計算できる。Sharpe は return / vol の無次元量であり home 換算の共通スケール不要。
  - (iii) swim-lane / run-ga 側で graduation lane がマルチ pair 評価する際も本 TODO の範疇では pair 単体評価のみを扱う。マルチ通貨統合会計は別 TODO。
- `backtest/engine.py` の改修（本 TODO では触らない）
- `DslStrategy` / `RegistryEvaluator` の改修（pair-specific primitive の real shadow stats は別 TODO）
- swap 精密再現（日付境界・水曜 3 倍・side 別）

## 4. アプローチの基本方針

### 方針 A: "per-pair home" 解釈（採用）

MockBroker は「その pair の quote currency を暗黙の home とみなす」モードを持つ。つまり:

- USD_JPY: quote=JPY → home=JPY、cash は JPY 建て（既存どおり）
- EUR_USD: quote=USD → home=USD、cash は USD 建て（新規、同 broker instance 内で完結）
- USD_CAD: quote=CAD → home=CAD、cash は CAD 建て

**重要なのは、broker インスタンスは 1 つの instrument を扱う single-instrument orientation** であり、T009 / T016 すべてこの前提 (`bar.pair_name != self._meta.oanda_name` で raise) で動作している。したがって quote==home を pair ごとに再宣言すれば OK。

MockBroker コンストラクタを以下のいずれかにする:

- **(A1)** `home_currency` 引数の default を現状 `"JPY"` 固定から `None` にし、`None` なら `meta.quote_currency` を採用（自動 per-pair home）。明示的に指定されれば従来挙動。
- **(A2)** `home_currency` 引数を削除し、常に `meta.quote_currency` を home とみなす。

**(A1) を採用**。既存の呼び出し側 (`usd_jpy_meta()` + デフォルト) は挙動不変、cross_pair.py / swim_lane.py は引数無指定で呼ぶので自動的に pair の quote を home に合わせる。既存テストに壊れがない。

### 方針 B: `notional_home_currency` の扱い

現状 `quote_is_home=True` を前提に `|units| * price` を返しているため、broker 側で `quote_is_home=True` を **一貫して渡す** 限り、関数自体は不変でよい。ただし `quote != home` の NotImplemented メッセージが誤解を招く（phase 4 で真の quote→home 換算が必要になる）ため、docstring を整理し **「per-pair home 解釈下では常に quote_is_home=True が期待値」** を明記する。

### 方針 C: pip_size / display_precision の追加

本 TODO の第一目的 (cross-pair を動かす) のために pip_size は**必須ではない**。Sharpe は return ratio なので pip / precision に依存しない。しかし以下 2 つの理由で `InstrumentMeta` に追加する:

1. **将来の spread bps / holding cost 按分で "pip" 粒度を取り出す場面がある**（T009 holding cost は notional ベースで bps なので pip 非依存だが、テスト / ログ / 将来の slippage モデルで pip 情報があると便利）。
2. 用語集 `terminology.md` / pair metadata SSOT として一箇所にまとめることで、別所で各自実装される散逸を防ぐ。

- `pip_size: Decimal` — USD_JPY 等 JPY-quote = 0.01 / EUR_USD 等 USD-quote = 0.0001 / USD_ZAR = 0.0001 (OANDA 仕様)
- `display_precision: int` — JPY-quote = 3 (0.001 粒度) / USD-quote = 5 (0.00001 粒度)（OANDA instrument meta より）
- ただし**デフォルト値**を持たせ、既存の `InstrumentMeta(...)` 呼び出しが壊れないようにする（後方互換性）。

補助: `CurrencyPair` には既に `pip_location` / `pip_size` / `display_precision` が存在する。`InstrumentMeta` にも派生的に揃えることで SSOT を 2 箇所化しない（`CurrencyPair` は ingest / oanda 層、`InstrumentMeta` は broker / backtest 層）。 将来的には両者の統合も視野に入るが、本 TODO ではスコープ外。

### 方針 D: P&L 計算

既存 `_realized_pnl`:

```
long:  units * (exit - entry)
short: units * (entry - exit)
```

これは **quote currency 建ての P&L** を返している。per-pair home では home==quote なので、この値が直接 cash 増減になる。したがって**計算式変更は不要**。broker-level の `cash`, `equity`, `margin` 全てが「その broker の home=quote currency」建てで閉じる。

### 方針 E: Margin / leverage

`margin_rate` は OANDA 業者の最低マージン率で、通貨ペアごとに異なる。`InstrumentMeta.margin_rate` で既に pair 単位に保持されているので、本 TODO では変更しない（validation logic は共通）。

### 方針 F: cross_pair.py 側の対応

現状 cross_pair.py は `MockBroker(instrument_meta=meta)` を生成。`meta.quote_currency` が home に自動設定される（方針 A1）ので、**cross_pair.py 側の改修は不要**。ただしテスト側で `_dummy_meta` が全 pair quote=JPY を捏造していた部分を reality に合わせ直す余地あり（本 TODO 範囲では触らず、実 backtest pass を追加 test で担保）。

## 5. 整合性チェックポイント

| 項目 | 現状 | T019 後 |
|---|---|---|
| USD_JPY broker 挙動 | quote=JPY, home=JPY, cash=JPY | quote=JPY, home=JPY（自動）, cash=JPY（変化なし） |
| EUR_JPY broker 挙動 | quote=JPY, home=JPY, cash=JPY | quote=JPY, home=JPY（自動）, cash=JPY（変化なし） |
| EUR_USD broker 挙動 | NotImplementedError | quote=USD, home=USD, cash=USD（新規対応） |
| USD_CAD broker 挙動 | NotImplementedError | quote=CAD, home=CAD, cash=CAD（新規対応） |
| cross_pair shadow (target=EUR_JPY) | 1/3 pair_failure (EUR_USD) | 0 pair_failure、意味ある mean/std Sharpe |
| 798 passed baseline | 維持 | 維持 or 増加（new tests） |

## 6. リスクと対策

### R1: 既存テストの暗黙的な home=JPY 前提が壊れる
- 対策: `home_currency` 引数のデフォルトを `None` にして内部で `meta.quote_currency` を採用するが、明示値（例: `home_currency="JPY"`）を渡した場合は現状の挙動にフォールバック。`test_mock_broker.py` 既存ケースは `usd_jpy_meta()` で quote=JPY のため引数無指定でも結果不変。

### R2: cross_pair shadow の Sharpe 集約が pair 間で home が違うことで歪む
- 対策: Sharpe は無次元 (return mean / return std)。pair 間の home 通貨が異なっても Sharpe の大小比較は意味論的に有効 (各 pair 内で自己完結)。`mean(Sharpe) - λ×std(Sharpe)` も Sharpe 同士の集約なので OK。ただし docstring / cross-pair.md に「per-pair home Sharpe 集約である」ことを明記する。

### R3: `cross_pair.py::_dummy_meta` が quote=JPY 捏造で動いていたテストが (i) home=JPY が自動で meta.quote_currency=JPY になり依然動く、(ii) 実際の anchor pair に沿った meta を渡す新 test が動くべき
- 対策: 既存 `_dummy_meta` は quote_currency="JPY" 固定で tests が動く。新しい multi-currency test のみリアルな quote を使う。

### R4: 将来 Phase 4 で quote→home 換算が必要になった場合の interface 退行
- 対策: `home_currency` 引数は残す（現状 None default で per-pair、指定時は従来挙動）。将来 `home_currency != meta.quote_currency` を **真の換算で** サポートする道は残してある。docstring に "Phase 4 will enable cross-quote conversion" を記載。

### R5: notional_home_currency のメッセージ混乱
- 対策: docstring を改訂、「per-pair home を採用する呼び出し側では `quote_is_home=True` 一択」と明示。旧 NotImplementedError メッセージから "Phase 4" を "future cross-quote conversion" に書き換え。

## 7. per-pair home Sharpe 集約の前提（明文化）

cross_pair.py が `mean(Sharpe_i) - λ × std(Sharpe_i)` を pair 単位 Sharpe 間で集約できるのは、**各 pair の P&L 時系列が「home 通貨の数値スケール」に依存せず生成されていること** が前提となる。この前提は次の 3 条件で担保される（本 TODO で保護される）:

**P1. 初期資金のスケール不変性**  
`BacktestConfig.initial_cash` は全 pair 共通の数値（例: `1_000_000`）として投入される。この値は「home 通貨建ての絶対額」だが、position sizing が `units` を絶対値で決める固定単位前提（cross-pair でも同一 `Genome.units`、Stage A/B の設定からも同一定数）。returns ratio = Δequity / equity は home 通貨が何であれ同じ率になる（initial_cash が一定なら scale 定数が相殺される）。

**P2. 注文量 sizing のスケール不変性**  
`Genome.units` は絶対単位（USD_JPY = 10000 units など）で決まり、home 通貨によらず同じ数値を使う。JPY 口座でも USD 口座でも同 units で注文する前提。

**P3. コスト計算のスケール不変性**  
`holding_cost_per_day_bps` は bps（notional 比例）なので home 通貨非依存。`max_spread_bps` 判定も bps で正規化されており非依存。

**検証方法**: 新規 test で EUR_USD / USD_CAD を同 `initial_cash=1_000_000` + 同 units で走らせ、trades が発生する条件下で `Sharpe` が意味ある値 (not None) であること、**P&L 符号が価格変動方向と一致**することを確認する（scale 差は検出しにくいが、Sharpe が nonzero / finite かつ価格方向整合性で sanity check）。

**注記**: P1 は「`initial_cash=1_000_000 JPY` と `initial_cash=1_000_000 USD` が異なる実質リスクを持つ」状態でも Sharpe は同じ（return ratio が等しい）ので shadow stats は収束する。ただし、cross-pair で「EUR_USD の 1_000_000 USD ≒ 150,000,000 JPY の擬似口座」になっている事実は `docs/alpha_factory/cross-pair.md` に明記しておく（shadow 統計の解釈は per-pair home モードである旨）。

## 8. Phase 4 quote→home 換算への拡張点（予約）

本 TODO では `home_currency=None` (自動 per-pair) / `home_currency="<通貨>"`（明示、現状は `meta.quote_currency` との一致時のみサポート）の 2 形態を受け付けるが、Phase 4 で真の quote→home 換算が必要になった際の拡張点を**設計予約**として命名しておく:

- **`fx_rate_provider: Callable[[str, str, datetime], Decimal] | None`** — 将来追加予定の broker コンストラクタ引数。`(base, quote, t) -> rate` のシグネチャで、指定時刻の変換レートを返す。本 TODO では受け取らない（interface 未定義）。
- Phase 4 実装時は以下の経路で組み込む想定:
  - `MockBroker.__init__(... , fx_rate_provider=None)`
  - `notional_home_currency(..., fx_converter=None)` 引数追加
  - `_realized_pnl` は依然 quote 建て、broker 内で `fx_rate_provider` による home 換算のあとに `self._cash` を更新
- 本 TODO ではこの引数を**追加せず**、docstring に「Phase 4 will introduce `fx_rate_provider` for quote→home conversion」と明示するに留める（実装の gold-plating を避ける）。

**Phase 4 契約予約（fail-fast 規約）**: `home_currency != meta.quote_currency` かつ `fx_rate_provider is None` の場合、broker コンストラクタは **fail-fast で `NotImplementedError` を維持する**（本 TODO のエラーメッセージは "Phase 4 requires fx_rate_provider" に更新する）。これにより Phase 4 実装前に混同経路で使われるのを防ぐ。本 TODO で `home_currency=None` default が機能する経路は `home_currency=meta.quote_currency` と等価な帰結になるため安全。

## 9. 受け入れ基準

1. 既存 `tests/broker/test_mock_broker.py` が全 pass（回帰なし）
2. 新規 `tests/broker/test_mock_multi_currency.py`:
   - EUR_USD backtest 完走・P&L が pips 方向に正しい符号
   - USD_CAD backtest 完走・P&L 正しい符号
   - USD_JPY 比較テスト（pip_size / precision が instrument meta に正しく乗る）
   - **明示 `home_currency="JPY"` の旧挙動が USD_JPY meta で壊れないこと**
   - **`home_currency="USD"` 指定時も `meta.quote_currency="USD"` なら受け入れる（将来互換性の担保）**
   - **Scale 不変性直接検証 (initial_cash)**: 同一 pair (USD_JPY / EUR_USD の両方)・同一価格系列で、`initial_cash=C` と `initial_cash=k*C` (k=10) の 2 回 backtest を実行し、margin 制約が発火しないシナリオ（十分な initial_cash + 小 units）で `abs(sharpe_C - sharpe_kC) < 1e-6` を assert
   - **Scale 不変性直接検証 (units)**: 同 pair・同 initial_cash で `units=U` と `units=k*U` を比較し、margin 非拘束条件下で `abs(sharpe_U - sharpe_kU) < 1e-6` を assert
3. cross_pair の新 test（または既存 test の拡張）で anchor3 pair（うち少なくとも 1 つ non-JPY-quote）の shadow 評価が `pair_failure:…:NotImplementedError` を含まず意味ある `mean_sharpe / std_sharpe` を返す
4. `mypy src/broker/` / `ruff check src/broker/ tests/broker/` clean
5. 既存 798 passed 維持 + 新規 test passed
6. `CurrencyPair` と `InstrumentMeta` の SSOT 境界の 1 行メモを mock.py docstring に追加

## 10. 主要設計決定サマリ

- **per-pair home 解釈を採用**（broker の home を明示指定無ければ meta.quote_currency に自動合わせ）。
- `InstrumentMeta` に `pip_size` / `display_precision` を **デフォルト付きで追加**（後方互換）。
- `notional_home_currency` の関数本体は変更せず docstring のみ更新。
- backtest engine.py / cross_pair.py 呼び出し側の改修は**不要**。
- 既存 USD_JPY / EUR_JPY テストは不変のまま通る。
- Sharpe 集約の scale 不変性前提 P1/P2/P3 を明文化。
- Phase 4 拡張点 `fx_rate_provider` を名前だけ予約（本 TODO では実装せず docstring で宣言）。
