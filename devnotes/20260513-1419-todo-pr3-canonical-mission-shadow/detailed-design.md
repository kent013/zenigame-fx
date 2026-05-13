# PR3 詳細設計: canonical_metrics / mission_inf_gap shadow 配線

## 実装差分

### 1. `src/alpha_factory/stage_gate.py`

#### 1.1 import 追加

```python
from src.alpha_factory.mission_inf_gap import (
    MissionGapResult,
    evaluate_mission_inf_gap,
)
from src.alpha_factory.canonical_metrics import CanonicalFiveResult
```

`CanonicalFiveResult` は既に import 済 (= `_try_evaluate_canonical_five_safe` の return 型)、 改めて公開 alias として明示 import するのは可読性のためのみ (= 既存 import 行を維持で OK)。

#### 1.2 helper 関数 `_canonical_shadow_summary` を追加

`_log_canonical_dual_path` の直後 (= line 305 付近) に追加:

```python
def _canonical_shadow_summary(
    canonical: CanonicalFiveResult | None,
) -> dict[str, object] | None:
    """canonical_sidecar から archive shadow 列用の summary dict を抽出.

    PR3: stage_gate → archive payload 経路の SSOT helper。 archive 側の
    ``collect_stage_b`` / ``collect_stage_c`` が `.get("gate_pass")` 等で
    安全参照することを前提に、 ±inf は本関数で **正規化しない** (= archive
    側 `_finite_or_none` helper が一括処理する責務分離)。

    Args:
        canonical: ``_try_evaluate_canonical_five_safe`` の return。 ``None``
            なら ``None`` を返す (= adapter / thresholds 例外 fallback、 archive
            列も None で初期化される).

    Returns:
        ``{"gate_pass": bool, "mission_inf_gap": float, "mission_signed_margin": float}``
        の dict (= keys は archive 側と SSOT 一致)、 ``canonical`` が ``None``
        なら ``None``.

        ``mission_inf_gap`` / ``mission_signed_margin`` は ``evaluate_mission_inf_gap``
        の戻り値そのまま (= ±inf を含み得る、 archive 側で正規化).
    """
    if canonical is None:
        return None
    try:
        mission = evaluate_mission_inf_gap(canonical)
    except ValueError:
        # canonical_metrics の slack が NaN 等の異常時 (= upstream T061 engine bug
        # indicator)、 PR3 shadow としては「計算不能」 とみなして gate_pass のみ返す
        # (mission 系は None)。 caller の log は既に T061 / T062 で出ているはず。
        return {
            "gate_pass": bool(canonical.gate_pass),
            "mission_inf_gap": None,
            "mission_signed_margin": None,
        }
    return {
        "gate_pass": bool(canonical.gate_pass),
        "mission_inf_gap": float(mission.mission_inf_gap),
        "mission_signed_margin": float(mission.mission_signed_margin),
    }
```

#### 1.3 `evaluate_stage_b` の payload 拡張

`evaluate_stage_b` 内、 `canonical_sidecar_b_is = _try_evaluate_canonical_five_safe(...)` 呼出後 (= line 1024-1033) と同じ try-block 内で payload 用 summary を計算し、 既存 payload `is_full_*` 群と同列で書込む。

`metrics_envelope` (= line 1262-1287) の `"payload"` dict に 1 key 追加:

```python
metrics_envelope: dict[str, object] = {
    "stage": "B",
    "genome_name": genome.name,
    "n_bars": len(bars_stage_b),
    "wall_time_seconds": elapsed,
    "payload": {
        "n_fold": n_fold,
        "n_fold_unavailable": n_fold_unavailable,
        "n_fold_effective": n_fold_effective,
        "oos_sharpes": tuple(oos_sharpes_imputed),
        "median_oos_sharpe": median_oos,
        "positive_fold_ratio": positive_ratio,
        "positive_fold_ratio_effective": positive_ratio_effective,
        "dsr": None,
        "is_full_sharpe": is_full_sharpe,
        "is_full_total_pnl": is_full_total_pnl,
        "is_full_trade_count": is_full_trade_count,
        "unavailable_reason_counts": {
            r.value: c for r, c in reason_counts.items()
        },
        "fold_trade_counts": tuple(fold_trade_counts),
        # PR3: canonical 5 / mission_inf_gap shadow summary (archive 用、
        # in-memory only)。 canonical_sidecar_b_is が None / 例外 fallback の
        # 場合は本 key も None。 詳細:
        # devnotes/20260513-1419-todo-pr3-canonical-mission-shadow/
        "canonical_shadow_b_is": _canonical_shadow_summary(canonical_sidecar_b_is),
    },
}
```

