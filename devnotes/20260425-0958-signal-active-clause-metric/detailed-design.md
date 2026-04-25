# 詳細設計: signal-active-clause-metric (active_clause の実測化)

## 概念設計との対応

概念設計: `devnotes/20260425-0958-signal-active-clause-metric/conceptual-design.md`
概念設計 review: `conceptual-review-round-1.md` — APPROVED (Round 1)

## 変更対象ファイル一覧

| ファイル | 変更種別 | 内容 |
|---------|---------|------|
| `src/dsl/strategy.py` | 変更 | `_active_clause_indices` フィールド追加、`on_bar` 内計測、`active_clause_indices` property 追加 |
| `src/alpha_factory/stage_gate.py` | 変更 | `evaluate_stage_a` で payload に `active_clause` 追加 |
| `src/alpha_factory/archive.py` | 変更 | `_compute_active_clause_placeholder` 廃止、`collect_stage_a` で payload から読む |
| `tests/dsl/test_strategy.py` | 変更 | `active_clause_indices` テスト 3 件追加 |
| `tests/alpha_factory/test_stage_gate.py` | 変更 | `evaluate_stage_a` の payload に `active_clause` が含まれるテスト追加 |
| `tests/alpha_factory/test_archive.py` | 変更 | `collect_stage_a` で `active_clause` が payload から転記されるテスト追加 |

## 1. `src/dsl/strategy.py` の変更

### 1.1 `DslStrategy.__init__` — フィールド追加

```python
# 追加フィールド (既存フィールドの後)
self._active_clause_indices: set[int] = set()
```

初期化は `__init__` で空 set。`prepare()` の再 prepare 時に reset しない（`_active_clause_indices` は backtest 全体を通して蓄積する設計 — 一個体の全期間 backtest は 1 回の `DslStrategy` インスタンスで完結するため）。

### 1.2 `active_clause_indices` property 追加

```python
@property
def active_clause_indices(self) -> frozenset[int]:
    """Runtime で少なくとも 1 度 clause_score != 0 だった clause index 集合.

    backtest 完了後に evaluate_stage_a から参照される。
    frozenset を返すことで呼び出し元の意図しない変更を防ぐ。
    """
    return frozenset(self._active_clause_indices)
```

### 1.3 `on_bar` — clause 発火計測ロジックの挿入位置

`values_per_clause` 構築 → `compute_composite(...)` の間、各 clause の評価値が `values_per_clause` に揃った時点でスキャンする。

**変更箇所の特定**:

現行 `on_bar` の構造:
```
1. prepared/unprepared で values_per_clause を構築
2. composite = compute_composite(self._genome.clauses, values_per_clause)  ← ここの直前に挿入
3. pos_cfg 参照
4. entry/exit 判定
```

挿入するコード（`compute_composite` の呼び出し直前）:

```python
# active_clause 計測: compute_clause_score の結果を values_per_clause 経由で観察
# composite 計算前に clause_score を再評価せず、values_per_clause を使って
# compute_clause_score を呼ぶ（重複計算なし）
for _ci, (_clause, _vals) in enumerate(
    zip(self._genome.clauses, values_per_clause)
):
    if compute_clause_score(_clause, _vals) != 0.0:
        self._active_clause_indices.add(_ci)
```

**import**: `compute_clause_score` は `src/dsl/composite.py` に存在する（確認済み）。`strategy.py` の既存 `from src.dsl.composite import compute_composite` に追記する:
```python
from src.dsl.composite import compute_clause_score, compute_composite
```
循環 import リスクなし（`strategy.py` → `composite.py` は既存の依存方向）。

**不感帯について**: `!= 0.0` の厳密等価比較を採用する。`compute_clause_score` の実装上、信号なし = 真の 0.0 を返す設計が前提。丸め誤差が問題になる場合は後続 TODO で `abs(score) > EPS` 形式に変更する（本 TODO スコープ外）。

**実装上の注意**:
- `compute_clause_score` は既存の `compute_composite` の内部でも呼ばれているが、ここでは重複して呼ぶ（pure function で状態変更なし）
- prepared/unprepared 両 path ともに `values_per_clause` が構築された後なので、同一のループで処理できる（分岐不要）

## 2. `src/alpha_factory/stage_gate.py` の変更

### 2.1 `evaluate_stage_a` — payload に `active_clause` 追加

**変更前** (L276-L280 付近):
```python
strategy = DslStrategy(genome, primitive_evaluator)
broker = MockBroker(instrument_meta=meta)
result = run_backtest(bars_60d, strategy, broker, backtest_config)
bt = compute_metrics(result.trades, result.equity_curve)
trade_count = bt.trade_count
sharpe_raw = float(bt.sharpe) if bt.sharpe is not None else None
```

