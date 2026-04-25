# 詳細設計: 無取引優位の遮断設計 (risk-no-trade-fitness-guard)

## 使命・制約（絶対遵守）

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1. A・B・C 評価期間を根拠なしに延長
2. 見た目の数値改善
3. GA ハック
4. live_criteria 緩和
5. 過度な複雑化
6. 取引回数削減で成績を見せる
7. オーバーナイト保有前提

### コーディングルール
- バグ修正はテストファースト: 再現最小テスト → FAIL 確認 → 修正 → PASS
- 全施策にテスト必須
- テスト命名: 振る舞いを説明する汎用的な名前
- uv 必須: `uv run pytest tests/alpha_factory/`
- ruff / mypy 通過: `uv run ruff check src/ tests/` / `uv run mypy src/`
- Python 3.13 + numpy + pandas

## 概念設計リファレンス

`devnotes/20260425-0937-risk-no-trade-fitness-guard/conceptual-design.md` (APPROVED Round 4)

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | Stage A 3 経路 sentinel 化 + min_exposure_trade_count 導入 | `src/alpha_factory/stage_gate.py` | Critical |
| 2 | StageGateConfig.min_exposure_trade_count config loader 経路 | `src/alpha_factory/config.py` / `config/alpha_factory/default.yaml` | Critical |
| 3 | calibrate_gate sentinel 除外フィルタ | `src/alpha_factory/calibrate_gate.py` | Critical |
| 4 | docs SSOT 更新 (stage-gates.md) | `docs/alpha_factory/stage-gates.md` | Critical |
| 5 | 既存テスト更新 + 新規テスト | `tests/alpha_factory/test_stage_gate.py` 他 | Critical |
| 6 | run_ga 回帰テスト | `tests/alpha_factory/test_run_ga_*` | High |

---

## 施策 1: Stage A 3 経路 sentinel 化

### 変更箇所
- `src/alpha_factory/stage_gate.py` (L63-145, 238-340)

### 波及変更
- `AGENTS.md`: なし (CLI / 公開 API 不変)
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: 施策 2 で対応
- `docs/alpha_factory/stage-gates.md`: 施策 4 で対応

### 現行コード (抜粋)

```python
# src/alpha_factory/stage_gate.py L63-101
@dataclass(frozen=True)
class StageGateConfig:
    # Stage A
    stage_a_window_days: int = 60
    stage_a_alpha: float = 0.03
    stage_a_threshold: float = 0.0
    # ...
    live_criteria: Mapping[str, float | int] = field(
        default_factory=lambda: {
            "sharpe_min": 1.0,
            "total_pnl_min": 50000,
            ...
            "trade_count_min": 50,
            ...
        }
    )

# stage_gate.py L302-316 (evaluate_stage_a)
if exception_caught:
    reasons.append("system_failure")
elif trade_count < 1:
    reasons.append("no_trades")
elif sharpe_raw is None:
    reasons.append("metric_unavailable")
else:
    assert size_norm_val is not None
    fitness_raw = sharpe_raw
    fitness_pen = fitness_raw - stage_config.stage_a_alpha * size_norm_val
    if fitness_pen <= stage_config.stage_a_threshold:
        reasons.append("below_threshold")
```

### 変更後コード

