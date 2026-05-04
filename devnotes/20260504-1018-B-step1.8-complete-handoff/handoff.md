# B step 1.8 Complete (Stage C cross_pair (ii-lite) dual-path 拡張) + 次 step 引き継ぎ Handoff

**作成日時**: 2026-05-04 10:18 JST
**Session**: B Phase 2 切替コミット step 1.8 完了 (= 概念設計 3 round + 詳細設計 5 round + 実装 5 round Codex APPROVED + main マージ)
**前 handoff**: `devnotes/20260504-0003-B-step1.7-complete-handoff/handoff.md`
**次セッション**: **B Phase 2 切替コミット step 2 (= stage_bc_evaluator main flow 統合)**

---

## 0. 現在地

```
T081 step 1 (ABDivergenceMetric 実値配線)        ████████████████████ 100% ✨ (Closed、 main commit 27acfb3)
T081 step 2-6                                     ░░░░░░░░░░░░░░░░░░░░  Deferred
T082 (TradeRecord.spread_cost 伝搬経路配線)      ⚠ Obsoleted (前提誤認)
B step 1 (canonical_metrics → main flow 統合)    ████████████████████ 100% ✨🎉 (main commit 9bc6a02)
B step 1.5 (Stage B IS / Stage C base dual-path) ████████████████████ 100% ✨🎉 (main commit 6276d58)
B step 1.6 (Stage B per-fold dual-path)          ████████████████████ 100% ✨🎉 (main commit 1dadc8b)
B step 1.7 (Stage C stress dual-path)            ████████████████████ 100% ✨🎉 (main commit e3a428b)
B step 1.8 (Stage C cross_pair dual-path)        ████████████████████ 100% ✨🎉 (本セッション、 main commit c3ee70a)
B step 2 (stage_bc_evaluator main flow 統合)     ░░░░░░░░░░░░░░░░░░░░    0% ← 次推奨
B step 3-7                                        ░░░░░░░░░░░░░░░░░░░░    0%
T081 step 2-6 再開 (B 完了後)                     ░░░░░░░░░░░░░░░░░░░░    0%
GA 動作確認 (smoke 5 Run + 実 GA)                ░░░░░░░░░░░░░░░░░░░░    0%
```

mission 必須軸 (= ii-lite) の per-pair canonical observability が完成 → step 2 着手前提条件 (= mission 軸 observability 完成) 達成。

---

## 1. 本セッション完了内容

### 1.1 B step 1.8 設計 (Codex 8 round)

設計ファイル: `devnotes/20260504-0010-B-phase2-step1.8-stage-c-cross-pair-dual-path/`

#### 概念設計 (Codex Round 1-3、 Round 3 APPROVED)

| Round | 判定 | 主要取込 |
|---|---|---|
| 1 | CHANGES_REQUESTED | [Critical] 案 A は cross_pair.py に canonical 計算責務まで持ち込みすぎ → A' 推奨。 [Critical] CrossPairConfig への dual-path field 追加は伝搬面が広すぎる。 [Warning] sidecar 名前空間隔離が弱い / メモリ実測前提 / C1/C4 未充足 / pair_label 採用妥当 |
| 2 | CHANGES_REQUESTED | [Critical] sidecar が `del sidecar_map` だけでは破棄されない (= cp_result が cross_pair_payload / GenomeStageResult.cross_pair に残るため payload 内に永続化)。 [Critical] MappingProxyType({}) default は multiprocessing pickle 失敗。 [Critical] _PairSidecarInputs の循環依存リスク |
| 3 | **APPROVED** | sanitize 経路 (= `replace(cp_result, _shadow_sidecar_inputs={})`) 追加、 `field(default_factory=dict, repr=False, compare=False)` で multiprocessing pickle 互換、 _PairSidecarInputs を stage_gate.py 側に定義で循環依存回避、 役割識別 (target/anchor1/anchor2) は dual-path log に出さず Stage C payload と join する設計 |

#### 詳細設計 (Codex Round 1-5、 Round 5 APPROVED)

