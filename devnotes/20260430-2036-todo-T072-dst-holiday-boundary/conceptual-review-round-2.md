## Verdict
NEEDS_REVISION

## 前提 (C4)
- verified: Round 2 は T070 の bucket 境界・bucket 割当・date universe を変更しない前提で設計されている。
- verified: `schedule_status` と `observability_flags` の 2 軸分離により、Round 1 の「DST が weekend に食われる」問題は構造上かなり改善している。
- verified: `expected_bar_count` は固定 480 から overlap 駆動へ改訂されている。
- verified: `BrokerSession` は週次 reopen/close を UTC hour 固定値として持つ設計で、DST season の 21/22 UTC 差は未解決として残っている。
- verified: 本レビューは提示テキストのみを対象にした概念設計レビューであり、実コード・OANDA 実データ・既存 caller は未確認。

## Critical (必修正、Round 3 で解消)
- [C1] `BrokerSession` の UTC hour 固定は概念設計として不十分です。OANDA の close/reopen が DST season で 21 UTC / 22 UTC に変わるなら、ズレは DST transition day だけでなく season 全体に発生します。`observability_flags.is_dst_transition` で audit しても expected の誤計算は修正されません。`BrokerSession` は固定 hour ではなく `open_window_for_utc_date(d) -> [start_min,end_min]` のような date-aware contract にする必要があります。
- [C2] `compute_bucket_open_minutes()` が `bucket_market in holiday_markets` で expected を 0 にするのは、OANDA holiday bar 前提と矛盾します。Round 2 本文は「holiday は通常 bar 配信あり」と書いている一方、Tokyo holiday の Tokyo bucket を `closed_full` にします。これは broker availability と market holiday observability を混同しています。holiday は原則 `observability_flags` / eligibility 側に留め、expected bar は broker session close と broker full-close holiday だけで決めるべきです。
- [C3] `is_bucket_eligible_for_pattern()` が bucket 同字面の market holiday だけで分母除外する設計は、T071 の意味論としてまだ危険です。FX の Tokyo/London/NY bucket は物理取引所ではなく流動性時間帯であり、Tokyo holiday でも Tokyo 時間帯に EUR/USD や USD/JPY の取引 bar は存在します。`holiday_markets` は観測特徴として有用ですが、pattern eligibility の分母から即除外するのは成績・entropy の conditioning を変え、collider bias を生みます。
- [C4] `closed_partial` が 120 分と 360 分を同じ enum に潰す設計は、下流の fold pooled / entropy で情報落ちします。`expected_bar_count` は保持されますが、`schedule_status` だけを読む consumer が必ず出ます。概念 SSOT として `open_minutes` または `expected_bar_count` を primary field とし、`closed_partial` は derived label と明記すべきです。
- [C5] `schedule_status="regular" -> expected_bar_count == 480` はまだ M1 8h bucket 前提を invariant 化しています。T072 が session boundary contract なら、granularity と bucket duration から `expected_bar_count` を導出する契約に寄せるべきです。将来 M5/H1 に変えた瞬間に enum invariant が壊れます。

## Warning (要検討、詳細設計で解消可)
- [W1] `ObservabilityFlags.is_dst_transition` が business_date 単位だと、「London DST transition が NY bucket にも付く」など bucket-local な説明力が落ちます。v1 で許容するなら `dst_transition_markets: frozenset[MarketCode]` の方が誤解が少ないです。
- [W2] `is_g3_holiday` は `len(holiday_markets)==3` の事実系 derived property なので `is_business_day` ほど危険ではありません。ただし下流が「全休」と解釈しやすいため、名前は `has_all_g3_holidays` の方が安全です。
- [W3] `validate_calendar_coverage()` と per-call `ValueError` の併存は設計が二重になります。概念設計では「coverage は load 時に必須検証、contains は検証済 calendar の raw lookup」と一本化した方が caller 契約が明確です。
- [W4] `HolidayCalendar` は市場祝日、`BrokerSession` は broker 配信時間、`BrokerHolidayCalendar` は broker full-close/early-close として分離した方がよいです。現案は市場祝日を broker close に使っており責務が混ざっています。
- [W5] synthesis Round 22 の文言改訂は本 PR より先、または同一 PR 内で先に読む位置に置くべきです。改訂前 merge だと T072 が上位 SSOT と一時的に矛盾します。
- [W6] `bar_count <= expected + tolerance` は絶対値 5 本だけでなく、`max(abs_tolerance, ratio_tolerance)` または status 別 tolerance を概念で要求した方が安全です。特に expected=120 で 5 本は相対的に大きいです。
- [W7] backward-compat の `eq/hash` claim はまだ要注意です。default field 追加後の dataclass equality は「旧オブジェクト」と比較できるわけではなく、既存 fixture の期待値形式に依存します。

