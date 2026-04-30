## Verdict
APPROVED

## 前提 (C4)
- レビュー対象は提示された Round 4 本文のみ。実ファイル確認はしていない。`Verified`
- `GraduationTriggerEvaluation` は dataclass 直接構築でも invariant を守る設計。`Verified`
- `recent_mission_pass_epoch_ids` は実測 diagnostic field で、partial pass を保持する。`Verified`
- AST grep DoD は production code 混入検出が目的で、case-sensitive 判定を採用する。`Verified`

## Critical
- なし

## Warning
- なし

## Suggestion
- [S1] F22j は `len(recent_mission_pass_epoch_ids) == recent_epochs_required` の fixture にして、`n_distinct_epochs < required` が I-2b で落ちることを固定するとよいです。
- [S2] `alias.asname` は必須ではありませんが、`import safe_module as archive` のような local binding も forbid したいなら検査対象に含めてください。
- [S3] `synthesis_schema_version: 22` は `synthesis.md` 冒頭の metadata block に置くのが最も監査しやすいです。別 file より SSOT が分散しません。
- [S4] case-sensitive 方針では `"HOLIDAY"` と `"dst_xxx"` は許容です。F27 の説明文にこの非検出例を明記すると誤解が減ります。

## Round D1-D3 から残置の最終確認
- D1 `[C1]`: 解消。`recent_epochs_required >= 1` は直接構築にも効く。
- D2 `[W1]`: 解消。partial pass diagnostic field 化は status invariant と整合。
- D3 `[W1]`: 解消。duplicate 禁止 + `n_distinct_epochs >= len(ids)` により ready の `n_distinct_epochs >= required` は導出可能。
- D3 `[W2-W4]`: 解消。tier1 exact、ImportFrom alias、case-sensitive substring は仕様として固定済み。
- 概念設計との整合: 問題なし。詳細側の invariant 強化であり、概念 Round 3 SSOT の改訂は不要。

## test_id 1:1 ギャップ
- なし。F22f/F22g/F22h/F22i/F22j と F27 系追加で Round D3 指摘は 1:1 に閉じています。
- 任意強化として、F27 に `import safe_module as archive` を許容/拒否どちらにするかの case を追加可能です。

## 学術文献 (任意)
- なし。今回の論点は設計 invariant と静的検査 contract です。

## 総評
T074 Phase 1 の詳細設計として確定可能です。`GraduationTriggerEvaluation` の status 別 invariant、cross-field invariant、partial diagnostic の意味論が揃い、直接構築でも破綻しにくい形になっています。

Phase 2 adapter contract も「A > B > C」の推奨順が明確になったため、Phase 1 実装は `graduation.py` と `test_graduation.py` に閉じて進めて問題ありません。TODO 登録 + commit に進んでよいです。