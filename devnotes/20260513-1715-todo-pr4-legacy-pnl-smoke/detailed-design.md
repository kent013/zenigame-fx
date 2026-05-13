# PR4 詳細設計: legacy_pnl_smoke fitness opt-in + anti-luck guard

## 実装差分

### 1. `src/alpha_factory/config.py`

#### 1.1 `Phase4Config` 新規追加

`Phase2Config` の直下に追加 (= 同型 pattern):

```python
@dataclass(frozen=True)
class Phase4Config:
    """PR4 = legacy_pnl_smoke fitness opt-in + anti-luck guard 用 config.

    fitness_mode:
        - legacy: 現状 fitness 関数 (= sharpe - α*size_norm - tc_penalty)、 default、
          完全行動不変。
        - legacy_pnl_smoke: legacy + β*clipped_pnl_slack*persistence_weight
          - lucky_run_penalty。 1 RUN smoke 検証必須。

    詳細: devnotes/20260513-1715-todo-pr4-legacy-pnl-smoke/.
    """

    fitness_mode: Literal["legacy", "legacy_pnl_smoke"] = "legacy"
    beta: float = 0.05
    persistence_weight: float = 0.5  # PR4 minimal scope = 固定値
    lucky_hard_penalty: float = 1.0
    lucky_soft_penalty: float = 0.3

    def __post_init__(self) -> None:
        valid = {"legacy", "legacy_pnl_smoke"}
        if self.fitness_mode not in valid:
            raise ValueError(
                f"Phase4Config.fitness_mode must be one of {sorted(valid)}, "
                f"got {self.fitness_mode!r}."
            )
        if not 0.0 <= self.beta <= 1.0:
            raise ValueError(
                f"Phase4Config.beta must be in [0.0, 1.0], got {self.beta}"
            )
        if not 0.0 <= self.persistence_weight <= 1.0:
            raise ValueError(
                f"Phase4Config.persistence_weight must be in [0.0, 1.0], "
                f"got {self.persistence_weight}"
            )
        if self.lucky_hard_penalty < 0.0 or self.lucky_soft_penalty < 0.0:
            raise ValueError(
                f"Phase4Config.lucky_* penalty must be non-negative, "
                f"got hard={self.lucky_hard_penalty} soft={self.lucky_soft_penalty}"
            )
        # HARD >= SOFT 契約 (= hard は max_dd≈0、 soft は max_dd<0.5%、 hard 側が
        # 強い違反シグナル)
        if self.lucky_hard_penalty < self.lucky_soft_penalty:
            raise ValueError(
                f"Phase4Config.lucky_hard_penalty ({self.lucky_hard_penalty}) "
                f"must be >= lucky_soft_penalty ({self.lucky_soft_penalty}) "
                f"(= hard は max_dd≈0 即時抑制、 soft は max_dd<0.5% 連続抑制、 "
                f"hard 側が強い signal でなければ順序整合性違反)"
            )
```

#### 1.2 `AlphaFactoryConfig` に追加

```python
phase4: Phase4Config = field(default_factory=Phase4Config)  # PR4 で追加
```

#### 1.3 config loader 更新 (`_build_config` / `_build_stage_gate_config`)

```python
phase4 = _build_phase4(raw.get("phase4") or {})

stage_gate = _build_stage_gate_config(
    raw.get("stage_gate", {}),
    ...,
    phase2_canonical_metrics_mode=phase2.canonical_metrics_mode,
    phase4_fitness_mode=phase4.fitness_mode,  # PR4 追加
    phase4_beta=phase4.beta,
    phase4_persistence_weight=phase4.persistence_weight,
    phase4_lucky_hard_penalty=phase4.lucky_hard_penalty,
    phase4_lucky_soft_penalty=phase4.lucky_soft_penalty,
)

return AlphaFactoryConfig(
    ...,
    phase4=phase4,
)


def _build_phase4(raw: Mapping[str, Any]) -> Phase4Config:
    """PR4: ``phase4`` yaml section → :class:`Phase4Config`."""
    allowed = {
        "fitness_mode", "beta", "persistence_weight",
        "lucky_hard_penalty", "lucky_soft_penalty",
    }
    unknown_keys = set(raw.keys()) - allowed
    if unknown_keys:
        raise ValueError(f"phase4: unknown keys {sorted(unknown_keys)}")
    kwargs: dict[str, Any] = {}
    if "fitness_mode" in raw:
        kwargs["fitness_mode"] = str(raw["fitness_mode"])
    for numeric_key in ("beta", "persistence_weight",
                        "lucky_hard_penalty", "lucky_soft_penalty"):
        if numeric_key in raw:
            kwargs[numeric_key] = float(raw[numeric_key])
    return Phase4Config(**kwargs)
```

### 2. `src/alpha_factory/stage_gate.py`

#### 2.1 `StageGateConfig` に PR4 fields 追加

`phase2_canonical_metrics_mode` の直後に追加:

```python
# PR4: legacy_pnl_smoke fitness opt-in + anti-luck guard
# (= AlphaFactoryConfig.phase4 から伝搬)。 default `legacy` で行動完全不変。
# 詳細: devnotes/20260513-1715-todo-pr4-legacy-pnl-smoke/
phase4_fitness_mode: Literal["legacy", "legacy_pnl_smoke"] = "legacy"
phase4_beta: float = 0.05
phase4_persistence_weight: float = 0.5
phase4_lucky_hard_penalty: float = 1.0
phase4_lucky_soft_penalty: float = 0.3
```

`__post_init__` で `Phase4Config` と同じ範囲検証 + HARD>=SOFT 契約を追加 (= 重複だが SSOT は config 側、 stage_gate 側は最終防御線)。

#### 2.2 helper 関数 2 個追加

`_canonical_shadow_summary` の直後に追加:

