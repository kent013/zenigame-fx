# 概念設計: aux data loader Phase 2 — 実データ取得 + production wiring（Codex Round 1 指摘反映版）

## 0. 前提検証表（C4）

| # | 前提 | 状態 | 根拠 |
|---|---|---|---|
| P1 | 32 primitive のうち **9 個（28%）が定数信号化**（P5/P7/P8/P9/P10/P11/P12 + M4/M5） | **verified** | /tmp/ga-run-26.log の RuntimeWarning 集計 |
| P2 | T046 / T047 は close 済（Phase 1 scaffold + API） | **verified** | TODO-closed.md L51-52 |
| P3 | Phase 1 で `aux_loader.py` 公開 API（`AuxBundle` / `build_aux_bundle` 等）が揃っている | **verified** | コード読解 |
| P4 | `scripts/fetch_fred.py` の DEFAULT_SERIES に Gold / WTI / Copper / SPX500 は未含 | **verified** | コード読解 |
| P5 | `run_ga.py:1145` の `RegistryEvaluator` で aux 引数全部 None | **verified** | コード読解 |
| P6 | `data/raw/` フォルダは空 | **verified** | `ls data/raw/` |
| P7 | aux_series は **bars 数 N と同じ長さに per-bar align** されてる必要あり（`_check_aux_series_length`） | **verified** | pair_specific.py:170 |
| P8 | aux_pair_bars は **bar_time strict 一致**で fail-fast | **verified** | pair_specific.py:95-105 |
| P9 | run_ga.py は **bars_60d (Stage A) / bars_18m (Stage B) / bars_holdout (Stage C) の 3 系列**を同じ evaluator で扱う | **verified** | run_ga.py の lane 構造 |
| P10 | FRED 経路が DB（`scripts/fetch_fred.py` upsert）と CSV（`aux_loader._read_csv_dict`）で **二重化**している | **verified** | コード読解（aux_loader 側は CSV 直読み） |
| P11 | 既存 `aux_series` は `list[float]`、`aux_pair_bars` は `Sequence[PriceBar | None]` | **verified** | aux_loader.py 型定義 |
| P12 | FRED API は `realtime_start` フィールドを持つ（公表時刻管理可能） | **unverified** | 実装時に確認、要調査 |

---

## 1. 背景・課題（再掲）

run-26 RUN log で 9 primitive が safe default 経路（per-bar 数万回）で動作。T046/T047 で API は揃っているが production への実データ注入経路が未完。本 TODO は Phase 2 全体（実データ取得 + 注入経路 + 契約整備）を完成させる。

---

## 2. 設計の柱（Codex Round 1 Critical / Warning 全反映）

### 2.1 [Critical 1 反映] AuxBundle = raw container、stage 別に align する設計

**問題**: 1 evaluator で Stage A (60d=86400 bars) / B (18mo=183403 bars) / holdout (60d=86400 bars) を扱う場合、aux_series 長さが bars に合わない（`_check_aux_series_length` で fail）。

**解決**: `AuxBundle` を **raw データ container** として再設計し、stage 別 bars が来た時点で `align_to(bars)` で per-bar 展開した `AlignedAuxBundle` を作る:

```python
# AuxBundle: raw データ保持
@dataclass
class AuxBundle:
    """Raw container — stage 別 bars に align される前の状態。"""
    daily_series: dict[str, DailySeriesObservation]   # 各 macro series
    event_calendar: EconomicCalendar | None           # raw events list
    aux_pair_bars_index: AuxPairBarsIndex             # bar_time → PriceBar の dict
    
    def align_to(self, bars: Sequence[PriceBar]) -> AlignedAuxBundle:
        """指定 bars に per-bar align した bundle を返す。"""
        ...

# AlignedAuxBundle: bars と同じ長さに整列済
@dataclass(frozen=True)
class AlignedAuxBundle:
    aux_series: dict[str, np.ndarray]                 # ndarray[float64]、bars と同長
    event_snapshot: EconomicEventSnapshot | None      # bars[-1].bar_time が as_of
    vix_snapshot: VixSeriesSnapshot | None            # 同上
    aux_pair_bars: dict[str, list[PriceBar | None]]   # bars と同長、bar_time strict 一致
```

