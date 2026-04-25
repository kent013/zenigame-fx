# T012 Modulator generic primitives (M1-M6) — Conceptual Design

## 背景

T010 registry 骨格と T011 directional generic 14 個（F1-F14）が merged（`b3268d5`）。
現時点で `category_counts()` の MODULATOR は 0 件。local_gate slot が空なので clause の
`directional * local_gate` 評価経路の local_gate 部が機能していない。

本 TODO は `local_gate` として GA が進化対象にする MODULATOR primitive を 6 個
実装し registry に登録することで、Alpha Factory の clause 構造を完成させる。

## 目的（仮説）

**仮説**: 「directional signal のみで収束する GA は、volatility regime や event blackout 等の
*文脈条件* を表現できないため Stage A / B で不安定に振る舞う。MODULATOR を local_gate として
乗せることで、不利な regime をゲートアウトし fitness を改善できる」。

成功判断: T012 merge 後、registry の `MODULATOR` が 6 件になり、`list_all()` が 20 件返し、
look-ahead property test を含む全テストが passing。

## スコープ

### 実装対象（全 6 件、MODULATOR / generic / local_gate）

| ID | 名称 | 入力 | 出力式 | 外部データ依存 |
|----|------|------|--------|----------------|
| M1 | ATRRegimeGate | OHLC（ATR） | `sigmoid((ATR - θ)/scale)` × 方向 param | なし |
| M2 | SessionGate | bar_time | session 該当なら 1 それ以外は 0（soft edge option） | なし |
| M3 | SpreadConditionGate | bid/ask.close | `1 / (1 + exp(k*(spread_bps - θ)))` | なし |
| M4 | EconomicEventGate | bar_time + event 一覧 | `1 - sigmoid((window - |Δt|)/scale)` | **event_calendar** |
| M5 | VIXRegimeGate | bar_time + VIX daily | `sigmoid((θ - vix)/scale)` | **vix_daily** |
| M6 | TrendStrengthGate | OHLC（ADX） | `sigmoid((ADX - θ)/scale)` | なし |

出力は全て `[0, 1]` bounded（sigmoid / step）。

### 非スコープ

- pair_specific primitive（P1-P12）は別 TODO
- event_calendar / vix_daily の ingest は既に T010 以前で完了（`src/events/`, `src/ingest/fred.py`）
- GA 側の local_gate slot 呼出し経路は既に T010 時点で integrated（dummy registry を撤廃する別 TODO で改修）

## 設計上の核心論点

### L1. EvaluationContext の外部データ注入方法

M4（event）・M5（VIX）は OHLC 以外のデータを参照する。現 `EvaluationContext` は以下:

```python
bars: Sequence[PriceBar]
idx: int
pair: str
params: Mapping[str, float | int]
aux_series: Mapping[str, Sequence[float]]  # 既存の補助時系列（長さ=bars）
```

**採用案**: `aux_series` は数値系列（既存の `macro.vix` bar-aligned serialized array 等）で
既に対応可能。ただし、**event_calendar は "時刻付き離散イベント列" で aux_series の
"bar-aligned float 列" 契約と合わない**。VIX daily は bar-aligned 配列化しやすい
（前営業日 close を M1 バーに forward-fill）ので aux_series で扱える。

結論: 後方互換の default field を追加する。ただし **as-of timestamp を必ず伴う専用 dataclass** で
注入し、primitive 側では「as-of <= bar_time」を検証してから参照する（look-ahead bias を
型で防ぐ）。

