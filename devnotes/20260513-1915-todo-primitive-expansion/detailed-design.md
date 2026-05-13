# primitive 拡張 詳細設計

## 実装方針 (= 長期保留、 撤退条件成立まで着手しない)

### Step 1: primitive 候補選定 (= Codex 議論)

zenigame 82 primitive を以下軸で評価:
- FX 適合性 (= イントラデイ / 通貨ペア特性 / セッション)
- look-ahead bias の有無 (= zenigame 側で過去発見 bug の re-trace)
- existing FX primitive との重複

→ 30-50 個に絞る

### Step 2: 移植 (= 1 primitive / PR)

各 primitive:
- `src/alpha_factory/primitives/` に実装
- look-ahead bias check 6 項目全 pass
- パフォーマンスチェック 4 項目全 pass
- unit test 5 件以上
- ruff / mypy clean

### Step 3: clause_architecture 統合

`docs/alpha_factory/clause-architecture.md` 更新で新 primitive を clause に組込む規約整備。

### Step 4: GA primitive_weights 初期重み調整

新 primitive の sampling 比率を 0.5 (= 安全側) で開始、 archive 観測で調整。

## トリガー条件 (= conditional → open 昇格)

- PR1-PR6 完了 + 20 RUN 相当で Stage C 30k+ が 0 個体
- AND archive 横断で out-of-cluster 達成個体ゼロ
- OR ユーザー判断で primitive 拡張を試したいタイミング

## 受入基準 (= sub-TODO 1 件あたり)

- [ ] primitive 実装 + look-ahead bias check 6/6
- [ ] パフォーマンスチェック 4/4
- [ ] unit test 5 件以上
- [ ] integration test (= 既存 clause architecture との整合)
- [ ] docs/alpha_factory/primitives.md 更新

## コミット計画

本 TODO は **umbrella tracker**、 実装時は 30-50 個の sub-TODO に分割。 撤退条件成立時に plan-and-design で sub-TODO 群を生成。

## 関連 TODO

- run71-63-warmstart (= 同じく実験的、 戦略空間探索)
- progress-criteria-docs (= 撤退条件の明文化)
