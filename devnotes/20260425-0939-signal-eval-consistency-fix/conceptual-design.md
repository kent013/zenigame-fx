# 概念設計: signal-eval-consistency-fix (無取引優位の選抜下位化)

## 背景・課題

### 観察事実 (Fact, run-9 / run-8 / run-7 横断)

run-9 (run_20260425_002330) の archive 横断分析で、以下の事実が確認された:

1. **無取引個体 (`trade_count = 0`) が選抜優位**:
   - `fitness_pen = 0` の個体 90/120 (75%) はすべて `trade_count = 0`
   - 取引した 30 個体は `fitness_pen = -8.91 ~ -93.10` (全て負 Sharpe)
   - run-9 best は `g0_i1` (gen 0, `trade_count=0`, `fitness=0`, A/B/C 全不通過)

2. **GA が「無取引」へ世代収束**:
   - 世代平均 `trade_count`: 380.9 → 100.6 → 44.7 → 14.2 → 22.15 → 82.1
   - 中盤に強い無取引偏向

3. **既存合議 (improvement-plan.md §確定施策一覧 C1) で「Critical / 無取引ペナルティの構造的導入」が承認済**:
   - target_metric: `trade_count=0` 比率を Run 10 で 30% 未満
   - causal_path: `trade_count=0 → fitness_pen=0` が「取引する負 Sharpe」より上位

### 解釈 (Interpretation)

- Stage A 不通過個体の selection_score 比較で `(0,0,0,fitness_pen)` の `fitness_pen` 部分が支配的
- 現状: `trade_count=0` (`no_trades` reason) → payload `fitness_pen=None` → `_required_float(default=0.0)` で archive に `0.0` 永続化
- 一方、取引したが負 Sharpe の個体は `fitness_pen` が負値で archive に永続化
- 比較 `0.0 > -8.91` の自然な大小関係で、無取引が常勝

### コード側の前提検証 (C4)

`scripts/alpha_factory/run_ga.py` `IndividualCacheEntry.selection_score` (L111-118):
```python
return (
    int(self.stage_c_pass),
    int(self.stage_b_pass),
    int(self.stage_a_pass),
    float(self.fitness_pen),
)
```
辞書式比較。Stage 全不通過の個体間では `fitness_pen` のみが差異要因。

`scripts/alpha_factory/run_ga.py` cache 構築 (L444-467):
```python
fp_raw = row.get("fitness_pen")
try:
    fp = float(fp_raw) if fp_raw is not None else -math.inf
except (TypeError, ValueError):
    fp = -math.inf
cache[g.name] = IndividualCacheEntry(..., fitness_pen=fp, ...)
```
**archive に書かれた値**を読む。archive `fitness_pen` カラムは `nullable=False default 0.0`。

`src/alpha_factory/stage_gate.py` payload (L325-333) は `fitness_pen=None` を返すが、`src/alpha_factory/archive.py` `_required_float` (L212-217) で `None` → `0.0` に default 化される。

### Codex レビュー指摘 (Round 1) 反映

Round 1 で以下の Critical / Warning を受けた:
- **Critical**: archive の canonical `fitness_pen` に sentinel 値 (`-1e12` 等) を入れると `calibrate_gate.py` (L317, L548) が quantile 集計に使うため threshold が floor に寄って Stage A が壊れる
- **Critical**: `total_pnl` 列は Stage B IS 値 / Stage C holdout 値の SSOT。Stage A 60d 値で上書きすると意味論が破綻
- **Warning**: スコープが「記録整合性 + 選抜圧」と広がっている。本 TODO は **selection 専用** に絞り、PnL audit は別 TODO

→ archive canonical は触らず、**selection_score 専用に feasibility を加える**方針へ revise。

## 改善アイデア (revised)

### 単一施策: selection_score への feasibility tier 追加

`IndividualCacheEntry.selection_score` の lex tuple に `feasible_trade` (bool→int) を追加:

```python
return (
    int(self.stage_c_pass),
    int(self.stage_b_pass),
    int(self.stage_a_pass),
    int(self.feasible_trade),   # 新規: trade_count >= 1 (or > 0)
    float(self.fitness_pen),
)
```

**意味付け**:
- Stage A/B/C 全不通過の個体間で、まず「取引したか否か」で大小を決める
- 取引した個体 (`feasible_trade=1`) > 無取引個体 (`feasible_trade=0`)
- 取引個体内では `fitness_pen` で順序

**archive を変更しない**:
- `fitness_pen` の意味論は不変
- `calibrate_gate` の quantile pool に汚染なし
- `total_pnl` カラムも不変

**`feasible_trade` のソース**:
- archive row の canonical `trade_count` を読む (既存カラム)
- `feasible_trade = (trade_count >= 1)` を `_update_cache_from_archive` 内で算出
- **意味の明示**: ここでの `trade_count` は archive SSOT (Stage A→B→C で最後段が prevail) であり、「その row の canonical trade_count が 1 以上」を意味する。「ever-traded 判定」ではない

### 観測指標 (測定可能性)

成功条件 (Run 10 archive で観測):
- **条件付き**: `feasible_trade=True` 個体が母集団に 1 体以上存在する run では、best が no-trade にならない (`trade_count > 0`)
- `tc=0` 比率の低下 (75% → < 50% smoke target、5 RUN 横断 descriptive comparison)

注意: 5 RUN smoke check は descriptive に限定し、有意性主張は行わない (C7)。
全個体 `trade_count=0` の run では本施策のみでは best も no-trade になり得る (この場合は別の構造改善が必要)。

## 期待効果

### live_criteria 達成パスへの貢献