`canonical_sidecar_b_is` 変数は try-block 内で定義されているが、 IS monitor の `try-except` (= line 1005-1057) の except 経路では未定義のままになるため、 except 前に `canonical_sidecar_b_is: CanonicalFiveResult | None = None` で初期化を行う:

```python
# 既存 line 1002 前後
is_full_sharpe: float | None = None
is_full_total_pnl: float = 0.0
is_full_trade_count = 0
# PR3: canonical_sidecar_b_is を except 経路でも安全に参照できるように初期化
canonical_sidecar_b_is: CanonicalFiveResult | None = None
try:
    ...
    canonical_sidecar_b_is = _try_evaluate_canonical_five_safe(...)
    ...
```

#### 1.4 `evaluate_stage_c` の payload 拡張

`evaluate_stage_c` も対称構造。 `canonical_sidecar_c_base` を except 前に `None` で初期化し、 `stress_payload` 確定後の最終 `metrics_envelope` (= 詳細は line 1700+ 周辺、 grep `"payload":` で確認) の `"payload"` dict に追加:

```python
metrics_envelope["payload"]["canonical_shadow_c_base"] = _canonical_shadow_summary(
    canonical_sidecar_c_base
)
```

実装位置は **`mission_score` 計算より後 / `metrics_envelope` 構築時** とする (= mission_score と並んで shadow 系の集約位置)。

### 2. `src/alpha_factory/archive.py`

#### 2.1 GENOMES_SCHEMA に 6 列追加

`persistence_score_shadow` 直後 (= PR2 で追加した位置の隣) に追加:

```python
# PR3: canonical_metrics / mission_inf_gap shadow 列 (selection 影響なし、 audit only)。
# Stage B IS monitor (18 ヶ月) と Stage C base 評価 (60 日 holdout) で算出した
# CanonicalFiveResult + MissionGapResult の summary。 ±inf / NaN は None に正規化。
# canonical_sidecar が skip (= adapter 例外 / mode=disabled) の場合は全 None。
# 詳細: devnotes/20260513-1419-todo-pr3-canonical-mission-shadow/
pa.field("canonical_gate_pass_b_shadow", pa.bool_(), nullable=True),
pa.field("mission_inf_gap_b_shadow", pa.float64(), nullable=True),
pa.field("mission_signed_margin_b_shadow", pa.float64(), nullable=True),
pa.field("canonical_gate_pass_c_shadow", pa.bool_(), nullable=True),
pa.field("mission_inf_gap_c_shadow", pa.float64(), nullable=True),
pa.field("mission_signed_margin_c_shadow", pa.float64(), nullable=True),
```

#### 2.2 `_create_row_template` に default 追加

PR2 `"persistence_score_shadow": None,` の直後に追加:

```python
# PR3: canonical_metrics / mission_inf_gap shadow 列 (collect_stage_b/c で書込)
"canonical_gate_pass_b_shadow": None,
"mission_inf_gap_b_shadow": None,
"mission_signed_margin_b_shadow": None,
"canonical_gate_pass_c_shadow": None,
"mission_inf_gap_c_shadow": None,
"mission_signed_margin_c_shadow": None,
```

`_TEMPLATE_KEYS == _SCHEMA_NAMES` の import-time assert で schema/template の整合性が検証される。

#### 2.3 helper `_finite_or_none` を追加

`_compute_persistence_score_shadow` の直後に追加:

