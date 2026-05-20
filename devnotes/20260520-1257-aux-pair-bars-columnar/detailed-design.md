# 詳細設計: aux_pair_bars の columnar 化 (main RSS 削減 step A / T107)

## 使命・制約（絶対遵守）

### 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。
**本施策単体では strategy quality は改善しない。GA 探索を最後まで回せる確率
(OOM 回避) を上げる前提整備。**

### 禁止事項
1 評価期間延長 / 2 見た目数値改善 / 3 GA ハック / 4 live_criteria 緩和 /
5 過度な複雑化 / 6 取引回数削減 / 7 オーバーナイト

### コーディングルール
- 全施策にテスト必須 / バグ修正はテストファースト
- テスト命名は振る舞い説明 / 対象モジュールに対応するテストファイル
- uv 必須 / ruff / mypy src 通過 / Python 3.11 + numpy

## 概念設計リファレンス
devnotes/20260520-1257-aux-pair-bars-columnar/conceptual-design.md (APPROVED Round 2)

## 前提 (C4)

| 項目 | 状態 | 根拠 |
|---|---|---|
| aux_pair_bars 消費者は P5 のみ | verified | grep `ctx.aux_pair_bars` = pair_specific.py:411-412 のみ。`_is_aux_provided` の cross_pair. 判定 (evaluator.py:100) も対象 |
| P5 は mid close + bar_time のみ使用 | verified | _aligned_pair_close (pair_specific.py:108) |
| 契約フィールドは EvaluationContext.aux_pair_bars (_base.py:262) / RegistryEvaluator._aux_pair_bars (evaluator.py:74) / AlignedAuxBundle.aux_pair_bars (aux_loader.py:153) / AuxBundle.aux_pair_bars_index + aux_pair_bars (aux_loader.py:177,186) | verified | 直接読み |
| align は AuxBundle.align_to の §4 で list[PriceBar|None] 構築 (aux_loader.py:243-250) | verified | 同上 |
| raw 構築は load_aux_pair_bars_index (aux_loader.py:610-668, T106 streaming 済) | verified | 同上 |
| aux_bundle は worker に pickle 送信 (initargs) | verified | parallel_eval AuxAlignmentCache (T057) |
| PriceBarM1.bar_time は tz-aware UTC, M1 (秒=0) | verified | T106 で確認、_normalize_bar_time で正規化 |

## 施策一覧

| # | 施策 | 変更ファイル | 優先度 |
|---|---|---|---|
| C-1 | raw columnar `AuxPairMidSeries` + load 関数 + build wiring + 検証 | aux_loader.py | High |
| C-2 | align_to → `aux_pair_mid_close` (searchsorted exact-match, read-only) | aux_loader.py | High |
| C-3 | 契約 swap: EvaluationContext / RegistryEvaluator (`aux_pair_bars`→`aux_pair_mid_close`) | _base.py, evaluator.py | High |
| C-4 | P5 + `_aligned_pair_close` を mid 配列消費に書換 | pair_specific.py | High |
| C-5 | parallel_eval / AuxAlignmentCache の field 名追従 | parallel_eval.py | Med |
| C-6 | phase marker 分割 (after_raw_aux_index_built / after_aux_aligned_built) | run_ga.py, aux_loader.py | Med |
| C-7 | テスト (golden / strict-match 4 ケース / 契約) | tests/ | High |
| C-8 | smoke 検証 | (検証 phase) | Med |

---

## C-1. raw columnar `AuxPairMidSeries`

### 変更箇所
`src/alpha_factory/aux_loader.py` (L556-668 周辺 + 新規 dataclass)

### 設計