```python
@dataclass(frozen=True)
class EconomicEventSnapshot:
    """as-of <= bar_time までに既知のイベント予定/結果のスナップショット。"""
    calendar: EconomicCalendar
    as_of: datetime  # この時刻までに publication / 予定が既知

@dataclass(frozen=True)
class VixSeriesSnapshot:
    """as-of per date の VIX close。各 close は publication (16:15 ET) 以降にのみ既知。"""
    # {publication_ts_utc: vix_close}: publication_ts_utc は 16:15 ET の UTC 換算
    observations: tuple[tuple[datetime, float], ...]  # 昇順
    # lookup helper: bar_time より strictly 前に publication されたものから直近を返す

@dataclass(frozen=True)
class EvaluationContext:
    bars: Sequence[PriceBar]
    idx: int
    pair: str
    params: Mapping[str, float | int]
    aux_series: Mapping[str, Sequence[float]] = field(default_factory=dict)
    # --- T012 追加 (後方互換 default) ---
    event_snapshot: EconomicEventSnapshot | None = None
    vix_snapshot: VixSeriesSnapshot | None = None
```

- `event_snapshot.as_of`: backtest では各 bar_time ≤ as_of の条件下で evaluate する必要がある。
  concept 上は「backtest 全区間のカレンダーを as_of=+∞ で流すことで近似」する case が多い（予定は
  事前公開される性質）が、**設計書にこの仮定を明文化し、実装の compute では `event.event_time <= ctx.bars[ctx.idx].bar_time + window_after` までで絞る**ことで future-leak を防ぐ。
- `vix_snapshot.observations`: `(publication_ts_utc, vix_close)` の tuple 列。lookup は
  `publication_ts_utc < bar_time` の中で最新値を返す binary search（bisect_left）。UTC 日付ベースではなく **publication timestamp ベース**。
- None のときの挙動（Must-fix 対応）:
  - **primitive が実際に選択された（genome に含まれた）場合**の None は **hard warning + metric 露出**（一度だけログ、EvaluationResult meta に `gate_data_missing=True` を載せる）。safe default 値を返す経路は保持するが、silent fallback は avoid。
  - 選択されていない genome では None のままで OK（不要なデータロードを避ける）。
- Production path では `ensure_event_snapshot_coverage()` / `ensure_vix_snapshot_coverage()` を
  backtest entry で呼び、選択された primitive に必要なデータが揃っているかを fail-fast で検証。

**別案検討**: `aux_series` に `calendar.economic_event` key で event list を embed する案もあったが、
型が `Sequence[float]` と矛盾する（Mapping contract 破壊）ので却下。明示 field 追加が健全。

### L1-a. 注入経路（伝搬漏れ防止）

以下の 4 段を設計書に明記（zenigame 由来の re-occurring failure pattern への対処）:

1. **config / data loader**: `src/ingest/fred.py` の `MacroIndexDaily` から VIX 系列を読み出し、`VixSeriesSnapshot` を構築する helper（例: `src/alpha_factory/snapshots.py::load_vix_snapshot(session, start, end)`）。`src/events/repository.py::list_events_in_range` から `EconomicEventSnapshot` を構築する helper も同じファイル。
2. **RegistryEvaluator**: `__init__` に `event_snapshot` / `vix_snapshot` を受け付ける kwarg を追加（default None）。
3. **GA backtest entry**: Stage A/B/C の backtest runner が上記 helper を呼んで snapshot を構築し、RegistryEvaluator に渡す。
4. **tests**: fixture で mock snapshot を作り、primitive が snapshot 経由で値を引くことを verify。

### L2. M4 EconomicEventGate の参照方向

要件「high impact 指標発表 ±window 分を抑制」を満たすために各 bar で「その bar に最も近い high-impact イベントまでの |Δt|」を計算する必要がある。

**as-of semantics（明示）**:

- 予定イベント（scheduled announcements）は **event publication lead time が長い** ため、「bar_time の数日前にはスケジュール予定時刻が公開されている」が通常ケース。したがって、bar_time から見て **event_time が未来であっても、その event が "発表予定として bar_time 時点で既に公開されていた"** ものは参照可能（= no look-ahead）。
- しかし：
  - **actual 値**（発表後の数値）は絶対参照しない。M4 compute は event 予定時刻のみ使い、`EconomicEvent.actual` には一切触れない。
  - **schedule の追加 / 時刻変更**が bar_time 後に発生した event（ex-post rescheduled）は本来除外すべき。MVP では「backtest で使う calendar は全て `known_at <= bar_time`」という前提で動かし、この前提を docs/alpha_factory/primitives.md と `EconomicEventSnapshot` docstring に明記する。
  - 将来的に `EconomicEvent.known_at` / `schedule_published_at` を event row に追加する方向は別 TODO として切り出す（本 TODO 範囲外）。
