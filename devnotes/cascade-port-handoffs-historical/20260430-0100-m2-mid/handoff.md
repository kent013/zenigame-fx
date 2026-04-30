# Selection Cascade Port — Session Handoff (M2 中間: T061-T062 完了時点)

**作成日時**: 2026-04-30 01:00 JST
**Session**: M2 (評価層) 中間、 T061 (canonical 5 engine) + T062 (mission_inf_gap engine) 設計完了直後
**前セッション**: M1 (基盤層 T058-T060) → 本セッション M2 中間 (T061-T062) → 次セッション M2 残 (T063-T064)
**次セッション**: T063 (Stage A evaluator) から続行予定

---

## 0. 現在地 (Where we are)

### 完了済 (M1 + M2 部分)

**M1 基盤層 (前セッション完了)**:
- T058 Schema v2 contract: 概念 4 round + 詳細 7 round で APPROVED + TODO 登録済
- T059 Epoch / Window Manager: 概念 5 round + 詳細 2 round で APPROVED + TODO 登録済
- T060 Partition + fold generator: 概念 2 round + 詳細 2 round で APPROVED + TODO 登録済

**M2 評価層 (本セッション完了)**:
- **T061 canonical 5 engine**: 概念 3 round (Round 3 で APPROVED) + 詳細 3 round (Round 3 で APPROVED) + TODO 登録済
- **T062 mission_inf_gap engine**: 概念 2 round (Round 2 で APPROVED) + 詳細 2 round (Round 2 で APPROVED 条件付き、 Warning 3 件吸収済) + TODO 登録済

### 未着手 (M2 残)

- **T063 Stage A evaluator**: 概念 + 詳細 設計、 TODO 登録
- **T064 Stage B + C-lite + C evaluator**: 概念 + 詳細 設計、 TODO 登録
- M2 完了報告

### 重要: 設計のみ完了、 実装はまだ

T061-T062 は **devnotes/ の概念設計 + 詳細設計のみ完了**、 src/ に新規コードは未実装。 既存 stage_gate.py / swim_lane.py / archive.py には**一切 touch していない**。

---

## 1. 全体ロードマップ

| Milestone | TODO 範囲 | 進捗 |
|---|---|---|
| **M1: 基盤層** | T058-T060 | ✅ **完了** (前セッション) |
| **M2: 評価層** | T061-T064 | 🔵 **半分完了** (本セッション T061-T062 / 次セッション T063-T064) |
| **M3: GA 中核** | T065-T066 (NSGA-II + CPPS 2-state) | 後続 |
| **M4: Loop+緊急** | T067-T069 | 後続 |
| **M5: Engine+DST+Observability** | T070-T072 | 後続 |
| **M6: Audit+Graduation+Smoke** | T073-T075 | 最終 |

---

## 2. 本セッションで確立した M2 部分 (実装はまだ)

### T061 canonical 5 engine

**設計**: `devnotes/20260429-2300-todo-T061-canonical-five-engine/`
**最終 review**: 詳細設計 Round 3 で APPROVED

**主要成果**:

- 数式 synthesis § 6 厳密準拠 (denom_floor=1e-6 厳密、 metric 別 floor 不採用)
- annual scale 換算は `compute_signed_slacks` 内で完結 (`SR_block * sqrt(N_BLOCKS_PER_YEAR=756)`)
- 入力契約 4 dataclass: `TradeRecord` (UTC 厳密 + business_day_index + invariant flags)、 `BarEquityPoint` / `BarEquitySeries` (sorted/no-dup/UTC-aware/finite invariant)、 `SessionBlockSummary`、 `CanonicalFiveThresholds`
- 出力契約: `CanonicalFiveResult` (5 raw + 5 signed slack + worst_gap + gate_pass + log_pf_clip + invariants + bucket_validator_version)
- 例外階層: `CanonicalMetricsInputError` (基底) + `TradeRecordInvalidError` / `BarEquityInvalidError` / `ThresholdsInvalidError` (派生)
- `InfeasibleReasonCode` StrEnum (strategic_* / input_* prefix で型強制)
- `business_day_universe` 入力で trade=0 block を含めて WR neutral 0.5 規約を有効化 (Round 1 [C1] 反映)
- no-raise 契約境界明文化: `__post_init__` 例外は caller raise、 `evaluate_canonical_five` 内部処理は no-raise (例外→reason code 変換)
- max_dd 値域 [0, 1] clip + ゼロ除算保護 (MAX_DD_DENOM_FLOOR=1e-12)
- HAC Bartlett q=5 + sigma2_LR_eps=1e-12 + low_sample_buckets 診断出力 (hard fail なし)
- C2 parallel-path grep 4 段階 DoD (直 import / 再エクスポート / alias / runtime 配線)

