## Verdict
NEEDS_REVISION

## 前提 (C4)
- verified: T070 の bucket 境界・UTC date universe・`compute_bucket_for_*` を不変にする方針は維持されている。
- verified: broker 配信 schedule と market holiday observability は Round 3 で分離され、Round 2 の最大問題は概ね解消されている。
- verified: `expected_bar_count` が primary、`schedule_status` が derived property になっている。
- verified: `aggregate_session_blocks()` は `broker_schedule` / `calendars` の部分構成を許容している。
- unverified: OANDA の broker full close / early close / holiday partial close の実仕様。
- unverified: `utils/time.py` 側の granularity 定義と T072 の I7 が一致していること。

## Critical (必修正)
- [C1] `broker_schedule is None` 時の `expected=480` が granularity-aware 設計を破壊します。`granularity_seconds=300` なら bucket full bars は 96 なので、`expected=480` は I6 に違反します。互換 default は `compute_expected_bar_count(480, granularity_seconds)` にするべきです。
- [C2] `schedule_status` を `expected_bar_count` から導出すると、粗い granularity で partial open が消えます。例: H4 で Sunday NY open 120 分なら `expected_bar_count=0` になり、実際は 2 時間 open なのに `closed_full` になります。`open_minutes` を primary field として保持し、`schedule_status` は `open_minutes` から導出する必要があります。
- [C3] `BrokerTradingSchedule` が `broker_full_close_holidays` しか持たないため、broker holiday の early close / late open / partial close を表現できません。T072 は holiday session boundary contract なので、概念設計段階で `broker_special_windows: date -> (start_min,end_min)` か同等の override を SSOT に含めるべきです。
- [C4] `dst_aware_close_table` の境界日 semantics が未確定です。DST 開始週末では Friday close は standard、Sunday reopen は DST になり得ます。`region_start/end` の inclusive 規則、Friday/Sunday それぞれがどの date の spec を採るか、coverage non-overlap validation は概念設計で確定してください。

## Warning (要検討、詳細設計可)
- [W1] `schedule_status` が `asdict()` に出ないため、audit/export consumer が見落とすリスクがあります。`to_record(include_derived=True)` か exporter 側の明示計算を contract 化した方が安全です。
- [W2] `broker_schedule` / `calendars` の部分構成許容は半端 state を作ります。T070 互換の `both None` と T072 本番の `both provided` を基本にし、片方のみは test/debug 限定にする方が明確です。
- [W3] `holiday_markets` を caller 委譲にしただけでは collider bias 回避は保証されません。T071/T064/T066 への申し送りとして「holiday_markets 単独で drop/filter しない、必ず stratified audit する」程度の統一指針が必要です。
- [W4] I7 の granularity 許容値が `utils/time.py` の 12 種類と不一致です。M1 以上限定なら「session block は M1+ の complete candle 前提」と明記し、S5/S10/S15/S30 を意図的に除外してください。
- [W5] `tolerance = max(5, expected * 0.01)` は float になります。概念上は `ceil(max(abs_tolerance, expected * ratio_tolerance))` として整数 bar tolerance に固定した方がよいです。
- [W6] `broker_full_close_holidays` は公式仕様ではなく経験則になる可能性があります。YAML schema に `source`, `verified_at`, `confidence`, `notes` を入れるべきです。

## Suggestion (改善案)
- [S1] `SessionBlock` に `open_minutes: int = 480` を追加し、`expected_bar_count` は `open_minutes` と `granularity_seconds` からの derived または検証済み storage にしてください。
- [S2] `BrokerTradingSchedule.open_window_for_utc_date()` は最終的に `date_overrides` を最優先、次に weekly/DST season、最後に weekday default の順にすると拡張しやすいです。
- [S3] 複合ケース表に `H4 Sunday NY reopen`, `Christmas Eve early close`, `DST start Friday close vs Sunday reopen`, `calendars only prohibited/debug` を追加してください。
- [S4] `validate_calendar_coverage()` は market calendar だけでなく broker schedule の seasonal table / override coverage / overlap absence も検証対象にしてください。
- [S5] `has_all_g3_holidays` は事実系 property として許容できますが、audit 名では `all_g3_market_holiday` のように market holiday であることを明示すると誤読が減ります。

## Round 1-2 から残置の最終確認
- Round 2 [C1] は大部分解消済みですが、DST season 境界日の採用規則が未確定です。
- Round 2 [C2] は解消済みです。market holiday は expected から分離されています。
- Round 2 [C3] は T072 内では解消済みですが、下流 caller への bias 回避指針が未確定です。
- Round 2 [C4] は一部残置です。`expected_bar_count` primary 化で改善しましたが、粗い granularity では `open_minutes` なしに partial 強度を保持できません。
- Round 2 [C5] は一部残置です。480 invariant は消えましたが、`broker_schedule is None` の default 480 が残っています。

## 新規 Approved 部分
- broker 配信 schedule と market holiday observability の責務分離は正しいです。
- `is_bucket_eligible_for_pattern` 削除は妥当です。T072 が分母除外を決めない方が安全です。
- `dst_transition_markets` / `holiday_markets` の frozenset 化は、観測事実を失わない設計として妥当です。
- per-call `ValueError` をやめ、load 時 validation に寄せた判断は妥当です。
- synthesis Round 22 を同期または先 merge にする方針は妥当です。

## 学術文献 (任意)
- Andersen and Bollerslev (1998) “Deutsche Mark-Dollar Volatility: Intraday Activity Patterns, Macroeconomic Announcements, and Longer Run Dependencies.” 要確認。
- Dacorogna et al. (2001) “An Introduction to High-Frequency Finance.” 要確認。
- Müller et al. (1990) “Statistical Study of Foreign Exchange Rates, Empirical Evidence of a Price Change Scaling Law, and Intraday Analysis.” 要確認。
- Goodhart and O’Hara (1997) “High Frequency Data in Financial Markets: Issues and Applications.” 要確認。
- OANDA trading hours / candle specification は broker schedule の一次資料として必須確認。要確認。
- IANA Time Zone Database / RFC 6557 / RFC 8536 は DST operational dependency の一次資料候補。要確認。

## 総評
Round 3 は設計方向としてかなり良くなっています。特に broker schedule と market holiday の分離、eligibility 削除、observability の frozenset 化は概念設計として承認できる水準です。

ただし最終確定前に、`open_minutes` を SSOT primary に昇格する修正が必要です。現状は `expected_bar_count` primary のため、H4 など粗い granularity で「開いていたが complete bar は 0」という session boundary 事実を失います。あわせて `broker_schedule is None` の 480 default と broker early-close override を直せば、Round 4 では APPROVED にかなり近いです。