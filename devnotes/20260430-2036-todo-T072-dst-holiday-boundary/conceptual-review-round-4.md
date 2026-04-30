## Verdict
NEEDS_REVISION

概念設計はほぼ確定水準ですが、`M1_PLUS_GRANULARITIES` と I5 の SSOT 不整合が 1 点だけ Critical です。ここを直せば APPROVED 相当です。

## 前提 (C4)
- verified: `open_minutes` primary 化により、H4 Sunday NY reopen のような「open だが complete bar 0」の情報落ちは解消されている。
- verified: `expected_bar_count` と `schedule_status` は storage ではなく `open_minutes` 由来の derived property になっている。
- verified: `broker_schedule=None` 時も `open_minutes=480` なので、M5/H4 などで expected が granularity に応じて導出される。
- verified: broker schedule と market holiday observability は分離され、holiday が expected に混入しない。
- unverified: OANDA の early close / full close / partial close の実仕様と YAML 例の正確性。

## Critical
- [C1] `M1_PLUS_GRANULARITIES` に `10800` が含まれている一方、I5 は `28800 % granularity_seconds == 0` を要求しています。`28800 % 10800 = 7200` なので、H3 は invariant 違反です。8h session block を SSOT にするなら `10800` を除外してください。H3 を残すなら I5 を撤回し、bucket 境界を跨ぐ candle の帰属規則まで概念設計で定義する必要があります。

## Warning
- [W1] `tolerance = ceil(max(5, expected * 0.01))` は、M1+ かつ最大 expected=480 なら ratio 側が実質発火しません。常に 5 bar tolerance です。意図通りなら「M1 session で最大約1.04%許容」と明記してください。
- [W2] `expected_bar_count=0` の closed block にも tolerance 5 が適用されるため、closed_full で 1-5 bar が出ても warning threshold 内になります。full close は別 tolerance、または severity を上げる方が安全です。
- [W3] `date_overrides` と `broker_full_close_holidays` の重複は、reject か override 優先かを明文化してください。個人的には ambiguity 防止のため原則 reject、例外は `date_overrides` に集約がよいです。
- [W4] `date_overrides` が 1 日 1 window なので、同日内の split session は表現できません。OANDA で不要なら v1 制約として明記すれば十分です。
- [W5] 部分構成は test/debug 限定と書かれていますが、実装では誤って production に流れ得ます。詳細設計で warning log か `mode="production"` 時の reject を入れてください。
- [W6] `to_record(include_derived=False)` は backward compat に有利ですが、audit/export では derived が必須です。audit 系 caller は `include_derived=True` を使う、という contract を明記してください。

## Suggestion
- [S1] `M1_PLUS_GRANULARITIES` は `60,120,240,300,600,900,1800,3600,7200,14400` の 10 種類にするのが自然です。H3 は 8h block と相性が悪いです。
- [S2] `compute_expected_bar_count()` は floor でよいですが、「complete candle 数を数えるため floor」とコメント化すると H4/C18 の意図が伝わります。
- [S3] `BrokerTradingSchedule.__post_init__` で `date_overrides` の window 範囲、start/end 順序、coverage、season overlap、full close との重複を検証対象にしてください。
- [S4] Daily / Weekly granularity は session block の対象外と SSOT に明記してください。8h block と概念的に合いません。
- [S5] `all_g3_market_holiday` は approved でよいですが、derived property なので `to_record(include_derived=True)` に含めるかは明示してください。

## Round 1-3 から残置の最終確認
- Round 1 の universe / weekend / DST 食われ / holiday 粒度問題は解消済みです。
- Round 2 の broker schedule と market holiday 混同は解消済みです。
- Round 3 の `open_minutes` primary 化、granularity-aware default、date override、DST 境界規則は概ね解消済みです。
- 残置は Round 3 [W4] 系の granularity SSOT だけです。H3 と I5 が矛盾しています。

## 新規 Approved 部分
- `open_minutes` primary、`expected_bar_count` / `schedule_status` derived の設計は承認できます。
- `broker_schedule=None` 時に `open_minutes=480` とする default は granularity-aware で妥当です。
- `date_overrides > full close > weekly/DST` の優先順位設計は妥当です。ただし重複 validation 方針は要明記です。
- DST region の inclusive / disjoint / continuous cover は概念 SSOT として妥当です。
- market holiday を observability に限定し、expected に混ぜない方針は承認できます。
- collider bias 回避規範として「holiday_markets 単独 drop/filter 禁止、stratified audit」は妥当です。

## 学術文献 (任意)
- Andersen and Bollerslev (1998) “Deutsche Mark-Dollar Volatility: Intraday Activity Patterns, Macroeconomic Announcements, and Longer Run Dependencies.” 要確認。
- Dacorogna et al. (2001) “An Introduction to High-Frequency Finance.” 要確認。
- Goodhart and O’Hara (1997) “High Frequency Data in Financial Markets: Issues and Applications.” 要確認。
- IANA Time Zone Database / RFC 6557 / RFC 8536 は DST 管理の一次資料候補。要確認。
- broker session contract は学術文献より OANDA 公式 trading hours / candle specification を一次資料にするべきです。要確認。

## 総評
Round 4 は設計としてほぼ固まっています。`open_minutes` primary 化により、session boundary contract と bar completeness contract の分離ができており、T072 の役割名にも合っています。

ただし `10800` を許容しながら `28800 % granularity_seconds == 0` を invariant にするのは SSOT 不整合です。H3 を除外するだけなら概念設計の軽微修正で済みます。そこを直せば、概念設計は APPROVED として詳細設計に進めてよいです。