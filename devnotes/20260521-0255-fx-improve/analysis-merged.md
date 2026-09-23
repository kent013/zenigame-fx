# マージ分析: Run 83 (run_20260520_152204)

## 合意事項（Claude + Codex 一致）
- **mission 達成**: best g51_i71 が live_criteria 4/4 達成。Stage C 通過 43 個体すべて total_pnl≥50k・trade_count≥50（mission_score 0.97+）。North Star 到達。
- ただし **3 点が未充足**で「達成は前進だが頑健性は未確認」（Claude=OK要追検証 / Codex=CONCERN）:
  1. **再現性**: 単一 seed=68・単一ペア EUR_JPY・実質 ~6 genotype（P7+P9+F4+P11 モチーフ 1 ファミリー）への収束。前ループで profit_safe_pfr の seed variance 極端（Run75 lucky 前例）。
  2. **graduation=0 の構造**: ii_lite_pass が全 5856 個体 None（cross-pair ii-lite は shadow-only、gate 未配線）。graduation 構造的に発火不能。
  3. **stress 機構の無効性**: stress_pnl_degradation が全 436 個体 0。
- B→C gap 主因は **profit magnitude**（pnl_only 162 は count 十分だが pnl 18k-50k で 50k に near-miss）、cost は非要因。

## 確定した整合性問題（Claude 検証 + Codex 仮説C 一致）
**Stage C の「spread×1.5 stress」は cost robustness を検証していない。**
- `max_spread_bps` は `set_spread_filter`（broker が spread>閾値 の trade を skip する**フィルタ閾値**）であり、per-trade コストではない（src/broker/mock.py:165-195, src/backtest/engine.py:169）。
- spread×1.5 stress は**フィルタを緩める**だけ（より高 spread の trade を通す）でコストを増やさない → 境界付近に trade がなければ degradation=0。
- 結果、436 個体全件 degradation=0。「stress」という名前が果たすべき役割（高コスト環境でのロバスト性検証）を果たしていない（思考原則: 機能の名前に立ち返れ）。
- 含意: mission 達成個体の「cost robustness」は実質未検証。

## Claude 独自の発見
- 43 C-pass は gen43-60 持続だが unique fitness_pen 7 / distinct primitive-set 6 → 低 genotype 多様性。
- pnl_only 162 は near-miss（median 36k = 目標 72%）、同モチーフの pnl scaling 余地。

## Codex 独自の発見
- 仮説B 検証法: ii-lite を gate 入力として計算可能化 → 段階昇格（いきなり全面 hard でなく「計測可能化→部分 hard」）。
- 仮説C: 436 全件 0 は不自然 → stress 機構不全の可能性高い（Claude が filter/cost 取り違えと確認）。
- 「次水準」は再現性条件（複数 seed×複数 pair）を先に追加 → その後 pnl_min/sharpe_min を段階引き上げ（緩和禁止）。

## 矛盾・要議論
- 優先順位: (a) 再現性検証（seed 変更、ゼロコード risk）と (b) stress 機構修正（整合性問題、中 risk）のどちらを cycle 2 に。
  - (a) は「達成が seed-lucky か」を最速で判定。(b) は「達成個体が真に cost-robust か」を検証可能にする。
  - mission 達成済のため、North Star「達成後は robustness 確認後に閾値引き上げ」に従い再現性が先。だが stress 無効は達成の妥当性そのものに関わる。

## 統合改善提案（優先度順、Codex 合議で確定）
| # | 提案 | 優先度 | 出所 | 変更分類 | target_metric | 期待効果 |
|---|------|--------|------|---------|--------------|---------|
| P1 | 再現性検証: 別 seed で R84 を回し mission 再現率と genotype 多様性を観測（コード変更なし or 最小） | Critical | 両者 | 観測 | 全 live_criteria | 達成が seed-lucky か頑健かを判定。閾値引き上げ前の必須ゲート |
| P2 | stress 機構の cost-robustness 化（spread filter 緩和でなく per-trade コスト割増 stress を導入、または stress を診断計測可能化） | High | 両者(整合性) | Structural | 全 live_criteria の妥当性 | mission 個体の真の cost robustness 検証 |
| P3 | cross-pair ii-lite の計測可能化→段階 gate 昇格 | Warning | Codex | Structural | cross-pair / graduation | graduation を真の多ペア汎化ゲートに |

## 次フェーズへの申し送り
- cycle_focus = `ga_improvements`（T100 design-stale 既知、他 standalone は本 Run ボトルネックと非整合）。
- Codex 合議で P1/P2/P3 を「1 反証可能仮説 + 1 最小変更」に収束。低リスク（loop 停止回避）最優先。
