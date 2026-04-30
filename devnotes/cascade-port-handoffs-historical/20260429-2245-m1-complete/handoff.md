# Selection Cascade Port — Session Handoff (M1 完了時点)

**作成日時**: 2026-04-29 22:45 JST
**Session**: M1 (基盤層 T058-T060 設計フェーズ) 完了直後
**次セッション**: M2 (評価層 T061-T064 設計フェーズ) 開始予定

---

## 0. 現在地 (Where we are)

### 完了済 (M1)
- **synthesis 議論**: Codex × 20 round (Round 1-10 旧議論は前提誤りで `historical/old-rounds-1-10/` 隔離、 Round 11-20 が確定議論)、 18 章構成の最終確定文書
- **T058 Schema v2 contract**: 概念設計 4 round + 詳細設計 7 round で APPROVED + TODO 登録済
- **T059 Epoch / Window Manager**: 概念 5 round + 詳細 2 round で APPROVED + TODO 登録済
- **T060 Partition + fold generator**: 概念 2 round + 詳細 2 round で APPROVED + TODO 登録済
- **M1 進捗報告**: 出力済

### 未着手 (M2 以降)
- T061 canonical 5 engine
- T062 mission_inf_gap engine
- T063 Stage A evaluator
- T064 Stage B + C-lite + C evaluator
- M2 進捗報告
- T065-T075 (Milestone M3-M6)

### 重要: 設計のみ完了、 実装はまだ
すべて **devnotes/ の概念設計 + 詳細設計のみ完了**、 src/ に新規コードは未実装。 旧 walk_forward / stage_gate / preflight には**一切 touch していない**。

---

## 1. 全体ロードマップ

| Milestone | TODO 範囲 | 進捗 |
|---|---|---|
| **M1: 基盤層** | T058-T060 (Schema v2 / EpochManager / Partition+Fold) | ✅ **完了** (本セッション) |
| **M2: 評価層** | T061-T064 (canonical 5 / mission_inf_gap / Stage A/B/C-lite/C) | 次セッション |
| **M3: GA 中核** | T065-T066 (NSGA-II + CPPS 2-state) | 後続 |
| **M4: Loop+緊急** | T067-T069 (Archive / Warmstart / Calibrate / Emergency) | 後続 |
| **M5: Engine+DST+Observability** | T070-T072 (backtest engine / DST / 監視) | 後続 |
| **M6: Audit+Graduation+Smoke** | T073-T075 (DSR / graduation lane / big-bang smoke) | 最終 |

---

## 2. 設計の核 (synthesis 18 章ベース)

設計上位文書: **`devnotes/20260428-2300-cascade-port-debate/synthesis.md`**
(Codex Round 11-20 で全構成合意確定、 異論なし)

### 2.1 確定構成

```
[A 計算リソース]
  lane=1 (EUR_JPY anchor) / pop=192 baseline / 256 promotion / gen=64 / max_workers 自動
  shadow 5 通貨 = validation のみ / graduation lane = Phase 4 で batch 起動

[B Dataset / Partition]
  24m primary / epoch-rolling stride=4w (28 日固定) / max_runs/epoch=6
  partition: [B 62w][A 8w][emb 1w][C-lite 6w×3+emb 1w×3][C 12w] = 104w
  Stage B fold: train 36w + emb 1w + test 5w + step 5w → 5 folds
  Stage A は時間軸では B より後 (recent proxy)、 cascade 順 (A→B→C-lite→C) は維持

[C Metric (gate / search 完全分離)]
  canonical 5 (gate worst): SR_session_worst (HAC Bartlett q=5)、 net_pnl_after_cost、 max_dd、 trade_count、 session_block_win_rate_worst
  Pareto 3 軸 (search): max net_pnl, min max_dd, min mission_inf_gap (live_criteria 4 指標 inf-norm)
  invariant fail-fast 2 種: session_close_drop > 0、 negative_equity_drop_open > 0
  spread_consumption_ratio = tie-break + monitor (gate 圏外)
  cross-pair shadow = validation + archive metadata
  log_pf_clip(-2, 2) = archive lexicographic 末端 tie-break

[D GA 構造]
  NSGA-II + 純 CPPS 2-state (push/pull、 fallback flag なし)
  選抜: rank + 標準 crowding (3 軸正規化) + deterministic tie-break (genome_hash)
  主選抜評価値 = Stage B pooled (A-fail は除外)
  CA/DA 進化母集団 動的比率 (push 84/108 → pull 120/72 for pop=192)
  archive epoch aware (prev_epoch 20% via Stage A quick recheck、 epoch_age>=2 purge)
  exec_floor 不採用 (objective taxonomy で対象消失)

[E Loop Closure]
  archive=120 (CA 72 / DA 48)、 inflow=8/per_run_max=12、 warmstart=20% ramp
  3 層流入 (mission_pass + progress_pass + score_bypass)
  bypass = Stage B 評価済 + 品質床 (invariant_feasible + margin_inf percentile <= 70)
  emergency = warmstart 20% → 25% (1 run のみ)
  calibrate-gate 凍結窓 3 Run + Δ<=0.03

[F P2 Regime]
  session_bucket 3 (Tokyo/London/NY) 固定、 6 bucket 不採用 (C-lite で C7 違反)
  spectral weight = support-aware clip [0.25, 0.45]、 development span のみ
  vol/aux/period_bucket = archive metadata
  regime_pass_pattern = archive diversity 軸 (P2 禁止、 outcome-derived collider)

[G Cross-cutting]
  GA selection 圧 = Stage A proxy / archive admission = Stage B pooled (分離)
  dataset_epoch_id 全経路必須 (T058 で確立)
  A→B 乖離は warn-only + q_force 自動引き上げ (上限 0.40)
  schema lint で fail-closed (T067 切替後)
```