- MVP 実装: compute は `|bar_time - event_time|` と window param で gate 値を計算。window 範囲外のイベントは参照しない（O(N) scan → 後続最適化可）。
- compute 内コメントと primitive docstring に「この primitive は schedule leakage を前提として避けていない。calendar の `known_at` 管理は別 TODO」を明記。

### L3. M5 VIXRegimeGate の look-ahead bias

VIX close は **米国市場 close (16:15 ET)** で確定し、FRED は当日中に observation を publish する。
M1 bar で使う場合、**publication timestamp ベース**で lookup する必要がある（日付ベースだと tz edge case で future leak する）。

採用方針:

1. **VIX publication timestamp 規約**: 各 VIX close observation の `publication_ts_utc` を「obs_date の 21:15 UTC」（16:15 ET; DST の悪化を保守側に取る）と定義。DST に厳密対応する必要が出たら別 TODO で修正（現状は保守的に 21:15 UTC 固定）。
2. **lookup 規約**: `publication_ts_utc < bar_time`（strict less than）を満たす observation の中で最新値を返す。bisect_left で O(log N)。
3. **欠損 / 週末 / 祝日**: 該当なしの場合は直近の publication_ts_utc 以前の観測に fall back。全て無しなら None を返し primitive は safe default（0.5）と metric 露出（前述 L1 参照）。
4. **境界例**: 火曜 00:30 UTC の bar → 月曜 21:15 UTC 以前の publication が最新 → 月曜 VIX close（これは正しく「bar_time 以前に既知の値」）。
5. **設計書と docstring への明記**: `publication_ts_utc = 21:15 UTC` という保守的固定規約と、DST に厳密対応しない保守的な選択の理由を記録する。

この方針で「UTC 日付 - 1」では回避できない「火曜 00:30 UTC bar で月曜 21:00 UTC の未確定 VIX を拾う」問題を回避できる。

### L4. M2 SessionGate の境界処理

F6 SessionMomentum の `_SESSION_RANGES_UTC = {0: (0,9), 1: (7,16), 2: (12,21)}` と同じ定義を
再利用（`_indicators.py` に切り出す or `modulator_generic.py` 内で再宣言）。

M2 は step 関数（該当 1.0 / 外 0.0）が基本だが、soft edge option として境界近傍で sigmoid にする
case があると GA の smoothness に寄与する。**MVP では step**、option `soft_edge_min=0` のとき
単純 step、`soft_edge_min>0` のとき sigmoid blend を適用する param を用意。

### L5. M3 スプレッド単位（Must-fix 対応）

`PriceBar.spread_close = ask.close - bid.close` は **価格単位**。ペアごとに pip_size が違うため
raw price で閾値比較すると EURUSD（4-5 桁小数点）と USDJPY（2-3 桁小数点）でスケールが 100 倍違う。
generic primitive としての不整合（cross-pair ii-lite での behavior 不一致）を防ぐため、**bps 正規化を MVP に含める**。

**採用規約**:

- `spread_bps = (ask.close - bid.close) / mid_close * 10_000` （basis points = 1/10_000 比率）
- 閾値 param は `threshold_bps`（float, default=2.0、range=[0.1, 20.0]）
- sigmoid steepness param `k`（float, default=1.0、range=[0.1, 5.0]）
- 出力: `1 / (1 + exp(k*(spread_bps - threshold_bps)))` → spread 小で 1 に近く、大で 0 に近い

mid_close は `(bid.close + ask.close) / 2`。両者 > 0 が保証される bar 前提（`_bars_to_mid_ohlc` と同じ規約）。