`run_ga.py` での使い方:
```python
aux_raw = build_aux_bundle(...)  # raw load 1 回

# Stage A 評価時
aux_a = aux_raw.align_to(bars_60d)
evaluator_a = RegistryEvaluator(pair=..., **aux_a.as_evaluator_kwargs())

# Stage B 評価時
aux_b = aux_raw.align_to(bars_18m)
evaluator_b = RegistryEvaluator(pair=..., **aux_b.as_evaluator_kwargs())
```

**1 evaluator → 複数 evaluator** の変更（lane アーキテクチャと整合させる）。

### 2.2 [Critical 2 + Round 2 Critical 反映] macro daily series の `effective_from_utc` 契約（保守的 policy）

**問題**: `expand_daily_to_bars` の「前日 close」だけでは look-ahead 漏洩リスク（公表時刻 / 改定遅延 / UTC 境界）。

**Round 2 [Critical] 追加反映**: FRED API の `realtime_start` は「リビジョン有効日」で「当日その値が市場で利用可能になった時刻」とは異なる場合あり。series 固有時刻を FRED だけで一意復元できる保証はない。

**解決**: daily series は `(observation_date, value, effective_from_utc, source)` の 4 列で管理。`effective_from_utc` は **2 種類のソース**から決まり、`source` 列で区別:

```python
@dataclass(frozen=True)
class DailyObservation:
    observation_date: date
    value: float
    effective_from_utc: datetime  # tz-aware UTC
    source: Literal["fred_realtime_start", "policy_conservative"]
    # "fred_realtime_start": FRED API の realtime_start を直接採用（信頼度高）
    # "policy_conservative": observation_date + 保守的 lag（series 別）

# Phase 2 の既定: 全 series で policy_conservative を採用（保守側）
# series 別の厳密時刻（fred_realtime_start 採用）は別 TODO で昇格
SERIES_POLICY_CONSERVATIVE = {
    "VIXCLS":            {"lag_hours": 24},  # observation_date 翌日 00:00 UTC
    "DTWEXBGS":          {"lag_hours": 24},
    "GOLDPMGBD228NLBM":  {"lag_hours": 24},
    "DCOILWTICO":        {"lag_hours": 24},
    "PCOPPUSDM":         {"lag_hours": 24 * 35},  # 月次は 35 日 lag
    "PALLFNFINDEXM":     {"lag_hours": 24 * 35},
    "SP500":             {"lag_hours": 24},
}
```

`align_to(bars)` での展開:
- `bar.bar_time >= obs.effective_from_utc` を満たす最新の obs を採用
- 該当 obs が無い（warmup）→ 0.0 / NaN policy（series 別）
- look-ahead test: `bar.bar_time < obs.effective_from_utc` の obs を絶対に使わない
- 保守側に倒すため、daily 系列は **observation_date 翌日 00:00 UTC まで利用不可**（lag_hours=24）。一部月次系列は **35 日 lag** で改定遅延を吸収

**運用方針**: Phase 2 では保守的 policy を採用。FRED API `realtime_start` ベースの厳密時刻昇格は別 TODO（実 API 検証後）。

### 2.3 [Critical 3 + Round 2 Warning 反映] preflight check + strict_aux_required + hard/soft required 分離

**問題**: `strict_aux_required=False` のままでは「定数信号悪用解消」を主張できない。

**Round 2 [Warning] 反映**: preflight required を一律固定すると意図せず RUN 全停止になる。**hard_required** と **soft_required** に分離:

```python
# preflight required 定義
HARD_REQUIRED_AUX = {
    "macro.vix":         "VIXCLS",         # M5, P7 が必須依存
    "macro.dxy":         "DTWEXBGS",       # P11 が必須依存
    # その他 P5 用 EUR_USD/USD_JPY M1 bars も hard_required
}

SOFT_REQUIRED_AUX = {
    "macro.gold":              "GOLDPMGBD228NLBM",   # P12 のみ依存
    "macro.wti":               "DCOILWTICO",         # P9 のみ依存
    "macro.copper":            "PCOPPUSDM",          # P8（or commodity_index）
    "macro.commodity_index":   "PALLFNFINDEXM",      # P8（or copper）
    "macro.spx500":            "SP500",              # P7（or vix_snapshot）
    "events_calendar":         None,                  # P10, M4 が依存（partial coverage 許容）
}
```

