# 詳細設計: Stage B gate redesign — noise-floor 整合化 + trade_count scale 整合化

**改版**:
- v1 (2026-05-08 12:30 JST): 初版
- v2 (2026-05-08 12:50 JST): Codex detailed-review Round 2 (CHANGES_REQUESTED) を反映
  - 施策 3 (DSR) を Phase 1 から **Phase 2 に移動** (Codex Critical: 数式 kurtosis 定義 / V[SR] / valid 条件の誤実装が monitor only でも誤データ蓄積リスク)
  - 施策 1: テストを Monte Carlo から決定的計算に変更 (非 flaky 化)
  - 施策 2: T044 「Stage A 値固定」 契約遵守 (旧 `trade_count` 列に書かない)、 NaN/pd.NA fallback helper、 IndividualCacheEntry constructor で trade_count_full_dataset 値を必ず渡す、 コスト見積を Stage B bars 数で再計算
  - 施策 4: smoke_test を flush の明示引数に、 RunContext 経由で archive marker 全 row 注入、 graduate / calibrate / report に直接 marker を渡す、 np.bool_ 正規化、 report 名を `SMOKE-run-X.md`

**概念設計**: `devnotes/20260508-1203-stage-b-gate-redesign/conceptual-design.md` (v2 APPROVED at Round 3)

---

## 使命・制約 (絶対遵守)

### zenigame-fx Alpha Factory 使命

`config/alpha_factory/default.yaml.live_criteria` 全指標同時充足 + Stage C pass + cross-pair (ii-lite) pass で使命達成。
絶対制約: イントラデイ前提 / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項 (関連)

- **1**: A・B・C 評価期間延長禁止 → 本設計は閾値・selection 整合化のみ、 期間は触らない
- **4**: live_criteria 緩和禁止 → live_criteria.sharpe_min / trade_count_min は変更しない (Stage B gate 内部閾値のみ)
- **5**: 過度な複雑化禁止 → NSGA-II 等は本設計範囲外、 incremental 4 段適用
- **8**: archive schema 値伝搬漏れ禁止 → 4 点セット (GENOMES_SCHEMA + _create_row_template + collect_stage_* + flush) 全て検証

### コーディングルール

- **テストファースト**: 各施策で `tests/alpha_factory/` に行動説明的なテスト追加
- **uv 必須**: `uv run pytest tests/alpha_factory/` / `uv run ruff check src/ tests/` / `uv run mypy src/`
- Python 3.13 + numpy + pandas
- 24GB マシン × 6 worker (1 worker 最大 3GB)

---

## 概念設計リファレンス

`devnotes/20260508-1203-stage-b-gate-redesign/conceptual-design.md` (v2)

主要決定 (概念設計より):
1. `stage_b_median_oos_sharpe_min: 0.05 → 0.025` (検出力 50% → 60%)
2. DSR per-fold 計算 (Bailey & López de Prado 2014)、 N=同一 RUN Stage A pass 個体数、 monitor only
3. `trade_count_full_dataset = stage_a_unique + stage_b_full_unique` (canonical 定義、 fold 合算禁止)
4. `stage_partition_guard` に holdout_days 検証 + 二重 opt-in escape hatch

---

## 施策一覧 (v2: DSR を Phase 2 に移動)

| # | 施策名 | 変更ファイル | 優先度 |
|---|---|---|---|
| 1 | median_oos_sharpe_min 閾値変更 + 設計コメント | `config/alpha_factory/default.yaml`、 `src/alpha_factory/stage_gate.py` | High (replay 検証で graduate 候補確定) |
| 2 | trade_count_full_dataset 列追加 + selection 切替 | `src/alpha_factory/archive.py`、 `src/alpha_factory/stage_a_evaluator.py`、 `src/alpha_factory/stage_gate.py`、 `scripts/alpha_factory/run_ga.py`、 `src/alpha_factory/config.py` | High (selection 圧整合化) |
| 3 | stage_partition_guard holdout_days 検証 + 二重 opt-in | `src/alpha_factory/stage_partition_guard.py`、 `scripts/alpha_factory/run_ga.py`、 `src/alpha_factory/archive.py`、 `src/alpha_factory/run_context.py` | Medium (smoke override 安全弁) |
| ~~4~~ | ~~DSR per-fold 計算~~ → **Phase 2 に移動** | (Phase 2 別タスク) | - |

**実装順序** (Codex Round 2 Suggestion + Round 2 review 反映): **1 → 2 → 3** (元の施策 4 が新施策 3、 DSR は Phase 2)。

**DSR を Phase 2 に移動した理由** (Codex detailed-review Round 2 [Critical] 3 件):
- DSR 数式: kurtosis 定義 (Pearson vs Fisher excess) と分母 (1 + 0.5×SR² と 1 - skew×SR + ((kurt-1)/4)×SR² の整合性) が誤実装の risk
- V[SR] が trial 間分散 (Bailey & López de Prado 2014 の DSR 定義) ではなく fold 間分散になっている可能性
- valid 条件が「全 fold skew/kurt 有限」 を保証できていない
- monitor only でも誤った archive データを蓄積し、 Phase 2 hard gate 化時に誤った根拠データとして使われる副作用

→ Phase 2 で別タスクとして DSR 単独設計を実施。 Bailey & López de Prado (2014) の正規実装と V[SR] / kurtosis 定義の精査をその時に行う。 Phase 1 では archive `dsr` 列を null のまま維持。

---

## 施策 1: median_oos_sharpe_min 閾値変更 + 設計コメント

### 変更箇所

- ファイル: `config/alpha_factory/default.yaml` (stage_gate.stage_b)
- ファイル: `src/alpha_factory/stage_gate.py` (`StageGateConfig.stage_b_median_oos_sharpe_min` のデフォルト値とコメント、 line 400-405)

### 波及変更

- `AGENTS.md`: なし (内部閾値変更で運用コマンド変化なし)
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: 閾値変更 + 設計コメント追加
- `docs/alpha_factory/sharpe-rescale.md`: 検出力計算の明記追加 (post-Phase 1 update)
- `docs/alpha_factory/stage-gates.md`: stage_b_median_oos_sharpe_min の根拠更新

### 現行コード

`config/alpha_factory/default.yaml`:
```yaml
stage_b:
  ...
  median_oos_sharpe_min: 0.05  # trade-level (T042 再校正)
```