```python
def _finite_or_none(value: object) -> float | None:
    """PR3: Parquet float64 互換のため ±inf / NaN / None を None に正規化.

    archive 列が ``pa.float64()`` nullable で、 ``±inf`` は技術的には書き込めるが
    downstream 解析の単純化のため有限値 / None のみに統一する。 boolean は受け付け
    ない (= caller の型保証責務、 archive 側でも明示的に弾く).

    Args:
        value: 数値 / None / NaN / ±inf 想定。 boolean / 文字列等は ``None`` 扱い.

    Returns:
        有限 float なら ``float(value)``、 None / NaN / ±inf / 非数値型 なら ``None``.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        # bool は ``isinstance(True, int) == True`` だが、 PR3 shadow 列は float
        # 専用のため弾く (= caller が gate_pass を誤って渡した時の defensive)
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return f
```

`import math` は archive.py 先頭で既に取得されている (= grep で確認推奨)。 されていなければ追加。

#### 2.4 helper `_extract_canonical_shadow` を追加

`_finite_or_none` の直後に追加:

```python
def _extract_canonical_shadow(
    payload: Mapping[str, object],
    key: str,
) -> tuple[bool | None, float | None, float | None]:
    """PR3: stage_gate payload から canonical_shadow summary を抽出.

    Args:
        payload: ``stage_result.metrics["payload"]``.
        key: ``"canonical_shadow_b_is"`` (Stage B) / ``"canonical_shadow_c_base"``
            (Stage C).

    Returns:
        ``(gate_pass, mission_inf_gap, mission_signed_margin)`` tuple。
        payload に key が無い / 値が None / 非 Mapping / field 欠損 のとき、
        該当値は ``None`` で返す (= defensive、 stage_gate が PR3 未対応バージョン
        の場合でも archive 側で安全に fall through する).
    """
    shadow = payload.get(key)
    if not isinstance(shadow, Mapping):
        return (None, None, None)
    gate_pass_raw = shadow.get("gate_pass")
    gate_pass: bool | None
    if isinstance(gate_pass_raw, bool):
        gate_pass = gate_pass_raw
    else:
        gate_pass = None
    return (
        gate_pass,
        _finite_or_none(shadow.get("mission_inf_gap")),
        _finite_or_none(shadow.get("mission_signed_margin")),
    )
```

#### 2.5 `collect_stage_b` に書き込みロジック追加

既存 `row["persistence_score_shadow"] = _compute_persistence_score_shadow(...)` の直後に追加:

```python
# PR3: canonical_metrics / mission_inf_gap shadow を archive に記録
# (Stage B IS monitor 由来、 selection 影響なし、 audit only).
gate_pass_b, gap_b, margin_b = _extract_canonical_shadow(
    payload, "canonical_shadow_b_is"
)
row["canonical_gate_pass_b_shadow"] = gate_pass_b
row["mission_inf_gap_b_shadow"] = gap_b
row["mission_signed_margin_b_shadow"] = margin_b
```

#### 2.6 `collect_stage_c` に書き込みロジック追加

既存 `row["mission_score"] = _opt_float(payload, "mission_score")` の直後に追加:

```python
# PR3: canonical_metrics / mission_inf_gap shadow を archive に記録
# (Stage C base 由来、 selection 影響なし、 audit only).
gate_pass_c, gap_c, margin_c = _extract_canonical_shadow(
    payload, "canonical_shadow_c_base"
)
row["canonical_gate_pass_c_shadow"] = gate_pass_c
row["mission_inf_gap_c_shadow"] = gap_c
row["mission_signed_margin_c_shadow"] = margin_c
```

### 3. `tests/alpha_factory/test_archive.py`

#### 3.1 既存テストの列数更新

PR2 で `test_schema_has_52_columns` に更新済。 PR3 で `test_schema_has_58_columns` に更新:

```python
def test_schema_has_58_columns() -> None:
    """PR3: schema 列数は 58 (= 52 + canonical/mission shadow 6 列)."""
    assert len(GENOMES_SCHEMA.names) == 58
```

`_create_row_template` の key 数を assert する既存テストがあれば同様に更新。

#### 3.2 新規テスト