- **直接効果**: GA selection が「取引した負 Sharpe」を「無取引 fitness=0」より優先するようになり、取引する個体への進化圧が回復
- **使命寄与**: live_criteria の `trade_count_min: 50` への到達確率が構造的に上昇 (現状 0)
- **副次効果**: `tc=0` 比率の世代単調減少パターンの解消が期待される

### 禁止事項チェック

| 禁止事項 | 該当性 | 説明 |
|---------|------|------|
| 1. 評価期間延長 | 該当なし | 期間変更なし |
| 2. 見た目の数値改善 | 該当なし | 真の信号効力を表面化させる方向 |
| 3. GA ハック | **境界** | selection_score の lex tuple 変更は GA 選抜ロジック変更だが、archive canonical (`fitness_pen` / `total_pnl`) は不変。calibrate-gate にも影響なし。**「fitness の意味」を変えるのではなく「同 stage 失敗時の tie-break」を追加する**範囲に限定 |
| 4. live_criteria 緩和 | 該当なし | 閾値変更なし |
| 5. 過度な複雑化 | 該当なし | tuple に 1 要素追加のみ |
| 6. 取引回数削減で成績を見せる | **逆方向** | 「取引した方が選抜上位」の構造に修正 |
| 7. オーバーナイト保有前提 | 該当なし | 該当なし |

## 実装方針 (概要)

### 変更コンポーネント

1. **`scripts/alpha_factory/run_ga.py`**
   - `IndividualCacheEntry` に `feasible_trade: bool` field 追加
   - `selection_score` lex tuple に `int(self.feasible_trade)` を `stage_a_pass` と `fitness_pen` の間に挿入
   - `_update_cache_from_archive` で `archive row.trade_count >= 1` から `feasible_trade` を導出
   - archive row 不在 (None) の個体は `feasible_trade=False` (= 評価未到達 = 取引もしていない)

2. **archive 側変更なし**
   - `src/alpha_factory/archive.py`: 不変
   - `src/alpha_factory/stage_gate.py`: 不変
   - schema 変更なし

3. **波及変更**
   - `AGENTS.md`: GA selection ロジックの説明箇所 (該当箇所があれば追記)
   - `docs/alpha_factory/clause-architecture.md`: best 選抜の lex tuple 記述 (`(C, B, A, fitness_pen)` → `(C, B, A, feasible_trade, fitness_pen)`)
   - `docs/alpha_factory/stage-gates.md`: 該当箇所があれば
   - `.claude/skills/zenigame-fx-*/SKILL.md`: 該当する記述があれば

4. **テスト計画 (テストファースト)**
   - **既存テスト確認**: `tests/scripts/alpha_factory/test_run_ga.py` (該当するファイルがあれば) の `selection_score` / `_select_best` 関連
   - **新規回帰テスト**:
     - 「Stage 全不通過、`trade_count=0`、`fitness_pen=0`」の個体 vs 「Stage 全不通過、`trade_count=10`、`fitness_pen=-5`」の個体 → 後者が `_select_best` で勝つ
     - 「Stage A 通過、`trade_count=10`、`fitness_pen=-5`」の個体 > 「Stage 全不通過、`trade_count=100`、`fitness_pen=10`」 (Stage pass tier が `feasible_trade` より上位)
     - 「Stage 全不通過、`trade_count=5`、`fitness_pen=-3`」 > 「Stage 全不通過、`trade_count=10`、`fitness_pen=-5`」 (`feasible_trade` 同値の場合、`fitness_pen` で順序)
     - archive row 不在の個体は `feasible_trade=False`

### 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | incremental |
| 判断根拠 | 単一ファイル (`scripts/alpha_factory/run_ga.py`) の小範囲変更 + テスト追加で完結。archive / stage_gate / calibrate-gate への影響なし |
| 競合リスク | 同時並行で run_ga.py を改修する別 TODO があれば衝突。現状無し |
| 想定実装規模 | 小〜中 (~50 LOC + テスト ~80 LOC) |

**スコープ表現の補足**: production logic の変更は `scripts/alpha_factory/run_ga.py` のみ。追従として以下の更新あり:
- `tests/scripts/test_alpha_factory_run_ga.py` の selection_score 長さ 4 → 5 を見ているテスト (該当箇所)
- `scripts/alpha_factory/generate_run_report.py` の selection_score 4 要素 tuple 説明箇所
- `docs/alpha_factory/clause-architecture.md` の lex tuple 記述

## 制約・前提

### 既存アーキテクチャとの整合性

- **archive schema 不変**: SSOT (`fitness_pen`, `total_pnl`) の意味論を保持
- **calibrate-gate 影響なし**: `fitness_pen` の分布が変わらない
- **monotonic enrich 規則不変**: archive の collect_stage_* ロジックは触らない

### existing 改善計画との整合 (improvement-plan.md §C1)

- improvement-plan.md の C1 (無取引ペナルティの構造的導入) と target_metric / causal_path / falsification / success_criterion を継承
- 同 C2 (PnL 集計経路の数値整合性監査) は **本 TODO のスコープ外**。別 TODO で audit/log として実装する

### メモリ制約

`IndividualCacheEntry` に bool 1 つ追加。1 個体当たり ~1 byte 増。120 個体で ~120 byte 増 → 影響なし

## スコープ外

- **archive schema 変更** (nullable 化 / 新カラム追加) → 別 TODO
- **PnL 集計経路の数値整合性監査** (improvement-plan §C2) → 別 TODO で audit/log として
- **`live_criteria.trade_count_min` の fitness 内生化** → 別 TODO
- **`active_clause` 実測化** → 別 TODO (本 review-theme の別候補)
- **ルックアヘッド全経路 CI** → 別 TODO (本 review-theme の別候補)
- **反証実験 (短縮 RUN x 5)** の自動実行 → improve-cycle が次サイクルで自然に行う
