**前提確認（C4/C6）**
- **Fact**: 提示された diff と機械検証結果（`pytest 2094 passed, 1 xfailed / ruff clean / mypy clean`）のみを根拠にレビューしました。実行再検証はしていません。
- **Interpretation**: T077 の主目的（`applied_from_run_id` 必須化 + hot-fix 経路削除 + テスト追加）は概ね実装されています。

**ファイル別判定**

- [Warning] [src/alpha_factory/calibrate_freeze.py:151](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_freeze.py:151)  
  hot-fix 削除自体は方針に整合しますが、`evaluate_freeze_status` 側で入力 invariant（`applied_from_run_id` が非空 `str`）を再確認していません。  
  `HistoryRecord` 以外や不正生成オブジェクト混入時に `None` などが set に入り、旧実装と違って**静かに誤カウント**し得ます。fail-fast 方針ならここで `ValueError` を投げる防衛線を 1 行入れる方が安全です。

- [Suggestion] [src/alpha_factory/calibrate_gate_history.py:94](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_gate_history.py:94)  
  `applied_from_run_id: str = ""` + `__post_init__` reject は runtime fail-fast としては正しいですが、呼び出し忘れを静的検出できません（mypy では漏れる）。  
  将来改善としては `kw_only` 必須化などで compile-time に寄せる余地があります。

- [Suggestion] [tests/alpha_factory/test_calibrate_gate_history.py:292](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_calibrate_gate_history.py:292), [tests/alpha_factory/test_calibrate_freeze.py:240](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_calibrate_freeze.py:240)  
  `_UNSET` sentinel を使った「省略 vs 明示 `None/""`」分離は妥当です。  
  ただし運用リスク観点では「JSONL に不正 v2 行が混在した場合の挙動（明示 fail-fast か skip か）」を 1 本追加しておくと、hot-fix 削除後の意図が固定化されます。

- [Suggestion] [devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:927](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:927)  
  「Round 21 まで Optional → Round 22/T077 で必須化」の系譜は明記されており、設計文言は要件に整合しています（ここは問題なし）。

- [Suggestion] [tests/alpha_factory/test_t058_integration.py:331](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_t058_integration.py:331)  
  必須 field 追加は適切で、既存 caller 互換性担保の方向性と一致しています。

**[Critical]**
- 該当なし。

**全体判定**
- **CHANGES_REQUESTED**

理由は 1 点のみで、`calibrate_freeze` の入力境界で invariant 再検証がないため、hot-fix 削除後に「壊れた入力が来たときの挙動」が fail-fast で固定されていない点です。ここを埋めれば APPROVED 相当です。