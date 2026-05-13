# primitive 拡張 (zenigame 82 primitive 相当の FX 用拡充)

## 背景

zenigame (姉妹プロジェクト) は 82 primitive で運用、 zenigame-fx は現状 ~32 primitive 程度 (= F-* / M-* / P-*)。 archive 実測で Stage C 30k+ が 0 個体、 真の robust 戦略空間が存在するか INCONCLUSIVE。 primitive 表現力が制約になっている可能性。

## 目的

zenigame primitive 集合を **FX 特性に合わせて再選定 + 移植**:
- zenigame の primitive 82 個から FX 適合な subset 抽出
- FX 固有 (= スプレッド / スワップ / セッション特性) の primitive 追加
- 既存 primitive との整合性 (= clause_architecture)

## トリガー条件 (= 将来候補、 撤退条件と連動)

撤退判定:
- PR1-PR6 後 20 RUN 相当で Stage C 30k+ が 0 かつ 20k+ artifact のまま

= 上記成立時に「**primitive 拡張 or 目標水準再設定**」 議論を開始。 本 TODO は **長期保留**、 撤退条件成立まで着手しない。

## 期待効果 (= 仮説、 INCONCLUSIVE)

- 戦略空間拡張で真の robust 個体発見の可能性
- zenigame で実証済の primitive 知見を FX に移植

## スコープ

- primitive 選定議論 (= 別途 Codex 議論で 30-50 個に絞る)
- 各 primitive の clause_architecture / IC 検証
- look-ahead bias check 6 項目必須
- 行動完全変更 (= L 規模、 multi-PR)

## 非目的

- zenigame primitive 全 82 移植 (= 過剰)
- primitive 表現力で everything が解けるという過信

## 参考

- handoff § 12 段 TODO 順 12
- handoff § 撤退条件
- zenigame `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/primitives/` (= 82 primitive)
