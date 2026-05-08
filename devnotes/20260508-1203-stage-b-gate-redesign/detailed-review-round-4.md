**前提**
- Round 4 の貼付サマリのみで判定します。v3 全文・実コードは未読です。
- Round 3 の Critical 2 件は方向として大きく改善しています。
- ただし C9 で反証を探すと、`archive.flush` の一貫性検証に新しい抜けがあります。

**反証結果**
- T044 契約: 旧 `row["trade_count"] = tc` 分岐を「明示削除」と書いたため、意図は明確です。これは解消扱いでよいです。
- 二重 opt-in: `final_allow = rc_override AND rc_smoke` は、通常経路では env のみ / CLI のみ / なしを拒否できるため妥当です。
- 反例: `overrides = {None, True}` のような marker 伝搬漏れがある場合、`non_null = {True}` になり一貫性エラーを出さず、両 opt-in 時に flush を通します。これは「全 row 一貫性」契約を満たしません。
- 反例: `smoke_test_override=True` は public 引数のままだと二重 opt-in を bypass できます。test 専用なら許容可能ですが、名前と利用箇所で強く隔離すべきです。

**残指摘**
- [Critical] `archive.flush` の一貫性検証が `non_null` ベースのため、`{None, True}` / `{None, False}` を許容します。修正案: 新規 RUN の flush では `normalized_expected = bool(self._run_context.holdout_short_override)` とし、全 row が `normalized_expected` と一致することを要求してください。少なくとも `len(overrides) > 1` は即 raise に戻すべきです。
- [Warning] `smoke_test_override` は production code から渡せる形だと final guard を bypass できます。修正案: 引数を削除して tests も `RunContext` で表現するか、`_testing_smoke_test_override` に改名し、通常 callsite では使用禁止にしてください。
- [Warning] `_coerce_optional_int` の `type(value).__name__ in ("bool_", "bool8")` は NumPy バージョン差に弱いです。修正案: numpy 依存がある前提なら `isinstance(value, np.bool_)` を使う。追加で `int32` 上限も検証すると archive schema と整合します。
- [Suggestion] T044 の説明で `stage_gate.py 967 行付近 — 旧 collect_stage_b` とありますが、過去抜粋では `collect_stage_b` は `archive.py` です。設計書のファイル名を正してください。

**重点回答**
- `T044`: 明確化されています。旧分岐が実コードから削除されるなら解消です。
- `final_allow = AND`: 通常経路の二重 opt-in は保証できます。ただし `smoke_test_override` と `{None, True}` 混在が反例です。
- `_coerce_optional_int`: container / NaN / pd.NA / 非整数 / 負数は概ね可。NumPy bool 判定はまだ堅牢ではありません。
- `5 hours SLA`: `247min` に対して `300min` なので約 `53min` の余裕があり、run-52 見積りベースでは許容範囲です。
- 統合テスト: 5 consumer の正方向伝搬は cover できています。追加で mixed marker rejection の負方向テストが必要です。

**全体判定**
- CHANGES_REQUESTED
- 残る blocking は `archive.flush` の marker 一貫性検証です。ここを `None` 混在不可に修正し、`smoke_test_override` を test-only に閉じれば APPROVED にかなり近いです。