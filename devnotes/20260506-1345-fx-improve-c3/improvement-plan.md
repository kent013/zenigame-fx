# 最終改善計画: Run 35 → Run 36 (cycle 3)

## 合議ステータス: CONSENSUS REACHED (Round 1)

Codex 合議で全提案が APPROVE / MODIFY (P1) で収束。 ループ収束ルールに従い 1 ラウンドで終了。

## 確定施策一覧

| # | 施策名 | 内容 | 変更対象 | 優先度 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion | 合議結果 |
|---|--------|------|---------|--------|---------|--------------|-------------|------------|---------------|-------------------|---------|
| **C1 (P1)** | **Stage A 上位群 fold robustness sidecar parquet 追加** | archive Parquet 確定後、 generation 別 stage_a 上位 20% の fold_sign / median_oos_sharpe 集計を sidecar Parquet として書き出す | `src/alpha_factory/diagnostics/` 系 + run_ga.py 末尾 hook + `reports/run-reports/run-{N}/diagnostics/stage_a_top_fold_robustness.parquet` | Critical | **Structural** (観察データ追加のみ、 GA 評価ロジック変更なし) | Stage A 上位群の世代別 fold robustness 可観測性 (cycle 4 で相関検証可能か) | top20% 集計だけだと分母・選抜基準不明で誤読、 NaN 混入時に解釈不能 | 観測設計の曖昧さが「目的関数不整合」仮説の反証可能性を下げる | cycle 4 で「generation ごとの Stage A 順位優位群ほど fold_sign が上がる/上がらない」を統計的に判定できれば仮説検証成立 | 各 generation で top 群と母集団の比較ができ、 再計算不要で analyze-run から直接判定可能 | **MODIFY** (Codex Round 1) |
| **C2 (P2)** | archive Top-1 trade<50 stage_a_pass 経路調査 (devnotes ノートのみ、 実コード非変更) | g26_i95 の stage_a_pass=True 経路を log + grep で追跡、 設計通り or bug の判定資料を 1 ページにまとめる | `devnotes/20260506-1345-fx-improve-c3/investigation-stage-a-pass-trade-min.md` | Critical | Structural (調査のみ) | live_criteria 整合性 | trade_count<50 で stage_a_pass=True になる経路未同定 | 判定経路未把握で修正すると別ルートを壊す恐れ | g26_i95 の通過ログと判定関数経路を突合し設計通り/bug を二択化 | cycle 4 開始時点で「fix 要否」と「修正ポイント候補」が 1 ページで判断可能 | **APPROVE** (Codex Round 1) |

### C1 の MODIFY 内容 (Codex Round 1)

sidecar Parquet スキーマに以下を追加（最小防御的フィールド）:
- `run_id` (string): 同定用
- `population_n` (int): 母集団サイズ (= 96)
- `top_n` (int): 集計対象数 (= int(population_n × 0.20) = 19)
- `top_selector` (string): 選抜基準名 (= "fitness_pen")
- `fold_sign_positive_ratio` (float): top 群で fold_sign_ratio >= 0.0 個体の比率
- `median_oos_sharpe_nan_ratio` (float): top 群で median_oos_sharpe が NaN だった個体の比率 (NaN 混入の警告)

既存案フィールド:
- `generation` (int)
- `top_pct` (float, = 0.20)
- `n` (int, top_n と同じ)
- `fold_sign_mean` (float)
- `fold_sign_median` (float)
- `median_oos_sharpe_mean` (float)
- `median_oos_sharpe_median` (float)
- `fitness_pen_mean` (float)

合計 13 column の sidecar parquet を `reports/run-reports/run-{N}/diagnostics/stage_a_top_fold_robustness.parquet` に出力。

## 却下された提案

| # | 提案 | 却下理由 |
|---|------|---------|
| — | (なし — cycle 3 は最小介入方針) | — |

## 保留事項（合議収束ルールにより次 Run 検証申し送り）

| # | 仮説 | 最小変更案 | 検証条件 |
|---|------|----------|---------|
| P3 | best trade_count attractor (50-55 帯固定化) | cycle 4-5 best trade_count の経時観察 | 4-5 run 連続で 50-55 帯集中が再現しなければ棄却 |
| P4 | cross-pair shadow 妥当性 | multi-instrument RUN 復帰時に判断 | 復帰後 1 cycle で採否判断可能な指標 |
| P5 | max_clause=2 維持/戻し | P1 sidecar 結果待ち | P1 で「目的関数不整合が主因でない」と verified なら再検討 |

## 次フェーズへの申し送り

- Phase C (詳細設計): C1 (sidecar Parquet 追加) のみが実コード変更対象。 C2 は devnotes ノート作成のみで実コード非変更。
- Phase 4 (RUN 36): cycle 3 改修の効果検証。 期待: sidecar 出力が成功して cycle 4 で「Stage A 上位 vs fold robustness」 相関が分析可能に
- cycle 4 analyze で P1 sidecar データを読んで、 「探索圧不整合」仮説を反証/確証

## 使命・禁止事項チェック

- ✅ 禁止事項 1 (期間延長): 該当なし
- ✅ 禁止事項 2 (見栄え改善): C1 は観察 sidecar 追加のみ、 fitness や Stage 通過には影響しない
- ✅ 禁止事項 3 (GA ハック): 該当なし
- ✅ 禁止事項 4 (閾値緩和): 該当なし
- ✅ 禁止事項 5 (複雑化): C1 は単純な集計 sidecar、 1 column 追加 + 13 列の parquet 1 個
- ✅ 禁止事項 6 (取引回数削減): 該当なし
- ✅ 禁止事項 7 (オーバーナイト保有前提): 該当なし
- ✅ FX 固有制約: 該当なし (本 cycle は GA 評価ロジック非変更)
- ✅ メタ過学習ガード: C1 = Structural, C2 = Structural (調査) で全て APPROVE 可