```python
# PR4: legacy_pnl_smoke fitness opt-in の helper 関数。
# 二層 PnL target (short 12k 主圧 + long 50k 方向付け) と二段 anti-luck guard。
# 詳細: devnotes/20260513-1715-todo-pr4-legacy-pnl-smoke/

# PR4: 二層 PnL target (Codex Y Round 3-5 確定)
_PR4_PNL_SHORT_TARGET: Final[float] = 12000.0   # archive p95 近辺 = 探索勾配あり
_PR4_PNL_LONG_TARGET: Final[float] = 50000.0    # mission (live_criteria.total_pnl_min)
_PR4_SHORT_WEIGHT: Final[float] = 0.7           # short 主圧
_PR4_LONG_WEIGHT: Final[float] = 0.3            # long 方向付け
_PR4_LUCKY_TRIGGER_PNL: Final[float] = 12000.0  # short target 達成個体のみ対象
_PR4_LUCKY_HARD_DD_EPSILON: Final[float] = 1e-9 # max_dd_pct ≒ 0 判定
_PR4_LUCKY_SOFT_DD_THRESHOLD: Final[float] = 0.5 # 0.5% 未満で soft trigger
_PR4_LUCKY_SOFT_TC_THRESHOLD: Final[int] = 80    # trade_count < 80 で soft trigger


def _compute_clipped_pnl_slack(total_pnl: float) -> float:
    """PR4: 二層 PnL target からの clipped slack (= mission_shortfall 探索圧).

    short (12k) を主圧、 long (50k = mission) を方向付け。 short は [-1.0, +2.0]、
    long は [-1.0, +1.0] にクリップして Goodhart を抑制.

    Args:
        total_pnl: Stage A backtest の total_pnl (= float JPY).

    Returns:
        slack 値 (= 加重平均、 値域は ``[-1.0, 0.7*2.0 + 0.3*1.0]`` ≒ ``[-1.0, 1.7]``).

    詳細: devnotes/20260513-1715-todo-pr4-legacy-pnl-smoke/ § Codex Y Round 5.
    """
    short = (total_pnl - _PR4_PNL_SHORT_TARGET) / _PR4_PNL_SHORT_TARGET
    short_clip = max(-1.0, min(2.0, short))
    long_ = (total_pnl - _PR4_PNL_LONG_TARGET) / _PR4_PNL_LONG_TARGET
    long_clip = max(-1.0, min(1.0, long_))
    return _PR4_SHORT_WEIGHT * short_clip + _PR4_LONG_WEIGHT * long_clip


def _compute_lucky_run_penalty(
    total_pnl: float,
    max_dd_pct: float,
    trade_count: int,
    *,
    hard_penalty: float,
    soft_penalty: float,
) -> float:
    """PR4: 二段 anti-luck guard (= max_dd≈0 lucky run の連続抑制).

    短期 target (12k) 達成個体のみ対象。 二段:
    - hard_lucky_flag: ``max_dd_pct <= epsilon (≒ 0)`` → ``hard_penalty`` (強)
    - soft_lucky_penalty: ``max_dd_pct < 0.5% AND trade_count < 80`` → ``soft_penalty`` (連続)

    その他 (= max_dd > 0.5% or trade_count >= 80) → 0.0.

    Args:
        total_pnl: Stage A backtest の total_pnl (= float JPY).
        max_dd_pct: Stage A backtest の max_drawdown_pct (= percent, e.g. 1.0 = 1%).
        trade_count: Stage A backtest の trade_count (= int).
        hard_penalty: ``stage_config.phase4_lucky_hard_penalty``.
        soft_penalty: ``stage_config.phase4_lucky_soft_penalty``.

    Returns:
        penalty 値 (= 0.0 / soft_penalty / hard_penalty のいずれか、 非負).

    詳細: devnotes/20260513-1715-todo-pr4-legacy-pnl-smoke/ § Codex Y Round 4.
    """
    if total_pnl <= _PR4_LUCKY_TRIGGER_PNL:
        return 0.0
    if max_dd_pct <= _PR4_LUCKY_HARD_DD_EPSILON:
        return hard_penalty
    if (
        max_dd_pct < _PR4_LUCKY_SOFT_DD_THRESHOLD
        and trade_count < _PR4_LUCKY_SOFT_TC_THRESHOLD
    ):
        return soft_penalty
    return 0.0
```

#### 2.3 `evaluate_stage_a` の fitness 計算分岐

既存 `fitness_pen = fitness_raw - α*size_norm - tc_penalty` ブロック (= line 920-938) を mode 分岐に書き換え:

```python
# 既存 (= line 920 周辺、 sharpe_raw is not None 経路)
assert size_norm_val is not None  # type narrowing
fitness_raw = sharpe_raw
# cycle 6: trade_count adequacy penalty
entry_count_min_lc = int(stage_config.live_criteria["trade_count_min"])
if trade_count < entry_count_min_lc:
    trade_count_penalty = (
        stage_config.stage_a_trade_count_penalty_gamma
        * (entry_count_min_lc - trade_count)
        / entry_count_min_lc
    )
else:
    trade_count_penalty = 0.0

# PR4: legacy 部分 (= sharpe_raw - α*size_norm、 tc_penalty は最終合算で 1 回控除)
sharpe_term = fitness_raw - stage_config.stage_a_alpha * size_norm_val

# PR4: fitness mode 分岐
if stage_config.phase4_fitness_mode == "legacy":
    # 現状 fitness (= 完全行動不変)
    fitness_pen = sharpe_term - trade_count_penalty
    pnl_slack_observed = None  # payload 用 (observe only)
    lucky_penalty_observed = None
elif stage_config.phase4_fitness_mode == "legacy_pnl_smoke":
    # PR4 新規: PnL 探索圧 + anti-luck guard
    pnl_slack = _compute_clipped_pnl_slack(total_pnl_a)
    pnl_term = (
        stage_config.phase4_beta
        * pnl_slack
        * stage_config.phase4_persistence_weight
    )
    lucky_penalty = _compute_lucky_run_penalty(
        total_pnl=total_pnl_a,
        max_dd_pct=float(bt.max_drawdown_pct),
        trade_count=trade_count,
        hard_penalty=stage_config.phase4_lucky_hard_penalty,
        soft_penalty=stage_config.phase4_lucky_soft_penalty,
    )
    fitness_pen = sharpe_term + pnl_term - trade_count_penalty - lucky_penalty
    pnl_slack_observed = pnl_slack
    lucky_penalty_observed = lucky_penalty
else:
    # __post_init__ で範囲検証済だが防御的に
    raise RuntimeError(
        f"unknown phase4_fitness_mode: {stage_config.phase4_fitness_mode!r}"
    )

if fitness_pen <= stage_config.stage_a_threshold:
    reasons.append("below_threshold")
```