```python
@dataclass(frozen=True)
class AuxPairMidSeries:
    """aux pair の bar_time→mid_close を columnar に保持する (T107).

    契約 (構築時 fail-fast 検証):
      - ts_epoch_ns: UTC epoch ナノ秒 int64、 strict monotonic increasing + unique
      - mid_close: float64、 ts_epoch_ns と同一長
      - mid_close[i] = (bid_close + ask_close)/2 (float 演算、 P5 の式と同一)
    epoch 単位は ns 固定。 target 側も同一の変換関数 (_to_epoch_ns) のみを使う。
    """
    ts_epoch_ns: np.ndarray  # dtype int64, read-only
    mid_close: np.ndarray    # dtype float64, read-only

    def __post_init__(self) -> None:
        # 構築時 read-only 化 (setflags は in-place なので frozen でも可)
        self.ts_epoch_ns.setflags(write=False)
        self.mid_close.setflags(write=False)

    def __setstate__(self, state: dict) -> None:
        # unpickle 後に read-only を再適用 (pickle は writable に戻すため)。
        # frozen __setattr__ を迂回しつつ slots 化耐性のため object.__setattr__ 使用
        # (Round 3 Codex 推奨)。
        object.__setattr__(self, "ts_epoch_ns", state["ts_epoch_ns"])
        object.__setattr__(self, "mid_close", state["mid_close"])
        self.ts_epoch_ns.setflags(write=False)
        self.mid_close.setflags(write=False)


_EPOCH_UTC: Final = datetime(1970, 1, 1, tzinfo=UTC)


def _to_epoch_ns(dt: datetime) -> int:
    """tz-aware/naive datetime → UTC epoch ナノ秒 int。 epoch 単位の単一権威。

    float 経路 (timestamp()*1e9) は丸め誤差を生むため使わない。
    timedelta の整数フィールド (days/seconds/microseconds) から ns を整数算出する。
    """
    d = dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    d = d.astimezone(UTC)
    delta = d - _EPOCH_UTC
    # timedelta は days/seconds/microseconds の整数 3 組で内部表現される
    total_us = (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
    return total_us * 1_000  # μs → ns (整数のみ、 丸めなし)
```

`_to_epoch_ns` は **整数経路のみ** (Round 1 [Critical] 3: `if False` 削除、
float 経路完全排除)。M1 は秒解像度だが、 raw/target で同一関数を使う契約のため
microsecond 整数まで保持する。

`pair_not_found` 等の空配列も read-only にするヘルパを設ける
(Round 1 [Critical] 2):
```python
def _empty_aux_pair_mid_series() -> AuxPairMidSeries:
    ts = np.empty(0, dtype=np.int64); ts.setflags(write=False)
    mid = np.empty(0, dtype=np.float64); mid.setflags(write=False)
    return AuxPairMidSeries(ts_epoch_ns=ts, mid_close=mid)
```

`load_aux_pair_bars_index` を `load_aux_pair_mid_index` に置換:

```python
def load_aux_pair_mid_index(
    *, db_session: Session, pairs: Sequence[str],
    period: tuple[datetime, datetime],
) -> dict[str, AuxPairMidSeries]:
    out: dict[str, AuxPairMidSeries] = {}
    for pair_name in pairs:
        pair = db_session.scalars(
            select(CurrencyPair).where(CurrencyPair.oanda_name == pair_name)
        ).one_or_none()
        if pair is None:
            out[pair_name] = _empty_aux_pair_mid_series()  # read-only 空配列
            logger.warning("aux_loader.aux_pair_bars.pair_not_found", pair=pair_name)
            continue
        out[pair_name] = _stream_aux_pair_mid(
            db_session, pair_db_id=pair.id, pair_name=pair_name,
            start=period[0], end=period[1],
        )
    return out


def _stream_aux_pair_mid(db_session, *, pair_db_id, pair_name, start, end,
                         batch_size=_LOAD_BARS_BATCH_SIZE) -> AuxPairMidSeries:
    """server-side cursor streaming で (ts_epoch_ns, mid_close) を構築 (T106 streaming 継承).

    bid_close / ask_close のみ取得。 V15 fail-fast (同 minute normalize 重複) を
    維持。 構築後に strict monotonic + unique を検証。
    """
    stmt = (
        select(PriceBarM1.bar_time, PriceBarM1.close_bid, PriceBarM1.close_ask)
        .where(PriceBarM1.pair_id == pair_db_id)
        .where(PriceBarM1.bar_time >= start)
        .where(PriceBarM1.bar_time < end)
        .order_by(PriceBarM1.bar_time.asc())
        .execution_options(yield_per=batch_size)
    )
    ts_list: list[int] = []
    mid_list: list[float] = []
    seen_last_ns: int | None = None
    result = db_session.execute(stmt)
    try:
        for row in result:
            key = _normalize_bar_time(row.bar_time)  # tz-aware UTC, 秒切捨て
            ns = _to_epoch_ns(key)
            if seen_last_ns is not None and ns <= seen_last_ns:
                # V15 + monotonic/unique: normalize 重複 or 非単調 → fail-fast
                raise ValueError(
                    f"aux_pair_mid non-monotonic/duplicate bar_time after "
                    f"normalize for pair={pair_name} ns={ns} (prev={seen_last_ns})"
                )
            seen_last_ns = ns
            ts_list.append(ns)
            # P5 と同一の float 演算順序 (bid+ask)*0.5
            mid_list.append((float(row.close_bid) + float(row.close_ask)) * 0.5)
    finally:
        result.close()
    ts = np.asarray(ts_list, dtype=np.int64)
    mid = np.asarray(mid_list, dtype=np.float64)
    ts.setflags(write=False)
    mid.setflags(write=False)
    return AuxPairMidSeries(ts_epoch_ns=ts, mid_close=mid)
```