| Round | 判定 | 主要取込 |
|---|---|---|
| 1 | CHANGES_REQUESTED | [Critical] pair_label fail-fast が None のみ。 [Critical] sanitize は条件付き、 finally 保証ではない。 [Warning] metric_unavailable で sidecar 捨てる設計の見直し / メモリ N/A 不正確 / disabled mode で per-pair iterate / pair キー妥当性検証 / smoke 自動計測 / E2E test |
| 2 | CHANGES_REQUESTED | [Warning] BrokerTrade import 波及 / E7 test 名 / pair_label 前後空白 / non-C_cross_pair 拒否 / metric_unavailable 契約整理 / no-trade None 検証 / smoke uv 統一 / 指標名訂正 |
| 3 | CHANGES_REQUESTED | [Warning] § 8.4 コードコメント文言整合 / § 2 主要決定の古い契約文言 / smoke B2 元制約 (1 worker 3GB) 直接検証なし / time -l RSS 解釈の不確実性 |
| 4 | CHANGES_REQUESTED | [Warning] psutil 依存明記 / smoke 関連 ファイル § 11.1 / docs § 11.1/§ 11.2 矛盾 / sampling 失敗時 INCONCLUSIVE 徹底 |
| 5 | **APPROVED** | psutil>=5.9 既存依存 (pyproject.toml:22) を再利用、 § 11.1 に smoke 3 ファイル + docs 必須移動、 sampling 失敗時 B2 INCONCLUSIVE で merge 不可 (= 暫定運用しない、 fallback は手動 ps 経路で SSOT 再 verify) |

設計の主要決定:
- **採用案: A'** (= cross_pair.py は per-pair sidecar 保持・返却のみ、 canonical 計算と log emit は stage_gate.py 側、 責務境界明確化)
- **`_PairSidecarInputs`**: stage_gate.py 側 CrossPairResult 近傍に定義 (= 循環依存回避)
- **`CrossPairResult._shadow_sidecar_inputs`**: `dict[str, _PairSidecarInputs] = field(default_factory=dict, repr=False, compare=False)` (= multiprocessing pickle 互換 + repr/equality 除外)
- **sanitize 経路**: dual-path 経路を `try ... finally` で囲み、 finally 句で `cross_pair_payload["result"] = replace(cp_result, _shadow_sidecar_inputs={})` を **常時実行** (= 例外時 / disabled / sidecar 空 / cp_result is None / pair_failure 全分岐)
- **dual-path skip SSOT**: `sidecar_inputs is None` (= exception pair のみ skip、 metric_unavailable は canonical_skipped emit 対象)
- **pair_label**: 実 pair 名 (= "EUR_USD" 等)、 識別子契約 fail-fast (= None / 空文字 / 空白 / 前後空白 / non-C_cross_pair で ValueError)
- **smoke merge gate**: psutil sampling SSOT で `sampled_max_worker_rss < 3 GB` (= 主条件)、 wall_time step 1.7 比 ±20% (= B3、 baseline_dir 引数化)、 sampling 失敗時 INCONCLUSIVE で merge 不可

### 1.2 B step 1.8 実装 + Codex 実装 review (Round 1-5、 Round 5 APPROVED)

| Round | 判定 | 主要取込 |
|---|---|---|
| 1 | CHANGES_REQUESTED | [Critical] B_IS 互換 test / #26 系分離 test 不足、 smoke 3 ファイル + docs 不在、 fold_index non-B_fold reject 未対応 |
| 2 | CHANGES_REQUESTED | [Critical] B3 が常に INCONCLUSIVE で B2 PASS なら exit 0、 sampling 欠損 (sampled_tree is None) で B2 PASS、 cross-run contamination guard 弱、 docs 実装ズレ |
| 3 | CHANGES_REQUESTED | [Critical] sampler 欠損 (run-N.log 5 本 vs sample-N.jsonl 1 本) 検出不能、 B2 health guard 全 run sampling 成功要求なし |
| 4 | CHANGES_REQUESTED | [Critical] LOG_DIR 既存 stale file 未削除、 sample が現在 run のものか証明なし |
| 5 | **APPROVED** | stale file rm -f 初期化、 sampler header 検証 (= run_index pair)、 JSONDecodeError / header_missing / no_data_samples / run_index_mismatch を全件 failed 扱い、 grace 1.0 秒で false negative 防止、 docs 整合 |

主要変更 (= worktree commit `490b45e`、 main merge commit `c3ee70a`):

