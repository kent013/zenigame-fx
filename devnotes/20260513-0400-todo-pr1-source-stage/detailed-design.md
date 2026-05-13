# PR1 詳細設計: source_stage 値入力

## 実装差分

### `src/alpha_factory/archive.py`

#### 変更箇所: `_mark_stage()` メソッド

**現状 (line 977-980)**:
```python
def _mark_stage(self, row: dict[str, Any], incoming: str) -> None:
    prev = str(row.get(_MAX_STAGE_KEY, ""))
    if _STAGE_ORDER[incoming] > _STAGE_ORDER[prev]:
        row[_MAX_STAGE_KEY] = incoming
```

**変更後**:
```python
def _mark_stage(self, row: dict[str, Any], incoming: str) -> None:
    prev = str(row.get(_MAX_STAGE_KEY, ""))
    if _STAGE_ORDER[incoming] > _STAGE_ORDER[prev]:
        row[_MAX_STAGE_KEY] = incoming
        # T058 contract: source_stage を小文字 stage label で同期 populated。
        # 既存挙動 (max stage tracking) は不変。 archive Parquet schema は
        # nullable string で定義済み、 row template default は None。
        row["source_stage"] = incoming.lower()
```

#### 変更ポイント

- 1 行追加のみ (`row["source_stage"] = incoming.lower()`)
- `_STAGE_ORDER[incoming] > _STAGE_ORDER[prev]` のガード内で更新 = stage 進行時のみ書き込み (退行・同 stage 再呼び出しでは更新しない)
- `incoming` は "A" / "B" / "C" の大文字、 schema コメントに合わせて小文字化

### `tests/alpha_factory/test_archive.py`

#### 新規テスト

```python
def test_source_stage_populated_after_stage_a(...) -> None:
    """Stage A collect 後に source_stage == "a" が書き込まれる。"""
    arc = GenomeArchive(run_id="test", run_number=1)
    arc.collect_stage_a(
        genome=fixture_genome,
        lane_id="EUR_JPY",
        generation=0,
        stage_result=stage_a_result_pass,
        instrument="EUR_JPY",
    )
    row = arc.get_row("EUR_JPY", 0, fixture_genome.name)
    assert row["source_stage"] == "a"


def test_source_stage_advances_through_stages(...) -> None:
    """Stage A → B → C の進行で source_stage が "a" → "b" → "c" に更新される。"""
    arc = GenomeArchive(run_id="test", run_number=1)
    arc.collect_stage_a(...)
    assert arc.get_row(...)["source_stage"] == "a"
    arc.collect_stage_b(...)
    assert arc.get_row(...)["source_stage"] == "b"
    arc.collect_stage_c(...)
    assert arc.get_row(...)["source_stage"] == "c"


def test_source_stage_remains_a_when_stage_b_unreached(...) -> None:
    """Stage A pass のみで Stage B 未評価の row は source_stage == "a" のまま。"""
    arc = GenomeArchive(run_id="test", run_number=1)
    arc.collect_stage_a(...)  # pass
    # Stage B 評価せず flush
    row = arc.get_row(...)
    assert row["source_stage"] == "a"


def test_source_stage_initial_default_is_none(...) -> None:
    """row template の source_stage default は None (= 評価開始前)。"""
    template = _create_row_template()
    assert template["source_stage"] is None
```

#### 既存テストへの影響

- `collect_stage_*` 系の既存テストは挙動不変なので影響なし
- ただし archive flush で書き出した Parquet を読み戻して全行 source_stage が populated かを確認する E2E テストがあれば動作確認

## 受入基準

- [ ] `_mark_stage` 修正後、 archive flush の Parquet で source_stage が populated
- [ ] Stage A only 個体: source_stage == "a"
- [ ] Stage A pass ∧ Stage B 評価済個体: source_stage == "b"
- [ ] Stage A pass ∧ Stage B pass ∧ Stage C 評価済個体: source_stage == "c"
- [ ] 評価開始前 (Stage A 評価実行前) の row template: source_stage is None
- [ ] 既存 `tests/alpha_factory/test_archive.py` が全 pass (= 既存挙動不変)
- [ ] 新規テスト 4 件追加 + 全 pass
- [ ] `uv run pytest tests/alpha_factory/test_archive.py` 全 pass

## ロールバック条件

- 既存テスト破壊
- archive flush でエラー
- source_stage が "a"/"b"/"c" 以外の値で populated

## コミット計画

- 1 コミット: `feat(archive): T058 contract source_stage value population (PR1 minimal)`
- 影響範囲: src/alpha_factory/archive.py (1 行追加) + tests/alpha_factory/test_archive.py (4 テスト追加)

## 関連議論

- `tmp/codex-debate-round2/.codex-output-debate-Y-round-5.md` PR1 仕様
- `devnotes/20260513-0400-todo-pr1-source-stage/conceptual-design.md`
