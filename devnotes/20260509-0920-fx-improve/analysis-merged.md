# マージ分析: Run 54 (cycle 2)

**Generated**: 2026-05-09 09:30 JST
**run_id**: `run_20260508_224819`

## 合意事項 (両者一致)

| # | 観察 / 仮説 | Claude | Codex |
|---|---|---|---|
| 1 | run-53 と run-54 で archive 全フィールド完全一致 (n=5,856) | F2 | Facts |
| 2 | T091 段階 1 (median 0.025) は gate 内部で機能 verified (`median_oos_sharpe<min` reason -2 件) | I1 | H1 賛成 |
| 3 | 主ボトルネックは median ではなく positive_fold_ratio | (F4 観察) | H2 強く支持 |
| 4 | seed=100 領域は profitability 構造的に低い (cycle 1 verified を再確認) | I2 | I2 賛成 |
| 5 | Layer 1 archive replay (run-52、 g70_i9 / g83_i12) は段階 2 実装より優先 | (Suggestion) | B 高優先 |
| 6 | mission-eligible 個体は run-52 archive で 7 件存在、 うち pfre>=0.6 で positive_fold_ratio<min reason 不含は 2 件 (g70_i9 / g83_i12) | (検証データ) | (検証データ) |

## Layer 1 archive replay 結果 (本 cycle で実施)

### 検証対象 (run-52 archive)

g70_i9: trade=138, total_pnl=56,930, pfre=0.7, blocked reason="median_oos_sharpe<min" のみ
g83_i12: trade=127, total_pnl=50,820, pfre=0.7, blocked reason="median_oos_sharpe<min" のみ

### 重大な発見

**archive に `median_oos_sharpe` の実値が保存されていない**。
- `trade_sharpe_stage_b` 列は存在するが、 これは Stage B **全期間 1 pass** の trade Sharpe (T044 仕様)、 `median_oos_sharpe` (per-fold median) とは別物
- g70_i9: trade_sharpe_stage_b=-0.040269 (Stage B 全期間 backtest)、 median_oos_sharpe 値は不明
- g83_i12: trade_sharpe_stage_b=-0.035215 (Stage B 全期間 backtest)、 median_oos_sharpe 値は不明

### Layer 1 直接 verify の不可性

archive replay 経路では median_oos_sharpe の実値が取得不可のため、 T091 段階 1 (0.025) で g70_i9 / g83_i12 が pass するかは **直接 verify 不可**。

### 推定

`stage_b_reason_codes` から:
- median_oos_sharpe < 0.05 (現行閾値) — 既知
- positive_fold_ratio >= 0.6 (= pfre 0.7、 別 reason 不含)

→ median_oos_sharpe ∈ [-∞, 0.05) の範囲。 T091 段階 1 (0.025) で:
- 0.025 ≤ median < 0.05: pass (期待効果あり)
- median < 0.025: 不通過 (期待効果なし)

**結論**: 直接 verify 不可、 50/50 確率の推定。

## Claude 独自の発見

| # | 発見 |
|---|---|
| C1 | run-54 と run-53 の summary.best 完全一致 (g52_i27、 trade=61、 fp=0.0375) |
| C2 | archive top fp は g57_i15 (trade=32、 feasible=False)、 selection_score lex で g52_i27 (feasible=True) が best として選ばれる構造 verified |
| C3 | `median_oos_sharpe<min` trigger 数の 2 件減 (1439→1437) は段階 1 が gate 内部で機能している唯一の証拠 |

## Codex 独自の発見

| # | 発見 |
|---|---|
| Z1 | T091 段階 2/3 の seed=100 効果は **INCONCLUSIVE** (Claude 「変わらない見込み」 は弱い、 段階 2 で境界個体の選抜順が非線形に変わる可能性) |
| Z2 | mission 到達経路完全閉塞 (CRITICAL_DRIFT) は seed/gens を広げないと未立証、 seed 23/42 で B pass 実績ある |
| Z3 | cross-pair shadow 妥当性は **INCONCLUSIVE** (single instrument で skipped 継続、 ii-lite 証拠欠落) |

## 矛盾・要議論

| # | 論点 | Claude | Codex | 判断 |
|---|---|---|---|---|
| M1 | T091 段階 2/3 の seed=100 効果見込み | 「変わらない見込み」 | 「INCONCLUSIVE、 断定早い」 | **Codex 採用** (段階 2 で境界個体の selection 変化は実装後に verify) |

## 統合改善提案 (優先度順)

| # | 提案 | 優先度 | 出所 | target_metric | 期待効果 | 分類 |
|---:|---|---|---|---|---|---|
| 1 | **T091 段階 2 (trade_count_full_dataset) 実装** + **median_oos_sharpe を archive 列に追加** (Layer 1 検証用) | High | TODO + Codex 推奨 | selection 圧整合化 + Layer 1 検証可能化 | 次 RUN-55 で trade_count_full_dataset / median_oos_sharpe 列が non-null、 selection ranking 変化を観察 | Structural |
| 2 | **T091 段階 3 (partition guard) 実装** + 二重 opt-in escape hatch | Medium | TODO | mission 監査性 | holdout 14d 不整合の起動時 fail-closed 検出、 smoke override で次 RUN を smoke として継続可能 | Structural |
| 3 | (Phase 2 候補) seed 多様化 RUN (seed=23/42/100 比較) | Medium | Codex Z2 | mission 到達経路の局所/全体閉塞切り分け | 反証可能性向上 | Structural |
| 4 | (Phase 2 候補) cross-pair shadow 復帰 | Medium | Codex Z3 | ii-lite 証拠 | shadow 統計 archive 記録 | Structural |

### 採用判断

- **今 cycle 採用**:
  - 提案 1: T091 段階 2 + median_oos_sharpe archive 列追加 (Layer 1 検証用)
  - 提案 2: T091 段階 3 (smoke override で次 RUN を smoke として実行可能化)
- **Phase 2 移動**: 提案 3, 4

### 次 RUN 戦略

- T091 段階 2 + 段階 3 完了後、 二重 opt-in (smoke) で run-55 を実行
- run-55 で:
  - Layer 1 検証: archive 新列 `median_oos_sharpe` (per-fold median) で g70_i9 等の値が確認可能 (run-55 archive ではなく、 run-55 で再 RUN したものの archive)
  - 注意: run-55 は seed=100 で再実行、 run-52 (seed=42) の個体は再現されない → 段階 1 効果検証は run-55 では不可
  - 段階 1 効果の真の検証には run-52 を replay する必要があり、 これは別タスク

### 次フェーズ申し送り

- Phase C (詳細設計) で段階 2 詳細設計に **median_oos_sharpe 追加 archive 列** を併設
- 段階 3 詳細設計に二重 opt-in smoke override を含める
- 既設計 (commit 4624c7a + cycle 1 統合) を流用可能、 列追加のみ追加変更