#### S1: stage_gate.py の `_PairSidecarInputs` 新規定義 + `CrossPairResult._shadow_sidecar_inputs` field
- `_PairSidecarInputs` (frozen dataclass): bars / trades / equity_curve / bt 保持
- `CrossPairResult._shadow_sidecar_inputs: dict[str, _PairSidecarInputs] = field(default_factory=dict, repr=False, compare=False)`
- multiprocessing pickle 互換 + dataclass equality / repr 除外

#### S2: `_log_canonical_dual_path` に `pair_label: str | None = None` 追加
- 識別子契約 fail-fast: None / 空文字 / 空白 / 前後空白 / non-C_cross_pair で ValueError
- `fold_index` も non-B_fold で対称化 (= 両 kwargs ともに stage 専用に絞る)
- log_kwargs に `pair=<実 pair 名>` 追加 (= canonical None / non-None 両分岐)

#### S3: cross_pair.py の `_run_pair_sharpe` 戻り値 3-tuple 化
- `(sharpe, failure_reason, sidecar_inputs)`
- 成功時: `_PairSidecarInputs` instance (= bt + trades + equity_curve + bars 参照)
- metric_unavailable 時: sidecar 保持 (= canonical 観測継続、 dual-path で canonical_skipped emit)
- exception 時: sidecar None (= dual-path skip)

#### S4: `evaluate_cross_pair` で sidecar 集約
- `sidecar_inputs_per_pair` dict を構築 → `CrossPairResult(_shadow_sidecar_inputs=sidecar_inputs_per_pair, ...)` で渡す
- aggregation 経路 (= sharpe_per_pair / pass_criteria / aggregate_fitness) に絶対干渉しない

#### S5: `evaluate_stage_c` の cross_pair 区画 dual-path 配線 + sanitize
- try-finally で物理隔離: dual-path 経路成功 / 例外 / disabled mode 全分岐で sanitize finally 句実行
- per-pair iterate: enabled mode で canonical 計算 + log emit、 disabled mode で軽量 log のみ emit
- invalid pair key (= 空文字 / 空白 / 非 str) 早期検出 + WARN log + skip

#### S6: テスト 23 ケース追加 (cross_pair 58 + dual-path 51 + 23 new = 132 PASS、 alpha_factory 全 2208 PASS)
- helper 単体識別子契約 (= None / 空文字 / 空白 / 前後空白 / non-C_cross_pair / fold_index non-B_fold で ValueError)
- 既存 51 caller 後方互換 (= A / B_IS / B_fold / C_base / C_stress 全 stage)
- E2E test (= evaluate_stage_c with cross_pair_evaluator + sidecar)
  - 3 entries / genome emit (= per-pair × 3)
  - skipped / cp_evaluator None で 0 件
  - canonical raise / log raise で payload 不変 (= D1/D3)
  - disabled mode で canonical_skipped event emit (= per-pair lightweight log)
  - sanitize 経路で `_shadow_sidecar_inputs == {}` (= 成功時 / 例外時 / disabled mode 全分岐)
  - invalid pair key で skip + `_log_canonical_dual_path` 未到達
- dataclass 振る舞い (= equality / repr / pickle 互換)

#### smoke 計測関連 (= 新規 3 ファイル、 acceptance B2 / B3 merge 条件 SSOT)
- `scripts/smoke/measure_step1.8_memory.sh`: stale file rm -f 初期化 + psutil sampler 起動 + uv run python 経路統一
- `scripts/smoke/sample_worker_rss.py`: per-worker RSS sampling (= header 検証 + cross-run contamination guard、 grace 1.0 秒)
- `scripts/smoke/aggregate_step1.8_memory.py`: B2/B3 merge gate 判定 (= sampled_max_worker_rss < 3 GB + step 1.7 baseline ±20%)、 sampling 失敗時 INCONCLUSIVE で exit 1

#### ドキュメント
- `docs/alpha_factory/stage-gates.md` 末尾に「B Phase 2 切替コミット dual-path log SSOT (= step 1-1.8)」 セクション追加 (= ログ命名規約 SSOT 表 / 識別子契約 / dual-path skip SSOT / sanitize 経路 / smoke merge gate / stale file contamination guard 全件 SSOT)

最終 test 結果: **alpha_factory 全 2208 passed** (= step 1.7 比 +27)、 1 xfailed、 ruff / mypy clean (= step 1.8 関連)。

### 1.3 main マージ + worktree クリーンアップ