pip_size は pair ごとに違うが、bps 正規化は mid_close 相対比率なので pair 依存なし（ただし「1 pip ≈ N bps」の関係は pair ごとに違うので、param チューニングの解釈は別問題として docs に注記）。

後続 TODO で「pip 単位」「ADR 相対」などの正規化 option を GA param として切替可能にする余地は残す。

### L6. M6 TrendStrengthGate vs F4 ADXTrend

F4 は `tanh((ADX - 25) / scale) * sign(+DI - -DI)` で **directional** 出力（±1 bounded）。
M6 は方向を持たず **強度のみ gate**。`sigmoid((ADX - θ) / scale)` → `[0, 1]` 出力。category は
MODULATOR。param は `theta`（ADX threshold, default 25）/ `scale` / `n`（ADX 期間）。

## 共通仕様

- 出力は `[0, 1]` bounded（下限 0、上限 1、safe default は用途別に 0.5 / 1.0 / 0.0）
- `compute(ctx) -> float` / `compute_all_bars(ctx) -> np.ndarray`（長さ `len(ctx.bars)`、NaN は warmup / データ欠損）
- `required_data`:
  - M1 / M2 / M6: `("ohlc",)` — M2 は bar_time（時刻規約）のみで実データ依存なし（S3）
  - M3: `("ohlc", "spread")`
  - M4: `("ohlc", "calendar.economic_event")`
  - M5: `("ohlc", "macro.vix")`
- `category = "MODULATOR"`、`domain = "generic"`
- warmup 中は `np.nan`（`_make_compute_single` は NaN を 0.0 に吸収）

## look-ahead bias 対策

| ID | 参照するデータ | 対策 |
|----|----------------|------|
| M1 | ATR (past-only) | Wilder recurrence で過去参照のみ |
| M2 | bar_time | 自 bar の時刻のみ参照、完全 deterministic |
| M3 | spread at bar_time | 自 bar の close spread のみ |
| M4 | event_snapshot | `event.event_time` のみ参照（actual 値は参照しない）。calendar の `known_at` 管理は別 TODO、MVP では backtest 全量 calendar を as_of=+∞ 近似で使う前提を docstring に明記（L2） |
| M5 | vix_snapshot | **`publication_ts_utc < bar_time`** (strict) を満たす observation のみ bisect_left lookup。`publication_ts_utc = obs_date の 21:15 UTC` 保守固定（L3） |
| M6 | ADX (past-only) | Wilder recurrence で過去参照のみ |

## テスト戦略

既存 `test_directional_generic.py` の parametrize パターンを踏襲。

- `TestRegistryIntegration`: M1-M6 が registry に登録、合計 20 件になること
- `TestEachPrimitiveCommon (parametrize)`: `compute == compute_all_bars[idx]`, output bounded `[0, 1]`, no-lookahead property
- 個別テスト:
  - M1: sigmoid 単調性、方向 param の効き
  - M2: session 外 0、session 内 1（step）、soft_edge_min > 0 で境界が smooth
  - M3: spread が閾値より小 → 1 に近づく、大 → 0 に近づく
  - M4: event_snapshot=None → 1.0 constant + warning 発出、event 付近 → 0 に近づく、event 範囲外 → 1 に近づく
  - M5: vix_snapshot=None → 0.5 constant + warning 発出、低 VIX → 1 に近づく、高 VIX → 0 に近づく、`publication_ts_utc >= bar_time` の observation を混入させたテストで lookup が正しく排除することを verify
  - M6: ADX 小 → 0、ADX 大 → 1
- EvaluationContext 後方互換: `event_snapshot / vix_snapshot` を指定しないで既存 primitive（F1-F14）が動くこと

## 安全な default 挙動（Must-fix 対応）

外部データが無い（None）場合の挙動:

| ID | データ欠損時 | 設計意図 |
|----|--------------|----------|
| M4 | event_snapshot=None → 1.0 | 「イベント情報なしなら抑制しない」(pass through) |
| M5 | vix_snapshot=None or lookup 失敗 → 0.5 | 「VIX 不明なら neutral」 |

