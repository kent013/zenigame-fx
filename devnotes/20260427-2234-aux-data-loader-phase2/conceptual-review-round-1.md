**前提**
- `verified`: 本レビューは、埋め込み済みテキストのみを根拠にした desk review です。追加のファイル読み込みや実行結果確認はしていません。
- `verified`: 入力には 2 件の設計案が混在していますが、`### C9. Falsification-first` 以降で役割・出力形式・対象入力が再定義されているため、本レビューは aux loader Phase 2 案を主対象として扱います。
- `unverified`: 先頭の Numba/JIT 設計案も同時レビュー対象だった可能性は残ります。今回は対象外と仮定しています。
- `verified`: 現行の [`build_aux_bundle`]( /Users/ishitoya/repository/zenigame-fx/src/alpha_factory/aux_loader.py ) は `aux_series` を 1 つ返し、`aux_pair_bars` は空 dict のままです。
- `verified`: 現行の [`run_ga.py`]( /Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py ) では `RegistryEvaluator` が 1 回だけ生成され、その後 Stage A / B / holdout の複数 bar set を持つ lane に渡されています。
- `verified`: 現行の [`fetch_fred.py`]( /Users/ishitoya/repository/zenigame-fx/scripts/fetch_fred.py ) は DB upsert を行う CLI であり、提示テキスト上は `data/raw/fred/*.csv` を生成しません。
- `verified`: 提示された `pair_specific.py` snippet では、aux 欠損時は strict でなければ safe default に落ち、長さ不一致は fail-fast です。
- `unverified`: 提示 snippet が HEAD と完全一致しているか、また FRED/OANDA 側の実際の時刻仕様・欠損頻度がどうかは未検証です。

**全体判定**
要再設計です。反証観点では、「production wiring が成立する」「look-ahead を防げる」「定数信号悪用を解消できる」の 3 点がまだ成立していません。

[Critical] 1. 1 つの `AuxBundle` / `RegistryEvaluator` では Stage A / B / holdout を同時に満たせません。  
Fact:
- 現案は `build_aux_bundle(..., bars=bars_for_aux_alignment, ...)` で bar-aligned aux を 1 回構築する前提です。
- 一方で現行 [`run_ga.py`]( /Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py ) は `bars_60d`, `bars_18m`, `bars_holdout` の 3 系列を同じ evaluator で扱う構造です。
- `pair_specific.py` の `_check_aux_series_length` は `len(series) == len(bars)` を要求します。  
Interpretation:
- どの bar 列に合わせても、残り 2 系列では長さ不一致になります。Phase 2 の主配線はこのままだと成立しません。  
修正提案:
- `RegistryEvaluator` を stage/window ごとに分ける。
- もしくは `AuxBundle` には raw daily/raw event/raw aux-pair を保持し、各 backtest 開始時に対象 `bars` へ整列する。
- 「1 evaluator で全 stage 共用」はやめた方が安全です。

[Critical] 2. `expand_daily_to_bars` の「前日の close」規則だけでは look-ahead 回避を証明できません。  
Fact:
- 現案は `date,close` だけを持つ daily CSV を前提にしています。
- 提案文は「UTC の前日 close を使う」としていますが、系列ごとの公表時刻・市場 close 時刻・改定遅延の扱いは定義されていません。
- 現行には event 用 `as_of_strict` はありますが、macro daily series 用の同等 contract は提示されていません。  
Interpretation:
- 日付だけで availability を表すと、「その値がいつ利用可能になったか」が消えます。`bar.bar_time.date() - 1 day` だけで埋める設計は、UTC 境界や公表遅延のある系列で漏洩し得ます。  
修正提案:
- daily 系列は `observation_date` と `effective_from_utc` を分けて扱う。
- 最低でも series ごとの availability policy を明文化する。
- テストは「UTC 日付境界」「週末跨ぎ」「祝日連休」「dataset 開始直後の warmup 欠損」を必須にしてください。

[Critical] 3. `strict_aux_required=False` のままでは「定数信号悪用の解消」を主張できません。  
Fact:
- 現行 primitive は aux 欠損時、strict でなければ 0.0 / 0.5 / 1.0 の safe default に落ちます。
- 現案でも `strict_aux_required` は当面 `False` のままです。
- さらに events は手動 CSV の最小整備、aux_pair_bars は新規 loader、macro series も新規整備で、欠損余地が大きいです。  
Interpretation:
- 現案で保証できるのは「揃えば使う」までで、「本番 RUN で欠損により定数信号へ退避しない」は保証できていません。主目的と運用方針が噛み合っていません。  
修正提案:
- Phase 2a: wiring + observability + preflight check。
- Phase 2b: production run では required aux 完備を必須化し、未完備なら run 開始前に fail。
- 少なくとも `strict_aux_required=False` を維持するなら、「悪用解消」は期待効果から下げるべきです。