**Phase 2 申し送り (T063-T064 と同時、 別 PR)**:

| # | ファイル / 箇所 | 担当 |
|---|---|---|
| 1 | `stage_gate.py:evaluate_stage_a` を T061 + q_force ranking に置換 | T063 |
| 2 | `stage_gate.py:evaluate_stage_b` を 5 fold pooled + T061 worst aggregation に置換 | T064 |
| 3 | `stage_gate.py:evaluate_stage_c` を 12w + T061 + cross-pair shadow validation に置換 | T064 |
| 4 | (新規) `stage_gate.py:evaluate_stage_c_lite` を 3 disjoint × T061 worst で実装 | T064 |
| 5 | `cross_pair.py` の shadow validation を T061 + cross-pair pass 統合 | T064 |
| 6 | `config.py:StageGateConfig` に `win_rate_min` 追加、 旧 `stage_a/b/c.{*_sharpe_min, fold_*}` 全廃 | T063/T064 |
| 7 | `default.yaml` に `live_criteria.win_rate_min: 0.45` 追加 + 旧 stage_a/b/c 全廃 | T063/T064 |
| 8 | `swim_lane.py` の tier1 evaluator が新 stage_gate 経路 | T064 |
| 9 | `archive.py` の admission が CanonicalFiveResult を直接消費 | T067 (Loop closure) |

### T062 mission_inf_gap engine

**設計**: `devnotes/20260430-0030-todo-T062-mission-inf-gap-engine/`
**最終 review**: 詳細設計 Round 2 で APPROVED 条件付き (Warning 3 件 + Suggestion 3 件吸収済)

**主要成果**:

- synthesis § 6.4 厳密式: `mission_inf_gap = max(max(0, -slack_*4))` (win_rate 除外、 sharpe/pnl/dd/tc のみ)
- T062 → T061 の依存方向 (logical pipeline): `evaluate_mission_inf_gap(result: CanonicalFiveResult)` で T061 出力を直接消費
- **sentinel +inf を mission_inf_gap から撤廃** (詳細 Round 1 [C1]): mission_inf_gap は純粋 § 6.4 式 (有限値 [0, +inf])
- **新規 `constraint_violation: float` field**: NSGA-II constrained-domination (Deb 2000) 用 violation 量、 infeasible 個体間の序列化に使用 (有限スカラー)
- mission_margin (synthesis § 8.3 命名通り、 BACKWARD COMPAT) と mission_signed_margin (実用 SSOT、 archive CA #5 ordering 用) の二段構造
- synthesis § 8.3 矛盾認識 (`mission_margin = -mission_inf_gap` は数式と命名乖離) → `mission_signed_margin = min(slack_*4)` を新設
- NaN fail-fast 全経路化 (`is_feasible` 判定前に `_validate_slacks_dict`)
- `per_metric_shortfall: MappingProxyType[str, float]` (frozen dataclass の immutable 性保護)
- 4 代表ケース unit test (全達成 / 1 指標不足 / infeasible / NaN)
- C2 parallel-path grep 5 段階 DoD (alias import / relative import 追加)
- T065 申し送り: constrained-domination 疑似コード明記 (`is_feasible` 優先 → `constraint_violation` → 通常 Pareto)

**Phase 2 申し送り (T065-T067 と同時、 別 PR)**:

| # | ファイル / 箇所 | 担当 |
|---|---|---|
| 1 | (新規) `ga/nsga2_objectives.py`: f3 = MissionGapResult.mission_inf_gap | T065 |
| 2 | **(新規、 必須) `ga/constrained_domination.py`**: Deb 2000 constrained-domination | T065 |
| 3 | (新規) `ga/archive_eviction.py`: CA #5 = MissionGapResult.mission_signed_margin | T067 |
| 4 | `archive.py`: admission が is_feasible 安全網 | T067 |
| 5 | `swim_lane.py`: tier1 evaluator が GA 経由で MissionGapResult 消費 | T065 |
| 6 | `diagnostics_sidecar.py`: per_metric_shortfall を archive metadata 記録 | T067 |
| 7 | **synthesis 改訂 PR (別途)**: § 8.3 CA #5 を mission_signed_margin に、 § 15 残論点追記 | T064 PR 完了後 |

**暫定 SSOT 宣言**:
- `MissionGapResult.mission_signed_margin` は archive CA #5 ordering の **暫定 SSOT**
- synthesis § 8.3 改訂は T064 PR 完了後に別 PR

---

## 3. 次セッションの開始手順

### 3.1 まず読むもの (10 分)

1. **本ハンドオフ**: `devnotes/20260430-0100-cascade-port-handoff-m2-mid/handoff.md` (これ)
2. **synthesis 全体**: `devnotes/20260428-2300-cascade-port-debate/synthesis.md` (特に § 5 Stage 仕様、 § 7 NSGA-II + CPPS、 § 11 Graduation)
3. **TODO リスト**: `docs/alpha_factory/TODO.md` (T058-T062 が Open に登録済)
4. **M2 完了 2 TODO の詳細設計** (T063-T064 で参照): `devnotes/20260429-2300-todo-T061-*/detailed-design.md` + `devnotes/20260430-0030-todo-T062-*/detailed-design.md`
5. **前セッション handoff**: `devnotes/20260429-2245-cascade-port-handoff/handoff.md` (M1 完了時点の引き継ぎ)

### 3.2 T063 開始時のチェックリスト

T063 (Stage A evaluator) は **T061 canonical 5 engine + q_force 動的計算 + Stage A hard gate** を統合する評価器:

- 評価期間: 末尾 8w (recent proxy、 T060 Partition の stage_a Period)
- 評価指標: T061 canonical 5 worst gate_score (= 1 / (1 + worst_gap))
- 通過判定: 世代内 gate_score 降順で **top q_force%** が hard pass
- q_force 動的式: `clamp(0.15 + 0.15 × max(0, 0.10 - feasible_ratio_ema)/0.10, 0.15, 0.30)` (synthesis § 5.1)
- A→B 乖離時 q_force 自動引き上げ (上限 0.40、 戻し条件 corr >= 0.5、 0.02/Run、 synthesis § 8.7)
- A-pass のみ Stage B 進出、 A-fail は Pareto 圧計算からも排除

参考: synthesis § 5.1 (Stage A: hard gate + q_force) + § 8.7 (A→B 乖離監視)

### 3.3 T064 開始時のチェックリスト

T064 (Stage B/C-lite/C evaluator) は M2 最大の TODO:

- **Stage B**: 5 fold pooled (T060 FoldGenerator の出力) + T061 worst aggregation + invariant fold fail-fast
- **Stage C-lite**: 3 disjoint windows (T060 Partition の c_lite_1/2/3) × T061 worst → 15 セル + top 30% 強制通過 + progress_pass = 2/3 windows
- **Stage C**: 12w contiguous holdout (T060 stage_c) + spread stress (×1.5) + cross-pair shadow validation (5 通貨)
- A-pass only B-eval をログで検証 (A-fail が B/親選択へ入らない、 T918 smoke DoD)

参考: synthesis § 5.2 / § 5.3 / § 5.4 (Stage B/C-lite/C 仕様)

### 3.4 設計フローのテンプレート (T061-T062 と同じ)

```
1. devnotes/{YYYYMMDD-HHMM}-todo-T{NNN}-{topic}/ ディレクトリ作成
2. 概念設計 (conceptual-design.md) 作成
   - 背景・課題、 前提検証 C4、 改善アイデア、 期待効果、 実装方針、 スコープ外
   - synthesis 該当章の引用
3. Codex 概念レビュー (gpt-5.4 / medium、 zenigame-fx-codex-review)
   - APPROVED まで Round を回す (典型 2-5 round、 [Critical] 解消必須)
   - **Codex は file 読み込み拒否しがち**: 本文を貼り付けた Round 2 prompt で再投入
4. 詳細設計 (detailed-design.md) 作成
   - 施策一覧、 各施策の変更コード、 テスト計画、 DoD
   - Phase 1 / Phase 2 分離 (T061-T062 と同様)
5. Codex 詳細レビュー (gpt-5.3-codex / high)
   - APPROVED まで Round を回す
   - 同様に本文貼付前提
6. /zenigame-fx-todo-add で TODO 登録
   - uv run python scripts/alpha_factory/todo_manager.py add ...
```

### 3.5 重要な原則 (T063-T064 でも遵守)

- **Phase 1 / Phase 2 分離**: 各 TODO PR は単体テストのみで runtime 未組込、 既存 stage_gate / swim_lane / archive に touch しない
- **Phase 2 申し送りを設計時に明示**: 後段で同時更新が必要な箇所を漏らさず列挙
- **C2 parallel-path grep 確認**: T062 で 5 段階化済 (直 import / `import as` / relative / 再エクスポート / runtime シンボル)
- **C4 前提検証**: 設計書冒頭で `main@<commit>` 基準を明示、 verified を実コードで確認
- **synthesis 確定値を変えない**: 安易な変更禁止 (T062 で synthesis § 8.3 命名矛盾を発見した時は、 synthesis 改訂 PR を別途出す方針を採用)

### 3.6 T063-T064 が消費する依存先 module

- **T060 Partition**: `Period`, `Partition`, `Fold`, `PartitionGenerator`, `FoldGenerator` (Stage 評価期間の dataclass)
- **T061 canonical_metrics**: `evaluate_canonical_five`, `CanonicalFiveResult`, `CanonicalFiveThresholds`, `BarEquitySeries` (canonical 5 worst gate)
- **T062 mission_inf_gap**: `evaluate_mission_inf_gap`, `MissionGapResult` (mission_inf_gap、 ただし Stage A は使わない、 Stage B/C のみ内部 metadata で使用)

---

## 4. リソース / Contact 点

### 4.1 重要 docs / devnotes

| 場所 | 内容 |
|---|---|
| `devnotes/20260428-2300-cascade-port-debate/synthesis.md` | 設計上位文書 18 章 |
| `devnotes/20260429-1912-todo-T058-schema-v2-contract/` | T058 設計 |
| `devnotes/20260429-2113-todo-T059-epoch-window-manager/` | T059 設計 |
| `devnotes/20260429-2210-todo-T060-partition-fold-generator/` | T060 設計 |
| `devnotes/20260429-2245-cascade-port-handoff/handoff.md` | M1 完了時点 handoff |
| `devnotes/20260429-2300-todo-T061-canonical-five-engine/` | T061 設計 |
| `devnotes/20260430-0030-todo-T062-mission-inf-gap-engine/` | T062 設計 |
| `devnotes/20260430-0100-cascade-port-handoff-m2-mid/handoff.md` | 本ハンドオフ |
| `docs/alpha_factory/TODO.md` | TODO 一覧 (T058-T062 が Open に登録済) |
| `AGENTS.md` | プロジェクト全体規約 |

### 4.2 zenigame コード参照 (T063-T064 で参考)

| 機構 | zenigame ファイル |
|---|---|
| Stage A Adaptive Gate (T063 参考) | `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/stage_a_gate.py` |
| GA optimize loop (T063 q_force 動的計算 参考) | `.../ga/nsga2/optimize.py:950, 1006/1195` |
| canonical 5 worst gate_score (T063 参考、 T061 で実装済の旧版) | `.../evaluation/fitness.py:461` |
| Stage B fold-based 評価 (T064 参考) | (zenigame でも fold-based 評価あり、 詳細は zenigame の stage_gate.py) |
| Stage C cross-pair (T064 参考) | (cross_pair.py 同等、 fx 側にも基本 module あり: `src/alpha_factory/cross_pair.py`) |

### 4.3 Codex 呼び出し方 (T061-T062 と同じ)

- 概念レビュー: `gpt-5.4` / `medium`、 label `conceptual-review`
- 詳細レビュー: `gpt-5.3-codex` / `high`、 label `detailed-review`
- skill: `zenigame-fx-codex-review`

例 (Round 1 + 続く Round):

```bash
# Round 1
scripts/codex exec --sandbox read-only -m gpt-5.4 -c 'model_reasoning_effort="medium"' --json \
  -o devnotes/{dir}/conceptual-review-round-1.md \
  - < devnotes/{dir}/.codex-prompt-conceptual-review.md \
  > devnotes/{dir}/.codex-session-conceptual-review.jsonl

SESSION_ID=$(head -1 devnotes/{dir}/.codex-session-conceptual-review.jsonl | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['thread_id'])")
echo "$SESSION_ID" > devnotes/{dir}/.codex-session-conceptual-id

# Round N (N>=2)
SESSION_ID=$(cat devnotes/{dir}/.codex-session-conceptual-id)
scripts/codex exec resume "$SESSION_ID" --json \
  -o devnotes/{dir}/conceptual-review-round-{N}.md \
  - < devnotes/{dir}/.codex-prompt-conceptual-review-round-{N}.md \
  >> devnotes/{dir}/.codex-session-conceptual-review.jsonl
```

**重要 (本セッションで判明)**: Codex は `--sandbox read-only` でも file read を「コマンド実行禁止」 と誤解釈して拒否することがある。 Round 2 以降のプロンプトに **本文を inline で貼り付ける** のが確実。

### 4.4 TODO 登録方法

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

## 5. 進捗状況サマリー

```
synthesis  ████████████████████ 100% (Codex × 20 round で確定)
M1 (基盤)  ████████████████████ 100% (T058-T060 設計完了 + TODO 登録)
M2 (評価)  ██████████░░░░░░░░░░  50% (T061-T062 設計完了 + TODO 登録、 T063-T064 未着手)
M3 (GA)    ░░░░░░░░░░░░░░░░░░░░   0% (T065-T066 未着手)
M4 (Loop)  ░░░░░░░░░░░░░░░░░░░░   0% (T067-T069 未着手)
M5 (Eng)   ░░░░░░░░░░░░░░░░░░░░   0% (T070-T072 未着手)
M6 (Fin)   ░░░░░░░░░░░░░░░░░░░░   0% (T073-T075 未着手)
```

**全体進捗**: 設計 18 件中 5 件完了 (27.8%)、 実装は 0%

---

## 6. 次セッションの最初の指示テンプレート

ユーザが次セッションで以下のように指示すると即座に再開可能:

> 引き継ぎは `devnotes/20260430-0100-cascade-port-handoff-m2-mid/handoff.md` 読んで。 T063 (Stage A evaluator) から続行してください。 同じ flow (概念設計 → Codex レビュー APPROVED → 詳細設計 → Codex レビュー APPROVED → TODO 登録) で。

---

## 補足: 本セッションで学んだこと (T063-T064 で適用)

- **Codex の file read 拒否**: `--sandbox read-only` でも「コマンド実行禁止」 解釈で file read を拒否する。 Round 2 以降のプロンプトに本文を inline で貼り付けるのが確実 (本セッションで T061-T062 共に発生)
- **synthesis の semantic 矛盾を発見した場合**: synthesis 確定値を変えず、 詳細設計で「暫定 SSOT 宣言」 + 「synthesis 改訂 PR を後段別途」 の方針 (T062 § 8.3 で初適用)
- **Codex 詳細レビューの厳しさ**: T061 詳細 Round 1 で 3 Critical + 5 Warning + 3 Suggestion、 T062 詳細 Round 1 で 2 Critical + 4 Warning + 4 Suggestion。 数式 / 例外契約 / 値域 / 学術引用 (full citation + DOI) が頻出指摘
- **Phase 2 申し送り表は具体ファイル列挙が肝**: 「申し送り」 という曖昧記述だと Phase 2 で漏れが発生 (T060 で経験)。 ファイル名 + 行番号 + 担当 TODO を明記する
- **InfeasibleReasonCode 等の StrEnum 化**: 文字列直書きを避け、 prefix 規約 (strategic_* / input_*) を型で強制すると downstream の誤読を防げる
- **immutable mapping**: frozen dataclass でも dict は外部から変更可能、 `MappingProxyType` wrap が必要 (T062 で発生)
- **NaN fail-fast の全経路化**: 早期 return 経路で検証を skip すると上流破損をマスク。 全経路で同じ検証を通す (T062 で指摘)

これらの教訓は次セッションでも継続適用する。