注: order_by asc + ns<=prev で raise により、 strict monotonic + unique が
DB 取得順で保証される (ORDER BY が崩れない限り)。 念のため raise メッセージで
原因を区別。

### 波及変更
- AGENTS.md / skill / config / docs: なし (内部実装)
- `__all__`: `load_aux_pair_bars_index` を `load_aux_pair_mid_index` に、
  `AuxPairMidSeries` を追加。`_bar_row_to_price_bar` (aux_loader 内、 raw 用途)
  は P5 経路から不要になるが run_ga / sieve が別途持つので **aux_loader 内の
  ものは削除可** (要 grep 確認: aux_loader._bar_row_to_price_bar の外部参照)

### テスト計画
- `test_load_aux_pair_mid_index_returns_columnar` (sqlite): ts_epoch_ns/mid_close 長一致 + 値
- `test_aux_pair_mid_strict_monotonic_unique_fail_fast`: 同 minute 重複 → ValueError
- `test_aux_pair_mid_arrays_read_only`: setflags(write=False) で書込不可
- `test_to_epoch_ns_integer_path_no_float_drift`: 既知 datetime → 期待 ns (丸め誤差なし)

### リスク
- `_to_epoch_ns` の float 丸め → 整数経路で回避 (設計済)
- 外部に `load_aux_pair_bars_index` を import している箇所 → grep して全置換 (実装時)

---

## C-2. align_to → `aux_pair_mid_close`

### 変更箇所
`aux_loader.py`: `AlignedAuxBundle` (L143-162), `AuxBundle` (L165-256)

### 設計

`AlignedAuxBundle`:
```python
@dataclass(frozen=True)
class AlignedAuxBundle:
    aux_series: Mapping[str, np.ndarray]
    event_snapshot: EconomicEventSnapshot | None
    vix_snapshot: VixSeriesSnapshot | None
    aux_pair_mid_close: Mapping[str, np.ndarray]  # 旧 aux_pair_bars を置換

    def as_evaluator_kwargs(self) -> dict[str, Any]:
        return {
            "aux_series": dict(self.aux_series),
            "event_snapshot": self.event_snapshot,
            "vix_snapshot": self.vix_snapshot,
            "aux_pair_mid_close": dict(self.aux_pair_mid_close),
        }
```

`AuxBundle`:
- `aux_pair_bars_index: dict[str, dict[datetime, PriceBar]]` を
  `aux_pair_mid_index: dict[str, AuxPairMidSeries]` に置換
- Phase 1 後方互換の `aux_pair_bars: dict[str, list[PriceBar | None]]` field は
  **削除** (CSV 経路含め未使用化、 要 grep 確認)

`align_to` の §4 (aux_pair_bars 構築) を置換:
```python
        # 4. aux_pair_mid_close: target bars の epoch に searchsorted で exact-match。
        #    align_to is the sole authority for exact timestamp matching (SSOT)。
        #    forward-fill 禁止 (exact-match のみ、 look-ahead 防止)。consumer は
        #    bar_time を再検証しない。 ← docstring に明文化 (Round 1 [Suggestion] 2)
        target_ns = np.fromiter(
            (_to_epoch_ns(_bar_time_utc(b.bar_time)) for b in bars),
            dtype=np.int64, count=n,
        )
        aux_pair_mid_close: dict[str, np.ndarray] = {}
        for pair_name, series in self.aux_pair_mid_index.items():
            out = np.full(n, np.nan, dtype=np.float64)
            raw_ts = series.ts_epoch_ns
            if raw_ts.size > 0:
                pos = np.searchsorted(raw_ts, target_ns, side="left")
                in_range = pos < raw_ts.size
                # exact-match 行のみ採用 (raw_ts[pos] == target_ns)
                valid = np.zeros(n, dtype=bool)
                valid[in_range] = raw_ts[pos[in_range]] == target_ns[in_range]
                out[valid] = series.mid_close[pos[valid]]
            out.setflags(write=False)
            aux_pair_mid_close[pair_name] = out
```

空 bars の早期 return も `aux_pair_mid_close={}` に変更。