[Warning] 1. FRED のデータ経路が DB と CSV で二重化しており、現案のままだと loader に届かない可能性があります。  
Fact:
- 現行 [`fetch_fred.py`]( /Users/ishitoya/repository/zenigame-fx/scripts/fetch_fred.py ) は DB upsert です。
- 現行 [`aux_loader.py`]( /Users/ishitoya/repository/zenigame-fx/src/alpha_factory/aux_loader.py ) は `data/raw/fred/*.csv` を読みます。  
Interpretation:
- `DEFAULT_SERIES` を増やすだけでは production wiring は完成しません。SSOT が DB なのか CSV なのかをまず固定すべきです。  
修正提案:
- `aux_loader` を DB reader に寄せるか、`fetch_fred` に CSV export を追加して runbook に明記してください。

[Warning] 2. `aux_pair_bars` misalign を `None` padding で吸収する検証計画は、現行の data integrity 契約を弱めます。  
Fact:
- 提示 snippet では `None` は stale 扱いですが、非 `None` で `bar_time` がずれたら `ValueError` fail-fast です。
- 現案 V3 は「misalign シナリオで loader が None でパディング、primitive 側 fail-fast を意図的に避ける」と書いています。  
Interpretation:
- 「その時刻の bar が存在しない欠損」と「同じ index に別時刻の bar が乗っている misalign」は別問題です。後者まで `None` に潰すと feed/calendar の構造バグを隠します。  
修正提案:
- 欠番は `None` padding 可。
- ただし join 後に別時刻 bar が衝突したケースは fail-fast を維持してください。

[Warning] 3. メモリ概算が楽観的です。  
Fact:
- 現案の `aux_series` は `list[float]`、`aux_pair_bars` は `Sequence[PriceBar | None]` 前提です。
- 概算は `8B/float`, `PriceBar ~200B` として計算しています。  
Interpretation:
- Python `list[float]` と Python object の `PriceBar` は packed `float64` よりかなり重いです。24GB 環境でも「十分余裕」とまではまだ言えません。  
修正提案:
- `aux_series` は最初から `np.ndarray[np.float64]` にする。
- `aux_pair_bars` も `PriceBar` object 列ではなく mid-close など必要最小限の numeric array に圧縮してください。

[Warning] 4. `events.csv` の手動最小整備では P10 / M4 の実効カバレッジが不足する可能性があります。  
Fact:
- 現案は主要イベント約 30 件を手動管理する方針です。
- 一方で期待効果では P10 / M4 も動作回復に含めています。  
Interpretation:
- 「主要イベントだけで十分か」は未立証です。少なくとも P10 / M4 を fully recovered と見なすのは早いです。  
修正提案:
- Phase 2 の完了条件から P10 / M4 を切り離すか、「partial coverage」と明記してください。
- 手動運用を続けるなら preflight で対象期間イベント件数の下限チェックを入れるべきです。

[Suggestion] 1. Phase 2 は少し肥大化しています。  
Fact:
- 現案は FRED 拡張、forward-fill、aux_pair_bars、manual events、run_ga 配線、wrapper script、運用 docs を一括で抱えています。  
Interpretation:
- 最小 viable な「production wiring の成立」を超えており、失敗時の切り分けが難しくなります。  
修正提案:
- まずは 3 つに分けるのがよいです。
- Phase 2a: stage-scoped aux alignment と runner wiring。
- Phase 2b: macro daily series の availability/staleness 設計。
- Phase 2c: aux_pair_bars と events。

**補足評価**
- Stage 2 の主張のうち「9 primitive が本来の機能で動作」は `unverified` です。
- 「性能 overhead は限定的」も `unverified` です。現案データ構造のままではむしろ Python object overhead が先に出ます。
- 「manual events で最小成果物」は `partially verified` ですが、production 主経路としては弱いです。

**優先度つき修正順**
1. `AuxBundle` を stage/window 単位に再設計する。
2. daily series の availability contract を `date` ではなく `effective_from_utc` ベースで定義する。
3. production run の preflight を入れ、required aux 欠損時は fail させる。
4. FRED の SSOT を DB か CSV に一本化する。
5. `aux_pair_bars` の「欠番」と「misalign」を分離して扱う。
6. events は Phase 2 完了条件から一段下げるか、coverage 基準を明文化する。

この設計は方向性自体は妥当ですが、現時点では「実データ取得」より先に「どの時点で利用可能と見なすか」「どの stage の bars にどう整列するか」の契約を先に固定すべきです。そこを曖昧にしたまま実装に入ると、後で look-ahead と wiring 崩れの両方を抱えます。