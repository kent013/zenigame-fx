# 概念設計: signal-active-clause-metric (active_clause の実測化)

## 背景・課題

### 観察事実 (Fact, run-9 / run-8 / run-7 横断)

run-9 archive の構造分析で、`active_clause` カラムが **全 120 個体で `0` 固定** である:

- `active_clause: n=120, mean=0, median=0, std=0, min=0, max=0`
- run-7 / run-8 / run-9 すべて同じ症状

### コード側の前提検証 (C4)

`src/alpha_factory/archive.py` L162-169:
```python
def _compute_active_clause_placeholder() -> int:
    """**Phase 2 placeholder**: runtime 発火 clause 数取得経路が未整備のため
    ``0`` を返す。

    将来 ``DslStrategy`` / engine 側に発火カウンタを追加し、
    ``collect_stage_a`` の引数で受け渡すよう拡張予定（別 TODO）。
    """
    return 0
```

L344:
```python
row["active_clause"] = _compute_active_clause_placeholder()
```

**事実**: これは "TODO 未実装" の placeholder であり、設計上 既に「別 TODO で対応する」とコメントされている。本 TODO がその後続。

### 解釈 (Interpretation)

- `active_clause` が観測不能 (常に 0) のため:
  1. Clause 構造が runtime で機能しているか不明 (clause が「死んでいる」 = 全期間 score=0 か区別不能)
  2. Clause 数の世代追跡 (genome 進化に伴う発火 clause 数の変化) が不可能
  3. 多様性指標 (clause activation entropy など) を archive で集計できない
- これは **観測精度問題**であり、修復しないと他の改善 TODO の効果検証も困難

### 用語の定義 (重要)

`active_clause` の意味を明確にする必要がある。候補:

- **(a) Static**: genome 構造上、`directional` または `local_gate` を 1 つ以上持つ clause の数 (= genome を見れば即決定)
- **(b) Runtime fired**: 評価期間中に少なくとも 1 度、`compute_clause_score(clause, values) != 0` となった clause の数
- **(c) Runtime composite-non-zero**: 評価期間中に composite に非ゼロ寄与した clause の数 (entry/exit を促した数)
- **(d) Runtime entry-firing**: 評価期間中にポジション entry の決定に直接寄与した clause の数

placeholder docstring は「runtime 発火 clause 数」と記載しており **(b) または (c)** を意図している。
本 TODO では **(b) Runtime fired = `compute_clause_score(clause, values) != 0` が少なくとも 1 度発生した clause 数**を採用する (最も基本的な「動作した clause」の意味)。

**float 比較の誤差注記**: `!= 0.0` の比較は Python の float 厳密等価比較。`compute_clause_score` が真にゼロを返す（信号なし）か、浮動小数点誤差で微小非ゼロを返すかを実装時に確認する。信号なし = 真の 0.0 であれば誤差問題は生じない（clause の compute ロジックの性質上、0 か非 0 かは明確に区別される前提）。

**取引未発生でも clause は発火し得る**: `active_clause` は entry/exit の決定（composite 閾値の超過）とは独立。composite がゼロでも各 clause は非ゼロ score を出し得る。したがって `trade_count=0` の個体でも `active_clause>0` になり得る（clause は動いていても複合シグナルが閾値を超えなかったケース）。

**なぜ (a) Static でないのか**: genome 構造から即決まる値は archive の `n_nodes` で既に保持されている (L77 `pa.field("n_nodes", pa.int32(), nullable=False)`)。冗長な記録を避け、`active_clause` には runtime 情報を担わせる方が情報量が高い。

## 改善アイデア

### 単一施策: Runtime fired clause counter の実装

**概要**:
- `DslStrategy` に per-genome の `_active_clause_indices: set[int]` を追加 (clause idx の集合)
- `on_bar` 内で `compute_clause_score(clause, values_per_clause[idx]) != 0.0` の clause idx を set に追加
- `evaluate_stage_a` で `len(strategy.active_clause_indices)` を payload に載せる
- `collect_stage_a` で archive `active_clause` カラムに転記

**シグネチャ**:
```python
class DslStrategy:
    @property
    def active_clause_indices(self) -> frozenset[int]:
        """Runtime で少なくとも 1 度 clause_score != 0 だった clause idx 集合."""
        return frozenset(self._active_clause_indices)
```

### 計測経路 (因果ループを切断しない)

- 本機能は **観測のみ**。`composite` / entry/exit logic / fitness 計算には一切影響しない
- counter は `DslStrategy.on_bar` の既存の `compute_clause_score` 結果を見て set に idx を加えるのみ
- 計測コスト: per-bar O(num_clauses) の比較のみ。numpy なし
- prepared / unprepared 両 path で同じ動作を保証 (T029 prepared signal flattening 後の context)

### Stage B / C との関係

Stage B / C も同じ DslStrategy を使うが、本 TODO では **Stage A の active_clause のみを archive に記録** する (`collect_stage_a` のタイミング)。
Stage B / C は本 TODO スコープ外 (将来 schema 拡張で `active_clause_b`, `active_clause_c` 追加検討の余地あり、ただし scope 外)。

### 観測指標 (測定可能性)

- Run 10 archive で `active_clause` の統計が `min/max/mean` で意味のある分布になる
- `active_clause = 0` は「runtime で 1 度も発火しなかった = clause 完全死滅」を意味するようになる
- per-generation の active_clause 分布変化を archive 集計で追える

## 期待効果