```python
# src/alpha_factory/stage_gate.py — モジュールレベル sentinel 定数追加
_SYSTEM_FAILURE_FITNESS: float = -1e12
_NO_EXPOSURE_FITNESS: float = -1e9
_METRIC_UNAVAILABLE_FITNESS: float = -1e6

#: stage_a の sentinel 集合 (calibrate_gate / archive 互換チェックで参照)
STAGE_A_FITNESS_SENTINELS: frozenset[float] = frozenset(
    {_SYSTEM_FAILURE_FITNESS, _NO_EXPOSURE_FITNESS, _METRIC_UNAVAILABLE_FITNESS}
)

@dataclass(frozen=True)
class StageGateConfig:
    # Stage A
    stage_a_window_days: int = 60
    stage_a_alpha: float = 0.03
    stage_a_threshold: float = 0.0
    min_exposure_trade_count: int = 1  # 新規: trade_count<この値は no_exposure 扱い
    # ... 既存フィールド変更なし ...
    live_criteria: Mapping[str, float | int] = field(
        default_factory=lambda: {
            "sharpe_min": 1.0,
            "total_pnl_min": 50000,
            "max_drawdown_max": 0.20,
            "trade_count_min": 50,
            "trade_count_max": 5000,
        }
    )

    def __post_init__(self) -> None:
        # ... 既存検証 ...
        # 新規: min_exposure_trade_count 不変条件
        if self.min_exposure_trade_count < 1:
            raise ValueError(
                "min_exposure_trade_count must be >= 1: "
                f"got {self.min_exposure_trade_count}"
            )
        # 上限制約: live_criteria.trade_count_min >= 1 の場合のみ適用
        # (trade_count_min=0 はテスト用 min_config や既存 fixture での利用があるため
        #  上限制約を常時適用すると既存 fixture/config が壊れる)
        live_criteria_dict = dict(self.live_criteria)
        trade_count_min = int(live_criteria_dict.get("trade_count_min", 50))
        if trade_count_min >= 1 and self.min_exposure_trade_count >= trade_count_min:
            raise ValueError(
                "min_exposure_trade_count must be < live_criteria.trade_count_min "
                "(only enforced when trade_count_min >= 1): "
                f"got min_exposure_trade_count={self.min_exposure_trade_count}, "
                f"trade_count_min={trade_count_min}"
            )
        # ... 既存 live_criteria 検証 (frozen 化) ...


def evaluate_stage_a(...) -> StageResult:
    # ... 前段は変更なし (try/except でメトリクス計算) ...

    # 判定優先順位 (canonical):
    #   system_failure > no_exposure > metric_unavailable > below_threshold
    if exception_caught:
        reasons.append("system_failure")
        fitness_pen = _SYSTEM_FAILURE_FITNESS  # sentinel
        fitness_raw = _SYSTEM_FAILURE_FITNESS  # raw も sentinel に揃える
    elif trade_count < stage_config.min_exposure_trade_count:
        reasons.append("no_exposure")
        fitness_pen = _NO_EXPOSURE_FITNESS  # sentinel
        fitness_raw = _NO_EXPOSURE_FITNESS  # raw も sentinel
    elif sharpe_raw is None:
        reasons.append("metric_unavailable")
        fitness_pen = _METRIC_UNAVAILABLE_FITNESS  # sentinel
        fitness_raw = _METRIC_UNAVAILABLE_FITNESS  # raw も sentinel
    else:
        assert size_norm_val is not None
        fitness_raw = sharpe_raw
        fitness_pen = fitness_raw - stage_config.stage_a_alpha * size_norm_val
        if fitness_pen <= stage_config.stage_a_threshold:
            reasons.append("below_threshold")

    # ... payload 構築は既存と同じ。fitness_raw / fitness_pen は上で確定済み ...
```

#### reason_codes 命名の整理

- `no_trades` を **`no_exposure` に置き換え** (canonical 名称統一)
- 既存テスト `test_no_trades_reason` は `test_no_exposure_reason` にリネーム + 期待値更新
- `min_exposure_trade_count > 1` の場合の振る舞いも `no_exposure` で統一 (新規テスト追加)

#### fitness_raw も sentinel に揃える理由

archive schema (`row["fitness_raw"]`) も `_required_float(default=0.0)` で読まれるため、`None` のまま放置すると 0.0 fallback で観察分析が誤誘導される。

### ルックアヘッドバイアスチェック（primitive 変更時のみ必須）
- 該当なし (primitive 変更ではない)

### パフォーマンスチェック（primitive 変更時のみ必須）
- 該当なし

### テスト計画
- [x] (再現テスト先行) `test_run_ga_no_exposure_dominance.py` — `trade_count=0, fitness_pen=sentinel` 個体が `trade_count>0, fitness_pen=負実値` 個体に **負ける** ことを確認 (FAIL → 修正 → PASS)
- [x] 既存 `test_no_trades_reason` を `test_no_exposure_reason` にリネーム + payload `fitness_pen == _NO_EXPOSURE_FITNESS` を assert
- [x] 新規 `test_min_exposure_trade_count_threshold` — `min_exposure_trade_count=3` で `trade_count=2` の個体が `no_exposure` 判定
- [x] 新規 `test_system_failure_sets_sentinel` — system_failure で payload `fitness_pen == _SYSTEM_FAILURE_FITNESS`
- [x] 新規 `test_metric_unavailable_sets_sentinel` — sharpe=None で payload `fitness_pen == _METRIC_UNAVAILABLE_FITNESS`
- [x] 新規 `test_min_exposure_lt_trade_count_min_invariant` — `__post_init__` で `min_exposure_trade_count >= live_criteria.trade_count_min` が ValueError

