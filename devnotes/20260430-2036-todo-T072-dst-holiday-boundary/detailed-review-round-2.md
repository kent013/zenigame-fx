## Verdict
NEEDS_REVISION

## 前提 (C4)
- Round D1 の 6 Critical 対応は、提示テキスト上では概ね反映済み。
- 実コード未提示のため、PyYAML / pytest / caller 配線は設計テキスト上の実装可能性レビューに限定。
- Round 2 では新規設計穴のみを反証対象とし、概念 Round 5 の論点は再審査しない。

## Critical
- [C1] `SESSION_BLOCK_DERIVED_FIELDS` と `to_record` 出力形状が不整合。Fact: 定数では `all_g3_market_holiday` が derived field だが、擬似コードでは `record["observability_flags"]["all_g3_market_holiday"]` にネストされる。Interpretation: consumer が top-level field と nested field のどちらを読むべきか割れるため、SSOTとして未確定。
- [C2] `_DuplicateKeyRejectLoader` は `flatten_mapping` または merge key 禁止方針が未定義。Fact: PyYAML の `SafeConstructor.construct_mapping` は YAML merge key `<<` を処理するために `flatten_mapping` を使う。Interpretation: merge key 経由の重複・上書きが未検出または不定挙動になり、duplicate reject の保証が弱い。
- [C3] `mode="test"` の production code path 混入防止が設計上まだ構造化されていない。Fact: `mode` 必須化で指定漏れは防げるが、production caller が誤って `"test"` を渡すことは型上可能。Interpretation: DoD の grep/lint 方針だけでは North Star 系の実行経路を fail-open にしうる。

## Warning
- [W1] `RECORD_SCHEMA_VERSION` の bump 条件は明記された方がよい。特に field 追加、field 削除、nested path 変更、意味変更、型変更を MAJOR/MINOR/PATCH のどれで扱うか未定義。
- [W2] `SESSION_BLOCK_STORAGE_FIELDS` に `observability_flags` を含める設計は妥当だが、内部キーの schema version も固定しないと nested field 変更が検出しづらい。
- [W3] `dataset_span` は date 両端 inclusive、minute window は半開区間という二重規約は妥当だが、関数名・引数名に `_date` / `_minute` を付ける規約まで入れた方が誤用を減らせる。
- [W4] property-based test は有効だが、`hypothesis` 未導入なら依存追加の是非が未決。既存依存方針に合わせて「導入する」または「標準pytestの生成ループにする」を固定した方がよい。
- [W5] OANDA 一次資料ゲートは PR description だけでは弱い。production反映時のチェックリストに「参照日」「対象URL/文書名」「確認者」「YAML反映差分」を必須化した方がよい。

## Suggestion
- [S1] `all_g3_market_holiday` は top-level derived field に寄せるか、定数を `SESSION_BLOCK_DERIVED_FIELD_PATHS = ("observability_flags.all_g3_market_holiday", ...)` に変更する。
- [S2] YAML merge key `<<` はカレンダー設定では禁止が安全。duplicate reject loader 内で明示的に `ConstructorError` にすると監査しやすい。
- [S3] production caller は `aggregate_session_blocks_production(...)` の薄い wrapper からのみ呼ぶ設計にすると、`mode="test"` 混入を grep より強く防げる。
- [S4] C2 parallel-path grep は `SESSION_RANGES`, `BLOCK_BUCKET`, `bucket`, `open_window`, `schedule_status`, `expected_bar_count` も検索語に加えると漏れが減る。
- [S5] collider bias テンプレートには具体例として「holiday_markets で drop せず stratified audit」「n_archive_members は conditioning set を明記」を入れると下流PRで使いやすい。

## Round D1 から残置の最終確認
- D1 C1: 「3 field + 1 method」への修正は解消。
- D1 C2: duplicate key reject 方針は前進。ただし merge key 方針未定義で C2 として残る。
- D1 C3: 半開区間 `[start, end)` 統一は解消。境界値 `start == other_end` は overlap 0 で妥当。
- D1 C4: `mode` 必須化は指定漏れ対策として解消。ただし `"test"` 誤指定対策が残る。
- D1 C5: schema 定数化は前進。ただし derived field の top-level/nested 不整合が残る。
- D1 C6: inclusive coverage 明記は解消。

## test_id 1:1 ギャップ
- `Fxxx_<behavior>` 方針で旧枝番問題は概ね解消。
- 追加推奨: `F14_duplicate_key_rejects_merge_key_or_duplicate_after_flatten`。
- 追加推奨: `F41_to_record_derived_field_paths_match_schema_constants`。
- 追加推奨: `F49_production_callers_do_not_use_test_mode`。

## YAML schema lint
- duplicate key reject に加えて、YAML merge key `<<` を禁止または flatten 後に重複検出する方針を必須化。
- `date_overrides` / `broker_full_close_holidays` のキー型を `date` に正規化してから intersection 判定することを明記。
- CI lint は「schema検証」「duplicate/merge key検出」「period連続性」「coverage」「production gate checklist」の5段に分けると十分。

## 学術文献 (任意)
- なし。

## 総評
Round D1 の主要穴はかなり潰れていますが、`to_record` schema の field path 不整合と YAML merge key の扱いは詳細設計確定前に直すべきです。どちらも実装後に consumer や設定ファイル側へ波及しやすい設計境界です。

`mode` 必須化は良い修正ですが、production 経路で `"test"` を渡せる余地はまだ残ります。wrapper 化または lint 方針の具体化まで入れれば、Round 3 では APPROVED にかなり近いです。