```python
def test_pr3_schema_has_canonical_shadow_columns() -> None:
    """PR3: GENOMES_SCHEMA に canonical/mission shadow 6 列が存在."""
    names = GENOMES_SCHEMA.names
    for col in (
        "canonical_gate_pass_b_shadow",
        "mission_inf_gap_b_shadow",
        "mission_signed_margin_b_shadow",
        "canonical_gate_pass_c_shadow",
        "mission_inf_gap_c_shadow",
        "mission_signed_margin_c_shadow",
    ):
        assert col in names, f"missing column: {col}"
    # 型 / nullable 検証
    assert GENOMES_SCHEMA.field("canonical_gate_pass_b_shadow").type == pa.bool_()
    assert GENOMES_SCHEMA.field("canonical_gate_pass_b_shadow").nullable
    assert GENOMES_SCHEMA.field("mission_inf_gap_b_shadow").type == pa.float64()
    assert GENOMES_SCHEMA.field("mission_inf_gap_b_shadow").nullable
    assert GENOMES_SCHEMA.field("mission_signed_margin_b_shadow").type == pa.float64()
    assert GENOMES_SCHEMA.field("canonical_gate_pass_c_shadow").type == pa.bool_()
    assert GENOMES_SCHEMA.field("mission_inf_gap_c_shadow").type == pa.float64()
    assert GENOMES_SCHEMA.field("mission_signed_margin_c_shadow").type == pa.float64()


def test_pr3_template_canonical_shadow_defaults_none() -> None:
    """PR3: row template default は全 6 列 None (Stage B/C 評価前)."""
    template = _create_row_template()
    for col in (
        "canonical_gate_pass_b_shadow",
        "mission_inf_gap_b_shadow",
        "mission_signed_margin_b_shadow",
        "canonical_gate_pass_c_shadow",
        "mission_inf_gap_c_shadow",
        "mission_signed_margin_c_shadow",
    ):
        assert template[col] is None, f"expected None for {col}"


def test_pr3_finite_or_none_normalizes_non_finite() -> None:
    """PR3: _finite_or_none で ±inf / NaN / None / 非数値 が None に正規化される."""
    from src.alpha_factory.archive import _finite_or_none
    import math
    assert _finite_or_none(None) is None
    assert _finite_or_none(math.inf) is None
    assert _finite_or_none(-math.inf) is None
    assert _finite_or_none(math.nan) is None
    assert _finite_or_none("hoge") is None
    assert _finite_or_none(True) is None  # bool は弾く (gate_pass 誤渡し対策)
    assert _finite_or_none(0.0) == 0.0
    assert _finite_or_none(-3.5) == -3.5
    assert _finite_or_none(1e10) == 1e10


def test_pr3_extract_canonical_shadow_missing_key() -> None:
    """PR3: payload に canonical_shadow key が無い (= stage_gate PR3 未対応) なら全 None."""
    from src.alpha_factory.archive import _extract_canonical_shadow
    assert _extract_canonical_shadow({}, "canonical_shadow_b_is") == (None, None, None)
    assert _extract_canonical_shadow(
        {"canonical_shadow_b_is": None}, "canonical_shadow_b_is"
    ) == (None, None, None)
    assert _extract_canonical_shadow(
        {"canonical_shadow_b_is": "not_a_mapping"}, "canonical_shadow_b_is"
    ) == (None, None, None)


def test_pr3_extract_canonical_shadow_valid_payload() -> None:
    """PR3: payload に valid shadow dict があれば 3-tuple で抽出."""
    from src.alpha_factory.archive import _extract_canonical_shadow
    payload = {
        "canonical_shadow_b_is": {
            "gate_pass": True,
            "mission_inf_gap": 0.0,
            "mission_signed_margin": 0.5,
        }
    }
    assert _extract_canonical_shadow(payload, "canonical_shadow_b_is") == (
        True, 0.0, 0.5
    )


def test_pr3_extract_canonical_shadow_infeasible_payload() -> None:
    """PR3: ±inf / NaN は None に正規化されて返る."""
    from src.alpha_factory.archive import _extract_canonical_shadow
    import math
    payload = {
        "canonical_shadow_c_base": {
            "gate_pass": False,
            "mission_inf_gap": math.inf,
            "mission_signed_margin": -math.inf,
        }
    }
    assert _extract_canonical_shadow(payload, "canonical_shadow_c_base") == (
        False, None, None
    )


def test_pr3_collect_stage_b_writes_canonical_shadow_when_payload_has_it() -> None:
    """PR3: collect_stage_b で canonical_shadow_b_is が archive に書き込まれる."""
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(), instrument="USD_JPY")
    # _stage_b_result の payload に canonical_shadow_b_is を注入したテスト helper
    stage_b = _stage_b_result_with_canonical_shadow(
        gate_pass=True,
        mission_inf_gap=0.0,
        mission_signed_margin=0.42,
    )
    arc.collect_stage_b(g, "lane", 0, stage_b)
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["canonical_gate_pass_b_shadow"] is True
    assert row["mission_inf_gap_b_shadow"] == pytest.approx(0.0)
    assert row["mission_signed_margin_b_shadow"] == pytest.approx(0.42)


def test_pr3_collect_stage_b_without_canonical_shadow_keeps_none() -> None:
    """PR3: payload に canonical_shadow_b_is が無ければ shadow 列は None のまま."""
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(), instrument="USD_JPY")
    arc.collect_stage_b(g, "lane", 0, _stage_b_result())  # PR3 未対応 payload
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["canonical_gate_pass_b_shadow"] is None
    assert row["mission_inf_gap_b_shadow"] is None
    assert row["mission_signed_margin_b_shadow"] is None


def test_pr3_collect_stage_c_writes_canonical_shadow_when_payload_has_it() -> None:
    """PR3: collect_stage_c で canonical_shadow_c_base が archive に書き込まれる."""
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(), instrument="USD_JPY")
    arc.collect_stage_b(g, "lane", 0, _stage_b_result())
    stage_c = _stage_c_result_with_canonical_shadow(
        gate_pass=False,
        mission_inf_gap=0.18,
        mission_signed_margin=-0.18,
    )
    arc.collect_stage_c(g, "lane", 0, stage_c)
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["canonical_gate_pass_c_shadow"] is False
    assert row["mission_inf_gap_c_shadow"] == pytest.approx(0.18)
    assert row["mission_signed_margin_c_shadow"] == pytest.approx(-0.18)


def test_pr3_canonical_shadow_persisted_in_parquet(tmp_path: Path) -> None:
    """PR3: flush 後の Parquet で canonical_shadow 6 列が読み出せる."""
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(), instrument="USD_JPY")
    arc.collect_stage_b(g, "lane", 0, _stage_b_result_with_canonical_shadow(
        gate_pass=True, mission_inf_gap=0.0, mission_signed_margin=0.5,
    ))
    arc.collect_stage_c(g, "lane", 0, _stage_c_result_with_canonical_shadow(
        gate_pass=False, mission_inf_gap=0.1, mission_signed_margin=-0.05,
    ))
    out = arc.flush(output_dir=tmp_path)
    import pyarrow.parquet as pq
    table = pq.read_table(out)
    df = table.to_pandas()
    for col in (
        "canonical_gate_pass_b_shadow",
        "mission_inf_gap_b_shadow",
        "mission_signed_margin_b_shadow",
        "canonical_gate_pass_c_shadow",
        "mission_inf_gap_c_shadow",
        "mission_signed_margin_c_shadow",
    ):
        assert col in df.columns, f"missing in Parquet: {col}"
    assert df.iloc[0]["canonical_gate_pass_b_shadow"]
    assert df.iloc[0]["mission_inf_gap_b_shadow"] == pytest.approx(0.0)
    assert df.iloc[0]["mission_signed_margin_b_shadow"] == pytest.approx(0.5)
    # Stage C は gate_pass=False / 有限値
    assert not df.iloc[0]["canonical_gate_pass_c_shadow"]
    assert df.iloc[0]["mission_inf_gap_c_shadow"] == pytest.approx(0.1)
    assert df.iloc[0]["mission_signed_margin_c_shadow"] == pytest.approx(-0.05)
```