**解決**:
- `run_ga.py` startup で preflight check 実装
- **hard_required 不足 → fail-closed**（run 開始前 reject）
- **soft_required 不足 → WARN log + 該当 primitive は safe default 経路で動作**（pessimistic だが GA は他 primitive を使える）
- **動的化** (Round 2 反映): preflight required を「**今回 register された primitive の required_data の和集合**」に動的連動させる選択肢も検討（実装時に primitive registry の reflection で取得）
- override: `--allow-aux-missing` flag（hard_required も soft 扱いにする、開発専用）
- `strict_aux_required` は **hard_required に対してのみ default True**

**preflight ログフォーマット**:
```
preflight.aux_data_check
  hard_required: ["macro.vix", "macro.dxy", "EUR_USD_M1", "USD_JPY_M1"]
  hard_satisfied: ["macro.vix", "macro.dxy"]
  hard_missing:   ["EUR_USD_M1"]   → FAIL
  soft_required: ["macro.gold", "macro.wti", ...]
  soft_satisfied: ["macro.gold"]
  soft_missing:   ["macro.wti", ...]   → WARN, primitive will use safe default
```

### 2.4 [Warning 1 反映] FRED SSOT 一本化（DB 経由）

**問題**: `fetch_fred.py` は DB upsert、`aux_loader.py` は CSV 直読み → 二重経路。

**解決**: aux_loader を **DB reader 経由** に統一。CSV 直読みは test fixture 用にのみ残す:

```python
def load_aux_series(
    *,
    db_session: Session,
    series_ids: Sequence[str],
    period: tuple[datetime, datetime],
) -> dict[str, list[DailyObservation]]:
    """DB の fred_observation テーブルから series を読み出す。
    period (start, end) で filter、effective_from_utc を含む。
    """
```

既存の DB schema に `effective_from_utc` 列を追加する migration が必要（Critical 2 と連動）。

### 2.5 [Warning 2 反映] aux_pair_bars の misalign vs 欠番分離

```python
def load_aux_pair_bars(
    *,
    target_bars: Sequence[PriceBar],
    aux_pairs: Sequence[str],
    db_session: Session,
) -> dict[str, list[PriceBar | None]]:
    """aux pair の bars を bar_time index で取得。
    
    - **欠番**（該当 bar_time の aux pair bar が DB に存在しない）→ None で padding
    - **misalign**（aux pair bar の bar_time が target と微小ずれ）→ ValueError fail-fast
    
    DB から取得後 dict[bar_time, PriceBar] を作って target_bars をループし、
    完全一致のみ採用、不一致は raise（broker 側 primitive の既存契約と整合）。
    """
```

### 2.6 [Warning 3 反映] aux_series を numpy ndarray に変更

`aux_series: dict[str, list[float]]` → `aux_series: dict[str, np.ndarray]` (`dtype=float64`)。

primitive 側 (`pair_specific.py:170`) は `len(spx) == n` でしか check していないので、`ndarray.shape[0] == n` でも互換。ただし要 grep で他の使用箇所確認（`spx[i]` のような indexing は ndarray でも同じ動作）。

`aux_pair_bars` は **PriceBar object のままで保持**（broker primitive 内で attribute access が多く、numeric array 化は別 TODO）。

### 2.7 [Warning 4 反映] events.csv は partial coverage 明記

events.csv 30 件手動整備では P10/M4 は **partial coverage**。期待効果から「fully recovered」を削除、partial と明記。

将来 TODO（別途）: forex factory / OANDA Calendar API / FRED releases endpoint からの自動取得。

---

## 3. 施策一覧（再構成、9 施策）