### リスク
- 既存テストの `("no_trades",)` assert が破壊される → 一括 grep して `no_exposure` に置換
- `fitness_raw` を sentinel にすることで run-report の比較解析が変わる → run-report の表示で sentinel 値検出時は "—" 表示する側で対応 (本施策では行わず観察)

---

## 施策 2: config loader 経路の追加

### 変更箇所
- `src/alpha_factory/config.py` `_build_stage_gate` (L261-297)
- `config/alpha_factory/default.yaml` `stage_gate.stage_a` セクション (L43-48)

### 現行コード

```python
# config.py L261-297
def _build_stage_gate(...) -> StageGateConfig:
    a_raw = stage_gate_raw.get("stage_a") or {}
    # ...
    kwargs: dict[str, Any] = {
        "stage_a_window_days": int(a_raw.get("window_days", 60)),
        "stage_a_alpha": float(a_raw.get("alpha", 0.03)),
        "stage_a_threshold": float(a_raw.get("threshold", 0.0)),
        # ... (min_exposure_trade_count なし)
    }
```

```yaml
# default.yaml L43-48
stage_gate:
  stage_a:
    window_days: 60
    target_pass_rate: 0.15
    alpha: 0.03
    threshold: 0.0
```

### 変更後コード

```python
# config.py
def _build_stage_gate(...) -> StageGateConfig:
    a_raw = stage_gate_raw.get("stage_a") or {}
    kwargs: dict[str, Any] = {
        # 既存項目 (変更なし)
        "stage_a_window_days": int(a_raw.get("window_days", 60)),
        "stage_a_alpha": float(a_raw.get("alpha", 0.03)),
        "stage_a_threshold": float(a_raw.get("threshold", 0.0)),
        "min_exposure_trade_count": int(
            a_raw.get("min_exposure_trade_count", 1)
        ),
        # ...
    }
```

```yaml
# default.yaml
stage_gate:
  stage_a:
    window_days: 60
    target_pass_rate: 0.15
    alpha: 0.03
    threshold: 0.0
    min_exposure_trade_count: 1   # trade_count<この値は no_exposure 扱い (sentinel)
                                  # 不変条件: 1 <= min_exposure_trade_count < live_criteria.trade_count_min
```

### 波及変更
- `AGENTS.md`: なし
- skill: なし

### テスト計画
- [x] `test_config_loader_min_exposure_default` — default.yaml で 1 が設定される
- [x] `test_config_loader_min_exposure_invalid` — `trade_count_min >= 1` かつ `min_exposure_trade_count >= trade_count_min` で ValueError
- [x] `test_config_loader_min_exposure_with_zero_trade_count_min` — `trade_count_min=0` (min_config 相当) の場合は上限制約が発動しない

---

## 施策 3: calibrate_gate sentinel 除外フィルタ

### 変更箇所
- `src/alpha_factory/calibrate_gate.py` `aggregate_sample` (L283-363)

### 現行コード

```python
# calibrate_gate.py L325 等 — pool 構築箇所 (3 mode 全て)
pool = tuple(float(r["fitness_pen"]) for r in used)
```

### 変更後コード

