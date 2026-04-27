1. [Warning] state record 必須メタデータ記述に旧 `config_hash` が残っており、仕様が二重化している  
Fact: 差分では record 実体が `base_config_hash` / `full_config_hash` を出力する一方、直下の必須項目リストに旧 `config_hash` が残っています（[detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260427-1856-stage-pipeline-health-fix/detailed-design.md), [calibrate_gate.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/calibrate_gate.py), [calibrate_state.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_state.py)）。  
Interpretation: 実装者ごとに出力フィールドが分岐し、将来の互換運用で混乱するリスクがあります。  
修正案: 必須項目リストを `base_config_hash` / `full_config_hash` に一本化し、`config_hash` は「互換読み取り専用（非必須）」として明記。

2. [Suggestion] `source="cli"` の優先順位テストを 1 本追加すると運用事故が減る  
Fact: `threshold_source` の単一値化は明記されていますが、「history 適用後に CLI override が来た場合の最終優先順位」の検証ケースは抜粋内で未明示です（[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py)）。  
Interpretation: 仕様はほぼ固まっているため、最終優先順位の回帰だけ先に封じると監査性が上がります。  
修正案: 「history 適用あり + CLI 指定あり => 最終 source は `cli`」のテストを追加。

**Round 2 指摘の解消確認**
- [Critical] `base_config_hash` 呼び出し整合: 解消
- [Warning] `effective_threshold` source プレースホルダ: 解消
- [Warning] unavailable reason 優先順位 + 排他 + 不変条件: 解消

**新規 Critical / Warning**
- 新規 Critical: なし
- 新規 Warning: 1 件（上記 #1、非ブロッキング）

**施策判定**
- 施策0a: `APPROVE`
- 施策0b: `APPROVE`
- 施策B: `APPROVE`
- 施策A: `APPROVE`

**全体判定**
- `APPROVED`（上記 Warning 1 件はドキュメント整合の軽微修正推奨）