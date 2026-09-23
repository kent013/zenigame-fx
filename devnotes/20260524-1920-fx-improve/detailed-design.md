# 詳細設計 (cycle 17): max_drawdown_max 20%→5% 厳格化 (dd 軸の閾値引き上げ)

## 決定
**dd厳格化 max_drawdown_max 0.20→0.05** を実装し、R99 (seed70) で in-loop 検証。

### 方針の根拠 (Codex (E) を user standing directive で上書き)
- Codex consensus-round-1 は (E) 「形式的引き上げを止め frontier 確定+方針転換」を推奨。
- ただし **user の North Star = 閾値引き上げのみ・緩和禁止・達成後 raise** が最優先。loop directive も「判定後…次は別品質軸(dd厳格化/sortino)」と明示 → 閾値引き上げ継続が user 意図。AskUserQuestion は user に拒否され「自律進行」を確認。
- → Codex (E) でなく、Codex が (B) で提示した dd厳格化手順を採用。dd は robustness 直結軸で、達成 dd max 2.68% に対し 5% は margin あり (緩和でなく引き上げ=厳格化)。

### Codex (B) ガイダンス遵守
- **5% 先行** (3% は達成 max 2.68% に近すぎ seed/相場耐性薄、5% 合格後に検討)。
- **post-hoc sweep 信仰の再発防止** (74k 教訓): in-loop 検証必須。同一 seed 反実仮想で判定。
- **3 seed 非崩壊を最終採用条件** (1 seed でも StageC=0 なら棄却)。

## 変更
1. `config/alpha_factory/default.yaml` max_drawdown_max 0.2→0.05。
2. `tests/scripts/test_alpha_factory_run_ga.py` に max_drawdown_max==0.05 assert 追加 (現状 assert なしなら新規)。

## R99 = R98 反実仮想 (同一 seed70、dd だけ変更)
R98 (seed70, dd20%) StageC=634 が baseline。R99 (seed70, dd5%) で dd 厳格化の in-loop 影響を単一変数で測定 (R97/R98 で有効だった反実仮想法)。

## R99 反証可能成功/失敗基準 (in-loop、post-hoc 信仰禁止)
- 成功 (dd5% in-loop 安全 = 引き上げ採用候補): StageC pass>0 ∧ mission_candidate(sharpe1.5∧pnl70k∧dd**5%**∧trade50-5000)≥10 ∧ StageC max_dd_pct≤5% (定義上自明) ∧ StageC count が R98(634)比で壊滅的減少でない (目安≥100)。
- 失敗 (dd5% in-loop 崩壊 = 74k 同型、棄却): StageC=0 or mission_candidate<10 or StageC count が R98比で激減 (funnel 崩壊兆候)。
- 採用は R99 成功後、さらに別 seed 2 本で非崩壊を確認 (運用ルール: 独立3seed)。

## R99 launch 条件
pop96/gen60/EUR_JPY/profit_safe_pfr/warmstart0.1/cross-pair-enable+selection-pressure、**seed=70** (R98と同一)、max_drawdown_max=0.05、total_pnl_min=70000 (frontier 据置)。default挙動 bit-exact 維持。cross-pair shadow 継続。
