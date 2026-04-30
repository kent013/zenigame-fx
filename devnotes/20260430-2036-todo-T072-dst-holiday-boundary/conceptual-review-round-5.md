## Verdict
APPROVED

概念設計として確定して詳細設計に進んでよいです。残りは blocking ではなく、詳細設計・実装時の明文化とテストで潰せる範囲です。

## 前提 (C4)
- verified: H3=10800 は `M1_PLUS_GRANULARITIES` から除外され、I5 `28800 % granularity_seconds == 0` と整合している。
- verified: D/W は 8h session block の対象外として SSOT 明記された。
- verified: `open_minutes` が primary field、`expected_bar_count` / `schedule_status` は derived property で統一されている。
- verified: production mode では `broker_schedule` と `calendars` の片方欠落を reject する契約になっている。
- verified: broker schedule と market holiday observability の責務分離は維持されている。
- unverified: OANDA の full close / early close / partial close の YAML 内容自体は詳細設計で公式仕様・実データ確認が必要。

## Critical
- なし。

## Warning
- [W1] tolerance docstring の「ratio 1% は将来 H4 拡張用」は不正確です。H4 は expected が小さくなるため ratio 側は発火しません。現行 M1+ では実質常に abs=5 なので、「将来 sub-minute granularity 等への拡張用」または「現行では abs=5 固定」と書く方が正確です。
- [W2] `mode` default が `"test"` だと、production caller が指定漏れした場合に安全側へ倒れません。詳細設計では entrypoint 側で必ず `mode="production"` を渡すテストを入れてください。
- [W3] `to_record(include_derived=True)` は docstring contract なので、audit/export caller のテストで `schedule_status`, `expected_bar_count`, `all_g3_market_holiday` が出力されることを固定してください。
- [W4] closed_full の `bar_count >= 1 → WARNING`, `bar_count > 5 → ERROR` は妥当ですが、ログ名は `closed_full_unexpected_bars` のように通常 tolerance と別系列にした方が運用で混ざりません。

## Suggestion
- [S1] `M1_PLUS_GRANULARITIES` のコメントに「すべて 28800 を割り切る」と明記すると、H3 再追加の再発防止になります。
- [S2] `BrokerTradingSchedule.__post_init__` の検証項目は単体テスト名にそのまま落とせる粒度なので、詳細設計で test matrix 化してください。
- [S3] C22 calendars-only は test/debug 専用であることを、複合ケース表だけでなく関数 docstring にも入れると誤用が減ります。

## Round 1-4 から残置の最終確認
- Round 1 の universe / weekend / DST / holiday 粒度問題は解消済みです。
- Round 2 の broker schedule と market holiday 混同は解消済みです。
- Round 3 の `open_minutes` primary 化、date override、DST boundary semantics は解消済みです。
- Round 4 の H3 granularity 矛盾は解消済みです。
- blocking な残置はありません。

## 新規 Approved 部分
- `M1_PLUS_GRANULARITIES` 10 種類への確定は妥当です。
- D/W を session block 対象外にした SSOT は妥当です。
- closed_full と open block の tolerance 分離は妥当です。
- `date_overrides ∩ broker_full_close_holidays == ∅` の reject 原則は妥当です。
- production mode で schedule/calendar の片方欠落を reject する方針は妥当です。
- `to_record(include_derived=True)` を audit/export contract にする方針は妥当です。

## 学術文献 (任意)
- Andersen and Bollerslev (1998) “Deutsche Mark-Dollar Volatility: Intraday Activity Patterns, Macroeconomic Announcements, and Longer Run Dependencies.” 要確認。
- Dacorogna et al. (2001) “An Introduction to High-Frequency Finance.” 要確認。
- Goodhart and O’Hara (1997) “High Frequency Data in Financial Markets: Issues and Applications.” 要確認。
- IANA Time Zone Database / RFC 6557 / RFC 8536 は DST 管理の一次資料候補。要確認。
- OANDA 公式 trading hours / candle specification は broker schedule の一次資料として詳細設計で必ず確認対象。

## 総評
T072 の概念設計は APPROVED です。最終形は「T070 の UTC 8h partition は不変」「broker 配信可能性は `open_minutes`」「bar completeness は `expected_bar_count`」「holiday/DST は observability」という責務分離が明確で、T914 の session boundary contract として成立しています。

詳細設計では、YAML coverage validation、DST season table、date override、production mode reject、audit/export の derived fields をテストで固定するのが最重要です。特に OANDA 実仕様は設計値ではなく一次資料・実データで検証してください。