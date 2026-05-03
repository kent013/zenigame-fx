**前提検証 (C4)**
1. `Verified`: 現行 Stage C は base と stress で `run_backtest` を 2 回呼び、stress 失敗時は `stage_c.stress_failure` を出す実装です（[stage_gate.py:1291](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1291), [stage_gate.py:1407](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1407), [stage_gate.py:1436](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1436)）。
2. `Verified`: `_try_evaluate_canonical_five_safe` は enabled=False で即 `None`、例外時は `canonical_five.skipped` を出す契約です（[stage_gate.py:143](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:143), [stage_gate.py:159](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:159)）。
3. `Verified`: 概念設計は D2/C5 を「ログ契約」として明示しています（[conceptual-design.md:357](/Users/ishitoya/repository/zenigame-fx/devnotes/20260503-2319-B-phase2-step1.7-stage-c-stress-dual-path/conceptual-design.md:357), [conceptual-design.md:359](/Users/ishitoya/repository/zenigame-fx/devnotes/20260503-2319-B-phase2-step1.7-stage-c-stress-dual-path/conceptual-design.md:359)）。
4. `Unverified`: B2/B3（RSS/時間）は実測前提で、現時点では設計仮説のままです（[conceptual-design.md:348](/Users/ishitoya/repository/zenigame-fx/devnotes/20260503-2319-B-phase2-step1.7-stage-c-stress-dual-path/conceptual-design.md:348)）。

**施策 1: `_log_canonical_dual_path` docstring 更新**  
判定: **APPROVE**
1. [Suggestion] `C_stress` 追記は SSOT 整合として妥当です。実装影響なしのため設計リスクは低いです。

**施策 2: `evaluate_stage_c` stress dual-path 配線（別 try 物理隔離）**  
判定: **APPROVE**
1. [Warning] 設計意図（legacy と dual-path の物理分離、skip 整合、disabled 時の `canonical_skipped`）は現行関数構造に自然に載ります。  
Fact: stress 判定本体は `reasons/stress_payload` 更新箇所が明確です（[stage_gate.py:1385](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1385)）。  
Interpretation: 提示の「別 try + ガード」は D1/D4 を満たしやすいです。
2. [INCONCLUSIVE] B2/B3（メモリ/速度）は設計段階では未確証。実装後 smoke 5 run の実測が必須です。

**施策 3: C_stress dual-path テスト 7 ケース**  
判定: **REQUEST_CHANGES**
1. [Critical] **D2 の反証テストが不足**しています。  
Fact: D2 は「dual-path 例外は `unexpected_failure/log_failed` のみ、`stage_c.stress_failure` 経路に触れない」契約です（[conceptual-design.md:359](/Users/ishitoya/repository/zenigame-fx/devnotes/20260503-2319-B-phase2-step1.7-stage-c-stress-dual-path/conceptual-design.md:359)）。  
Interpretation: 提示 test #2/#3 は StageResult 比較中心で、`stage_c.stress_failure` **非出力**を直接 assert していないため、D2 を厳密に falsify できません。  
対策: #2/#3 に `capsys` を加え、`"stage_c.stress_failure"` が出ないことを明示 assert してください。
2. [Warning] `run_backtest` 2 回目 raise 方式は、**stress 経路同定として脆い**です。  
Fact: 現在は base→stress の2回ですが、呼び出し順依存です（[stage_gate.py:1291](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1291), [stage_gate.py:1407](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1407)）。  
Interpretation: 将来の呼出追加で「2回目=stress」が崩れると偽陽性/偽陰性が出ます。  
対策: call count ではなく `max_spread_bps`（base値と stress値）で分岐してください。
3. [Suggestion] 概念設計では C_stress の golden 1 ケース追加が書かれているため、詳細設計との SSOT 差分は解消した方が安全です（[conceptual-design.md:265](/Users/ishitoya/repository/zenigame-fx/devnotes/20260503-2319-B-phase2-step1.7-stage-c-stress-dual-path/conceptual-design.md:265)）。

**全体判定**  
**CHANGES_REQUESTED**

（主理由: 施策3で D2 監査契約を直接反証できるテストが不足。ここを埋めれば、設計の本体ロジックは前進可能です。）