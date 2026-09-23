# 概念設計: Stage B→C gap diagnostic v1 (C1)

## 背景
Run 82 で Stage A=2687 / B=941（ループ累積 record 高）/ C=0 / graduated=0。mission 未達。
検証の結果、profit_safe_pfr gate は設計通り動作している（Stage B 通過 941 個体の median_oos_total_pnl・sum_oos_total_pnl は全件 >=0）。当初疑った「gate が赤字個体を通過させている」は誤りだった。

真のボトルネックは **Stage B（dataset 全域の fold-CV OOS、cost stress なし）では黒字・頑健なのに、Stage C（dataset 末尾=直近の連続 60日 holdout 窓 + spread×1.5 stress）では全 941 件が赤字/低頻度で全滅** という汎化ギャップ。
- B 通過群 trade_count: full_dataset 192 / stage_b 142 → holdout では 34（短窓で取引機会激減）。
- Stage C は全 B-pass を無 cap 評価（swim_lane.py:665-694）→ C=0 は「選抜の偏り」ではなく「誰も通らない」問題。

## 目的
C 全滅の主因を機械的に分解する観測機構を追加する。次サイクルで「count 不足 / pnl 不足 / cost stress 由来 / regime drift」のどれが支配的かを判定し、因果に基づいて次の構造施策（cost stress 前倒し or 直近整合 selection）を選択できるようにする。

**仕組みが機能していない段階で値を弄らない**という原則に従い、まず観測機構を入れて因果を確定させる。本サイクルでは gate 閾値・GA 探索空間・fitness を一切変更しない。

## 反証可能仮説（H83）
Stage C 全滅の主因は「短窓 60日 × spread1.5 で trade_count が 50 未満へ崩れる頻度不足（count 系）」であり、cost 耐性不足（stress PnL 劣化）は二次要因。
→ R83 diagnostic で `count_only` + `both_pnl_count` 比率が支配的なら H83 支持。`pnl_only` 支配的なら棄却（cost/収益性が主因）。

## スコープ
- Stage C 評価時に既に計算済みの `live_criteria_pass` / `stress.pnl_degradation` / base・stress `trade_count` を per-individual の diagnostics sidecar に永続化する。
- gap_class（固定 enum）で base live_criteria 失敗の組合せを分類。
- 新規 backtest 実行なし。観測専用・fail-soft。

## 非目的
- gate 閾値・fitness・GA 探索空間の変更（行動変更は次サイクル以降、診断結果に基づく）。
- main archive Parquet のスキーマ変更（sidecar に限定）。

## 期待効果
- 次サイクルで C 全滅の主因が機械集計可能になり、構造施策選択の因果根拠が得られる。

## 使命・禁止事項整合
観測のみの追加。live_criteria 緩和・期間延長・取引回数削減・見かけ改善・オーバーナイトのいずれにも該当しない。

## 詳細設計
`detailed-design.md` 参照（Codex design-review APPROVED, Round 2）。
