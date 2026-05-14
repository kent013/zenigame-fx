**全体判定: CHANGES_REQUESTED**

Round 1 の主要論点はかなり整理されていますが、まだ **schema 契約の自己矛盾** と **`max_workers=1` 計測経路の正確性** が残っています。施策 5 の PoC ゲートと scale-int 固定は妥当です。

**前提検証 (C4)**
- Fact: 今回は提示テキストのみをレビューしました。
- Fact: コード実体、git 履歴、grep 証跡、parquet 集計は未検証です。
- Interpretation: grep 証跡と現行コード一致は **INCONCLUSIVE** として扱います。

**施策別判定**
| 施策 | 判定 |
|---|---|
| 1 二層メモリ計測 | REQUEST_CHANGES |
| 2 4項メモリモデル | REQUEST_CHANGES |
| 3 Aux cache 管理 | APPROVE |
| 4 `PriceBar/Ohlc __slots__` | INCONCLUSIVE |
| 5 mmap SoA | APPROVE |
| 決定論ゲート | APPROVE with Warning |

**指摘**
[Critical] 施策1/2: `schema_version` 不変・トップレベルキー集合不変と、`memory_model_inputs` 常時トップレベル追加が矛盾しています。  
Fact: 施策1では「無効時はトップレベルキー集合が現行と完全一致」とあります。施策2では `memory_model_inputs` を summary に常時出力するとあります。  
Interpretation: Round 1 の schema 問題が `memory_profile` では解消された一方、施策2で同じ型の互換性問題が再発しています。  
修正案: `memory_model_inputs` は `parallel_config.memory_model_inputs` 配下に入れる、または「トップレベルキー集合完全一致」を契約から外して additive diagnostics を許容すると明記してください。前者を推奨します。

[Critical] 施策1: `max_workers=1` の `measure_worker_memory` が実データを測れない可能性があります。  
Fact: 提示コードでは spawn worker の module-global は `_init_worker` が設定します。一方、`pool is None` 経路で `_measure_worker_memory_task(None)` を呼ぶ設計です。  
Interpretation: sequential 経路で `_WORKER_LANE_CONTEXTS` が初期化されていない場合、計測マトリクスの `max_workers=1` 条件が空計測になります。  
修正案: `GenomeEvaluator` が保持する `lane_contexts` / `prim_evaluator` を使う in-process 専用計測関数を追加してください。module-global に依存しない形が安全です。

[Warning] 施策1: `peak_rss_per_generation[idx]` に `worker_object_breakdown` をマージする記述が残っています。  
Fact: 成果物では `memory_profile.per_generation[*]` に隔離すると書かれています。  
Interpretation: 実装者が legacy per-generation 側へ追加してしまう余地があります。  
修正案: legacy `peak_rss_per_generation` には従来 RSS キーだけを残し、USS と object breakdown は `memory_profile.per_generation` にだけ格納すると明記してください。

[Warning] 施策1: `_recursive_sizeof` の ndarray view 計上規則はもう一段具体化が必要です。  
Fact: `arr.base is not None` の場合に base 側を `_seen` に登録するとあります。  
Interpretation: view のヘッダ、owner buffer、複数 view の扱いで過小/過大計上が起き得ます。  
修正案: base chain の owner を特定し、owner buffer bytes は一度だけ、view object header は view ごとに計上する規則に固定してください。dataclass と slots の二重走査も避ける分岐順を明記してください。

[Warning] 施策1: worker 被覆未達時の failure policy が少し揺れています。  
Fact: `target_pids` 未被覆なら `RuntimeError`、一方で「計測は本番を止めない」とあります。  
Interpretation: `--mem-profile` 有効時は止める設計としては妥当ですが、文言が fail-open と読めます。  
修正案: `--mem-profile` 有効時の被覆未達は fail-closed、psutil USS 取得失敗だけ fail-open、と明記してください。

[Warning] 施策4: grep 証跡は設計上は十分ですが、レビュー上は未検証です。  
Fact: 設計書には grep 結果 0 件とあります。  
Interpretation: 実コード確認なしでは APPROVE までは上げられません。  
修正案: 実装直前 grep のコマンドと結果を devnotes に固定し、テストで pickle/spawn 経路を押さえれば APPROVE 可能です。

[Warning] 施策5: scale-int 方針は妥当ですが、scale 決定規則が未確定です。  
Fact: 「pip スケール等」とあります。  
Interpretation: OANDA 由来の小数桁や USD_ZAR などで lossless 条件が曖昧です。  
修正案: pair 別固定 scale ではなく、入力 Decimal の exponent 最大値から dataset/instrument ごとに lossless scale を決める PoC を推奨します。`int64` overflow check も PoC 条件に入れてください。

**重点論点への再判定**
- `(a) memory_profile 隔離`: 概ね妥当。ただし `memory_model_inputs` 常時トップレベル追加との契約衝突は未解消。
- `(b) measure_worker_memory 被覆保証`: `max_workers>1` の pid 被覆ロジックは妥当。`max_workers=1` 経路は修正必須。
- `(c) 施策5 PoC + scale-int`: 妥当。着手抑制として十分に保守的。
- `(d) recursive_sizeof`: 方針は改善済み。ndarray view と dataclass/slots 二重走査規則を明文化すれば十分。
- `(e) selected_genome_names`: 追加は妥当。`lane_id/generation` ごと、順序込み、診断出力が選抜処理に影響しない形で取得する条件を明記するとさらに堅いです。