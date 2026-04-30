# Run 20-22 バグハント — Codex 独立検証

## 0. 本検証の前提 (C4)
- verified: `reports/run-reports/run-20/history.json` の `stage_b_pass` 合計を python で算出し 834 を再現済み（sum 関数のみ利用）。
- verified: Stage B 用 bars は `dataset.start <= bar_time < dataset.end` を満たし、Stage A はその末尾 60 日をスライスして生成（`scripts/alpha_factory/run_ga.py:344-395`）。
- verified: Stage B 各 fold で `DslStrategy` と `MockBroker` を毎回新規作成して state leak を防止（`src/alpha_factory/stage_gate.py:529-533`）。
- verified: Walk-Forward 判定は `median_oos_sharpe` と `positive_fold_ratio` のみを閾値チェックし、IS モニタ値は payload 記録のみ（`src/alpha_factory/stage_gate.py:583-592,607-617`）。
- verified: BacktestConfig は `max_spread_bps=10` と `holding_cost_per_day_bps=0` を共有（`config/alpha_factory/default.yaml:14-32`）し、`run_backtest` が spread filter を適用（`src/backtest/engine.py:117-138`）。
- unverified: `.cache/alpha_factory/runs/genomes_run_20260426_145502.parquet` は `pyarrow` 未導入かつ書込み禁止 sandbox のため読取不可（環境制約で検証不能）。

## 1. 致命的観察事実 (Sec 致命的観察) の独立検証
事実: history 集計で Stage B 通過個体総数 834 を確認。best 個体（`summary.json`）は `stage_b_pass=true` で `total_pnl=-16850`／`sharpe=-0.189` を保持。  
解釈: Stage B 通過群全員が負利益かどうかは Parquet を直接読めず INCONCLUSIVE。ただし Stage B で `trade_sharpe_raw` が IS 値に上書きされる実装（`src/alpha_factory/archive.py:452-457`）を確認し、表示上の Sharpe/PnL 乖離はこの上書きが主要因。Stage B OOS 判定そのものは fold Sharpe 集計で行われており（`src/alpha_factory/stage_gate.py:583-592`）、全員負利益であれば別途データ確認が必要。

## 2. 20 点疑惑リストへの個別判定
(1) trade_sharpe_raw 上書き  
- 直接証拠: `src/alpha_factory/archive.py:452-457`, `src/alpha_factory/stage_gate.py:607-617`  
- 検証結果: confirmed  
- 緊急度: P2  
- bug claim の力: strong（実装で明示的に上書き）  
- 最小修正方針: 列追加（Stage B IS 指標を専用列に保持し `trade_sharpe_raw` は Stage A 値を維持）

(2) Stage B OOS Sharpe positive bias  
- 直接証拠: `scripts/alpha_factory/run_ga.py:344-399`, `src/alpha_factory/stage_gate.py:583-592`  
- 検証結果: rejected（train+test 分割と閾値チェックは仕様通り）  
- 緊急度: P3  
- bug claim の力: weak（設計通りの挙動）  
- 最小修正方針: なし

(3) WF fold でコスト未適用  
- 直接証拠: `src/alpha_factory/stage_gate.py:532-535`, `src/backtest/engine.py:117-138`, `src/broker/mock.py:180-224`  
- 検証結果: rejected  
- 緊急度: P3  
- bug claim の力: weak  
- 最小修正方針: なし

(4) Stage B is_full_sharpe の表示混乱  
- 直接証拠: `src/alpha_factory/stage_gate.py:607-617`, `src/alpha_factory/archive.py:452-460`  
- 検証結果: partially_confirmed（記録先名称が誤解を誘発）  
- 緊急度: P2  
- bug claim の力: medium  
- 最小修正方針: 関数書き換え（IS モニタ値を `is_full_*` 列として別保存／レポート側で名称修正）

(5) fold Sharpe を年率換算せず比較  
- 直接証拠: `config/alpha_factory/default.yaml:114-122`  
- 検証結果: rejected（trade-level スケールで統一という仕様）  
- 緊急度: P3  
- bug claim の力: weak  
- 最小修正方針: なし

(6) max_drawdown=0 多発  
- 直接証拠: `src/backtest/metrics.py:133-144`  
- 検証結果: inconclusive（データ欠如で再現不可）  
- 緊急度: P2  
- bug claim の力: inconclusive  
- 最小修正方針: 再現用 equity curve を抽出して検証

(7) negative equity warnings  
- 直接証拠: `src/backtest/metrics.py:67-90`, `src/broker/mock.py:199-224`  
- 検証結果: inconclusive（実行ログ未確認）  
- 緊急度: P1（発生していれば致命的）  
- bug claim の力: inconclusive  
- 最小修正方針: ログ抽出と trade dump で equity_at_entry を要確認

(8) spread/swap 適用漏れ  
- 直接証拠: 同 (3)  
- 検証結果: rejected  
- 緊急度: P3  
- bug claim の力: weak  
- 最小修正方針: なし

(9) holding_cost=0 でも別コスト混入  
- 直接証拠: `config/alpha_factory/default.yaml:28-32`, `src/broker/mock.py:237-280,351-356`  
- 検証結果: rejected  
- 緊急度: P3  
- bug claim の力: weak  
- 最小修正方針: なし

(10) MockBroker fill timing 不整合  
- 直接証拠: `src/backtest/engine.py:123-166`, `src/broker/mock.py:199-223`  
- 検証結果: rejected  
- 緊急度: P3  
- bug claim の力: weak  
- 最小修正方針: なし