`src/alpha_factory/stage_gate.py:400-405`:
```python
# T042 Phase 0: trade-level スケール (per-fold trade_sharpe_raw との比較)。
# 旧 0.20 は v1 bar-level 想定の legacy 値。Run 14-16 archive replay
# (reports/sharpe-rescale/) で trade-level 分布が 0.05〜0.19 中央域だったため
# 0.05 へ再校正した。詳細: docs/alpha_factory/sharpe-rescale.md
stage_b_median_oos_sharpe_min: float = 0.05
```

### 変更後コード

`config/alpha_factory/default.yaml`:
```yaml
stage_b:
  ...
  # @cycle_phase1 (2026-05-08): 0.05 → 0.025 (Stage B gate redesign Phase 1).
  # Lo (2002) "The Statistics of Sharpe Ratios" SE 公式に基づく検出力整合化:
  #   per-fold SE ≈ √((1 + 0.5×SR²)/N), N=stage_b_fold_trade_count_min=10 → SE ≈ 0.32
  #   10-fold median SE ≈ 0.32/√10 ≈ 0.10
  #   真値 SR=0.05 個体の median 推定値が >=0.025 になる確率:
  #     z = (0.025 - 0.05)/0.10 = -0.25
  #     P ≈ Φ(0.25) ≈ 60% (vs 0.05 維持時 50%)
  # = 「真値 0.05 個体の検出力 50% → 60% への保守的拡張」
  # 緩和ではなく noise-floor 整合化 (禁止事項 4 抵触なし、 Stage B gate 内部閾値のみ、
  # live_criteria.sharpe_min は不変)。
  # 検証根拠: run-52 archive (genomes_run_20260507_112309.parquet) で
  # mission-eligible 個体 7 件全員が median_oos_sharpe<min で blocked。
  # 詳細: devnotes/20260508-1203-stage-b-gate-redesign/conceptual-design.md
  median_oos_sharpe_min: 0.025
```

`src/alpha_factory/stage_gate.py:400-405`:
```python
# T042 Phase 0 → Phase 1 (cycle_phase1, 2026-05-08): trade-level スケール。
# 旧 0.20 (bar-level 想定) → 0.05 (Run 14-16 replay 校正) → 0.025 (検出力整合化)。
# Lo (2002) SE 公式: 10-fold median SE ≈ 0.10 → 0.025 で真値 SR=0.05 検出力 60%。
# 詳細: docs/alpha_factory/sharpe-rescale.md / config/alpha_factory/default.yaml
stage_b_median_oos_sharpe_min: float = 0.025
```

### テスト計画 (Round 2 [Warning] 反映: 非 flaky 化)

- [ ] **既存テスト確認**: `tests/alpha_factory/test_stage_gate.py` で `stage_b_median_oos_sharpe_min` のデフォルト値が 0.05 で hard-coded されている箇所を 0.025 に更新
- [ ] **新規テスト (主)**: `test_stage_b_median_threshold_at_noise_floor_deterministic` — Lo (2002) 近似式の **決定的な数値検証**:
  - SE_per_fold = √((1 + 0.5×0.05²)/10) ≈ 0.3163
  - SE_median_10folds = SE_per_fold / √10 ≈ 0.1000
  - z = (0.025 - 0.05) / 0.1000 = -0.25
  - P(estimate >= 0.025) ≈ scipy.stats.norm.cdf(0.25) ≈ 0.5987
  - assert 0.59 <= P <= 0.61 (決定的、 flaky なし)
- [ ] **新規テスト (補助、 任意 skip 可)**: `test_stage_b_median_monte_carlo_sanity` — synthetic fold sharpes (seed=42) で Monte Carlo 1000 trial、 median >= 0.025 の割合が 0.55-0.65 内 (広い許容幅、 flaky 防止)
  - `pytest.mark.skip_unless_env("RUN_MONTE_CARLO_TESTS")` でデフォルト skip
- [ ] **archive replay test**: `test_run_52_archive_replay_with_lower_median_fixture` — run-52 archive の `(stage_a_pass=True) AND (positive_fold_ratio_effective>=0.6) AND (stage_b_reason_codes に positive_fold_ratio<min を含まない)` 個体について、 fixture data 上で median_oos_sharpe>=0.025 を満たす個体が 1+ 件存在することを **ordering regression test** として verify
  - **conditioning set 明示**: Stage A pass + pfre>=0.6 + reason_codes に positive_fold_ratio<min を含まない
  - **claim 制限**: 「特定 fixture 上での再分類確認」 のみ、 一般化 claim はしない (C3 collider bias / C7 sample size 遵守)

### リスク

- **副作用**: 0.025 を満たす個体が増えるため Stage B pass 数が膨らむ。 推定 +10〜+30% (run-52 archive 個別観察、 一般化 claim はしない)
- **後退リスク**: positive_fold_ratio_min=0.6 の AND 条件があるため、 noise-driven survivor の追加 admission は限定的 (low-trade survivor は positive_fold_ratio で別途 filter)
- **Codex Round 2 Warning 残**: replay で 0 件 pass の場合は仮説 H_A1' を反証 → Phase 2 で別の根因を探る
- **非 flaky 化**: Monte Carlo simulation を主テストにせず、 決定的な scipy.stats.norm.cdf 計算で確率を verify

---

## 施策 2: trade_count_full_dataset 列追加 + selection 切替

### 変更箇所

- ファイル: `src/alpha_factory/archive.py` (GENOMES_SCHEMA, _create_row_template, collect_stage_a/b)
- ファイル: `src/alpha_factory/stage_gate.py` (evaluate_stage_b で full-pass backtest 追加)
- ファイル: `scripts/alpha_factory/run_ga.py` (IndividualCacheEntry, _update_cache, selection)
- ファイル: `src/alpha_factory/config.py` (config loader)
- ファイル: `scripts/alpha_factory/generate_run_report.py` (report レンダリング)

### 波及変更

- `AGENTS.md`: archive 列定義の説明 1 行追加
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: なし (動作デフォルト変更だが新 config key は追加しない)
- `docs/alpha_factory/stage-gates.md`: trade_count_full_dataset の canonical 定義を SSOT として明記

### archive schema 拡張 (4 点セット)

