## 判定: REVISE

## 全体所感
C1制約上、設計ドキュメント本文が未提示のため「設計意図との一致」は一部 INCONCLUSIVE ですが、提示コード単体の整合性は高いです。  
ただし、`schema validation` と `exit code mapping` の接続で実害が出る欠陥が1点、ログ契約で1点あり、現時点は `REVISE` が妥当です。

## 観点別評価
1. pure logic / CLI 分離: 良好（`src` と `scripts` の責務分離は明確）。  
2. CalibrateConfig 値域検証: 概ね良好。  
3. `aggregate_sample` 3 mode 式: 実装は自己整合。設計意図との厳密一致は INCONCLUSIVE。  
4. `decide()` 制御則: quantile-snap + hysteresis + delta clamp は実装済みで整合。  
5. yaml atomic write: `mkstemp + flock + os.replace` 実装済みで妥当。  
6. schema validation: **要修正**（下記必須修正1）。  
7. exit code mapping: **要修正**（必須修正1に起因して崩れる経路あり）。  
8. テスト網羅: 件数・内訳は十分。  
9. 転記漏れ（`calibrate.*` 配線）: 主要キーは loader→consumer まで接続済み。  
10. `ruamel.yaml` 依存追加: round-trip要件に照らして妥当。  
11. ログ出力4イベント: **要修正**（下記必須修正2）。

## 必須修正点 (REVISE のみ)
1. [`src/alpha_factory/calibrate_gate.py`](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T027/src/alpha_factory/calibrate_gate.py) と [`scripts/alpha_factory/calibrate_gate.py`](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T027/scripts/alpha_factory/calibrate_gate.py) の接続不備。  
事実: `validate_schema()` は `total_pnl` / `max_drawdown_pct` / `trade_count` の null/NaN を弾かない一方、`compute_monitoring()` は `float(...)` / `int(...)` を直接実行。  
解釈: null混入時に `TypeError` 等が未捕捉で上位に伝播し、規定の `EXIT_SCHEMA_MISMATCH(8)` や `EXIT_IO_ERROR(5)` ではなく異常終了し得る。  
修正方針: `validate_schema()` で当該列の null/NaN を明示検証するか、`compute_monitoring()` 側で `None/NaN` を安全スキップし、想定外値は `SchemaMismatchError` に正規化して exit code を固定化する。

2. [`scripts/alpha_factory/calibrate_gate.py`](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T027/scripts/alpha_factory/calibrate_gate.py) の JSONL イベント契約。  
事実: `calibrate_gate.applied` は「実書き込み時のみ」出力され、`dry-run` / `in_band` / `skip_*` では欠落する。  
解釈: 「input / monitoring / decision / applied の4イベント」を前提にする監視・集計側で欠損扱いになる。  
修正方針: 常に `applied` を出し、`applied=false`・`reason`（`dry_run`/`no_change`/`skip_*`）を載せる。

## 推奨改善点 (任意)
`load_calibrate_config()` の `enabled=bool(section["enabled"])` は、将来 `"false"` 文字列混入時に真になるため、型検証を追加すると安全です。