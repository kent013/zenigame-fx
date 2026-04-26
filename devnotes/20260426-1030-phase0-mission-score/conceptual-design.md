# Phase 0 / T043 — mission_score 4 軸 soft 合算（概念設計）

**起点監査**: [audit-codex-round-2.md §3-4](../20260426-1010-ga-audit-r16/audit-codex-round-2.md)

## 仮説

**「使命達成までの距離」が 0/1 hard 判定でしか分からないため、Run 間比較・改善方向検出が困難**。zenigame の `amscore` のような連続スコアを観測指標として導入することで、改善 cycle の判断が data-driven になる。

## 検証済み事実

- `live_criteria` は 4 軸 (sharpe / total_pnl / max_drawdown / trade_count) hard pass/fail のみ
- GA fitness は `sharpe` 単軸で他 3 軸は selection 圧に直接寄与しない
- Run 14: total_pnl=0 / Run 15: pnl=8,660 sharpe=0.069 / Run 16: pnl=0 — **Run 間で「どちらが mission に近いか」を 1 軸で測定不能**
- zenigame R1260 では amscore=0.7731 のような連続値で 86 Run 連続未達でも進捗追跡可能

## 北極星制約との接続

AGENTS.md 禁止事項 #2「見た目の数値をよくしようとする改善」に **抵触しない**: 本タスクは hard live_criteria は不変、archive/report への観測指標追加のみ。GA fitness にも組み込まない（当面 observation only）。

## 解決方針

各軸 `i` に `lower_i` / `target_i` を定め、min-max 正規化 + [0.1, 1.0] スケーリングし幾何平均:
```
score_i = clip((metric_i - lower_i) / (target_i - lower_i), 0, 1)
score_i' = 0.1 + 0.9 × score_i
mission_score = (Π score_i')^(1/4)
```

archive Parquet スキーマに `mission_score: float` カラム追加（既存値伝搬規約: schema → template → write の 4 段）。

## 成功判定

- archive `mission_score` が Stage C pass/fail に依存せず（Stage A 通過個体から）計算される
- Run 14-16 archive replay で `mission_score` 分布が出る
- report で best mission_score / median / hist 表示
- 全軸 target 達成で 1.0、全軸 lower 以下で 0.1（log 表示可能）

## scope 外

- `mission_score` を GA fitness に組み込む（Phase 1 以降に re-evaluate）
- 軸別重み付け（当面は等重幾何平均、運用後に見直し）

## 詳細設計

[detailed-design.md](detailed-design.md) 参照。
