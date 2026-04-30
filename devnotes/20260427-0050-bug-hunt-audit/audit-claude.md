# Run 20-22 バグハント監査 — 20 点疑惑リスト (Claude 一次)

**監査対象**: Run 20-22 (post Phase 0 + T034/T036/T033/T039/T040)
**動機**: Stage A pass=2750/2395/1758 で機能再開したが Stage C pass=0 継続。data 観察で **Stage B 通過 834 個体が全員 sharpe<0 / pnl<0** という致命的兆候を検出。仕組みのどこかにバグがある前提で、コードとデータに基づき網羅的監査する。
**討論方針**: 各論点に「直接証拠」「反証仮説」を併記し、Codex に独立検証させる。C9 Falsification-first。

## 致命的観察事実（決定的、Run 20 archive 由来）

```
Stage A pass: 2750 / 5856
Stage B pass: 834 / 2750
Stage B passing 個体の統計:
  trade_sharpe_raw: mean=-0.1923, max=-0.1234 (全員 NEGATIVE)
  total_pnl:        mean=-16,522, max=-10,740 (positive 0 件!)
  positive_fold_ratio_effective: mean=0.803  (fold の 80% で OOS sharpe > 0)
  n_fold_effective: median=8

Stage A 通過個体の fitness_pen:
  mean=0.067, max=0.327 (全部 positive、threshold=0.0 通過)
fitness_pen と trade_sharpe_raw の差分:
  mean=0.23 (= -α × size_norm のはずだが α=0.03 と整合しない、size_norm 負値?)

mission_score:
  n=834, std=0.0009 (834 個体すべて 0.31 付近に集中)
```

これは「Stage B median fold sharpe > 0 + positive_fold_ratio 80% でも total sharpe / pnl が negative」という構造的不整合。**OOS fold 評価と全期間集計のどちらかに bug がある。**

---

## 疑惑リスト 20 点

### A. Stage B WF / fold 計算系