#### 3.3 テスト helper の追加

`tests/alpha_factory/test_archive.py` の既存 `_stage_b_result` / `_stage_c_result` の隣に `*_with_canonical_shadow` 拡張版を追加:

```python
def _stage_b_result_with_canonical_shadow(
    *,
    gate_pass: bool | None,
    mission_inf_gap: float | None,
    mission_signed_margin: float | None,
    passed: bool = True,
) -> StageResult:
    """PR3 test helper: 既存 _stage_b_result に canonical_shadow_b_is を追加."""
    base = _stage_b_result(passed=passed)
    payload = dict(base.metrics["payload"])  # shallow copy
    payload["canonical_shadow_b_is"] = {
        "gate_pass": gate_pass,
        "mission_inf_gap": mission_inf_gap,
        "mission_signed_margin": mission_signed_margin,
    }
    return StageResult(
        stage=base.stage,
        passed=base.passed,
        metrics={**base.metrics, "payload": payload},
        reason_codes=base.reason_codes,
    )


def _stage_c_result_with_canonical_shadow(
    *,
    gate_pass: bool | None,
    mission_inf_gap: float | None,
    mission_signed_margin: float | None,
    passed: bool = True,
) -> StageResult:
    """PR3 test helper: 既存 _stage_c_result に canonical_shadow_c_base を追加."""
    base = _stage_c_result(passed=passed)
    payload = dict(base.metrics["payload"])
    payload["canonical_shadow_c_base"] = {
        "gate_pass": gate_pass,
        "mission_inf_gap": mission_inf_gap,
        "mission_signed_margin": mission_signed_margin,
    }
    return StageResult(
        stage=base.stage,
        passed=base.passed,
        metrics={**base.metrics, "payload": payload},
        reason_codes=base.reason_codes,
    )
```

