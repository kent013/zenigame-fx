**Section A: 実装候補の判定**

判定: **T099 は `MODIFY` で APPROVE**（= 案B、ただし「1仮説・1最小変更」に再定義）

- `target_metric`
  - 最優先: Stage B 通過群の `median_oos_total_pnl >= 0` 達成率
  - 次点: Stage C `trade_sharpe_stage_c` median（legacy 比）
  - 監視: Stage B pass 数の極端な崩壊（過締め検知）

- `failure_mode`
  - 現状は sign-based 条件のみで、**赤字通過を防げない**（Run 74 の主因）
  - `pfr_only` 単独だとこの構造欠陥が残るため、Critical 問題に不十分

- `causal_path`
  - Stage B gate を「持続性（pfr）」だけでなく「収益整合（magnitude）」も満たす条件へ変更
  - これにより Stage B 通過時点で赤字候補を除外し、Stage C での無駄な評価を減らす
  - FX制約（イントラデイ、ロング/ショート許容、スプレッド/スワップ反映 fitness）と整合

- `falsification`
  - Run 75 smoke で以下なら仮説棄却:
    - Stage B pass がほぼ 0 に崩壊
    - Stage B 通過群の pnl が依然マイナス中心
    - Stage C 指標が legacy 比で悪化

- `success_criterion`
  - `treatment`（modified gate）で
    - Stage B 通過群 `median_oos_total_pnl >= 0`
    - Stage C `trade_sharpe_stage_c` median が legacy 以上
    - pass 数が運用不能レベルまで崩壊しない

実装最小化:
- `pfr_only` を「純pfr」ではなく **profit-safe pfr** に変更  
  `pfr >= 0.4` AND `median_oos_total_pnl >= 0` AND `trade_sharpe_stage_b > 0`  
- legacy は不変、opt-in でA/B可能

---

**Section B: TODO 全体の関係分析**

- **T099 と T100 は両立可能**。依存は弱く、同時実装必須ではない
- 現在のボトルネックは Stage B の通過品質なので、**T099 を先行**が妥当
- T100（Stage C stratified）は Stage B 品質が改善した後に効果検証した方が因果が明確

---

**Section C: 総合推薦**

推薦: **案B**（T099 + C22-1 統合）

根拠:
- 案Aは Run 74 の核心（赤字許容）を残すため不十分
- 案Cは30 RUN連続ループ下で修正機会を後ろ倒ししすぎる
- 案Bを「profit-safe pfr」という**単一仮説・単一変更**として扱えば、収束要件にも合致する

---

**Section D: TODO vs GA 改善のバランス判断**

**`ga_improvements`** が妥当です。  
今回の主課題は設計上の gate 不整合で、一般TODO（docs/mypy/監査スクリプト）より GA 改善を優先すべきです。