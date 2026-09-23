# 最終改善計画: Run 82 → Run 83

## 合議ステータス: CONSENSUS REACHED (consensus Round 1)

## 背景（確定事実）
- Run 82: Stage A=2687 / B=941（record 高）/ C=0 / graduated=0。mission 未達。
- profit_safe_pfr gate は設計通り動作（B 通過群の median/sum_oos_total_pnl は全件 >=0）。
- 真のボトルネック: **Stage B（dataset 全域 fold-CV OOS、cost stress なし）→ Stage C（直近 60日 holdout 窓 + spread×1.5 stress）の汎化ギャップ**。全 941 件が Stage C で全滅。
- Stage C は全 B-pass を無 cap 評価（swim_lane.py:665-694）→ T100（stratified allocation）は design-stale で REJECT。

## 確定施策一覧
| # | 施策名 | 内容 | 変更対象 | 優先度 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion | 合議結果 |
|---|--------|------|---------|--------|---------|--------------|-------------|------------|---------------|-------------------|---------|
| C1 | Stage B→C gap diagnostic v1 | Stage C 評価時の base live_criteria 失敗の組合せを固定コードで分類（`pass`/`pnl_only`/`count_only`/`both_pnl_count`/`sharpe_involved`/`mixed`/`stress_or_other`/`system_fail`）し、stress 1.0→1.5 の PnL 劣化量と base/stress trade_count を **diagnostics sidecar** に永続化。**gate 閾値・GA 探索空間・fitness は一切変更しない** | `diagnostics_collector.py`, `diagnostics_sidecar.py`, `swim_lane.py`（record_stage_c 呼出 2 箇所） | Critical | Structural（観測機構の追加、行動変更なし） | Run82 で Stage C=0、holdout で trade_count が 50 未満へ崩れる頻度不足が疑われるが因果未分解 | Stage C 評価時に既に計算済みの live_criteria_pass / stress.pnl_degradation / base・stress trade_count を per-individual sidecar に記録 → 次サイクルで「C 全滅の主因が count 不足か / pnl 不足か / cost stress 由来か」を機械的に集計可能にする | sidecar に gap_class 列が出力されず、または全件 null で主因分離が不能 | 次 Run R83 で sidecar に gap_class が全 Stage-C 評価個体ぶん出力され、主因比率（count_only / pnl_only / both）が集計できる | APPROVED |

## 反証可能仮説（次 Run で検証）
**H83**: Run82 の Stage C 全滅の主因は「短窓 60日 × spread1.5 で trade_count が 50 未満へ崩れる頻度不足（count 系）」であり、純粋な cost 耐性不足（stress PnL 劣化）は二次要因。
→ R83 の diagnostic 集計で `count_only` + `both_pnl_count` の比率が支配的なら H83 支持。`pnl_only` が支配的なら H83 棄却（cost/収益性が主因）。

## 却下された提案
| # | 提案 | 却下理由 |
|---|------|---------|
| T100 | Stage C stratified allocation | design-stale: Stage C に選定 cap が無く層別化対象が存在しない（swim_lane.py:665-694） |
| ② | 直近整合 selection 項の先行投入 | Codex REJECT: drift と cost/frequency の寄与分解が未確定。診断（C1）で drift 優位が確認されるまで保留 |
| ① | Stage B fold-CV への cost stress 前倒し | Codex MODIFY/保留: 診断で cost 由来が主因と確認されてから hard/soft を決める。先行導入は Stage B pass 激減・variance 増のリスク |

## 保留事項（次 Run 検証申し送り）
| # | 仮説 | 最小変更案 | 検証条件 |
|---|------|----------|---------|
| 1 | C 全滅は cost stress 由来（H83 の対立仮説） | Stage B に cost stress 前倒し（①） | R83 diagnostic で stress_pnl_degradation が大きく pnl_only 支配的なら① を次サイクルで設計 |
| 2 | C 全滅は regime drift 由来 | 直近整合 selection 項（②） | R83 diagnostic で count/pnl 単独で説明できず drift 痕跡があれば② を次サイクルで設計 |

## 次フェーズへの申し送り
- cycle_focus = `ga_improvements`（TODO 由来なし、diagnostic 追加のみ）。
- C1 は観測機構の純粋追加。GA hot path の挙動・gate・fitness は不変（行動変更なし → 理想的には smoke で sidecar 列の存在のみ確認すればよい）。
- 使命・禁止事項チェック: C1 は live_criteria 緩和・期間延長・取引回数削減・見かけ改善のいずれにも該当しない（観測のみ）。✅