#### (1) GENOMES_SCHEMA 追加列

`src/alpha_factory/archive.py:68-146` の `GENOMES_SCHEMA = pa.schema([...])` に追加:

```python
# === 新規追加 (cycle_phase1 / Stage B gate redesign) ===
# trade_count_stage_a: Stage A 60日 backtest unique entry count (= 旧 trade_count と同等)
pa.field("trade_count_stage_a", pa.int32(), nullable=True),
# trade_count_stage_b: Stage B 全期間 (~67日) を 1 pass で再評価した unique entry count
pa.field("trade_count_stage_b", pa.int32(), nullable=True),
# trade_count_full_dataset: stage_a + stage_b unique 合算 (selection feasibility 用)
pa.field("trade_count_full_dataset", pa.int32(), nullable=True),
```

**重要**: 既存 `trade_count` (pa.int32, nullable=False) は **維持** (後方互換)。 新列は **null 許容で追加**。

#### (2) _create_row_template デフォルト

```python
"trade_count_stage_a": None,
"trade_count_stage_b": None,
"trade_count_full_dataset": None,
```

#### (3) collect_stage_a 書き込み (T044 「Stage A 値固定」 契約遵守)

`src/alpha_factory/archive.py` の `collect_stage_a` 内 `row["trade_count"] = _required_int(payload, "trade_count")` の直後:

```python
# T044 既存契約: trade_count は Stage A 値で固定、 Stage B/C で上書きしない (現行維持)
row["trade_count"] = _required_int(payload, "trade_count")
# cycle_phase1 NEW: 同値を explicit な命名で trade_count_stage_a にも書く
row["trade_count_stage_a"] = row["trade_count"]
```

#### (4) collect_stage_b 書き込み (T044 契約と整合)

**Round 2 [Critical] + Round 3 [Critical] 修正**: 現行 `collect_stage_b` には `tc = _opt_int(payload, "trade_count")` → `row["trade_count"] = tc` という上書き経路が残っているが、 これは T044 契約 (Stage A 値固定) と**矛盾**している。 本施策で **既存上書き分岐を削除**して契約を明示化する:

1. **既存の `row["trade_count"] = tc` 上書き分岐を `collect_stage_b` から削除** (T044 契約遵守の明示化、 Round 3 [Critical] 対応)
2. **新列 `trade_count_stage_b` のみに Stage B trade count を書く**
3. **`trade_count_full_dataset` は stage_a + stage_b で計算**

#### 現行 `collect_stage_b` (削除対象部分)

```python
# archive.py の collect_stage_b 内 (現行、 T044 契約と矛盾している箇所)
tc = _opt_int(payload, "trade_count")
if tc is not None:
    row["trade_count"] = tc  # ← この分岐を削除 (T044 契約: Stage A 値固定)
```

#### 修正後 `collect_stage_b`

```python
# Round 2 [Critical] + Round 3 [Critical] 修正:
# - T044 契約: row["trade_count"] は collect_stage_a で Stage A 値が書かれた後、 Stage B/C で
#   絶対に上書きしない。 既存 collect_stage_b の `row["trade_count"] = tc` 分岐は削除する。
# - 新列 trade_count_stage_b に Stage B 全期間 1 pass の値を書く (新規責務)
# - trade_count_full_dataset = trade_count_stage_a + trade_count_stage_b の合算

# 既存削除: tc = _opt_int(payload, "trade_count"); if tc is not None: row["trade_count"] = tc

# 新規追加:
tcb = _opt_int(payload, "trade_count_stage_b")  # Stage B 1 pass count
if tcb is not None:
    row["trade_count_stage_b"] = tcb

# trade_count_full_dataset の計算 (両値が揃ってから)
tca = row.get("trade_count_stage_a")
tcb_final = row.get("trade_count_stage_b")
if tca is not None and tcb_final is not None:
    row["trade_count_full_dataset"] = int(tca) + int(tcb_final)
# どちらか null なら full_dataset も null (consumer は fallback)
```

**追加テスト** (Round 2 [Critical] + Round 3 [Critical] 対応):
- `test_collect_stage_b_does_not_overwrite_stage_a_trade_count` — collect_stage_a 後の `row["trade_count"]=42` (Stage A 値) に対し、 collect_stage_b で異なる payload trade_count=99 を渡しても **`row["trade_count"]` は 42 のまま**を直接 assertion で verify (T044 契約の単体検証)
- `test_collect_stage_b_only_writes_to_new_column` — `row["trade_count_stage_b"]` のみ更新され、 `row["trade_count"]` は変更されないことを verify

#### 既存挙動への後方互換確認

run_ga.py / report 生成側 / replay コードで `row["trade_count"]` を Stage B 値として参照している箇所がないか grep で確認:
- `archive.py:597-601` の T044 コメント箇所が削除対象 (本変更で削除)
- `generate_run_report.py` で `trade_count` 表示は OK (Stage A 値が正しい意図)
- `_update_cache` の `row.get("trade_count")` は `trade_count_full_dataset` 不在時の fallback として **残置** (旧 archive 互換)

### Stage B 全期間 1 pass 計算の追加

`src/alpha_factory/stage_gate.py` の `evaluate_stage_b` 関数の冒頭 (fold ループ前):

```python
# === cycle_phase1: trade_count_stage_b 計算 (full Stage B 1 pass) ===
# 目的: trade_count_full_dataset 算出のため、 Stage B 全期間で 1 回 backtest を実行
# fold 合算は重複カウントリスクで禁止 (canonical 定義)。
# コスト: ~10% trade evaluation 増 (24GB / 6 worker 制約に影響なし)。
trade_count_stage_b: int | None = None
try:
    if _aux_supports_with_aux:
        aligned_full = aux_bundle.align_to(bars_stage_b)
        evaluator_full = primitive_evaluator.with_aux(**aligned_full.as_evaluator_kwargs())
    else:
        evaluator_full = primitive_evaluator
    strategy_full = DslStrategy(genome, evaluator_full)
    broker_full = MockBroker(instrument_meta=meta)
    res_full = run_backtest(bars_stage_b, strategy_full, broker_full, backtest_config)
    # T044 / Stage A の compute_metrics と同パターン
    bt_full = compute_metrics(
        res_full.trades, res_full.equity_curve,
        trade_count_min_for_sharpe=stage_config.trade_count_min_for_sharpe,
    )
    trade_count_stage_b = int(bt_full.trade_count)
    # 詳細 trade list は破棄、 count のみ保持 (RSS 節約、 Codex Round 3 Suggestion)
    del res_full, bt_full
except Exception as exc:
    logger.warning(
        "stage_b.full_pass_failure",
        genome=genome.name,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    trade_count_stage_b = None  # 計算失敗時 null、 selection は安全側 (full_dataset null → fallback)
```