### ルックアヘッドバイアスチェック
- [x] 未来バー参照なし (exact-match のみ、 forward-fill しない)
- [x] 当日確定値先取りなし (bar_time 完全一致のみ採用)
- [x] rolling 不使用 / 統計量不使用
- searchsorted は align のみ、 因果性に影響しない (時刻一致判定)

### パフォーマンスチェック
- [x] searchsorted は O(n log m) ベクトル化 (per-bar Python loop の dict lookup
  より速い)
- [x] 内側ループに Python loop なし (target_ns 構築の fromiter のみ)
- [x] read-only ndarray でキャッシュ安全

### テスト計画 (strict-match 境界を網羅, Round 1 [Warning] C-7)
- `test_align_aux_pair_mid_exact_match`: target と raw が一致する index で mid 値
- `test_align_aux_pair_mid_miss_is_nan`: raw に無い bar_time → NaN
- `test_align_aux_pair_mid_target_before_first`: target_ns < raw 先頭 → NaN (pos=0 だが不一致)
- `test_align_aux_pair_mid_target_after_last`: target_ns > raw 末尾 → NaN (pos==size, in_range で防御)
- `test_align_aux_pair_mid_equal_last`: target_ns == raw 末尾 → mid 値 (境界一致)
- `test_align_aux_pair_mid_partial_overlap`: 一部一致 (in_range 境界含む)
- `test_aligned_aux_pair_mid_read_only`: 出力配列 read-only
- `test_align_empty_bars_returns_empty`: 空 bars → 空 dict
- `test_align_empty_raw_all_nan`: raw 空 (pair_not_found) → 全 NaN

### リスク
- searchsorted side: raw_ts unique + sorted 前提 (C-1 で fail-fast 保証)
- target_ns の単位が raw と異なると全 miss → `_to_epoch_ns` 単一権威で防止

---

## C-3. 契約 swap (EvaluationContext / RegistryEvaluator)

### 変更箇所
`primitives/_base.py` (L262), `primitives/evaluator.py` (L62,74,100-101,138-153,179-211)

### 設計
- `EvaluationContext.aux_pair_bars: Mapping[str, Sequence[PriceBar|None]]` を
  `aux_pair_mid_close: Mapping[str, np.ndarray]` に置換 (default 空 dict)
- `RegistryEvaluator`: `__init__` / `with_aux` の引数名 `aux_pair_bars` →
  `aux_pair_mid_close`、 内部 `_aux_pair_bars` → `_aux_pair_mid_close`。
  `__init__` / `with_aux` で受領した各 mid 配列に `_freeze_aux_pair_mid`
  (setflags write=False) を適用し、 unpickle 後の writable 復元を再 freeze する
  (Round 2 [Warning] C-5)
- `_is_aux_provided`: `key.startswith("cross_pair.")` 判定を
  `key[len("cross_pair."):] in self._aux_pair_mid_close` に
- `evaluate` / `evaluate_all_bars` が EvaluationContext に渡す field 名変更

### 波及変更
- AGENTS.md / skill / config / docs: なし (内部 API)
- docstring (_base.py:239-244) を mid 配列契約に更新

### 契約移行 監査チェックリスト (Round 1 [Critical] 1 必須)
実装時に以下を **grep して全置換漏れを潰す** (チェックリストを impl-review に提示):
- [ ] `aux_pair_bars` (識別子) の全出現: src / tests / scripts
- [ ] `aux_pair_bars_index` の全出現
- [ ] `cross_pair.` prefix を扱う箇所 (_is_aux_provided)
- [ ] `load_aux_pair_bars_index` の import 元 (run_ga / sieve / tests)
- [ ] CSV loader (`build_aux_bundle`) が aux_pair_bars field を埋める箇所
- [ ] report 生成 / archive で aux_pair_bars を参照する箇所 (なければ確認のみ)
- [ ] `_aligned_pair_close` の import 元 (P5 以外で使われていないか)

### テスト計画
- `test_evaluator_passes_aux_pair_mid_close_to_context`: with_aux で渡した mid が ctx に届く
- `test_is_aux_provided_cross_pair_uses_mid_close`: cross_pair.EUR_USD 判定
- **`test_csv_build_to_align_to_p5_integration`** (Round 1 [Critical] 1):
  CSV 経路 (`build_aux_bundle`) で aux pair を与え → align_to → P5 が動く
  end-to-end 統合テスト 1 本。CSV 経路が壊れていないことを保証