### 2.2 5 設計原則

- **原則 0**: Lookahead bias / Leakage 徹底排除
- **原則 1**: 絶対閾値は破綻排除のみ、 選抜圧は相対 ranking
- **原則 2**: 難易度次元 (session_bucket) を明示的に正規化
- **原則 3**: cycle 全滅を防ぐ強制流入 / 通過
- **原則 4**: canonical 5 worst aggregation で pass/fail (mean/RMS/spectral/weighted は tie-break 限定)

### 2.3 ザク導入方針

- 後方互換性・段階導入は不要、 big-bang
- これまでの実装はベースラインにすらしない、 **本設計が新ベースライン**
- NSGA-II と CPPS の切り替え機構 (fallback flag) は不要、 純 CPPS のみ
- 不要なものは削除

---

## 3. M1 で確立した基盤 (実装はまだ)

### T058 Schema v2 contract
**設計**: `devnotes/20260429-1912-todo-T058-schema-v2-contract/`
**最終 review**: 詳細設計 Round 7 で APPROVED

**主要成果**:
- 4 artifact 別 contract: `GENOME_ENTRY_CONTRACT_V2` / `CALIBRATE_HISTORY_CONTRACT_V2` / `RUN_REPORT_CONTRACT_V2` / `DIAGNOSTICS_CONTRACT_V2`
- 共通必須 field: `dataset_epoch_id` (grammar `^[a-z0-9_]+$`)
- enforcement_mode = `LOG_ONLY` (T058) → `FAIL_CLOSED` (T067 で切替)
- `ValidationResult` 返却型統一
- `RunContext` dataclass 受け皿 (主要 3 component に optional 注入、 全 component 必須化は T067)
- `cascade_contract_version: int = 2` (既存 `schema_version: "1.1"` (string) と分離)
- 9 経路 Tier 1 lint + 9 経路 Tier 2 引用 (合計 18 経路)
- `--reset-epoch-state` は T059 担当、 schema 側は `enforcement_mode` 切替のみ

**Phase 2 申し送り (T067 で実施)**:
- v1 archive 排除 (FAIL_CLOSED 切替)
- 全 component への RunContext 必須注入完成

### T059 Epoch / Window Manager
**設計**: `devnotes/20260429-2113-todo-T059-epoch-window-manager/`
**最終 review**: 詳細設計 Round 2 で APPROVED

**主要成果**:
- `EpochWindow` (start, end のみ identity、 UTC 00:00 固定契約)
- `EpochManager`:
  - fcntl file lock + atomic reservation (LOCK_TIMEOUT_SECONDS=10)
  - `make_epoch_id = epoch_{start_yyyymmdd}_{end_yyyymmdd}` (canonical window identity)
  - `slots_consumed_in_epoch` 単調増加カウンタ (status と分離、 max=6 cap 強制)
  - `run_records: {epoch_index: {run_id: record}}` 入れ子辞書 (旧 epoch の running run も保持)
  - `latest_data_end_floor` data horizon gate (MARGIN_DAYS=7)
  - `compatibility_fingerprint` (instrument / window_length / stride / max_runs / anchor_origin / epoch_id_format_version / state_schema_version)