metrics_envelope.payload に追加:

```python
"trade_count_stage_b": trade_count_stage_b,
```

### selection_score の feasibility 切替 (Round 2 [Critical] 修正: NaN/pd.NA fallback)

#### IndividualCacheEntry に新フィールド追加

`scripts/alpha_factory/run_ga.py:170-185`:

```python
@dataclass
class IndividualCacheEntry:
    individual_name: str
    generation: int
    fitness_pen: float
    stage_a_pass: bool
    stage_b_pass: bool
    stage_c_pass: bool
    feasible: bool = True  # ← trade_count_full_dataset >= entry_count_min で判定
    violation_magnitude: float = 0.0
    stage_c_feasible: bool = True
    fold_robust: bool = False
    # NEW: cycle_phase1 - selection feasibility 計算経路の verification 用
    trade_count_full_dataset: int | None = None  # archive から読み込み (None=旧 archive or 計算失敗)
```

#### NaN / pd.NA fallback helper (Round 2 [Critical] 対応)

```python
def _coerce_optional_int(value: Any) -> int | None:
    """row dict 値を optional non-negative int に正規化する (Round 3 [Warning] 対応).

    棄却条件 (None 返す):
    - None
    - NaN / pd.NA (value != value で TypeError catch)
    - list / tuple / dict / array (hasattr __len__)
    - bool / np.bool_ (整数値偽装)
    - 非有限値 (inf, -inf)
    - 非整数 float (例: 100.5)
    - 負数 (trade_count は非負前提)

    許容: int, np.int64, 整数値の float (例: 100.0)。
    """
    if value is None:
        return None
    # list / array / dict
    try:
        if hasattr(value, "__len__"):
            return None
    except (TypeError, ValueError):
        return None
    # NaN / pd.NA
    try:
        if value != value:
            return None
    except (TypeError, ValueError):
        return None
    # bool / np.bool_ (Python bool は int subclass、 別途拒否)
    # numpy.bool_ は int subclass ではないが、 isinstance(value, bool) で catch できないので type 名で判定
    if isinstance(value, bool):
        return None
    try:
        import numpy as np
        if isinstance(value, np.bool_):  # numpy bool (Round 4 [Warning]: バージョン差耐性)
            return None
    except ImportError:
        pass
    # 数値変換と非有限/非整数/負数チェック
    try:
        f = float(value)
        if not math.isfinite(f):
            return None
        if not f.is_integer():
            return None  # 100.5 等の非整数 float は拒否
        if f < 0:
            return None  # 負数は trade_count として不正
        return int(f)
    except (TypeError, ValueError, OverflowError):
        return None
```

#### _update_cache で fallback helper 使用

```python
# 現行
trade_count = row.get("trade_count", 0) or 0
feasible = bool(trade_count >= entry_count_min)

# 変更後 (Round 2 [Critical] 対応: NaN / pd.NA を取り逃がさない)
trade_count_full = _coerce_optional_int(row.get("trade_count_full_dataset"))
if trade_count_full is None:
    # 後方互換 fallback: 旧 archive (新列なし) or Stage B 1 pass 失敗時
    trade_count_full = _coerce_optional_int(row.get("trade_count")) or 0
feasible = bool(trade_count_full >= entry_count_min)

# IndividualCacheEntry constructor で値を必ず渡す (Round 2 [Warning] 対応)
cache[name] = IndividualCacheEntry(
    individual_name=name,
    generation=int(row.get("generation", 0)),
    fitness_pen=fp,
    stage_a_pass=stage_a_pass,
    stage_b_pass=stage_b_pass,
    stage_c_pass=stage_c_pass,
    feasible=feasible,
    violation_magnitude=violation,
    stage_c_feasible=stage_c_feasible,
    fold_robust=fold_robust,
    trade_count_full_dataset=trade_count_full if trade_count_full > 0 else None,  # NEW
)
```

**追加テスト**:
- `test_coerce_optional_int_handles_nan_and_na` — None / np.nan / pd.NA / inf / "string" / [list] → None
- `test_coerce_optional_int_handles_finite_numerics` — 100 / 100.5 / np.int64(100) → 100

### selection_score schema bump

`v3_3_stage_b_feasible_priority` → **`v3_4_full_dataset_feasibility`**

