# PR2 詳細設計: persistence_score_shadow 列追加

## 実装差分

### `src/alpha_factory/archive.py`

#### 1. GENOMES_SCHEMA に新規列追加

`source_stage` 直後 (= T058 contract 4 field 群の隣) に追加:

```python
pa.field("persistence_score_shadow", pa.float64(), nullable=True),
```

または既存の Stage B 観察可能性列 (= n_fold_effective / positive_fold_ratio_effective / stage_b_reason_codes 群) の隣に追加するのが論理的。

スキーマコメント:
```
# PR2: Stage B 持続性予測 shadow score (selection 影響なし、 audit only)。
# 計算式: clip(0.7 * positive_fold_ratio_effective + 0.3 * fold_sign_ratio, 0, 1)。
# 詳細: devnotes/20260513-1223-todo-pr2-persistence-score-shadow/
```

#### 2. `_create_row_template()` に default 追加

```python
"persistence_score_shadow": None,
```

`_TEMPLATE_KEYS == _SCHEMA_NAMES` の import-time assert で整合性検証されるため、 schema と template の同時更新が必須。

#### 3. `collect_stage_b()` に書き込みロジック追加

`collect_stage_b` 内、 既存 `row["median_oos_sharpe"] = median_oos` の直後に追加:

```python
# PR2: persistence_score_shadow を archive に記録 (shadow audit、 selection 影響なし)。
pfr = row.get("positive_fold_ratio_effective")
fsr = row.get("fold_sign_ratio")
row["persistence_score_shadow"] = _compute_persistence_score_shadow(pfr, fsr)
```

#### 4. ヘルパー関数 `_compute_persistence_score_shadow()` を追加

```python
def _compute_persistence_score_shadow(
    positive_fold_ratio: float | None,
    fold_sign_ratio: float | None,
) -> float | None:
    """PR2: Stage B 持続性予測 shadow score (audit only).

    archive 実測で Stage C 持続性を正予測する 2 metric の加重合成:
    - positive_fold_ratio_effective (Spearman ρ=+0.345) を 0.7 重み
    - fold_sign_ratio (Spearman ρ=+0.248) を 0.3 重み

    両 None なら None、 片方 None なら他方のみで計算 (= NaN handling).
    結果は [0.0, 1.0] にクリップ.

    詳細: devnotes/20260513-1223-todo-pr2-persistence-score-shadow/
    """
    if positive_fold_ratio is None and fold_sign_ratio is None:
        return None
    if positive_fold_ratio is None:
        return max(0.0, min(1.0, float(fold_sign_ratio)))
    if fold_sign_ratio is None:
        return max(0.0, min(1.0, float(positive_fold_ratio)))
    return max(0.0, min(1.0, 0.7 * float(positive_fold_ratio) + 0.3 * float(fold_sign_ratio)))
```

### `tests/alpha_factory/test_archive.py`

#### 新規テスト

