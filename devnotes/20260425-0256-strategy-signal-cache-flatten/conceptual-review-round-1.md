全体判定: **CHANGES_REQUESTED**

以下は、提示された概念設計文のみを根拠にした Round 1 の反証中心レビューです。

**1. 使命との整合性**
- [Warning] 事実: この提案が直接変えるのは `prepare()/on_bar()` の実行コストであり、シグナル品質、long-short 制約、swap・spread 反映、Stage C/ii-lite 判定ロジック自体は変えません。解釈: 使命への寄与は探索効率の間接効果に限られるため、「live_criteria 充足に効く改善」という主張は弱いです。修正提案: 成功基準を「selection invariance を壊さず prepare hot path を削る補助改善」と明記し、live_criteria との因果主張は切り分けてください。
- [Suggestion] 事実: 現設計は性能改善のみを扱っています。解釈: スコープを性能限定に固定する方が、禁止事項との境界が明確です。

**2. 禁止事項違反**
- [Warning] 事実: 提案自体は評価期間延長、閾値緩和、GA ハック、オーバーナイト化を含みません。解釈: ただし「本番推定 120-150 秒/RUN」の外挿を根拠に探索量増加を強く期待すると、実質的に GA ハック寄りの説明になります。修正提案: 本設計では探索量増加を成果物に含めず、性能計測結果だけを成果として扱ってください。
- [Suggestion] 事実: `vals` 生成経路だけを変える設計です。解釈: この範囲なら「数値改善」には当たりません。

**3. 実現可能性**
- [Critical] 事実: flat list は `prepare()` 時点の clause 順序と signal 順序に依存しますが、`prepare()` 後から `on_bar()` 完了までその順序が不変であることは、成功基準に書かれているだけで設計上は未強制です。解釈: GA / crossover / mutate 後の genome 差し替えや in-place mutation が少しでも入ると、index 対応崩れで bit-identical 仮説は即破綻します。修正提案: `prepare()` 時に `genome_fingerprint` と clause 長・各 clause の signal fingerprint を固定保存し、`on_bar()` 入口で一致検証するか、不一致時は prepared path を無効化してください。
- [Critical] 事実: prepared path の分岐条件が `self._precomputed is not None` だけです。解釈: `_precomputed` だけが残存し `_precomputed_clauses` が stale / None / 長さ不一致の状態でも、paper trading / live feed 側で誤って fast path に入る余地があります。修正提案: 分岐条件を単一の `_prepared_state is not None` に統一し、`arrays` と `clauses` を 1 オブジェクトで持ってください。
- [Warning] 事実: `prepare()` no-op path の説明には stale state clear がありません。解釈: 同一インスタンス再利用時に古い `_precomputed_clauses` を踏む危険があります。修正提案: `prepare()` の先頭で prepared state を必ず初期化してください。

**4. 期待効果の妥当性（C3, C7）**
- [Warning] 事実: `_lookup_signal` の 0.357s には `float(arr[idx])` と `math.isfinite` のコストも含まれている可能性が高く、inline 化後もこの部分は残ります。解釈: `_lookup_signal` 60-80% 削減は過大推定の可能性があります。修正提案: 仮説を `_signal_cache_key` ほぼ全削減と `_lookup_signal` 一部削減に分け、後者の期待値は下げてください。
- [Warning] 事実: 本番外挿は `14d EUR_JPY pop=8 gen=1 seed=42` の単一 profile からの 348 倍換算です。解釈: 条件付けされた 1 サンプルの外挿なので、C3/C7 の観点では強い性能主張に使えません。修正提案: 本番換算は参考値扱いに落とし、「n=1, 条件依存」と明記してください。
- [Suggestion] 事実: selection invariance 仮説は性能仮説と独立です。解釈: 2 つを別判定にした方が設計レビューしやすいです。

