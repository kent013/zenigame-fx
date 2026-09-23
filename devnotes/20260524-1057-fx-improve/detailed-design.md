# 詳細設計 (cycle 16): R98 = 70k+seed70 反実仮想で閾値因果を切り分け

## 決定 (Codex consensus-round-1)
次手は **B: total_pnl_min を 74000→70000 に戻し、seed70 固定で R98 を実行**。同一 seed で 74k→70k の反実仮想を取り、**閾値効果を直接同定** (案A 74k+seed71 は seed と gate が同時変化で解像度低)。

## 位置づけ
これは「正式 revert」ではなく **診断 run**。R97 (74k,seed70) StageC=0 の原因が gate(74k過大) か seed(seed70分散) かを切り分ける。
- R98 (70k,seed70) で StageC>0 回復 → 原因は 74k (gate効果) → 70k を last validated frontier として正式採用、74k 棄却 (cycle13 trade_count precedent、緩和でなく未検証引き上げの撤退)。
- R98 (70k,seed70) でも StageC=0 継続 → 原因は seed70 (seed分散) → 70k は無罪、74k へ戻し別seedで再挑戦。

## 変更
1. `config/alpha_factory/default.yaml` total_pnl_min 74000→70000 (診断、cycle16)。
2. `tests/scripts/test_alpha_factory_run_ga.py` assert 70000。

## R98 反証可能基準 (Codex 提示)
config: R97から total_pnl_min だけ 74000→70000、seed=70 固定。
- 成功 (仮説「74k過大」支持): StageC_pass>0 ∧ mission_candidate≥10 ∧ holdout total_pnl median が R97(33020)比で明確回復 (目安≥45k)。
- 失敗 (仮説棄却=seed70異常): StageC_pass=0 ∧ mission_candidate<10 継続。

## 運用ルール追記 (Codex 推奨)
「閾値引き上げの正式採用は独立2seed以上で mission_candidate>0 再現を要件とする」。→ 74k は R97 (seed70) 1本で StageC=0、未検証。70k は R95/R96 2seed再現済 = validated。

## R98 launch 条件
pop96/gen60/EUR_JPY/profit_safe_pfr/warmstart0.1/cross-pair-enable+selection-pressure、**seed=70 固定** (R97と同一)、total_pnl_min=70000。default挙動 bit-exact 維持。cross-pair shadow 継続。