(11) fitness_pen と trade_sharpe_raw 差分 0.23  
- 直接証拠: `src/alpha_factory/stage_gate.py:421-442`, `src/alpha_factory/archive.py:452-460`  
- 検証結果: confirmed（Stage B 上書きが原因）  
- 緊急度: P2  
- bug claim の力: strong  
- 最小修正方針: (1) と同一

(12) mission_score の集中  
- 直接証拠: `src/alpha_factory/stage_gate.py:681-705`  
- 検証結果: rejected（設計上、全軸ゼロ付近なら 0.31 付近に集まる）  
- 緊急度: P3  
- bug claim の力: weak  
- 最小修正方針: なし

(13) selection_score tie drift  
- 直接証拠: `scripts/alpha_factory/run_ga.py:230-276`  
- 検証結果: inconclusive（均一 fitness の頻度未解析）  
- 緊急度: P2  
- bug claim の力: weak（tie 時は安定 sort）  
- 最小修正方針: 世代ログから重複ケース調査

(14) elite_count=2 のクローン化  
- 直接証拠: `scripts/alpha_factory/run_ga.py:470-509`  
- 検証結果: rejected（GA 一般の elite 戦略）  
- 緊急度: P3  
- bug claim の力: weak  
- 最小修正方針: なし

(15) mutate/crossover で deep copy 漏れ  
- 直接証拠: `src/ga/operators.py:84-160`（`replace` + tuple）  
- 検証結果: rejected  
- 緊急度: P3  
- bug claim の力: weak  
- 最小修正方針: なし

(16) pair_specific safe default が定数化  
- 直接証拠: `src/alpha_factory/primitives/pair_specific.py:120-149,669-725`  
- 検証結果: partially_confirmed（データ欠如時に 0 or 1 を返し GA が実質一定値を利用）  
- 緊急度: P2  
- bug claim の力: medium  
- 最小修正方針: strict_aux 必須化 or Stage A で fail-fast させる

(17) F6 SessionMomentum 過集中  
- 直接証拠: なし（データ未取得）  
- 検証結果: inconclusive  
- 緊急度: P2  
- bug claim の力: inconclusive  
- 最小修正方針: archive 集計が必要

(18) P10 NADataProximityGate 常時 open  
- 直接証拠: `src/alpha_factory/primitives/pair_specific.py:719-742`  
- 検証結果: confirmed（イベント欠如時に 1.0 を返す）  
- 緊急度: P2  
- bug claim の力: strong  
- 最小修正方針: strict snapshot を default にするか、欠如時は fail させる

(19) Stage C Sharpe 年率換算の二重適用  
- 直接証拠: `src/alpha_factory/stage_gate.py:808-1004`  
- 検証結果: rejected（trade-level と annualized を別 key で保持）  
- 緊急度: P3  
- bug claim の力: weak  
- 最小修正方針: なし

(20) calibrate-gate monotone tighten  
- 直接証拠: `src/alpha_factory/calibrate_gate.py:550-576`  
- 検証結果: inconclusive（実行ログ未確認）  
- 緊急度: P2  
- bug claim の力: inconclusive  
- 最小修正方針: Run 20-22 の calibrate 出力比較が必要

## 3. Claude が見落とした論点 (21 点目以降)
### 確認済み
- DslStrategy ヒステリシスは long/short 対称条件で実装され、短期バイアスなし（`src/dsl/strategy.py:342-352`）。
- trade_sharpe_raw は net pnl / equity_at_entry ベースのトレードリターンを用い、Equity リターンとは独立（`src/backtest/metrics.py:67-114`）。
- Stage B fold ごとに `DslStrategy`・`MockBroker` を再生成し state leak を阻止（`src/alpha_factory/stage_gate.py:529-533`）。
- Stage A 60 日窓は Stage B bars の末尾から抽出し look-ahead を防止（`scripts/alpha_factory/run_ga.py:392-395`）。
- archive flush 時に `_MAX_STAGE_KEY` は明示的に除去され Parquet に出力されない（`src/alpha_factory/archive.py:565-576`）。

### 追跡継続推奨
- Stage A `run_backtest` から得る `trades` は `_trades.append` 順に保存され時系列順と推定されるが、データ確認までは保証できず。
- `Genome.clauses` は tuple で固定化され、max_clause=1 でも iterable を維持（`src/dsl/genome.py:47-77`）。
- `_breed_next_gen` は `provenance` に parent_a/b を必ず記録（`scripts/alpha_factory/run_ga.py:480-507`）。
- `random_signal_config` は `SignalConfig` を毎回新規生成し params の共有は MappingProxyType で防御（`src/ga/random_gen.py:84-111`）。

## 4. 最重要修正 P1 / P2 まとめ
- Stage B/Stage A 指標混線（疑惑 1, 4, 11）は GA 選抜と診断を混乱させるため、Stage B の IS モニタを別列に切り出す修正が必要。
- pair_specific/P10 の safe default が常時 0/1 を返すため、実データ欠如時でも Stage A を通過しうる。strict_aux を標準化して欠測を Fail にすべき。
- Stage B pass 群の PnL/Sharpe 確認は Parquet 読取環境の復旧後に再検証が必要（現在 INCONCLUSIVE）。

## 5. Verdict
全体: SUSPICIOUS（観測系バグが複数 P2 レベルで成立し、根因特定の追加データ取得が必要）。  
各点: confirmed=3, partially_confirmed=2, rejected=9, inconclusive=6。  
不確定領域: max_drawdown 0 問題、negative equity 警告、F6 集中、calibrate tighten、Stage B 通過群の PnL/Sharpe 実測はデータ不足のため再調査が必要。