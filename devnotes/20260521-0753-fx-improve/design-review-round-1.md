**施策判定: REQUEST_CHANGES**

[Critical] `mutate` 呼び出し設計が現行シグネチャと不整合で、そのまま実装すると成立しません。  
根拠:
- `mutate` に `name` 引数は存在しません（[operators.py](/Users/ishitoya/repository/zenigame-fx/src/ga/operators.py:507)）。
- `genome_from_dict` は archive 内の元 `name` をそのまま復元します（[serialize.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/serialize.py:87)）。
- 現行 gen0 は `g0_i*` 命名前提です（[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:2075)）。  
修正案（最小変更）:
- `mutate(seed_g, rng, ...)` の後に `replace(mutated, name=f"g0_ws{i}", units=cfg.backtest.units)` を必須化。
- `provenance` は `g0_ws*` も必ず登録し、衝突しない命名規約を固定する。  
反証可能仮説:
- 現提案のまま実装すると、`TypeError`（unexpected keyword `name`）または重複名混入が発生し、gen0 構築が壊れる。

[Warning] `warmstart_ratio=0.0` の「完全不変」保証は、設計意図は正しいがテスト契約が不足しています。  
根拠:
- 既存の決定論テストはあるが warmstart 経路 OFF の未介入性を直接検証していません（[test_run_ga_parallel.py](/Users/ishitoya/repository/zenigame-fx/tests/scripts/test_run_ga_parallel.py:1)）。  
修正案:
- `warmstart_ratio=0.0` で `load_warmstart_motifs` / `mutate` が呼ばれないことをモックで検証。
- 同 seed で warmstart設定有無（ratio=0）を比較し、gen0 の genome 列と最終 `summary.best` が一致することを固定テスト化。

[Suggestion]
- 即時淘汰リスク低減のため、`n_ws` のうち少なくとも 1 個体は「非 mutate のアンカー複製」にすると、再現性目的と整合しやすいです。
- R85→R86 同一 dataset/holdout 利用は「再現性検証」には妥当ですが、「汎化性能検証ではない」と成功基準に明記すると監査が通しやすいです。

**全体判定**
- 方針（T102から切り離した simple injection、default OFF 不変）は妥当です。  
- ただし上記 Critical 1点を先に潰さないと実装が成立しないため、現時点は `REQUEST_CHANGES` です。