# 概念設計: T066 — CPPS 2-state FSM + CA/DA archive admission/eviction

**作成日時**: 2026-04-30 12:17 JST、 Round 2 修正 12:35 JST
**前提**: synthesis Round 21 改訂後 (2026-04-30 確定)、 T058-T065 設計 APPROVED、 **T064 follow-up (c_pass_depth field 追加)** を Phase 0 として要する
**マイルストーン**: M3 (GA 中核) の 2 番目の TODO、 T065 と組み合わせて M3 完了
**位置付け**: T065 selection 結果と T064 BC 評価を消費し、 CPPS 2-state FSM (push/pull) と Two-Archive (CA/DA) の admission/eviction を提供する pure function module

## Round 1 review 反映 (Codex 概念レビュー)

| Round 1 [Critical/Warning/Suggestion] | 概念設計での吸収 |
|---|---|
| [C1] archive_admit SSOT 崩壊 (§3.1: IndividualEvaluation, §8.2: ArchiveMember, §11.2: Mapping[str, ArchiveMember]) | **入力 dataclass を 2 層に分離** (Suggestion 1 採用): `ArchiveCandidate` (admission 前、 全 source field 含む) + `ArchiveMember` (archive 登録後、 archive_role は 3 種類のみ、 archive_target 確定)。 § 3.1 / § 8 / § 11.2 を統一して `archive_admit(state, candidates: Mapping[str, ArchiveCandidate], ...)` に |
| [C2] dataclass field 欠落 (gate_worst_gap, run_id_index, new_dataset_epoch_id) | `ArchiveCandidate` に `gate_worst_gap` / `dataset_epoch_id` / `genome_id` / `run_id` / `generation_no` 等を必須化。 `update_archive_per_run` に `new_dataset_epoch_id` 引数追加。 `run_id_index` は ArchiveState.run_history から pure 計算化 |
| [C3] CA/DA 流入責務未定義 (DA に何が入るかが本文にない) | **設計判断確定 (synthesis § 8.2 解釈)**: T066 Phase 1 では `archive_admit` は **CA admission のみ** を実施。 DA admission は T067 warmstart 経路で別途扱う (Phase 2 で確定)。 archive_target は admission 時に T066 が「mission_pass / progress_pass / score_bypass の 3 層は全て CA」 と決定。 DA は eviction のみ T066 提供。 § 1 / § 8 / § 11.2 で明文化、 synthesis Round 22 改訂候補として § 13 残論点に追加 |
| [C4] 強制遷移値不整合 (§1.1/§5.2: gen=64 で 44 / §4.1: pop_gen=64 else 30) | § 4.1 / § 5.2 / § 11.2 で **force_g は caller 引数で渡す方針** に統一 (config 由来)、 「gen=64 baseline → force_g=44、 gen=48 fallback → smoke 後再校正」 を default として明示。 概念設計内で hardcode しない |
| [C5] deterministic 不足 (lex 末尾に stable key なし、 admit が Mapping.values 順序依存) | CA / DA eviction lex の末尾に `genome_id` を追加 (lex 9 段 / 8 段に拡張)。 `archive_admit` 内では `sorted(candidates.items(), key=lambda kv: kv[0])` 等で入力順固定 |
| [W1] compute_ca_da_capacities pop>=2 vs archive 系 192/256 限定 | 全 capacity 系 API を 192/256 限定に統一、 他 pop_size は ValueError raise |
| [W2] target_inflow 丸め規約未明記 | 192/256 固定値表 (target=8/10、 per_run_max=12/16) を SSOT とし、 0.04*pop / 0.06*pop は導出規約として注記。 将来の pop_size 追加時は table 拡張で対応 |
| [W3] partition_survivors_to_ca_da が sort_keys 未使用 | sort_keys 引数削除、 「survivor_indices は T065 sort 順前提」 を docstring 明示 |
| [W4] recency_floor=12 「保証」 vs 12 未満時不可 | 「best-effort」 化、 recency_floor 未達時は `RecencyFloorUnmet` warning + eviction 続行を明記 |
| [W5] per_run_max 超過時の階層内残留未定義 | trim 規則確定: 階層内では admission key (gate_worst_gap 昇順 / mission_signed_margin 降順) で残留優先 |
| [W6] quality_floor_margin と margin_inf p70 threshold 混線 | 名前分離: DA eviction #5 は `quality_floor_margin` (caller 計算)、 admission の品質床は `margin_inf_passes_p70 (bool)` (caller 計算済 bool で受ける) |
| [S1] 入力を 2 層に分離 (ArchiveCandidate / ArchiveMember) | 採用 (Critical 1 と統合) |
| [S2] update_archive_per_run に new_dataset_epoch_id 引数 | 採用 (Critical 2 と統合) |
| [S3] eviction lex 末尾に genome_id、 run_id_index pure 計算化 | 採用 (Critical 5 と統合) |
| [S4] not_score_bypass は導出値 | ArchiveMember では保存値削除、 lex 比較時に `archive_role != "score_bypass"` で導出 |
| [S5] c_pass_depth は INCONCLUSIVE、 T064 SSOT 改訂を先 | **T066 Phase 0**: T064 follow-up で BCEvaluationResult に `c_pass_depth: float` field 追加 PR を T066 詳細設計より先に着地。 計算式: `c_pass_depth = c_lite_n_pass_windows × 0.25 + (1.0 if c_result.mission_pass==PASS else 0.5 if PENDING else 0.0)` (合計 [0, 1.75])、 詳細は T064 follow-up で確定 |

---

## 1. 背景・課題

synthesis § 7.2-7.4 + § 8.1-8.3 で確定した **CPPS 2-state FSM (push/pull)** と **CA/DA Two-Archive admission/eviction** を zenigame-fx に big-bang 移植する。 既存実装 (単純 fitness ranking + post-RUN MD-only sieve) はベースラインにせず全廃。

T066 が提供する責務 (Phase 1 = 単体 module + テストのみ、 既存 ga loop に未配線):

1. **CPPS 2-state FSM (push/pull)**: synthesis § 7.2、 zenigame `push_pull_fsm.py:45` 同等
   - state 遷移: `feasible_ratio_ema >= θ_switch` の連続 N 世代充足で push → pull (一方向、 thrash 防止)
   - 強制遷移: caller 引数 `force_g` (gen=64 baseline → 44、 gen=48 fallback → smoke 後再校正)
