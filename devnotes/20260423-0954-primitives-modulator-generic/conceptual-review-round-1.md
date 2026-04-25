**Verdict**

**NEEDS_REVISION**

**本分析の前提**
- `Verified`: レビュー根拠は、添付された [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-0954-primitives-modulator-generic/conceptual-design.md) 本文のみです。
- `Verified`: ユーザー指定によりコマンド実行・書き込みは行っていません。
- `Verified`: そのため、[src/alpha_factory/primitives/_base.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_base.py)、[src/alpha_factory/primitives/directional_generic.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/directional_generic.py)、[src/events/calendar.py](/Users/ishitoya/repository/zenigame-fx/src/events/calendar.py)、[docs/alpha_factory/primitives.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/primitives.md) との実整合性は **INCONCLUSIVE** です。
- `Verified`: 以下の verdict は「概念設計としての論理健全性」に限定します。実装経路の接続確認ではありません。

**Facts**
- 設計は `MODULATOR` を local_gate として 6 個追加し、`directional * local_gate` の local_gate 部を埋める方針です。
- `EvaluationContext` に `event_calendar` と `vix_daily` を `default=None` で追加する案です。
- M4 は「予定時刻は未来既知で可」、M5 は「`bar_time.date() - 1` 以前で直近の VIX close を使う」と書かれています。
- M3 は MVP では価格単位の spread をそのまま閾値比較する案です。
- 欠損時 default は、M4 が `1.0`、M5 が `0.5` です。

**Interpretations**
- 1. 設計方針の大筋は妥当です。directional だけでは regime / blackout を表現しづらく、local_gate を追加する方向自体は Alpha Factory の使命に整合します。
- 2. ただし「gate を入れて Sharpe を改善する」が「取引を削って見かけを良くする」に滑りやすい設計でもあります。trade count と active ratio を同時監視しないと、使命への寄与が曖昧になります。
- 3. `EvaluationContext` への後方互換 field 追加自体は自然です。ただし `default=None` の safe fallback は、今回の重点監査項目である「値の伝搬漏れ」を隠しやすいです。
- 4. M4 の look-ahead 議論は不十分です。問題は actual 値だけではなく、「イベント予定・importance・時刻変更が bar 時点で既知だったか」という as-of 管理です。履歴全量ロード済みの finalized calendar をそのまま使うと leakage 余地が残ります。
- 5. M5 の look-ahead 対策は現状だと危険です。`bar_time.date() - 1` 基準は UTC 日付であり、たとえば火曜 00:30 UTC の bar で月曜 VIX close を拾うと、その close はまだ米国市場で確定していない可能性があります。これは concept 上の重大な穴です。
- 6. M3 を「generic primitive」としながら raw price spread を使うのは不整合です。EURUSD と USDJPY で尺度が違い、cross-pair (ii-lite) に不利です。使命と衝突します。
- 7. 6 primitive 一括 MVP は hidden complexity があります。M1/M2/M6 は内部系列、M4/M5 は外部データ注入、M3 は尺度正規化問題を含み、失敗時の切り分けが悪いです。

**Must-fix**
- M5 の参照規則を `date()-1` ではなく「VIX 観測値の publication timestamp / as-of timestamp 基準」に修正すること。UTC 日付ベースでは future close 混入を防げません。
- M4 について「予定時刻は未来既知で可」をもう一段具体化し、`known_at` / snapshot 時刻の前提を設計に明記すること。finalized calendar 全量参照は危険です。
- `event_calendar=None` / `vix_daily=None` の safe default を、M4/M5 が実際に選択された場合まで黙認しないこと。少なくとも production evaluation では fail-fast か明示的な hard warning / metric 化が必要です。そうしないと伝搬漏れを隠します。
- M3 の尺度を raw price のままにしないこと。pip / bps / mid-price 正規化のいずれかに寄せるか、M3 を MVP から外すべきです。
- `EvaluationContext` 注入経路の設計を追加すること。Stage A/B/C、cross-pair、テスト helper のどこで `event_calendar` / `vix_daily` を埋めるかを明示しないと、今回の重点監査対象である伝搬漏れが再発します。

**Should-consider**
- MVP を 1 TODO に詰め込まず、少なくとも `M1/M2/M6` と `M4/M5/M3` を分けること。
- local_gate 導入の評価指標に `trade_count` と `gate_active_ratio` を明示し、「良化が単なる取引削減ではない」ことを確認できるようにすること。
- M2 の `required_data=("ohlc", "calendar.session")` は実データ依存というより時刻規約依存なので、命名を再考すること。
- M4/M5 の欠損時挙動を docs と logger だけでなく、genome/meta や evaluation result に露出させること。後段での監査が楽になります。

結論として、**local_gate として MODULATOR を足す方向自体は支持**しますが、現案のままでは **M4/M5 の as-of semantics と M3 の尺度設計が弱く、使命に対して危うい** です。特に **M5 は concept 上の look-ahead risk が未解消** なので、現時点では `APPROVED` にはできません。