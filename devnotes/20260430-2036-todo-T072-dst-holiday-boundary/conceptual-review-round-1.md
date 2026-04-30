## Verdict
NEEDS_REVISION

## 前提 (C4)
- verified: T070 SSOT は `BLOCK_BUCKET_RANGES_UTC` 不変、`compute_bucket_for_bar()` 不変、date universe SSOT は「`bars + trades` が touched した UTC date set × 3 bucket」。
- verified: T072 概念設計は T070 の bucket 境界を動かさず、別 layer で calendar contract を追加する方針を明示している。
- verified: T071 の `session_pass_pattern` は T072 の non-business block contract に依存している。
- verified: 提示テキスト上、OANDA M1 は「週末 bar 不在」「holiday は 480 bar 想定」という前提で書かれている。
- unverified: OANDA の holiday/full-holiday 時の実 bar 配信が常に 480 であること。
- unverified: 実行環境の `zoneinfo` / tzdata が 2024-2027 の DST transition を常に正しく持つこと。
- scope note: 以下は提示された設計本文だけを対象にした概念設計レビューであり、実コード確認はしていない。

## Critical (必修正、概念設計確定の前に解消)
- [C1] 事実: T070 の date universe SSOT は touched UTC date set × 3 bucket で、週末に `bars=0` かつ `trades=0` ならその UTC date 自体が universe に入らない。解釈: 現案の「週末の `(date, bucket)` を機械判定し `block_status="weekend"` で mark」は、T070 SSOT を変えない限り実現不能です。`aggregate_session_blocks()` の現擬似コードでも weekend synthetic block は生成されません。
- [C2] 事実: `is_weekend(d) = d.weekday() in (5,6)` と `expected_bar_count=0 if weekend else 480` を invariant にしている。一方で本文自身が「金曜 NY close ～ 日曜 NY 22:00 UTC」の gap を問題設定に置いています。解釈: FX の週境界は UTC date 単位ではなく、少なくとも金曜 NY bucket / 日曜 NY bucket に部分営業が混じります。現案だと日曜 22:00-24:00 UTC の実 bar がある場合に `weekend + expected=0` と衝突し、金曜 NY bucket は正当な部分営業なのに `is_partial_bar_block=True` の偽陽性になります。T914 の本丸である「holiday session boundary contract」が date-based weekend 判定で壊れています。
- [C3] 事実: 判定優先順位は `weekend > dst_transition > ...`、`is_dst_transition()` は London/NY の DST 切替日を date 単位で返す設計です。London/NY の DST 切替は通常日曜です。解釈: `dst_transition` はほぼ常に `weekend` に食われ、実質到達不能です。今の enum は disjoint ですが、その代償で DST observability を失っています。`dst_transition` を status に載せる設計目的と整合していません。
- [C4] 事実: `holiday_partial` は「3 市場のうち 1-2 市場 holiday」を block 単位の単一 enum に潰し、`is_business_day` は `holiday_partial` を全 bucket で `True` にしています。解釈: これは T071/T066 の hard dependency に対して粒度が間違っています。たとえば Tokyo holiday でも London/NY bucket まで一律 `holiday_partial` になり、逆に Tokyo bucket は `is_business_day=True` のままです。`session_pass_pattern` の 3 bit は bucket ごとの営業性を見たいのに、現案は「グローバル日付属性」を block に上書きしており、分母契約を定義できていません。
- [C5] 事実: `expected_bar_count=480` を `regular/dst_transition/holiday_*` の invariant に昇格しています。解釈: これは OANDA の経験則を SSOT 化しすぎです。full holiday、partial holiday、週跨ぎ reopen/close bucket、将来 granularity 変更のいずれにも耐えません。少なくとも概念設計段階で invariant にしてはいけません。ここを固定すると T070 backward-compat 以前に `is_partial_bar_block` の意味が壊れます。
- [C6] 事実: backward-compat の根拠が「default field を足すだけ」に寄っています。解釈: dataclass 追加 field は `eq/hash/repr/asdict/serialization/snapshot` の public surface を変えます。さらに `__post_init__` に新 invariant を足すと、既存 builder/test fixture/round-trip のどこかで暗黙破壊が起こりえます。互換 claim を概念設計 SSOT に入れるなら、「何を互換対象とするか」を先に列挙すべきです。