- 6 例外: `EpochCapExceeded` / `EpochStateIncompatible` / `EpochStateCorruptError` / `EpochDatasetMismatch` / `EpochLockTimeout` / `DuplicateRunIdError`
- run_id は**全 epoch で一意**必須 (mark_run_status の対象一意性保証)
- state 破損時 fail-closed (`--reset-epoch-state --yes-reset-epoch-state --reason "..."` 3-flag 必須 + `audit_log.jsonl` 追記、 破損 state でも reset 完遂)

**Phase 1 (T059 PR) スコープ**: EpochManager 単体テストのみ
**Phase 2 申し送り**: 24m 切替 (`default.yaml` の `dataset.start/end`) + run_ga.py 組込 + RSS gate (24m 化前に `max_workers=1/2` で 3 GB/worker 実測必須)

### T060 Partition + fold generator
**設計**: `devnotes/20260429-2210-todo-T060-partition-fold-generator/`
**最終 review**: 詳細設計 Round 2 で APPROVED

**主要成果**:
- `PeriodLabel` StrEnum (string literal 依存回避)
- `Period` (UTC 専用、 `utcoffset() == timedelta(0)` 厳密、 半開区間 [start, end))
- `Partition` (24m=104w → 10 領域、 timedelta 厳密一致 + cursor 例外化)
- `Fold` (5 folds: train 36w + emb 1w + test 5w + step 5w、 末端 fold 例外化)
- `PartitionGenerator.generate(window) -> Partition` (deterministic)
- `FoldGenerator.generate(stage_b) -> tuple[Fold, ...]` (5 folds)
- 例外: `PartitionMismatchError` / `FoldMismatchError`

**Phase 1 (T060 PR) スコープ**: partition.py + test_partition.py のみ
**Phase 2 申し送り (9 箇所同時更新 + 運用 2 件、 T061-T064 と同時)**:
- `walk_forward.py` の `make_wf_folds` / `compute_max_folds` / `wf_min_unique_dates` を全廃 or thin wrapper 化
- `stage_gate.py:StageGateConfig` から `stage_b_window_months` / `wf_*_days` 削除
- `stage_gate.py:evaluate_stage_b` の `bars_18m` 引数廃止
- `swim_lane.py:465` の `compute_max_folds` 呼出を新 FoldGenerator に
- `run_ga.py:1260` の preflight `wf_min_unique_dates` を新仕様に
- `default.yaml: stage_gate.stage_b.{window_months, wf_*}` を全廃、 新 (固定 5 folds) 反映
- `config.py:StageGateConfig` の Stage B 関連 field 再定義
- `docs/alpha_factory/stage-gates.md` の Stage B 仕様を新 Partition / Fold ベースに
- `calibrate_state.py:74` の `stage_b_window_months` 参照を新 Partition ベースに
- `aux_preflight.py:52, 189` の `stage_b_window_months` 参照と `wf_*` 経路を新 Partition / Fold ベースに
- `inspect_stage_b_folds.py:83` の `wf_*` / fold logic を新 FoldGenerator に
- `tests/alpha_factory/test_config.py:333` の `wf_*_days` / `stage_b_window_months` test を新仕様に

---

## 4. 次セッションの開始手順

### 4.1 まず読むもの (5 分)

1. **本ハンドオフ**: `devnotes/20260429-2245-cascade-port-handoff/handoff.md` (これ)
2. **synthesis 全体**: `devnotes/20260428-2300-cascade-port-debate/synthesis.md` (18 章、 特に § 4-8 が M2 に必要)
3. **TODO リスト**: `docs/alpha_factory/TODO.md` (T058-T060 が Open に登録済)
4. **M1 完了 3 TODO の詳細設計** (M2 で参照): `devnotes/20260429-{1912/2113/2210}-todo-T{058,059,060}-*/detailed-design.md`

### 4.2 T061 開始時のチェックリスト

T061 (canonical 5 engine) は Codex 議論時に頻出した複数 helper を 1 module で実装:
- HAC Bartlett q=5 補正 Sharpe
- session block PnL aggregation (1 営業日 × 1 bucket = 8h)
- session_block_win_rate_worst (trade=0 → 0.5 neutral、 3 bucket worst)
- slack_to_range (trade_count [L, U] range)
- log_pf_clip (-2, 2)

