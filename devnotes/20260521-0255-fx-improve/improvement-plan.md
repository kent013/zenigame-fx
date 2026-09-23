# 最終改善計画: Run 83 → Run 84

## 合議ステータス: CONSENSUS REACHED (consensus Round 1)

## 背景
Run 83 で mission 達成（live_criteria 全達成個体 43）。ただし両分析一致で 3 点未充足（再現性 / graduation gap / stress 無効）+ 整合性問題（spread stress が cost robustness を検証していない）。North Star は「達成後は robustness 確認後に閾値引き上げ（緩和禁止）」。

## 確定施策（R84）
| # | 施策 | 内容 | 変更対象 | 優先度 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion | 合議 |
|---|------|------|---------|--------|---------|--------------|-------------|------------|---------------|-------------------|------|
| R84-1 | 再現性検証（seed perturbation only） | seed=68→69 のみ変更し他パラメータ・ロジック完全不変で R84 実行。mission 再現率・genotype 多様性を観測 | run_args のみ（**コード変更なし**） | Critical | Structural（評価プロトコル強化、GA値最適化ではない） | mission_count / genotype_family_count | Run83 が lucky seed 依存で次 run で mission 消失 | seed のみ変えて同一設定を再実行し seed 感度を直接観測 | 別 seed で mission=0 かつ多様性増えずなら「seed-lucky」仮説を支持（=達成は脆弱） | 別 seed run で mission 個体≥1 再出現（達成が seed 非依存と判定） | APPROVED |

## 反証可能仮説（R84 で検証）
**H84**: Run83 の mission 達成は lucky seed ではなく、同一設定で seed を変えても mission 個体は再出現する。
- 成功（事前固定）: mission 個体 ≥1。
- 失敗（事前固定）: mission 個体 =0 → cycle 3 で P2（stress cost-robustness 化）を最優先実装。

## キュー化（cycle 3 の確定 Structural 施策）
| # | 施策 | 理由 | 分類 |
|---|------|------|------|
| P2 | **stress の cost-robustness 化** | Stage C の spread×1.5 stress は max_spread_bps（spread フィルタ閾値、broker が spread>閾値 の trade を skip）を緩めるだけで per-trade コストを増やさない（src/broker/mock.py, src/backtest/engine.py:169）。stress_pnl_degradation 全 436 個体 0 = cost robustness 未検証。per-trade コスト割増 stress を導入し「stress」を名前通りの機能にする | Structural（整合性修正） |
| P3 | cross-pair ii-lite 計測可能化→段階 gate 昇格 | graduation=0 は ii_lite_pass=None の構造。計測可能化→部分 hard 昇格で graduation を真の多ペア汎化ゲートに | Structural（配線、中-大 risk） |

## 却下された提案（R84 では）
| # | 提案 | 却下理由 |
|---|------|---------|
| P2 (R84 即実装) | stress cost-robustness 化を R84 で | コード変更を伴う修正は R84 では入れず、cycle 3 先頭の Structural 修正としてキュー化（loop 停止リスク回避、再現性検証を先に） |
| P3 | cross-pair gate 昇格 | 実装面積大・loop 停止リスク。R84 の「低リスク最小変更」方針に不適合 |
| T100 | Stage C stratified allocation | design-stale（cycle 1 で確認、Stage C 無 cap 評価で層別化対象なし） |

## 使命・禁止事項チェック
R84-1 は seed のみ変更（コード・閾値・gate 不変）。閾値緩和・期間延長・取引回数削減・見かけ改善のいずれにも該当しない。✅

## 次フェーズへの申し送り
- cycle_focus = `ga_improvements`（reproducibility_validation_only、seed perturbation only）。
- **Phase 3 (implement) はスキップ**（コード変更なし、selected_todos=[]）。
- Phase 4: R84 を `--seed 69`（他は R83 と同一: EUR_JPY / pop96 / gen60 / mutation 0.5 / max-workers 2 / profit_safe_pfr）で実行。
- detailed-design.md は「コード変更なし」の宣言のみ（実装対象なし）。