```python
# calibrate_gate.py モジュール先頭 (import の後)
from src.alpha_factory.stage_gate import STAGE_A_FITNESS_SENTINELS


def _is_sentinel(value: float) -> bool:
    """fitness_pen が Stage A sentinel 値のいずれかと一致するか判定。

    閾値分離 (例: -1e8 より小さいか) ではなく **明示一致** で判定する理由:
    fitness_pen の通常実値 (sharpe - α·size_norm) は sharpe に下限 clamp が無いため
    理論上 sentinel 帯と被る可能性がある。明示一致のみが安全。
    """
    return value in STAGE_A_FITNESS_SENTINELS


# AggregatedSample dataclass に n_pool_used フィールドを追加
@dataclass(frozen=True)
class AggregatedSample:
    n_rows_total: int
    n_rows_used: int       # 集計対象範囲全体 (pass_rate 計算用、sentinel 含む)
    n_pool_used: int       # 新規: sentinel 除外後の pool 件数 (quantile 計算の実効サンプル数)
    pass_count_used: int
    actual_pass_rate: float
    fitness_pen_pool: tuple[float, ...]
    mode: AggregationMode
    window: int


# pool 構築箇所 (last_k_generations / all_generations)
pool = tuple(
    float(r["fitness_pen"])
    for r in used
    if not _is_sentinel(float(r["fitness_pen"]))
)
n_pool_used = len(pool)

# generation_weighted_mean では pool は全行 → 同じ filter 適用
pool = tuple(
    float(r["fitness_pen"])
    for r in rows_list
    if not _is_sentinel(float(r["fitness_pen"]))
)
n_pool_used = len(pool)

# AggregatedSample 構築時に n_pool_used を渡す
return AggregatedSample(
    n_rows_total=n_rows_total,
    n_rows_used=n_used,
    n_pool_used=n_pool_used,  # 新規
    ...
)
```

#### decide() の effective_sample_size は n_pool_used で判定

```python
def decide(sample: AggregatedSample, config: CalibrateConfig) -> Decision:
    prev = config.prev_threshold
    n_used = sample.n_rows_used

    # サンプルサイズ判定: pool の実効件数 (sentinel 除外後) で判断する
    # n_rows_used (sentinel 含む) を使うと「見せかけのサンプルサイズ充足」になる
    n_pool = sample.n_pool_used  # 新規参照
    if n_pool < config.min_sample_size:
        return Decision(
            decision="skip_sample_size",
            effective_sample_size=n_pool,  # pool 長を返す
            ...
        )
    ...
    # effective_sample_size は pool 長を使う (quantile 計算の実態と一致させる)
    return Decision(..., effective_sample_size=n_pool)
```

#### 補足: pass_count 計算は変更しない

`pass_count = sum(1 for r in used if bool(r["stage_a_pass"]))` は `stage_a_pass` bit ベースなので、sentinel 個体は元々 `stage_a_pass=False` で正しく扱われる。pass_count / actual_pass_rate の計算には sentinel 影響はない。

#### n_used と n_pool_used の役割分担

| フィールド | 目的 | sentinel 含む |
|-----------|------|--------------|
| `n_rows_used` | pass_rate 計算の母数 (集計対象範囲全体) | 含む |
| `n_pool_used` | quantile 計算の実効サンプル数 / skip 判定 | 含まない |

`decide()` の `effective_sample_size` は `n_pool_used` に変更することで、「pool で quantile 計算をするのに min_sample_size を n_rows_used で判定する」という矛盾を解消する。

### 波及変更
- `AGENTS.md`: なし
- skill: `zenigame-fx-calibrate-gate` の SKILL.md を Read して、フィルタ振る舞いの説明追加要否を確認 (実装時に判断)

### リスク
- `n_pool_used` フィールド追加により `AggregatedSample` を直接構築しているテストは引数を追加する必要がある → テスト計画に明記
- フィルタ後 `pool` が空 (`n_pool_used=0`) → `decide()` が `skip_sample_size` に入るため quantile 計算は実行されず安全
- `skip_zero_variance` は `pool` 内の分散 eps ガード用であり、sentinel 除外とは独立した概念 — `all_sentinel` は `skip_sample_size` として扱う (Warning 対応)

### テスト計画
- [x] `test_aggregate_sample_excludes_sentinels` — sentinel 値混入 archive 行で pool が sentinel を除外、`n_pool_used` が sentinel 除外後件数と一致
- [x] `test_aggregate_sample_pool_when_all_sentinel` — 全行 sentinel で pool が空タプル、`n_pool_used=0`、`decide()` が `skip_sample_size` になる
- [x] `test_aggregate_sample_normal_values_preserved` — 通常値混在で正常値だけ pool に入る
- [x] `test_decide_uses_n_pool_used_for_skip` — `n_rows_used >= min_sample_size` でも `n_pool_used < min_sample_size` なら `skip_sample_size`