**変更後**:
```python
strategy = DslStrategy(genome, primitive_evaluator)
broker = MockBroker(instrument_meta=meta)
result = run_backtest(bars_60d, strategy, broker, backtest_config)
bt = compute_metrics(result.trades, result.equity_curve)
trade_count = bt.trade_count
sharpe_raw = float(bt.sharpe) if bt.sharpe is not None else None
active_clause_count = len(strategy.active_clause_indices)  # 追加
logger.debug(
    "stage_a.active_clause_measured",
    genome=genome.name,
    active_clause=active_clause_count,
)  # 監査性: 転記値をログに残す
```

**変数宣言の追加** (`active_clause_count` の初期化):

`try` ブロックの外側（例外時のデフォルト値）:
```python
active_clause_count = 0  # exception 時は 0 (測定不能)
```

**payload への追加**:
```python
"payload": {
    "fitness_raw": fitness_raw,
    "size_norm": size_norm_val,
    "fitness_pen": fitness_pen,
    "alpha_a": stage_config.stage_a_alpha,
    "threshold": stage_config.stage_a_threshold,
    "trade_count": trade_count,
    "sharpe_raw": sharpe_raw,
    "active_clause": active_clause_count,  # 追加
},
```

## 3. `src/alpha_factory/archive.py` の変更

### 3.1 `_compute_active_clause_placeholder` の廃止

```python
# 削除対象
def _compute_active_clause_placeholder() -> int:
    """**Phase 2 placeholder**: ..."""
    return 0
```

→ 完全削除。テスト (`test_archive.py`) が `_compute_active_clause_placeholder` を import している場合は合わせて修正が必要（後述）。

### 3.2 `collect_stage_a` の変更

**変更前** (L344):
```python
row["active_clause"] = _compute_active_clause_placeholder()
```

**変更後**:
```python
row["active_clause"] = _required_int(payload, "active_clause", default=0)
```

`_required_int` は既存のヘルパー関数。`default=0` は payload に `active_clause` キーがない場合（旧コードとの互換 or 例外時）の fallback。

### 3.3 `__all__` と import の更新

`_compute_active_clause_placeholder` は `__all__` に含まれていないが、`test_archive.py` が明示的に import している。テスト修正と合わせて対応。

### 3.4 flush 保証の確認

`flush()` は `_rows` の各 `row` dict をそのまま `pa.Table.from_pylist` に渡す。`collect_stage_a` で `row["active_clause"]` に書いた値は `flush()` 時点でも保持される（`flush` はフィールドを再計算しない）。last-mile guard (`cr_keys != schema_names`) は schema 整合性のみチェック — 値は通り抜ける。

**確認事項**: `_create_row_template()` の `"active_clause": 0` はデフォルト値として維持する（Stage A が呼ばれる前に `flush` が起きる異常系 = 0 fallback を保証）。変更不要。

## 4. テスト計画

### 4.1 `tests/dsl/test_strategy.py` — 追加テスト 3 件

既存 `ScriptedEvaluator` を再利用する。

**test_active_clause_indices_initially_empty**:
```python
def test_active_clause_indices_initially_empty():
    """DslStrategy 初期化直後の active_clause_indices は空 frozenset。"""
    genome = _mk_genome()
    evaluator = ScriptedEvaluator({})
    strategy = DslStrategy(genome, evaluator)
    assert strategy.active_clause_indices == frozenset()
```

**test_active_clause_indices_records_fired_clause_idx**:
```python
def test_active_clause_indices_records_fired_clause_idx():
    """clause_score が 1 度でも非ゼロになった clause idx が記録される。"""
    # clause idx=0 が bar 0 で発火するケース
    genome = _mk_genome(entry_threshold=0.3)
    # F1=0.5 → clause_score != 0 → idx=0 が記録されるはず
    evaluator = ScriptedEvaluator({0: {"F1": 0.5}})
    strategy = DslStrategy(genome, evaluator)
    bar = make_bar(0)
    snapshot = PortfolioSnapshot(positions=[], available_margin=Decimal("100000"))
    strategy.on_bar(bar, snapshot)
    assert 0 in strategy.active_clause_indices
```

