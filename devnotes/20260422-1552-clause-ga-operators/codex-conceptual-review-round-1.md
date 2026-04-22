前提確認: 対象設計、T007 の `Genome/composite/enforce/strategy`、旧 `src/ga/` 実装、concept stub を確認しました。

1. Clause-aware crossover の設計妥当性  
指摘事項: 現行案の「50/50 固定ミックス」は、今の構造制約だと実効的に偏ります。初期世代は `max_clause=1` 固定で、`local_gate` は `enforce_consistency` により最大 1 本なので、Clause-level point crossover は初期条件では不可能、local_gate の signal-level point crossover も実質不可能です。そのため設計上は二層 mix でも、実運用では directional 側の限定的 swap か fallback に寄りやすく、building block 保存と多様性のバランスを 50/50 で制御しているとは言いにくいです。根拠は [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L52), [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L96), [enforce.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/enforce.py#L47), [clause-architecture.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/clause-architecture.md#L43) です。構造制約付き GP で型や構造を先に守る発想自体は STGP の系譜と整合しますが、固定比率の 2 モード mix まで文献が支持しているわけではありません。 ([gpbib.cs.ucl.ac.uk](https://gpbib.cs.ucl.ac.uk/gp-html/montana_stgpEC.html))  
推奨対応: `50/50` 固定ではなく「実行可能な operator の集合から重み付き選択」に変えてください。少なくとも `max_clause=1` 中は Clause-level mode を無効化し、local_gate は point crossover ではなく「丸ごと swap」か「親択一」に落とす方が自然です。  
根拠: point crossover の階層拡張という説明を維持するなら、実際に切断点が存在する場合だけその operator を選ぶべきです。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L54)

2. Mutate の独立確率モデル  
指摘事項: `mutation_rate=0` で完全無変化は成立しますが、`mutation_rate=1` で「多数変化」が仕様として保証されていません。最小合法ゲノムを仮定しても、weight perturb・params perturb・add signal・cfg perturb がすべて外れるだけで no-op になり、その下限確率は 0.14 です。さらに `max_clause=1` では clause add/delete が無効化され、params が空なら実効変化率はもっと下がります。   
推奨対応: `mutation_rate` の意味を「有効編集が 1 回以上起きる確率」か「期待編集回数」のどちらかに固定してください。前者なら `mutation_rate>0` で少なくとも 1 つの有効 mutation を保証する再抽選が必要です。後者なら Poisson/Binomial で編集回数を先に引き、その後に編集種別を割り当てる方が仕様が明瞭です。  
根拠: 現行案は per-signal / per-clause に独立判定を掛けるので、ゲノムサイズが増えるほど mutation 圧も増えます。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L69)

