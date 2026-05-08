**前提**
- ローカル `Read` は実施せず、Round 3 の対応報告だけを根拠に判定します。v2 全文との完全一致は未検証です。
- DSR を Phase 2 に移動した判断は妥当です。Round 2 の DSR 数式 Critical は Phase 1 設計からは解消扱いです。
- ただし貼付内容だけでも、二重 opt-in の最終 guard と T044 契約の表現にまだ blocking 懸念があります。

**判定サマリ**
- 施策 1: APPROVE
- 施策 2: REQUEST_CHANGES
- 施策 3: REQUEST_CHANGES
- DSR Phase 2 移動: APPROVE
- 全体判定: CHANGES_REQUESTED

**残指摘**
- [Critical] 施策 2: T044 対応の文言が曖昧です。「既存 `row["trade_count"]` 上書き経路は触らず」が、旧 `collect_stage_b` の `row["trade_count"] = tc` 分岐を残す意味なら未解消です。修正案: `collect_stage_b` から既存 `trade_count` 上書き分岐を削除または到達不能化し、`test_collect_stage_b_does_not_overwrite_stage_a_trade_count` で Stage A 値固定を直接検証してください。
- [Critical] 施策 3: `archive.flush(smoke_test=self._run_context.smoke_test_mode)` だけでは archive 層で二重 opt-in を保証できません。`ZENIGAME_FX_SMOKE_TEST=1` だけで `holdout_short_override=True` row を許容し得ます。修正案: flush では `True in non_null` を許す条件を `self._run_context.holdout_short_override is True and self._run_context.smoke_test_mode is True` に限定してください。
- [Warning] 施策 2: `_coerce_optional_int` は `None` / `NaN` / `pd.NA` / list / tuple / dict は概ね catch できますが、`np.bool_(True)`、非整数 float、負数を受け入れ得ます。修正案: `bool` と `np.bool_` を拒否し、`float_value.is_integer()` と `>= 0` を要求してください。
- [Warning] 施策 2: +37% で `180min → 247min` は 4 時間 SLA を超えます。improve-cycle が 4 時間以下で kill する設定なら運用上未承認です。修正案: timeout / runbook を 5 時間以上に更新するか、Stage B full pass の計測ログで実 RUN 前に budget check してください。
- [Warning] 施策 3: `_check_graduation(..., run_context)` と `append_record(..., run_context)` の signature 変更は呼び出し元影響が広い可能性があります。修正案: 全 callsite 更新に加え、smoke override 時に graduation / calibrate / report / archive が同じ `RunContext` を参照する統合テストを追加してください。

**重点回答**
- `_coerce_optional_int`: pd.NA は `if value != value` の TypeError catch で落とせるため概ね可。ただし `np.bool_`、小数 truncation、負数が残るため Warning。
- `IndividualCacheEntry`: default 付き field を末尾追加なら既存 constructor fixture 互換性は基本維持されます。位置引数で全 field を厳密比較する特殊テストのみ要確認。
- コスト +37%: 4 時間 cycle 前提なら許容不可寄りです。247 分は overhead なしでも 240 分を超えます。
- `RunContext` frozen 追加: default 付き field 追加なら immutability 契約は壊しません。ただし hash/equality 利用があれば影響確認が必要です。
- `flush(smoke_test=None)`: SSOT は `run_context` でよいですが、引数 override は test 専用に限定し、最終許可条件は `smoke_test_mode AND holdout_short_override` にしてください。
- signature 変更: 設計としては安全側ですが、全 callsite 更新と統合テストが必須です。

**全体判定**
- CHANGES_REQUESTED
- DSR 除外と NaN fallback 方針は大きく改善していますが、T044 契約の曖昧さと archive flush の二重 opt-in 不完全性は North Star と安全運用に直結するため、v2 はまだ承認できません。