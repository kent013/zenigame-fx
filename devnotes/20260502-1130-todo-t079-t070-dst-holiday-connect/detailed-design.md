# 詳細設計 (skeleton): T079 — T070 DST/holiday 連携完成

**作成日時**: 2026-05-02 11:30 JST
**status**: **skeleton + option 未確定 (= 後続セッションで現状調査 → option 選定 → 実装 詳細化)**

---

## 1. 使命・制約

T070 で導入した `BLOCK_BUCKET_RANGES_UTC` 固定 partition と、 T072 で導入した `observability_flags` (= DST/holiday flag) の連携状況を精査し、 必要に応じて DST/holiday 期間で boundary 動的化または adjustment table 追加。

## 2. 概念設計リファレンス

`/Users/ishitoya/repository/zenigame-fx/devnotes/20260502-1130-todo-t079-t070-dst-holiday-connect/conceptual-design.md`

## 3. 改訂対象一覧 (skeleton、 option 未確定)

| # | 改訂名 | 変更箇所 | 性質 | 優先度 |
|---|---|---|---|---|
| 1 | 現状調査 + option 選定 (= 概念設計議論) | (= 議論のみ、 ファイル変更なし) | 設計議論 | 高 |
| 2-A | option A: 現状維持 + observability_flags 活用拡大 | (= 軽量、 caller 経路で flag 利用拡大) | コード追加 | 中 (option A 採用時) |
| 2-B | option B: BLOCK_BUCKET_RANGES_UTC dynamic 化 | `src/backtest/session_block.py` 大幅改造 | 大規模 | 高 (option B 採用時) |
| 2-C | option C: 別 adjustment table 追加 | `src/backtest/calendar.py` に table 追加 | 中規模 | 中 (option C 採用時) |

## 4. 詳細実装方針 (= option 確定後)

option 選定が完了するまで詳細実装は確定不可。 後続セッションでの議論結果に従う。

## 5. 機械検証手順 (= option 確定後)

option 別に異なる検証 grep を用意。

## 6. テスト計画 (= option 確定後)

- option A: observability_flags 利用箇所の test
- option B: dynamic boundary の test (= DST 期間 / 通常期間それぞれで invariant 確認)
- option C: adjustment table 利用箇所の test

## 7. リスク (= 概念設計と同じ)

## 8. 実装モード

**option 選定後に確定** (= option A なら incremental、 option B なら standalone、 option C なら incremental)

## 9. 後続セッションでの本格化手順

1. compute_observability_flags の連携状況を grep + 図示
2. 直近 Run の DST 期間影響を定量評価
3. zenigame-fx-alpha-design で option 選定 + Codex 議論
4. detailed-design 起草 + Codex review → APPROVED
5. zenigame-fx-implement で実装
