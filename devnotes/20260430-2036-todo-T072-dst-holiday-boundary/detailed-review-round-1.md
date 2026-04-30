## Verdict
NEEDS_REVISION

## 前提 (C4)
- 概念設計 Round 5 APPROVED の 8 前提は正として扱う（再反証対象外）。
- 反証対象は、提示された詳細設計テキストのみ（実コード未提示）。
- したがって、実装依存の事項は `INCONCLUSIVE` を許容しつつ、設計上の不整合・未規定を優先して指摘する。

## Critical (必修正)
- [C1] `SessionBlock` の「4 field 追加」に対し列挙が3つ（`open_minutes`, `granularity_seconds`, `observability_flags`）しかない。  
  Fact: 仕様文内で個数不一致。  
  Interpretation: SSOT整合違反で、実装者ごとに第4フィールド解釈が割れる。
- [C2] `I-8: date_overrides は Mapping 型で1日1windowを構造保証` は成立しない。  
  Fact: YAMLはローダ設定次第で重複キーを最後勝ちで黙って上書きしうる。  
  Interpretation: `__post_init__` 検証前に情報欠落し、Invariant担保が破綻する。
- [C3] `compute_bucket_open_minutes` の境界契約（閉区間/半開区間）が未明記。  
  Fact: `max(0, min(end, open_end) - max(start, open_start))` は半開区間 `[start,end)` 前提でのみ一意。  
  Interpretation: `start == open_end` / `end == open_start` の扱いが実装者依存になり、off-by-oneリスクが残る。
- [C4] `aggregate_session_blocks` の `mode` 既定が `"test"` のままだと、production caller 指定漏れを fail-open で通す。  
  Fact: Round 5 [W2] で production 部分構成 reject を強化したのに、既定値で回避可能。  
  Interpretation: North Starに対する安全性要件と逆行。
- [C5] `to_record(include_derived=True)` の出力スキーマが未固定。  
  Fact: 本文に derived項目の完全列挙がなく、`all_g3_market_holiday` などテスト要求との対応が曖昧。  
  Interpretation: 将来フィールド追加時に監査/export互換性が壊れる。
- [C6] `validate_calendar_coverage` の `start/end` 包含規約が未定義。  
  Fact: F50-F53が境界テスト対象なのに、仕様側で inclusive/exclusive が明文化されていない。  
  Interpretation: coverage pass/fail が実装差で揺れる。

## Warning (要検討、 実装時で解消可)
- [W1] `__post_init__` 8 invariant の検証順序依存（特に I-7 は I-5/I-6 正規化後でないと誤判定しうる）を明文化した方が良い。
- [W2] `compute_expected_bar_count` で 0 本（例: 120分×H4）が仕様意図どおりかは設計上明記済みに見えるが、利用側の期待値（最低1本期待）とのズレ注意。
- [W3] `closed_full` 別logger系列は良いが、`__post_init__` 内でのlogger取得方針（module-level固定推奨）を決めないとログ分散しやすい。
- [W4] OANDA一次資料根拠は「TODO残し」自体は許容だが、Phase 2導入ゲート（未確認ならproduction反映禁止）をDoDに入れるべき。
- [W5] C2 parallel-path は現状 `INCONCLUSIVE`。`src/utils/time.py` / `T060 period UTC` / primitive側への影響確認タスクをDoDに明示すべき。

## Suggestion (改善案)
- [S1] `mode` はデフォルト廃止（必須引数）またはデフォルト `"production"` に変更。
- [S2] 全window/periodを `[start_minute, end_minute)` と明記し、`open_window_for_utc_date` と coverage 判定で共通契約化。
- [S3] `to_record` に `record_schema_version` を導入し、`storage_fields` と `derived_fields` を定数で固定。
- [S4] Broker schedule は表形式テストに加えて property-based test（連続cover/非重複）を1本入れると強い。
- [S5] PR description 用に collider bias 規範テンプレート（Fact/Interpretation/Conditioning set）を定型文で定義。

## test_id 1:1 ギャップ (= 詳細 vs 実装の test 名整合)
- `F1-F4` と `F5-F7` で `is_market_holiday` が重複記載され、責務境界が不明。
- `F8-F14d`, `F37i`, `F44b`, `F49c` のような枝番表記は pytest名と1:1対応しにくい。
- `F41b` で要求される `include_derived=True` 出力項目が仕様側で未列挙。
- 対策: `Fxxx_<behavior>` 形式で一意IDを固定し、設計書に「ID ↔ test関数名」を明示。

## YAML schema lint
- duplicate key reject を強制するローダ設定を必須化（`date_overrides` のI-8担保）。
- schema検証をCIに追加（必須キー、型、period範囲、region連続cover、重複/隙間）。
- `dst_aware_close_table` は開始日・終了日の連結条件を機械検証するルールを明文化。
- production投入前チェックとして「YAML lint + coverage validate + invariant tests pass」をDoDに追記。

## 学術文献 (任意)
- なし（本レビューは設計整合性監査が主対象）。

## 総評
設計の方向性は概念 Round 5 の改善をよく継承しており、特に schedule と observability 分離、production 部分構成 reject 方針は妥当です。一方で、詳細設計としては「境界契約の明文化不足」「YAML重複キー前提の誤り」「mode既定値による安全性低下」「to_recordスキーマ未固定」が残っており、現時点で `APPROVED` は難しいです。

上記 Critical を潰せば、実装フェーズでの解釈ブレと監査不整合をかなり抑えられます。特に C2/C3/C4/C5 は、実装後に直すより設計段階で固定した方がコストが低いです。