- 構造変化なし (10-tuple 維持)、 docstring 更新のみ
- 後続施策 (Phase 1 タスク #2 niching) で position 7 dead-code 削除と同時に schema bump 予定

### config 変更 (なし、 archive 経路のみ)

`StageGateConfig` には新フィールド追加せず。 archive 列追加のみ。

### テスト計画

- [ ] `test_archive_schema_has_trade_count_columns` — GENOMES_SCHEMA に 3 列が存在
- [ ] `test_create_row_template_initializes_trade_count_columns_to_none`
- [ ] `test_collect_stage_a_writes_trade_count_stage_a` — payload trade_count → archive trade_count_stage_a
- [ ] `test_collect_stage_b_computes_trade_count_full_dataset` — stage_a + stage_b 合算 verify
- [ ] `test_evaluate_stage_b_runs_full_pass_backtest` — fold ループとは別に 1 pass backtest 実行を verify (trade_count_stage_b が non-null)
- [ ] `test_full_pass_backtest_failure_falls_back_gracefully` — 例外時 trade_count_stage_b=None、 trade_count_full_dataset も None
- [ ] `test_individual_cache_entry_feasible_uses_full_dataset` — `trade_count_full_dataset>=50` で feasible=True
- [ ] `test_legacy_archive_backwards_compat` — `trade_count_full_dataset=None` の旧 archive 行で `trade_count` (Stage A) を fallback 使用
- [ ] **archive replay test**: `test_run_52_replay_selection_with_full_dataset` — run-52 archive を replay して top-K (K=20) selection で trade>=120 over-trading 比率が 20% 以上低下することを verify (H_A3')

### コスト見積の修正 (Round 2 [Warning] C4 前提不一致)

Round 2 指摘: `stage_b_window_months=18` (config) と詳細設計の `~67日` の整合性。

**実態整理**:
- `stage_b_window_months=18` は **config の上限指定** (StageGateConfig)、 実際の Stage B partition は dataset 全期間 - Stage A 期間 (60d) - holdout 期間で決まる
- 本データセット (2025-10-01 → 2026-04-01、 6 ヶ月) では Stage B 実態 ~67日 (run-52 報告 `bars_stage_b=97003` ≈ 67d at M1)
- Stage A 1 pass = 86,400 bars、 Stage B 1 pass = 97,003 bars

**追加コスト**:
- 既存 fold ループ: ~10 fold × wf_test_days=18d ≈ 180d 相当の trade evaluation
- 新規 Stage B 1 pass: 67d 相当の trade evaluation (= 既存 fold 評価の ~37%)
- 全体: 既存 1.0x → 新規 1.37x ≈ **+37% trade evaluation コスト** (旧見積 ~10% は誤り、 修正)
- 1 RUN wall-time: 180 min × 1.37 = ~247 min (4.1 時間)
- 24GB / 6 worker 制約: 1 worker 3GB 上限維持、 trade list は集計後即破棄 (RSS 影響軽減)

**Round 3 [Warning] 対応 (cycle SLA)**:
- 現行 `improve_cycle.max_cycle_seconds=3600` (1 時間) は **改訂前の RUN 時間とも整合していない** (run-52 wall-time 180 min)
- 既に運用上 budget 不整合 → 本施策で更に +37% で 247 min ≈ 4.1 時間
- **対応**: `improve_cycle.max_cycle_seconds: 3600 → 18000` (5 時間 = 18,000 秒) に config 更新を本施策に含める
- runbook.md / docs/alpha_factory/runbook.md に「Phase 1 後の RUN 想定時間 4-5 時間」 を明記
- 実装時に `evaluate_stage_b` 内で Stage B full pass 計測ログを log.info 出力、 実 RUN 後に budget actual を verify

**Codex 指摘の log 出力** (Round 2 [Warning] 対応):
```python
# evaluate_stage_b 内で Stage B 1 pass 完了後
logger.info(
    "stage_b.full_pass_observation",
    genome=genome.name,
    bars_stage_b=len(bars_stage_b),
    trade_count_stage_b=trade_count_stage_b,
    rss_mb=psutil.Process().memory_info().rss / 1024 / 1024,  # 監視用
    wall_time_seconds=time.perf_counter() - start_full_pass,
)
```

### リスク

- **副作用**: Stage B 1 pass backtest の追加コスト **+37%** (run-52 で wall-time 180min → ~247min 推定、 旧見積 ~10% を訂正)。 24GB / 6 worker 制約は worker 数に影響しないため許容。 `del res_full` で trade list 即破棄 (RSS 影響軽減)
- **後退リスク**: Stage B 1 pass で例外 → trade_count_full_dataset=None → 後方互換 fallback (Stage A trade_count) → 旧 selection と同等動作
- **archive 読み込み backwards compat**: 既存 archive (genomes_run_*.parquet) は新 3 列を持たない → pandas/pyarrow の null tolerant read で問題なし。 _coerce_optional_int helper で NaN / pd.NA も catch
- **T044 「Stage A 値固定」 契約**: 本施策では既存 `row["trade_count"]` 上書き経路を触らず、 新列に書き込み (Codex Round 2 [Critical] 対応済み)

---

## 施策 3: stage_partition_guard holdout_days 検証 + 二重 opt-in (Round 2 [Critical] 反映)

**Round 2 [Critical] 4 件対応**: smoke_test を flush の明示引数化、 RunContext 経由で archive marker 全 row 注入、 graduate / calibrate / report に直接 marker を渡す、 np.bool_ 正規化、 report 名を `SMOKE-run-X.md`。

**Round 2 旧施策 3 (DSR) は Phase 2 に移動** (Codex Critical 3 件: kurtosis 定義 / V[SR] 出所 / valid 条件)。 archive `dsr` 列は Phase 1 では null のまま維持。


### 変更箇所

- ファイル: `src/alpha_factory/stage_partition_guard.py` (validate_stage_partition 拡張)
- ファイル: `scripts/alpha_factory/run_ga.py` (CLI フラグ + env var チェック + summary.json marker)
- ファイル: `src/alpha_factory/archive.py` (holdout_short_override 列追加)

### 波及変更

- `AGENTS.md`: smoke test 運用方法の説明 1 段落追加
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/runbook.md`: smoke test 運用ガイド追加

### holdout_days 検証

`src/alpha_factory/stage_partition_guard.py`:

```python
def validate_stage_partition(
    bars_stage_a: list[PriceBar],
    bars_stage_b: list[PriceBar],
    bars_holdout: list[PriceBar],
    *,
    expected_holdout_days: int | None = None,  # NEW
    allow_holdout_short: bool = False,  # NEW (escape hatch)
) -> None:
    """... (既存 docstring に追加: holdout_days 検証) ..."""
    _validate_inputs(bars_stage_a, bars_stage_b, bars_holdout)
    _validate_chronological_partition(bars_stage_a, bars_stage_b, bars_holdout)
    _validate_timestamp_disjoint(bars_stage_a, bars_stage_b, bars_holdout)
    # NEW: holdout_days 検証 (cycle_phase1)
    if expected_holdout_days is not None:
        _validate_holdout_length(
            bars_holdout, expected_holdout_days, allow_holdout_short
        )


def _validate_holdout_length(
    bars_holdout: list[PriceBar],
    expected_days: int,
    allow_short: bool,
) -> None:
    """holdout の実日数が expected_days を満たすか検証.

    bars_holdout の最初と最後の bar_time から実 span を計算する。
    weekday/weekend を考慮せず単純な calendar 日数で判定 (FX は 24x5 trading)。

    expected_days の 80% 未満なら fail (calendar の weekend 考慮で 20% buffer)。
    allow_short=True なら WARN log のみで raise しない (escape hatch)。
    """
    if not bars_holdout:
        return  # _validate_inputs で既に raise
    span = bars_holdout[-1].bar_time - bars_holdout[0].bar_time
    actual_days = span.total_seconds() / 86400.0
    threshold = expected_days * 0.8
    if actual_days < threshold:
        msg = (
            f"holdout_days mismatch: expected {expected_days}, "
            f"actual {actual_days:.1f} (< 80% threshold {threshold:.1f})"
        )
        if allow_short:
            import logging
            logging.warning("stage_partition_guard.holdout_short_override: %s", msg)
        else:
            raise StagePartitionInputError(
                f"B-2 violation: {msg}. "
                f"Use --allow-holdout-short + ZENIGAME_FX_SMOKE_TEST=1 for smoke tests."
            )
```

### 二重 opt-in escape hatch (run_ga.py)

```python
# CLI args
p.add_argument("--allow-holdout-short", action="store_true",
               help="Allow short holdout (smoke test only, requires ZENIGAME_FX_SMOKE_TEST=1)")

# parse args 後
holdout_short_override = False
if args.allow_holdout_short:
    if os.environ.get("ZENIGAME_FX_SMOKE_TEST") != "1":
        raise SystemExit(
            "--allow-holdout-short requires ZENIGAME_FX_SMOKE_TEST=1 env var. "
            "This double-opt-in prevents accidental production override."
        )
    holdout_short_override = True
    logger.warning("smoke_test.holdout_short_override_enabled: graduate disabled, calibrate disabled")

# validate_stage_partition 呼び出し
validate_stage_partition(
    bars_stage_a, bars_stage_b, bars_holdout,
    expected_holdout_days=cfg.stage_gate.stage_c_holdout_days,
    allow_holdout_short=holdout_short_override,
)

# summary.json と report に marker 記録
summary["holdout_short_override"] = holdout_short_override
if holdout_short_override:
    # graduate 判定強制 SKIP
    # calibrate-gate history append 強制 SKIP
    # report file 名に [SMOKE TEST] prefix
    ...
```

### archive 列追加 + RunContext 経由の SSOT 伝搬 (Round 2 [Critical] 4 件対応)

#### archive 列定義

`holdout_short_override`: bool, nullable=True
- `None`: legacy archive (列を持たない、 後方互換読み込み)
- `False`: 通常 production RUN
- `True`: 二重 opt-in 経由の smoke test RUN

```python
pa.field("holdout_short_override", pa.bool_(), nullable=True),
```

template:
```python
"holdout_short_override": None,
```

#### RunContext 経由の SSOT 伝搬 (Round 2 [Critical] 修正)

Codex Round 2 [Critical]: 「`archive.flush` の `env` が未定義」 「marker 伝搬不足」 「graduate / calibrate / report に直接 marker を渡す必要」 を一括解決:

`src/alpha_factory/run_context.py` (既存) に `holdout_short_override: bool` フィールド追加。 RUN 起動時に決定し、 全 consumer (archive / graduation / calibrate / report) に渡す **SSOT**:

```python
# src/alpha_factory/run_context.py
@dataclass(frozen=True)
class RunContext:
    run_id: str
    run_number: int
    dataset_epoch_id: str
    # NEW: cycle_phase1
    holdout_short_override: bool = False  # 二重 opt-in 経由の smoke override marker
    smoke_test_mode: bool = False  # 同等の意味、 別名 alias (運用判別用)
    # ... (既存フィールド)
```

`run_ga.py` 起動経路で:
```python
# 二重 opt-in 検証
holdout_short_override = False
smoke_test_mode = (os.environ.get("ZENIGAME_FX_SMOKE_TEST") == "1")
if args.allow_holdout_short:
    if not smoke_test_mode:
        raise SystemExit(
            "--allow-holdout-short requires ZENIGAME_FX_SMOKE_TEST=1 env var."
        )
    holdout_short_override = True

# RunContext に SSOT として保持
run_context = RunContext(
    run_id=run_id,
    run_number=run_number,
    dataset_epoch_id=dataset_epoch_id,
    holdout_short_override=holdout_short_override,
    smoke_test_mode=smoke_test_mode,
    # ...
)

# validate_stage_partition に渡す
validate_stage_partition(
    bars_stage_a, bars_stage_b, bars_holdout,
    expected_holdout_days=cfg.stage_gate.stage_c_holdout_days,
    allow_holdout_short=run_context.holdout_short_override,
)
```

#### 全 row に marker 注入 (archive collector)

`src/alpha_factory/archive.py` の `_create_row_template` でデフォルト None だが、 `collect_stage_*` は **RunContext から marker を受け取り全 row に注入**:

```python
def collect_stage_a(self, stage_result, run_context: RunContext, ...):
    row = self._create_row_template()
    row["holdout_short_override"] = run_context.holdout_short_override  # NEW
    # ... 既存処理
```

→ `row["holdout_short_override"]` は run_ga.py から直接書かない。 RunContext SSOT を経由する設計。

#### archive.flush の SSOT 検証 (smoke_test 明示引数化)

```python
# src/alpha_factory/archive.py
class ArchiveWriter:
    def __init__(self, run_context: RunContext, ...):
        self._run_context = run_context  # NEW: SSOT 保持

    def flush(self, *, _testing_smoke_test_override: bool | None = None) -> None:
        """archive Parquet を flush する。

        二重 opt-in 厳格化 (Round 4 [Critical] 対応):
        - 全 row marker が `bool(run_context.holdout_short_override)` と完全一致を要求 (None 混在禁止)
        - 最終許可条件: run_context.holdout_short_override AND run_context.smoke_test_mode の AND
        - `_testing_smoke_test_override` は **テスト専用 escape hatch**、 通常 callsite での使用禁止

        Args:
            _testing_smoke_test_override: **TEST ONLY** (production code から呼び出さないこと)。
                None で run_context 経由 (通常)。 引数名の `_testing_` prefix は production grep で
                発見しやすくし、 ロード時に static analysis で flag できるようにする。
        """
        import numpy as np  # numpy.bool_ for isinstance check

        # Round 2 [Warning] + Round 4 [Warning] 対応: np.bool_ / pandas bool 正規化
        def _normalize_bool(v):
            if v is None:
                return None
            # numpy bool (Round 4: バージョン差耐性のため isinstance を使う)
            if isinstance(v, np.bool_):
                return bool(v)
            if isinstance(v, bool):
                return bool(v)
            try:
                return bool(v)  # pandas BooleanArray 等 fallback
            except (TypeError, ValueError):
                return None

        # Round 4 [Critical] 修正: 全 row 完全一致を要求 (None 混在禁止)
        rc_override = bool(self._run_context.holdout_short_override)
        rc_smoke = bool(self._run_context.smoke_test_mode)
        expected_marker = rc_override  # 期待値 = RunContext SSOT

        # 全 row の marker を取得 + 検証
        all_markers = [_normalize_bool(row.get("holdout_short_override")) for row in self._rows]
        unique_markers = set(all_markers)

        # None 混在を即 raise (Round 4 Critical: {None, True} を許容しない)
        if None in unique_markers:
            raise RuntimeError(
                "archive flush rejected: holdout_short_override=None detected in some rows "
                f"(unique={unique_markers}). RunContext SSOT 経由で全 row に marker 注入が必要。"
            )

        # 全 row が expected_marker と一致すること
        if unique_markers != {expected_marker}:
            raise RuntimeError(
                f"archive flush rejected: holdout_short_override mismatch with RunContext. "
                f"Expected all rows == {expected_marker}, got {unique_markers}."
            )

        # Round 3 [Critical] 二重 opt-in 厳格化
        # 最終許可条件 = run_context.holdout_short_override AND run_context.smoke_test_mode
        final_allow = rc_override and rc_smoke

        if _testing_smoke_test_override is not None:
            # **TEST ONLY** escape hatch (本番経路から呼び出されないこと)
            final_allow = bool(_testing_smoke_test_override)

        if expected_marker is True and not final_allow:
            raise RuntimeError(
                "archive flush rejected: holdout_short_override=True but final_allow=False "
                f"(rc_override={rc_override}, rc_smoke={rc_smoke}). "
                "Both --allow-holdout-short CLI AND ZENIGAME_FX_SMOKE_TEST=1 env var required."
            )
        # 既存 flush ロジック
        ...
```

#### `_testing_smoke_test_override` の運用ガード (Round 4 [Warning] 対応)

- 引数名に `_testing_` prefix を付与 (production grep で発見容易)
- `pyproject.toml` の `ruff.lint.flake8-tidy-imports.banned-api` に `archive.flush:_testing_smoke_test_override` を追加 (静的解析で production callsite を fail)
- pre-commit hook で `_testing_smoke_test_override=` を tests/ 以外で grep して警告

#### Round 4 [Critical] テスト追加

- `test_archive_flush_rejects_none_marker_mixed_with_true` — `{None, True}` 混在で RuntimeError
- `test_archive_flush_rejects_marker_mismatch_with_run_context` — RunContext.holdout_short_override=False なのに row が True → RuntimeError
- `test_archive_flush_rejects_legacy_none_marker_in_new_run` — 新 RUN で全 row None (collector 経由しない不正状態) → RuntimeError

**追加テスト** (Round 3 [Critical] 対応):
- `test_archive_flush_rejects_when_only_env_var_set` — `ZENIGAME_FX_SMOKE_TEST=1` のみ (`--allow-holdout-short` なし) で override=True row → RuntimeError
- `test_archive_flush_rejects_when_only_cli_flag_set` — `--allow-holdout-short` のみ (env var なし) → そもそも run_ga.py 起動時に SystemExit (flush に到達しない)
- `test_archive_flush_allows_when_both_optin_set` — 両方 set で override=True row → flush 成功
- `test_archive_flush_rejects_when_neither_optin` — 両方なし で override=True row が混入 → RuntimeError

### graduate / calibrate / report の SSOT 経由 marker 伝搬

```python
# graduate 判定 (graduation.py)
def _check_graduation(genome, run_context: RunContext, ...):
    """run_context.holdout_short_override を SSOT として参照"""
    if run_context.holdout_short_override:
        logger.info("graduation.skipped_due_to_smoke_override")
        return GraduationResult(graduated=False, reason="smoke_override")
    # ... 既存ロジック

# calibrate-gate history (calibrate_gate_history.py)
def append_record(record, run_context: RunContext):
    if run_context.holdout_short_override:
        logger.info("calibrate_gate.append_skipped_due_to_smoke_override")
        return  # 強制 SKIP
    # ... 既存ロジック

# report 名 (generate_run_report.py) — Round 2 [Warning]: shell glob 友好的に
report_filename = f"run-{run_number}.md"
if run_context.holdout_short_override:
    report_filename = f"SMOKE-{report_filename}"  # 旧 [SMOKE]- から SMOKE- に変更 (glob 簡素化)
```

### テスト計画 (Round 3 [Warning] 対応: 統合テスト追加)

#### 単体テスト

- [ ] `test_validate_holdout_length_passes_when_above_threshold`
- [ ] `test_validate_holdout_length_raises_when_below_threshold`
- [ ] `test_validate_holdout_length_warns_when_allow_short`
- [ ] `test_run_ga_rejects_allow_short_without_env_var` — `--allow-holdout-short` 単独で SystemExit
- [ ] `test_run_ga_accepts_allow_short_with_env_var` — 両方指定で起動成功 + warning log
- [ ] `test_summary_json_records_holdout_short_override`
- [ ] `test_archive_records_holdout_short_override_per_row`
- [ ] `test_graduation_skipped_when_holdout_short_override`
- [ ] `test_calibrate_history_skipped_when_holdout_short_override`
- [ ] `test_report_prefix_smoke_when_holdout_short_override`
- [ ] `test_archive_flush_rejects_inconsistent_override_marker`

#### Round 3 [Critical] 二重 opt-in テスト群

- [ ] `test_archive_flush_rejects_when_only_env_var_set` — env var only → RuntimeError
- [ ] `test_archive_flush_rejects_when_only_cli_flag_set` — CLI only → SystemExit (run_ga 経路)
- [ ] `test_archive_flush_allows_when_both_optin_set` — 両 opt-in で flush 成功
- [ ] `test_archive_flush_rejects_when_neither_optin` — 両方なしで override row 混入 → RuntimeError

#### Round 3 [Warning] 統合テスト

- [ ] `test_smoke_override_propagates_to_all_consumers_integration` — 二重 opt-in RUN で:
  1. `RunContext.holdout_short_override == True`
  2. archive 全 row に `holdout_short_override=True` 注入
  3. `_check_graduation` が `smoke_override` reason で skip
  4. `calibrate_gate_history.append_record` が skip
  5. `generate_run_report` が `SMOKE-run-X.md` で出力
  6. `archive.flush` が成功 (二重 opt-in 充足)
  → 上記全て同一 `RunContext` を経由した SSOT 伝搬であることを verify

- [ ] `test_signature_change_callsite_compat` — `_check_graduation` / `append_record` の signature 変更で全 callsite が更新されており、 旧 signature 呼び出しが mypy/ruff で fail することを verify

### リスク

- **副作用**: 既存 RUN は holdout=14 日固定で動作していたため、 本変更を入れた最初の RUN は **fail-closed で起動失敗**する。 これは intentional (= F6 構造的問題の表面化)。 解決策: (a) Phase 2 で dataset 延長 / (b) 一時的に smoke override (二重 opt-in) で RUN を継続
- **後退リスク**: 既存 archive Parquet は新列を持たない → null tolerant で読み込み可
- **運用影響**: 次 RUN が起動失敗するため、 ユーザーへの周知が必須 (AGENTS.md / docs/alpha_factory/runbook.md 更新)

---

## 実装モード

| 項目 | 内容 |
|---|---|
| 推奨モード | **incremental** (4 段階で段階適用、 各段階で commit + Codex review) |
| 段階順序 | 施策 1 → 施策 2 → 施策 3 → 施策 4 |
| 判断根拠 | Codex Round 2 Suggestion: 同時投入で原因帰属が濁る。 段階適用で各段の効果を独立検証 |
| 競合リスク | Phase 1 タスク #2 (niching) と selection_score 変更で軽微競合。 別ブランチで段階マージ。 selection_score schema bump (`v3_3` → `v3_4_full_dataset_feasibility` → `v3_5_niching` 等) で diff 最小化 |
| 想定実装時間 | 中〜長 (各段階 1.5-3 hours、 計 8-12 hours) |
| Codex review | 各施策実装時に 1 回 (impl-review label)、 詳細設計全体合議 (本ドキュメント) は別途 |

### worktree 分離 (推奨)

施策 1-4 を独立 worktree で実装:
```
worktrees/stage-b-gate-redesign-1-median/  (施策 1)
worktrees/stage-b-gate-redesign-2-feasibility/  (施策 2)
worktrees/stage-b-gate-redesign-3-dsr/  (施策 3)
worktrees/stage-b-gate-redesign-4-guard/  (施策 4)
```

各 worktree で `zenigame-fx-implement` skill 実行 → tests pass + Codex impl-review APPROVED → main マージ。

---

## ルックアヘッドバイアスチェック (primitive 変更時のみ必須)

本設計は **primitive 変更を含まない** ため該当なし。 既存 primitive (F1-F14, M1-M6, P1-P12) のロジックは変更しない。

---

## パフォーマンスチェック

- 施策 1: 閾値変更のみ、 性能影響なし
- 施策 2: Stage B 1 pass backtest 追加 (~10% 増)、 24GB / 6 worker 制約に影響なし (1 worker 3GB 上限維持、 trade list 即破棄で RSS 影響軽減)
- 施策 3: per-fold DSR 計算 = O(10N) per 個体 (N=trade per fold)。 1 RUN 全体 < 1 秒
- 施策 4: holdout 検証 = O(1)、 性能影響なし

---

## 全体テスト戦略

- 単体テスト: 各施策の helper / config / archive 機能
- 統合テスト: archive replay (run-52 fixture) で施策 1 (median 緩和) の効果検証
- E2E: smoke test (`ZENIGAME_FX_SMOKE_TEST=1` + `--allow-holdout-short` + `--generations 5`) で全段階の協調動作 verify

---

## 全体リスク

- **使命達成への寄与**: Phase 1 単独では使命達成 (Stage C pass + cross-pair ii-lite + live_criteria 全充足) には到達しない。 必要条件 (Stage B pass + trade>=50 個体出現) のみ満たす。 Phase 2-3 (Stage C 機構整備 + niching + dataset 延長) との組合せで graduate
- **後退観測**: 施策 1-3 を入れた最初の RUN は holdout 不整合で **fail-closed 起動失敗**する → smoke override で一時的に継続 or Phase 2 で dataset 延長を先行
- **monitoring**: 各施策実装後の archive replay で副作用ゼロを確認、 次 RUN で archive 新列が non-null で記録されることを verify

---

## 実装時 Reminder (Codex Round 5 [Suggestion] 反映)

実装フェーズ (zenigame-fx-implement) で以下を遵守:

### S1. `_testing_smoke_test_override` の CI grep 監視

ruff `banned-api` は keyword argument の使用検知に弱いため、 CI で grep based check を追加:

```yaml
# .github/workflows/ci.yml or pre-commit hook
- name: Detect _testing_ argument leak
  run: |
    if grep -rn "_testing_smoke_test_override=" --include="*.py" src/ scripts/ | grep -v "tests/"; then
      echo "ERROR: _testing_smoke_test_override used outside tests/"
      exit 1
    fi
```

### S2. `_normalize_bool` の bool-only 化

実装時に `_normalize_bool` を bool / np.bool_ 以外を None にして reject する形に寄せる:

```python
def _normalize_bool(v):
    if v is None: return None
    if isinstance(v, np.bool_): return bool(v)
    if isinstance(v, bool): return bool(v)
    return None  # 文字列等は明示的に reject (Codex Round 5 [Suggestion])
```

### S3. `_coerce_optional_int` の numpy import を module-level に

```python
# scripts/alpha_factory/run_ga.py 先頭
import numpy as np

def _coerce_optional_int(value: Any) -> int | None:
    ...
    if isinstance(value, np.bool_):
        return None
    ...
```

### S4. `flush` で `_rows` 空時の挙動明記

```python
def flush(self, *, _testing_smoke_test_override: bool | None = None) -> None:
    if not self._rows:
        # 空 RUN の flush は no-op (Codex Round 5 [Suggestion] 明記)
        logger.warning("archive.flush_empty_rows", run_id=self._run_context.run_id)
        return
    # ... marker 検証ロジック
