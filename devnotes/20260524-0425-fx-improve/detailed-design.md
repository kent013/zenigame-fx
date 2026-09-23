# 詳細設計 (cycle 15): total_pnl_min 70000→74000 引き上げ

## 決定 (Codex 合議 consensus-round-1: 条件付きOK)
`config/alpha_factory/default.yaml` の `live_criteria.total_pnl_min` を **70000→74000** に引き上げる。他の閾値・config は固定。

## 根拠
- R95/R96 両 seed で North Star 閾値引き上げ (pnl70k) 再現確認済 (cycle14)。
- 引き上げ幅は**弱 seed (R96, max80520) 律速**。82k 以上は R96=0 で再現崩壊 → 不可。
- 74000 = 両 seed で mission_candidate≥10 (Codex 条件3) を保つ**最大値** (R95=57, R96=12)。75k は R96=8 で条件3 を割る。
- Codex: 「72k は安全マージン +2 増えるだけで引き上げ圧を弱める効果の方が大きい」→ 74k 推奨。
- 禁止事項抵触なし (閾値引き上げのみ、取引数操作・期間延長・overnight・default挙動変更に該当せず)。メタ過学習は「R97条件事前固定 + 次seed再検証」で管理。

## 変更
1. `config/alpha_factory/default.yaml:102` total_pnl_min 70000→74000。
2. `tests/scripts/test_alpha_factory_run_ga.py:262` assert 74000。

## R97 反証可能成功基準 (Codex 提示 5 条件)
1. Config固定: 変更は total_pnl_min=74000 のみ。
2. Stage C有効性: stage_c_pass_count > 0。
3. North Star実用性: mission_candidate_count(新基準 sharpe1.5∧pnl74k∧dd20∧trade50-5000) ≥ 10。
4. 高取引数tail再出現: Stage B trade_count≥100 が ≥1 (補助指標)。
5. 独立seed再現: R97達成後、別seed R98 でも mission_candidate_count > 0 (同一閾値74000)。

## R97 launch 条件
pop96/gen60/EUR_JPY/profit_safe_pfr/warmstart0.1/cross-pair-enable+selection-pressure。**新 seed (R95/R96 と独立)** で launch。default挙動 bit-exact 維持 (feature opt-in)。cross-pair は shadow 観測継続。