ただし **production evaluation path では silent fallback を避ける**:

- M4/M5 が genome で選択されているのに snapshot が None の場合、`warnings.warn` で一度だけ警告を出す（`stacklevel=2`、毎バー出さないため module-level `_warned` flag で制御）。
- 可能なら `EvaluationResult.meta` に `gate_data_missing={"M4": True}` のように露出し、post-run 監査で検出できるようにする。本 TODO では meta 追加は後続（dummy registry 廃止 TODO）に委ねるが、**warning は実装必須**。
- 追加で backtest runner 側で「選択された primitive の required_data に対応する snapshot が揃っているか」を起動時に verify する helper を提供（`ensure_event_snapshot_coverage` / `ensure_vix_snapshot_coverage`）。

この方針により L1 で言及した「safe default による伝搬漏れ隠蔽」を回避する。

## Should-consider 反映メモ

### S1. 監査 metric（trade_count / gate_active_ratio）

ゲート追加で「取引を削って見かけを良くする」failure mode を検出するため、**evaluation result に gate が active だった bar 比率**を出す仕組みを後続 TODO で議論。本 TODO は primitive 実装に focus。

### S2. MVP 範囲の切り分け

Codex review の指摘通り、M1/M2/M6（OHLC 内部系列のみ） と M4/M5（外部 snapshot）は hidden complexity が違う。

ただし本 TODO の上位 skill 指示は「**M1-M6 を 1 TODO で実装**」と明記されているため、本 TODO は 6 個をまとめて実装する。**実装中に複雑度が想定を超える兆候が出たら、M4/M5 を skip して別 TODO に切り出す判断ポイントを impl フェーズの中間チェックとする**。

具体的には:

- Phase 1: M1 / M2 / M6 / M3（外部 snapshot 不要、スケール正規化のみ）を先に実装 + テスト
- Phase 2: M4 / M5（外部 snapshot 必要）を追加実装
- Phase 1 までで merge 不可能なほど問題が噴出したら、Phase 2 を別 TODO（T013）に切り出して T012 を Phase 1 のみで close

### S3. M2 の required_data 命名

M2 は実データ依存ではなく bar_time（時刻規約）のみ参照。`required_data=("ohlc",)` に簡素化。
`calendar.session` Literal は registry の canonical 語彙に残しておくが、M2 では使わない。

## 関連 TODO / dependencies

- T010 / T011（merged, `b3268d5`）
- FRED VIXCLS ingest（`src/ingest/fred.py`, `003_macro_index_daily.py`）完了済
- economic events ingest（`src/events/`）完了済
- dummy registry 撤廃（T010-d 系の移行 TODO）は本 TODO と直交（本 TODO merged 後でも対応可）

## Definition of Done

- [ ] `src/alpha_factory/primitives/modulator_generic.py` (M1-M6 + ensure_registered)
- [ ] `_base.py` に `EconomicEventSnapshot` / `VixSeriesSnapshot` dataclass を新設（or `src/alpha_factory/snapshots.py` に分離）し、`EvaluationContext` に `event_snapshot=None` / `vix_snapshot=None` default 追加（後方互換）
- [ ] `_registry.py::ensure_registered` が modulator_generic も bootstrap
- [ ] 6 primitive すべて registry 登録、`MODULATOR` count=6, 合計 20
- [ ] `tests/alpha_factory/primitives/test_modulator_generic.py` で個別 + parametrize + no-lookahead property + snapshot 注入テスト
- [ ] 既存 T011 テスト全件通過（後方互換）
- [ ] `docs/alpha_factory/primitives.md` の Modulator 節に詳細テーブル追記
- [ ] 伝搬漏れ検知の担保: snapshot None + primitive 選択時の `warnings.warn` を test で verify（unittest の `pytest.warns` で捕捉）。`EvaluationResult.meta` への露出は後続 TODO だが、warning は本 TODO で必須