### リスク
- 旧 `aux_pair_bars` を参照する全テスト/コードの grep 全置換 (上記チェックリストで担保)

---

## C-4. P5 + `_aligned_pair_close` 書換

### 変更箇所
`primitives/pair_specific.py` (L75-109 `_aligned_pair_close`, L402-430 `_p5_compute_all`)

### 設計
`_aligned_pair_close` を削除 (整列は align_to SSOT に移管済)。`_p5_compute_all`:
```python
def _p5_compute_all(ctx: EvaluationContext) -> np.ndarray:
    n = len(ctx.bars)
    eu = ctx.aux_pair_mid_close.get("EUR_USD")
    uj = ctx.aux_pair_mid_close.get("USD_JPY")
    if eu is None or uj is None:
        if ctx.strict_snapshot_required:
            raise RuntimeError("P5: aux_pair_mid_close EUR_USD/USD_JPY missing but strict mode")
        _warn_missing("P5", "aux_pair_mid_close EUR_USD/USD_JPY")
        return np.zeros(n, dtype=np.float64)
    # 長さ整合は align_to が保証するが、 防御的に MISALIGNMENT を fail-fast
    if len(eu) != n or len(uj) != n:
        raise ValueError(
            f"P5: aux_pair_mid_close length mismatch eu={len(eu)} uj={len(uj)} bars={n}"
        )
    eu_close = eu  # 既に mid close (NaN=stale)
    uj_close = uj
    target_close = _bars_to_mid_close(ctx.bars)
    synth = eu_close * uj_close
    residual = target_close - synth
    z = zscore(residual, _get_int_param(ctx.params, "z_n"))
    scale = _get_float_param(ctx.params, "scale")
    out = -np.tanh(z / (scale + _EPS))
    out = np.where(np.isnan(z), np.nan, out)
    return out
```

mid close 値・演算順序は現行と同一 (`(bid+ask)*0.5` を C-1 で事前計算済)。
NaN (stale/欠番) の伝播も現行 `_aligned_pair_close` の None→NaN と等価。

### ルックアヘッドバイアスチェック
- [x] 未来参照なし / 当日確定先取りなし (mid は align 済、 bar_time exact-match)
- [x] zscore は既存 (rolling 過去方向、 不変)
- [x] mid 計算式不変 → P5 出力 semantic equivalent

### パフォーマンスチェック
- [x] compute_all_bars 実装済 / 内側 Python loop 削減 (旧 _aligned_pair_close の
  per-bar loop が消え、 ベクトル化 mid 配列直参照に)
- [x] SoA (mid 配列) / read-only 配列

### テスト計画
- `test_p5_golden_equivalence_vs_legacy`: 同入力で旧実装 (PriceBar list) と
  新実装の出力配列一致 (一次判定 KPI)。比較は **`np.testing.assert_array_equal`**
  で NaN 同位置を許容しつつ bit-level 同等性を検証 (Round 1 [Warning] 2:
  `allclose` は NaN/bit 差を見逃すため不可)
- `test_p5_missing_pair_safe_default` / `test_p5_strict_mode_raises`
- `test_p5_stale_nan_propagation`: 欠番 NaN が synth/out に伝播
  (assert_array_equal で NaN 位置一致を確認)

### リスク
- `_bars_to_mid_close` (target) は PriceBar のまま (target bars は lane bars、 本施策スコープ外) → 変更なし

---

## C-5. parallel_eval / AuxAlignmentCache 追従

### 変更箇所
`parallel_eval.py` (L238-264 `_get_aligned_for_stage` / `_evaluator_for_stage`)

### 設計
- `AlignedAuxBundle.as_evaluator_kwargs()` が `aux_pair_mid_close` を返すよう
  C-2 で変更済 → `with_aux(**aligned.as_evaluator_kwargs())` は自動追従
- `_get_aligned_for_stage` は型が AlignedAuxBundle のままなので変更最小
- AuxAlignmentCache は align_to を呼ぶだけ → field 名変更の追従のみ

### read-only flag の pickle 復元 (Round 1 [Warning] 1 / Round 2 [Warning] C-5)
numpy 配列は pickle 後に `flags.writeable` が **True に戻る**。worker は spawn で
initargs を unpickle し、 同一 aligned aux を複数 genome 評価で再利用するため、
復元後 writable だと将来 primitive / デバッグコードによる mutation が
**cross-evaluation contamination** になりうる。read-only は「現行 P5 が書かない」
ではなく「評価コンテキスト配列が誤変更されない」防御線。よって **復元直後に
read-only を再適用する** (Round 2 [Warning] C-5 反映、 低コストで契約維持):