参考: synthesis § 6 (canonical 5 + Pareto 3 数式仕様)

### 4.3 設計フローのテンプレート (各 TODO 共通)

```
1. devnotes/{YYYYMMDD-HHMM}-todo-T{NNN}-{topic}/ ディレクトリ作成
2. 概念設計 (conceptual-design.md) 作成
   - 背景・課題、 前提検証 C4、 改善アイデア、 期待効果、 実装方針、 スコープ外
   - synthesis 該当章の引用
3. Codex 概念レビュー (gpt-5.4 / medium、 zenigame-fx-codex-review)
   - APPROVED まで Round を回す (典型 2-5 round、 [Critical] 解消必須)
4. 詳細設計 (detailed-design.md) 作成
   - 施策一覧、 各施策の変更コード、 テスト計画、 DoD
   - Phase 1 / Phase 2 分離 (T060 と同様)
5. Codex 詳細レビュー (gpt-5.3-codex / high)
   - APPROVED まで Round を回す
6. /zenigame-fx-todo-add で TODO 登録
   - uv run python scripts/alpha_factory/todo_manager.py add ...
```

### 4.4 重要な原則 (M2 でも遵守)

- **Phase 1 / Phase 2 分離**: T058-T060 と同じく、 各 TODO PR は単体テストのみで runtime 未組込、 既存 walk_forward / stage_gate / preflight に touch しない
- **Phase 2 申し送りを設計時に明示**: 後段で同時更新が必要な箇所を漏らさず列挙 (Codex も指摘した重要原則)
- **C2 parallel-path grep 確認**: `grep -rn "from src.alpha_factory.{new_module}" scripts/ src/` が自身と test 以外で hit しないことを DoD に
- **C4 前提検証**: 設計書の冒頭で `main@<commit>` 基準を明示、 verified を実コードで確認
- **dataset_epoch_id 整合**: T058 の lint と T059 の生成と T060 の Partition (epoch_window 経由) を全 stage で揃える
- **synthesis 確定値を変えない**: pop/gen/window/fold 数等は synthesis で確定、 安易な変更禁止 (思想ベースで議論し直すなら別)

### 4.5 やってはいけないこと (synthesis § 13 から)

- gate 指標と search 指標を同じランキングで混ぜる
- shadow pair を selection objective に入れる
- epoch_id なしデータを archive/history に保存する
- A-only proxy 個体を bypass で archive に入れる
- 緊急時に prev_epoch 制約を緩めて帳尻を合わせる
- C-lite/B の sample 不足状態で bucket 数を増やす
- smoke 前に値チューニングで辻褄合わせをする
- gen=48 fallback 時に FSM 再校正を skip する
- pop=256 promotion 時に E 系 hyper-parameter scaling を忘れる

---

## 5. リソース / Contact 点

### 5.1 重要 docs / devnotes

| 場所 | 内容 |
|---|---|
| `devnotes/20260428-2300-cascade-port-debate/synthesis.md` | 設計上位文書 18 章 |
| `devnotes/20260428-2300-cascade-port-debate/round-{11-20}.md` | Codex 議論ログ |
| `devnotes/20260428-2300-cascade-port-debate/historical/old-rounds-1-10/` | 旧議論 (前提誤りで隔離、 参考のみ) |
| `devnotes/20260429-1912-todo-T058-schema-v2-contract/` | T058 設計 |
| `devnotes/20260429-2113-todo-T059-epoch-window-manager/` | T059 設計 |
| `devnotes/20260429-2210-todo-T060-partition-fold-generator/` | T060 設計 |
| `devnotes/20260429-2245-cascade-port-handoff/handoff.md` | 本ハンドオフ |
| `docs/alpha_factory/TODO.md` | TODO 一覧 (T058-T060 が Open に登録済) |
| `AGENTS.md` | プロジェクト全体規約 |

### 5.2 zenigame コード参照 (synthesis § 14)

zenigame 側の実装ファイルを参考に T061 以降を設計する場合:

| 機構 | zenigame ファイル |
|---|---|
| Stage A Adaptive Gate | `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/stage_a_gate.py` |
| GA optimize loop | `.../ga/nsga2/optimize.py:950, 1006/1195, 2125/2141` |
| canonical 5 worst gate_score | `.../evaluation/fitness.py:461` |
| live_criteria_gap helper | `.../evaluation/live_criteria_gap.py` |
| Push/Pull FSM (2-state) | `.../ga/nsga2/push_pull_fsm.py:45` |
| CA/DA Two-Archive | `.../ga/nsga2/archives.py` |
| Sieve filter (4 層流入) | `.../alpha_sieve/filter.py` |
| Archive admission/eviction | `.../alpha_sieve/archive_updater.py:123` |
| DSR | `.../runner/_dsr.py:126` |
| determinism | `.../ga/nsga2/core.py:114, 1026/1085` |

注意: zenigame は universe=64 銘柄前提なので、 fx 単一通貨ペアでは読み替えが必要 (synthesis § 13 参照)。

### 5.3 Codex 呼び出し方

- 概念設計レビュー: `gpt-5.4` / `medium`、 label `conceptual-review`
- 詳細設計レビュー: `gpt-5.3-codex` / `high`、 label `detailed-review` (or `design-review`)
- skill: `zenigame-fx-codex-review` (使命・禁止事項自動挿入、 セッションモードあり)

例:
```bash
scripts/codex exec --sandbox read-only -m gpt-5.4 -c 'model_reasoning_effort="medium"' --json \
  -o devnotes/{dir}/conceptual-review-round-1.md \
  - < devnotes/{dir}/.codex-prompt-conceptual-review.md \
  > devnotes/{dir}/.codex-session-conceptual-review.jsonl
```

### 5.4 TODO 登録方法

```bash
uv run python scripts/alpha_factory/todo_manager.py add \
  --id "T0XX" \
  --title "T0XX-{topic}" \
  --theme "{stage-gate|infrastructure|ga-architecture|...}" \
  --summary "..." \
  --priority "Critical" \
  --mode "incremental" \
  --design-link "[設計](devnotes/{dir}/)" \
  --added-at "$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M')"
```

---

## 6. 進捗状況サマリー

```
synthesis  ████████████████████ 100% (Codex × 20 round で確定)
M1 (基盤)  ████████████████████ 100% (T058-T060 設計完了 + TODO 登録)
M2 (評価)  ░░░░░░░░░░░░░░░░░░░░   0% (T061-T064 未着手)
M3 (GA)    ░░░░░░░░░░░░░░░░░░░░   0% (T065-T066 未着手)
M4 (Loop)  ░░░░░░░░░░░░░░░░░░░░   0% (T067-T069 未着手)
M5 (Eng)   ░░░░░░░░░░░░░░░░░░░░   0% (T070-T072 未着手)
M6 (Fin)   ░░░░░░░░░░░░░░░░░░░░   0% (T073-T075 未着手)
```

**全体進捗**: 設計 18 件中 3 件完了 (16.7%)、 実装は 0%

---

## 7. 次セッションの最初の指示テンプレート

ユーザが次セッションで以下のように指示すると即座に再開可能:

> 引き継ぎは `devnotes/20260429-2245-cascade-port-handoff/handoff.md` 読んで。 T061 (canonical 5 engine) から続行してください。 同じ flow (概念設計 → Codex レビュー APPROVED → 詳細設計 → Codex レビュー APPROVED → TODO 登録) で。

---

## 補足: 議論の重要な転換点 (M1 で学んだこと)

- **config default を hard constraint と扱う誤りを 2 回繰り返した** (Round 11 直前): pop=40, gen=15, max_workers=2 を制約と思い込んで設計した結果、 軽量 CPPS / pop=96 等の妥協案が出た。 ユーザ指摘で「default は config 値、 hard constraint ではない」 と認識し直して pop=192/gen=64 に転換 → CPPS フルポート可能に。 **次セッションでも config default を勝手に固定値扱いしない**
- **canonical 5 第 5 指標**: profit_factor 案 → win_rate 戻し → graduation lane Phase 4 で意味復活、 ただし **session_block_win_rate に semantic 上げ**で確定 (synthesis § 13 で win_rate と表記、 実装は session_block_win_rate)
- **fold 数**: 6 folds と書いた箇所が多数あったが、 実際は 62w / 5w step で **5 folds**。 文書整合性チェック必須
- **Phase 1 / Phase 2 分離**: T060 で初めて明示、 各 PR を runtime 未組込で merge 可能に (Codex 推奨)
- **C2 parallel-path grep 確認**: 旧経路に新定数を逆流させない、 新経路を runtime に配線しない、 を grep で機械的に確認 (Round 1 で Codex 提案)

これらの教訓は次セッションでも継続適用する。