---

## 施策 4: docs SSOT 更新

### 変更箇所
- `docs/alpha_factory/stage-gates.md` reason_codes セクション (L111 付近)

### 現行コード

```
- no_trades
- system_failure
- metric_unavailable
- below_threshold
```

### 変更後コード

```
### Stage A reason_codes (canonical)

判定優先順位: `system_failure` > `no_exposure` > `metric_unavailable` > `below_threshold`

| reason | 条件 | fitness_pen sentinel | 序列 |
|--------|------|---------------------|------|
| `system_failure` | evaluate_stage_a 内で例外 | `_SYSTEM_FAILURE_FITNESS = -1e12` | 最も厳しく罰する |
| `no_exposure` | `trade_count < stage_gate.stage_a.min_exposure_trade_count` (旧 `no_trades` を統一) | `_NO_EXPOSURE_FITNESS = -1e9` | 取引が成立せずリスク評価不能 |
| `metric_unavailable` | `sharpe is None` (取引はあるが std=0 等で sharpe 計算不能) | `_METRIC_UNAVAILABLE_FITNESS = -1e6` | 取引はあるが metric 不能 |
| `below_threshold` | `fitness_pen <= stage_a_threshold` | 実値 (sentinel ではない) | 通常通り淘汰 |

### min_exposure_trade_count 仕様

- 不変条件: `1 <= min_exposure_trade_count < live_criteria.trade_count_min`
- 初期値: 1 (live_criteria.trade_count_min=50 の 2%)
- 役割: stage_a レベルで「最小エクスポージャ未達個体」を sentinel 化し、GA selection_score の tie-break で取引する個体に劣後させる
- live_criteria.trade_count_min は触らない (禁止事項 #4)

### sentinel 序列

```
_SYSTEM_FAILURE_FITNESS (-1e12)
  < _NO_EXPOSURE_FITNESS (-1e9)
    < _METRIC_UNAVAILABLE_FITNESS (-1e6)
      < below_threshold (実値)
        < 通常 fitness_pen
```

意味:
- system が壊れた個体は再現性がないため最も厳しく罰する
- 取引が成立しなかった個体は次に厳しく罰する (リスク評価不能)
- metric が計算不能な個体は中程度に罰する (取引するだけ no_exposure よりはマシ)

### sentinel 値の扱い

- archive 行に直接保存される (`fitness_raw` / `fitness_pen` 双方)
- `calibrate_gate.aggregate_sample` の `fitness_pen_pool` からは **明示一致除外** (set membership) で取り除く
- run-report での表示は別 issue (本 phase 対象外)

### fitness_raw の意味論

`fitness_raw` は通常「ペナルティ前の sharpe 値」を表すが、sentinel ケースでは実 sharpe ではなく sentinel 定数 (`_SYSTEM_FAILURE_FITNESS` / `_NO_EXPOSURE_FITNESS` / `_METRIC_UNAVAILABLE_FITNESS`) を取り得る。

- これは「fitness_raw = 失敗時は sentinel を取り得る」という拡張意味論
- genome-archive-schema.md にも同様の注記を追加する (Suggestion 対応)
- 後段レポート解釈では `fitness_raw in STAGE_A_FITNESS_SENTINELS` のチェックで「評価失敗個体」と識別可能
```

### 波及変更
- `AGENTS.md`: なし
- `docs/alpha_factory/concepts/genome-archive-schema.md`: `fitness_raw` / `fitness_pen` フィールドの説明に「失敗時 sentinel を取り得る」旨を追記

### テスト計画
- [x] (該当なし — docs のみ)
- [x] markdown lint 通過

---

## 施策 5: 既存テスト更新 + 新規テスト

### 変更箇所
- `tests/alpha_factory/test_stage_gate.py` (L350-378 + 周辺)
- `tests/alpha_factory/test_config_loader.py` (相当箇所)
- 新規: `tests/alpha_factory/test_calibrate_gate_sentinel_filter.py`

### 既存テストの修正