```python
def test_pr2_schema_has_persistence_score_shadow_column() -> None:
    """PR2: GENOMES_SCHEMA に persistence_score_shadow 列が存在 (nullable float)."""
    names = GENOMES_SCHEMA.names
    assert "persistence_score_shadow" in names
    assert GENOMES_SCHEMA.field("persistence_score_shadow").type == pa.float64()
    assert GENOMES_SCHEMA.field("persistence_score_shadow").nullable


def test_pr2_template_persistence_score_shadow_default_none() -> None:
    """PR2: row template default は None (Stage B 評価前)."""
    template = _create_row_template()
    assert template["persistence_score_shadow"] is None


def test_pr2_collect_stage_b_writes_persistence_score_shadow() -> None:
    """PR2: collect_stage_b で persistence_score_shadow が計算・書き込みされる."""
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(), instrument="USD_JPY")
    # _stage_b_result の oos_sharpes=(0.1,-0.2,0.3,-0.1,0.4) → fold_sign_ratio=1.0
    # positive_fold_ratio: payload に 0.6 で設定済
    arc.collect_stage_b(g, "lane", 0, _stage_b_result())
    row = arc._rows[("lane", 0, "g0_i0")]
    # 0.7 * 0.6 + 0.3 * 1.0 = 0.42 + 0.30 = 0.72
    assert row["persistence_score_shadow"] == pytest.approx(0.72)


def test_pr2_persistence_score_shadow_none_when_inputs_none() -> None:
    """PR2: positive_fold_ratio / fold_sign_ratio が両 None なら shadow も None."""
    from src.alpha_factory.archive import _compute_persistence_score_shadow
    assert _compute_persistence_score_shadow(None, None) is None
    assert _compute_persistence_score_shadow(0.5, None) == pytest.approx(0.5)
    assert _compute_persistence_score_shadow(None, 0.8) == pytest.approx(0.8)


def test_pr2_persistence_score_shadow_clipped_to_unit_range() -> None:
    """PR2: 結果は [0.0, 1.0] にクリップされる."""
    from src.alpha_factory.archive import _compute_persistence_score_shadow
    # 上限: 0.7 * 1.5 + 0.3 * 1.5 = 1.5 → clip 1.0
    assert _compute_persistence_score_shadow(1.5, 1.5) == 1.0
    # 下限: 0.7 * -0.5 + 0.3 * -0.5 = -0.5 → clip 0.0
    assert _compute_persistence_score_shadow(-0.5, -0.5) == 0.0


def test_pr2_persistence_score_shadow_persisted_in_parquet(tmp_path: Path) -> None:
    """PR2: flush 後の Parquet で persistence_score_shadow が読み出せる."""
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(), instrument="USD_JPY")
    arc.collect_stage_b(g, "lane", 0, _stage_b_result())
    out = arc.flush(output_dir=tmp_path)
    import pyarrow.parquet as pq
    table = pq.read_table(out)
    df = table.to_pandas()
    assert "persistence_score_shadow" in df.columns
    # 0.72 = 0.7 * 0.6 + 0.3 * 1.0
    assert df.iloc[0]["persistence_score_shadow"] == pytest.approx(0.72)
```

#### 既存テストへの影響

- `test_schema_has_51_columns` → **`test_schema_has_52_columns`** に更新 (= schema 列 51 → 52)
- _create_row_template 全 key を assert する既存テスト (= line 219 周辺) があれば key 追加

## 受入基準

- [ ] GENOMES_SCHEMA に persistence_score_shadow 列追加 (= 52 列)
- [ ] _create_row_template に default None 追加
- [ ] collect_stage_b で計算・書き込み
- [ ] _compute_persistence_score_shadow ヘルパー実装
- [ ] PR2 新規テスト 6 件全 pass
- [ ] 既存 test_archive.py 全 pass
- [ ] alpha_factory 全テスト pass (= PR1 既存失敗 1 件を除く)
- [ ] 既存 RUN 動作不変 (= shadow only)

## ロールバック条件

- 既存テスト破壊
- Parquet schema migration エラー
- collect_stage_b でエラー
- persistence_score_shadow が [0, 1] 外で書き込まれる

## コミット計画

- 1 コミット: `feat(archive): persistence_score_shadow 列追加 (PR2 shadow audit)`
- 影響範囲:
  - src/alpha_factory/archive.py (= schema + template + collect_stage_b + helper、 ~25 行追加)
  - tests/alpha_factory/test_archive.py (= テスト 6 件追加 + 既存 column count assertion 更新)
  - devnotes/20260513-1223-todo-pr2-persistence-score-shadow/ (= conceptual + detailed)

## 関連議論

- `tmp/codex-debate-round2/.codex-output-debate-X-round-5.md` X-T2 仕様
- `tmp/codex-debate-round2/.codex-output-debate-Y-round-5.md` PR2 仕様
- `devnotes/20260513-1223-todo-pr2-persistence-score-shadow/conceptual-design.md`
