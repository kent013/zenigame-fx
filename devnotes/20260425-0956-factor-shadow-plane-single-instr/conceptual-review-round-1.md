**前提**
このレビューは添付された概念設計本文だけを根拠にした概念レビューです。`T016`、`T004`、既存 archive 読み込み実装、既存 devnotes / git 履歴は未読なので、`Design-first` の観点では「暫定判定」です。特に重複判定と Parquet 互換は、実装本文確認前は `CONFIRMED` ではなく `未検証` 扱いです。

**Critical**
- `DXY/VIX を M1 に因果的補間して評価因子にする` という前提は、そのままだと成立しにくいです。Fact: FRED の `DXY/VIX` は実質的に日次密度で、M1 に落としても当日中はほぼ定数系列になります。Interpretation: その状態で rolling Spearman を取ると、因子感応度ではなく「日付ブロック」「営業日境界」「ポジション保有時間帯」の影響を拾いやすく、single instrument の shadow 妥当性評価としては弱いです。修正提案: Phase 1 は `daily/hourly shadow plane` と明示して評価周波数を因子密度に合わせるか、M1 を維持したいなら intraday proxy に因子を差し替えてください。少なくとも `fsp_sampling_mode` と `factor_asof_lag` を設計に入れるべきです。
- `factor / idio 分解 (R²)` は conditioning set を明示しないと collider bias を起こします。Fact: 被説明変数候補として書かれているのは「個体の position 系列」で、これは戦略・閾値・生存条件の出力です。さらに archive 後段だけで計測すると、すでに複数フィルタを通過した母集団になります。Interpretation: この R² は「因子がアルファを説明した」ではなく、「選抜後のエクスポージャ経路と因子がどれだけ共変動したか」しか意味しません。修正提案: `conditioning_set` を明記し、少なくとも `全 bar グリッド上の signed exposure` と `strategy bar return / pnl path` のどちらを説明対象にするか固定してください。`ポジション保有中バーのみ` や `survivor 個体のみ` の R² は禁止、と設計に書くべきです。
- Phase 1 の成功基準が `non-null` だけなのは、使命に対して弱すぎます。Fact: H1/H2 の成功基準は「active になり列が埋まる」「計測値が non-null」です。Interpretation: これは計測基盤の疎通確認であって、`single instrument でも動く外生因子 shadow 評価面` が有意義かどうかの検証になっていません。場当たり的な telemetry 追加で終わるリスクがあります。修正提案: Phase 1 に falsifiable な判定を追加してください。例として、`coverage rate`、`window 安定性`、`既知の factor-heavy ベースラインとの識別性`、`skip 率`、`run 間再現性` のどれかを success / kill criteria に置くべきです。

**Warning**
- `T016` との関係がまだ曖昧です。Fact: 本文では FSP を「独立面」と呼びつつ、H3 では `multi-pair -> ii-lite / single instrument -> FSP` という排他的 dispatch を想定しています。Interpretation: 現状の記述だと、FSP が `ii-lite の代替` なのか `single instrument 専用 fallback` なのかが不明で、使命の重複判定ができません。修正提案: `dispatch matrix` を 1 行で定義してください。`single+factor_available=FSP, multi+cross_pair_available=ii-lite, multiでもFSPは走らせない/走らせる` を明文化すべきです。
- archive schema 拡張は「nullable 追加だから安全」とは言い切れません。Fact: 列追加自体は後方互換に見えますが、既存の Parquet 読み込み側が `固定 schema`、`明示列選択`、`row group 混在 schema` を前提にしていると壊れます。Interpretation: 破綻点は schema 自体より reader 実装です。修正提案: `old archive only`、`new archive only`、`old+new mixed read` の 3 ケースで互換テストを設計に追加してください。`runtime_mode` は enum 文字列集合も固定した方が安全です。
- `trade_count 不変` は条件付きでのみ妥当です。Fact: 選抜介入なし、post-RUN 一括計算、GA worker 外なら論理上は売買件数は変わりません。Interpretation: ただし実装が同一プロセスでメモリ圧迫、例外波及、run 完了順序変更を起こすと、間接的に run 成否へ影響し得ます。修正提案: `archive を immutable に確定後、別 task/process で FSP を計算し、失敗時は skipped に倒す` を必須条件として書いてください。
- メモリと計算量の見積もりがまだ甘いです。Fact: rolling Spearman + OLS を個体ごと・window ごと・M1 バーで回すと、single instrument でも個体数次第でかなり重くなります。Interpretation: `GA worker 外` だけでは十分でなく、post-run 集計のボトルネック化があり得ます。修正提案: 因子系列は run ごとに 1 回だけ構築し、個体ごとの統計は streaming / vectorized に寄せる前提を入れてください。

**Suggestion**
- 名前は悪くないですが、Phase 1 の実態は `plane` より `diagnostic layer` に近いです。期待を過大化しないため、設計文書では `diagnostic-only exogenous shadow layer` と補助説明を添えた方が誤読が減ります。
- `R²` 単独より、`partial correlation` か `explained variance under fixed conditioning set` の方が誤解が少ないです。少なくとも列名は解釈を限定する方が安全です。
- 因子集合は最初から `USD broad / VIX / 金利差 proxy` の 3 本を並べるより、Phase 1 は 1 本で始めた方が失敗時の原因分離が容易です。

**依頼 6 点への回答**
1. `T016` との重複判定は現時点では `未検証` です。ただし記述上は「single instrument 専用 fallback」と定義すれば重複は避けられます。上位互換ではありません。
2. `FRED 日次データを M1 に因果的補間して高頻度 shadow に使う` のは厳しいです。技術的には可能でも、評価量としての意味が弱いです。
3. `R²` はそのままだと collider bias リスクがあります。特に `ポジションがある区間だけ`、`survivor だけ`、`archive 後段だけ` は危険です。
4. schema 拡張の後方互換は reader 実装次第です。`nullable 追加だから安全` と結論してはいけません。混在読み込み試験が必要です。
5. diagnostic-only Phase 1 は、成功条件を `non-null` から引き上げない限り、本質寄与は弱いです。疎通確認以上の仮説検証にしてください。
6. `trade_count 不変` は、FSP が完全に post-run・非介入・失敗隔離なら妥当です。その条件を書かないと強すぎる主張です。

**総評**
この案は「single instrument で shadow 経路が空転する」という課題認識自体は妥当です。ただし現状のままでは、`日次因子を M1 に持ち込む実現可能性` と `R² の解釈可能性` が弱く、使命に対して計測追加で終わる危険があります。次版ではまず `dispatch matrix`、`conditioning set`、`sampling granularity`、`Phase 1 success/kill criteria` の 4 点を先に固定するべきです。