### live_criteria 達成パスへの (間接) 貢献

- **直接効果**: 観測精度向上 (本 TODO の主目的)
- **間接効果 (将来)**:
  - clause 死滅の検出が可能になり、後続 TODO で「死滅 primitive 撤退」「多様性圧」等の介入の効果測定が可能になる
  - signal-eval-consistency-fix と組み合わせると「無取引 = active_clause=0 = clause 全死滅」の判定が archive レベルでできる
- **使命寄与**: 直接的な達成寄与は弱いが、他の改善 TODO の効果検証基盤になる

### 禁止事項チェック

| 禁止事項 | 該当性 | 説明 |
|---------|------|------|
| 1. 期間延長 | 該当なし |
| 2. 見た目改善 | 該当なし | observability のみ |
| 3. GA ハック | 該当なし | fitness / selection に影響なし |
| 4. live_criteria 緩和 | 該当なし |
| 5. 過度な複雑化 | 該当なし | per-bar O(num_clauses) の set 操作のみ |
| 6. 取引回数削減 | 該当なし | trade decision 経路に影響なし |
| 7. オーバーナイト | 該当なし |

## 実装方針 (概要)

### 変更コンポーネント

1. **`src/dsl/strategy.py` `DslStrategy`**:
   - `_active_clause_indices: set[int]` フィールド追加
   - `on_bar` 内で `compute_clause_score(clause, values) != 0.0` を判定し、idx を set に追加
   - `active_clause_indices` 公開 property 追加

2. **`src/alpha_factory/stage_gate.py` `evaluate_stage_a`**:
   - backtest 完了後に `len(strategy.active_clause_indices)` を取得し、payload に `active_clause: int` を追加
   - exception 時は `active_clause: 0` (測定不能)

3. **`src/alpha_factory/archive.py`**:
   - `_compute_active_clause_placeholder()` を撤廃 (もしくは一時的に維持して deprecated 化)
   - `collect_stage_a` で `row["active_clause"] = _required_int(payload, "active_clause")` に変更

4. **テスト計画 (テストファースト)**:
   - `tests/dsl/test_strategy.py` (該当ファイルがあれば):
     - `test_active_clause_indices_initially_empty()`
     - `test_active_clause_indices_records_fired_clause_idx()`
     - `test_active_clause_indices_excludes_never_fired_clause()`
   - `tests/alpha_factory/test_archive.py` / `test_stage_gate.py`:
     - `test_stage_a_payload_includes_active_clause()`
     - `test_collect_stage_a_writes_active_clause_from_payload()`

### 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | incremental |
| 判断根拠 | 既存の TODO marker 撤去 = placeholder 排除。strategy / stage_gate / archive の小範囲変更で完結 |
| 競合リスク | signal-eval-consistency-fix と並行実装可。両者は別ファイルを変更 |
| 想定実装規模 | 小 (~80 LOC + テスト ~120 LOC) |

## 制約・前提

### 既存アーキテクチャとの整合性

- archive schema 不変 (`active_clause: int32 nullable=False default 0`)
- `_required_int(payload, "active_clause", default=0)` で archive default は維持
- **flush() の書き込み保証**: Run 10 以降の `flush()` では `collect_stage_a` で転記した payload 値が優先される。`_create_row_template` のデフォルト 0 が残置されないことを実装時に確認する
- monotonic enrich 規則: Stage A で書かれた `active_clause` は B/C で上書きされない (現状ロジック維持)

### archive 後方互換 (run-7/8/9)

- run-7/8/9 は `active_clause=0` 固定のまま。本 TODO の変更はランタイム側のみで、既存 Parquet ファイルは変更しない
- `generate_run_report.py` など archive を読むスクリプトが `active_clause` の値を 0 前提で特殊処理（ヒストグラム軸幅固定など）していないか実装時に確認する
- Run 10 以降は実測値が入るため、横断比較スクリプトは `active_clause=0` を「実測 0 / placeholder 0 の判別不能期間」として扱う（Run 番号で区別可能）

### 並行計算経路の確認 (C2)

`active_clause` を読む箇所:
- `scripts/alpha_factory/generate_run_report.py:140, 400`: archive 集計
- 他に `active_clause` を fitness / selection に使う箇所があれば本 TODO で副作用確認 (現状無いと予想)

### メモリ制約

- per-genome `set[int]` は最大 num_clauses 個 (通常 1-10) → 数十 byte
- 1 worker 内 active_clause counter は GA 1 個体評価ごとに reset (`DslStrategy` インスタンスは個体ごとに作る) → leak なし
- **並列 worker の安全性**: 現行実装はマルチプロセス (各 worker が独立プロセス) のため `_active_clause_indices` は process-local。共有メモリ化への将来改修時はこのフィールドを thread-local もしくは評価関数への引数に変更する必要がある
- 影響: 無視できる

### パフォーマンス

- per-bar の clause_score 比較 1 回: 数 ns
- 14351 bar × 10 clause = 143,510 比較 / backtest → 1ms 未満
- 既存 `compute_clause_score` は既に呼ばれているので新規計算なし

## スコープ外

- Stage B / C の active_clause 記録 (将来 schema 拡張で追加検討)
- clause activation entropy / per-generation 分布の集計 (報告書側に集約は別 TODO)
- 死滅 clause の自動撤退 / 多様性圧 (別 TODO; 本 TODO は観測精度のみ)
- `n_nodes` (static) との対比指標 `active_clause / n_nodes` 比 → 別 TODO で集計
