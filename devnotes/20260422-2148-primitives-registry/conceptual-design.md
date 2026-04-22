# Conceptual Design: primitives-registry（T010 骨格）

## 背景

- 32 primitive は docs/alpha_factory/primitives.md に索引のみが書かれている。
- Phase 2D で 32 個を並列実装するが、GA（random_gen / serialize / analyze）や DslStrategy が参照する **単一の registry** が未整備。
- T008（GA operators）では暫定 `src/ga/_dummy_registry.py` を使い、primitive 仕様を最小 PrimitiveSpec で表現している（category + domain + param_schema のみ）。
- T007 で導入された `PrimitiveEvaluator` Protocol（`src/dsl/strategy.py`）の実装がまだない。

本 TODO は **registry/spec/evaluator の契約（骨格）だけ** を Phase 2D の先頭として切り出し、後続 4 TODO（directional-generic / modulator / pair-specific / dummy 削除移行）の共通基盤とする。

## North Star 整合

- 本タスクは **骨格のみ**。学習・実 backtest を走らせないため fitness / イントラデイ絶対制約に直接触れない。
- 後続 primitive 実装群が必須データを宣言する枠を提供することで、look-ahead 防止・データ依存の静的検査を可能にする（`required_data` フィールド）。
- 絶対制約（イントラデイ / ロングショート / コスト反映）を **阻害しない** 契約設計であることを以下で担保:
  - `compute` に `EvaluationContext` を通すことで、将来 session_calendar / spread / swap シリーズを primitive が参照する余地を残す（コスト反映との整合）。
  - pair 情報を context に含めることで pair-specific primitive が long/short 非対称な制約を持ち込まないかをレビュー可能にする。

## スコープ（In）

1. `src/alpha_factory/primitives/` パッケージ新設。
2. PrimitiveSpec / ParamSpec / EvaluationContext の正式版 dataclass 定義。
3. 登録 / 取得 / 列挙 / カテゴリ・ドメイン絞込 / clear（テスト用）の registry API。
4. `PrimitiveEvaluator` Protocol の実装クラス `RegistryEvaluator`。
5. GA slot 語彙と Category 語彙の対応関数 `slot_from_category()`。
6. `required_data` の canonical naming rule（簡易 enum）。
7. 契約テスト（register / get / list / clear / KeyError / ValueError / evaluator 配線 / slot mapping / naming rule）。

## スコープ（Out、後続 TODO）

- 実 primitive（F1〜F14, M1〜M6, P1〜P12）の実装登録。
- `_dummy_registry.py` 削除・tests/ga/ 移行（`slot_from_category` を使った tests/ga/ の書換えは移行 TODO）。
- CrossSeriesCache / DataBundle の具体データロード実装（本 TODO は EvaluationContext の **形** のみ定義）。
- numpy ベクトル化 compute_all_bars の性能最適化。

## 設計判断

### 1. PrimitiveSpec を正式 dataclass に昇格

- `src/ga/random_gen.py:PrimitiveSpec` は暫定で `category/domain/param_schema` しか持たず、compute 関数を保持できない。
- 正式 spec は **compute（スカラー） / compute_all_bars（ベクトル） / required_data** を追加で持つ。
- 両 spec は namespace が別 (`src/ga/_dummy_registry.py` vs `src/alpha_factory/primitives/_registry.py`) なので衝突しない。
- 後続移行 TODO で tests/ga/ を正式 spec に切替、旧 spec を削除する。

### 2. ParamSpec: 範囲 + 型 + default を明示

- 旧 registry は `{"n": (5, 50)}` の tuple 方式。型判定は tuple 要素の int/float で推論。
- 正式版は **`ParamSpec(name, low, high, is_int, default)`** で明示宣言。これにより:
  - serialize（genome → JSON）時のバリデーションが安定する。
  - default が明示され、一部 primitive で固定値を使う余地を残せる。
  - int/float 判別が型推論でなく is_int フラグで確実になる。

### 3. EvaluationContext の導入（R1 対応）

compute 契約を `bars, idx, params` のみに閉じず、補助系列と pair 情報を通せる **文脈オブジェクト** を骨格段階で定義する。後続 primitive（VIXRegimeGate / LondonNYOverlapMomentum 等）での契約破壊を防ぐ。

```python
@dataclass(frozen=True)
class EvaluationContext:
    bars: Sequence[PriceBar]                    # OHLC（必須・bars[idx] が判定対象 bar）
    idx: int                                    # 判定対象 bar のインデックス
    pair: str                                   # 通貨ペア名（例: "EUR_USD"）
    params: Mapping[str, float | int]           # primitive 固有パラメータ
    aux_series: Mapping[str, Sequence[float]]   # 補助時系列（required_data の非 OHLC キーに対応）
```