注: 既存実装は `bt.max_drawdown_pct` を `total_pnl_a` と並んで参照しているが、 PR4 では明示的に `float(bt.max_drawdown_pct)` で再取得 (= line 786-790 周辺の `total_pnl_a` 計算と同列で `max_dd_a` を追加するのが理想)。 実装時に `bt` 変数の scope と `BacktestMetrics.max_drawdown_pct` を確認。

#### 2.3.1 sentinel 経路の不変性契約 (= Codex 設計レビュー Round 1 [Critical] 反映)

**重要**: `evaluate_stage_a` には canonical 経路 4 種類があり、 PR4 の fitness 計算分岐は **`below_threshold` 経路のみで発火** する。 他 3 経路 (= `system_failure` / `no_exposure` / `metric_unavailable`) では legacy_pnl_smoke mode でも **完全 skip** され、 既存 sentinel fitness 値が legacy mode と完全一致することを契約として固定する:

```python
# 既存 判定優先順位 (= 不変):
#   system_failure > no_exposure > metric_unavailable > below_threshold
if exception_caught:
    reasons.append("system_failure")
    fitness_pen = SYSTEM_FAILURE_FITNESS  # = -1e12、 mode 関係なし
elif trade_count < stage_config.min_exposure_trade_count:
    reasons.append("no_exposure")
    fitness_pen = NO_EXPOSURE_FITNESS  # = -1e9、 mode 関係なし
elif sharpe_raw is None:
    reasons.append("metric_unavailable")
    fitness_pen = METRIC_UNAVAILABLE_FITNESS  # = -1e6、 mode 関係なし
else:
    # ===== ここから PR4 fitness mode 分岐 (= below_threshold 経路のみ) =====
    if stage_config.phase4_fitness_mode == "legacy":
        ...
    elif stage_config.phase4_fitness_mode == "legacy_pnl_smoke":
        ...
```

= **sentinel 3 経路 (system_failure / no_exposure / metric_unavailable) は legacy mode と legacy_pnl_smoke mode で fitness_pen が完全一致**。 これは payload 内 `phase4_fitness_mode` 記録とは独立した契約 (= `phase4_pnl_slack` / `phase4_lucky_penalty` は sentinel 経路では `None`)。

これは「opt-in default OFF で行動完全不変」 契約 + 「smoke 経路でも sentinel は不変」 契約の 2 層保証。

#### 2.3.2 境界等号値の仕様固定 (= Codex 設計レビュー Round 1 [Critical] 反映)

`_compute_clipped_pnl_slack` / `_compute_lucky_run_penalty` の境界仕様を「等号でどちらに倒すか」 まで明文化:

**`_compute_clipped_pnl_slack`**:
- `total_pnl == 12000.0` (= short target): short_slack = (12000-12000)/12000 = 0.0、 clip 範囲内 → 加重後 `0.7*0 + 0.3*long_slack`
- `total_pnl == 50000.0` (= long target): long_slack = 0.0、 short_slack = (50000-12000)/12000 = 3.17 → clip +2.0 → 加重後 `0.7*2.0 + 0.3*0 = 1.4`
- clip 境界 (= short_slack = 2.0 / -1.0、 long_slack = 1.0 / -1.0) は `max` / `min` で **境界値を含む** (= `clip 2.0` で `slack = 2.0` も許容)

**`_compute_lucky_run_penalty`** (= 三段分岐の境界、 等号は **緩い側** に倒す):
- `total_pnl == 12000.0` (= trigger 境界): **trigger 対象外 (= 0.0)** (= `total_pnl > 12000` で発火、 `>` 厳密不等号、 12000 ちょうどは免責)
- `total_pnl == 12000.001`: trigger 対象
- `max_dd_pct == 1e-9` (= epsilon): **hard penalty 対象 (= `<=` 等号含む)** (= `max_dd_pct <= 1e-9` で hard、 epsilon ちょうどは hard)
- `max_dd_pct == 0.5` (= soft threshold): **soft penalty 対象外 (= 0.0)** (= `max_dd_pct < 0.5` で soft、 0.5 ちょうどは免責)
- `trade_count == 80` (= soft trade count threshold): **soft penalty 対象外 (= 0.0)** (= `trade_count < 80` で soft、 80 ちょうどは免責)

**等号の方向選択の根拠**:
- `total_pnl > 12000`: 12000 ちょうどを「short target ぎり達成」 とみなして lucky 判定対象外 (= 達成個体への過剰罰則回避)
- `max_dd_pct <= 1e-9`: epsilon 内は数値誤差込みでゼロ扱い、 hard penalty 対象 (= 真の lucky run 検出)
- `max_dd_pct < 0.5`: 0.5 ちょうどは「ぎりぎり robust」 とみなして免責 (= 過剰罰則回避)
- `trade_count < 80`: 80 ちょうどは「ぎりぎり robust」 とみなして免責 (= 同上)