3. Complexity penalty  
指摘事項: `size_norm` の `depth` が実際には「1 clause 内 signal 数の最大値」であり、深さではなく幅です。現構造は Clause の入れ子木ではないので、この式は `nodes` と幅を二重計上しているに近く、Clause 構造の複雑性を表す指標名として不正確です。また Poli 2008 が支持するのは parsimony pressure の一般論であって、この重み付け式や `α=0.03 / size_ref=10.0` の具体値ではありません。bloat 抑制の実証に寄せるなら、Luke & Panait 2006 の方が「サイズ罰則と制限の併用」に近い根拠です。 ([gpbib.cs.ucl.ac.uk](https://gpbib.cs.ucl.ac.uk/gp-html/poli08_fieldguide.html))  
推奨対応: `depth` は `max_clause_width` のように改名するか、本当に深さ概念を持ち込みたいなら signal expression 側の構造深さを別に測ってください。係数と `size_ref` は「暫定 default」と明記し、SSOT に移す前提を強めるべきです。  
根拠: [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L97), [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L105), [clause-architecture.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/clause-architecture.md#L175)

4. Dummy registry の扱い  
指摘事項: `PrimitiveSpec.category` の設計が既存 docs と不整合です。設計案は `TREND_FOLLOW/MEAN_REVERT/MODULATOR/LOCAL_GATE` を category に入れていますが、既存ドキュメントでは registry の category は `directional/modulator` で、`local_gate` は primitive の種類ではなく配置先です。このままだと T010 の registry 境界がぶれます。さらに `DUMMY_REGISTRY` を本番モジュール `src/ga/random_gen.py` の公開 namespace に置くと、後続で偶発依存が生まれやすいです。  
推奨対応: `PrimitiveSpec` は docs に合わせて `category=directional|modulator`、必要なら `domain=generic|pair_specific` を追加してください。dummy は `tests` fixture か `src/ga/_dummy_registry.py` の private module に分離した方が安全です。  
根拠: [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L44), [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L135), [primitives.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/primitives.md#L21)

5. Runner の evaluator 注入  
指摘事項: `Callable[[Genome], float]` に bars/meta/backtest_config を closure へ閉じ込める発想自体は、T008 を T009 から切り離す意味で妥当です。ただし「float しか返せない」形で固定すると、後で raw fitness 以外の評価メタデータを runner が扱えません。T008 の `Individual` は `fitness_raw/fitness_pen` しか持たず、後続の archive/stage 連携で再評価や side channel が必要になる可能性が高いです。  
推奨対応: I/F は closure のままで構いませんが、返り値を `float` ではなく `EvaluationResult` dataclass にして、最低でも `fitness_raw` と任意 `meta` を持たせる方が後方互換性があります。  
根拠: [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L117), [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L184), [runner.py](/Users/ishitoya/repository/zenigame-fx/src/ga/runner.py#L53)

6. `enforce_consistency` の呼び出し規約  
指摘事項: operator 直後に `enforce_consistency` を呼ぶ方針は必要ですが、それだけでは不十分です。`enforce_consistency` は単なる validator ではなく、dedupe・gate 1 本化・clause 上位 3 本化・threshold swap を行う lossy repair です。つまり operator の不整合が silently repaired され、探索が実質 no-op 化しても見えにくいです。  
推奨対応: 契約を 2 段に分けてください。「構造不変条件は operator が原則守る」「clip/swap/dedupe は enforce の最終正規化」に分離するべきです。`ValueError` は `random_gen` と `add_clause` のみ bounded retry 可、`crossover/mutate` で出たら原則バグ扱い、必要でも少数回 retry 後に親を返す、まで決めた方が安全です。  
根拠: [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L18), [enforce.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/enforce.py#L91)

7. テスト計画の網羅性  
指摘事項: 現行計画には重要な抜けがあります。`max_clause=1` かつ `local_gate<=1` で crossover が実質どう振る舞うか、親個体が不変か、`params` dict の alias が子に漏れないか、non-finite evaluator を runner がどう処理するか、seed 再現性があるか、が未記載です。`test_mutate_rate_one_changes` も「多試行中に変化が発生」だと仕様が弱く、rate=1 の意味論を固めるテストになっていません。  
推奨対応: 最低でも「最小合法ゲノムで rate=1 が有効編集を保証するか」「local_gate swap fallback が deterministic か」「親子間で `params` 参照共有がないか」「NaN evaluator を `-inf` へ落とすか」「同一 seed で GA 履歴が再現するか」を追加してください。  
根拠: [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L210), [genome.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/genome.py#L18), [enforce.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/enforce.py#L26)

8. 学術引用  
指摘事項: 3 本とも全否定ではありませんが、役割がずれています。Koza 1992 は GP 全般の基礎文献としては適切でも、「building block 保存」や固定 50/50 crossover mix の根拠としては弱いです。building block の語を使うなら Holland 1975 / Goldberg 1989 の方が筋がよく、構造制約付き crossover の議論なら Montana 1995 が近いです。Poli 2008 は parsimony pressure の一般論として適切ですが、今回の size 式や係数の根拠にはなりません。Luke & Panait 2006 を補う方が良いです。Jacobs 1991 / Jordan 1994 は Clause を gated expert とみなす設計比喩には適切ですが、GA operator 設計の根拠にはなりません。 ([openlibrary.org](https://openlibrary.org/books/OL1559961M/Adaptation_in_natural_and_artificial_systems?utm_source=openai))  
推奨対応: 引用の役割を分けてください。`Koza 1992 = GP 背景`、`Holland/Goldberg = building block 用語`、`Montana 1995 = 構造制約`、`Poli 2008 + Luke & Panait 2006 = bloat/parsimony`、`Jacobs 1991 + Jordan 1994 = Clause 意味論` が整理しやすいです。  
根拠: 上記文献の対象領域がそれぞれ異なります。 ([openlibrary.org](https://openlibrary.org/books/OL1559961M/Adaptation_in_natural_and_artificial_systems?utm_source=openai))

総合すると、方向性は良いですが、`crossover` の実効性、`mutation_rate=1` の意味論、registry 境界、`size_norm` の定義がまだ設計として締まっていません。特に 1, 2, 4 は実装に入る前に明文化を直すべきです。

REVISE