```python
# 変更前
def test_no_trades_reason(self) -> None:
    """Constant 0.0 では entry シグナルが発生しない → trade_count == 0."""
    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    res = evaluate_stage_a(...)
    assert not res.passed
    assert res.reason_codes == ("no_trades",)

# 変更後
def test_no_exposure_reason(self) -> None:
    """trade_count < min_exposure_trade_count では no_exposure (旧 no_trades)."""
    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    res = evaluate_stage_a(...)
    assert not res.passed
    assert res.reason_codes == ("no_exposure",)
    payload = res.metrics["payload"]
    assert payload["fitness_pen"] == _NO_EXPOSURE_FITNESS  # sentinel
    assert payload["fitness_raw"] == _NO_EXPOSURE_FITNESS
```

```python
# system_failure テストも sentinel 確認を追加
def test_system_failure_reason(self) -> None:
    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = _RaisingEvaluator()
    res = evaluate_stage_a(...)
    assert not res.passed
    assert "system_failure" in res.reason_codes
    payload = res.metrics["payload"]
    assert payload["fitness_pen"] == _SYSTEM_FAILURE_FITNESS  # 新規 assert
```

### 新規テストの追加

```python
def test_min_exposure_trade_count_threshold(self) -> None:
    """min_exposure_trade_count=3 で trade_count=2 の個体が no_exposure 判定."""
    # 2 trades 発生する fixture
    config = StageGateConfig(min_exposure_trade_count=3)
    res = evaluate_stage_a(..., stage_config=config)
    assert "no_exposure" in res.reason_codes


def test_min_exposure_lt_trade_count_min_invariant(self) -> None:
    with pytest.raises(ValueError, match="min_exposure_trade_count"):
        StageGateConfig(min_exposure_trade_count=50)  # == trade_count_min
    with pytest.raises(ValueError, match="min_exposure_trade_count"):
        StageGateConfig(min_exposure_trade_count=0)  # < 1
```

### 事前作業: no_trades 全検索

実装前に以下を grep して `no_exposure` への置換漏れを防ぐ:

```bash
# codebase 全体で "no_trades" 文字列を検索
grep -rn "no_trades" src/ tests/ scripts/ docs/ config/
```

現時点で判明している置換箇所:
- `tests/alpha_factory/test_stage_gate.py` L363, L396 (reason_codes assert)
- `src/alpha_factory/stage_gate.py` L303-307 (コメント + 実装)

grep 結果で追加の箇所が見つかった場合は同一 commit 内で更新する。

### 判定優先順位テスト

```python
def test_reason_priority_system_failure_beats_no_exposure() -> None:
    """system_failure は no_exposure より優先 (exception がある場合は必ず system_failure)."""
    # exception + trade_count=0 でも system_failure が先に来る
    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = _RaisingEvaluator()  # 例外を発生させる
    # min_exposure_trade_count=1 なので trade_count=0 は no_exposure にもなりうる
    res = evaluate_stage_a(...)
    assert res.reason_codes[0] == "system_failure"

def test_reason_priority_no_exposure_beats_metric_unavailable() -> None:
    """trade_count < min_exposure では no_exposure になる (metric_unavailable より優先)."""
    # trade=0 → sharpe は None になるが no_exposure が先
    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    res = evaluate_stage_a(...)
    assert res.reason_codes[0] == "no_exposure"
    # metric_unavailable は no_exposure の後ろにはならない
    assert "metric_unavailable" not in res.reason_codes
```

### テスト計画
- [x] 事前: `grep -rn "no_trades"` でコードベース全網羅確認、置換漏れゼロを保証
- [x] 既存 `test_no_trades_reason` → `test_no_exposure_reason` リネーム + sentinel assert
- [x] 既存 `test_below_threshold_reason` の `no_trades` assert → `no_exposure` に更新
- [x] 既存 `test_system_failure_reason` に sentinel assert 追加
- [x] 新規 `test_metric_unavailable_sets_sentinel`
- [x] 新規 `test_min_exposure_trade_count_threshold`
- [x] 新規 `test_min_exposure_lt_trade_count_min_invariant`
- [x] 新規 `test_reason_priority_system_failure_beats_no_exposure` (優先順位確認)
- [x] 新規 `test_reason_priority_no_exposure_beats_metric_unavailable` (優先順位確認)
- [x] 新規 `test_aggregate_sample_excludes_sentinels` (calibrate_gate)
- [x] 新規 `test_aggregate_sample_pool_when_all_sentinel`