**test_active_clause_indices_excludes_never_fired_clause**:
```python
def test_active_clause_indices_excludes_never_fired_clause():
    """全バーで clause_score=0 だった clause idx は含まれない。"""
    # F1=0.0 → clause_score = 0 → idx=0 は記録されない
    genome = _mk_genome()
    evaluator = ScriptedEvaluator({0: {"F1": 0.0}})
    strategy = DslStrategy(genome, evaluator)
    bar = make_bar(0)
    snapshot = PortfolioSnapshot(positions=[], available_margin=Decimal("100000"))
    strategy.on_bar(bar, snapshot)
    assert strategy.active_clause_indices == frozenset()
```

**注意**: `ScriptedEvaluator` は `evaluate(bars, idx, signal)` を実装しているが、`compute_clause_score` が `values: dict[str, float]` を期待する点との整合をテスト設計時に確認すること（`on_bar` の `values_per_clause` 構築 → `compute_clause_score` 呼び出しの流れ）。

### 4.2 `tests/alpha_factory/test_stage_gate.py` — 追加テスト

**test_stage_a_payload_includes_active_clause**:
- `evaluate_stage_a` の戻り `StageResult.metrics["payload"]` に `"active_clause"` キーが存在することを確認
- 値は `int` 型であること
- 最小の mock genome（clause 数 = 1、常に発火する evaluator）で `active_clause >= 0` になること

### 4.3 `tests/alpha_factory/test_archive.py` — 修正・追加

**import 修正**:
- `_compute_active_clause_placeholder` の import を削除
- 当該関数を参照するテストを削除 or 書き換え

**test_collect_stage_a_writes_active_clause_from_payload**:
- `payload` に `"active_clause": 3` を含む `StageResult` を作成
- `collect_stage_a` 後 `get_row_snapshot` で `active_clause == 3` を確認

**test_collect_stage_a_active_clause_defaults_to_zero_when_missing**:
- `payload` に `"active_clause"` キーが無い `StageResult` を使用
- `collect_stage_a` 後 `active_clause == 0` になること（backward compat fallback）

## 5. `compute_clause_score` の確認事項

実装前に以下を確認:

```bash
grep -rn "compute_clause_score" src/dsl/
```

期待: `src/dsl/eval.py` または `src/dsl/composite.py` に存在。`on_bar` 内での追加 import が必要かを確認。

## 6. 後方互換まとめ

| 項目 | 対応 |
|------|------|
| run-7/8/9 Parquet の `active_clause=0` | 既存ファイルは変更しない。Run 10 以降は実測値が入る |
| `generate_run_report.py` の集計 | `active_clause=0` が placeholder 期間と実測ゼロの両方を指すが、Run 番号で区別可能。スクリプト側の変更は不要（値が意味を持つようになるのみ） |
| `_compute_active_clause_placeholder` の削除 | `test_archive.py` の import を合わせて修正する |
| `_create_row_template` の `"active_clause": 0` | 維持する（Stage A 前 flush の fallback） |

## 7. 実装順序 (テストファースト)

1. `tests/dsl/test_strategy.py` に 3 テスト追加 → RED
2. `src/dsl/strategy.py` に `_active_clause_indices` + `active_clause_indices` property + `on_bar` 計測ロジック追加 → GREEN
3. `tests/alpha_factory/test_stage_gate.py` に payload テスト追加 → RED
4. `src/alpha_factory/stage_gate.py` の `evaluate_stage_a` に `active_clause_count` 追加 → GREEN
5. `tests/alpha_factory/test_archive.py` 修正（import + 新テスト）→ RED
6. `src/alpha_factory/archive.py` の `collect_stage_a` 変更 + placeholder 削除 → GREEN
7. 全テスト一括実行で確認

## 8. 禁止事項最終チェック

| 禁止事項 | 本変更での影響 |
|---------|-------------|
| 1. 期間延長 | なし |
| 2. 見た目改善 | なし（観測のみ） |
| 3. GA ハック | なし（fitness/selection 計算に `active_clause_indices` を使わない） |
| 4. live_criteria 緩和 | なし |
| 5. 過度な複雑化 | なし（フィールド 1 個、set 操作のみ） |
| 6. 取引回数削減 | なし（entry/exit 判定を通過する前に計測するが、判定ロジックを変更しない） |
| 7. オーバーナイト | なし |
| 8. 伝搬漏れ | `evaluate_stage_a` → payload → `collect_stage_a` → archive row → flush の全経路を網羅 |

## 9. スコープ外の再確認

本 TODO が終わったら以下の後続 TODO を新規登録して良い（本 TODO の成果を前提とする）:
- Stage B / C の `active_clause_b`, `active_clause_c` 記録
- `active_clause / n_nodes` 比の `generate_run_report.py` 集計
- `active_clause=0` 個体の clause 死滅診断（後続 TODO）