これらの境界仕様は本詳細設計の **SSOT**、 helper 実装と test 双方で厳密に固定する。

#### 2.4 payload に observe-only fields 追加

`metrics_envelope["payload"]` に追加 (= archive 列拡張なし、 in-memory only):

```python
"payload": {
    "fitness_raw": fitness_raw,
    "size_norm": size_norm_val,
    "fitness_pen": fitness_pen,
    "alpha_a": stage_config.stage_a_alpha,
    "gamma_trade_count": stage_config.stage_a_trade_count_penalty_gamma,
    "threshold": stage_config.stage_a_threshold,
    "trade_count": trade_count,
    "trade_sharpe_raw": sharpe_raw,
    "active_clause": active_clause_count,
    "total_pnl": total_pnl_a,
    # PR4: fitness mode + observed values + config snapshot
    # (= archive 列拡張なし、 diagnostics sidecar 用、 future migration 監査の
    # 再現性確保、 Codex 設計レビュー Round 1 [Warning] 反映で config 値も記録)
    "phase4_fitness_mode": stage_config.phase4_fitness_mode,
    "phase4_pnl_slack": pnl_slack_observed,         # legacy mode は None
    "phase4_lucky_penalty": lucky_penalty_observed, # legacy mode は None
    "phase4_beta": stage_config.phase4_beta,
    "phase4_persistence_weight": stage_config.phase4_persistence_weight,
    "phase4_lucky_hard_penalty": stage_config.phase4_lucky_hard_penalty,
    "phase4_lucky_soft_penalty": stage_config.phase4_lucky_soft_penalty,
}
```

注: Stage A 既存 payload に `canonical_shadow_b_is` は無い (= Stage B/C にのみ)、 PR4 では Stage A しか触らないため shadow 列追加なし。

注: sentinel 経路 (system_failure / no_exposure / metric_unavailable) では `pnl_slack_observed` / `lucky_penalty_observed` は **`None`** で残り (= mode 分岐に到達しないため)、 残りの config snapshot field は常に値が入る (= mode 設定自体は不変)。

### 2.5 `scripts/alpha_factory/run_ga.py` CLI 拡張 (= Codex 設計レビュー Round 2 非 blocking note 2 反映)

smoke 実行容易化のため `--fitness-mode` CLI 引数を追加:

```python
# _parse_args() 内 (= --stage-a-threshold の隣):
p.add_argument(
    "--fitness-mode",
    choices=["legacy", "legacy_pnl_smoke"],
    default=None,
    help=(
        "PR4: Stage A fitness mode を CLI で明示指定 (yaml phase4.fitness_mode より優先)。"
        "未指定時は yaml の値 (default `legacy` = 行動完全不変)。"
        "smoke 時のみ `legacy_pnl_smoke` 指定。"
    ),
)
```

`_args_to_overrides()` 内:
```python
return {
    ...
    "phase4": {
        "fitness_mode": args.fitness_mode,  # None なら yaml 値を維持
    },
}
```

これで smoke 時は yaml 編集なしで `uv run python scripts/alpha_factory/run_ga.py --fitness-mode legacy_pnl_smoke ...` で実行可能 (= 既存 `--stage-a-threshold` と同型の override 経路)。

### 3. `config/alpha_factory/default.yaml`

PR4 関連 yaml section 追加 (= optional、 未指定なら Phase4Config default):

```yaml
# PR4: legacy_pnl_smoke fitness opt-in + anti-luck guard
# default legacy で行動完全不変。 1 RUN smoke 検証後に legacy_pnl_smoke 切替を検討。
# 詳細: devnotes/20260513-1715-todo-pr4-legacy-pnl-smoke/
# @why: PR1-PR3 で観測基盤完成、 PR4 で初の行動変更 (Codex Y Round 5 確定)。
phase4:
  fitness_mode: legacy  # legacy | legacy_pnl_smoke
  beta: 0.05
  persistence_weight: 0.5
  lucky_hard_penalty: 1.0
  lucky_soft_penalty: 0.3
```

### 4. `tests/alpha_factory/test_stage_gate.py` + 関連

#### 4.1 helper unit tests (新規ファイル or 既存に追記)

