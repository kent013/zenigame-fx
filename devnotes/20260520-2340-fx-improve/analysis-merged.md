# マージ分析: Run 82 (run_20260514_211202)

## 合意事項（両者一致）
- Stage A=2687 / B=941（record 高）/ C=0 / graduated=0。mission 未達。
- sharpe(annualized 2.276)は live 閾値を越えた（cycle 23 修正の効果）。**新たな壁は total_pnl(4670<50000) と trade_count(23<50)**。
- best fitness_pen 個体 g53_i19 は Stage B 不通過（高 fitness と gate 通過が乖離）。
- 禁止事項 6（取引回数削減で sharpe 稼ぎ）の過選択兆候: live 候補が trade_count 23 と低い。live_criteria の trade_count 下限 50 が正しく弾いている。

## 検証で確定した訂正（Codex Critical → Claude 撤回）
- **profit_safe_pfr gate は設計通り動作**。B 通過 941 個体の median_oos_total_pnl（中央値 1280）・sum_oos_total_pnl（中央値 18250）は全件 >=0。違反ゼロ。
- 当初 Claude が見た「total_pnl 中央値 -1950」は **Stage C holdout 窓（連続 60日 + spread×1.5 stress）の PnL** であり、Stage B 判定に使う fold-CV OOS 指標とはスコープが別物。Codex 仮説 B が正解。

## 真のボトルネック（合意・再定義）
**Stage B（dataset 全域の fold-CV OOS）では黒字・頑健なのに、Stage C（連続 60日 holdout 窓 + spread×1.5 stress）では全 941 件が赤字/低頻度で全滅。**

補強事実:
- B 通過群 trade_count: full_dataset 192 / stage_b 142 → **holdout 34**（短窓で取引機会激減）。
- holdout は dataset 末尾（直近）60日 → 「過去 fold で選抜 → 直近窓で失敗」= 温度差/regime drift + cost stress の複合。
- Stage C は全 B-pass を無 cap 評価（swim_lane.py:665-694）→ C=0 は「選抜の偏り」ではなく「誰も通らない」問題。

## Claude 独自の発見
- genome が浅い（n_nodes median 3、active_clause<=2）。primitive P7/P2 がほぼ全個体に出現（同型解大量生成の疑い）。
- T100（Stage C stratified allocation）は **design-stale**: Stage C に選定 cap が無いため層別化対象が存在しない。→ REJECT。

## Codex 独自の発見
- 仮説 D: 低取引 sharpe 偏重（過選択）の因果確定には trade_count×sharpe の分位比較が必要。
- 仮説 E: P7/P2 偏在 + genome 浅さ → 探索の実効多様性不足。
- 全体判定 CRITICAL_DRIFT（Stage B 増が C/mission に全く接続していない目的整合性の崩れ）。

## 矛盾・要議論
- 改善方向: (a) Stage C 評価集団の質改善（T100 系）は **無効と判明**。 (b) Stage B→C 汎化を予測する選択圧の付与 が残る主路線。
- どの構造レバーを引くか（cost stress の前倒し / recency-aware fold / holdout 整合の selection 項）は Codex 合議で 1 つに収束させる。

## 統合改善提案（優先度順、Codex 合議で確定）
| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | 期待効果 |
|---|------|--------|------|--------------|-------------|---------|
| P1 | Stage B→C 汎化ギャップに対する **1 つの最小構造変更**（候補: ①Stage B に cost stress 前倒し ②直近期間整合の selection 項 ③holdout 整合 diagnostic）を Codex 合議で 1 つに収束 | Critical | Claude+Codex | Total PnL / Trade Count（C>0） | B 941 通過も C=0、holdout で全滅 | holdout で黒字・十分頻度の個体が Stage C を通過する |
| P2 | （保留）genome 浅さ・primitive 偏在の実効多様性監視 | Warning | Codex | 探索多様性 | P7/P2 偏在・n_nodes med3 | 同型解集中の緩和 |

## 次フェーズへの申し送り
- cycle_focus = `ga_improvements`（T100 は design-stale で REJECT、他 standalone は高リスク/低関連）。
- Codex 合議（B-2）で P1 を「1 つの反証可能仮説 + 1 つの最小変更」に収束させ、低リスク（loop 停止回避）を最優先する。