### リスク
- `grep` で `no_trades` が他ファイル (docs / config / skill SKILL.md 等) にも出現する可能性 → 実装前の grep で確認し、docs は施策4で対応済み

---

## 施策 6: run_ga 回帰テスト

### 変更箇所
- 新規: `tests/alpha_factory/test_run_ga_no_exposure_selection.py`

### 設計方針（Round 1 Critical 対応）

元不具合経路: `evaluate_stage_a (no-trade)` → `collect_stage_a` → `archive._required_float(0.0 fallback)` → `_update_cache (fp=0.0)` → `_select_best (0.0 > -3.5 で no-trade 個体が勝つ)`

Round 1 指摘: `_select_best` に sentinel を直接注入するだけでは、上記経路の `0.0 fallback` 問題 (修正前動作) を再現しない。**fail-first** にならないため回帰テストとして機能しない。

対策: `evaluate_stage_a` → `collect_stage_a` → `_update_cache` → `_select_best` の統合経路をテストする。

### テスト

```python
def test_no_exposure_individual_loses_in_full_pipeline() -> None:
    """統合経路テスト: evaluate_stage_a(no-trade) → collect_stage_a → _update_cache
    → _select_best の全行程で no-trade 個体が trading 個体に負けることを確認。

    元不具合の再現条件 (修正前):
    - evaluate_stage_a で trade_count=0 → fitness_pen=None → payload["fitness_pen"]=None
    - collect_stage_a → archive._required_float(default=0.0) で 0.0 保存
    - _update_cache → fp = float(0.0)
    - _select_best → (0,0,0, 0.0) > (0,0,0, -3.5) で no-trade 個体が勝つ (バグ)

    修正後:
    - evaluate_stage_a → fitness_pen = _NO_EXPOSURE_FITNESS (-1e9)
    - _update_cache → fp = float(-1e9)
    - _select_best → (0,0,0, -1e9) < (0,0,0, -3.5) で trading 個体が勝つ (期待動作)
    """
    # --- セットアップ ---
    # no-trade genome (ConstantPrimitiveEvaluator(0.0) → エントリなし)
    genome_no_trade = _one_clause_genome(name="no_trade_genome")
    # trading genome (AlternatingEvaluator → エントリあり、sharpe は低いが実値)
    genome_trading = _one_clause_genome(name="trading_genome")

    bars = _make_continuous_bars(3, bars_per_day=4)
    meta = usd_jpy_meta()
    bt_cfg = _backtest_config()
    stage_cfg = StageGateConfig()
    instrument = meta.instrument

    archive = GenomeArchive()
    lane_id = "test_lane"
    generation = 0

    # no-trade 個体: evaluate + collect
    result_no_trade = evaluate_stage_a(
        genome_no_trade, bars, meta, bt_cfg,
        ConstantPrimitiveEvaluator(value=0.0), stage_cfg
    )
    archive.collect_stage_a(
        genome_no_trade, lane_id, generation, result_no_trade,
        instrument=instrument
    )

    # trading 個体: evaluate + collect (sharpe は低い実値だが sentinel ではない)
    result_trading = evaluate_stage_a(
        genome_trading, bars, meta, bt_cfg,
        _AlternatingEvaluator(), stage_cfg
    )
    archive.collect_stage_a(
        genome_trading, lane_id, generation, result_trading,
        instrument=instrument
    )

    # cache 更新
    cache: dict[str, IndividualCacheEntry] = {}
    _update_cache(cache, [genome_no_trade, genome_trading], archive, lane_id, generation)

    # 検証: trading 個体が勝つ
    best_name, _ = _select_best(cache)
    assert best_name == "trading_genome", (
        f"no-trade genome should lose to trading genome, but got best={best_name!r}\n"
        f"cache: {cache}"
    )

    # 追加検証: no-trade 個体の fitness_pen が sentinel であること
    no_trade_fp = cache["no_trade_genome"].fitness_pen
    assert no_trade_fp == _NO_EXPOSURE_FITNESS, (
        f"Expected _NO_EXPOSURE_FITNESS, got {no_trade_fp}"
    )
```