## Suggestion (改善案)
- [S1] `BrokerSession` を `BrokerTradingSchedule` に改名し、`open_minutes_for_bucket(date,bucket)` を SSOT API にしてください。名前が役割を示し、DST/early close/holiday close を内包できます。
- [S2] `MarketHolidayCalendar` と `BrokerTradingCalendar` を分けてください。前者は observability、後者は expected bar count に使う、という責務分離が最も重要です。
- [S3] `is_bucket_eligible_for_pattern` は boolean ではなく `PatternEligibility(reason: Literal[...])` か、最低でも `eligible_by_schedule` と `holiday_markets` を併読する契約にしてください。
- [S4] `schedule_status` は storage field ではなく `expected_bar_count` からの derived value にする選択肢を検討してください。SSOT が 1 つになり、partial 強度の情報落ちを避けられます。
- [S5] Round 3 では複合ケース表を概念設計に追加してください。例は `Fri ny DST season`, `Sun ny DST season`, `Tokyo holiday Tokyo bucket`, `Christmas all buckets`, `London DST day ny bucket` が最低限です。

## Round 1 から残置 (= Round 2 で潰せていない指摘の再確認)
- Round 1 [C5] は一部残置です。480 hard-code は弱まったものの、`regular=480` invariant と M1 前提がまだ API に残っています。
- Round 1 [C4] は形を変えて残置です。`holiday_partial` の粒度問題は解消しましたが、今度は `bucket -> physical market` の eligibility が強すぎます。
- Round 1 [S5] は一部未反映です。load 時集約に寄せた点は良いですが、per-call fail-closed も残したため caller 契約が二重です。

## 新規 Approved 部分
- 2 軸分離は方向性として正しいです。`schedule_status` と `observability_flags` を混ぜない方針は維持すべきです。
- T070 date universe を変えず、universe 内 block のみ mark する整理は妥当です。
- `expected_bar_count` を overlap 駆動へ寄せた方向性は正しいです。ただし broker schedule と market holiday の入力分離が必要です。
- `is_business_day` を削除した判断は妥当です。
- synthesis §4.1 の「24/7 fill」文言を改訂対象にした判断は妥当です。

## 学術文献 (任意)
- Andersen and Bollerslev (1998) “Deutsche Mark-Dollar Volatility: Intraday Activity Patterns, Macroeconomic Announcements, and Longer Run Dependencies.” 要確認。
- Dacorogna et al. (2001) “An Introduction to High-Frequency Finance.” 要確認。
- Müller et al. (1990) “Statistical Study of Foreign Exchange Rates, Empirical Evidence of a Price Change Scaling Law, and Intraday Analysis.” 要確認。
- Gençay, Dacorogna, Müller, Pictet (2001) “An Introduction to High-Frequency Finance.” 版・章立て要確認。
- IANA Time Zone Database / RFC 6557 / RFC 8536 は timezone operational dependency の一次資料候補。要確認。

## 総評
Round 2 は Round 1 の構造問題をかなり潰していますが、新たな中核リスクは「broker 配信 schedule」と「市場 holiday / session 解釈」を同じ計算に入れてしまった点です。expected bar count は broker が bar を出すかどうかの契約であり、市場祝日は原則 observability と下流解釈の入力です。

Round 3 で最優先に直すべきは、`BrokerSession` を date-aware な broker trading schedule に拡張すること、そして market holiday を expected bar count から分離することです。この 2 点が解消すれば、残りは詳細設計で潰せるレベルに近づきます。