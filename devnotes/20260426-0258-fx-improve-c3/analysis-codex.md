**観察事実**
- Stage A pass 2000 / Stage B pass 0、失敗理由は `insufficient_folds=2000 (100%)` に単峰化。
- 現行WF設定 `train=120, embargo=1, test=20` は最小141観測日を要求。
- Stage B対象期間は約127観測日で、fold数が要件未達（実質1以下）になり、構造的に全Reject。
- Run-12→13で fitness/PnL は改善しており、探索品質より先に「検証器が通らない」状態。

**解釈**
- これはモデル性能問題ではなく、**Stage B feasibility不成立**が根因。
- よって最優先は「Stage Bでfoldを作れる条件を満たすこと」。ここを直さない限り他TODOは効かない。

**推奨案（C9 falsification-first）**
- 最有力: **案C（構造対応）+ 案A（即効プロファイル）**
- 具体:
  - Stage B実行前に `max_folds` を事前計算し、`min_folds`未満なら fail-fast で理由を固定出力。
  - その上で短窓WFプロファイル（例: `train=60,test=10,embargo=1`）を「feasible時のみ」適用。
- 反証条件:
  - 短窓適用後も `insufficient_folds` が主因なら仮説棄却。
  - `insufficient_folds` 解消後に Sharpe/PnL が悪化し live基準未達なら「次のボトルネックへ移行」と判定。

**各案の禁止事項チェック**
- 案A（WF縮小）:
  - 違反リスク: 値いじり化。
  - 回避: 目的を「fold成立」に限定し、Sharpe閾値等は不変更、事前反証条件を固定。
- 案B（期間延長）:
  - 違反リスク: 見栄え改善のための期間操作。
  - 回避: end日固定、start前倒し理由を「fold成立」に限定、比較は同一評価窓で実施。
- 案C（構造解決）:
  - 禁止事項適合。仕組み不全を先に修正するため最も原則準拠。

**Critical TODO（1件）**
- `title`: T038 Stage B Feasibility Contract（insufficient_folds恒久対策）
- `target_metric`: Stage B `insufficient_folds_rate` を 100% → 0%
- `failure_mode`: 観測日不足でWF fold未成立のまま全個体Reject
- `causal_path`: dataset_days と WF(required_days, step, min_folds) の不整合 → fold不足 → Stage B全滅
- `falsification`: 事前計算で `max_folds>=min_folds` を満たす設定でも `insufficient_folds` が主因なら仮説棄却
- `success_criterion`: 次Runで Stage B pass_count > 0 かつ primary reason の首位が `insufficient_folds` でない

**全体判定**
- **CRITICAL_DRIFT**（性能ドリフトではなく、検証パイプラインの構造不成立）