2. **CA/DA capacity 計算**: state 依存比率 (push 84/108、 pull 120/72 for pop=192、 端数規約: `CA=round(pop×ratio)`, `DA=pop-CA`)、 pop=192/256 のみ正式サポート
3. **Survivor → CA/DA partition**: T065 GenerationSelectionResult.survivor_indices を CA/DA capacity に応じて分割 (T065 sort 順前提、 sort_keys 引数不要)
4. **archive_role 判定**: T064 BCEvaluationResult から `mission_pass` / `progress_pass` / `score_bypass_candidate` / `ineligible` を決定 (synthesis § 8.2)
5. **archive_admit (CA only)**: **CA admission のみ** を実施。 3 層流入 (mission_pass 無制限 + progress_pass worst_gap 昇順 + score_bypass top-K)。 admission 時に archive_target="CA" 確定。 DA admission は T067 warmstart 経路で別途扱う (Round 1 [C3] 解消の設計判断、 § 8.5 参照)
6. **archive_evict (CA / DA 両方)**: synthesis § 8.3 の CA / DA 別 lex 順序 (Round 21 改訂後 CA #5 = mission_signed_margin、 lex 末尾に genome_id 追加で deterministic 完全保証)
7. **品質床 + ハード制約**: bypass 候補は `invariant_feasible AND margin_inf_passes_p70 (caller 計算 bool)`、 per_run_max=12 / 16、 pattern_max_share=0.25、 recency_floor=12 (best-effort)
8. **dataset_epoch_id 必須**: epoch 切替時に archive リセット、 update_archive_per_run に new_dataset_epoch_id 引数必須

T066 が**触らない** (別 TODO 担当):

- warmstart 注入 / Run 初期化 — **T067** (DA admission 経路含む、 § 8.5)
- emergency mode 発動 / 解除条件判定 — **T067** (T066 は mode フラグを引数で受ける)
- calibrate-gate — **T069 等**
- DA novelty / diversity_coverage / quality_floor_margin / margin_inf_passes_p70 の数値計算本体 — **別 TODO (zenigame archives.py 流用 + 別ヘルパー)**、 T066 は計算済値を引数で受ける
- archive 永続化 (Parquet / JSONL 書込) — **T058 schema v2 + 別 TODO**
- run_ga.py 配線 — **Phase 2 別 PR (T067 と同時)**
- observability (entropy / archive churn 等) — **T071**

### 1.1 synthesis § 7.2-7.4 / § 8.1-8.3 主要パラメータ確認

| 項目 | 値 (synthesis Round 20 + Round 21 確定) |
|---|---|
| FSM state | push (探索) / pull (収束)、 一方向 push→pull |
| pop=192 push | CA 84 / DA 108 |
| pop=192 pull | CA 120 / DA 72 |
| pop=256 push | CA 112 / DA 144 |
| pop=256 pull | CA 160 / DA 96 |
| 端数規約 | `CA = round(pop × ratio)`, `DA = pop - CA` (合計を pop に一致) |
| 遷移トリガー | `feasible_ratio_ema >= θ_switch` (smoke 後再校正)、 連続 N 世代 (zenigame 踏襲: N=3) |
| 強制遷移 | gen=64 で `gen >= 44`、 gen=48 fallback で再校正 |
| archive_total | pop=192: 120 (CA 72 / DA 48)、 pop=256: 160 (CA 96 / DA 64) |
| target_inflow / Run | pop=192: 8、 pop=256: 10 (= 0.04 × pop) |
| per_run_max | pop=192: 12、 pop=256: 16 (= 0.06 × pop) |
| bypass K (通常) | `clamp(target_inflow - n_mission - n_progress, 2, 6)` |
| bypass K (emergency) | `clamp(target_inflow + 2 - n_mission - n_progress, 4, 8)` |
| 品質床 | `invariant_feasible AND margin_inf percentile <= 70` |
| ハード制約 | per_run_max / pattern_max_share=0.25 / recency_floor=12 (last 3 runs) |

### 1.2 CA eviction lex 順序 (synthesis § 8.3、 Round 21 改訂後 + 概念 Round 1 [C5] / 詳細 Round 3 [C2] で末尾 genome_id 追加、 9 段)

```
1. is_mission_pass (= archive_role == "mission_pass"、 True が上位)
2. is_progress_pass (= archive_role == "progress_pass"、 True が上位)
3. not_score_bypass (= archive_role != "score_bypass"、 True が上位)
4. C_pass_depth (Stage C 通過の度合い、 大が上位、 T064)
5. mission_signed_margin (= min(slack_*)、 大が上位、 T062 Round 21 改訂後 SSOT)
6. shadow_robustness_score (cross-pair 通過強度、 大が上位、 T064)
7. recency (新が上位、 run_history 内 index 小)
8. log_pf_clip (大が上位、 T061)
9. genome_id (昇順、 deterministic 完全保証 tie-break、 概念 Round 1 [C5])
```

### 1.3 DA eviction lex 順序 (synthesis § 8.3 + 概念 Round 1 [C5] で末尾 genome_id 追加、 8 段)

```
1. novelty (大が上位、 caller 計算)
2. diversity_coverage (session/family の希少性寄与、 大が上位、 caller 計算)
3. is_progress_pass (= archive_role == "progress_pass"、 True が上位)
4. not_score_bypass (True が上位)
5. quality_floor_margin (大が上位、 caller 計算)
6. recency (新が上位)
7. log_pf_clip (大が上位)
8. genome_id (昇順、 deterministic 完全保証 tie-break、 概念 Round 1 [C5])
```

### 1.4 T065 / T064 / T062 / T061 連携

| データ | source | T066 での消費 |
|---|---|---|
| survivor_indices | T065 GenerationSelectionResult | CA/DA partition の入力 |
| BCEvaluationResult.mission_pass | T064 (StagePassStatus.PASS at Stage C) | archive_role 判定 (層 1) |
| BCEvaluationResult.progress_pass | T064 (Stage C-lite 2/3 windows pass) | archive_role 判定 (層 2) |
| BCEvaluationResult.b_pooled_cf | T064 | bypass 候補品質床 (Stage B 評価済) |
| BCEvaluationResult.pareto_axis_usable | T064 | bypass 候補 (invariant_feasible) |
| BCEvaluationResult.shadow_robustness_score | T064 | CA eviction #6 |
| BCEvaluationResult.c_pass_depth | T064 (推定 field 名) | CA eviction #4 |
| BCEvaluationResult.b_pooled_cf.log_pf_clip | T064 → T061 | CA / DA eviction 末端 |
| BCEvaluationResult.b_pooled_cf.gate_worst_gap | T064 → T061 | progress / score_bypass の worst_gap 昇順 |
| MissionGapResult.mission_signed_margin | T062 | CA eviction #5 |
| InvariantFlags.is_feasible | T061 | 品質床 (invariant_feasible) |
| GenomeArchiveMetadata.run_id / generation / archive_role | T058 schema v2 | recency / pattern / source_run |

### 1.5 zenigame 参考実装の流用方針

| 機構 | zenigame 出典 | fx 流用方針 |
|---|---|---|
| Push/Pull 2-state FSM | `push_pull_fsm.py:45` (PushPullFSM) | state machine 構造を踏襲、 trigger 条件を fx 用に簡素化 (synthesis § 7.2 厳密準拠) |
| Two-Archive 構造 (CA/DA 分離) | `archives.py` (ArchiveState) | dataclass 構造を踏襲、 fx は ID ベース (genome_id 経由) で世代跨ぎ identity 維持 |
| CA lex eviction | `archives.py:select_ca_lex` | lex 8 段に拡張 (synthesis Round 21 改訂後の順序) |
| DA max-min diversity | `archives.py:select_da_max_min` | DA は novelty/diversity_coverage の数値は caller (T067 or 別) 責務、 T066 は lex 順序のみ |
| ID ベース identity | `archives.py:Codex Round 1 critical fix` | fx でも genome_id を必須とし、 idx の世代跨ぎ誤参照を回避 |

### 1.6 Phase 1 / Phase 2 分離

**Phase 1 (T066 PR)**:
- `src/alpha_factory/ga/cpps_archive.py` 新規 (FSM + admission/eviction の pure function 群)
- `tests/alpha_factory/ga/test_cpps_archive.py` 新規 (約 70 件の sub-suite)
- 既存 `archive.py` / `cross_pair.py` / `swim_lane.py` / `run_ga.py` 未変更
- 単独 merge で runtime 影響なし

**Phase 2 (T067 / T070 / T071 と同時、 別 PR)**:
- `run_ga.py` per-generation chain で T065 → T066 配線
- `config/alpha_factory/default.yaml` に CPPS / Archive パラメータ追加 (T058 schema v2 準拠)
- 旧 archive 経路全廃 + sieve 削除

---

## 2. 前提検証 (C4) — current HEAD `main@8b25c61` (T065 commit 後) 基準

| 前提 | verified | 出典 |
|---|---|---|
| synthesis § 7.2 push/pull 2-state、 一方向 | ✓ | synthesis § 7.2 |
| CA/DA 配分 push 84/108 / pull 120/72 (pop=192) | ✓ | synthesis § 7.2 |
| 端数規約 `CA=round(pop×ratio)`, `DA=pop-CA` | ✓ | synthesis § 7.3 |
| archive_total=120 / CA 72 / DA 48 (pop=192) | ✓ | synthesis § 8.1 |
| 3 層流入 mission_pass / progress_pass / score_bypass | ✓ | synthesis § 8.2 |
| target_inflow=0.04×pop / per_run_max=0.06×pop | ✓ | synthesis § 8.2 |
| bypass K = clamp(8 - n_mission - n_progress, 2, 6) (通常) | ✓ | synthesis § 8.2 |
| 品質床 invariant_feasible AND margin_inf p<=70 | ✓ | synthesis § 8.2 |
| CA lex 9 段 (Round 21 改訂後 #5 = mission_signed_margin、 概念 Round 1 [C5] で末尾 genome_id 追加) | ✓ | synthesis § 8.3 (改訂済) + § 1.2 / § 9.1 |
| DA lex 8 段 (novelty / diversity_coverage / ... + genome_id 末尾 tie-break) | ✓ | synthesis § 8.3 + § 1.3 / § 9.2 |
| ハード制約 per_run_max=12 / pattern_max_share=0.25 / recency_floor=12 | ✓ | synthesis § 8.3 |
| T065 GenerationSelectionResult.survivor_indices で CA/DA partition | ✓ | T065 詳細設計 APPROVED |
| T064 BCEvaluationResult に mission_pass / progress_pass / shadow_robustness_score | ✓ | T064 詳細設計 APPROVED |
| T062 MissionGapResult.mission_signed_margin | ✓ | T062 詳細設計 APPROVED + synthesis Round 21 改訂 |
| T061 CanonicalFiveResult に log_pf_clip / gate_worst_gap | ✓ | T061 詳細設計 APPROVED |
| T058 schema v2 で archive_role / dataset_epoch_id 必須 | ✓ | T058 詳細設計 APPROVED |
| zenigame `push_pull_fsm.py:45` / `archives.py` 構造踏襲 | ✓ | zenigame `push_pull_fsm.py:45`、 `archives.py` |
| 既存 zenigame-fx に CPPS / Two-Archive 実装は未存在 | ✓ | grep `PushPullState\|CA / DA\|cpps` で hit なし |

---

## 3. 責務範囲とスコープ分離

### 3.1 Phase 1 (T066 PR) スコープ

**新規 module**: `src/alpha_factory/ga/cpps_archive.py`

提供 API は **§ 11.2 を SSOT とする**。 § 3.1 内では概略のみ記載 (シグネチャ詳細は § 11.2 を参照、 詳細 Round 2 [C3] / [Suggestion 3] で同期):

- dataclass: `PushPullState`、 `ArchiveCandidate` (admission 前)、 `ArchiveMember` (admission 後、 archive_target 確定)、 `ArchiveState`、 `InflowTargets`、 `AdmissionReport` (§ 8.1.1-8.1.2 / § 10)
- CPPS FSM: `update_push_pull_state` / `compute_ca_da_capacities` / `compute_archive_capacities`
- Survivor partition: `partition_survivors_to_ca_da` (sort_keys 不要、 T065 sort 順前提)
- archive_role: `determine_archive_role(bc_result) -> Literal[...]`
- Inflow: `compute_inflow_targets`
- admission: `archive_admit(state, candidates: Mapping[str, ArchiveCandidate], *, pop_size, mode)` — **CA admission のみ** (§ 8.5)
- eviction: `archive_evict_ca` / `archive_evict_da`
- top-level: `update_archive_per_run(prev, candidates, *, pop_size, mode, new_dataset_epoch_id, new_run_id)`

**新規テスト**: `tests/alpha_factory/ga/test_cpps_archive.py` (13 sub-suite × 約 70 件)

### 3.2 Phase 2 (T067 / T070 / T071 と同時、 別 PR)

- `src/alpha_factory/ga/__init__.py` で `from .cpps_archive import ...` 追加 (T065 と同時)
- `scripts/alpha_factory/run_ga.py` per-generation chain: T063 → T064 → T062 → T065 → **T066 update_push_pull_state + partition_survivors_to_ca_da** → archive_admit (Run 終了時)
- `config/alpha_factory/default.yaml` に CPPS / Archive パラメータ追加
- 旧 archive 経路全廃

### 3.3 non-責務 (touch しない)

- novelty / diversity_coverage / quality_floor_margin の数値計算本体 — 別 TODO (zenigame `archives.py:compute_d_genome` / `compute_d_slack` 流用)、 T066 では引数で受け取る
- emergency mode 発動 / 解除条件 — T067 / T068 (T066 は mode 引数で受ける)
- warmstart 注入 — T067
- archive 永続化 (Parquet / JSONL) — T058 schema v2 + 別 TODO
- Run loop 全体 / population init — T067
- A→B 乖離自動 q_force 引き上げ — T071

---

## 4. データフロー

### 4.1 per-generation (FSM 更新 + survivor partition、 Round 1 [C4] / [W3] 反映)

```
入力:
- prev_state: PushPullState
- generation_no: int
- feasible_ratio_ema: float (T071 observability で計算済、 caller 引数)
- survivor_indices: Sequence[int] (T065 出力、 sort 順前提)
- pop_size: int
- force_g: int (caller 引数、 config 由来)
- theta_switch: float (caller 引数、 仮 0.40)

処理:
1. new_state = update_push_pull_state(
       prev_state,
       generation_no=g,
       feasible_ratio_ema=r_feas,
       force_g=force_g,                   # config 由来、 gen=64 baseline → 44
       theta_switch=theta_switch,
       consecutive_n=3,
   )
2. ca_cap, da_cap = compute_ca_da_capacities(pop_size, new_state.phase)
3. ca_indices, da_indices = partition_survivors_to_ca_da(
       survivor_indices, phase=new_state.phase, pop_size=pop_size,
   )
   # T065 sort 順前提 (rank → -crowding → genome_hash → index 昇順)
   # CA は survivor 先頭から ca_cap 体、 DA は次の da_cap 体

出力:
- new_state, ca_indices, da_indices
```

### 4.2 per-Run (archive 更新、 詳細 Round 2 [C1] + Round 3 [W2] 反映で § 8.6 と同期)

`update_archive_per_run` 入口での処理順序 (詳細 Round 2 [C1] 修正、 詳細は § 8.6):

```
入力:
- prev_archive: ArchiveState
- candidates: Mapping[str, ArchiveCandidate]   # genome_id → candidate
- pop_size: int
- mode: "normal" | "emergency"
- new_dataset_epoch_id: str
- new_run_id: str

処理 (§ 8.6 SSOT、 本節は要約):
1. candidates 全件の dataset_epoch_id 一致検証 (詳細 Round 2 [W2])
2. epoch 切替検出 (prev_archive.dataset_epoch_id != new_dataset_epoch_id)
   → 不一致なら archive 初期化 (members=()、 run_history=())
3. **run_history を先に更新** (詳細 Round 2 [C1]、 maxlen=10、 新が前):
   `new_run_history = (new_run_id,) + base.run_history`
4. archive_admit 呼出 (eviction 内で更新済 run_history を参照、 当 Run 新規が「最新」 として正しく扱われる)
   - candidate.archive_role 確認 (= determine_archive_role(bc_result))
   - inflow_targets = compute_inflow_targets(pop_size, n_mission, n_progress, mode=mode)
   - CA admission のみ (mission/progress/score_bypass の 3 層)、 品質床 (invariant_feasible AND margin_inf_passes_p70)
   - hard constraints (per_run_max / pattern_max_share=0.25)
   - merge は upsert (詳細 Round 3 [C1]、 genome_id 一意制約)
   - CA / DA eviction (lex 末尾から削除)
5. epoch reset 時は AdmissionReport.dataset_epoch_reset=True

出力:
- new_archive, AdmissionReport
```

`AdmissionReport` の field 詳細は § 10 SSOT 参照。 selected (hard constraints 前) vs admitted (実流入) を別カウント (詳細 Round 3 [W1])。

---

## 5. CPPS 2-state FSM

### 5.1 状態 dataclass

```python
@dataclass(frozen=True)
class PushPullState:
    """CPPS 2-state FSM の状態 (immutable)."""
    phase: Literal["push", "pull"]
    consecutive_count: int     # 切替条件成立の連続世代数
    switch_generation: int | None    # pull 遷移時の世代番号 (None for push)
    last_feasible_ratio_ema: float
    forced_switch: bool        # gen >= force_g による強制遷移かどうか
```

### 5.2 遷移関数 (Round 1 [C4] 反映)

```python
def update_push_pull_state(
    prev: PushPullState,
    *,
    generation_no: int,
    feasible_ratio_ema: float,
    force_g: int,                    # caller 引数 (config 由来)、 gen=64 baseline → 44、 gen=48 fallback → smoke 後再校正
    theta_switch: float,             # smoke 後再校正、 仮 0.40
    consecutive_n: int = 3,          # zenigame 踏襲
) -> PushPullState:
    """Push → Pull 一方向遷移を計算.

    一方向性 (push → pull のみ): 一度 pull に入ったら pull のまま
    強制遷移: generation_no >= force_g なら pull 強制 (forced_switch=True)
    通常遷移: feasible_ratio_ema >= theta_switch かつ
              consecutive_count >= consecutive_n の場合
    """
    if prev.phase == "pull":
        # 一方向、 pull 維持
        return replace(prev, last_feasible_ratio_ema=feasible_ratio_ema)

    # push → pull 判定
    if generation_no >= force_g:
        return PushPullState(
            phase="pull",
            consecutive_count=0,
            switch_generation=generation_no,
            last_feasible_ratio_ema=feasible_ratio_ema,
            forced_switch=True,
        )

    if feasible_ratio_ema >= theta_switch:
        new_count = prev.consecutive_count + 1
        if new_count >= consecutive_n:
            return PushPullState(
                phase="pull",
                consecutive_count=new_count,
                switch_generation=generation_no,
                last_feasible_ratio_ema=feasible_ratio_ema,
                forced_switch=False,
            )
        return replace(prev, consecutive_count=new_count, last_feasible_ratio_ema=feasible_ratio_ema)
    else:
        # 連続失敗、 count リセット
        return replace(prev, consecutive_count=0, last_feasible_ratio_ema=feasible_ratio_ema)
```

### 5.3 CA/DA capacity 計算

```python
PUSH_CA_RATIO = 84 / 192   # = 0.4375
PULL_CA_RATIO = 120 / 192  # = 0.625
SUPPORTED_POP_SIZES = (192, 256)


def compute_ca_da_capacities(pop_size: int, phase: Literal["push", "pull"]) -> tuple[int, int]:
    """state 依存 CA/DA capacity (端数規約: CA=round(pop×ratio), DA=pop-CA).

    pop_size は 192 / 256 のみ正式サポート (詳細 Round 2 [C5] 反映、 W1 統一).
    他は ValueError raise. 192/256 で固定値を返す (詳細 Round 1 [W2] 丸め規約):
    - push: pop=192 → (84, 108) / pop=256 → (112, 144)
    - pull: pop=192 → (120, 72) / pop=256 → (160, 96)
    """
    if pop_size not in SUPPORTED_POP_SIZES:
        raise ValueError(
            f"pop_size must be one of {SUPPORTED_POP_SIZES}, got {pop_size}"
        )
    ratio = PUSH_CA_RATIO if phase == "push" else PULL_CA_RATIO
    ca = round(pop_size * ratio)
    da = pop_size - ca
    return ca, da
```

合計 = pop_size 一致を保証 (端数規約 synthesis § 7.3)。

### 5.4 Archive 容量 (per-Run baseline、 pop_size 連動)

```python
ARCHIVE_TOTAL_192 = 120
ARCHIVE_CA_192 = 72
ARCHIVE_DA_192 = 48
ARCHIVE_TOTAL_256 = 160
ARCHIVE_CA_256 = 96
ARCHIVE_DA_256 = 64

def compute_archive_capacities(pop_size: int) -> tuple[int, int, int]:
    """archive_total / CA / DA (synthesis § 8.1)."""
    if pop_size == 192:
        return ARCHIVE_TOTAL_192, ARCHIVE_CA_192, ARCHIVE_DA_192
    if pop_size == 256:
        return ARCHIVE_TOTAL_256, ARCHIVE_CA_256, ARCHIVE_DA_256
    raise ValueError(f"pop_size must be 192 or 256, got {pop_size}")
```

注: pop_size=192/256 のみ正式サポート、 他は ValueError (smoke 後の追加検討)。

---

## 6. archive_role 判定 (3 層流入 + ineligible)

```python
def determine_archive_role(
    bc_result: BCEvaluationResult | None,
) -> Literal["mission_pass", "progress_pass", "score_bypass_candidate", "ineligible"]:
    """T064 出力から archive_role を一意に決定.

    階層: mission_pass > progress_pass > score_bypass_candidate > ineligible
    - mission_pass: bc_result.mission_pass == StagePassStatus.PASS
    - progress_pass: bc_result.progress_pass == StagePassStatus.PASS (mission_pass=False の時)
    - score_bypass_candidate: pareto_axis_usable=True かつ b_pooled_cf is not None
      (= Stage B 評価済 + invariant_feasible)、 上記 2 層に該当しない場合
    - ineligible: bc_result is None (a_fail or B-invariant-fail)、 archive 流入対象外

    contract: caller (archive_admit) は最終的に品質床
    (margin_inf percentile <= 70) と pattern_max_share / per_run_max を適用してから admit.
    """
    if bc_result is None:
        return "ineligible"
    if bc_result.mission_pass == StagePassStatus.PASS:
        return "mission_pass"
    if bc_result.progress_pass == StagePassStatus.PASS:
        return "progress_pass"
    if bc_result.pareto_axis_usable and bc_result.b_pooled_cf is not None:
        return "score_bypass_candidate"
    return "ineligible"
```

### 6.1 Inflow targets

```python
@dataclass(frozen=True)
class InflowTargets:
    target_inflow: int           # 0.04 × pop
    per_run_max: int             # 0.06 × pop
    bypass_k: int                # clamp(target - n_mission - n_progress, [2, 6] or [4, 8])
    mode: Literal["normal", "emergency"]


def compute_inflow_targets(
    pop_size: int,
    n_mission: int,
    n_progress: int,
    *,
    mode: Literal["normal", "emergency"],
) -> InflowTargets:
    """synthesis § 8.2 確定式."""
    if pop_size == 192:
        target = 8
        per_run_max = 12
    elif pop_size == 256:
        target = 10
        per_run_max = 16
    else:
        raise ValueError(f"pop_size must be 192 or 256, got {pop_size}")

    if mode == "emergency":
        target += 2     # synthesis § 8.2 emergency: clamp(target+2 - n_m - n_p, 4, 8)
        bypass_min, bypass_max = 4, 8
    else:
        bypass_min, bypass_max = 2, 6

    bypass_k = max(bypass_min, min(bypass_max, target - n_mission - n_progress))
    return InflowTargets(
        target_inflow=target,
        per_run_max=per_run_max,
        bypass_k=bypass_k,
        mode=mode,
    )
```

---

## 7. Survivor → CA/DA partition (詳細 Round 2 [C3] 反映で sort_keys 引数削除)

```python
def partition_survivors_to_ca_da(
    survivor_indices: Sequence[int],
    *,
    phase: Literal["push", "pull"],
    pop_size: int,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """state 依存比率で survivor を CA / DA に分割.

    入口契約 (T065 sort 順前提):
    - survivor_indices は T065 GenerationSelectionResult.survivor_indices で
      `(rank, -crowding, genome_hash, index)` の lex 昇順にソート済
    - len(survivor_indices) <= pop_size
    - 順序保証は caller (T065 / Phase 2) 責務、 T066 は再 sort しない

    分割規約:
    - CA = 先頭 ca_cap 体 (rank/crowding で優位な個体、 収束圧)
    - DA = 次の da_cap 体 (多様性保持)
    - eligible が pop_size 未満の場合、 ca_indices + da_indices < pop_size
      (caller 認識、 sample_size_warnings は T065 GenerationSelectionResult で既に出力済)
    """
    ca_cap, da_cap = compute_ca_da_capacities(pop_size, phase)
    survivors_list = list(survivor_indices)
    if len(survivors_list) > pop_size:
        raise ValueError(
            f"survivor count {len(survivors_list)} exceeds pop_size {pop_size}"
        )
    ca_indices = tuple(survivors_list[:ca_cap])
    da_indices = tuple(survivors_list[ca_cap:ca_cap + da_cap])
    return ca_indices, da_indices
```

---

## 8. Archive admission (CA only、 3 層流入、 Round 1 [C1] / [C3] 反映)

### 8.1 dataclass 2 層モデル (Round 1 Suggestion 1 採用)

#### 8.1.1 ArchiveCandidate (admission 前、 全 source field を持つ)

```python
@dataclass(frozen=True)
class ArchiveCandidate:
    """archive admission 前の候補 (caller 構築、 全 source field を持つ).

    caller (T067 / Phase 2 run_ga.py) は T064 BCEvaluationResult / T062 MissionGapResult /
    T061 InvariantFlags / T058 schema v2 metadata から本 dataclass を構築して T066 に渡す.
    """
    # identity (T058 schema v2 必須)
    genome_id: str                               # 世代跨ぎ identity、 lex 末尾 tie-break
    run_id: str                                  # 流入 Run ID (recency 用)
    generation_no: int                           # 流入 generation
    dataset_epoch_id: str                        # epoch 跨ぎ汚染防止 (T058)
    pattern_id: str                              # session/family pattern (pattern_max_share)
    family_id: str                               # family (warmstart cooldown、 T067)

    # archive_role 判定材料 (T064 BCEvaluationResult から導出、 caller 計算済)
    archive_role: Literal["mission_pass", "progress_pass", "score_bypass_candidate", "ineligible"]
    gate_worst_gap: float                        # T061 → T064 b_pooled_cf.gate_worst_gap (admission sort key)

    # CA eviction lex 4-7 用 (T064 / T062 / T061 経由)
    c_pass_depth: float                          # T064 follow-up で追加 (Phase 0)
    mission_signed_margin: float                 # T062 (Round 21 改訂後 CA #5)
    shadow_robustness_score: float               # T064 (CA #6)
    log_pf_clip: float                           # T061 (末端 tie-break)

    # 品質床 (caller 計算済)
    invariant_feasible: bool                     # T061 InvariantFlags.is_feasible
    margin_inf: float                            # 品質床 percentile 計算 source
    margin_inf_passes_p70: bool                  # caller 計算済 bool (= margin_inf <= 当 Run p70 threshold)

    # DA eviction lex 1-2, 5 用 (caller 計算、 別 TODO 担当)
    novelty: float                               # 別 TODO で zenigame archives.py 流用
    diversity_coverage: float                    # 同上
    quality_floor_margin: float                  # 同上 (Round 1 [W6] で margin_inf threshold と分離)
```

#### 8.1.2 ArchiveMember (archive 登録後、 不変メタ)

```python
@dataclass(frozen=True)
class ArchiveMember:
    """archive 登録後の不変メタデータ (admission 経て確定).

    archive_role は admission 時に "score_bypass_candidate" → "score_bypass" に変換される
    (= 「品質床通過 + bypass 選定された」 ことを明示)。 archive_target は T066 が決定。
    not_score_bypass は保存値ではなく `archive_role != "score_bypass"` で導出 (Round 1 [S4]).
    """
    # identity
    genome_id: str
    run_id: str
    generation_no: int
    dataset_epoch_id: str
    pattern_id: str
    family_id: str

    # admission 時に確定
    archive_role: Literal["mission_pass", "progress_pass", "score_bypass"]
    archive_target: Literal["CA", "DA"]          # Phase 1: CA only (T066 で確定)、 DA admission は T067 別経路

    # eviction lex 用 (ArchiveCandidate からコピー)
    gate_worst_gap: float
    c_pass_depth: float
    mission_signed_margin: float
    shadow_robustness_score: float
    log_pf_clip: float
    novelty: float
    diversity_coverage: float
    quality_floor_margin: float
    margin_inf: float
    invariant_feasible: bool

    @property
    def not_score_bypass(self) -> bool:
        """CA / DA eviction lex 第 3 段の導出値 (Round 1 [S4])."""
        return self.archive_role != "score_bypass"
```

### 8.2 archive_admit 実装 (CA only、 Round 1 [C1] / [C3] / [C5] 反映)

```python
def archive_admit(
    archive_state: ArchiveState,
    candidates: Mapping[str, ArchiveCandidate],   # genome_id → candidate
    *,
    pop_size: int,
    mode: Literal["normal", "emergency"],
) -> tuple[ArchiveState, AdmissionReport]:
    """CA admission 3 層流入 + ハード制約 + 品質床 (DA admission は T067 別経路).

    Phase 1: pure function、 archive_state は immutable に置換 (replace).
    Phase 2: T067 で run_ga.py 配線、 emergency mode 判定 caller 責務.

    入力順依存性排除 (Round 1 [C5]): candidates.items() は sorted(genome_id) で安定化、
    同一スコア tie は genome_id 昇順で決定論化.
    """
    # 0. 入力順固定 (genome_id 昇順)
    sorted_candidates = sorted(candidates.items(), key=lambda kv: kv[0])

    # 1. 階層別カウント (archive_role は caller が事前確定)
    n_mission = sum(1 for _, c in sorted_candidates if c.archive_role == "mission_pass")
    n_progress = sum(1 for _, c in sorted_candidates if c.archive_role == "progress_pass")
    targets = compute_inflow_targets(pop_size, n_mission, n_progress, mode=mode)

    # 2. mission_pass 全件 (per_run_max まで、 mission_signed_margin 降順 + genome_id 昇順)
    mission_pool = [c for _, c in sorted_candidates if c.archive_role == "mission_pass"]
    mission_admits = sorted(
        mission_pool,
        key=lambda c: (-c.mission_signed_margin, c.genome_id),
    )

    # 3. progress_pass: gate_worst_gap 昇順 + genome_id 昇順 で remaining inflow まで
    remaining = max(0, targets.target_inflow - len(mission_admits))
    progress_pool = [c for _, c in sorted_candidates if c.archive_role == "progress_pass"]
    progress_admits = sorted(
        progress_pool,
        key=lambda c: (c.gate_worst_gap, c.genome_id),
    )[:remaining]

    # 4. score_bypass: bypass_k 体、 品質床通過のみ
    bypass_pool = [
        c for _, c in sorted_candidates
        if c.archive_role == "score_bypass_candidate"
        and c.invariant_feasible
        and c.margin_inf_passes_p70    # caller 計算済 bool
    ]
    bypass_pool_sorted = sorted(
        bypass_pool,
        key=lambda c: (c.gate_worst_gap, c.genome_id),
    )[:targets.bypass_k]

    # 5. ArchiveCandidate → ArchiveMember 変換 (archive_target="CA" 確定、 score_bypass_candidate → score_bypass)
    admitted_members: list[ArchiveMember] = []
    for c in mission_admits:
        admitted_members.append(_to_member(c, archive_role="mission_pass", archive_target="CA"))
    for c in progress_admits:
        admitted_members.append(_to_member(c, archive_role="progress_pass", archive_target="CA"))
    for c in bypass_pool_sorted:
        admitted_members.append(_to_member(c, archive_role="score_bypass", archive_target="CA"))

    # 6. ハード制約: per_run_max / pattern_max_share (recency_floor は eviction 側、 § 9.3)
    admitted_filtered = apply_hard_constraints(admitted_members, archive_state, pop_size, targets)
    hard_drops = len(admitted_members) - len(admitted_filtered)

    # 7. archive merge (詳細 Round 3 [C1] 反映: genome_id upsert で一意制約保持)
    existing_by_id = {m.genome_id: m for m in archive_state.members}
    for nm in admitted_filtered:
        existing_by_id[nm.genome_id] = nm   # 既存 genome_id は新 member で置換 (upsert)
    new_members = tuple(existing_by_id.values())
    new_state = replace(archive_state, members=new_members)

    # 8. eviction (CA / DA capacity 超過時)
    _, ca_capacity, da_capacity = compute_archive_capacities(pop_size)
    new_state = archive_evict_ca(new_state, target_size=ca_capacity)
    new_state = archive_evict_da(new_state, target_size=da_capacity)

    # 9. AdmissionReport 構築 (詳細 Round 2 [W1] 反映: 旧 archive + 当 Run admit のうち
    #    new_state に含まれない genome_id を全て evicted_genome_ids に含める)
    admitted_ids = tuple(m.genome_id for m in admitted_filtered)
    new_state_ids = {nm.genome_id for nm in new_state.members}
    evicted_candidates = list(archive_state.members) + list(admitted_filtered)
    evicted_ids = tuple(
        m.genome_id for m in evicted_candidates
        if m.genome_id not in new_state_ids
    )
    recency_unmet = _check_recency_floor_unmet(new_state, run_history_floor=12, last_n_runs=3)
    # admitted 内訳カウント (詳細 Round 3 [W1])
    admitted_by_role = Counter(m.archive_role for m in admitted_filtered)
    return new_state, AdmissionReport(
        admitted_genome_ids=admitted_ids,
        evicted_genome_ids=evicted_ids,
        n_selected_mission=len(mission_admits),
        n_selected_progress=len(progress_admits),
        n_selected_bypass=len(bypass_pool_sorted),
        n_admitted_mission=admitted_by_role.get("mission_pass", 0),
        n_admitted_progress=admitted_by_role.get("progress_pass", 0),
        n_admitted_bypass=admitted_by_role.get("score_bypass", 0),
        mode=mode,
        hard_constraint_drops=hard_drops,
        recency_floor_unmet=recency_unmet,
        dataset_epoch_reset=False,                           # update_archive_per_run で reset 検出時に True に上書き
    )


def _to_member(
    c: ArchiveCandidate,
    *,
    archive_role: Literal["mission_pass", "progress_pass", "score_bypass"],
    archive_target: Literal["CA", "DA"],
) -> ArchiveMember:
    """ArchiveCandidate → ArchiveMember 変換 (archive 登録時の不変化)."""
    return ArchiveMember(
        genome_id=c.genome_id, run_id=c.run_id, generation_no=c.generation_no,
        dataset_epoch_id=c.dataset_epoch_id, pattern_id=c.pattern_id, family_id=c.family_id,
        archive_role=archive_role, archive_target=archive_target,
        gate_worst_gap=c.gate_worst_gap,
        c_pass_depth=c.c_pass_depth, mission_signed_margin=c.mission_signed_margin,
        shadow_robustness_score=c.shadow_robustness_score, log_pf_clip=c.log_pf_clip,
        novelty=c.novelty, diversity_coverage=c.diversity_coverage,
        quality_floor_margin=c.quality_floor_margin,
        margin_inf=c.margin_inf, invariant_feasible=c.invariant_feasible,
    )
```

### 8.3 ハード制約 (Round 1 [W5] / [W6] 反映、 階層内 trim 規則明示)

```python
ARCHIVE_ROLE_PRIORITY = {
    "mission_pass": 0,
    "progress_pass": 1,
    "score_bypass": 2,
}


def apply_hard_constraints(
    admitted: Sequence[ArchiveMember],
    archive_state: ArchiveState,
    pop_size: int,
    targets: InflowTargets,
) -> list[ArchiveMember]:
    """per_run_max / pattern_max_share=0.25 適用.

    Round 1 [W5] 反映 (per_run_max 超過時の階層内残留 trim 規則):
    - per_run_max: 当 Run admitted 数を per_run_max 体までトリム
      - 階層優先 (ARCHIVE_ROLE_PRIORITY): mission_pass > progress_pass > score_bypass
      - 同階層内: admission key (mission_pass = mission_signed_margin 降順 / progress_pass = gate_worst_gap 昇順 / score_bypass = gate_worst_gap 昇順) 順で保持
      - 最終 tie-break: genome_id 昇順
    - pattern_max_share=0.25: 同 pattern_id の archive 内総数が archive_total × 0.25 まで
      (archive_state 既存 members + 当 Run admitted の合計でカウント)

    recency_floor=12 は admission では制約なし、 eviction 側で best-effort 適用 (§ 9.3).
    """
    # 1. per_run_max トリム (階層優先 + admission key 順)
    if len(admitted) > targets.per_run_max:
        admitted = sorted(
            admitted,
            key=lambda m: (
                ARCHIVE_ROLE_PRIORITY[m.archive_role],
                # mission: -mission_signed_margin、 progress/bypass: gate_worst_gap
                -m.mission_signed_margin if m.archive_role == "mission_pass" else m.gate_worst_gap,
                m.genome_id,
            ),
        )[:targets.per_run_max]

    # 2. pattern_max_share=0.25
    archive_total, _, _ = compute_archive_capacities(pop_size)
    pattern_cap = int(archive_total * 0.25)
    pattern_count = Counter(m.pattern_id for m in archive_state.members)
    filtered = []
    for m in admitted:
        if pattern_count[m.pattern_id] < pattern_cap:
            filtered.append(m)
            pattern_count[m.pattern_id] += 1
    return filtered
```

### 8.4 品質床 (Round 1 [W6] 反映、 名前分離)

ArchiveCandidate には 2 つの独立した品質指標を持つ:

| field | 用途 | 計算者 |
|---|---|---|
| `margin_inf_passes_p70: bool` | admission 時の **品質床** (score_bypass 候補が当 Run p70 を通過したか) | caller (T067 / T071、 当 Run 全候補の margin_inf 分布から p70 threshold を計算済) |
| `quality_floor_margin: float` | DA eviction lex #5 (大が上位) | caller (別 TODO、 zenigame archives.py 流用) |

両者は独立した概念。 T066 では引数で受け取り、 admission で `margin_inf_passes_p70` を、 DA eviction で `quality_floor_margin` を消費する。 名前混線 (Round 1 [W6]) を解消。

### 8.5 DA admission 経路の責務分担 (Round 1 [C3] 解消)

**設計判断**: T066 Phase 1 の `archive_admit` は **CA admission のみ** を実施。 DA admission 経路は T067 (warmstart) で別途扱う。

理由:
1. synthesis § 8.2 の 3 層流入 (mission_pass / progress_pass / score_bypass) は GA 出力の質 metric ベースで CA 寄り (収束圧)
2. DA は novelty / diversity_coverage で評価される多様性保持、 archive 内の流入経路は warmstart や別途 admission を要する
3. zenigame `archives.py` でも CA admission と DA admission は別経路 (CA: convergence / DA: diversity による max-min selection)
4. T066 Phase 1 では CA admission に集中し、 DA admission の経路設計は T067 で確定 (Phase 2 同時 PR で archive 全体の整合性を取る)

**synthesis Round 22 改訂候補 (§ 13 残論点 R8)**: synthesis § 8.2 で「3 層流入は CA、 DA は warmstart 経路」 を明文化する改訂を T067 PR と同時に検討。 T066 単体では synthesis 改訂を必須としない (Round 22 改訂は T067 PR で同時実施推奨)。

T066 が DA に対して提供する操作:
- `archive_evict_da`: DA capacity 超過時の lex 末尾削除のみ
- DA への新規 member 追加は T066 では行わない (T067 warmstart admission で実施)

### 8.6 epoch 切替時のリセット + run_history 先反映 (詳細 Round 2 [C1] / [W2] 反映)

```python
RUN_HISTORY_MAXLEN = 10


def update_archive_per_run(
    prev_archive: ArchiveState,
    candidates: Mapping[str, ArchiveCandidate],
    *,
    pop_size: int,
    mode: Literal["normal", "emergency"],
    new_dataset_epoch_id: str,
    new_run_id: str,
) -> tuple[ArchiveState, AdmissionReport]:
    """top-level entry: epoch reset 検出 + run_history 先反映 + admission + eviction を 1 関数で.

    詳細 Round 2 [C1] 修正 (recency 順序):
    - run_history への new_run_id 追加を **archive_admit より先** に実行
    - これにより admission 後の eviction で当 Run 新規流入個体が「最新」 として扱われる

    詳細 Round 2 [W2] 修正 (epoch 汚染防止):
    - candidates 全件の dataset_epoch_id == new_dataset_epoch_id を検証
    - 不一致は ValueError (caller 責務違反、 epoch 汚染 indicator)

    epoch 切替検出 (T058 dataset_epoch_id 必須契約):
    - prev_archive.dataset_epoch_id != new_dataset_epoch_id なら archive 全リセット
      (members=()、 run_history=()、 dataset_epoch_id=new_dataset_epoch_id)
    - AdmissionReport.dataset_epoch_reset=True
    """
    # 1. candidates の epoch 一致検証 (詳細 Round 2 [W2])
    for genome_id, c in candidates.items():
        if c.dataset_epoch_id != new_dataset_epoch_id:
            raise ValueError(
                f"candidate {genome_id} dataset_epoch_id={c.dataset_epoch_id!r} "
                f"does not match new_dataset_epoch_id={new_dataset_epoch_id!r}"
            )

    # 2. epoch 切替検出 → archive 初期化
    epoch_reset = prev_archive.dataset_epoch_id != new_dataset_epoch_id
    if epoch_reset:
        base_archive = ArchiveState(
            members=(), dataset_epoch_id=new_dataset_epoch_id, run_history=(),
        )
    else:
        base_archive = prev_archive

    # 3. run_history を先に更新 (詳細 Round 2 [C1])、 maxlen=10、 新が前
    new_run_history = (new_run_id,) + base_archive.run_history
    if len(new_run_history) > RUN_HISTORY_MAXLEN:
        new_run_history = new_run_history[:RUN_HISTORY_MAXLEN]
    base_with_history = replace(base_archive, run_history=new_run_history)

    # 4. archive_admit (内部で eviction 実施、 run_history は更新済を参照)
    new_state, report = archive_admit(
        base_with_history, candidates, pop_size=pop_size, mode=mode,
    )
    if epoch_reset:
        report = replace(report, dataset_epoch_reset=True)
    return new_state, report
```

---

## 9. Archive eviction

### 9.1 CA eviction (lex 9 段、 詳細 Round 2 [C2] で archive_role 導出に統一)

```python
def _ca_eviction_sort_key(
    m: ArchiveMember,
    *,
    run_history: Sequence[str],   # archive_state.run_history (新が前)
) -> tuple:
    """CA lex eviction key (上位が残る、 末尾から削除).

    詳細 Round 2 [C2] 反映: ArchiveMember には mission_pass / progress_pass field を持たず、
    archive_role から完全導出する (= `archive_role == "mission_pass"` / `archive_role == "progress_pass"`).

    1. is_mission_pass (= archive_role == "mission_pass"、 True が上位)
    2. is_progress_pass (= archive_role == "progress_pass"、 True が上位)
    3. not_score_bypass (= archive_role != "score_bypass"、 m.not_score_bypass property で導出)
    4. c_pass_depth (大が上位、 T064)
    5. mission_signed_margin (大が上位、 T062 Round 21 改訂後 SSOT)
    6. shadow_robustness_score (大が上位、 T064)
    7. recency (新 = run_history 内 index 小が上位、 pure 計算)
    8. log_pf_clip (大が上位、 T061)
    9. genome_id (昇順、 deterministic 完全保証 tie-break、 概念 Round 1 [C5])
    """
    is_mission = m.archive_role == "mission_pass"
    is_progress = m.archive_role == "progress_pass"
    run_id_index = run_history.index(m.run_id) if m.run_id in run_history else len(run_history)
    return (
        not is_mission,                    # False (= 0) が前 = 上位 = 残る
        not is_progress,
        not m.not_score_bypass,            # property で導出 (archive_role != "score_bypass")
        -m.c_pass_depth,
        -m.mission_signed_margin,
        -m.shadow_robustness_score,
        run_id_index,                      # 新が前 (run_history は新が前順) = 0 が上位
        -m.log_pf_clip,
        m.genome_id,                       # lex 末尾 tie-break (概念 Round 1 [C5])
    )


def archive_evict_ca(state: ArchiveState, *, target_size: int) -> ArchiveState:
    """CA capacity 超過時、 lex 末尾から削除して target_size 体に.

    recency_floor=12 best-effort (Round 1 [W4]): 直近 3 Run 由来 member が 12 未満なら
    AdmissionReport.recency_floor_unmet=True (caller 通知)、 eviction は強行.
    """
    ca_members = [m for m in state.members if m.archive_target == "CA"]
    if len(ca_members) <= target_size:
        return state
    sorted_ca = sorted(ca_members, key=lambda m: _ca_eviction_sort_key(m, run_history=state.run_history))
    survivors = sorted_ca[:target_size]
    survivor_ids = {m.genome_id for m in survivors}
    new_members = tuple(
        m for m in state.members
        if m.archive_target != "CA" or m.genome_id in survivor_ids
    )
    return replace(state, members=new_members)
```

### 9.2 DA eviction (lex 8 段)

```python
def _da_eviction_sort_key(
    m: ArchiveMember,
    *,
    run_history: Sequence[str],
) -> tuple:
    """DA lex eviction key (上位が残る、 末尾から削除).

    詳細 Round 2 [C2] 反映: progress_pass / not_score_bypass は archive_role から導出.

    1. novelty (大が上位)
    2. diversity_coverage (大が上位)
    3. is_progress_pass (= archive_role == "progress_pass"、 True が上位)
    4. not_score_bypass (m.not_score_bypass property、 True が上位)
    5. quality_floor_margin (大が上位)
    6. recency (新が上位)
    7. log_pf_clip (大が上位)
    8. genome_id (昇順、 deterministic tie-break、 概念 Round 1 [C5])
    """
    is_progress = m.archive_role == "progress_pass"
    run_id_index = run_history.index(m.run_id) if m.run_id in run_history else len(run_history)
    return (
        -m.novelty,
        -m.diversity_coverage,
        not is_progress,
        not m.not_score_bypass,
        -m.quality_floor_margin,
        run_id_index,
        -m.log_pf_clip,
        m.genome_id,
    )


def archive_evict_da(state: ArchiveState, *, target_size: int) -> ArchiveState:
    """DA capacity 超過時、 lex 末尾から削除. CA と同形."""
    da_members = [m for m in state.members if m.archive_target == "DA"]
    if len(da_members) <= target_size:
        return state
    sorted_da = sorted(da_members, key=lambda m: _da_eviction_sort_key(m, run_history=state.run_history))
    survivors = sorted_da[:target_size]
    survivor_ids = {m.genome_id for m in survivors}
    new_members = tuple(
        m for m in state.members
        if m.archive_target != "DA" or m.genome_id in survivor_ids
    )
    return replace(state, members=new_members)
```

### 9.3 recency_floor=12 best-effort (Round 1 [W4] 反映)

「直近 3 Run 由来は最低 12 体保持」 を保証ではなく **best-effort** とし、 不可時は warning + 続行:

```python
def _check_recency_floor_unmet(
    state: ArchiveState,
    *,
    run_history_floor: int = 12,
    last_n_runs: int = 3,
) -> bool:
    """直近 last_n_runs Run 由来 members が run_history_floor 未満なら True (warning)."""
    last_runs = set(state.run_history[:last_n_runs])
    recency_count = sum(1 for m in state.members if m.run_id in last_runs)
    return recency_count < run_history_floor
```

これにより epoch 序盤や archive 規模が小さい段階での「保証不可能」 状況を **AdmissionReport.recency_floor_unmet** で caller (T067) に通知する設計。 強制保持は T066 では実施しない (Round 1 [W4] best-effort 化)。 強制保持の必要性は smoke 後再校正候補 (synthesis § 15 残論点)。

---

## 10. ArchiveState / AdmissionReport dataclass (詳細 Round 2 [C4] / [W1] 反映)

```python
@dataclass(frozen=True)
class ArchiveState:
    """CA + DA を保持する状態オブジェクト (immutable).

    - members: 全 archive entries (CA + DA、 archive_target で識別)
    - dataset_epoch_id: T058 schema v2 必須 (epoch 跨ぎ汚染防止)
    - run_history: 直近 N Run の run_id 列 (recency 計算用、 maxlen=10、 直近順 / 新が前)

    **genome_id 一意制約 (詳細 Round 3 [C1] 反映)**:
    `members` 内の `m.genome_id` は重複禁止 (uniqueness invariant)。 archive_admit / eviction は
    この invariant を保つ責務を持つ。 同一 genome_id の再 admission は **upsert** (既存 member
    を新 ArchiveMember で置換) として実装、 eviction の `survivor_ids = {m.genome_id}` set 比較
    が安全に成立する。

    **設計意図 (詳細 Round 4 [Suggestion]): 同一 genome を CA / DA 同時保持しない。**
    Phase 1 では admission が CA only のため自動的に 1 個体 1 archive_target だが、 Phase 2 で
    T067 が DA warmstart 経路を実装する際も genome_id 一意制約を維持し、 同一 genome は
    CA か DA の片方にのみ保持する (両方保持しない) を不変条件とする。
    """
    members: tuple[ArchiveMember, ...]
    dataset_epoch_id: str
    run_history: tuple[str, ...]


@dataclass(frozen=True)
class AdmissionReport:
    """archive_admit の結果サマリ (observability)、 詳細 Round 2 [C4] / Round 3 [W1] field 補完.

    詳細 Round 2 [W1] 反映: `evicted_genome_ids` は「admission 全候補のうち new_state に
    含まれない genome_id」 を網羅 (= admit→即 evict も計上)。 旧 archive 既存 + 当 Run admit
    の合計から new_state.members を引いた差分.

    詳細 Round 3 [W1] 反映 (selected vs admitted カウント分離):
    - `selected_*`: candidate 階層別選抜段階の件数 (品質床通過 + bypass_k clamp 後、 hard
      constraints 適用 *前*、 § 8.2 step 4-5 時点)
    - `admitted_*`: hard constraints (per_run_max / pattern_max_share) 適用 *後* の実 admission 数
    """
    admitted_genome_ids: tuple[str, ...]
    evicted_genome_ids: tuple[str, ...]
    # selected (hard constraints 前、 candidate 階層選抜時点)
    n_selected_mission: int
    n_selected_progress: int
    n_selected_bypass: int
    # admitted (hard constraints 後、 実流入数)
    n_admitted_mission: int
    n_admitted_progress: int
    n_admitted_bypass: int
    mode: Literal["normal", "emergency"]
    hard_constraint_drops: int
    recency_floor_unmet: bool         # 詳細 Round 2 [C4]、 § 9.3 best-effort 通知
    dataset_epoch_reset: bool         # 詳細 Round 2 [C4]、 § 8.6 で True
```

---

## 11. 主要 dataclass / API シグネチャ (Phase 1 SSOT、 Round 1 [C1] / [C2] / [C5] 反映)

### 11.1 dataclass

```python
@dataclass(frozen=True)
class PushPullState: ...

@dataclass(frozen=True)
class ArchiveCandidate: ...     # admission 前 (caller 構築、 § 8.1.1)

@dataclass(frozen=True)
class ArchiveMember: ...        # admission 後 (T066 内部、 § 8.1.2)

@dataclass(frozen=True)
class ArchiveState: ...

@dataclass(frozen=True)
class InflowTargets: ...

@dataclass(frozen=True)
class AdmissionReport: ...      # § 4.2 仕様
```

### 11.2 関数シグネチャ (SSOT、 詳細設計はこれを引用元として完全同期)

```python
# CPPS FSM
def update_push_pull_state(
    prev: PushPullState,
    *,
    generation_no: int,
    feasible_ratio_ema: float,
    force_g: int,                    # caller 引数 (config 由来)、 gen=64 baseline → 44、 gen=48 fallback → 再校正
    theta_switch: float,             # caller 引数 (smoke 後再校正、 仮 0.40)
    consecutive_n: int = 3,
) -> PushPullState: ...

def compute_ca_da_capacities(
    pop_size: int,                   # 192 / 256 のみ正式 (Round 1 [W1] 統一)
    phase: Literal["push", "pull"],
) -> tuple[int, int]: ...

def compute_archive_capacities(
    pop_size: int,                   # 192 / 256 のみ正式
) -> tuple[int, int, int]: ...       # total, ca, da

# Survivor partition (sort_keys 不要、 T065 sort 順前提、 Round 1 [W3])
def partition_survivors_to_ca_da(
    survivor_indices: Sequence[int],
    *,
    phase: Literal["push", "pull"],
    pop_size: int,
) -> tuple[tuple[int, ...], tuple[int, ...]]: ...

# archive_role
def determine_archive_role(
    bc_result: BCEvaluationResult | None,
) -> Literal["mission_pass", "progress_pass", "score_bypass_candidate", "ineligible"]: ...

# Inflow
def compute_inflow_targets(
    pop_size: int,                   # 192 / 256 のみ正式
    n_mission: int,
    n_progress: int,
    *,
    mode: Literal["normal", "emergency"],
) -> InflowTargets: ...

# Seed: blake2b stable seed helper (deterministic、 T065 と同方式)
def make_archive_admission_seed(run_id: str, dataset_epoch_id: str) -> int: ...

# admission (CA only、 Round 1 [C3])
def archive_admit(
    archive_state: ArchiveState,
    candidates: Mapping[str, ArchiveCandidate],   # genome_id → candidate (Round 1 [C1] 統一)
    *,
    pop_size: int,
    mode: Literal["normal", "emergency"],
) -> tuple[ArchiveState, AdmissionReport]: ...

# eviction
def archive_evict_ca(state: ArchiveState, *, target_size: int) -> ArchiveState: ...
def archive_evict_da(state: ArchiveState, *, target_size: int) -> ArchiveState: ...

# Top-level entry per Run (admission + eviction + epoch reset + run_history 更新)
def update_archive_per_run(
    prev_archive: ArchiveState,
    candidates: Mapping[str, ArchiveCandidate],
    *,
    pop_size: int,
    mode: Literal["normal", "emergency"],
    new_dataset_epoch_id: str,        # Round 1 [C2] 必須化、 prev と不一致なら archive reset
    new_run_id: str,                   # run_history に追加
) -> tuple[ArchiveState, AdmissionReport]: ...
```

`ArchiveCandidate` は § 8.1.1、 `ArchiveMember` は § 8.1.2、 `ArchiveState` / `AdmissionReport` は § 10 / § 4.2 を参照。

---

## 12. テスト計画 (代表のみ、 詳細設計で完全リスト化)

### 12.1 PR DoD 必須

- `test_push_pull_one_way_transition_does_not_revert_to_push` (synthesis § 7.2 一方向)
- `test_archive_admit_preserves_dataset_epoch_id` (T058 schema v2)
- `test_archive_evict_ca_uses_round_21_lex_order_with_mission_signed_margin_at_position_5`
- `test_archive_admit_score_bypass_quality_floor_excludes_high_margin_inf`

### 12.2 PushPullState transitions

- `test_push_pull_state_initial_phase_is_push`
- `test_push_pull_state_consecutive_count_increments_on_threshold_met`
- `test_push_pull_state_resets_consecutive_count_on_threshold_failure`
- `test_push_pull_state_transitions_to_pull_after_consecutive_n_met`
- `test_push_pull_state_forces_pull_at_force_g`
- `test_push_pull_state_pull_phase_remains_pull_regardless_of_feasible_ratio`

### 12.3 CA/DA capacity

- `test_compute_ca_da_capacities_pop192_push_returns_84_108`
- `test_compute_ca_da_capacities_pop192_pull_returns_120_72`
- `test_compute_ca_da_capacities_pop256_push_returns_112_144`
- `test_compute_ca_da_capacities_pop256_pull_returns_160_96`
- `test_compute_ca_da_capacities_sum_equals_pop_size_via_round`
- `test_compute_archive_capacities_pop192_returns_120_72_48`
- `test_compute_archive_capacities_pop256_returns_160_96_64`
- `test_compute_archive_capacities_unsupported_pop_size_raises_value_error`

### 12.4 partition_survivors_to_ca_da

- `test_partition_survivors_top_ca_cap_to_ca_rest_to_da`
- `test_partition_survivors_respects_t065_sort_order`
- `test_partition_survivors_eligible_below_pop_size_returns_partial`
- `test_partition_survivors_exceeds_pop_size_raises_value_error`

### 12.5 determine_archive_role

- `test_determine_archive_role_none_returns_ineligible`
- `test_determine_archive_role_mission_pass_returns_mission_pass`
- `test_determine_archive_role_progress_pass_returns_progress_pass`
- `test_determine_archive_role_pareto_axis_usable_returns_score_bypass_candidate`
- `test_determine_archive_role_b_pooled_cf_none_returns_ineligible`
- `test_determine_archive_role_priority_mission_over_progress`

### 12.6 compute_inflow_targets

- `test_compute_inflow_targets_pop192_normal_returns_target_8_per_run_max_12`
- `test_compute_inflow_targets_pop256_normal_returns_target_10_per_run_max_16`
- `test_compute_inflow_targets_emergency_increases_target_and_bypass_max`
- `test_compute_inflow_targets_bypass_k_clamps_to_2_6_normal`
- `test_compute_inflow_targets_bypass_k_clamps_to_4_8_emergency`

### 12.7 archive_admit (3 層流入)

- `test_archive_admit_mission_pass_admitted_unconditionally_until_per_run_max`
- `test_archive_admit_progress_pass_sorted_by_worst_gap_ascending`
- `test_archive_admit_score_bypass_quality_floor_invariant_feasible`
- `test_archive_admit_score_bypass_quality_floor_margin_inf_p70`
- `test_archive_admit_per_run_max_trims_excess`
- `test_archive_admit_pattern_max_share_25_percent`
- `test_archive_admit_dataset_epoch_id_propagated`
- `test_archive_admit_upsert_existing_genome_id_replaces_member` (詳細 Round 3 [C1]、 genome_id 一意制約)
- `test_archive_admit_evicted_genome_ids_includes_admit_then_immediate_evict` (詳細 Round 3 [W1])
- `test_admission_report_distinguishes_selected_and_admitted_counts` (詳細 Round 3 [W1])

### 12.8 archive_evict_ca / archive_evict_da

- `test_archive_evict_ca_keeps_mission_pass_at_top`
- `test_archive_evict_ca_uses_mission_signed_margin_at_position_5`
- `test_archive_evict_ca_uses_shadow_robustness_at_position_6`
- `test_archive_evict_ca_genome_id_is_final_tiebreak` (詳細 Round 3 [C2]、 概念 Round 1 [C5] 9 段末尾)
- `test_archive_evict_ca_log_pf_clip_is_position_8_not_final` (旧 final → position 8 に降格、 末尾は genome_id)
- `test_archive_evict_da_keeps_high_novelty_at_top`
- `test_archive_evict_da_uses_diversity_coverage_at_position_2`
- `test_archive_evict_capacity_match_after_eviction`
- `test_archive_evict_recency_floor_reports_unmet_best_effort_when_below_12` (詳細 Round 4 [W2] best-effort 整合)

### 12.9 ArchiveState immutability

- `test_archive_state_members_is_tuple`
- `test_archive_state_run_history_is_tuple`
- `test_archive_state_replace_returns_new_instance`

### 12.10 update_archive_per_run (top-level)

- `test_update_archive_per_run_normal_mode_admits_and_evicts`
- `test_update_archive_per_run_emergency_mode_increases_bypass`
- `test_update_archive_per_run_dataset_epoch_id_changes_resets_archive` (epoch 切替)
- `test_update_archive_per_run_returns_admission_report_with_counts`

### 12.11 Determinism

- `test_archive_admit_deterministic_same_input_same_output`
- `test_archive_evict_lex_order_deterministic_with_ties`
- `test_partition_survivors_deterministic`

### 12.12 Edge cases

- `test_archive_admit_no_candidates_returns_empty_admission_report`
- `test_archive_admit_only_score_bypass_candidates_admits_bypass_k_at_most`
- `test_archive_evict_capacity_zero_returns_empty_archive` (運用上想定外、 ValueError か?)
- `test_partition_survivors_pull_phase_uses_120_72_for_pop192`

### 12.13 schema v2 / Round 21 整合性

- `test_archive_member_archive_role_matches_schema_v2_enum`
- `test_archive_member_dataset_epoch_id_required`
- `test_archive_evict_ca_position_5_field_name_is_mission_signed_margin_not_mission_margin` (Round 21 改訂後 SSOT)

総テスト数: 約 70 件 (13 sub-suite)

---

## 13. 残論点 / Decision Pending

### R1: theta_switch (push → pull 遷移閾値)

- 仮: 0.40 (zenigame 値踏襲、 INCONCLUSIVE)
- smoke 観測 DoD: feasible discovery curve から最適 θ を再校正
- synthesis § 15 残論点と整合

### R2: pattern_id / family_id の生成方針

- archive_member の pattern_id (= session/family pattern) と family_id (= warmstart cooldown) は genome から caller (T058 schema v2) で導出
- T066 では引数で受け取り、 hard constraints 適用のみ
- 詳細設計で field 名と契約を確定

### R3: novelty / diversity_coverage / quality_floor_margin の数値計算

- T066 では引数で受け取る (caller 責務)
- 計算本体は別 TODO (zenigame `archives.py:compute_d_genome` / `compute_d_slack` 流用候補)
- T067 / T070 / T071 のいずれかで実装、 T066 の interface のみ Phase 1 で確定

### R4: c_pass_depth の field 名と計算

- T064 BCEvaluationResult に `c_pass_depth: float` field が必要 (CA eviction #4)
- T064 詳細設計に明示されているか要確認、 不在なら T064 詳細設計の改訂 PR が必要
- 詳細設計で確定

### R5: emergency mode の判定権 (T067 担当)

- T067 で「mission_pass=0 が 3 連続 AND MA3(best_margin_inf) < MA6(best_margin_inf) - 0.05」 を計算し、 mode フラグを T066 に渡す
- T066 は受け取った mode で動作、 自身は判定しない
- INCONCLUSIVE: emergency 解除条件の T066 側ロジック (per_run_max が 1 run 限定で増えるか永続か)、 詳細設計で確定

### R6: archive_total の pop_size 制限

- 現状 pop_size=192/256 のみ正式サポート
- promotion 中の混在期 (192→256) の扱いは INCONCLUSIVE (smoke 後判定)

### R7: per_run_max=12 の階層別配分

- per_run_max=12 を超えた場合、 mission_pass / progress_pass / score_bypass のどの順で削るか
- 候補 A: mission_pass 優先保持、 score_bypass 削る → **採用 (synthesis § 8.2 の階層原則)**
- 候補 B: 一律削減
- § 8.3 `apply_hard_constraints` で確定 (Round 1 [W5] 反映)

### R8: synthesis § 8.2 「3 層流入」 の CA / DA 解釈 (synthesis Round 22 改訂候補)

- T066 Phase 1 の設計判断: 3 層流入 (mission_pass / progress_pass / score_bypass) は **CA admission のみ**
- DA admission は T067 warmstart 経路で別途扱う (§ 8.5)
- synthesis § 8.2 では「CA / DA の区別」 が明示されていない → fx 独自の解釈確定
- T067 PR と同時に synthesis § 8.2 改訂を検討 (synthesis Round 22 改訂候補): 「3 層流入は CA、 DA は warmstart 経路」 を明文化
- T066 単体では synthesis 改訂を必須としない (rationale.md で fx 独自設計判断として記録)

### R9: T064 follow-up (c_pass_depth field 追加) の Phase 0

- T066 Phase 1 PR 着地より先に T064 follow-up PR (BCEvaluationResult.c_pass_depth field 追加) が必要
- 計算式 (案、 詳細は T064 follow-up で確定):
  - `c_pass_depth = c_lite_n_pass_windows × 0.25 + (1.0 if c_result.mission_pass==PASS else 0.5 if PENDING else 0.0)`
  - 値域 [0, 1.75]、 大きいほど Stage C 通過の度合い大
- T066 詳細設計で c_pass_depth を消費する前に T064 follow-up が merge されている前提

---

## 14. Phase 2 申し送り (T067 / T070 / T071 と同時、 別 PR)

| # | ファイル / 箇所 | 担当 | 内容 |
|---|---|---|---|
| 1 | `src/alpha_factory/ga/__init__.py` で `from .cpps_archive import ...` | T067 | T065 と同時に export |
| 2 | `scripts/alpha_factory/run_ga.py` per-Run chain: T065 → **T066 update_push_pull_state + partition_survivors_to_ca_da** → archive_admit (Run 終了時) | T067 | 旧 archive 経路全廃 |
| 3 | `config/alpha_factory/default.yaml`: CPPS / Archive パラメータ追加 (theta_switch, force_g, archive_total, target_inflow, per_run_max, pattern_max_share, recency_floor) | T067 | T058 schema v2 準拠 |
| 4 | `src/alpha_factory/archive.py` 旧経路全廃、 T066 への dispatcher 化 | T067 | grep DoD: 旧 admission/eviction シンボル全消去 |
| 5 | (新規) `src/alpha_factory/observability/archive_metrics.py`: AdmissionReport / archive churn / pattern_share / front1 cardinality 観測 | T071 | T066 AdmissionReport を消費 |
| 6 | (新規) novelty / diversity_coverage / quality_floor_margin helper (zenigame `archives.py:compute_d_genome` / `compute_d_slack` 流用) | T067 / 別 TODO | T066 が引数で受け取る計算済値 |
| 7 | **T064 follow-up (Phase 0)**: BCEvaluationResult に `c_pass_depth: float` 追加 (T064 詳細設計改訂 PR + 実装 + テスト) | T064 follow-up | T066 詳細設計より **先に** 着地必須 (CA eviction #4 で必要)、 § 13 R9 |
| 8 | (新規) `tests/integration/test_ga_run_with_t066_archive.py`: per-Run chain integration test | T067 | T066 単体は Phase 1、 統合は Phase 2 |
| 9 | (新規) `docs/alpha_factory/ga-architecture.md` に CPPS / Two-Archive 仕様追加 | T067 | 旧 archive 経路全廃 + T066 仕様反映 |
| 10 | 旧 selection / archive 経路の削除対象シンボル一覧 (T065 申し送り #9 と統合) | T067 | grep で残存ゼロを DoD |

---

## 15. zenigame コード参考 (詳細設計時の流用判断材料)

| 機構 | zenigame ファイル | 行番号 | fx 流用方針 |
|---|---|---|---|
| Push/Pull FSM 状態構造 | `ga/nsga2/push_pull_fsm.py` | 36-61 (PushPullState) | dataclass 構造踏襲、 fx は immutable (frozen=True) |
| 切替条件評価 | `ga/nsga2/push_pull_fsm.py` | 100+ (compute_r_feas / compute_rank_kendall_tau) | r_feas は外部計算、 fx では caller 引数で受ける (T071 観測対象) |
| Two-Archive 状態構造 | `ga/nsga2/archives.py` | 42-63 (ArchiveState) | ID ベース identity を踏襲、 dataset_epoch_id 必須化 |
| CA lex eviction | `ga/nsga2/archives.py` | (select_ca_lex) | lex 8 段に拡張 (Round 21 改訂後) |
| DA max-min diversity | `ga/nsga2/archives.py` | (select_da_max_min) | DA は lex 7 段で簡素化、 max-min は novelty 計算 (caller 別) |
| 距離計算 (compute_d_genome / compute_d_slack) | `ga/nsga2/archives.py` | 90-150 | 別 TODO で fx 用に移植 (T066 では使わない) |
| ID ベース identity (Codex critical fix) | `ga/nsga2/archives.py` | (Codex Round 1 critical fix コメント) | fx でも genome_id を必須化 |

---

## 16. 完了判定 (概念設計 APPROVED 条件)

- [ ] § 1 で T066 責務範囲 (Phase 1 / Phase 2 分離 + 非責務 7 件) が明確
- [ ] § 2 で前提検証 (C4) が verified、 出典が明示
- [ ] § 5 で CPPS 2-state FSM の遷移仕様 (一方向 / 連続 N / 強制遷移) が確定
- [ ] § 6 で archive_role 判定 (4 状態: mission_pass / progress_pass / score_bypass_candidate / ineligible) が確定
- [ ] § 8 で 3 層流入 + 品質床 + ハード制約の admission 仕様が確定
- [ ] § 9 で CA / DA eviction lex 順序 (Round 21 改訂後 CA #5 = mission_signed_margin) が確定
- [ ] § 11 で API シグネチャが SSOT として揃う
- [ ] § 12 で PR DoD 必須テスト (4 件) が含まれる
- [ ] § 13 で残論点 9 件 (R1-R9) が Decision Pending タグ付き
- [ ] § 14 で Phase 2 申し送りが具体ファイル名 + 担当 TODO 名で 10 箇所
- [ ] Codex 概念レビューで CHANGES_APPLIED → APPROVED

---

## 17. synthesis Round 21 改訂後の整合性

本概念設計は synthesis Round 21 (2026-04-30 改訂) 後の確定値に基づく:

- archive CA eviction #5 = `mission_signed_margin` (T062 で実装済、 T066 で消費)
- mission_margin は BACKWARD COMPAT (T066 では参照しない)
- mission_inf_gap は T065 (Pareto f3) で消費、 T066 では使わない
- T064 BCEvaluationResult.shadow_robustness_score は CA #6 で消費

T066 詳細設計時に synthesis 章番号を再 grep で整合性確認、 Round 21 改訂内容を逸脱しないことを DoD で確定。
