**判定結果**

1. **#1 profit-safe pfr**: **APPROVE（軽微な補足付き）**  
- target_metric: `Stage B通過群のmedian_oos_total_pnl>=0達成率`、`Stage C trade_sharpe median`、`Stage C pass count`  
- failure_mode: Stage B通過個体が全赤字（既観測）、`median_oos_sharpe`優位が実利益に結びつかない  
- causal_path: sign-based中心の通過判定 → 実損益の負方向を許容 → Stage Cで剥落  
- falsification: あなたが定義した a/b/c で妥当（そのまま採用可）  
- success_criterion: あなたの定義で妥当（`運用可能水準`は事前に最小 pass 数を数値固定しておくこと）  

補足MODIFY（小）:
- `trade_sharpe_stage_b > 0` は低サンプルで不安定なので、`n_fold_effective`最小要件（既存列活用）を併記して解釈を固定してください。  
- `median_oos_total_pnl`追加はStructuralとして妥当。APPROVE。

2. **#2 clause使用率ペナルティ段階導入**: **REJECT（cycle 22では）**  
- 理由: 交絡要因が増え、#1の因果検証を汚す。Round 1収束ルールにも反する。  
- 扱い: 保留TODO化は妥当。

3. **#3 FX監査指標の必須出力化**: **MODIFY**  
- 実装は保留、ただし**設計だけ先に固定して improvement-plan に明記**（列定義・算出点・fail条件）。  
- 理由: 実装並走は不要だが、次cycleの観測設計は今固定した方がよい。

4. **#4 cross-pair/multi-instrument**: **REJECT（cycle 22では）**  
- 理由: 守備範囲超過かつ変更規模が大きい。#1の反証前に進めるべきでない。

---

**Q1 回答**  
**APPROVE**。提示の確定形で進めて問題ありません。  
`median_oos_total_pnl`新規集計・archive列追加を含めてStructural変更として成立しています。  
追加条件は上記の最小補足（`n_fold_effective`解釈固定）のみ推奨。

---

**Q2 回答**  
**cycle 22は profit-safe pfr 単独に絞るべき**です。  
#2/#4は実装並走しない。#3は「設計定義のみ」並走可（コード変更なし）。

---

**Q3 回答**  
提案の「cycle 23から即 default ON」は**MODIFY**。  
**保守案を採用**:  
1. cycle 22で smoke（profit_safe_pfr）  
2. cycle 23で **legacy vs profit_safe_pfr の比較再確認**（少なくとも1追加seed）  
3. その時点で success_criterion達成なら default ON  

理由: 1回のsmokeでdefault化は早計。C9（反証先行）と30-run全体の学習効率の両立には、最小追加検証を挟むのが妥当です。