## Warning (要検討、詳細設計で解消可)
- [W1] 事実: static YAML を採用し、library 依存を避ける方針自体は deterministic です。解釈: ただし `source`, `published_by`, `last_verified_at`, `coverage_start/end` など provenance が schema に無いと、更新漏れ検知が人依存になります。
- [W2] 事実: `holiday_partial` が「1 市場 holiday」と「2 市場 holiday」を同じ箱に入れます。解釈: 下流で pass rate / SR / entropy をこの status で集計すると collider 的に異質 regime を混ぜやすく、C3/C6 違反の温床になります。
- [W3] 事実: T072 は mark only と言いつつ `is_business_day` を dataclass property として新設しています。解釈: これは意味づけを下流に委ねる方針と矛盾します。概念設計では property を消すか、「観測事実」だけに限定した命名へ落とす方が安全です。
- [W4] 事実: `contains()` が period 外で毎回 `ValueError` を投げる設計です。解釈: fail-closed 自体は妥当ですが、per-call 例外よりも calendar load 時に run span を一括検証した方が安全で実装も単純です。
- [W5] 事実: `24/7 fill` という synthesis wording と、OANDA の「週末 no bar」前提が共存しています。解釈: 文書上の曖昧さが今回の設計ブレを生んでいます。Round 22 改訂候補は高優先です。
- [W6] 事実: zoneinfo 依存の補強策として unit test を予定しています。解釈: それだけでも最低限は成立しますが、runtime で tzdata version を observability に出す設計があると運用上さらに強いです。
- [W7] 事実: `business_date = UTC date` を守る方針は明示されています。解釈: これは bucket partition SSOT とは整合しますが、「market local holiday date」との対応は設計注記で明文化しておかないと、将来の誤読ポイントになります。

## Suggestion (改善案)
- [S1] `block_status` 1 本ではなく、少なくとも 2 軸に分けてください。`schedule_status`（`regular / closed_full / closed_partial` など）と `observability_flags`（`dst_transition`, `holiday_markets`）を分離した方が SSOT が崩れません。
- [S2] `expected_bar_count` は enum から決めず、「その bucket の UTC 区間と broker の週次 open/close 区間の overlap 分数」から導出する契約にしてください。これなら金曜 close / 日曜 reopen / DST / holiday short session を同じ枠組みで扱えます。
- [S3] T071 依存を先に潰すべきです。`session_pass_pattern` 用には `is_bucket_eligible_for_pattern` のような bucket-local 契約を別に置き、`holiday_partial` の global tag と切り離してください。
- [S4] `is_business_day` は概念設計から外し、詳細設計に送るのが無難です。今の粒度では事実ではなく解釈です。
- [S5] fail-closed は `HolidayCalendar.contains()` ではなく `validate_calendar_coverage(dataset_span)` の単発チェックに寄せると、caller が try/except 地獄になりません。
- [S6] synthesis §4.1 は本 PR と同時、遅くとも直後に「M1 source は実質 24/5、週末 reopen/close bucket は部分営業になりうる」と明文化すべきです。
- [S7] backward-compat は「constructor」「equality/hash」「serialization/asdict」「既存 fixture/snapshot」の 4 面で明示的に確認対象を定義してください。default field 追加だけでは証明になりません。

## Approved 部分 (Round 1 で確定、後続 Round で蒸し返さない)
- T070 の `BLOCK_BUCKET_RANGES_UTC` と `compute_bucket_for_bar()` を不変 SSOT として守る方針は妥当です。
- timezone / DST / holiday を bucket 境界ロジックから分離し、別 layer の contract として扱う方向性は正しいです。
- external calendar library を直導入せず、まず deterministic な calendar source を SSOT 化する発想は妥当です。
- T072 を mark/contract 層に寄せ、下流 evaluator の最終意味づけを別 TODO に逃がす方針自体は妥当です。ただし `is_business_day` のような意味づけは例外です。

## 学術文献 (任意)
- Andersen, T.G. and Bollerslev, T. (1998) *Deutsche Mark-Dollar Volatility: Intraday Activity Patterns, Macroeconomic Announcements, and Longer Run Dependencies*. 要確認
- Dacorogna, M. et al. (2001) *An Introduction to High-Frequency Finance*. 要確認
- Goodhart, C. and O'Hara, M. (1997) *High Frequency Data in Financial Markets: Issues and Applications*. 要確認
- Eggert, P. et al. *IANA Time Zone Database* 関連文書. 標準資料として参照候補
- OANDA developer / instrument candle specification. 仕様一次資料として要確認

## 総評
最大の反証点は 2 つです。第一に、T070 の date universe SSOT を維持したままでは「週末 block を mark する」という T072 の中心主張が成立しません。第二に、FX の週境界が UTC date ではなく金曜 close / 日曜 reopen の部分営業を含むため、`is_weekend()` と `expected_bar_count=0/480` の単純化は session boundary contract そのものを壊しています。

次 Round で最優先で潰すべきなのは、`status enum` の見直しではなく「何を block の事実として持つか」の再定義です。具体的には、`bucket` ごとの予定営業区間と実 bar overlap を SSOT にすること、そして T071 向けに bucket-local の eligibility 契約を切り出すことです。ここを直せば DST/holiday/YAML の細部は詳細設計へ送れますが、ここを曖昧にしたまま進むと M6 で必ず再炎上します。