```python
def test_pr4_compute_clipped_pnl_slack_below_short_target() -> None:
    """PR4: total_pnl が short target (12k) 未満 → short_slack 負値 + long_slack 負値 (1.0 clip)."""
    from src.alpha_factory.stage_gate import _compute_clipped_pnl_slack
    # total_pnl=0: short=(0-12000)/12000=-1.0、 long=(0-50000)/50000=-1.0
    # 加重: 0.7*(-1.0) + 0.3*(-1.0) = -1.0
    assert _compute_clipped_pnl_slack(0.0) == pytest.approx(-1.0)


def test_pr4_compute_clipped_pnl_slack_at_short_target() -> None:
    """PR4: total_pnl=short_target → short_slack=0、 long_slack=負値."""
    from src.alpha_factory.stage_gate import _compute_clipped_pnl_slack
    # short=(12000-12000)/12000=0、 long=(12000-50000)/50000=-0.76 → clip -0.76
    # 加重: 0.7*0 + 0.3*(-0.76) = -0.228
    assert _compute_clipped_pnl_slack(12000.0) == pytest.approx(0.3 * (-0.76))


def test_pr4_compute_clipped_pnl_slack_at_long_target() -> None:
    """PR4: total_pnl=long_target (50k) → short_slack clip +2.0、 long_slack=0."""
    from src.alpha_factory.stage_gate import _compute_clipped_pnl_slack
    # short=(50000-12000)/12000=3.17 → clip +2.0
    # long=(50000-50000)/50000=0
    # 加重: 0.7*2.0 + 0.3*0 = 1.4
    assert _compute_clipped_pnl_slack(50000.0) == pytest.approx(0.7 * 2.0)


def test_pr4_compute_clipped_pnl_slack_above_long_target() -> None:
    """PR4: total_pnl=100k → 両 slack clip 上限 = 0.7*2.0 + 0.3*1.0 = 1.7."""
    from src.alpha_factory.stage_gate import _compute_clipped_pnl_slack
    assert _compute_clipped_pnl_slack(100000.0) == pytest.approx(1.7)


def test_pr4_compute_lucky_run_penalty_below_trigger_returns_zero() -> None:
    """PR4: total_pnl <= 12000 → penalty 0.0 (= short target 未達なら lucky 判定対象外)."""
    from src.alpha_factory.stage_gate import _compute_lucky_run_penalty
    assert _compute_lucky_run_penalty(
        total_pnl=10000.0, max_dd_pct=0.0, trade_count=50,
        hard_penalty=1.0, soft_penalty=0.3,
    ) == 0.0


def test_pr4_compute_lucky_run_penalty_hard_trigger_max_dd_zero() -> None:
    """PR4: total_pnl > 12000 AND max_dd_pct == 0.0 → hard_penalty."""
    from src.alpha_factory.stage_gate import _compute_lucky_run_penalty
    assert _compute_lucky_run_penalty(
        total_pnl=15000.0, max_dd_pct=0.0, trade_count=100,
        hard_penalty=1.0, soft_penalty=0.3,
    ) == 1.0


def test_pr4_compute_lucky_run_penalty_soft_trigger() -> None:
    """PR4: total_pnl > 12000 AND max_dd_pct < 0.5% AND trade_count < 80 → soft."""
    from src.alpha_factory.stage_gate import _compute_lucky_run_penalty
    assert _compute_lucky_run_penalty(
        total_pnl=15000.0, max_dd_pct=0.3, trade_count=60,
        hard_penalty=1.0, soft_penalty=0.3,
    ) == 0.3


def test_pr4_compute_lucky_run_penalty_no_trigger_high_trade_count() -> None:
    """PR4: max_dd<0.5% でも trade_count>=80 なら robust 候補とみなして penalty 0.0."""
    from src.alpha_factory.stage_gate import _compute_lucky_run_penalty
    assert _compute_lucky_run_penalty(
        total_pnl=15000.0, max_dd_pct=0.3, trade_count=100,
        hard_penalty=1.0, soft_penalty=0.3,
    ) == 0.0


def test_pr4_compute_lucky_run_penalty_no_trigger_high_dd() -> None:
    """PR4: max_dd>=0.5% なら通常 robust 候補とみなして penalty 0.0."""
    from src.alpha_factory.stage_gate import _compute_lucky_run_penalty
    assert _compute_lucky_run_penalty(
        total_pnl=15000.0, max_dd_pct=1.0, trade_count=60,
        hard_penalty=1.0, soft_penalty=0.3,
    ) == 0.0


# === 境界等号テスト (= Codex 設計レビュー Round 1 [Critical] 反映、 § 2.3.2) ===


def test_pr4_compute_lucky_run_penalty_total_pnl_exact_trigger_is_exempt() -> None:
    """PR4: total_pnl==12000.0 ちょうど → 対象外 (= `>` 厳密不等号、 境界免責)."""
    from src.alpha_factory.stage_gate import _compute_lucky_run_penalty
    # 12000 ちょうどは「short target ぎり達成」 とみなして lucky 判定対象外
    assert _compute_lucky_run_penalty(
        total_pnl=12000.0, max_dd_pct=0.0, trade_count=50,
        hard_penalty=1.0, soft_penalty=0.3,
    ) == 0.0


def test_pr4_compute_lucky_run_penalty_max_dd_exactly_epsilon_is_hard() -> None:
    """PR4: max_dd_pct==1e-9 ちょうど → hard 対象 (= `<=` 等号含む、 数値誤差込み)."""
    from src.alpha_factory.stage_gate import _compute_lucky_run_penalty
    assert _compute_lucky_run_penalty(
        total_pnl=15000.0, max_dd_pct=1e-9, trade_count=50,
        hard_penalty=1.0, soft_penalty=0.3,
    ) == 1.0


def test_pr4_compute_lucky_run_penalty_max_dd_exactly_soft_threshold_is_exempt() -> None:
    """PR4: max_dd_pct==0.5 ちょうど → 対象外 (= `<` 厳密不等号、 境界免責)."""
    from src.alpha_factory.stage_gate import _compute_lucky_run_penalty
    # 0.5 ちょうどは「ぎりぎり robust」 とみなして免責
    assert _compute_lucky_run_penalty(
        total_pnl=15000.0, max_dd_pct=0.5, trade_count=50,
        hard_penalty=1.0, soft_penalty=0.3,
    ) == 0.0


def test_pr4_compute_lucky_run_penalty_trade_count_exactly_80_is_exempt() -> None:
    """PR4: trade_count==80 ちょうど → 対象外 (= `<` 厳密不等号、 境界免責)."""
    from src.alpha_factory.stage_gate import _compute_lucky_run_penalty
    # 80 ちょうどは「ぎりぎり robust」 とみなして免責
    assert _compute_lucky_run_penalty(
        total_pnl=15000.0, max_dd_pct=0.3, trade_count=80,
        hard_penalty=1.0, soft_penalty=0.3,
    ) == 0.0


def test_pr4_compute_clipped_pnl_slack_short_clip_upper_bound_inclusive() -> None:
    """PR4: short_slack の clip 上限 +2.0 は境界値を含む (= total_pnl=36000 で正確に 2.0)."""
    from src.alpha_factory.stage_gate import _compute_clipped_pnl_slack
    # total_pnl=36000: short=(36000-12000)/12000=2.0 (= clip 上限ちょうど)
    # long=(36000-50000)/50000=-0.28 (= clip 範囲内)
    # 加重: 0.7*2.0 + 0.3*(-0.28) = 1.4 - 0.084 = 1.316
    assert _compute_clipped_pnl_slack(36000.0) == pytest.approx(1.4 - 0.084)


def test_pr4_compute_clipped_pnl_slack_total_pnl_at_short_target_exact() -> None:
    """PR4: total_pnl==12000.0 ちょうど → short_slack=0.0 (= clip 範囲内、 境界等号値)."""
    from src.alpha_factory.stage_gate import _compute_clipped_pnl_slack
    # short=(12000-12000)/12000=0、 long=(12000-50000)/50000=-0.76 (clip 範囲内)
    # 加重: 0.7*0 + 0.3*(-0.76) = -0.228
    assert _compute_clipped_pnl_slack(12000.0) == pytest.approx(0.3 * (12000 - 50000) / 50000)
```