| # | 施策 | 担当ファイル / モジュール |
|---|---|---|
| 1 | AuxBundle / AlignedAuxBundle の re-design（raw container + align_to） | `src/alpha_factory/aux_loader.py` |
| 2 | DailyObservation + effective_from_utc 契約 | `src/alpha_factory/aux_loader.py` / DB migration |
| 3 | FRED SSOT 一本化（aux_loader を DB reader 化） | `src/alpha_factory/aux_loader.py` / `src/ingest/fred.py` |
| 4 | scripts/fetch_fred.py の DEFAULT_SERIES 拡張 + effective_from_utc 取得 | `scripts/fetch_fred.py` |
| 5 | aux_pair_bars DB loader（欠番 None / misalign fail-fast） | `src/alpha_factory/aux_loader.py` |
| 6 | events.csv 30 件 scaffold + load_economic_events 動作確認 | `data/raw/calendar/events.csv` / `scripts/load_economic_events.py` |
| 7 | run_ga.py preflight check + stage 別 evaluator 注入 + strict_aux_required default True | `scripts/alpha_factory/run_ga.py` / `config/alpha_factory/default.yaml` |
| 8 | aux_series を numpy ndarray に変更 + primitive 側互換確認 | `src/alpha_factory/aux_loader.py` / `src/alpha_factory/primitives/pair_specific.py`（最小変更） |
| 9 | AGENTS.md / runbook.md / fetch_aux_data.sh wrapper | docs / scripts |

---

## 4. 期待効果

### 4.1 機能目標（必須）

- 9 primitive のうち **7 個（P5/P7/P8/P9/P11/P12 + M5）が本来の機能で動作**（aux daily series + aux_pair_bars 整備で）
- **P10 / M4 は partial coverage**（events.csv 30 件で部分的に動作、自動取得は別 TODO）
- preflight で aux 不足時は run 開始前 fail（定数信号悪用が **構造的に不可能**になる）
- strict_aux_required=True により、実行時に safe default に落ちる経路が **構造的に閉じる**

### 4.2 副次効果

- GA selection で primitive 利用頻度の偏りが緩和
- T039 (as_of_strict) が production で有効化可能な状態に
- live_criteria 達成への到達経路が改善

### 4.3 性能目標（INCONCLUSIVE）

- numpy ndarray 化で aux lookup が高速化
- preflight overhead は 1 回のみ（無視可能）
- per-bar の影響は実測で確認（cProfile）

---

## 5. 制約・前提

### 5.1 数値・絶対制約

- look-ahead bias 厳禁: `effective_from_utc` ベースで availability 制約、test で「未来データ参照」のシナリオを必ず fail させる
- aux_pair_bars: bar_time strict 一致（misalign は fail-fast、欠番のみ None padding）
- T039 as_of_strict 整合: event_snapshot の as_of_strict は preflight check で True を要求
- T053-T056 の数値同値性: aux 不在時の既存 RUN との bit-exact 比較は維持（aux ありの新 RUN との比較は対象外、信号値が変わるため）

### 5.2 後方互換

- `aux_loader.py` の **既存公開 API は signature 変更**（`build_aux_bundle` の戻り値が `AuxBundle` → `AuxBundle (raw)`、`align_to` で `AlignedAuxBundle` 化）
- 既存テスト（CSV fixture 経由のテスト）は新 API に合わせて更新（test 移行ガイド付与）
- `RegistryEvaluator` は signature 維持（`AlignedAuxBundle.as_evaluator_kwargs()` で展開）

### 5.3 禁止事項の遵守

- live_criteria 緩和なし
- 評価期間延長なし
- aux データ look-ahead 漏洩は厳禁
- 過度な複雑化禁止: events 自動取得 / 多通貨 cross-pair / cron は別 TODO 分離

### 5.4 メモリ制約

- aux_series 7 × 86400 × 8B = 4.8 MB（ndarray packed）→ list 比 5-10x 削減
- aux_pair_bars 2 × 86400 × ~200B (PriceBar) = 34 MB → 別 TODO で numeric 化
- 6 worker × 200 MB 追加 = 3GB/worker 制約に対し 6.7%、許容内

---

## 6. スコープ外（別 TODO 候補）

- events.csv の自動取得（forex factory / FRED releases / OANDA Calendar API）
- 多通貨 cross-pair bars 拡張（GBP_USD / AUD_USD 等）
- aux_pair_bars の numeric array 化（メモリ最適化）
- aux データの cron 自動更新
- T046 / T047 の close 済み TODO の再評価（運用 review）
- macro daily series の改定 (revision) 対応（FRED は historical revision あり、本 TODO は最新 revision 採用で割切る）

