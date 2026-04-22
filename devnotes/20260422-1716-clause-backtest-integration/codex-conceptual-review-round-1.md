## 本分析の前提
- `conceptual-design.md` 本文は提示テキストで確認済み。
- C1 で要求された `docs/alpha_factory/clause-architecture.md`、T007/T008 の detailed-design、`src/backtest/engine.py`、`src/broker/mock.py`、`src/dsl/strategy.py` はこのスレッドで未提示。ユーザー指定によりコマンド実行も禁止されているため、**未検証**。
- よって以下の判定は「提示された概念設計書の自己整合性」と「そこから読める契約破綻経路」に対するレビューであり、既存実装との整合までは確証できない。

## Verdict: NEEDS_REVISION

## Facts (読み取った事実)
- 本設計は `BacktestConfig` に `max_spread_bps`、`swap_cost_per_day_bps`、`session_close_utc_hours`、`bar_minutes` を追加する方針を置いている。
- spread フィルタは「open 系シグナルのみを対象」「close 系は常に通す」「`fill_pending` 直前に約定対象 bar の spread で判定」と書かれている。
- swap は `swap_cost_per_day_bps` を bar ごとに線形按分し、開いているポジションに対して `cash` から控除する方針である。
- session close は `fill_pending` → `mark_to_market` の後、`on_bar` の前に `close_all(reason="eod")` を行う方針である。
- 同じ bar での `close -> open` を避けるため、「強制 close した bar では新規 open を抑制」と書かれている。
- `run_backtest` について、セクション 2 では `primitive_evaluator` を追加すると書かれている一方、セクション 3.4 の最終方針では「追加しない」と書かれている。
- `config/alpha_factory/default.yaml` への値追加、Stage Gate 接続、実プリミティブ実装は本 TODO のスコープ外とされている。
- `session_close_utc_hours` が空で `is_eod` が常に false の場合、`run_backtest` 入口では warning のみで fail しない方針が書かれている。
- `evaluate_genome` は `sharpe` / `calmar` が `None` のとき `_FAILURE_FITNESS` を返す方針である。

## Interpretations (解釈)
- 4 段伝搬契約の観点では、今回追加する値が `config -> GaConfig -> BacktestConfig -> consumer` にどう届くかが概念設計として未閉路である。
- session close を warning-only にすると、「イントラデイ絶対制約を engine レベルで強制する」という North Star の主張と整合しない。
- spread フィルタの説明は、「約定対象 bar の close spread を使う」のか「前 bar で記録した close spread を使う」のかが揺れており、現状の記述だと lookahead bias か契約不一致のどちらかになる。
- `fill_pending` の後に session close を発火させる設計だと、前 bar から持ち越された pending open が session close bar で一度約定してから即 close される経路が残る。
- `run_backtest` に `primitive_evaluator` を入れない最終方針自体は責務分離として妥当だが、文書内の契約が二重化しており詳細設計に進む前に一本化が必要である。
- `sharpe=None` / `calmar=None` を failure 扱いにする方針は、使命上「取引が薄すぎる個体を落とす」意図としては妥当である。
- swap を intraday 保有にも bar 単位で線形課金する近似は、実務上の overnight finance charge と一致しないため、fitness を別方向に歪めるリスクがある。

## 反証を探した結果
- **反証 1**: 20:59 に出た open シグナルが pending に入り、21:00 が `session_close_utc_hours` 対象 bar の場合、設計通りだと 21:00 の `fill_pending` で一度約定し、その後 `close_all` されうる。これは「session close bar では新規 open を抑制する」という意図を破る。
- **反証 2**: spread 判定に「約定対象 bar の close」を使うなら、約定時点では未観測の情報を使うことになり lookahead になる。逆に「前 bar の close」を使うなら、設計書の仕様文が誤っている。
- **反証 3**: `default.yaml` と `GaConfig` を今回触らないままだと、後続 TODO で配線を忘れた場合でも `BacktestConfig` は default 値で動作してしまい、spread/swap/session close が silently disabled になる。
- **反証 4**: `session_close_utc_hours` も EOD も効かないデータで warning のみ許すと、North Star の「イントラデイ絶対制約」は engine 不変条件にならない。
- **反証 5**: intraday 戦略に対して bar ごと線形 swap を課すと、overnight を避けているにもかかわらず保有時間コストを架空に上乗せするため、「スワップを純利益に反映する」という要求を満たしても、経済的意味はかなり弱い。

## 指摘事項（あれば番号付き）
1. **spread フィルタ契約が未確定です。** `fill bar close` を使う案は lookahead の疑いが強く、`previous bar close` を使う案と文書内で衝突しています。ここは「何をいつ観測できるか」を固定し、仕様・テスト・ログを同じ契約で揃える必要があります。
2. **session close の強制力が足りません。** warning-only は North Star 不遵守です。さらに `fill_pending` 後に close する順序では pending open の抜け道が残ります。少なくとも session close bar では pending open を fill 前に cancel/reject する設計が必要です。
3. **4 段伝搬契約が未閉塞です。** 本 TODO で実装しないとしても、`config/alpha_factory/default.yaml`、`GaConfig`、`BacktestConfig`、consumer への受け渡し名と責務境界を概念設計に明記しないと、zenigame 系で繰り返した値伝搬漏れが再発します。
4. **`run_backtest` API 方針が文書内で矛盾しています。** 最終方針を「`primitive_evaluator` は `DslStrategy` に bake-in、engine は evaluator 非依存」に一本化し、セクション 2 の変更要約も修正すべきです。
5. **swap の経済意味を再定義すべきです。** intraday にも per-bar 線形課金するなら、それは「swap」ではなく「保有コスト近似」です。名前と役割がズレています。実 swap を表現したいなら rollover event 課金に寄せるべきです。
6. **`_FAILURE_FITNESS` 方針自体は妥当ですが、原因の粒度を分けるべきです。** `metric unavailable` と `system exception` を同じ warning 1 本に潰すと、後続分析で「低活動個体」と「実装バグ」を分離できません。

## 次ラウンド要求（NEEDS_REVISION の場合のみ）
- spread フィルタについて、「観測可能な時点」と「使用する価格」を 1 つに固定してください。`fill bar open bid/ask` を使うのか、`previous bar close spread` を代理変数にするのかを明示し、lookahead を避けてください。
- session close について、`warning` ではなく engine 不変条件としての扱いを再設計してください。少なくとも session close bar で pending open が成立しない順序を定義してください。
- 4 段伝搬契約について、今回未実装でも `config -> GaConfig -> BacktestConfig -> consumer` のフィールド名と接続責務を設計書に追記してください。
- `swap` の命名と意味を整理してください。実 swap を模すのか、単なる holding cost proxy なのかを明確化してください。
- `run_backtest` のシグネチャ方針を本文全体で統一してください。