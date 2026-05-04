**前提検証 (C4)**
- `verified`: step 2.1 は LOG_ONLY、`shadow_enabled=False` default、使命・禁止事項は設計上明記されています。
- `verified`: collider bias 回避のために `skip/failure/degraded` を分離し、分母を `n_genomes_attempted` に統一する方針は妥当です。
- `unverified`: `context_missing` 観測経路、run-level 集計の並列安全性、メモリ上限(3GB/worker)を実装で満たす保証は、現設計スニペットだけでは成立していません。

**施策別判定**

1. `bc_evaluator_shadow.py`  
判定: `REQUEST_CHANGES`  
- [Critical] `evaluate_stage_bc_shadow_safe` 冒頭の `genome_hash` 計算・`legacy_summary` 抽出が保護されておらず、例外が main flow に伝播し得ます（D1/D2違反リスク）。  
修正案: wrapper 全体を最外周 `try/except` で囲み、失敗時は `stage_bc_evaluator.shadow_failure` を WARN emit して `failed/skipped` を記録し `return`。  
- [Critical] 設計表では「reference/lazy」を掲げつつ、実装案は `_sidecar_to_pair_bundle` で全 pair を都度 materialize しており、6 worker 条件でメモリ・CPU悪化の反証が成立します。  
修正案: `shadow_pairs` は遅延化（必要時変換）または上限制御（専用検証runのみ展開）を明示し、通常 run は参照共有を維持。  
- [Critical] event schema 要件が `descriptive_diff(s)` 前提なのに payload key が `diffs`。契約不整合です。  
修正案: key を仕様名に統一（互換性維持が必要なら両方出力して移行期間を定義）。  
- [Warning] `bounded_recompute_mode` が文脈にあるのに分岐未使用で、制約がコード化されていません。  
修正案: mode 別ガードを builder に実装し、`skip_reason` を固定文字列でテスト化。  
- [Warning] `stage_c_period` 導出に `bars_b` を使う案は T064 定義との一致が不明で、期間意味論ズレの余地があります。  
修正案: T064 のSSOT入力系列に合わせる（必要なら `bars_holdout` 由来）＋境界テスト追加。

2. `bc_evaluator_shadow_collector.py`  
判定: `REQUEST_CHANGES`  
- [Critical] run-level 集計がプロセス間共有されない場合、`shadow_run_summary` が worker 単位で分断・重複し、C6 の run-level 指標が歪みます。  
修正案: 親プロセス集約（Queue/IPC/最終リデューサ）に一本化し、summary emit を単一箇所に限定。  
- [Warning] `n=max(1, attempted)` は `attempted=0` を見えにくくし、偽観測を招きます。  
修正案: `attempted==0` は emit しないか、rates を `None` + `no_observation=True` を明示。

3. `StageGateConfig` field追加  
判定: `APPROVE`  
- [Suggestion] config round-trip テスト（未指定時 False、明示True反映）を追加すると後退防止になります。

4. `evaluate_stage_c` への shadow 配線  
判定: `REQUEST_CHANGES`  
- [Critical] `bc_shadow_context is not None` 条件付き呼出のため、要件C2の `context_missing` event が発火しません。  
修正案: `shadow_enabled=True` かつ context `None` 時に `status=skipped, skip_reason="context_missing"` を必ず emit。  
- [Warning] wrapper 側の想定外例外に対する二重隔離が弱いです。  
修正案: `evaluate_stage_c` 側でも shadow 呼出を `try/except` で包み、main flow 不変を強制。

5. `parallel_eval` 改修  
判定: `REQUEST_CHANGES`  
- [Critical] collector の所有境界が曖昧で、並列時に「run-level 1件集計」の保証が不足。  
修正案: collector を評価実行系の親オーケストレータのみ保持し、worker は event を送るだけに分離。  
- [Warning] `bars_b=tuple(ctx.bars_b)` を個体ごと生成するとメモリ圧迫要因です。  
修正案: immutable 参照を共有し、再構築を避ける。

6. `swim_lane` 同型修正  
判定: `REQUEST_CHANGES`  
- [Warning] parallel_eval と同等の集計・隔離契約が崩れると経路間で観測定義がズレます。  
修正案: swim_lane 側も同一の親集約契約と emit 条件を共通ヘルパで統一。

7. テスト25件追加計画  
判定: `REQUEST_CHANGES`  
- [Critical] `context_missing` 経路のテストが一覧に見当たりません（C2未固定）。  
修正案: `bc_shadow_context=None` で skipped/context_missing を検証するケースを追加。  
- [Critical] 「wrapper 冒頭例外でも main flow 不変」のテストが不足しています。  
修正案: hash生成失敗/legacy抽出失敗をモックし、`StageResult` 不変 + WARN のみを検証。  
- [Warning] B4 は「専用検証run」依存で、継続的回帰検知が弱いです。  
修正案: 1/2/4/6 worker の計測スモークを半自動化し、閾値逸脱時に失敗扱いへ。

**Fact / Interpretation 分離 (C6)**
- Fact: 現スニペットでは `context_missing` を emit する分岐が存在しません。  
Interpretation: C2 達成不可のため、step 2.1 の観測完全性に欠陥があります。
- Fact: 実装案は shadow pair を都度変換します。  
Interpretation: 3GB/worker 制約に対して反証リスクが高く、2.1b の merge 条件を満たせない可能性があります。

**全体判定**
- `CHANGES_REQUESTED`

主要ブロッカーは 1) context_missing 未観測、2) 例外隔離の穴、3) run-level 集計の並列安全性不足、4) eager materialization によるメモリ反証、5) schema key 不整合 です。これらを先に潰せば、段階分割方針（2.1a→2.1b）自体は妥当です。