---

## 7. 検証計画（概要、詳細設計で具体化）

| # | 項目 | 合格基準 |
|---|---|---|
| V1 | 既存テスト全パス | `uv run pytest tests/alpha_factory/ tests/backtest/ tests/dsl/ tests/broker/ -x` |
| V2 | look-ahead bias なし（必須、Critical 2 対応） | `align_to()` test で「未来 obs を参照しようとすると fail」シナリオを assert（4 ケース: UTC 日付境界 / 週末跨ぎ / 祝日連休 / dataset 開始直後 warmup） |
| V3 | aux_pair_bars misalign vs 欠番分離（必須、Warning 2 対応） | misalign は ValueError fail-fast、欠番は None padding（test で両ケース） |
| V4 | preflight check（必須、Critical 3 対応） | required aux 不足時に run 開始前 fail。`--allow-aux-missing` で override 可能 |
| V5 | stage 別 alignment（必須、Critical 1 対応） | bars_60d / bars_18m / bars_holdout で `align_to` がそれぞれ正しい長さの aux_series を返す |
| V6 | strict_aux_required default True で実行時 safe default 経路が走らない | RuntimeWarning が **0 件**（preflight 通過後の run で） |
| V7 | numpy ndarray 化の primitive 互換 | 既存 `_check_aux_series_length` が `np.ndarray` でも fail せず動作 |
| V8 | events.csv partial coverage の明示 | runbook に「P10/M4 は 30 件手動整備で部分カバー」明記、自動取得は別 TODO |
| V9 | ruff / mypy 通過 | 既存 baseline 維持 |
| V10 | 統合 smoke test | 小規模 RUN（pop=2, gen=1）で aux 完備の状態で `RuntimeWarning` 0 件 |

---

## 8. Phase 2 の規模に関する判断 + Acceptance Gate（Round 2 Warning 反映）

Codex Round 1 は Phase 2a/b/c 分割を Suggestion として提示したが、ユーザー方針「最後まで行って」に従い **本 TODO で全 9 施策を完成**させる。

**Round 2 [Warning] 反映**: 1 TODO のまま、acceptance を以下の **3 段階 Gate** に固定する:

### Gate A: 契約完成（施策 1-2）
- AuxBundle / AlignedAuxBundle re-design 完成
- DailyObservation + effective_from_utc 契約完成
- 既存テスト全パス、新規 unit test (V2 look-ahead, V5 stage 別 alignment) PASS
- **A 通過後に B 着手**

### Gate B: wiring 完成（施策 3-7、ただし strict 化はまだしない）
- aux_loader DB reader 化、fetch_fred 拡張、aux_pair_bars loader 完成
- run_ga.py の preflight + stage 別 evaluator 注入、ただし `strict_aux_required: false` 維持（safe default 経路で動作）
- 既存テスト全パス、統合 smoke test (V10 pop=2/gen=1) で run 完走
- **B 通過後に C 着手**

### Gate C: strict 化（施策 7 後半 + 8 + 9）
- strict_aux_required=true への切替、preflight hard_required で fail-closed
- aux_series numpy ndarray 化
- 運用ドキュメント完成
- 本番相当 RUN（pop=8, gen=2 程度）で hard_required の `RuntimeWarning` **0 件**達成
- **Round 3 [Warning] 反映**: 以下も Gate C 判定基準に追加
  - **「実際に選択・評価された primitive の required_data 充足率」を Gate C で観測**（archive Parquet から primitive 選択頻度 × required_data 充足を集計、低充足の primitive は GA selection で多用されないことを確認）
  - **series ごとの finite coverage / stale rate の監視**: Gate B で取得した daily series ごとに「dataset 期間中に non-stale 値が利用可能だった比率」を計測、月次系列 lag=35日で stale 率が極端に高い場合（例: 80% 超）は判定失敗 → policy 見直し
- **C 通過 = 本 TODO 完了**

各 Gate で commit を分け、Gate 単位で revert 可能性を保つ。実装規模は中-大（想定 3-5 日）。
