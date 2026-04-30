**全体判定**

`CHANGES_REQUESTED`

**Fact**
- Fact: 上位設計として [synthesis.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260428-2300-cascade-port-debate/synthesis.md) と [T058 detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md)、運用文書として [stage-gates.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/stage-gates.md) と [runbook.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/runbook.md)、履歴として `git log` を確認しました。HEAD は `ea56484` です。
- Fact: [synthesis.md:93](/Users/ishitoya/repository/zenigame-fx/devnotes/20260428-2300-cascade-port-debate/synthesis.md#L93) は `24m primary / stride=4w / max_runs/epoch=6 / dataset_epoch_id 必須` を確定値として扱っています。
- Fact: [conceptual-design.md:90](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L90) は `dataset_epoch_id = epoch_{end}_p{epoch_index}` を提案し、[conceptual-design.md:150](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L150) は `anchor_date=cfg.dataset.end` を default にしています。
- Fact: current HEAD の [config.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/config.py) には `SchemaContractConfig` と `EpochManagerConfig` がありません。`src/alpha_factory` 配下にも `run_context.py` と `schema_contract.py` はありません。[TODO.md:9](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/TODO.md#L9) でも T058 は Open のままです。
- Fact: current HEAD の [run_ga.py:1078](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L1078) は `load_calibrated_threshold(...)` を `dataset_span` ベースで呼んでおり、`dataset_epoch_id` はまだ使っていません。
- Fact: current HEAD の [default.yaml](/Users/ishitoya/repository/zenigame-fx/config/alpha_factory/default.yaml) は `dataset.start=2025-10-01`、`dataset.end=2026-04-01` の 6 か月設定です。上位設計の DB 上限は [synthesis.md:94](/Users/ishitoya/repository/zenigame-fx/devnotes/20260428-2300-cascade-port-debate/synthesis.md#L94) の `2026-04-21` です。

**Interpretation**
- Interpretation: T059 概念設計の C4 表は current HEAD と不一致です。前提「T058 受け皿実装済」は成立していません。
- Interpretation: 現案の epoch 切替は「run 回数」と結び付いており、「実データが 4 週進んだこと」と結び付いていません。
- Interpretation: 現案の `dataset_epoch_id` は window そのものではなく `anchor_date` と `epoch_index` にも依存します。したがって stated invariant の「同一 window → 同一 ID」を満たし切れていません。

**観点別レビュー**

1. 使命との整合性
- [Critical] `max_runs/epoch=6` 到達後に次 epoch へ進める設計が、実データ到達性と結び付いていません。[default.yaml](/Users/ishitoya/repository/zenigame-fx/config/alpha_factory/default.yaml) の `dataset.end=2026-04-01` を anchor にすると、次 epoch end は `2026-04-29` になり、[synthesis.md:94](/Users/ishitoya/repository/zenigame-fx/devnotes/20260428-2300-cascade-port-debate/synthesis.md#L94) の DB 上限 `2026-04-21` を超えます。live_criteria 達成に寄与するどころか、実行不能 window を作ります。  
修正提案: epoch advancement は `runs_in_epoch` だけでなく `latest_data_end` と連動させてください。`next_window.end <= latest_data_end_floor` を満たさない限り advance 禁止が必要です。
- [Warning] T058 未着地のため、T059 単独では contamination guard を実効化できません。[run_ga.py:1078](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L1078) はまだ `dataset_epoch_id` を消費していません。  
修正提案: T059 approval 条件に「T058 merge 済 commit を明記」を追加するか、T059 を「T058 merge 後前提」に格下げしてください。
- [Suggestion] 期待効果は「性能改善」ではなく「epoch スコープの正当化」として書く方が正確です。

2. 禁止事項違反
- [Warning] 明示的な禁止事項 1-7 への直接違反は見当たりません。  
修正提案: ただし `override via CLI flag` と `state 破損時 warning + 新規初期化` は構造ガードの迂回路になります。将来導入するなら dev/debug 限定、監査ログ必須、production 禁止を明記してください。
- [Suggestion] `warning で進める` 方針を control-state に持ち込まない方が安全です。T058 の `LOG_ONLY` 思想は schema lint 用であり、epoch cap enforcement 用ではありません。

3. 実現可能性
- [Critical] current HEAD には T058 の受け皿がありません。[src/alpha_factory](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory) に `run_context.py` / `schema_contract.py` が存在せず、[TODO.md:9](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/TODO.md#L9) でも T058 は未完です。  
修正提案: T059 の前提表を current HEAD 基準に更新し、依存関係を `T058 merged first` に変更してください。
- [Critical] `can_start_new_run()` と `finally: register_run()` の二段設計では hard cap を保証できません。atomic rename は torn write を防ぐだけです。lost update と TOCTOU は防げません。  
修正提案: `reserve_run_slot(run_id)` を run 開始前に原子的に実行してください。必要なのは atomic write ではなく file lock 付きの atomic reservation です。
- [Warning] `state_path=Path(".cache/...")` は CWD 依存です。[run_ga.py:1098](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L1098) は calibrate history だけ repo root 解決しています。  
修正提案: epoch state も repo root 基準で解決してください。

4. 期待効果の妥当性
- [Critical] `epoch_{end}_p{epoch_index}` は deterministic 性の定義が弱いです。同一 `(start,end)` でも anchor が 4w ずれると別 `epoch_index` が付きえます。さらに `strftime("%Y%m%d")` は時刻を切り捨てるため、同日内の別 timestamp window も衝突します。[conceptual-design.md:90](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L90)  
修正提案: ID は canonicalized `(window.start, window.end)` のみから生成してください。例は `epoch_20240401_20260401` か、その hash です。`epoch_index` は metadata に下げるべきです。
- [Warning] `max_runs/epoch=6` が selection inflation をどれだけ抑えるかは、現設計では構造仮説です。C3/C7 の観点では、ここで効果量を強く主張すべきではありません。  
修正提案: 「構造的に再利用範囲を制限する」に表現を下げてください。効果量の主張は後段 run analysis で分離してください。
- [Suggestion] collider bias の論点は本 TODO では主に「効果解釈の過剰主張を避ける」用途です。ID 生成ロジック自体には直接当たりません。

5. リスク
- [Critical] `state file 破損 -> warning + 新規初期化` は危険です。過去の archive / calibrate history が残ったまま epoch index だけ 0 に戻ると、旧 epoch_id 再利用や scope 取り違えが起きます。[conceptual-design.md:220](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L220)  
修正提案: control-state 破損は fail-closed にしてください。最低でも「明示 reset flag がない限り abort」が必要です。
- [Warning] state file に `window_length / stride / max_runs / instrument / config fingerprint` がありません。互換性不一致の state 再利用を検出できません。  
修正提案: state schema に compatibility fingerprint を追加し、不一致時は abort してください。
- [Suggestion] append-only journal を別に持つと recovery と監査が楽になります。

6. スコープの適切さ
- [Warning] `file lock`、`state 破損時 policy`、`data horizon check` を out of scope に落とすのは不適切です。これは改善ではなく correctness です。  
修正提案: T059 に含めてください。逆に `CLI override` は本当に out of scope で構いません。
- [Suggestion] T059 の最小スコープは「window identity」「pre-run reservation」「state compatibility check」に絞るのが良いです。

7. メモリ制約
- [Warning] `EpochManager` 自体は軽量です。問題は 24m dataset 化したときの既存 `run_ga.py` + [parallel_eval.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/parallel_eval.py) の bar broadcast です。現状は 6m 前提のメモリ感覚で書かれています。  
修正提案: 24m enable 前に `max_workers=1/2` で RSS 実測を必須化してください。3GB/worker を超えるなら worker 数を落とすか SharedBarStore 相当を別 TODO 化してください。
- [Suggestion] T059 approval 条件に「24m 化はまだ有効化しない」か「有効化するなら memory gate 実測必須」を入れると安全です。

8. 前提検証 (C4)
- [Critical] 概念設計の verified 表は current HEAD と一致していません。`RunContext` 受け皿、`schema_contract.py`、`dataset_epoch_id` wiring は未実装です。  
修正提案: verified を `False/Unverified` に戻し、T058 merge commit hash を参照する形に書き換えてください。
- [Warning] `anchor_date=cfg.dataset.end` は current config 6m と、将来の dynamic 24m dataset の両方に対して意味が曖昧です。  
修正提案: `anchor_date` の定義を「epoch 0 の end」ではなく「schedule origin」か「latest available epoch end snap」のどちらかに固定してください。

9. Design-first (C1)
- [Suggestion] レビュー側では C1 を満たしました。docs / devnotes / git log / current code を参照済みです。
- [Warning] 設計書側は C1 をまだ満たしていません。current HEAD のコード状態と verified 表がズレています。  
修正提案: 設計書冒頭に「verified against main@ea56484 ではない」か、反対に「verified against merge commit X」を明記してください。

**質問事項への回答**

1. `dataset_epoch_id` 生成式の deterministic 性
- [Critical] 不十分です。同一 window でも anchor 変更により `epoch_index` が変われば ID が変わります。`end` の date-only 化も衝突源です。  
修正提案: ID は canonical `(start,end)` だけで作ってください。`epoch_index` は識別子ではなく補助 metadata に下げるべきです。

2. state file の atomic write
- [Critical] atomic write だけでは足りません。複数 worker / 複数 run / crash 再開に対して cap enforcement は成立しません。  
修正提案: T059 内で file lock 付き `reserve_run_slot` を実装してください。別 TODO 分離は不可です。

3. `anchor_date` の管理
- [Critical] `cfg.dataset.end` default は妥当ではありません。mutable で、6m current config と 24m future schedule を混線させます。warning-only も弱すぎます。  
修正提案: anchor/schedule origin を state に固定し、不一致時は fail-closed にしてください。reset は明示 flag のみ許可でよいです。

4. state file 破損時の挙動
- [Critical] `warning + 新規初期化` は不整合を増幅します。T058 LOG_ONLY との整合を根拠にしてはいけません。対象が違います。  
修正提案: fail-closed へ変更してください。代替は「archive/history から再構築できる場合のみ rebuild」です。

5. `can_start_new_run` の RUN abort
- [Warning] 方針としては abort が正しいです。warning + 強行は不可です。  
修正提案: ただし abort 判定は pre-run reservation と一体化してください。現案の `can_start_new_run` 単独では強制力がありません。

6. `stride=4w` 固定
- [Suggestion] 問題ありません。上位 synthesis の baseline が旧議論より優先です。  
修正提案: ただし「月次相当」ではなく「28日固定」と表現した方が誤読を減らせます。

7. 見落とし論点
- [Critical] `epoch advance` が DB data horizon を超える論点が未処理です。これは最優先です。  
修正提案: `latest_data_end` check を追加してください。
- [Warning] `state_path` の CWD 依存が未処理です。  
修正提案: repo root 解決にしてください。
- [Warning] state compatibility fingerprint が未処理です。  
修正提案: `instrument/window/stride/max_runs/anchor_origin` を保存して照合してください。
- [Suggestion] `started/completed/failed` の run status を state/journal に残すと監査しやすくなります。

本質的誤りは 3 点です。`dataset_epoch_id` が window identity になっていないこと、epoch progression が data availability と切れていること、cap enforcement が lock-free で実効性を持たないことです。これが解消されれば、T059 は baseline の `dataset_epoch_id` 値生成側として成立に近づきます。