`_stage_b_result` / `_stage_c_result` の signature によっては fixture を直接拡張する方が簡潔。 既存実装を確認して最適な形に。

### 4. `tests/alpha_factory/test_stage_gate.py` (Optional、 影響あれば追加)

`_canonical_shadow_summary` の単体テストを追加:

```python
def test_pr3_canonical_shadow_summary_none_input() -> None:
    """PR3: canonical_sidecar=None → summary=None."""
    from src.alpha_factory.stage_gate import _canonical_shadow_summary
    assert _canonical_shadow_summary(None) is None


def test_pr3_canonical_shadow_summary_valid_canonical() -> None:
    """PR3: valid canonical → summary に gate_pass + mission 3 field が入る."""
    from src.alpha_factory.stage_gate import _canonical_shadow_summary
    canonical = _stub_canonical_five_result(
        gate_pass=True,
        slack_sharpe=0.1, slack_pnl=0.2, slack_dd=0.3, slack_tc=0.4, slack_wr=0.0,
        is_feasible=True,
    )
    summary = _canonical_shadow_summary(canonical)
    assert summary == {
        "gate_pass": True,
        "mission_inf_gap": 0.0,  # all slacks positive → no gap
        "mission_signed_margin": 0.1,  # min slack
    }


def test_pr3_canonical_shadow_summary_infeasible_canonical() -> None:
    """PR3: invariants infeasible → mission_signed_margin=-inf を float そのまま返す
    (archive 側で None 正規化される責務分離)."""
    from src.alpha_factory.stage_gate import _canonical_shadow_summary
    canonical = _stub_canonical_five_result(
        gate_pass=False,
        slack_sharpe=-0.5, slack_pnl=0.0, slack_dd=0.0, slack_tc=0.0, slack_wr=0.0,
        is_feasible=False,
    )
    summary = _canonical_shadow_summary(canonical)
    assert summary["gate_pass"] is False
    # invariants=False → mission_signed_margin sentinel = -inf
    assert math.isinf(summary["mission_signed_margin"])
    # mission_inf_gap = max(0, 0.5) = 0.5 (slack_sharpe=-0.5 由来)
    assert summary["mission_inf_gap"] == pytest.approx(0.5)
```

