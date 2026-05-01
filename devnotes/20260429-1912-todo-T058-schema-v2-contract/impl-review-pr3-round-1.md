本分析の前提:
- Verified: コマンド実行・ファイル書込は行わず、提供テキストのみでレビューしています。
- Verified: PR 3 の目的は `dataset_epoch_id` を calibrate-gate history/state の追加 AND 条件にすることです。
- Verified: 提供テキスト上、`validate_epoch_id` は `SchemaContractError` を raise し、`from_dict_or_none` は `TypeError/ValueError` のみ捕捉します。
- Not verified: 実コード上で `SchemaContractError` が `ValueError` を継承しているか、正確な行番号、git 履歴、docs 本文は未確認です。

## verdict
REQUEST_CHANGES

## 主要 Findings (重要度順)

### [Critical]
1. `read_history` の invalid record skip 契約が、`SchemaContractError` 経路で破れる可能性があります。  
   Facts: `__post_init__` は `validate_epoch_id(dataset_epoch_id)` を呼び、提供テキストでは `SchemaContractError` raise と明記されています。一方、`from_dict_or_none` は `cls(**obj)` の例外として `TypeError/ValueError` しか捕捉しない説明です。  
   Interpretation: `dataset_epoch_id="bad-epoch"` のような v2 invalid record は `None` skip + warning ではなく loader crash になり、施策 5 の passive/read skip 契約に反します。`SchemaContractError` が `ValueError` 継承ならこの指摘は解消ですが、未確認のため変更要求です。

   修正対象: `src/alpha_factory/calibrate_gate_history.py` の `HistoryRecord.from_dict_or_none` の `except` 節（実ファイル行番号は提供テキストに無く、コマンド禁止のため未特定）。

   修正案:
   ```python
   from alpha_factory.schema_contract import (
       CALIBRATE_HISTORY_SCHEMA_VERSION,
       SchemaContractError,
       SchemaEnforcementMode,
       assert_calibrate_history_v2,
       validate_epoch_id,
   )

   @classmethod
   def from_dict_or_none(cls, obj: dict[str, Any]) -> "HistoryRecord | None":
       if not obj.get("dataset_epoch_id"):
           return None
       if obj.get("calibrate_history_schema_version") != CALIBRATE_HISTORY_SCHEMA_VERSION:
           return None
       try:
           return cls(**obj)
       except (TypeError, ValueError, SchemaContractError):
           return None
   ```

2. `read_history` の invalid grammar record を直接検証するテストが不足しています。  
   追加すべきケースは、`calibrate_history_schema_version=2` かつ `dataset_epoch_id` が存在するが grammar invalid な JSONL record が、例外ではなく skip されることです。

   追加テスト案:
   ```python
   def test_read_history_skips_v2_record_with_invalid_epoch_id(tmp_path: Path) -> None:
       path = tmp_path / "history.jsonl"
       record = _record_dict(
           calibrate_history_schema_version=2,
           dataset_epoch_id="bad-epoch",
       )
       path.write_text(json.dumps(record) + "\n", encoding="utf-8")

       assert read_history(path) == []
   ```

### [Warning]
1. `dataset_epoch_id: str = ""` は default を持ちますが、`__post_init__` で空文字 reject されるため、実質的な旧 constructor 互換はありません。既存 caller が全て更新済みなら問題は限定的ですが、「default 値で keyword 互換」という説明は behavioral compat としては弱いです。

2. T067 移行性は方針として妥当ですが、実装コメントの存在は未確認です。`dataset_span` guard の直後に `dataset_epoch_id` guard があり、「T067 では dataset_span 行のみ削除」と読めるコメントがあることを確認してください。

3. `epoch_legacy` の literal が `calibrate_gate.py` と `run_ga.py` に重複しています。PR 5 で RunContext へ移る前提なら許容範囲ですが、転記漏れ再発パターンを考えると短期定数化も検討余地があります。

### [Suggestion]
1. 観点 1 / 3 / 7 は、提供テキスト上は概ね整合しています。`HistoryRecord` 書込、`_record_matches` 読込、`run_ga.py` 呼出の `epoch_legacy` は同一値で、初期通過条件は満たす設計です。

2. 観点 2 の `append_record(record, path)` positional 互換、`load_calibrated_threshold` keyword 呼出互換は、提供テキスト上は問題ありません。

3. 観点 4 は Critical 指摘の修正後に APPROVED 相当です。`append_record` の LOG_ONLY passive lint と `HistoryRecord` construction-time validation の責務分離自体は妥当です。