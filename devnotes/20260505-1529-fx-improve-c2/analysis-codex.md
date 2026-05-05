# RUN run_20260505_043320 分析（Codex 独立分析）

## 前提差分（C4）
- 前提A（「旧R34と新R34は同条件比較」）は **棄却**。  
  旧R34（`run_20260504_132300`）の `summary.json` では `bars_stage_b=183403`、新R34（`run_20260505_043320`）は `bars_stage_b=97003` かつ `bars_stage_b_excludes_stage_a=true`。  
  つまり Stage B 評価対象期間が異なるため、`all_folds_unavailable` の単純比較は collider（条件集合不一致）になりうる。
- 検証元: [旧 summary (git show a31a22a)](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-34/summary.json), [新 summary](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-34/summary.json), [archive collect 実装](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py), [selection 実装](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py)

## 観察事実（Facts、 C6 分離遵守）
- 新R34の Stage B fail 主因コンボは `median_oos_sharpe<min;positive_fold_ratio<min;all_folds_unavailable` が 2248 件。
- 旧R34では同コンボ 216 件。  
- ただし旧R34は Stage B が 183403 bars（実質 A+B）、新R34は 97003 bars（Bのみ）。
- `n_fold_effective` 分布:
  - 新R34 Stage A pass群: `{0:2248, 1:623, 2:58}`（max=2）
  - 旧R34 Stage A pass群: `{0:216, 1:370, 2:533, 3:1185, ... ,9:26}`（max=9）
- Stage B pass群（新R34, n=22）は `total_pnl mean=-14,303`, `trade_count mean=16.5`, `trade_sharpe_raw mean=0.023`, `n_fold_effective mean=2.0`。
- Stage A pass群（新R34, n=2929）は `total_pnl mean=+17,013`, `trade_count mean=65.5`, `trade_sharpe_raw mean=0.0793`。
- cycle1修正 (`collect_stage_a` の `total_pnl` 伝搬) により、`stage_c_feasible` 判定材料（`pnl>0 && sharpe>0`）が実質変化しうる設計（selection tupleに含まれる）。

## 解釈・推論（Interpretations、 C9 反証可能性付き）
- 仮説H1: `all_folds_unavailable` 10倍は cycle1 bugfix副作用が主因。  
  - 現時点判定: **反証寄り**。まず Stage B期間が旧新で違う（183403→97003）ため、fold数低下（max 9→2）だけで大半を説明できる。  
  - 反証条件: 同一コード・同一データ・同一partition（B=97003固定）で `collect_stage_a` 修正有無だけA/B実行し、`all_folds_unavailable` が有意差なく一致すればH1棄却。
- 仮説H2: Stage B pass群 negative PnL は禁止事項6（取引回数削減で見かけ改善）構造。  
  - 判定: **抵触兆候あり**。pass群で trade_count が 65.5→16.5 に急減し、PnLは負。  
  - ただし n=22（<30）なので因果断定は禁止（C7）。  
  - 反証条件: trade_count帯で層別（例: 10-20, 20-40, 40+）しても Stage B pass優位が消えないなら「回数削減だけが主因」は棄却。
- 仮説H3: `wf_min_folds_required 2→4` は有効対策。  
  - 判定: **現状では不適切**。新R34の `n_fold_effective` が max=2 のため、4へ上げると原理的に全滅しやすい。偽陽性対策ではなく gate停止になる。  
  - 反証条件: 先に Stage B window設計を増やして `n_fold_effective>=4` が十分発生することを確認できた場合のみ有効化余地。
- 仮説H4: `v3_1_stage_b_priority` は偽陽性増加時に歪む。  
  - 判定: **歪むリスク高い**。tupleで `stage_b_pass` が上位かつ重複キーで入っており、偽陽性B-passが増えると選抜圧が偏る。  
  - 反証条件: B-pass偽陽性群の selection score を全世代で再計算し、上位占有が起きないならリスクは限定的。

## 次サイクル候補
- [Critical] 旧新比較の前提是正: 「同条件再現」検証を先に実施（partition固定・code固定・data hash固定でA/B）。  
- [Critical] Stage B gate設計再検証: `wf_min_folds_required` を上げる前に、まず fold生成可能性（B期間長とWF窓）を契約化。  
- [Warning] Stage B pass品質監査: n<30明記のうえ、trade_count層別で偽陽性構造を検証。  
- [Warning] selection score感度分析: `stage_b_pass`重み（重複キー含む）が選抜を歪めるか再評価。  
- [Warning] reason code集計の正規化: `stage_b_reason_codes` がセミコロン連結文字列で、primary/any集計の解釈齟齬を生みやすい。

## 全体判定
**CRITICAL_DRIFT**  
根拠: 旧新比較が同条件でなく（Stage B対象期間が別物）、その状態で `all_folds_unavailable` 10倍を副作用扱いするのは誤判定リスクが高い。加えて Stage B pass品質（negative PnL + 低trade_count）が悪い。

## Claude 分析との差分
- 同意点: Stage B pass品質が悪く、禁止事項6の兆候がある点。  
- 反対: `all_folds_unavailable` 10倍を「cycle1修正の副作用疑い」と強く置く点。まず **partition差分（183403→97003）** を主因候補として先に反証すべき。  
- Claudeが見落とした観点: `wf_min_folds_required 2→4` は現データ幾何（`n_fold_effective max=2`）では対策でなく fail-closed 化になりやすい。