# 詳細設計: Run 11 施策

## 状況

cycle 2 でも TODO 0 件。施策 1/3（Structural）は cycle 3 以降で TODO 経由実装。
本 cycle は **再現性検証 RUN** として Run 10 と同条件で実行し、変動性を観察。

## 確定施策（実装は次サイクル）

improvement-plan.md §確定施策一覧 を継承。本 detailed-design.md では具体的な Before/After は記載せず、`/zenigame-fx-alpha-design` 経由の概念設計に委ねる。

## Run 11 実行パラメータ

| パラメータ | 値 | R10 からの変更 |
|-----------|-----|--------------|
| population_size | 96 | 同左 |
| generations | 60 | 同左 |
| dataset.start | 2026-03-01T00:00:00Z | 同左 |
| dataset.end | 2026-03-15T00:00:00Z | 同左 |

## 期待観測

- best_fitness と Stage A 通過率は Run 10 と同等 (再現性確認)
- 異なるシードで Run の振れ幅を計測 (R9 の崩壊が小規模 GA の確率的事故だったかの仮説検証)