#### 4.2 integration tests (stage_gate evaluate_stage_a)

```python
def test_pr4_legacy_mode_preserves_fitness_pen_regression_zero() -> None:
    """PR4: legacy mode で fitness_pen は変更前と完全一致 (= regression 0)."""
    # 既存 evaluate_stage_a を呼び、 legacy mode (= default) で fitness_pen を確認
    cfg = StageGateConfig(phase4_fitness_mode="legacy")
    ...
    # 期待値 = fitness_raw - alpha*size_norm - tc_penalty
    assert result.metrics["payload"]["fitness_pen"] == expected_legacy


def test_pr4_legacy_pnl_smoke_mode_adds_pnl_term_and_lucky_penalty() -> None:
    """PR4: legacy_pnl_smoke mode で fitness_pen が legacy + pnl_term - lucky_penalty."""
    cfg = StageGateConfig(phase4_fitness_mode="legacy_pnl_smoke",
                          phase4_beta=0.05, phase4_persistence_weight=0.5)
    ...
    expected = (
        fitness_raw - alpha*size_norm
        + 0.05 * pnl_slack * 0.5
        - tc_penalty - lucky_penalty
    )
    assert result.metrics["payload"]["fitness_pen"] == pytest.approx(expected)


def test_pr4_payload_records_fitness_mode_and_observations() -> None:
    """PR4: payload に fitness_mode + pnl_slack + lucky_penalty を記録."""
    # legacy mode
    cfg_legacy = StageGateConfig(phase4_fitness_mode="legacy")
    res = evaluate_stage_a(..., stage_config=cfg_legacy)
    payload = res.metrics["payload"]
    assert payload["phase4_fitness_mode"] == "legacy"
    assert payload["phase4_pnl_slack"] is None
    assert payload["phase4_lucky_penalty"] is None

    # legacy_pnl_smoke mode
    cfg_smoke = StageGateConfig(phase4_fitness_mode="legacy_pnl_smoke")
    res = evaluate_stage_a(..., stage_config=cfg_smoke)
    payload = res.metrics["payload"]
    assert payload["phase4_fitness_mode"] == "legacy_pnl_smoke"
    assert isinstance(payload["phase4_pnl_slack"], float)
    assert isinstance(payload["phase4_lucky_penalty"], float)


def test_pr4_legacy_pnl_smoke_no_exposure_path_unchanged() -> None:
    """PR4: trade_count < min (= no_exposure 経路) は legacy mode と同じく
    fitness_pen=NO_EXPOSURE_FITNESS、 PnL 探索圧と lucky penalty は適用しない."""
    cfg = StageGateConfig(phase4_fitness_mode="legacy_pnl_smoke")
    # trade_count=0 個体 → no_exposure
    res = evaluate_stage_a(no_trade_genome, ..., cfg)
    assert "no_exposure" in res.reason_codes
    assert res.metrics["payload"]["fitness_pen"] == NO_EXPOSURE_FITNESS
    # PR4: sentinel 経路では observe-only field も None (= 計算 skip された証跡)
    assert res.metrics["payload"]["phase4_pnl_slack"] is None
    assert res.metrics["payload"]["phase4_lucky_penalty"] is None


def test_pr4_legacy_pnl_smoke_system_failure_path_unchanged() -> None:
    """PR4: system_failure 経路 (= exception_caught) で legacy_pnl_smoke でも
    fitness_pen=SYSTEM_FAILURE_FITNESS のまま (= sentinel 経路の不変契約、
    Codex 設計レビュー Round 1 [Critical] 反映)."""
    cfg = StageGateConfig(phase4_fitness_mode="legacy_pnl_smoke")
    # backtest 例外を発生させる fixture を使用
    res = evaluate_stage_a(broken_genome, ..., cfg)
    assert "system_failure" in res.reason_codes
    assert res.metrics["payload"]["fitness_pen"] == SYSTEM_FAILURE_FITNESS
    assert res.metrics["payload"]["phase4_pnl_slack"] is None
    assert res.metrics["payload"]["phase4_lucky_penalty"] is None


def test_pr4_legacy_pnl_smoke_metric_unavailable_path_unchanged() -> None:
    """PR4: metric_unavailable 経路 (= sharpe_raw=None) で legacy_pnl_smoke でも
    fitness_pen=METRIC_UNAVAILABLE_FITNESS のまま (= sentinel 経路の不変契約、
    Codex 設計レビュー Round 1 [Critical] 反映)."""
    cfg = StageGateConfig(phase4_fitness_mode="legacy_pnl_smoke")
    # trade_count >= min かつ sharpe_raw が None になる fixture (= trade_count_min_for_sharpe
    # を上回らない trade_count、 または zero variance return)
    res = evaluate_stage_a(metric_unavailable_genome, ..., cfg)
    assert "metric_unavailable" in res.reason_codes
    assert res.metrics["payload"]["fitness_pen"] == METRIC_UNAVAILABLE_FITNESS
    assert res.metrics["payload"]["phase4_pnl_slack"] is None
    assert res.metrics["payload"]["phase4_lucky_penalty"] is None


def test_pr4_sentinel_paths_equivalence_legacy_vs_smoke_mode() -> None:
    """PR4: sentinel 3 経路 (system_failure / no_exposure / metric_unavailable) は
    legacy mode と legacy_pnl_smoke mode で fitness_pen が完全一致
    (= 二重保証契約、 Codex 設計レビュー Round 1 [Critical] 反映)."""
    for fixture, sentinel, expected_reason in [
        (broken_genome, SYSTEM_FAILURE_FITNESS, "system_failure"),
        (no_trade_genome, NO_EXPOSURE_FITNESS, "no_exposure"),
        (metric_unavailable_genome, METRIC_UNAVAILABLE_FITNESS, "metric_unavailable"),
    ]:
        cfg_legacy = StageGateConfig(phase4_fitness_mode="legacy")
        cfg_smoke = StageGateConfig(phase4_fitness_mode="legacy_pnl_smoke")
        res_legacy = evaluate_stage_a(fixture, ..., cfg_legacy)
        res_smoke = evaluate_stage_a(fixture, ..., cfg_smoke)
        assert res_legacy.metrics["payload"]["fitness_pen"] == sentinel
        assert res_smoke.metrics["payload"]["fitness_pen"] == sentinel
        assert (
            res_legacy.metrics["payload"]["fitness_pen"]
            == res_smoke.metrics["payload"]["fitness_pen"]
        ), f"{expected_reason}: legacy と smoke で fitness_pen 不一致"
```

