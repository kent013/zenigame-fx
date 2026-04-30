## Verdict
APPROVED

## 前提 (C4)
- Round D1-D2 の改訂内容を詳細設計 SSOT として扱う。
- T072 は Phase 1 では runtime 未組込、production 配線は Phase 2 gate で別途確認する前提。
- date 粒度は両端 inclusive、minute/window 粒度は半開区間 `[start, end)` で統一済みと判断する。

## Critical
- なし

## Warning
- [W1] `SESSION_BLOCK_*_FIELD_PATHS` は妥当だが、実装時に `get_by_field_path(record, path)` の標準 helper を置かないと consumer ごとに path 解釈が分散する。
- [W2] `F49_production_callers_no_test_mode` は `grep` subprocess より AST 解析推奨。文字列・docs・tests への false positive を避けるべき。
- [W3] YAML schema lint 5段は妥当だが、残り4段は `scripts/lint_calendar_configs.py` のような専用 lint script を DoD に明記した方がよい。
- [W4] `_DuplicateKeyRejectLoader` は merge key reject で十分強い。ただし unhashable key が来た場合は `TypeError` ではなく `ConstructorError` に包むと失敗モードが一貫する。
- [W5] production gate checklist は PR description だけだと enforce が弱い。CI で checklist file または PR template 項目を検査する方針を添えると確実。

## Suggestion
- [S1] `SESSION_BLOCK_STORAGE_FIELDS` / `SESSION_BLOCK_DERIVED_FIELD_PATHS` に `record_schema_version` を含めるか、明示的に `SESSION_BLOCK_META_FIELDS` として分離すると監査しやすい。
- [S2] `F14_yaml_duplicate_after_flatten` は merge を reject する設計なので、名前を `F14_yaml_merge_key_prevents_flatten_duplicate` に寄せると挙動と一致する。
- [S3] schema version bump 忘れ対策として、field path 定数の snapshot test を追加するとよい。
- [S4] `aggregate_session_blocks` 直呼びは `tests/` と `debug/devnotes` のみ許可、production modules では wrapper 必須、という許可リスト方式がよい。
- [S5] hypothesis 追加は妥当。ただし property test は最小ケース生成に留め、既存 deterministic tests を主にする方が診断性が高い。

## Round D1-D2 から残置の最終確認
- D1 C1-C6 は解消済み。特に半開区間、mode必須化、coverage inclusive、record schema 固定は詳細設計として十分。
- D2 C1 は path 形式への統一で解消済み。nested field の SSOT 不整合は消えている。
- D2 C2 は merge key reject で解消済み。alias/anchor は merge を使わない限り duplicate key 迂回にはならないため許容。
- D2 C3 は production wrapper 追加で解消済み。ただし F49 は grep ではなく AST/許可リスト方式が望ましい。

## test_id 1:1 ギャップ
- 重大なギャップなし。
- `F41_to_record_derived_field_paths_match` は `include_derived=False/True` の両方で path 集合を検証するとよい。
- `F49_production_callers_no_test_mode` は test名として妥当だが、実装は subprocess grep ではなく Python AST 解析推奨。
- `F14_yaml_duplicate_after_flatten` は命名だけ再調整推奨。

## YAML schema lint
- 5段構成は妥当。
- duplicate / merge key reject は loader test で固定可能。
- schema / period / coverage / OANDA checklist は専用 lint script + CI 実行に分離するのが現実的。
- production反映前 gate は「参照日」「一次資料URLまたは文書名」「確認者」「YAML差分」を機械的に要求する形式がよい。

## 学術文献 (任意)
- なし

## 総評
Round D2 の3 Critical は詳細設計レベルでは解消済みです。残っているのは実装時の enforce 方法、lint script 分離、ASTベースの production caller 検査といった運用強度の問題であり、TODO 登録を止める必修正ではありません。

この版は APPROVED でよいです。実装フェーズでは、field path helper、YAML lint script、production wrapper 呼び出し検査を最初に固定すると後続の T071/T064/T066 連携が安定します。