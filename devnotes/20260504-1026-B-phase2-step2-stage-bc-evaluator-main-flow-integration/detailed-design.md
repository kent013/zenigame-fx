# 詳細設計: B Phase 2 Integration Program — step 2.1 (stage_bc_evaluator shadow integration)

**作成日時**: 2026-05-04 11:13 JST (Round 2: 2026-05-04 11:25 JST、 Round 3: 2026-05-04 11:40 JST、 Round 4: 2026-05-04 11:50 JST、 Round 5 改訂: 2026-05-04 12:00 JST、 max round = 本文 SSOT 完全更新)
**status**: **詳細設計 Round 5 (= Codex Round 4 APPROVE_WITH_CHANGES + Round 1-3 累積指摘を本文 SSOT に完全反映、 capture sink 経由 + WorkerEvaluationResult 配置確定、 Round 5 review = max round で APPROVED 狙い)**
**概念設計**: `devnotes/20260504-1026-B-phase2-step2-stage-bc-evaluator-main-flow-integration/conceptual-design.md` (Codex Round 5 APPROVED、 案 B 採用 + step 2.1 (= 2.1a + 2.1b) scope 化)

---

## 0. 改訂対応マトリクス

### 0.-3 Round 4 → Round 5 改訂対応マトリクス (= 本文 SSOT 完全更新)

| Round 4 指摘 | 対応 |
|---|---|
| § 1 [Critical] wrapper return None のまま (= 全 event emit helper が dict 返却 + no-raise contract) | § 4.3 wrapper 内 inner / `_emit_shadow_event` を **`dict[str, Any]` 必ず return** に変更 (= `_emit_shadow_event` は payload を return、 caller が capture sink に格納)。 outer try/except 経路でも minimum failed payload を return |
| § 1 [Critical] shadow_context.identity 参照未統一 | wrapper 内で `identity = shadow_context.identity` を先頭で束縛、 全 event payload で identity 由来 (= run_id / generation_no / individual_index / genome_hash) を使う |
| § 1 [Critical] builder 呼出 bars_holdout / bounded_recompute_mode 未渡し | wrapper inner の builder 呼出を `build_bc_evaluation_input_from_sidecar(..., bars_holdout=tuple(bars_holdout), bounded_recompute_mode=shadow_context.bounded_recompute_mode)` に修正 |
| § 1 [Warning] WorkerEvaluationResult 配置 | bc_evaluator_shadow.py から **`src/alpha_factory/parallel_eval.py`** (= 中立 module、 既存 GenomeStageResult 隣接) に移動 |
| § 2 [Critical] collector に n_invalid_events / n_anchor_only / n_anchor_plus_shadow 未追加 | § 5.2 collector 本文を更新: scope 別 attempted/ok/degraded/failed/skipped + n_invalid_events + invalid_event_rate を追加、 record_event の必須 field validation 反映 |
| § 2 [Warning] degraded_rate と observation_scope 混同回避 | summary schema に `degraded_rate_by_reason` 追加、 anchor_only と「評価失敗」を区別 |
| § 2 [Warning] anchor_plus_shadow 母集団 attempted | summary に `n_anchor_plus_shadow_attempted` 追加 (= 2.2 exit criteria 用 = 全体 n_attempted とは別) |
| § 4 [Critical] **`evaluate_stage_c` の payload 受け渡し方法**: capture sink パターン採用 | **`bc_shadow_event_capture: list[dict] | None = None`** を evaluate_stage_c の optional 引数に追加。 wrapper return を capture sink (= list) に append、 _evaluate_genome_steps が capture から payload を取り出して WorkerEvaluationResult に格納 |
| § 4 [Critical] bc_shadow_identity signature 未反映 | `evaluate_stage_c` に `bc_shadow_identity: StageBCShadowIdentity | None = None` 追加、 context_missing 時は共通 helper `_emit_context_missing_event(identity, capture)` を呼ぶ |
| § 4 [Warning] emit / return 順序固定 | wrapper 内: `payload build → logger no-raise → capture no-raise → return payload` の順序を SSOT |
| § 5 [Critical] _evaluate_genome_steps が payload 受け取る方法 | `_evaluate_genome_steps` 内で `bc_shadow_event_capture: list[dict] = []` を作り、 `evaluate_stage_c(..., bc_shadow_event_capture=bc_shadow_event_capture)` 後に `WorkerEvaluationResult(c_result=c_result, shadow_event_payload=bc_shadow_event_capture[-1] if bc_shadow_event_capture else None)` で return |
| § 5 [Warning] worker 例外で return 不能時の attempted 漏れ | parent 側で submitted futures 数 = `n_genomes_submitted` を別集計、 received payload 数 = `n_genomes_attempted` (= shadow event を受け取った genome 数) で 2 値分離、 summary に `n_genomes_submitted` 追加 |
| § 6 [Warning] swim_lane / parallel_eval 共通化 | payload extraction / collector record helper を bc_evaluator_shadow.py に共通化 (= `record_worker_evaluation_result(worker_result, collector)` helper) |
| § 6 [Warning] LaneManager 親で 1 回 emit | LaneManager `__exit__` で `emit_run_summary` を **必ず 1 回だけ** 呼ぶ、 lane ごと emit 禁止 |
| § 7 [Critical] test 表 #1-40 本文反映 | § 9.1 を全件更新 (= test #1-40)、 archive 非混入 / pool 2 workers 集約 / anchor_plus_shadow 母集団 / collector scope 別 rate を必須化 |
| § 7 [Warning] holdout edge cases acceptance C4 本体に移動 | § 5.3 acceptance C4 を「holdout < 180 / 端数 / 営業日暦日 / bar 欠損 5 ケース fixture」 で本体化、 follow-up 削除 |
| § C3/C7 collider bias 防止 | anchor_only と anchor_plus_shadow は別母集団として扱う、 anchor_only は 2.2 で INCONCLUSIVE 扱い (= valid n に算入しない) を § 1.7 ガードに明記 |

**Round 5 max round 戦略**: 構造方向 (= Round 4 で APPROVE_WITH_CHANGES) は確定済、 Round 5 で本文 SSOT 完全更新を施し APPROVED 狙い。 残 detail (= 9 fields 表 mode 別分離 / decision table 全件 / collector 全 method 実装 / test 全件 sample code) は impl-review で確認する戦略 (= 設計レベルでは構造 + 主要 SSOT が確定すれば実装着手可能)。

### 0.-2 Round 3 → Round 4 改訂対応マトリクス (= 本文 SSOT 化 + WorkerEvaluationResult 分離)

| Round 3 指摘 | 対応 |
|---|---|
| § [Critical] 本文コードが Round 3 構造に追従していない (= shadow_context.run_id → identity 参照に未統一) | 本文の wrapper / evaluate_stage_c / parallel_eval / swim_lane 全コード snippet で `shadow_context.identity.run_id` 等に統一 (= SSOT 化) |
| § [Critical] **`GenomeStageResult.shadow_event_payload` は E1/E2 dormant 漏洩リスク** | **新規 dataclass `WorkerEvaluationResult`** を導入 (= archive 対象外 envelope)。 `_evaluate_genome_steps` の return type を `WorkerEvaluationResult` に変更 (= `c_result: GenomeStageResult` + `shadow_event_payload: dict | None`)。 GenomeStageResult は **完全不変** (= archive 互換、 acceptance E1/E2 完全保証) |
| § [Critical] wrapper return None で payload 取得不能 | `evaluate_stage_bc_shadow_safe` の return type を **`dict[str, Any] | None`** に変更 (= shadow event payload を返却、 caller が collector record_event に渡す) |
| § [Critical] evaluate_stage_c signature に bc_shadow_identity 追加 | evaluate_stage_c に `bc_shadow_identity: StageBCShadowIdentity | None = None` 追加、 context_missing 時にも identity で C3 識別子契約満たす |
| § [Critical] context_missing は stage_gate.py 内 schema drift リスク | `_emit_context_missing_event(identity, collector)` を **bc_evaluator_shadow.py 共通 helper** に集約、 stage_gate.py からは helper 呼出のみ |
| § [Critical] genome_hash 計算失敗時の identity safe fallback | `build_shadow_identity_first_safe` で `genome_hash="<hash_failed>"` + `identity_error` 返却、 identity 自体は必ず作る |
| § [Critical] observation_scope と status の決定表未定義 | § 4.4.1 決定表新設 (= bounded_recompute_mode + 計算結果から status / observation_scope を一意決定) |
| § [Critical] collector 本文 Round 2 のまま | 本文 § 5.2 collector 実装で `n_invalid_events` / `invalid_event_rate` / record_event 必須 field validation を反映 |
| § [Critical] smoke grep 撤廃 + parent 集約に統一 | § 5.3 を「step 2.1 正式仕様 = WorkerEvaluationResult.shadow_event_payload 経由 parent 集約」 に統一、 smoke は検証補助のみ |
| § [Critical] swim_lane も archive 漏洩リスク | swim_lane 同型: lane worker → WorkerEvaluationResult return → LaneManager で payload 集約 |
| § [Critical] テスト #33-35 + C4 5 ケース 本文反映 | § 9.1 test 表を 35 + 5 = 40 ケースに更新 |
| § [Critical] payload archive 漏洩 test | test #36 (新設): shadow_enabled=True で `GenomeStageResult` / archive Parquet snapshot に shadow_event_payload が **絶対漏れない** deep equality |
| § [Critical] payload return integration test | test #37 (新設): worker → WorkerEvaluationResult → parent collector → emit_run_summary の E2E |
| § [Warning] degraded_rate に anchor_only も含めると混同 | shadow_run_summary に `n_anchor_only` / `n_anchor_plus_shadow` 追加、 2.2 判断は anchor_plus_shadow 母集団のみで実行 |
| § [Warning] worker と parent の二重 counting 回避 | per-genome event は worker が 1 回 logger.info、 parent は payload count のみで re-log しない、 § 5.3 明記 |
| § [Warning] lane / pool で identity 採番規則 | `build_shadow_identity_first_safe` 共通 helper で完全共通化、 採番 source (= run_id / generation_no / individual_index) を caller 提供 |
| § [Warning] anchor_only / anchor_plus_shadow の母集団分離 test | test #38 (新設): 2.2 exit criteria 用集計で母集団分離 (= anchor_only は exit criteria の n>=30 に算入しない) |
| § [Warning] config round-trip test | test #39 (新設): StageGateConfig load/dump round-trip (= 未指定 default False / 明示 True / 明示 False) |

