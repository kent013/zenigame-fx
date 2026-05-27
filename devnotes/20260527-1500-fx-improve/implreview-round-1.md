**Critical**
- `--robust-selection` 有効時の実効 selection schema が `summary.json` に正しく反映されません。  
  [scripts/alpha_factory/run_ga.py:1736](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1736) で cross-pair 側しか解決しておらず、[scripts/alpha_factory/run_ga.py:1875](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1875) の `selection_key_schema` は robust 状態を見ません。さらに [scripts/alpha_factory/run_ga.py:1893](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1893) の `best.selection_score` も常に v3.3 10要素固定です。  
  結果として、`robust_selection=ON` の R107 を summary だけで監査すると誤判定します。cycle26 の検証ログとしては致命的です。

**Warning**
- `robust_selection_enabled` のパースが `bool(...)` で、文字列 `"false"` を `True` と解釈します。  
  [src/alpha_factory/config.py:607](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/config.py:607)  
  `default OFF bit-exact` の主張に対して設定事故耐性が弱いです（同ファイルの `_strict_bool` を使う設計に揃える方が安全）。
- cross-run contamination guard の `base_config_hash` に robust 設定が入っていません。  
  [src/alpha_factory/calibrate_state.py:67](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_state.py:67)  
  `robust ON/OFF` 間で calibrate history が共有されるため、実験分離を厳密にやるなら scope key へ追加が必要です。
- 設計文の「生存集合は不変・順序のみ変化」は厳密には不正確です。  
  robust は `fold_robust` と `fitness_pen` の間に入るため、同一 prefix 群内の勝者が変わり、elite/tournament 経由で世代遷移自体が変わります（これは実装としては意図通り）。

**Nit**
- テスト名が実態と不一致です。  
  [tests/alpha_factory/test_archive.py:187](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_archive.py:187) `test_schema_has_58_columns` なのに 71 列を検証しています。

**観点別の短評**
- bit-exact(OFF): 実装上は保たれています（`_selection_key` の早期 return）。  
- holdoutリーク: 見当たりません（robust入力は Stage B fold 統計のみ）。  
- schema後方互換: nullable 追加としては妥当です。`GENOME_ENTRY_SCHEMA_VERSION` 非bump方針とも整合。  
- 崩壊耐性: 仮説としては妥当だが、効果は R107a/b で実測確認が必要です。Gate1 で退行検知は可能です。

**実行確認**
- `uv run pytest -p no:cacheprovider tests/scripts/test_alpha_factory_run_ga_feasibility.py -k "robust or v31_selection_key" -q`  
- `uv run pytest -p no:cacheprovider tests/alpha_factory/test_archive.py -k "schema_has_58_columns or schema_nullable_attributes" -q`  
- `uv run pytest -p no:cacheprovider tests/alpha_factory/test_cross_pair_selection_pressure.py -q`  

**総合判定: 要修正**  
理由は Critical 1件（summary provenance の不整合）。ここを直してから R107 full run に進むのが安全です。