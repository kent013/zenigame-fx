**前提検証（C4）**
- **Fact**: 提示 diff では `TradeRecord` に `spread_cost` / `holding_cost` が default `0.0` で追加され、finite + `>=0` 検証が入っています（[canonical_metrics.py:253](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/canonical_metrics.py:253), [canonical_metrics.py:282](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/canonical_metrics.py:282)）。
- **Fact**: `apply_spread_stress` は `NotImplementedError` から実装へ置換され、式は `delta=m-1`, `new_pnl=pnl-spread*delta`, `new_spread=spread*m` です（[stage_bc_evaluator.py:1030](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_bc_evaluator.py:1030)）。
- **Fact**: テスト追加は `TradeRecord` 6件、`apply_spread_stress` 10件で、基本境界は押さえています（[test_canonical_metrics.py:215](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_canonical_metrics.py:215), [test_stage_bc_evaluator.py:1105](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_stage_bc_evaluator.py:1105)）。
- **Interpretation**: diff 範囲の実装自体は設計意図（T078前提）に整合。ただし「既存 caller 全件確認」「broker Decimal 実装との等価性」は提示情報だけでは完全検証不可。

[Critical]
- なし（diff範囲内で代数破綻・invariant破壊は見当たりません）。

[Warning]
1. **スプレッド伝搬未配線時のサイレント no-op リスク**  
   `spread_cost` が全 trade で `0.0` のままでも stress が通ってしまい、評価上は「stress適用済み」に見える可能性があります（[stage_bc_evaluator.py:1030](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_bc_evaluator.py:1030)）。  
2. **broker 経路との等価性テスト不足**  
   数式は等価ですが、`float` と `Decimal` の丸め差の回帰検知テストがないため、「完全等価」の監査証跡が弱いです（[test_stage_bc_evaluator.py:1105](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_stage_bc_evaluator.py:1105)）。

[Suggestion]
1. `apply_spread_stress` 呼び出し側で `multiplier>1` かつ `sum(spread_cost)==0` を WARN/FAIL するガードを追加。  
2. `session_block.apply_spread_stress`（Decimal）との同一入力比較テストを1本追加し、許容誤差を明示。  
3. 超大倍率での overflow 境界（`inf` 発生時）テストを追加し、期待例外を固定化。

**ファイル別判定**
- [canonical_metrics.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/canonical_metrics.py): **概ね妥当**（backward compat 方針・invariant 追加は適切）
- [stage_bc_evaluator.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_bc_evaluator.py): **概ね妥当**（式・fail-fast 妥当、ただし no-op 可視化は要検討）
- [test_canonical_metrics.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_canonical_metrics.py): **妥当**（追加 invariants を十分に検証）
- [test_stage_bc_evaluator.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_stage_bc_evaluator.py): **妥当だが改善余地あり**（Decimal 経路との等価回帰が未カバー）

**全体判定: INCONCLUSIVE**  
理由: 実装 diff 単体は承認可能レベルですが、重点指定された「既存 caller 全件互換」「broker Decimal 実装との等価性」は、提示差分だけでは監査的に確証不足です。