**重要決定**: **`anchor_plus_shadow` のみが step 2.2 exit criteria の有効観測母集団** (= 通常 run の anchor_only は除外、 専用検証 run のみ valid)、 § 1.5 exit criteria に明記。

### 0.-1 Round 2 → Round 3 改訂対応マトリクス

| Round 2 指摘 | 対応 |
|---|---|
| § 1 [Critical] builder signature 不一致 (= bars_holdout / bounded_recompute_mode 渡されていない) | wrapper 内 `_evaluate_stage_bc_shadow_inner` で `bars_holdout=tuple(bars_holdout)` + `bounded_recompute_mode=shadow_context.bounded_recompute_mode` を必ず渡す。 § 4.3 wrapper コード修正、 test #4/#30/#31 で実経路通る |
| § 1 [Critical] shadow_pairs={} の意味論不明 | `bc_summary.observation_scope: Literal["anchor_only", "anchor_plus_shadow"]` field を schema v1 に追加。 通常 run (= bounded_recompute_mode=False) は `observation_scope="anchor_only"` で `status="degraded"` 扱い、 専用検証 run のみ `anchor_plus_shadow` で `status="ok"` 可能 |
| § 1 [Critical] 9 fields 対応表の意味論矛盾 | mode 別に表分離 (§ 4.4): `bounded_recompute_mode=False` 行で shadow_pairs を `{} / observation_scope=anchor_only` と明示、 `bounded_recompute_mode=True` 行で `materialize / observation_scope=anchor_plus_shadow` |
| § 1 [Critical] collector 例外時の二重 event | `_emit_shadow_event` 内で collector.record_event を try/except で囲む (= collector raise を握って、 event emit 後の例外で二重 event 出さない、 § 4.3 修正、 test #N (新設) で固定) |
| § 1 [Warning] copy/recompute 表記訂正 | 9 fields 対応表で reference を **`recompute / copy / reference`** の 3 値に分類 |
| § 1 [Warning] failure_reason / skip_reason 分離 | per-genome event に `failure_reason` field を追加 (= `bc_summary.status="failed"` のみ非 None)、 skip_reason は `shadow_skipped=True` のときのみ |
| § 2 [Critical] pool 経路で collector が None で run_summary emit 不能 | **`GenomeStageResult.shadow_event_payload: dict | None`** field 追加、 worker は payload を返却、 親 (GenomeEvaluator) で futures から集約して `collector.record_event` 呼出、 run 終端で `emit_run_summary` (= acceptance C6 を pool 経路で実装) |
| § 2 [Critical] 親プロセス集約 vs smoke script 集計の責務曖昧 | **step 2.1 正式仕様: pool summary supported** (= GenomeStageResult.shadow_event_payload 経由で親集約)、 smoke スクリプトは検証補助 (= step 1.8 同型の RSS / wall-clock 計測のみ) |
| § 2 [Warning] schema 不正 payload silently skip | `record_event` で必須 field (= schema_version / run_id / individual_index / bc_summary.status) を validate、 不正 payload は `n_invalid_events` として別集計 |
| § 4 [Critical] context_missing の identifier 欠落 (= run_id="<unknown>") | **`StageBCShadowIdentity` (新規 dataclass)** で最小識別子 (= run_id / generation_no / individual_index / genome_hash) を context 構築前に作る。 evaluate_stage_c に別引数で渡す、 context 構築失敗時も schema v1 識別子契約 C3 維持 |
| § 4 [Critical] _emit_context_missing_shadow_event の責務未定義 | bc_evaluator_shadow.py に `_emit_context_missing_event(identity, collector)` 共通 helper、 通常 event と同じ schema builder + no-raise collector guard |
| § 4 [Warning] outer catch でも per genome 1 event 保証不足 | outer catch で最小識別子つき failed event を emit (= identity を必須引数化、 helper を no-raise 化) |
| § 5 [Critical] build_shadow_context 失敗時に identity が無い | **`build_shadow_identity_first` (新規 helper)**: parallel_eval / swim_lane の最初に identity を作る、 context 構築は次段階。 build_shadow_context_safe → tuple[context|None, identity, error_reason] 形式 |
| § 5 [Critical] pool 経路で collector=None なら summary 0 件 | GenomeStageResult.shadow_event_payload 経由集約 (= § 2 [Critical] と同じ修正) |
| § 5 [Warning] holdout list は既存 API 互換性で list 必須 | 確認: 既存 `evaluate_stage_c` signature が `bars_holdout: list[PriceBar]` なので list 維持、 ただし shadow context 用は tuple 化 |
| § 6 [Critical] swim_lane も pool / lane 並列時 summary 集約契約未確定 | swim_lane も同型: lane worker から payload return、 LaneManager で集約 + emit_run_summary |
| § 6 [Warning] context 構築失敗時の経路間共通化 | `build_shadow_context_safe` を返り値 3-tuple に統一 |
| § 7 [Critical] bounded_recompute_mode が integration まで通らない test 不足 | test #33 (新設): `evaluate_stage_bc_shadow_safe` 経由で mode true/false の挙動を検証 |
| § 7 [Critical] collector 例外時の二重 event 防止 test 不足 | test #34 (新設): record_event を raise させ、 log event 1 件 + main flow 不変を assert |
| § 7 [Critical] pool 経路 run_summary emit test 不足 | test #35 (新設): 2 worker 以上の最小 fixture で親集約 + summary 1 件 emit を検証 |
| § 7 [Warning] stage_c_lite_periods C4 acceptance 詳細 | acceptance C4 を「holdout < 180 / 端数 / 営業日 / 暦日 / bar 欠損 全パターン」 に拡張、 test fixture 5 ケース新設 |
| § 7 [Warning] 25/32 数値不整合 | § 9.3 実装規模を **35 ケース** (= test #1-35) に統一 |

### 0.0 Round 1 → Round 2 改訂対応マトリクス

| Round 1 指摘 | 対応 |
|---|---|
| § 1 [Critical] wrapper 冒頭 genome_hash / legacy_summary 保護なし | **wrapper 全体を最外周 try/except で囲む** (= 例外時 `stage_bc_evaluator.shadow_failure` WARN + `failed/skipped` emit、 acceptance D1/D2 反映)。 § 4.3 wrapper 構造を修正 |
| § 1 [Critical] shadow_pairs の eager materialization で 6 worker メモリ反証 | **lazy materialization 実装**: 通常 run では参照共有のみ (= sidecar→bundle の都度変換禁止)、 専用検証 run (= bounded_recompute_mode=True) のみ展開許可。 § 4.3 builder + § 4.4 9 fields 表に明記 |
| § 1 [Critical] schema key `diffs` / `descriptive_diff` 不整合 | schema v1 の payload key を **`descriptive_diff` に統一** (= 旧 `diffs` を撤廃)、 § 4.3 `_emit_shadow_event` 修正、 acceptance C1 / 概念設計 § 2.3 と整合 |
| § 1 [Warning] bounded_recompute_mode 未分岐 | builder 内で **mode 別 guard 実装**: `bounded_recompute_mode=False` (= 通常 run) で `_run_pair_sharpe` 等の追加 backtest 経路に絶対入らない、 acceptance D3 (= 新設) で固定 |
| § 1 [Warning] stage_c_period 導出 bars_b ベースは T064 と一致不明 | `_derive_stage_c_periods` の derive source を **`bars_holdout`** に変更 (= T064 SSOT 入力と整合)、 acceptance C4 fixture で 1対1 対応 test 固定 |
| § 2 [Critical] collector run-level 集計が worker 単位で分断 | **親プロセス集約に変更** (= multiprocessing Queue or 直接 in-process passing)。 worker は event 払出すのみ、 collector は parallel_eval / swim_lane / run_ga の親プロセスで保持。 § 5.2 / § 8 caller 構造を修正 |
| § 2 [Warning] `n=max(1, attempted)` は偽観測 | `attempted=0` のとき **`shadow_run_summary` を emit しない** (= 観測なし)、 § 5.2 修正 |
| § 4 [Critical] context is None で context_missing event 未 emit | `evaluate_stage_c` で **`shadow_enabled=True かつ context is None` のとき `context_missing` event を emit** (= 直接 logger 経由、 wrapper 経由しない)、 acceptance C2 強化 |
| § 4 [Warning] wrapper 二重隔離弱 | `evaluate_stage_c` 側でも shadow 呼出を **try/except で囲む** (= 多層防御)、 § 7.2 配線修正 |
| § 5 [Critical] collector 所有境界曖昧、 並列時 1 件集計保証不足 | **親オーケストレータのみ保持**: GenomeEvaluator (親プロセス) / LaneManager / run_ga が collector 保持、 worker は event payload を返すのみ。 § 8 改修方針修正 |
| § 5 [Warning] `bars_b=tuple(ctx.bars_b)` 個体ごと生成でメモリ圧迫 | **immutable 参照共有** (= ctx.bars_b 自体を tuple で持つ前提に統一、 個体ごとコピーしない)。 § 8 修正 |
| § 6 [Warning] swim_lane / parallel_eval の集計・隔離契約共通化 | **共通 helper** (= bc_evaluator_shadow.py に context 構築 helper) で集約、 caller 双方から同 helper を呼ぶ |
| § 7 [Critical] test に context_missing なし | test #16 を「`evaluate_stage_c with shadow_enabled and context_missing emits skipped event`」 に変更、 test list 拡張 |
| § 7 [Critical] wrapper 冒頭例外 test 不足 | test #N (新設) で hash 生成失敗 / legacy 抽出失敗 を mock し `StageResult` 不変 + WARN log を assert |
| § 7 [Warning] B4 専用検証 run 依存で継続的回帰検知弱 | 1/2/4/6 worker 計測スモークを **semi-automate** (= step 1.8 smoke スクリプト同型を step 2.1b に拡張、 閾値逸脱時 fail)。 § 12 拡張 |

---

## 1. 使命・制約 (絶対遵守)

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。 絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1. A・B・C 評価期間延長
2. 数値見せかけ改善
3. GA ハック
4. live_criteria 緩和
5. **過度な複雑化** ← 本 step で特に重要 (= 段階分割で複雑度を抑制)
6. 取引回数削減
7. オーバーナイト保有前提
8. ゲノム archive スキーマ変更時の値伝搬漏れ

### コーディングルール
- バグ修正はテストファースト
- 全施策にテスト必須
- テスト命名: 振る舞い説明的、 汎用的
- テスト配置: 対象モジュール対応のテストファイル
- uv 必須: `uv run pytest tests/alpha_factory/`
- ruff / mypy 通過

---

## 2. 概念設計リファレンス

`devnotes/20260504-1026-B-phase2-step2-stage-bc-evaluator-main-flow-integration/conceptual-design.md` (Round 5 APPROVED)

主要決定:
- **scope**: B Phase 2 Integration Program 配下 step 2.1 (= 2.1a input feasibility + 2.1b shadow logging)、 LOG_ONLY、 BCEvaluationResult は post-evaluation に流さない
- **采用案**: 案 B 段階分割 (= 2.1a → 2.1b → 2.2 switch → 2.3 deprecation)、 「Phase 2 切替コミット完了」 呼称は 2.2 完了時のみ
- **配置場所**: shadow 配線は `stage_gate.evaluate_stage_c` 内、 step 1.8 try-finally 構造の try 末尾 (= sanitize 直前)、 sidecar 利用可能性と sanitize SSOT 完全維持を両立
- **`StageBCShadowContext`**: caller (parallel_eval / swim_lane) で構築、 evaluate_stage_c 新引数で渡す (= Stage B artifacts 供給経路)
- **`BCShadowEventCollector`**: 上位層 GenomeEvaluator / LaneManager が保持、 run 終端で `stage_bc_evaluator.shadow_run_summary` emit
- **shadow_enabled=True で全件 emit**: ok/degraded/failed/skipped + context_missing 全 5 case で per genome 1 event 必須 (= 偽観測排除)
- **`uncontrolled full backtest` 禁止** (= 通常 run)、 `bounded recomputation` は専用検証 run のみ
- **schema v1**: identifier 4 軸 + genome_serialization_version + legacy/bc summary + descriptive_diff + skip_reason、 shadow_run_summary は 3 rate 分離 (= skip / failure / degraded) + n_genomes_attempted 分母統一
- **acceptance**: A1-A4 (regression 0) + B1-B5 (= sanitize 順序契約含む) + C1-C7 + D1-D2 + E1-E2

---

## 3. 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|---|---|---|
| 1 | `bc_evaluator_shadow.py` 新規 module: `StageBCShadowContext` + `_PairBacktestBundle` 構築 helper + builder + wrapper + log emit | src/alpha_factory/bc_evaluator_shadow.py | High |
| 2 | `bc_evaluator_shadow_collector.py` 新規 module: `BCShadowEventCollector` (= run-level 集約 + emit_run_summary) | src/alpha_factory/bc_evaluator_shadow_collector.py | High |
| 3 | `stage_gate.StageGateConfig` に `phase2_bc_evaluator_shadow_enabled: bool = False` field 追加 | src/alpha_factory/stage_gate.py | High |
| 4 | `stage_gate.evaluate_stage_c` に新引数 `bc_shadow_context / bc_shadow_collector` 追加 + try-finally 末尾 (= sanitize 直前) で shadow 配線 | src/alpha_factory/stage_gate.py | High |
| 5 | `parallel_eval._evaluate_genome_steps` で `StageBCShadowContext` 構築 + `evaluate_stage_c` 引数追加 + `GenomeEvaluator` に `BCShadowEventCollector` 保持 + run 終端 emit | src/alpha_factory/parallel_eval.py | High |
| 6 | `swim_lane` で同型修正 (= context 構築 + 引数追加 + LaneManager に collector 保持) | src/alpha_factory/swim_lane.py | High |
| 7 | テスト 25 ケース追加 + 既存 2208 PASS 後方互換確認 | tests/alpha_factory/test_bc_evaluator_shadow.py + test_bc_evaluator_shadow_collector.py + test_parallel_eval_bc_shadow.py | High |

---

## 4. 施策 1: `bc_evaluator_shadow.py` 新規 module

### 4.1 変更箇所
- ファイル: `src/alpha_factory/bc_evaluator_shadow.py` (= 新規)

### 4.2 波及変更
- import: `stage_gate.CrossPairResult` / `stage_gate._PairSidecarInputs` (= step 1.8 で確立) を再利用
- `stage_bc_evaluator.{BCEvaluationInput, evaluate_bc_for_a_pass, PairBacktestBundle}` import
- `failure_handling.evaluate_bc_safe` import (= isolation boundary)

### 4.3 module 構成 (= 概念設計 § 2.1 / § 2.2 反映)

```python
# bc_evaluator_shadow.py
from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

import structlog

from src.alpha_factory.canonical_adapter import (
    compute_business_day_universe_from_bars,
    equity_curve_to_bar_equity_series,
    trade_to_trade_record,
)
from src.alpha_factory.failure_handling import evaluate_bc_safe
from src.alpha_factory.partition import Fold, Period
from src.alpha_factory.stage_bc_evaluator import (
    BCEvaluationInput,
    BCEvaluationResult,
    PairBacktestBundle,
    evaluate_bc_for_a_pass,
)
from src.alpha_factory.stage_gate import (
    CrossPairResult,
    StageGateConfig,
    StageResult,
    _PairSidecarInputs,
)
from src.alpha_factory.walk_forward import make_wf_folds
from src.broker.orders import Trade as BrokerTrade
from src.domain.price import PriceBar
from src.dsl.genome import Genome

logger = structlog.get_logger(__name__)

GENOME_SERIALIZATION_VERSION = 1
SHADOW_EVENT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class WorkerEvaluationResult:
    """step 2.1 で parallel_eval / swim_lane の worker return type (= 新規、
    Round 3 [Critical] 反映で archive 漏洩防止).

    archive 対象外 envelope:
    - `c_result: GenomeStageResult`: 既存 GenomeStageResult (= archive 対象、
      shadow_event_payload を絶対含まない、 acceptance E1/E2 完全保証)
    - `shadow_event_payload: dict | None`: worker→parent 専用、 archive に流さない
      (= parent collector で record_event に渡す)
    """
    c_result: "GenomeStageResult"  # 既存 (= archive 対象)
    shadow_event_payload: dict[str, object] | None = None  # parent 集約用


@dataclass(frozen=True)
class StageBCShadowIdentity:
    """step 2.1 shadow 配線の最小識別子 (= Round 2 [Critical] 反映).

    context 構築失敗時にも識別子契約 C3 を満たすため、 run_id / generation_no /
    individual_index / genome_hash を context とは別途構築する。 caller
    (parallel_eval / swim_lane) が `_evaluate_genome_steps` の最初に必ず作成し、
    後続経路 (= context 構築 / wrapper) に必ず渡す。

    field:
        run_id: run 識別子
        generation_no: GA 世代番号
        individual_index: 個体 index
        genome_hash: sha256(canonical_serialization(genome)) (= identifier 4 軸)
    """
    run_id: str
    generation_no: int
    individual_index: int
    genome_hash: str


@dataclass(frozen=True)
class StageBCShadowContext:
    """step 2.1 shadow 配線用 context (= caller から artifacts を渡す).

    field:
        run_id: run 識別子
        generation_no: GA 世代番号
        individual_index: 個体 index
        genome: 評価対象 Genome (= genome_hash 生成 + builder 入力 SSOT)
        legacy_b_result: 既存 evaluate_stage_b 結果 (= trades / equity_curve source)
        bars_b: Stage B 評価窓 bars (= folds / business_day_universe source)
        bounded_recompute_mode: 専用検証 run のみ True、 通常 run は False
    """
    identity: StageBCShadowIdentity  # 最小識別子 (= 必須)
    genome: Genome
    legacy_b_result: StageResult
    bars_b: tuple[PriceBar, ...]
    bounded_recompute_mode: bool = False


def _compute_genome_hash(genome: Genome) -> str:
    """genome の canonical serialization から sha256 を計算.

    serialization version は GENOME_SERIALIZATION_VERSION で schema v1 に固定。
    """
    canonical = json.dumps(
        genome.to_dict() if hasattr(genome, "to_dict") else _genome_repr_canonical(genome),
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _genome_repr_canonical(genome: Genome) -> dict[str, Any]:
    """genome を serialization 可能な dict に変換 (= to_dict 不在時 fallback)."""
    return {
        "name": genome.name,
        "units": genome.units,
        "clauses": [
            {
                "directional": [{"name": s.name, "weight": s.weight, "params": s.params}
                                 for s in c.directional],
                "local_gate": [{"name": s.name, "params": s.params}
                                for s in c.local_gate],
                "weight": c.weight,
            }
            for c in genome.clauses
        ],
        "position": {
            "entry_threshold": genome.position.entry_threshold,
            "exit_threshold": genome.position.exit_threshold,
            "max_pos": genome.position.max_pos,
            "time_stop_min": genome.position.time_stop_min,
        },
        "risk": {"stop_atr": genome.risk.stop_atr, "take_atr": genome.risk.take_atr},
    }


def build_bc_evaluation_input_from_sidecar(
    *,
    individual_index: int,
    genome: Genome,
    cp_result_with_sidecar: CrossPairResult,
    legacy_b_result: StageResult,
    bars_b: tuple[PriceBar, ...],
    bars_holdout: tuple[PriceBar, ...],  # Round 1 [Warning] 反映: stage_c_period の SSOT
    stage_config: StageGateConfig,
    bounded_recompute_mode: bool = False,  # Round 1 [Warning] 反映で mode 別 guard
) -> tuple[BCEvaluationInput | None, str | None]:
    """sidecar (= step 1.8 _PairSidecarInputs) と legacy_b_result から
    BCEvaluationInput を構築する.

    制約 (= 概念設計 § 5.2):
    - `uncontrolled full backtest` 禁止 (= 通常 run、 既存成果物再利用のみ)
    - `bounded recomputation` 専用検証 run 限定 (= bounded_recompute_mode=True)
    - `shadow_pairs` は cp_result._shadow_sidecar_inputs から参照共有 + lazy
      materialization

    Returns:
        (bc_input, skip_reason). 構築成功時 (bc_input, None)、 構築不能時
        (None, skip_reason)。 skip_reason は § 2.1 feasibility 表の
        skip_reason 列に対応。
    """
    # Stage B trades / equity_curve / bars 構築 (= legacy_b_result から)
    b_payload = legacy_b_result.metrics.get("payload")
    if not isinstance(b_payload, Mapping):
        return None, "b_result_payload_unavailable"
    b_trades_raw = b_payload.get("trades")
    b_equity_raw = b_payload.get("equity_curve")
    if b_trades_raw is None or b_equity_raw is None:
        return None, "b_result_trades_or_equity_curve_unavailable"

    # adapter 経由で TradeRecord / BarEquitySeries に変換 (= 凍結 helper 再利用)
    try:
        canonical_trades = tuple(trade_to_trade_record(t) for t in b_trades_raw)
        canonical_bars = equity_curve_to_bar_equity_series(b_equity_raw)
        canonical_universe = compute_business_day_universe_from_bars(list(bars_b))
    except Exception as exc:
        return None, f"adapter_conversion_failed:{type(exc).__name__}"

    # folds 構築 (= make_wf_folds 既存出力を T060 Fold tuple に変換)
    try:
        wf_folds = make_wf_folds(list(bars_b), n_folds=stage_config.stage_b_n_folds)
        folds = tuple(_wf_fold_to_t060_fold(wf) for wf in wf_folds)
    except Exception as exc:
        return None, f"folds_construction_failed:{type(exc).__name__}"

    # stage_c_lite_periods + stage_c_period derive (= bars_holdout から、
    # synthesis § 5.3 「3 windows × 60d」 と 1対1 対応、 acceptance C4)
    # Round 1 [Warning] 反映: bars_b ではなく bars_holdout を使う (= T064 SSOT 整合)
    try:
        stage_c_period, stage_c_lite_periods = _derive_stage_c_periods(
            holdout_days=stage_config.stage_c_holdout_days,
            bars_holdout=bars_holdout,
        )
    except Exception as exc:
        return None, f"stage_c_periods_derive_failed:{type(exc).__name__}"

    # anchor_bundle / shadow_pairs 構築 (= step 1.8 _shadow_sidecar_inputs から
    # 参照共有、 lazy materialization)
    sidecar_map = cp_result_with_sidecar._shadow_sidecar_inputs
    if not sidecar_map:
        return None, "cross_pair_sidecar_inputs_empty"

    target_pair = cp_result_with_sidecar.target_pair
    target_sidecar = sidecar_map.get(target_pair)
    if target_sidecar is None:
        return None, "anchor_pair_sidecar_unavailable"

    # config_hash / partition_label の SSOT (= step 2.2 で安定化、 2.1 では暫定)
    config_hash = _compute_config_hash(stage_config)
    partition_label = _derive_partition_label(stage_c_period)

    try:
        anchor_bundle = _sidecar_to_pair_bundle(
            sidecar=target_sidecar,
            pair=target_pair,
            genome_id=genome.name,
            config_hash=config_hash,
            partition_label=partition_label,
        )
    except Exception as exc:
        return None, f"anchor_bundle_construction_failed:{type(exc).__name__}"

    # Round 1 [Critical] 反映: lazy materialization
    # - 通常 run (bounded_recompute_mode=False): shadow_pairs は dict のみ構築、
    #   per-pair bundle は materialize しない (= 参照共有のみ、 評価時に lazy 展開する
    #   設計に変更可能だが、 step 2.1 では bounded_recompute_mode=False で
    #   shadow_pairs を空 dict 化し、 stage_bc_evaluator 側で「shadow_pairs 不在」 と
    #   して扱わせる。 cross-pair shadow 評価結果は 2.1 では観測しない。
    #   2.2 切替時に full 展開を許可する移行)
    # - 専用検証 run (bounded_recompute_mode=True): per-pair bundle を都度
    #   materialize、 sidecar→bundle 変換 cost を観測 (= bounded recomputation 経路)
    shadow_pairs: dict[str, PairBacktestBundle] = {}
    if bounded_recompute_mode:
        for pair_name, sidecar in sidecar_map.items():
            if pair_name == target_pair:
                continue
            try:
                shadow_pairs[pair_name] = _sidecar_to_pair_bundle(
                    sidecar=sidecar, pair=pair_name,
                    genome_id=genome.name, config_hash=config_hash,
                    partition_label=partition_label,
                )
            except Exception:
                # 個別 pair 構築失敗 → skip (= shadow_pairs から除外)、 有効観測継続
                continue
    # else: shadow_pairs={} で stage_bc_evaluator 側に委譲 (= cross-pair shadow 観測
    #       なしで進む経路、 通常 run のメモリ抑制)

    bc_input = BCEvaluationInput(
        individual_index=individual_index,
        trades=canonical_trades,
        bars=canonical_bars,
        business_day_universe=canonical_universe,
        folds=folds,
        stage_c_lite_periods=stage_c_lite_periods,
        stage_c_period=stage_c_period,
        anchor_bundle=anchor_bundle,
        shadow_pairs=shadow_pairs,
    )
    return bc_input, None


def _sidecar_to_pair_bundle(
    *, sidecar: _PairSidecarInputs, pair: str, genome_id: str,
    config_hash: str, partition_label: str,
) -> PairBacktestBundle:
    """step 1.8 _PairSidecarInputs から PairBacktestBundle を構築 (= 参照共有)."""
    canonical_trades = tuple(trade_to_trade_record(t) for t in sidecar.trades)
    canonical_bars = equity_curve_to_bar_equity_series(sidecar.equity_curve)
    canonical_universe = compute_business_day_universe_from_bars(list(sidecar.bars))
    return PairBacktestBundle(
        pair=pair,
        genome_id=genome_id,
        config_hash=config_hash,
        partition_label=partition_label,
        trades=canonical_trades,
        bars=canonical_bars,
        business_day_universe=canonical_universe,
    )


def evaluate_stage_bc_shadow_safe(
    *,
    shadow_context: StageBCShadowContext,
    cp_result_with_sidecar: CrossPairResult | None,
    cross_pair_payload: Mapping[str, object],
    stage_c_payload_legacy: Mapping[str, object],
    bars_holdout: list[PriceBar],
    stage_config: StageGateConfig,
    event_collector: "BCShadowEventCollector | None" = None,
) -> None:
    """shadow 配線 wrapper. shadow_enabled=True で 5 case (= ok/degraded/failed/
    skipped/context_missing) いずれも 1 event emit.

    Round 5 [Warning] 反映: shadow_context が caller で構築失敗時の context_missing は
    `evaluate_stage_c` 側で直接 emit (= § 2.2.4 配線、 本 wrapper には必ず非 None で渡される)。

    Round 1 [Critical] 反映: wrapper 全体を最外周 try/except で囲む (= D1/D2 違反
    防止、 例外時は failed event emit + WARN log)。 genome_hash 計算 / legacy_summary
    抽出 / その他全処理が main flow に絶対伝播しない契約。
    """
    if not stage_config.phase2_bc_evaluator_shadow_enabled:
        return  # 0 event (= 通常 run、 acceptance C2)

    # Round 1 [Critical] 反映: 最外周 try/except で D1/D2 完全防御
    try:
        _evaluate_stage_bc_shadow_inner(
            shadow_context=shadow_context,
            cp_result_with_sidecar=cp_result_with_sidecar,
            cross_pair_payload=cross_pair_payload,
            stage_c_payload_legacy=stage_c_payload_legacy,
            bars_holdout=bars_holdout,
            stage_config=stage_config,
            event_collector=event_collector,
        )
    except Exception as exc:
        # 想定外例外 → failed event emit (= 偽観測排除)、 WARN log のみ
        # 注: genome_hash 計算が失敗していても individual_index は context にある
        logger.warning(
            "stage_bc_evaluator.shadow_failure",
            run_id=shadow_context.run_id,
            generation_no=shadow_context.generation_no,
            individual_index=shadow_context.individual_index,
            error=str(exc), error_type=type(exc).__name__,
        )
        # 最低限の event emit (= identifier だけは記録、 collector に通知)
        try:
            failed_event = {
                "schema_version": SHADOW_EVENT_SCHEMA_VERSION,
                "run_id": shadow_context.run_id,
                "generation_no": shadow_context.generation_no,
                "genome_hash": "<failed>",
                "genome_serialization_version": GENOME_SERIALIZATION_VERSION,
                "individual_index": shadow_context.individual_index,
                "legacy_summary": _make_unknown_legacy_summary(),
                "bc_summary": _make_failed_bc_summary(),
                "descriptive_diff": _make_unknown_descriptive_diff(),
                "shadow_skipped": False,
                "shadow_skip_reason": f"wrapper_outer_exception:{type(exc).__name__}",
                "interpretation_note": "shadow_observation_only_phase2.1",
            }
            logger.info("stage_bc_evaluator.shadow", **failed_event)
            if event_collector is not None:
                event_collector.record_event(failed_event)
        except Exception:
            # 二重例外でも main flow に伝播させない
            pass


def _evaluate_stage_bc_shadow_inner(
    *,
    shadow_context: StageBCShadowContext,
    cp_result_with_sidecar: CrossPairResult | None,
    cross_pair_payload: Mapping[str, object],
    stage_c_payload_legacy: Mapping[str, object],
    bars_holdout: list[PriceBar],
    stage_config: StageGateConfig,
    event_collector: "BCShadowEventCollector | None" = None,
) -> None:
    """wrapper の inner 実装 (= try/except でガード対象)."""
    genome_hash = _compute_genome_hash(shadow_context.genome)
    legacy_summary = _extract_legacy_summary(
        legacy_b_result=shadow_context.legacy_b_result,
        cross_pair_payload=cross_pair_payload,
        stage_c_payload_legacy=stage_c_payload_legacy,
    )

    # ===== 1. cp_result / sidecar 妥当性チェック =====
    if cp_result_with_sidecar is None or not getattr(
        cp_result_with_sidecar, "_shadow_sidecar_inputs", None
    ):
        _emit_shadow_event(
            shadow_context=shadow_context, genome_hash=genome_hash,
            legacy_summary=legacy_summary,
            bc_summary=_make_skipped_bc_summary(),
            shadow_skipped=True,
            shadow_skip_reason="cp_result_or_sidecar_unavailable",
            event_collector=event_collector,
        )
        return

    # ===== 2. builder で BCEvaluationInput 構築 =====
    try:
        bc_input, skip_reason = build_bc_evaluation_input_from_sidecar(
            individual_index=shadow_context.individual_index,
            genome=shadow_context.genome,
            cp_result_with_sidecar=cp_result_with_sidecar,
            legacy_b_result=shadow_context.legacy_b_result,
            bars_b=shadow_context.bars_b,
            stage_config=stage_config,
        )
    except Exception as exc:
        _emit_shadow_event(
            shadow_context=shadow_context, genome_hash=genome_hash,
            legacy_summary=legacy_summary,
            bc_summary=_make_skipped_bc_summary(),
            shadow_skipped=True,
            shadow_skip_reason=f"builder_exception:{type(exc).__name__}",
            event_collector=event_collector,
        )
        return

    if bc_input is None:
        _emit_shadow_event(
            shadow_context=shadow_context, genome_hash=genome_hash,
            legacy_summary=legacy_summary,
            bc_summary=_make_skipped_bc_summary(),
            shadow_skipped=True,
            shadow_skip_reason=skip_reason or "builder_input_missing",
            event_collector=event_collector,
        )
        return

    # ===== 3. evaluate_bc_safe で degraded / failed handling =====
    try:
        outcome = evaluate_bc_safe(
            genome_id=shadow_context.genome.name,
            run_id=shadow_context.run_id,
            generation_no=shadow_context.generation_no,
            stage="bc_shadow",
            evaluate_fn=evaluate_bc_for_a_pass,
            a_pass_inputs={shadow_context.individual_index: bc_input},
            individual_index=shadow_context.individual_index,
        )
    except Exception as exc:
        logger.warning(
            "stage_bc_evaluator.shadow_failure",
            run_id=shadow_context.run_id,
            generation_no=shadow_context.generation_no,
            genome_hash=genome_hash,
            individual_index=shadow_context.individual_index,
            error=str(exc), error_type=type(exc).__name__,
        )
        _emit_shadow_event(
            shadow_context=shadow_context, genome_hash=genome_hash,
            legacy_summary=legacy_summary,
            bc_summary=_make_failed_bc_summary(),
            shadow_skipped=False, shadow_skip_reason=None,
            event_collector=event_collector,
        )
        return

    bc_result = (
        outcome.result.get(shadow_context.individual_index)
        if isinstance(outcome.result, dict) else None
    )
    if bc_result is None:
        _emit_shadow_event(
            shadow_context=shadow_context, genome_hash=genome_hash,
            legacy_summary=legacy_summary,
            bc_summary=_make_failed_bc_summary(),
            shadow_skipped=False, shadow_skip_reason="outcome_unwrap_failed",
            event_collector=event_collector,
        )
        return

    # ===== 4. ok / degraded で event emit =====
    status = "degraded" if outcome.failure_record is not None else "ok"
    _emit_shadow_event(
        shadow_context=shadow_context, genome_hash=genome_hash,
        legacy_summary=legacy_summary,
        bc_summary=_make_bc_summary_from_result(bc_result, status=status),
        shadow_skipped=False, shadow_skip_reason=None,
        event_collector=event_collector,
    )


def _emit_shadow_event(
    *, shadow_context: StageBCShadowContext, genome_hash: str,
    legacy_summary: dict, bc_summary: dict,
    shadow_skipped: bool, shadow_skip_reason: str | None,
    event_collector: "BCShadowEventCollector | None",
) -> None:
    """schema v1 準拠の `stage_bc_evaluator.shadow` event を emit + collector に通知.

    Round 1 [Critical] 反映: payload key を `descriptive_diff` に統一
    (= 概念設計 § 2.3 と整合、 旧 `diffs` は撤廃)。
    """
    descriptive_diff = _compute_descriptive_diff(
        legacy_summary=legacy_summary, bc_summary=bc_summary,
    )
    event_payload = {
        "schema_version": SHADOW_EVENT_SCHEMA_VERSION,
        "run_id": shadow_context.run_id,
        "generation_no": shadow_context.generation_no,
        "genome_hash": genome_hash,
        "genome_serialization_version": GENOME_SERIALIZATION_VERSION,
        "individual_index": shadow_context.individual_index,
        "legacy_summary": legacy_summary,
        "bc_summary": bc_summary,
        "descriptive_diff": descriptive_diff,  # Round 1 [Critical] 反映で key 統一
        "shadow_skipped": shadow_skipped,
        "shadow_skip_reason": shadow_skip_reason,
        "interpretation_note": "shadow_observation_only_phase2.1",
    }
    logger.info("stage_bc_evaluator.shadow", **event_payload)
    if event_collector is not None:
        event_collector.record_event(event_payload)
```

(残: helper 関数 `_extract_legacy_summary` / `_make_skipped_bc_summary` /
`_make_failed_bc_summary` / `_make_bc_summary_from_result` /
`_compute_descriptive_diff` / `_compute_config_hash` / `_derive_partition_label` /
`_derive_stage_c_periods` / `_wf_fold_to_t060_fold` を 詳細実装)

### 4.4 9 fields 対応表 (= 概念設計 § 2.1 Round 4 反映)

| field | source | copy_or_reference | semantic_validity | skip_reason |
|---|---|---|---|---|
| individual_index | shadow_context.individual_index | (新規) | OK | n/a |
| trades | legacy_b_result.metrics["payload"]["trades"] → adapter | reference | OK | b_result_trades_or_equity_curve_unavailable |
| bars | legacy_b_result.metrics["payload"]["equity_curve"] → adapter | reference | OK | b_result_trades_or_equity_curve_unavailable |
| business_day_universe | shadow_context.bars_b → compute_business_day_universe_from_bars | (新規 dict) | OK | bars_b_unavailable |
| folds | make_wf_folds(bars_b) → T060 Fold tuple | reference | OK | folds_construction_failed |
| stage_c_lite_periods | stage_config.stage_c_holdout_days → time-series 3 分割 | (新規 tuple) | acceptance C4 で固定 | stage_c_periods_derive_failed |
| stage_c_period | stage_config.stage_c_holdout_days → 1 Period | (新規) | OK | stage_c_periods_derive_failed |
| anchor_bundle | cp_result._shadow_sidecar_inputs[target] → PairBacktestBundle | reference | OK (= step 1.8 sidecar 確立) | anchor_pair_sidecar_unavailable |
| shadow_pairs | cp_result._shadow_sidecar_inputs[!target] → dict[str, PairBacktestBundle] | reference (deep copy 禁止) | OK | (個別 pair 構築失敗は dict から除外、 全 pair skip 時 cross_pair_sidecar_inputs_empty) |

### 4.5 ルックアヘッドバイアスチェック
- [N/A] primitive 変更ではない (= 既存成果物の adapter 変換のみ、 新規評価窓追加なし)

### 4.6 パフォーマンスチェック
- [N/A] primitive 変更ではない (= shadow_enabled=False で overhead 0)

### 4.7 テスト計画
(= 施策 7 にまとめる、 acceptance B1-B5 / C1-C7 / D1-D2 対応)

### 4.8 リスク
- adapter 例外で builder skip → skip_reason で観測継続、 偽観測排除
- shadow_pairs 構築コストが per-pair で大きい → bounded recomputation を専用検証 run のみで許可

---

## 5. 施策 2: `bc_evaluator_shadow_collector.py` 新規 module

### 5.1 変更箇所
- ファイル: `src/alpha_factory/bc_evaluator_shadow_collector.py` (= 新規)

### 5.2 module 構成 (= 概念設計 § 2.2.3 反映)

```python
# bc_evaluator_shadow_collector.py
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

SHADOW_RUN_SUMMARY_SCHEMA_VERSION = 1


@dataclass
class BCShadowEventCollector:
    """per-genome event を集約し run 終端で shadow_run_summary を emit.

    Round 4 [Critical 4] 反映で stage_gate.py 内では run-level 集計不能のため
    上位層 (= GenomeEvaluator / LaneManager / run_ga) で保持する.
    """
    run_id: str
    n_genomes_attempted: int = 0
    n_ok: int = 0
    n_skipped: int = 0
    n_failed: int = 0
    n_degraded: int = 0
    skip_reasons: Counter = field(default_factory=Counter)

    def record_event(self, event_payload: dict[str, Any]) -> None:
        """per-genome event 受け取り (= status / skip_reason 集計)."""
        self.n_genomes_attempted += 1
        bc_summary = event_payload.get("bc_summary", {})
        status = bc_summary.get("status", "skipped")
        if status == "ok":
            self.n_ok += 1
        elif status == "degraded":
            self.n_degraded += 1
        elif status == "failed":
            self.n_failed += 1
        else:
            self.n_skipped += 1
        skip_reason = event_payload.get("shadow_skip_reason")
        if skip_reason is not None:
            self.skip_reasons[skip_reason] += 1

    def emit_run_summary(
        self, *, sampled_max_worker_rss_bytes: int | None = None,
        process_tree_peak_rss_max_bytes: int | None = None,
        wall_clock_total_seconds: float = 0.0,
        wall_clock_overhead_vs_baseline: float | None = None,
    ) -> None:
        """run 終端で stage_bc_evaluator.shadow_run_summary を emit.

        Round 1 [Warning] 反映: attempted=0 のとき emit しない (= 観測なし、
        偽観測排除)。 N>0 のときのみ rate 計算 + emit。
        """
        if self.n_genomes_attempted == 0:
            # 観測なし → emit しない (= 偽観測排除)
            return
        n = self.n_genomes_attempted
        skip_rate = self.n_skipped / n
        failure_rate = self.n_failed / n
        degraded_rate = self.n_degraded / n
        skip_rate_by_reason = {
            reason: count / n for reason, count in self.skip_reasons.items()
        }
        logger.info(
            "stage_bc_evaluator.shadow_run_summary",
            schema_version=SHADOW_RUN_SUMMARY_SCHEMA_VERSION,
            run_id=self.run_id,
            shadow_enabled=True,
            n_genomes_attempted=self.n_genomes_attempted,
            n_genomes_observed_ok=self.n_ok,
            n_genomes_skipped=self.n_skipped,
            n_genomes_failed=self.n_failed,
            n_genomes_degraded=self.n_degraded,
            skip_rate=skip_rate,
            failure_rate=failure_rate,
            degraded_rate=degraded_rate,
            skip_rate_by_reason=dict(skip_rate_by_reason),
            process_tree_peak_rss_max_bytes=process_tree_peak_rss_max_bytes,
            sampled_max_worker_rss_bytes=sampled_max_worker_rss_bytes,
            wall_clock_total_seconds=wall_clock_total_seconds,
            wall_clock_overhead_vs_baseline=wall_clock_overhead_vs_baseline,
            interpretation_note="shadow_run_summary_for_step2.2_exit_criteria",
        )
```

### 5.3 親プロセス集約モデル (= Round 3 [Critical] 反映で正式仕様確定: pool summary supported)

**step 2.1 正式仕様 = WorkerEvaluationResult.shadow_event_payload 経由 parent 集約** (= Round 3 [Critical] 反映で smoke grep 集計を撤廃):

#### 経路設計

```
worker (= 子プロセス)
  ↓ evaluate_stage_bc_shadow_safe (return: dict | None)
  ↓ shadow_event_payload を WorkerEvaluationResult に格納
  ↓ logger.info で event を emit (= trace 用、 1 回のみ)
worker return → parent (= GenomeEvaluator / LaneManager)
  ↓ futures から WorkerEvaluationResult 受領
  ↓ shadow_event_payload を BCShadowEventCollector.record_event に渡す (= parent 集約、 re-log なし)
parent run 終端
  ↓ BCShadowEventCollector.emit_run_summary
  → stage_bc_evaluator.shadow_run_summary event 1 件 emit (= acceptance C6)
```

#### 二重 counting 回避 (= Round 3 [Warning] 反映)
- per-genome event は worker が 1 回 logger.info で emit (= trace、 個別 genome の挙動を log に残す)
- parent は WorkerEvaluationResult.shadow_event_payload を **count するのみ** で re-log しない (= shadow_run_summary 1 件で集計、 個別 genome の re-log は不要)

#### archive 漏洩防止 (= Round 3 [Critical] 反映)
- `WorkerEvaluationResult` (新規 dataclass) は **archive 対象外 envelope**: `c_result: GenomeStageResult` (= archive 対象、 shadow_event_payload を **絶対含まない**) + `shadow_event_payload: dict | None` (= worker→parent 専用、 archive に流さない)
- GenomeStageResult は **完全不変** (= acceptance E1/E2 完全保証、 既存 archive 互換維持)
- parent は WorkerEvaluationResult から `c_result` を取り出して既存 archive 経路に流す (= shadow_event_payload は別経路で collector へ)

#### in-process 経路 (= max_workers=1)
- 同一プロセスなので worker = parent、 上記経路を直接実行可能
- pool 経路と同型 (= WorkerEvaluationResult を return + parent 集約) で統一

### 5.3 ルックアヘッドバイアスチェック / パフォーマンスチェック
- [N/A] primitive 変更ではない

---

## 6. 施策 3: `StageGateConfig` field 追加

### 6.1 変更箇所
- ファイル: `src/alpha_factory/stage_gate.py:371` 付近 (= StageGateConfig dataclass)

### 6.2 変更後コード

```python
@dataclass(frozen=True)
class StageGateConfig:
    ...
    phase2_canonical_metrics_mode: Literal["log_only", "disabled"] = "log_only"
    # B step 2.1 で追加 (= shadow_enabled、 default off で通常 run には影響しない)
    phase2_bc_evaluator_shadow_enabled: bool = False
```

---

## 7. 施策 4: `stage_gate.evaluate_stage_c` shadow 配線追加

### 7.1 変更箇所
- ファイル: `src/alpha_factory/stage_gate.py:1342` 以降 (= evaluate_stage_c signature) + 1605 付近 (= step 1.8 try-finally 末尾、 sanitize 直前)

### 7.2 変更後コード (= 概念設計 § 2.2.4 反映)

```python
def evaluate_stage_c(
    genome: Genome,
    bars_holdout: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    primitive_evaluator: PrimitiveEvaluator,
    stage_config: StageGateConfig,
    *,
    cross_pair_evaluator: CrossPairEvaluator | None = None,
    cross_pair_inputs: Mapping[str, object] | None = None,
    bc_shadow_context: "StageBCShadowContext | None" = None,
    bc_shadow_collector: "BCShadowEventCollector | None" = None,
) -> StageResult:
    ...
    try:
        # ... step 1.8 cross_pair dual-path 配線 (= 既存、 完全不変) ...

        # === step 2.1 shadow 配線 (= sanitize 直前、 sidecar 利用可能なタイミング) ===
        # Round 1 [Critical 4] 反映: shadow_enabled=True かつ context is None で
        # context_missing event を必ず emit (= acceptance C2、 偽観測排除)
        # Round 1 [Warning 4] 反映: evaluate_stage_c 側でも shadow 呼出を二重隔離
        if stage_config.phase2_bc_evaluator_shadow_enabled:
            try:
                if bc_shadow_context is None:
                    # context_missing event を直接 emit
                    _emit_context_missing_shadow_event(
                        run_id="<unknown>",  # context が無いので caller info も無い
                        event_collector=bc_shadow_collector,
                    )
                else:
                    from src.alpha_factory.bc_evaluator_shadow import (
                        evaluate_stage_bc_shadow_safe,
                    )
                    evaluate_stage_bc_shadow_safe(
                        shadow_context=bc_shadow_context,
                        cp_result_with_sidecar=cp_result_local,
                        cross_pair_payload=cross_pair_payload,
                        stage_c_payload_legacy=metrics_envelope_payload,
                        bars_holdout=bars_holdout,
                        stage_config=stage_config,
                        event_collector=bc_shadow_collector,
                    )
            except Exception as exc:
                # 二重隔離: wrapper 内 try/except があるが、 evaluate_stage_c 側でも
                # ガード (= 多層防御、 D1/D2 強化)
                logger.warning(
                    "stage_bc_evaluator.shadow_failure",
                    location="evaluate_stage_c_outer",
                    error=str(exc), error_type=type(exc).__name__,
                )
    finally:
        # === step 1.8 sanitize 経路 (= 完全不変、 acceptance E1/E2) ===
        cp_result_for_sanitize = cross_pair_payload.get("result")
        if isinstance(cp_result_for_sanitize, CrossPairResult) and getattr(
            cp_result_for_sanitize, "_shadow_sidecar_inputs", None
        ):
            cross_pair_payload["result"] = replace(
                cp_result_for_sanitize, _shadow_sidecar_inputs={}
            )

    passed = len(reasons) == 0
    ...
```

### 7.3 設計判断
- shadow 配線は import を関数内 (= lazy import) にして循環依存リスクを回避
- shadow_enabled=False では shadow 配線にも入らない (= overhead 0)
- step 1.8 sanitize SSOT は finally で完全保持

---

## 8. 施策 5-6: `parallel_eval` / `swim_lane` 改修

### 8.1 変更箇所
- `src/alpha_factory/parallel_eval.py:_evaluate_genome_steps` (= L270-380 付近)
- `src/alpha_factory/parallel_eval.py:GenomeEvaluator` (= L538 付近)
- `src/alpha_factory/swim_lane.py:LaneManager` 同型修正

### 8.2 変更後コード (= 概念設計 § 2.2.5 + Round 1 [Critical 5] 反映で親プロセス集約)

```python
# parallel_eval._evaluate_genome_steps 内 (= worker / in-process 共通)
# Round 1 [Warning] 反映: bars_b は ctx.bars_b の参照共有、 個体ごと tuple 再生成しない
# (ctx.bars_b 自体を tuple 化前提)

if stage_gate_cfg.phase2_bc_evaluator_shadow_enabled:
    bc_shadow_context = build_shadow_context(  # 共通 helper (bc_evaluator_shadow.py)
        run_id=ctx.run_id,
        generation_no=ctx.generation_no,
        individual_index=ctx.individual_index,
        genome=genome,
        legacy_b_result=b_result,
        bars_b=ctx.bars_b,  # 既に tuple、 参照共有
        bounded_recompute_mode=ctx.bounded_recompute_mode,
    )
else:
    bc_shadow_context = None

# Round 1 [Critical 5] 反映: collector は worker pool 経路では None
# (= 親プロセスのみ集約)、 in-process (= max_workers=1) なら collector 直接渡し可能
c_result = evaluate_stage_c(
    genome, list(ctx.bars_holdout), ctx.meta, ctx.bt_cfg, ev_c, stage_gate_cfg,
    cross_pair_evaluator=cp_evaluator,
    cross_pair_inputs=cp_inputs_dict,
    bc_shadow_context=bc_shadow_context,
    bc_shadow_collector=ctx.bc_shadow_collector,  # in-process なら non-None、 pool では None
)
```

### 8.3 共通 helper `build_shadow_context` (= Round 1 [Warning] 反映で集約)

`bc_evaluator_shadow.py` 内に追加 (= parallel_eval / swim_lane 双方から呼出):

```python
def build_shadow_context(
    *,
    run_id: str, generation_no: int, individual_index: int,
    genome: Genome,
    legacy_b_result: StageResult,
    bars_b: tuple[PriceBar, ...],
    bounded_recompute_mode: bool = False,
) -> StageBCShadowContext:
    """parallel_eval / swim_lane 共通の context builder. 集約契約と隔離契約を統一."""
    return StageBCShadowContext(
        run_id=run_id, generation_no=generation_no,
        individual_index=individual_index,
        genome=genome,
        legacy_b_result=legacy_b_result,
        bars_b=bars_b,  # tuple 化前提、 deep copy しない
        bounded_recompute_mode=bounded_recompute_mode,
    )
```

### 8.4 GenomeEvaluator 改修 (= 親プロセス集約)

```python
class GenomeEvaluator:
    def __init__(
        self, ..., *,
        run_id: str = "",
        bc_shadow_collector: BCShadowEventCollector | None = None,
    ):
        ...
        self._bc_shadow_collector = bc_shadow_collector

    def __exit__(self, *args):
        if self._bc_shadow_collector is not None and self._bc_shadow_collector.n_genomes_attempted > 0:
            # run 終端で shadow_run_summary emit (= attempted=0 なら collector 内で skip)
            self._bc_shadow_collector.emit_run_summary(
                wall_clock_total_seconds=time.time() - self._run_start_ts,
            )
```

### 8.5 swim_lane.LaneManager 同型修正

(同様の `build_shadow_context` 経由 context 構築 + LaneManager に collector 保持、 親プロセスでのみ summary emit)

### 8.6 multiprocessing pool 経路の集計 (= Round 1 [Critical 6] 反映)

step 2.1 では **simple model** を採用:
- in-process 経路 (= max_workers=1): collector を直接 worker に渡し集計可能
- pool 経路 (= max_workers>1): collector は parent process でのみ保持、 worker は event を logger.info でのみ emit (= structlog stdout 経路)、 collector は **smoke スクリプト側で log を grep + 集計** (= step 2.1b smoke スクリプト § 12 拡張)
- 親プロセス aggregate を multiprocessing Queue で実装するのは step 2.2 以降 (= 本 step では smoke 集計で十分、 観測 data n>=30 達成可能)

---

## 9. 施策 7: テスト追加

### 9.1 新規テストケース (= 概念設計 acceptance)

| # | テスト名 | 対応 acceptance | 配置 |
|---|---|---|---|
| 1 | `test_stage_bc_shadow_context_dataclass_fields_complete` | C7 | test_bc_evaluator_shadow.py |
| 2 | `test_genome_hash_is_sha256_of_canonical_serialization` | C3 | 同 |
| 3 | `test_genome_hash_stable_across_invocations_for_same_genome` | C3 | 同 |
| 4 | `test_build_bc_evaluation_input_from_sidecar_succeeds_with_full_fixture` | C7 / 2.1a feasibility | 同 |
| 5 | `test_build_bc_evaluation_input_skips_when_b_result_payload_unavailable` | feasibility 表 skip_reason | 同 |
| 6 | `test_build_bc_evaluation_input_skips_when_cross_pair_sidecar_inputs_empty` | feasibility 表 | 同 |
| 7 | `test_build_bc_evaluation_input_skips_when_anchor_pair_sidecar_unavailable` | feasibility 表 | 同 |
| 8 | `test_build_bc_evaluation_input_partial_shadow_pairs_skip_individual_failure` | feasibility 表 | 同 |
| 9 | `test_evaluate_stage_bc_shadow_safe_emits_ok_event_in_normal_path` | C1, C2, C5 | 同 |
| 10 | `test_evaluate_stage_bc_shadow_safe_emits_skipped_event_when_sidecar_unavailable` | C2, C5 | 同 |
| 11 | `test_evaluate_stage_bc_shadow_safe_emits_skipped_event_when_builder_skips` | C2, C5 | 同 |
| 12 | `test_evaluate_stage_bc_shadow_safe_emits_failed_event_when_evaluate_bc_safe_raises` | C2, C5 | 同 |
| 13 | `test_evaluate_stage_bc_shadow_safe_emits_degraded_event_when_failure_record_present` | C2, C5 | 同 |
| 14 | `test_evaluate_stage_bc_shadow_safe_emits_zero_event_when_shadow_enabled_false` | C2 | 同 |
| 15 | `test_evaluate_stage_bc_shadow_safe_event_schema_version_one_required_fields` | C1 | 同 |
| 16 | `test_evaluate_stage_bc_shadow_safe_descriptive_diff_no_equivalence_claim` | C1, descriptive_diff | 同 |
| 17 | `test_bc_shadow_event_collector_records_per_status` | C6 | test_bc_evaluator_shadow_collector.py |
| 18 | `test_bc_shadow_event_collector_emits_run_summary_with_three_rates` | C6 | 同 |
| 19 | `test_bc_shadow_event_collector_skip_rate_by_reason_dict` | C6 | 同 |
| 20 | `test_evaluate_stage_c_with_shadow_disabled_preserves_legacy_behavior` (= regression) | A1-A4, B2 | test_parallel_eval_bc_shadow.py |
| 21 | `test_evaluate_stage_c_with_shadow_enabled_runs_shadow_before_sanitize` (= sanitize 順序契約) | B5 | 同 |
| 22 | `test_evaluate_stage_c_with_shadow_enabled_sanitizes_sidecar_after_shadow` (= sanitize 後 sidecar 空) | E1, E2 | 同 |
| 23 | `test_evaluate_stage_c_shadow_exception_does_not_propagate_to_main_flow` | B3, D1, D2 | 同 |
| 24 | `test_evaluate_stage_c_with_shadow_disabled_emits_zero_collector_events` | C2 | 同 |
| 25 | `test_evaluate_stage_c_shadow_dormant_bc_result_not_in_genome_stage_result` | E1, E2 | 同 |
| 26 | `test_evaluate_stage_c_with_shadow_enabled_and_context_missing_emits_skipped_event` (= Round 1 [Critical 4] 反映) | C2 (context_missing) | test_parallel_eval_bc_shadow.py |
| 27 | `test_evaluate_stage_bc_shadow_safe_outer_try_protects_main_flow_when_genome_hash_raises` (= Round 1 [Critical 1] wrapper 冒頭例外 test) | D1, D2 | test_bc_evaluator_shadow.py |
| 28 | `test_evaluate_stage_bc_shadow_safe_outer_try_protects_main_flow_when_legacy_summary_extraction_raises` | D1, D2 | 同 |
| 29 | `test_evaluate_stage_bc_shadow_safe_event_payload_uses_descriptive_diff_key_not_diffs` (= Round 1 [Critical 3] schema key 統一) | C1 schema | 同 |
| 30 | `test_build_bc_evaluation_input_with_bounded_recompute_mode_false_skips_shadow_pairs_materialization` (= Round 1 [Critical 2] lazy materialization) | feasibility / メモリ | 同 |
| 31 | `test_build_bc_evaluation_input_with_bounded_recompute_mode_true_materializes_shadow_pairs` | feasibility | 同 |
| 32 | `test_bc_shadow_event_collector_emit_run_summary_skipped_when_attempted_zero` (= Round 1 [Warning 2] attempted=0 で emit しない) | C6 | test_bc_evaluator_shadow_collector.py |

### 9.2 既存 2208 PASS 後方互換確認
- shadow_enabled=False (= default) で既存 alpha_factory 全 2208 PASS 完全不変

### 9.3 実装規模見込み
- 新規 test ~32 ケース (= Round 1 → Round 2 で 25 → 32 に増、 context_missing / wrapper 冒頭例外 / schema key / bounded mode / collector attempted=0 を追加)
- 新規 module: ~500 行 (bc_evaluator_shadow.py、 wrapper / inner / builder / helpers) + ~180 行 (collector)
- 既存 ファイルへの追加: ~200 行 (parallel_eval / swim_lane / stage_gate / GenomeEvaluator / LaneManager)

---

## 10. 実装モード

| 項目 | 内容 |
|---|---|
| 推奨モード | **incremental** |
| 判断根拠 | step 1.5-1.8 で確立した shadow / dual-path 同型 pattern。 step 2.1 は shadow LOG_ONLY なので regression 0 で進められる。 段階分割 (= 2.1a → 2.1b) で複雑度抑制 |
| 競合リスク | 低 (= shadow 配線は既存判定経路に絶対干渉しない) |
| 想定実装時間 | 中 (= 25 test ケース、 新規 2 module、 caller 改修、 step 1.8 比 1.5x 規模) |

---

## 11. 波及変更

### 11.1 必要な変更
- `src/alpha_factory/bc_evaluator_shadow.py` (= 新規)
- `src/alpha_factory/bc_evaluator_shadow_collector.py` (= 新規)
- `src/alpha_factory/stage_gate.py` (= StageGateConfig field 追加 + evaluate_stage_c 新引数 + try-finally 末尾 shadow 配線)
- `src/alpha_factory/parallel_eval.py` (= context 構築 + GenomeEvaluator collector 保持)
- `src/alpha_factory/swim_lane.py` (= 同型修正 + LaneManager collector 保持)
- `tests/alpha_factory/test_bc_evaluator_shadow.py` (= 新規)
- `tests/alpha_factory/test_bc_evaluator_shadow_collector.py` (= 新規)
- `tests/alpha_factory/test_parallel_eval_bc_shadow.py` (= 新規)
- `docs/alpha_factory/stage-gates.md` (= step 2.1 SSOT 追記、 必須)

### 11.2 不要 / 任意 変更
- `AGENTS.md`: 変更なし (= public API 変化なし)
- `.claude/skills/zenigame-fx-*/SKILL.md`: 変更なし
- `config/alpha_factory/default.yaml`: 変更なし (= shadow_enabled は default off で yaml 不変)
- `pyproject.toml`: 変更なし

---

## 12. メモリ実測 (= acceptance B4 専用検証 run)

### 12.1 worker 数別計測 (= Round 1 [Critical] 反映)

shadow_enabled=True で 1 / 2 / 4 / 6 workers の専用検証 run を実行:
- 各 worker 数で `sampled_max_worker_rss < 3 GB` を検証
- step 1.7 baseline 比 ±20% 以内 (= acceptance B4)
- 専用検証 run 用 smoke スクリプト (= 後続別計画、 step 1.8 の `scripts/smoke/measure_step1.8_memory.sh` 同型を step 2.1b 専用に拡張)

### 12.2 失敗時のフォールバック
- B4 不達成 → step 2.1b を main merge せず、 2.1 継続条件 (= 概念設計 § 1.5) に従って観測継続 + 設計再考

---

## 13. 残課題・運用観測 follow-up

1. **stage_c_lite_periods derive rule の T064 一致**: acceptance C4 で 1対1 対応 test 固定、 holdout < 180 / 端数 / 営業日 / 暦日 / bar 欠損時の挙動を fixture で網羅
2. **bounded_recompute_mode の発火条件 / 上限**: 詳細設計 round で acceptance に落とす (= 専用検証 run 限定、 上限回数明示)
3. **run-level smoke スクリプト**: step 1.8 の `measure_step1.8_memory.sh` を step 2.1b 用に拡張、 shadow_run_summary を集計対象に
4. **2.2 exit criteria 達成判断**: shadow 観測 data が n>=30 + invalid_observation_rate <= 30% + descriptive_diff 分析が rigorous に揃うかは別計画 (= 専用検証 run の data から判断)

---

## 14. 参考資料

- 概念設計 (Round 5 APPROVED): `devnotes/20260504-1026-B-phase2-step2-stage-bc-evaluator-main-flow-integration/conceptual-design.md`
- Codex 概念設計 review Round 1-5: `devnotes/20260504-1026-B-phase2-step2-stage-bc-evaluator-main-flow-integration/conceptual-review-round-{1,2,3,4,5}.md`
- step 1.8 詳細設計 (Round 5 APPROVED): `devnotes/20260504-0010-B-phase2-step1.8-stage-c-cross-pair-dual-path/detailed-design.md`
- step 1.8 完了 handoff: `devnotes/20260504-1018-B-step1.8-complete-handoff/handoff.md`
- canonical_adapter.py (凍結): `src/alpha_factory/canonical_adapter.py`
- stage_bc_evaluator.py (新 API): `src/alpha_factory/stage_bc_evaluator.py:1-1419`
- stage_gate.py (拡張対象): `src/alpha_factory/stage_gate.py`
- parallel_eval.py / swim_lane.py: 拡張対象
- failure_handling.evaluate_bc_safe: `src/alpha_factory/failure_handling.py:525-622` (= isolation boundary 再利用)
