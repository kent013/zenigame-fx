# Concept: clause-ga-operators

## 目的

Clause Genome に対応した GA の crossover / mutate / random_gen を実装。複雑度ペナルティも導入。

## 前提

- `clause-genome-structure` 完了後

## 設計

### Crossover（`src/ga/operators.py`）

- Clause 単位の swap（親 A の Clause[0] と親 B の Clause[1] を入れ替え等）
- SignalConfig 単位の swap
- 両方のパターンを一定確率でミックス

### Mutate

- Signal の追加/削除
- Signal の weight 変更
- Signal の params（primitive 固有）変更
- Clause 全体の追加/削除（max_clause 範囲内）
- Position / Risk パラメータ変更

### Random 生成（`src/ga/random_gen.py`）

- 初期世代は max_clause=1 固定
- primitive_registry から primitive をランダム選択
- weight は許容範囲からサンプリング

### 複雑度ペナルティ（fitness.py 統合）

```
size_norm = (nodes + 0.5*depth + 2*(n_clause-1) + 0.5*gate_nodes) / size_ref
fitness_pen = fitness_raw - α * size_norm
```

- `α_stage_a = 0.03`
- `α_stage_bc = 0.05`
- `α_max = 0.10`（n_eff 連動で clamp）

## 制約

- enforce_consistency: 各 Clause に最低 1 つの directional、重複 signal 名禁止、Clause 内 modulator 最大 1 個

## テスト

- Crossover で有効な子が生成される
- Mutate で constraint 違反が起きない（enforce_consistency 通過）
- ペナルティで複雑な個体が劣位になる

## 優先度・モード

- Priority: Critical
- Mode: standalone
- テーマ: ga-architecture