**5. リスク**
- [Critical] 事実: `self._precomputed` と `self._precomputed_clauses` の 2 重管理を採る設計です。解釈: reset 漏れ、再 prepare 時の片側更新漏れ、テストが片側だけを見る状態を招きやすく、一貫性リスクが高いです。修正提案: `PreparedSignals(arrays, clauses, bar_count, fingerprint)` のような単一構造にまとめてください。
- [Critical] 事実: P7 の根拠は `SignalConfig` が frozen dataclass であることだけです。解釈: これは「同一 clause 内で `signal.name` が重複しない」ことの根拠になっておらず、前提未検証です。修正提案: clause 構築時に `directional` と `local_gate` を横断して name 一意性を明示検証するか、`values_per_clause` を name ベースではなく position ベースで保持してください。
- [Warning] 事実: duplicate name が存在すると `vals[name] = ...` の後勝ち上書きになります。解釈: 既存実装と同じでも、今回の「bit-identical を高確信」とする主張は弱まります。修正提案: 一意性を設計制約として明文化し、未満なら fail-fast にしてください。

**6. スコープの適切さ**
- [Warning] 事実: `strategy.py` のみを触る案に見えますが、実際には lifecycle 契約とテスト前提も変わります。解釈: 「局所最適化だけ」という表現より、`DslStrategy` の prepared state 契約変更として扱う方が適切です。修正提案: スコープに `DslStrategy state machine` を追加し、`unprepared -> prepared -> consumed/reset` を概念設計に明記してください。
- [Suggestion] 事実: `compute_composite` を触らない方針です。解釈: これは良いスコープ制御です。

**7. メモリ制約（24GB × 6 worker）**
- [Suggestion] 事実: flat list が ndarray を複製せず参照だけ持つなら追加メモリは小さいです。解釈: 24GB × 6 worker 制約には概ね収まります。
- [Warning] 事実: 2 重管理を続けると Python object 数は増えます。解釈: 総量は小さくても、worker 多重時の GC ノイズや object churn はゼロではありません。修正提案: 参照構造を 1 つにまとめ、tuple/list 生成回数も計測対象に含めてください。

**8. 前提検証（C4）**
- [Critical] 事実: 「clause.directional と clause.local_gate の tuple 順序が GA 生成から backtest 実行まで不変」は checklist にあるだけで、Verified 前提ではありません。解釈: 今回の仮説の成立条件そのものが未検証です。修正提案: 前提表に昇格し、コード上の不変条件かテストで検証してください。
- [Critical] 事実: P8 は `prepare() 未呼出 path 維持必須` を示していますが、「prepared state が live/paper で残存しない」ことまでは示していません。解釈: 誤使用リスクの反証がまだ閉じていません。修正提案: `paper/live では prepared state を持ち込めない` 契約を設計に追加してください。
- [Warning] 事実: `git log` と `grep` の記述はありますが、`DslStrategy` インスタンスの生成・再利用境界の根拠は提示されていません。解釈: lifecycle 前提が不足しています。修正提案: orchestrator / engine 側のインスタンス所有期間を前提表に追加してください。

**9. Design-first 原則（C1）**
- [Warning] 事実: docs/devnotes/hotspot の確認はされています。解釈: ただし今回の破綻点はアルゴリズムではなく state 契約なので、設計先行としては lifecycle 記述が足りません。修正提案: 詳細設計に入る前に `DslStrategy` の状態遷移図か契約表を 1 枚追加してください。
- [Suggestion] 事実: 外部 consumer が `strategy.py` と test のみという整理はあります。解釈: この限定は良いですが、「external caller が無い」と「stale state が無い」は別問題として扱うべきです。

**Round 1 反証の要点**
- [Critical] flat list の index 対応は「prepare 後に genome/clause/signal 順序が絶対不変」でないと崩れます。修正提案: fingerprint 検証か fail-fast を入れてください。
- [Critical] `self._precomputed` と `self._precomputed_clauses` の 2 重管理は誤使用と stale state の温床です。修正提案: 単一 prepared state に統合してください。
- [Critical] `signal.name` 一意性は Verified ではありません。修正提案: 検証を追加するか、name 依存を遅延させてください。
- [Warning] `float(arr[idx])` と `isfinite` が残る以上、0.35-0.43s 削減は上振れ仮説です。修正提案: 期待値を保守化してください。

この段階での結論は、**性能改善の方向性自体は妥当だが、bit-identical を支える前提と prepared state 契約が未閉塞なので CHANGES_REQUESTED** です。