#### 4.3 config tests

```python
def test_pr4_phase4_config_defaults_to_legacy_mode() -> None:
    """PR4: Phase4Config default は legacy mode (= 行動完全不変)."""
    from src.alpha_factory.config import Phase4Config
    cfg = Phase4Config()
    assert cfg.fitness_mode == "legacy"
    assert cfg.beta == 0.05
    assert cfg.persistence_weight == 0.5
    assert cfg.lucky_hard_penalty == 1.0
    assert cfg.lucky_soft_penalty == 0.3


def test_pr4_phase4_config_rejects_invalid_mode() -> None:
    """PR4: 未定義 mode は ValueError."""
    from src.alpha_factory.config import Phase4Config
    with pytest.raises(ValueError, match="fitness_mode must be"):
        Phase4Config(fitness_mode="unknown_mode")


def test_pr4_phase4_config_rejects_beta_out_of_range() -> None:
    """PR4: beta が [0, 1] 外なら ValueError."""
    from src.alpha_factory.config import Phase4Config
    with pytest.raises(ValueError, match="beta must be in"):
        Phase4Config(beta=2.0)
    with pytest.raises(ValueError, match="beta must be in"):
        Phase4Config(beta=-0.1)


def test_pr4_phase4_config_rejects_hard_lt_soft() -> None:
    """PR4: lucky_hard < lucky_soft は順序整合性違反で ValueError."""
    from src.alpha_factory.config import Phase4Config
    with pytest.raises(ValueError, match="lucky_hard_penalty.*lucky_soft_penalty"):
        Phase4Config(lucky_hard_penalty=0.1, lucky_soft_penalty=0.5)


def test_pr4_loader_builds_phase4_from_yaml(tmp_path: Path) -> None:
    """PR4: yaml の phase4 section が Phase4Config に反映され、 StageGateConfig に伝搬."""
    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text("""
phase4:
  fitness_mode: legacy_pnl_smoke
  beta: 0.10
  persistence_weight: 0.7
""")
    cfg = load_config(yaml_path)
    assert cfg.phase4.fitness_mode == "legacy_pnl_smoke"
    assert cfg.phase4.beta == 0.10
    assert cfg.stage_gate.phase4_fitness_mode == "legacy_pnl_smoke"
    assert cfg.stage_gate.phase4_beta == 0.10
```

## 受入基準

- [ ] `Phase4Config` 追加 (5 field、 __post_init__ で範囲検証 + HARD>=SOFT 契約)
- [ ] `AlphaFactoryConfig.phase4` field 追加
- [ ] config loader で yaml → Phase4Config → StageGateConfig 伝搬
- [ ] `StageGateConfig` に 5 fields 追加 (`phase4_fitness_mode` / `phase4_beta` / `phase4_persistence_weight` / `phase4_lucky_hard_penalty` / `phase4_lucky_soft_penalty`)
- [ ] `_compute_clipped_pnl_slack` / `_compute_lucky_run_penalty` helper 実装
- [ ] `evaluate_stage_a` の fitness 計算分岐 (= legacy / legacy_pnl_smoke 2 mode、 `below_threshold` 経路のみ発火、 sentinel 3 経路は不変)
- [ ] **sentinel 3 経路の不変性契約** (= Codex 設計レビュー Round 1 [Critical] 反映): `system_failure` / `no_exposure` / `metric_unavailable` の `fitness_pen` が legacy / legacy_pnl_smoke の両 mode で完全一致、 sentinel 経路では `phase4_pnl_slack` / `phase4_lucky_penalty` が **None** で記録される
- [ ] payload に `phase4_fitness_mode` / `phase4_pnl_slack` / `phase4_lucky_penalty` / **`phase4_persistence_weight`** / **`phase4_beta`** / **`phase4_lucky_hard_penalty`** / **`phase4_lucky_soft_penalty`** 追加 (= observe-only、 future migration 監査の再現性確保、 Codex 設計レビュー Round 1 [Warning] 反映)
- [ ] `config/alpha_factory/default.yaml` に phase4 section 追加 (= legacy default)
- [ ] PR4 helper unit tests **15 件** (= pnl_slack 4 件 + lucky_penalty 5 件 + **境界等号テスト 6 件**、 Codex 設計レビュー Round 1 [Critical] 反映: `total_pnl==12000` / `max_dd_pct==1e-9` / `max_dd_pct==0.5` / `trade_count==80` / short_clip upper bound / short_target exact)
- [ ] PR4 integration tests **8 件** (= legacy regression / smoke mode / payload / sentinel 3 経路不変 × 2 mode 比較 + 単独 3 経路)
- [ ] PR4 config tests 4 件以上 (= default / invalid / loader)
- [ ] **CLI `--fitness-mode` 引数追加** (= smoke 実行容易化、 Codex 設計レビュー Round 2 非 blocking note 2 反映)
- [ ] CLI test 1 件以上 (= `--fitness-mode legacy_pnl_smoke` で yaml override される)
- [ ] 既存 `test_stage_gate*.py` 全 pass (= 既存 fitness_pen 検証テストが legacy default で通る)
- [ ] alpha_factory 全 pass
- [ ] ruff / mypy clean