- worktree commit `490b45e` を main に no-ff merge (`c3ee70a`)
- worktree `todo-T086` クリーンアップ + branch 削除済 (= --force 使用、 untracked は他作業の残骸)
- worktree `todo-T081` は引き続き保持

---

## 2. 累積 commit 一覧 (本セッション、 main 6 個)

```
c3ee70a Merge branch 'todo/T086'                                          ← main マージ
70e1536 docs(TODO): T086 B-phase2-step1.8 (Stage C cross_pair dual-path) Closed (impl-review Round 5 APPROVED)
490b45e feat(B step 1.8): Stage C cross_pair (ii-lite) dual-path 配線追加 (Codex impl-review Round 5 APPROVED)  ← worktree commit
1464d87 docs(TODO): T086 B-phase2-step1.8 (Stage C cross_pair dual-path) Open 追加
da1b048 docs(B-phase2-step1.8): Stage C cross_pair (ii-lite) dual-path 拡張 設計完了
```

本セッション commit 計 5 個 (= 設計 1 + Open 1 + 実装 1 + Closed 1 + Merge 1)。 cascade port v2 全体 commit 累計 ~88 個。

### 2.1 補足資料

- 概念設計 review: `devnotes/20260504-0010-B-phase2-step1.8-stage-c-cross-pair-dual-path/conceptual-review-round-{1,2,3}.md`
- 詳細設計 review: `devnotes/20260504-0010-B-phase2-step1.8-stage-c-cross-pair-dual-path/detailed-review-round-{1,2,3,4,5}.md`
- 実装 review: `devnotes/20260504-0154-todo-T086/impl-review-round-{1,2,3,4,5}.md`

---

## 3. dual-path 観測点 (= step 1.8 完了時点)

per genome:
- Stage A: 1 entry
- Stage B IS: 1 entry
- Stage B fold: n_fold entries (動的、 ~8 fold 想定)
- Stage C base: 1 entry
- Stage C stress: 1 entry (= step 1.7、 stress 成功時のみ)
- **Stage C cross_pair: 3 entries (本セッションで追加、 cp_result 受領 + sidecar 取得時のみ、 per-pair × 3)**
- 合計: **6 + n_fold entries / genome**

GA Run 30 generations × 50 individuals × 6 pairs = 9000 genomes/Run、 n_fold = 8 想定で:
- ~14 entries × 9000 genomes = ~126,000 dual-path log entries / Run

### 3.1 残未観測軸

- **canonical 5 metrics の数値 calibration 解釈**: 別計画 (= n>>30 実 GA Run + collider bias 抑止条件下)
- mission 必須軸 (= ii-lite) の per-pair canonical observability は **完成** (= step 1.8 で per-pair × 3 entries 観測完了)

→ Stage C 全評価軸 (= base + stress + cross_pair) の canonical 観測完成、 step 2 着手前提条件 (= mission 軸の observability 完成) 達成。

---

## 4. 次セッション着手フロー

### 4.1 推奨次着手: B step 2 (= stage_bc_evaluator main flow 統合)

**scope**: `src/alpha_factory/stage_bc_evaluator.py` (= `evaluate_stage_b_pooled` / `evaluate_stage_c_lite`) を main flow から呼出。

- step 1.5 / 1.6 / 1.7 / 1.8 で dual-path 観測点が 6 系列で揃った (= mission 必須軸 observability 完成)
- mission 軸の calibration data が揃った状態で stage_bc_evaluator caller への置換が安全

**規模**: 大 (= stage_gate.py の Stage B/C ハンドラを stage_bc_evaluator caller に置換)

### 4.2 着手前調査が必要な軸

- `src/alpha_factory/stage_bc_evaluator.py` の signature と既存 API
- 現在の `evaluate_stage_b` / `evaluate_stage_c` (stage_gate.py) が stage_bc_evaluator に置換可能な構造か
- step 1.5-1.8 の dual-path log で取れた calibration data が stage_bc_evaluator 統合後も継続観測可能か
- **重要**: step 1.8 で導入した sanitize 経路 / `_shadow_sidecar_inputs` field / `_PairSidecarInputs` が stage_bc_evaluator caller でも一貫して動作するか (= main flow 経路の置換で sanitize の finally 保証が崩れないか)

### 4.3 各 step の Codex 設計 / 実装 review fence