- `aux_series` は Mapping なので欠落時は KeyError が生じる。本 TODO では **空 Mapping でも構築可能** とし、中身のロードは後続。
- `pair` は必須（pair_specific primitive の必要最低情報）。generic primitive は無視してよい。
- `bars` と `idx` を context に入れることで `compute(ctx)` のシグネチャが **1 引数** に揃い、後続の変更耐性が高まる。

compute / compute_all_bars の契約:

```python
compute: Callable[[EvaluationContext], float]
compute_all_bars: Callable[[EvaluationContext], np.ndarray]
```

`compute_all_bars` は `ctx.idx` を無視して全 bar 長ベクトルを返す契約（warmup 内は NaN で埋める）。これにより GA の in-sample 一括計算が高速化される。

### 4. required_data の canonical naming rule（R4 対応）

値の候補を以下の名前空間に限定する（string ではあるが、`_base.py` で Literal 型 alias を定義する）:

- `ohlc` — PriceBar.bid / PriceBar.ask（ctx.bars から直接）
- `atr` — 既存 ATR 計算ユーティリティから（T009 導入）
- `spread` — PriceBar.spread_close から
- `calendar.session` — session window 時刻マップ
- `calendar.economic_event` — 経済指標イベントマップ
- `macro.vix` / `macro.dxy` / `macro.dgs10` / `macro.dgs2` / `macro.t10yie` — FRED 系（docs/terminology.md 参照）
- `macro.spx500` — OANDA CFD SPX500_USD
- `cross_pair.<pair>` — 他ペアの OHLC（CrossPairTriangulation 等）

```python
RequiredDataKey = Literal[
    "ohlc", "atr", "spread",
    "calendar.session", "calendar.economic_event",
    "macro.vix", "macro.dxy", "macro.dgs10", "macro.dgs2", "macro.t10yie", "macro.spx500",
    # cross_pair.* は str として許容（型パラメータ化は過剰）
]
```

`cross_pair.<pair>` だけは `tuple[str, ...]` の自由度を残す（pair 列挙を骨格で固定すると docs と二重管理になる）。check は startswith で十分。

### 5. registry は **module-level 可変 dict** + register API

- 初期は空。primitive モジュール側で import 時に `register(PrimitiveSpec(...))` する設計を想定（後続 TODO）。
- テスト隔離のため `clear()` を提供（テスト内 fixture で使う想定）。
- 重複 register は ValueError（silent override でバグを隠さない）。

### 6. Bootstrap 方針（R6 対応）

本 TODO では registry は空のまま。後続 TODO では **明示的 bootstrap 関数** `ensure_registered()` を用意する方針を先に固定する:

```python
def ensure_registered() -> None:
    """primitives パッケージ配下の実装モジュールを import して register を発火。
    production path (GA entry) から明示的に 1 回呼ぶ。冪等。"""
```

副作用 import 単独に頼らず、テスト・本番両方で明示呼び出しする。本 TODO では関数のシグネチャと docstring のみ定義し、中身は pass（登録対象が未だ無いため）。登録漏れ検出は後続 TODO で「ensure_registered 後の `list_all()` 件数が期待値と一致」テストで担保する。

### 7. RegistryEvaluator は薄い adapter

- `RegistryEvaluator.evaluate(bars, idx, signal)` が `PrimitiveEvaluator` Protocol を満たす。
- 内部で `EvaluationContext` を構築して `spec.compute(ctx)` を呼ぶ。
- pair 情報は evaluator 構築時の引数で受け取る（`RegistryEvaluator(pair="EUR_USD", aux_series=...)`）。
- aux_series はデフォルト空 Mapping。後続 TODO で実データ注入。

```python
class RegistryEvaluator:
    def __init__(
        self,
        *,
        pair: str,
        aux_series: Mapping[str, Sequence[float]] | None = None,
    ) -> None: ...

    def evaluate(
        self, bars: list[PriceBar], idx: int, signal: SignalConfig
    ) -> float:
        spec = get_primitive(signal.name)
        ctx = EvaluationContext(
            bars=bars, idx=idx, pair=self._pair,
            params=signal.params, aux_series=self._aux_series,
        )
        return spec.compute(ctx)
```

### 8. PrimitiveCategory を docs 4 値に、GA slot 対応を本 TODO で確定（R3 対応）

- PrimitiveCategory: `Literal["TREND_FOLLOW", "MEAN_REVERT", "NEUTRAL", "MODULATOR"]`（docs 側）。
- GA slot: `Literal["directional", "local_gate"]`（`src/ga/random_gen.py`）。
- **本 TODO で** `slot_from_category()` を `_base.py` に実装し、契約テストで固定する:

```python
def slot_from_category(
    category: PrimitiveCategory,
) -> Literal["directional", "local_gate"]:
    if category == "MODULATOR":
        return "local_gate"
    return "directional"  # TREND_FOLLOW / MEAN_REVERT / NEUTRAL
```

tests/ga/ の移行は後続 TODO で行うが、対応関数自体の契約は本 TODO で凍結するので二重管理リスクが最小化される。

### 9. PrimitiveDomain と pair_specific の扱い（R2 対応）

- `PrimitiveDomain = Literal["generic", "pair_specific"]`。
- `pair_specific` primitive は `EvaluationContext.pair` を参照可能（R1 の EvaluationContext 導入でカバー）。
- 骨格時点では `pair_specific` primitive は登録されないが、契約は `pair` を受け取れる形で固定済み。
- 将来追加で必要になりそうな pair metadata（pip_size, quote_currency 等）は **本 TODO では context に入れない**。理由: 32 primitive のうち P1-P12 の具体仕様が固まっていない段階で metadata を固定すると過剰設計になる。pip/quote が必要になった時点で `EvaluationContext` を拡張する（dataclass フィールド追加は非破壊的）。

## リスクと緩和

| リスク | 影響 | 緩和策 |
|--------|------|--------|
| GA 側が暫定 PrimitiveSpec を使い続ける間、二重管理 | registry と dummy の乖離 | T008 の dummy は読取専用、本 TODO でも触らない。`slot_from_category` を先行凍結し、移行 TODO で一気に切替 |
| compute 関数の signature 差異 | 後続 primitive 実装で不整合 | `EvaluationContext` 1 引数契約で固定。dataclass 追加拡張は後方互換 |
| compute_all_bars の性能前提が未定 | 後続 TODO で再設計になる懸念 | 本 TODO では signature のみ固定。warmup は NaN で埋める規約のみ記載 |
| register tree への副作用 import 順序 | モジュール import 順で登録漏れ | 明示的 `ensure_registered()` 方針を骨格で宣言（中身は pass） |
| required_data の語彙ゆれ | 後続 primitive 実装で揺れ発生 | canonical naming rule（Literal + cross_pair プレフィックス規約）を本 TODO で凍結 |
| pair metadata 追加時の context 変更 | 後続の互換破壊 | dataclass に field 追加は後方互換。default 値つきで追加する運用ルールを docstring に記載 |

## 受入基準（局所化, R5 対応）

1. `src/alpha_factory/primitives/{__init__,_base,_registry,evaluator}.py` の 4 ファイルが存在。
2. `tests/alpha_factory/test_primitives_registry.py` の契約テストが全 pass:
   - register → get で同じ spec を取得
   - 重複 register で ValueError
   - list_all / list_by_category / list_by_domain が期待通り動作
   - clear で registry 空
   - 未登録 primitive で get_primitive が KeyError
   - RegistryEvaluator が DummyPrimitiveSpec を評価し期待値を返す
   - `slot_from_category("MODULATOR") == "local_gate"` / 他 3 値 → `"directional"`
   - `ensure_registered()` が呼べる（中身は空で OK）
3. `uv run mypy src/alpha_factory/primitives/` が clean。
4. `uv run ruff check src/alpha_factory/primitives/ tests/alpha_factory/` が clean。
5. `src/ga/_dummy_registry.py` の差分ゼロ。
6. 本 TODO 新設の契約テスト以外の既存テストが引き続き pass（件数の絶対値は要求しない、regression のみ要件）。

## 代替案の却下理由

- **EvaluationContext 不導入で `(bars, idx, params)` 継続**: R1 指摘通り aux_series を渡せず、後続で契約破壊。却下。
- **pair metadata（pip_size 等）を今入れる**: 32 primitive の P1-P12 仕様未定の段階で過剰。context は後方互換拡張可能なので延期。
- **required_data を完全 enum 化**: cross_pair.<pair> の柔軟性を殺す。startswith パターンで十分。
- **GA slot 対応を移行 TODO に送る**: R3 指摘通り二重管理期間が伸びる。本 TODO で関数だけ凍結。
- **単一 module に spec+registry を併置**: `_base.py` と `_registry.py` を分けない案。後続 32 primitive が `_base.py` のみ import して register できるよう分離。
- **PrimitiveSpec を TypedDict**: frozen dataclass の `__hash__` と不変性を捨てる。registry key としての安定性低下。却下。

## 後続タスク

- T010-a primitives-directional-generic 実装（F1-F14、ensure_registered 実装）
- T010-b primitives-modulator 実装（M1-M6）
- T010-c primitives-pair-specific 実装（P1-P12）
- T010-d GA/dummy registry 削除・tests/ga/ を `slot_from_category` ベースに移行