### 並行計算経路 (C2) のテスト

`_tournament` と elite sort も `selection_score` (= `fitness_pen` を含む lexicographic tuple) を使うため、同一の sentinel 比較軸が適用される。追加テスト:

```python
def test_tournament_excludes_no_exposure_sentinel() -> None:
    """_tournament で no-trade (sentinel) 個体が trading 個体に負けることを確認.

    k=2, population=[no_trade, trading] の tournament で trading が選ばれる。
    """
    genome_no_trade = _one_clause_genome(name="no_trade_genome")
    genome_trading = _one_clause_genome(name="trading_genome")

    cache = {
        "no_trade_genome": IndividualCacheEntry(
            generation=0,
            fitness_pen=_NO_EXPOSURE_FITNESS,
            stage_a_pass=False, stage_b_pass=False, stage_c_pass=False,
        ),
        "trading_genome": IndividualCacheEntry(
            generation=0,
            fitness_pen=-3.5,
            stage_a_pass=False, stage_b_pass=False, stage_c_pass=False,
        ),
    }
    pop = [genome_no_trade, genome_trading]
    rng = random.Random(42)
    # k=2 → 両方 sample → trading が常に勝つ
    winner = _tournament(pop, cache, rng, k=2)
    assert winner.name == "trading_genome"


def test_elite_sort_puts_no_exposure_last() -> None:
    """elite sort で no-trade sentinel 個体が末尾に来ることを確認."""
    cache = {
        "no_trade": IndividualCacheEntry(0, _NO_EXPOSURE_FITNESS, False, False, False),
        "negative": IndividualCacheEntry(0, -3.5, False, False, False),
        "positive": IndividualCacheEntry(0, 0.5, False, False, False),
    }
    pop = [_one_clause_genome(name=n) for n in cache]
    sorted_pop = sorted(pop, key=lambda g: cache[g.name].selection_score, reverse=True)
    assert sorted_pop[0].name == "positive"
    assert sorted_pop[-1].name == "no_trade"
```

### テスト計画
- [x] FAIL 確認 (修正前コードでは `cache["no_trade_genome"].fitness_pen == 0.0` になり `_select_best` で no-trade が勝つ)
- [x] 修正後 PASS 確認 (sentinel = -1e9 が正しく伝搬し trading が勝つ)
- [x] `test_tournament_excludes_no_exposure_sentinel` (C2 並行経路)
- [x] `test_elite_sort_puts_no_exposure_last` (C2 elite sort 経路)

---

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | **incremental** |
| 判断根拠 | 既存 stage_gate / archive / config / docs に閉じた変更で、外部 API 互換性 (CLI / skill) は維持。worktree 1 並列で完結。 |
| 競合リスク | calibrate_gate 系の他改修と同時並行になる場合に sentinel フィルタ箇所で衝突可能性 (現状他 TODO に該当なし) |
| 想定実装時間 | **中** (テスト含めて 4-6 時間) |

## 実装順序 (推奨)

1. 施策 1: stage_gate.py に sentinel 定数 / `evaluate_stage_a` の 3 経路 sentinel 化 / `min_exposure_trade_count` 追加
2. 施策 5: 既存テスト更新 + 新規 stage_gate テスト (この時点で `pytest tests/alpha_factory/test_stage_gate.py` 通過)
3. 施策 6: run_ga 回帰テストを書き、FAIL 確認 → 修正後 PASS
4. 施策 2: config loader / yaml
5. 施策 3: calibrate_gate sentinel フィルタ + テスト
6. 施策 4: docs SSOT 更新

## ruff / mypy 通過基準

- `uv run ruff check src/alpha_factory/ tests/alpha_factory/`
- `uv run mypy src/alpha_factory/`
- 全テスト: `uv run pytest tests/alpha_factory/ -x`

## 全体リスクサマリ

- (低) 既存テスト 1 ヶ所のリネーム漏れ → grep で網羅
- (低) `min_exposure_trade_count` invariant 違反で existing config が破綻 → default.yaml 設定で 1 を保証
- (中) calibrate_gate sentinel フィルタ後の pool が空になる → 既存 min_sample_size 30 ガードで safely skip
- (低) docs SSOT と code の語彙乖離 → 同一 commit 内で更新
