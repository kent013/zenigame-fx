前提を固定します（C4）。

- Verified: C1〜C9（提示された `analysis-merged.md` の観察事実）  
- Verified: 絶対制約（イントラデイ、両方向、swap/spread net反映）  
- Inconclusive: `trade_sharpe_raw` が Stage A 判定の唯一指標かどうか（未監査）

以下、Fact / Interpretation を分離して判定します（C6）。

**A. P1-P4 判定**

1. **P1: Stage A 判定契約監査 → APPROVE（最優先）**  
Fact: `max(trade_sharpe_raw)>0` なのに `pass=0`。  
Interpretation: 判定契約の不一致、別ゲート、丸め、列取り違えのいずれか。  
最小実装案（非侵襲・監査のみ）:
- Read対象:
  - `config/alpha_factory/default.yaml`（Stage A閾値SSOT確認）
  - `scripts/alpha_factory/run_ga.py`（実行時に閾値がどう解決されるか）
  - Stage A判定関数実装ファイル（例: `src/.../stage_gate*.py`）
  - 評価集計/保存実装（例: `src/.../evaluator*.py`, `src/.../archive*.py`）
- ログ挿入点:
  - `Stage A 判定直前`: 個体ID、used_metric名、raw値、比較演算子、threshold、pass/fail、fail_reason
  - `Stage A 判定直後`: `pass_count`, `fail_reason`集計
  - `archive 書込直前/直後`: 同一個体の評価値と保存値（値一致監査）
- 出力先:
  - `reports/run-28/stage_a_contract_audit.jsonl`（個体ごとの判定トレース）
  - `reports/run-28/stage_a_fail_reason_summary.json`
  - `reports/run-28/stage_a_contract_audit.md`（SSOTと差分要約）
- 必須ガード:
  - `used_metric_name` を明示ログ化（C2対策）
  - 比較式文字列（例 `trade_sharpe_raw > 0.0`）を明示（誤読防止）

2. **P2: archive 伝搬漏れ監査 → MODIFY（P1に統合）**  
単独実施は分散。P1の同一トレースに統合して1変更に収束。  
修正条件:
- target_metric: `archive_role/source_stage/sharpe/total_pnl` の非NaN率
- falsification: in-memory有値 + persist後NaN なら観測系バグ確定
- success_criterion: 個体キー一致で「評価時値=保存値」検証可能

3. **P3: max_clause 1→2 AB → MODIFY（今回は保留）**  
現時点で実施すると「判定系未検証で値調整」に近づく。  
実施条件（次ラウンド）:
- P1で判定契約が正しいと確認済み
- ABは同一seed帯で複数run（最低n>=3）で分布比較（C7）
- 成功基準を `max値` 単独でなく `pass_rate` と `net fitness` 併用に変更

4. **P4: cross-pair(ii-lite)準備 → MODIFY（中期キュー）**  
North Star上は必須だが、現ボトルネック（Stage A全滅）より後。  
今は設計のみ許可、実装は Stage A 生存回復後。

---

**B. Run-27→Run-28で1つに絞るなら**

- 採用: **P1（+P2を監査ログ統合）だけ**
- 反証可能仮説:  
  「Stage A pass=0 は戦略性能不足ではなく、判定契約/伝搬不整合が主因である」
- 最小変更:  
  「判定トレース + fail_reason集計 + archive一致監査の追加（挙動不変更）」

---

**C. P1で「判定式は正しい」と確認された場合の次手（予告）**

- 次ラウンド（Run-29想定）で **P3の最小AB** を実施。  
- 変更は `max_clause: 1→2` のみ、他パラメータ固定。  
- 判定指標は `trade_sharpe_raw` 単独でなく、`Stage A pass_rate` と `net fitness_pen` を同時監視。  
- 取引回数減による見かけ改善は禁止ルールで弾く（rejection rule #6）。

---

**D. メタ過学習ガード評価**

- P1: **Structural** で問題なし。  
- P2: **Structural**（ただしP1統合が望ましい）。  
- P3: **Principled Parametric** だが、単発run反応で決めるとReactive化するので要ガード。  
- P4: **Structural**、ただし時期尚早。  
- 結論: 問題があるのは「P3を今すぐ実施する運用判断」。提案自体は不適切ではない。

---

**E. North Star寄与での優先順位（再判定）**

1. **P1**（判定契約の真偽確定。全施策の前提）  
2. **P2（P1統合）**（監査不能状態の解消。禁止事項 #8 回避）  
3. **P3**（Stage A生存率改善の最小因果検証）  
4. **P4**（最終到達条件に必須だが、現時点の一次ボトルネックではない）

この順序が、禁止事項を踏まずに最短で `live_criteria` 到達可能性を上げる進め方です。