1. zenigame-fx-alpha-design で skeleton → Codex review APPROVED
2. zenigame-fx-implement で worktree todo/B-step2 で実装 → Codex impl-review APPROVED
3. main マージ → 次 step

---

## 5. 7 step segmentation 全体俯瞰 (= 進捗反映)

| step | 内容 | 統合先 module | 状態 |
|---|---|---|---|
| step 1 ✨ | canonical_metrics → main flow (= Stage A dual-path) | canonical_metrics | **完了** (commit 9bc6a02) |
| step 1.5 ✨ | Stage B IS + Stage C base dual-path | (stage_gate.py のみ) | **完了** (commit 6276d58) |
| step 1.6 ✨ | Stage B per-fold dual-path | (stage_gate.py のみ) | **完了** (commit 1dadc8b) |
| step 1.7 ✨ | Stage C stress dual-path | (stage_gate.py のみ) | **完了** (commit e3a428b) |
| step 1.8 ✨ | Stage C cross_pair (ii-lite) dual-path 拡張 | (stage_gate.py + cross_pair.py + scripts/smoke + docs) | **完了** (commit c3ee70a) |
| **step 2** | stage_bc_evaluator → main flow | stage_bc_evaluator | **次推奨 (mission 軸 observability 完成済の状態で着手)** |
| step 3-7 | (詳細はハンドオフ § 4) | ... | 後続 |

---

## 6. 次セッション first prompt 例

### B step 2 (推奨) 着手の場合

```
引き継ぎは devnotes/20260504-1018-B-step1.8-complete-handoff/handoff.md 読んで。
B Phase 2 切替コミット step 2 (= stage_bc_evaluator main flow 統合) を実装着手。

着手前調査:
1. src/alpha_factory/stage_bc_evaluator.py の signature と既存 API
2. 現在の evaluate_stage_b / evaluate_stage_c (stage_gate.py) が stage_bc_evaluator
   caller に置換可能な構造か
3. step 1.5-1.8 の dual-path log で取れた calibration data が stage_bc_evaluator
   統合後も継続観測可能か
4. step 1.8 で導入した sanitize 経路 / _shadow_sidecar_inputs / _PairSidecarInputs
   が main flow 経路置換で finally 保証が崩れないか

設計:
5. step 1 / 1.5 / 1.6 / 1.7 / 1.8 で凍結した canonical_adapter.py / helper を
   完全再利用 (= adapter / helper 改変ゼロ)
6. dual-path 配線 (= step 1.5-1.8 の 6 entries / genome SSOT) を stage_bc_evaluator
   caller でも保持
7. acceptance: regression 0 (= 既存 alpha_factory 全 2208 PASS 不変) +
   step 1.8 で確立した sanitize / pickle / 識別子契約 全保持

ゆっくり・確実に: 規模 大の改修なので着手前調査充実 + 設計 2 段階で進める。

Codex review APPROVED → 実装 → main マージ → step 3 へ。
```

---

## 7. 残課題・運用観測 follow-up (= step 1.8 から繰り越し)

詳細設計 § 13 / 概念設計 follow-up 反映:

1. **canonical 失敗件数閾値ベースの fail-fast サーキットブレーカ**: step 1.8 では WARN log のみ
2. **CI メモリ閾値ガード**: smoke 5 Run の peak RSS / wall time / dual-path log bytes を CI で監視。 step 1.8 では手動実測 (= acceptance B2 merge 条件、 SSOT は psutil sampling)
3. **canonical sidecar archive Parquet schema 拡張**: 永続化層への canonical 値書き込み (= step 3 cpps_archive 統合と合わせて検討、 cross_pair の per-pair canonical も対象)
4. **cross_pair gate との対応付け / calibration**: C_cross_pair canonical の意味整合は step 2 か別 step で扱う
5. **stage_bc_evaluator 統合**: step 2 で対応 (= cross_pair 経路の整合は step 1.8 完了後の現状で再確認)
6. **dual-path log volume 増加**: step 1.7 比 +3 entries / genome (cross_pair 走った場合のみ)、 必要なら structlog filter で観測 only run と production run で出力レベル切替
7. **smoke スクリプト unit test** (= Round 5 [Suggestion] 反映、 別タスクで追加が望ましい): missing sample / stale header mismatch / json_decode_error / B3 baseline missing の小さい test を追加すると将来の退行防止が強くなる
