**前提（C4）**
- `verified` 本レビューは、今回提示された差分テキストのみを根拠に実施（実ファイル未読）。
- `verified` Round 1 の C1/C3/W1/W2/Sg に対する設計上の対応方針は明示されている。
- `unverified` 実コード実装で、差分記載どおりに引数名・ハッシュ計算関数・reason分類が整合しているか。

**C9 反証先行（要点）**
- 反証対象: 「Round 1 指摘は全解消し、追加懸念はない」  
  結果: 反証成立。施策Aの呼び出し例に新規 Critical 相当の不整合が残るため、全解消とは判定できない。

1. [Critical] `base_config_hash` 設計の呼び出し整合が崩れている  
Fact: 施策Aで `load_calibrated_threshold(... base_config_hash: str ...)` を定義しつつ、呼び出し例が `config_hash=compute_config_hash(cfg)` になっている（[detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260427-1856-stage-pipeline-health-fix/detailed-design.md), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py), [calibrate_state.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_state.py)）。  
Interpretation: このまま実装すると API 不一致（最悪 TypeError）か、C2 の自己矛盾を再導入する。  
修正案: `compute_base_config_hash(cfg)` を明示追加し、呼び出しを `base_config_hash=...` に統一。`full_config_hash` は監査記録専用で別保存。

2. [Warning] `effective_threshold` ログの `source` がプレースホルダのままだと観測価値が落ちる  
Fact: `source="config|history|cli"` が例示のまま。  
Interpretation: 0b の観測目的（source-of-truth確定）を満たせない可能性。  
修正案: 実行時に単一値（`config` / `history` / `cli`）を必ず出す仕様に固定。

3. [Warning] unavailable reason の分類優先順位が未固定  
Fact: 0b で reason 内訳追加方針はあるが、`trade_count_below_min` と `zero_variance` 等の排他的優先順位が未記述。  
Interpretation: 実装者によって集計がぶれ、0a/0b比較の再現性が下がる。  
修正案: reason を排他的 enum とし、`sum(reason_counts.values()) == n_fold_unavailable` の不変条件テストを追加（[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py), [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py)）。

**Round 1 指摘の解消判定**
- C1: 解消（0a/0b 分割 + 計測パッチ前提化）
- C2: **未解消（部分解消）**（設計思想は改善、呼び出し整合に不備）
- C3: 解消（経験式削除、統計要件先行）
- W1: 解消（0a/0b 分割）
- W2: 解消（schema_version/isfinite/range/ISO8601 追加）
- Sg: 解消（seed=3, tolerance=±0.07, 2/3 ルール固定）

**施策別判定**
- 施策0a: `APPROVE`
- 施策0b: `APPROVE`
- 施策B: `APPROVE`
- 施策A: `REQUEST_CHANGES`

**全体判定**
- `CHANGES_REQUESTED`

全体を `APPROVED` にするための最小修正は1点です。  
`base_config_hash` の呼び出し仕様を設計文書内で完全統一してください。これが反映されれば、今回の残課題は実質解消です。