- `AuxPairMidSeries` を frozen dataclass とし、 `__post_init__` で
  `ts_epoch_ns.setflags(write=False)` / `mid_close.setflags(write=False)` を適用
  (構築時。 setflags は in-place mutation なので frozen でも可)
- pickle はデフォルトで `__dict__` 復元し `__post_init__` を呼ばないため、
  **`__setstate__` を定義して unpickle 後に setflags(write=False) を再適用**する
- `AlignedAuxBundle.aux_pair_mid_close` の各配列も align_to 構築時に read-only 化
  済 (C-2)。 こちらは np.ndarray 直保持なので、 worker 注入経路で
  `as_evaluator_kwargs` 経由でも同様に unpickle 後 writable に戻りうるが、
  AuxPairMidSeries 経由でない aligned 配列の re-freeze は RegistryEvaluator
  受領時 (`with_aux`) に `_freeze_aux_pair_mid` ヘルパで再適用する

### テスト計画
- `test_evaluator_for_stage_injects_aux_pair_mid_close`: stage 別 mid が evaluator に注入される
- `test_aux_pair_mid_series_pickle_roundtrip` (Round 1 [Warning] 1 / Round 2
  [Warning] C-5): pickle dumps/loads 後に値が一致 **かつ
  `flags.writeable is False`** (= __setstate__ で re-freeze されている)
- `test_aligned_aux_pair_mid_read_only_after_with_aux`: RegistryEvaluator.with_aux
  経由でも aligned 配列が read-only (`_freeze_aux_pair_mid` 適用確認)

### リスク
- pickle 経路: AuxPairMidSeries (numpy 2 配列) は picklable。 旧 dict[datetime,
  PriceBar] より大幅小。read-only flag は復元後 writable に戻りうるが P5 は
  read のみのため機能影響なし (上記テストで確認)

---

## C-6. phase marker 分割

### 変更箇所
`run_ga.py` (aux_bundle build 周辺), `aux_loader.py` (build_aux_bundle_from_db)

### 設計
- `after_raw_aux_index_built`: load_aux_pair_mid_index 完了直後 (build_aux_bundle_from_db 内 or run_ga 側)
- `after_aux_aligned_built`: 既存 after_aux_bundle_built の前後で align 完了を区別
- 既存 `after_aux_bundle_built` / `before_ga_loop` は維持

実装上、 build_aux_bundle_from_db は src 層 (logger あり) なので、 raw 構築直後の
marker は run_ga 側で `_log_phase_marker("after_raw_aux_index_built")` を
aux_bundle 構築の前後に挟む形が最小。

### テスト計画
- 既存 phase marker テストに新 phase 名追加確認 (logger event)

---

## C-7/C-8 テスト & smoke

### テスト
上記各施策のテスト + 既存 test_aux_loader_align.py の P5/align 系を新契約に更新。
全 pass + ruff + mypy src。

### smoke 検証 (C-8)
```bash
RUN_ID="smoke_t107_$(date +%Y%m%d_%H%M%S)"
PYTHONFAULTHANDLER=1 uv run python scripts/alpha_factory/run_ga.py \
  --config config/alpha_factory/default.yaml \
  --population-size 24 --generations 5 --max-workers 2 \
  --max-tasks-per-child 12 --seed 9999 --no-report --run-id "$RUN_ID"
```
判定 (概念設計の成果判定表、 Round 1 [Warning] 3 反映):
- **主判定**: (1) P5 golden 一致 (ユニットテスト) **かつ** (2) live_criteria
  判定 (使命判定の pass/fail 構造) が baseline と一致 **かつ** (3)
  after_aux_bundle_built 削減 ≥1.0GB (baseline 3277MB)
- **参考指標**: GA best genome 完全一致 (g2_i2, fitness
  -0.02894014223533147)。並列実行で不安定化しうるため pass/fail には使わず
  参考値として記録のみ

## 実装モード

| 項目 | 内容 |
|---|---|
| 推奨モード | **standalone** |
| 判断根拠 | aux_loader / primitives 契約 / parallel_eval を協調変更。 1 PR で C-1〜C-8 統合。 外向き API は内部のみ (CLI/config 不変)。 |
| 競合リスク | aux_loader を触る他 TODO と同時並行で conflict 可。 単独で進める |
| 想定実装時間 | **中〜大** (契約 swap が広域、 grep 全置換 + golden テスト。 1 日程度) |
