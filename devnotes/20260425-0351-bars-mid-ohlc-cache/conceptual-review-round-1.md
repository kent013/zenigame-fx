全体判定: **CHANGES_REQUESTED**

**Fact**
- P1-P5 はコード上で確認できました。`_bars_to_mid_ohlc` の重複定義は [directional_generic.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/directional_generic.py#L66)・[modulator_generic.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/modulator_generic.py#L58)・[pair_specific.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/pair_specific.py#L57) にあり、`run_backtest()` は `bars` を `bars_list` 化して `prepare()` に 1 回渡し、同じ list を downstream に流しています [engine.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/engine.py#L98) [engine.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/engine.py#L113) [strategy.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/strategy.py#L186) [evaluator.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/evaluator.py#L157)。
- `PriceBar` / `Ohlc` は frozen ですが、`bars` コンテナ自体は plain `list` です [price.py](/Users/ishitoya/repository/zenigame-fx/src/domain/price.py#L8)。
- 現行 `run_ga.py` は 1 プロセス内で単一 `Tier1Lane` を作り、その lane の `bars_60d / bars_18m / bars_holdout` を順番に使います。現状コード上は 6 pair 同居ではありません [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L750) [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L768) [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L788)。
- 既存 primitives 側は「循環 import 回避のため複製」と明記しています [modulator_generic.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/modulator_generic.py#L53) [pair_specific.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/pair_specific.py#L52)。registry bootstrap も遅延 import 前提です [_registry.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_registry.py#L118)。
- P6 の profile 数値は今回、実 profile ファイルまでは再追跡していません。概念設計記述を入力前提として扱っています。

**Interpretation**
- 提案は性能最適化に閉じており、イントラデイ / long-short / swap・spread / オーバーナイト禁止には直接触れていません。禁止事項への明示的違反は見当たりません。
- ただし、承認を止める論点は「速くなるか」より「selection invariance を壊さない契約が閉じているか」です。そこがまだ弱いです。

[Critical] キャッシュ整合の前提が未閉鎖です。  
Fact: 設計 key は `id(bars)` のみで、`bars` は mutable list です。一方、現行コードはたまたま `prepare()` 後に同じ list を append しないだけで、その不変条件は設計に書かれていません [strategy.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/strategy.py#L186) [price.py](/Users/ishitoya/repository/zenigame-fx/src/domain/price.py#L16)。  
Interpretation: 同じ list object に途中追加が入ると stale array を返し得るため、「Selection invariance 100%」は現状の文面では言い切れません。Round 1 の反証点の中で、ここがいちばん selection outcome に直結します。  
修正案: `bars` を immutable input と明文化してテストで固定するか、最低でも cache entry に `len(bars)` を持たせて長さ変化で miss にしてください。余裕があれば `(id, len, last_bar_identity)` まで持つ方が堅いです。

[Warning] `MAX_ENTRIES = 16` の根拠が現行実装とも将来仮説とも噛み合っていません。  
Fact: 現行 `run_ga.py` は 1 lane なので、1 プロセスで本質的に再利用したい `bars` は Stage A/B/C の 3 本です [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L755)。一方、設計根拠の「Stage A/B/C × 6 pair」は 18 本で、16 はその将来仮説には不足します。  
Interpretation: 16 は correctness を壊しませんが、期待 hit rate とメモリ見積りの両方が未検証です。現状では「過大な上限」かつ「未来仮説には不足」の中途半端な値です。  
修正案: 容量根拠を現行 topology に合わせて書き直してください。今の実装基準なら 4-8 でも足りるはずです。将来 multi-pair 同居を想定するなら定数化ではなく config 化し、eviction 発生回数を telemetry で記録してください。

[Warning] thread safety 前提が弱いです。  
Fact: 提案は module-level `OrderedDict` の write を想定していますが、registry は並行書込を lock で保護している一方、今回の cache にはその記述がありません [_registry.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_registry.py#L6)。repo 全体には thread 利用箇所も存在します。  
Interpretation: 現行の backtest/GA 主経路は単一スレッドで回っているので直ちに破綻するとは言いませんが、「same process 内で並列 backtest が走らない」は verified ではありません。概念設計としては未閉鎖です。  
修正案: 「backtest path は thread-parallel 不可」を契約として明文化するか、`_LRU_CACHE` / `_LRU_STRONG_REFS` 更新を軽量 lock で守ってください。

[Warning] DRY 統合は方向として妥当ですが、依存境界を書かないと import 循環リスクが再発します。  
Fact: 既存 2 モジュールは複製理由を「import 循環回避」と明記しています [modulator_generic.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/modulator_generic.py#L53) [pair_specific.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/pair_specific.py#L60)。  
Interpretation: `_bars_cache.py` 自体は正しく切れば安全ですが、設計文に依存制約が無いので、実装者が `primitives.__init__` や `_registry` を触る余地が残っています。  
修正案: `_bars_cache.py` は `numpy`・`collections`・`src.domain.price` のみ依存、`primitives.__init__` / `_registry` / 各 primitive module は import 禁止と明記してください。

[Warning] 期待効果の主張が強すぎます。  
Fact: 根拠 profile は 1 サンプルです。現行 run も single-instrument lane です [devnotes concept](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0351-bars-mid-ohlc-cache/conceptual-design.md#L12)。  
Interpretation: C7 的に、`85-91%` や `80-95秒/RUN` はまだ observation ではなく hypothesis です。ここを強く書くと、性能改善が使命に直接効くように見えてしまいます。  
修正案: 成功基準の先頭を selection invariance に固定し、時間短縮は「複数 pair / 複数 seed で再計測後に採否判定」に落としてください。

[Suggestion] `id()` 再利用そのものは、提示設計の strong ref 付きなら大きな blocker ではありません。  
Fact: resident entry が strong ref を保持している限り、その object の `id` は再利用されません。eviction 後に strong ref も key も消すなら、再利用 `id` は miss になります。  
Interpretation: Round 1 の「LRU 内にない場合と境界」の反証は、`_LRU_CACHE` と `_LRU_STRONG_REFS` を常に lockstep で更新する限り、概ね潰せています。  
修正案: ここは実装 invariant を 1 行足してください。「insert / move_to_end / eviction は 2 dict を同順序で同時更新する」。テストも resident-hit と eviction-boundary を追加すれば十分です。

[Suggestion] 同一内容だが別 object の bars は semantic に問題ありません。  
Fact: key が identity なので、内容一致コピーは miss します。  
Interpretation: correctness は壊れません。失うのは効率だけです。  
修正案: 期待効果の説明を「identity-sharing がある経路だけを取る局所最適化」と言い換えてください。content-hash 系へ広げないのは妥当です。

[Suggestion] メモリは現状そこまで厳しくありませんが、明文化した方がよいです。  
Fact: 1 entry は `float64` 4 配列なので概算 `32 * len(bars)` bytes です。60日 x 1分足なら 1 entry は数 MB 規模、18か月相当だと数十 MB 規模です。  
Interpretation: 24GB 制約下で即危険ではありませんが、global LRU なので「軽い」と断言するには上限式が必要です。  
修正案: 設計書に `memory_per_entry ~= 32 * len(bars)` を追記し、`MAX_ENTRIES` 採用理由と合わせて書いてください。

最小の修正方針は次です。  
1. `bars` immutability 契約を明記するか、`len(bars)` ガードを追加する。  
2. `MAX_ENTRIES=16` の理由を現行 topology ベースに書き直す。  
3. `_bars_cache.py` の import 禁止境界と、必要なら lock 方針を設計に追加する。  
4. 効果指標は「selection invariance first、速度は hypothesis」に下げる。

この 4 点が入れば、Round 1 としては APPROVED に寄せられます。