## ロールバック条件 (= 実装時)

- 既存 stage_gate 動作変更検出 (= legacy default で既存テスト fail)
- yaml loader 互換性破壊 (= phase4 section 無い既存 yaml が読めない)
- StageGateConfig __post_init__ で false-positive ValueError
- helper 関数の境界誤算 (= clip / threshold 境界)
- fitness_pen が `NaN` / `+inf` / `-inf` を取り得る経路

## smoke 条件 (= ユーザー実行待ち、 PR4 merge 後)

詳細は概念設計 § 検証戦略 § smoke 時 を参照。

### Baseline 定義 (= Codex 設計レビュー Round 1 [Warning] 反映、 恣意性排除)

「baseline」 = **直近 5 RUN の archive 累積値の median (= 観測単位は run-level 集計)**。 単一 RUN 比較ではなく、 直近 5 RUN の分布から下記指標を計算:

- Stage B pass 数: 各 RUN の Stage B pass 個体数の median
- Stage C pips/day p99: 各 RUN の Stage C 評価集団の pips/day p99 の median
- lucky high-PnL 比率: 各 RUN の Stage C 評価集団中で `max_dd<0.3% && total_pnl>=12000` の比率 の median
- trade_count top decile: 各 RUN の Stage B pass 個体の trade_count top decile の median

PR4 smoke は **1 RUN smoke**。 上記 baseline (= 5 RUN median) と比較。

### 主要合格条件 (= Codex Y Round 3-5 確定)

- Stage B pass 数 ≥ baseline × 80%
- Stage C pips/day p99 ≥ 5.0 (= absolute 閾値、 baseline 比較なし)
- Stage C total_pnl p95/p99 ≥ baseline
- trade_count median が 50-70 に潰れず、 p75/p90 が維持または上昇
- max_dd=0.0% 比率 ≤ baseline、 または `max_dd<0.3% && high_pnl` 比率 ≤ baseline

### PR3 shadow 列を活用した追加判定 (= 新規)

- `canonical_gate_pass_b_shadow=True` 比率が legacy mode (= baseline 5 RUN) より低下しないこと (= canonical 評価で過剰選別になっていない)
- `mission_inf_gap_b_shadow` の中央値が baseline より低下 (= mission に近づいた個体が増えている)、 ただし n<10 の場合は INCONCLUSIVE 扱い (= C7 Sample size 遵守)

### rollback 条件 (= flag off)

- Stage B pass 数 < baseline × 50%
- lucky 比率 (= `max_dd<0.3% && total_pnl>=12000`) baseline 1.5 倍超
- top decile trade_count=50 張り付き (= trade_count_max < 60 の比率が baseline×2 超)
- pips/day 上昇が trades/day 増加だけで説明される (= pips/trade 不変 + trades/day 上昇)

### Conditioning set / INCONCLUSIVE 許容 (= Codex 設計レビュー Round 1 [Warning] 反映)

- pair 固定: smoke RUN は baseline と **同 instrument** で実行 (= EUR_JPY 等、 cross-pair 混合不可)
- seed 固定: baseline 5 RUN と同 seed 系列か、 同等 seed range で再現性確保
- 1 RUN smoke で差が `Δ Stage B pass 数 < 5%` 等の **noise floor 内** なら `INCONCLUSIVE`、 追加 RUN 必要 (= C3 collider bias 回避、 C8 INCONCLUSIVE 第一級 verdict)

## コミット計画

- 1 コミット: `feat(stage_gate): legacy_pnl_smoke fitness opt-in + anti-luck guard (PR4 = 初の行動変更、 default OFF)`
- 影響範囲:
  - `src/alpha_factory/config.py` (Phase4Config + loader 拡張、 ~50 行)
  - `src/alpha_factory/stage_gate.py` (StageGateConfig 5 fields + 2 helper + fitness 分岐、 ~80 行)
  - `config/alpha_factory/default.yaml` (phase4 section、 ~10 行)
  - `tests/alpha_factory/test_stage_gate.py` or 新規 `test_stage_gate_phase4.py` (= helper + integration、 ~150 行)
  - `tests/alpha_factory/test_config.py` (Phase4Config + loader、 ~40 行)
  - `devnotes/20260513-1715-todo-pr4-legacy-pnl-smoke/` (= conceptual + detailed + impl-review)

## 関連 / 参考

- 概念設計: `devnotes/20260513-1715-todo-pr4-legacy-pnl-smoke/conceptual-design.md`
- Codex 議論: `tmp/codex-debate-round2/.codex-output-debate-Y-round-{3,4,5}.md`
- 既存 Phase2Config パターン: `src/alpha_factory/config.py:271-298` (Phase2Config)、 `src/alpha_factory/stage_gate.py:546` (phase2_canonical_metrics_mode)
- 現 Stage A fitness 計算: `src/alpha_factory/stage_gate.py:920-938` (`evaluate_stage_a` 内)
- PR3 で追加した archive shadow 列: `src/alpha_factory/archive.py:143-160` (smoke 検証で使う)