`_stub_canonical_five_result` は test 用 helper で、 既存 stage_gate test fixture に合わせて構築。 既存テスト群を参考に最低 1 個 happy-path + 1 個 infeasible で OK。

## 受入基準

- [ ] GENOMES_SCHEMA に canonical/mission shadow 6 列追加 (= 52 → 58 列)
- [ ] `_create_row_template` に default None 追加 (全 6 列)
- [ ] `_finite_or_none` helper 実装 (= ±inf / NaN / bool / 非数値 → None)
- [ ] `_extract_canonical_shadow` helper 実装 (= payload defensive 抽出)
- [ ] stage_gate.py `_canonical_shadow_summary` helper 実装
- [ ] `evaluate_stage_b` / `evaluate_stage_c` の payload に `canonical_shadow_b_is` / `canonical_shadow_c_base` key 追加
- [ ] `collect_stage_b` で `canonical_gate_pass_b_shadow` / `mission_inf_gap_b_shadow` / `mission_signed_margin_b_shadow` 書き込み
- [ ] `collect_stage_c` で `canonical_gate_pass_c_shadow` / `mission_inf_gap_c_shadow` / `mission_signed_margin_c_shadow` 書き込み
- [ ] PR3 新規テスト 11 件 (archive 9 + stage_gate 2 以上) 全 pass
- [ ] 既存 `test_archive.py` 全 pass
- [ ] 既存 `test_stage_gate.py` 全 pass
- [ ] `tests/alpha_factory/` 全 pass (= 既存失敗 `test_end_to_end_writes_v2_summary_json` は handoff § 既存問題で別 TODO、 deselect で除外)
- [ ] ruff / mypy clean (= PR3 で touch する 2 file + tests)

## ロールバック条件

- 既存テスト破壊 (= archive / stage_gate)
- Parquet schema migration エラー (= 旧 archive 読み込み失敗)
- collect_stage_b/c の例外
- ±inf 値が Parquet float64 で書き込み失敗
- stage_gate.py の `metrics_envelope` で payload key 衝突
- 既存 dual-path log の format / 内容が変わる (= step 1 LOG_ONLY 経路は不変保持)

## コミット計画

- 1 コミット: `feat(archive): canonical/mission shadow 6 列追加 (PR3 = T061/T062 main flow shadow 配線)`
- 影響範囲:
  - `src/alpha_factory/stage_gate.py` (= helper `_canonical_shadow_summary` 追加、 evaluate_stage_b/c の payload 拡張、 `canonical_sidecar_*` の None 初期化、 ~40-60 行追加)
  - `src/alpha_factory/archive.py` (= schema 6 列追加 + template default + `_finite_or_none` / `_extract_canonical_shadow` helper + collect_stage_b/c 書込、 ~40 行追加)
  - `tests/alpha_factory/test_archive.py` (= 新規テスト 9 件 + test helper 2 件 + 既存 column count assertion 更新、 ~150 行追加)
  - `tests/alpha_factory/test_stage_gate.py` (= 新規テスト 2-3 件、 ~60 行追加)
  - `devnotes/20260513-1419-todo-pr3-canonical-mission-shadow/` (= conceptual + detailed)

## 関連 / 参考

- `devnotes/20260513-1402-handoff-pr1-pr2-postdebate/handoff.md` § 「次のアクション Option A」
- `devnotes/20260513-1223-todo-pr2-persistence-score-shadow/` (= 同型 PR の参考)
- `devnotes/20260503-1024-B-phase2-step1-canonical-metrics/` (= step 1 LOG_ONLY 配線完了の経緯、 step 2 = PR3)
- `src/alpha_factory/canonical_metrics.py` (= T061 CanonicalFiveResult)
- `src/alpha_factory/mission_inf_gap.py` (= T062 MissionGapResult / evaluate_mission_inf_gap)
- `src/alpha_factory/stage_gate.py:112-167` (= `_try_evaluate_canonical_five_safe` 既存)
- `src/alpha_factory/stage_gate.py:175-305` (= `_log_canonical_dual_path` 既存)
- `src/alpha_factory/archive.py:295-318` (= `_compute_persistence_score_shadow` PR2 同型)