**1. trade_sharpe_raw 上書き bug**
- 直接証拠: archive `collect_stage_b` で `is_full_sharpe` が `trade_sharpe_raw` 列を上書きする ([archive.py:420-432](../../src/alpha_factory/archive.py#L420-L432))
- Stage A 評価時の trade_sharpe_raw (selection 用) と archive 表示値 (=Stage B is_full_sharpe) が乖離
- fitness_pen は Stage A 値で固定だが trade_sharpe_raw は overwrite される → 表示と selection 基準のズレ
- 影響: 監査時に「fitness_pen=0.04 / sharpe=-0.19」のような矛盾表示

**2. Stage B per-fold OOS sharpe が positive bias を持つ**
- 直接証拠: positive_fold_ratio 0.80 で 80% fold が positive sharpe、median > 0 なのに total negative
- 反証仮説: 短い fold (test_days=10) で偶発的に positive、cross-fold で打ち消される統計的帰結?
- 検証: WF fold ごとの実 PnL を log するか、is_full_sharpe vs sum-of-fold-sharpe の符号比較

**3. WF fold backtest のコスト適用漏れ**
- 直接証拠: max_spread_bps=10 が Stage A/Stage C には適用されるが、Stage B WF backtest 内で同じ config が伝搬しているか未確認
- 検証: `evaluate_stage_b` 内 backtest 呼び出し path で `BacktestConfig.max_spread_bps` を log

**4. Stage B `is_full_sharpe` の定義不整合**
- 直接証拠: archive で trade_sharpe_raw に上書きされる is_full_sharpe は Stage B 全期間 (18 ヶ月) の sharpe
- Stage A 60 日 sharpe vs Stage B 18 ヶ月 sharpe で同列比較されている
- 影響: 全 Run で Stage A 通過 → Stage B 期間延長で性能落ちる構造

**5. fold sharpe annualization なしで median 比較**
- 直接証拠: stage_b_median_oos_sharpe_min=0.05 (trade-level) で T042 後校正
- 各 fold は test_days=10 = 10 日間の trade Sharpe
- 反証仮説: 10 日 trade Sharpe で median 0.05 でも、long horizon で意味なし

### B. Backtest engine / コスト系

**6. max_drawdown 0.0 多発**
- 直接証拠: Run 22 best 個体 max_drawdown_pct=0.0 with trade_count=68
- 68 trade で完全に dd=0 = 全 trade 勝ち or position size = ノミナル極小?
- 検証: equity_curve の min/max を直接見る

**7. negative equity warnings (Run 19 で 10k+ 件)**
- 直接証拠: log の `trade_return.invalid_equity_at_entry equity_at_entry=-3,082,830`
- leverage 25x + units 10000 + 短期間多取引で margin 完全壊滅
- ストップアウト logic 不在の可能性
- 検証: MockBroker.equity_at_entry を強制 plot

**8. spread/swap 適用経路の verify**
- T041 で `max_spread_bps=10` 設定したが、実際に backtest engine が適用しているか
- 検証: 1 trade ごとに spread cost を log

**9. `holding_cost_per_day_bps=0` でも何か他のコスト混入?**
- 検証: trade.pnl の構成要素を分解 (raw_pnl - cost) で出力

**10. MockBroker fill timing**
- 直接証拠: 規約は「signal at close → execute next bar open」
- DslStrategy はこれに従っているか? 実装で next-bar fill が行われているか

### C. GA / selection / fitness 系

**11. fitness_pen と trade_sharpe_raw の差分 0.23 が α=0.03 と不整合**
- 直接証拠: Stage B passing で `fitness_pen - trade_sharpe_raw = 0.23 mean`
- α × size_norm = 0.23 → size_norm = 7.7 (n_nodes mean 2.9 で size_norm=2.9 / size_ref=10 = 0.29 のはずなら、α × 0.29 = 0.0087 mismatch)
- archive 表示値の上書き ([点 1] と関連) の副作用?
- fitness_raw vs fitness_pen の符号不整合の疑い

**12. mission_score std=0.0009 (834 個体ほぼ同値)**
- 直接証拠: 834 個体中 mission_score range 0.297〜0.311 のみ
- 4 軸合算なのに識別力ほぼゼロ = bug or 構造上の収束?
- 計算検証: sharpe < 0 → score 0、pnl < 0 → score 0、dd small → score ~1, tc 充足 → score 1
- (0.1 × 0.1 × 0.94 × 1.0)^(1/4) = 0.31 で計算合致
- → bug ではない、ただ識別力が無い (Codex 監査での懸念再現)

**13. selection_score tie-break drift**
- 直接証拠: 全員 stage_a=1, stage_b=0 or 1, fitness_pen 近似値で tie 多発
- 全員同じ score なら tournament が決定論的 drift = 多様性消失

**14. elite_count=2 の同個体 retain**
- elite が同じ genome を毎世代 retain = クローン化リスク
- 検証: gen 跨ぎで elite の genome_hash 比較

**15. mutate / crossover の deep copy 漏れ**
- 直接証拠: SignalConfig は frozen + MappingProxyType で deep immutable (T029)
- ただし list/tuple of SignalConfig 操作で参照共有してないか

### D. Primitive / data / aux 系

**16. pair_specific が EUR_JPY Run で 45-48% pass する症状**
- 直接証拠: P9 (USD_CAD), P4 (USD_JPY) が EUR_JPY Run で pass 率 45-48%
- aux_pair_bars 不在で safe default を返しているはずが、定数信号として GA に活用されている
- 反証仮説: safe default が 0.0 なら多様性に影響しない、bug ではない

**17. F6 SessionMomentum の集中過剰**
- 直接証拠: Run 22 で directional 14k 中 F6=4916 (34%)
- 反証仮説: Stage A pass 35-65% で実際機能している
- ただ winner-take-all で他 primitive 機会消失

**18. P10 NADataProximityGate strict_aux でない無条件 pass**
- 直接証拠: pair_specific.py:716 で `event_snapshot is None` なら 1.0 安全 default
- T039 で as_of_strict 厳密化したが、現状 production loader 不在で常に gate 開放
- 効果測定不能のまま GA selection に組み込まれている

### E. Stage A/C / live_criteria 系

**19. Stage C base_sharpe の annualization が二重?**
- T042 で Stage C lc.sharpe を annualized 比較に変更
- mission_score の sharpe 軸も annualized (T042 + T043 連携)
- 両方で `stage_c_holdout_days=60` を使う際、二重年率化 / window 重複の疑い
- 検証: stage_gate.py の base_sharpe_annualized 計算

**20. calibrate-gate の monotone tighten + 観察対象縮小**
- 直接証拠: Run 20 (threshold=0.0) → 21 (0.078) → 22 (0.178) で連続 tighten
- Stage A pass 数 2750 → 2395 → 1758 で計算可能個体減少
- T040 drift CLI の `monotone_tighten` ルールが発火する状態
- selection 圧の崩壊サイクルに入っている可能性

---

## Codex への依頼

各点について以下を独立検証してほしい:

1. **直接証拠の verify**: コード行番号 / 観察データを Read で検証
2. **bug claim の妥当性**: confirmed / partially_confirmed / rejected / inconclusive
3. **緊急度**: P1 (使命達成阻害) / P2 (観測歪み) / P3 (cosmetic)
4. **修正方針の最小案**: 1 行修正 / 関数書き換え / 設計レベル

特に重点:
- **点 1, 2, 4**: Stage B 通過個体の sharpe<0/pnl<0 構造的不整合の根因
- **点 3, 8, 9, 10**: backtest engine のコスト適用 / fill 経路に bug がないか
- **点 11**: fitness_pen と trade_sharpe_raw の差分 0.23 の説明

Codex の見落としがありそうな観点 (追加 21 点目以降) も歓迎。

discipline:
- C1 Design-first: docs / devnotes / git log を grep より先に読む
- C2 「X が無い = バグ」禁止: 別経路での計算を grep で広く探す
- C6 Fact-Interp 分離
- C7 Sample size: n=834 は十分大きい、n=20 程度なら因果断定避ける
- C8 INCONCLUSIVE 第一級
- C9 Falsification-first: 各 hypothesis の反証を先に探す
