# 最終改善計画: Run 57 → Run 58 (cycle 5)

## 合議ステータス: CONSENSUS REACHED (Round 1)、 APPROVED (案 B 再現性 check)

## 確定施策一覧

| # | 施策名 | 内容 | 変更対象 | 優先度 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion | 合議結果 |
|---|--------|------|---------|--------|---------|--------------|-------------|------------|---------------|-------------------|---------|
| C5-1 | 再現性 check (seed=43 で Run 58) | run_ga.py 引数 `--seed 43` で実行、 dataset / config / code は cycle 4 状態を維持 | (実装変更なし、 run 引数のみ) | Critical (cycle 5) | Principled Parametric (探索独立性) | fp 分布の variance、 elite collapse 再現性 | Run 57 が新 baseline で 1 RUN のみ、 fp variance 不明、 elite collapse 悪化が seed 起因か構造起因か切り分けできない | seed 変更で fp 分布・unique fp ratio・Stage A/B 通過数の差分を観測 | 全く同一の Best 個体 / Stage 通過数になれば仮説 false (seed が探索結果に効いていない、 何か固定的な bias) | Run 58 完走 + Run 57 と異なる Best 個体 + fp 分布の variance 計測完了 + elite collapse 比較データ取得 | APPROVED |

## 却下された提案

| # | 提案 | 理由 |
|---|------|------|
| 案A DSR 配線復帰 | cycle 5 は実装複雑性中-高で 1 cycle 完結に regression risk あり、 cycle 6 に分離 (Codex Q2/Q3 で同意) |
| 案C 観測 script (regime/コスト分解) | cycle 6+ に分離、 cycle 5 は再現性検証を優先 (Codex Q3 で APPROVE) |

## 保留事項

なし (合議 1 round で収束)

## cycle 5 内施策の射程

- **C5-1 単独**: 再現性 check
- 実装変更: **なし** (run_ga.py 引数 --seed 42 → 43)
- DSR 配線復帰は **cycle 6 に分離** (Codex Y パターン推薦)

## cycle 6+ 候補 (Codex 推薦継承)

| 優先 | 施策 | 変更分類 | 概要 |
|-----|------|---------|------|
| 高 | DSR 配線復帰 (cycle 6) | Structural | run_ga.py で SessionBlock 構築 + audit.compute_audit_dsr_for_genome 呼び出し + archive 書き込み |
| 中 | regime セグメント分析 (cycle 7+) | Structural (観測) | gen × Stage 通過率 / fold OOS Sharpe / 月別 fp 分布のクロス集計、 reports/run-reports/run-{N}/regime_segments.json 出力 |
| 中 | コスト分解レビュー (cycle 8+) | Structural (観測) | best 個体 total_pnl の spread / swap / 純 PnL 分解 |
| 中 | elite collapse 対策 (cycle 9+) | Principled | genome_json fingerprint dedup or niche preserving selection |

## 次フェーズへの申し送り

C5-1 は実装変更なし、 詳細設計も "run 引数のみ変更" で extremely simple。 Phase C-1 (詳細設計) は省略可能だが規約上作成、 Phase C-2/C-3 (Codex 設計レビュー) は --skip-consensus 相当の判断は避け、 1 round で軽くレビューしてもらう。
