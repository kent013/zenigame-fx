# PR1: source_stage 列の値入力 (orphan 解消、 行動不変)

## 背景

archive 51 列のうち以下 14 列が完全 orphan (count=0/362,124):
`sortino`, `calmar`, `bootstrap_ci_lower/upper`, `dsr`, `ii_lite_pass`, `fsp_runtime_mode/sampling_mode/factor_set/rolling_corr_60d/explained_variance/idio_ratio`, `archive_role`, `source_stage`.

T058 contract (= passive validation) で `genome_entry_schema_version` / `dataset_epoch_id` / `archive_role` / `source_stage` の 4 field を必須としているが、 後 2 つが orphan で contract 半実装。

30 ラウンド Codex 議論 (`tmp/codex-debate-impl-diff/` + `tmp/codex-debate-round2/`) で、 12 段統合 TODO の最初のステップ (= PR1) として「**archive_role / source_stage 値入力 (= 行動不変、 観測のみ)**」 が確定。

## スコープ縮小

元案では archive_role + source_stage の同時 populated だが、 archive_role は `cpps_archive.determine_archive_role(bc_result)` を呼ぶ必要があり、 bc_result は `stage_bc_evaluator.BCEvaluationResult` で **新規計算が必要** = 「行動変更」 になる。

PR1 の大原則「行動不変」 を厳守するため、 **archive_role は PR2 (Stage B persistence_score_shadow と同時)** に切り出し、 PR1 は **source_stage のみ実装**。

## 目的

- `source_stage` を `collect_stage_*` の進行に応じて populated にする
- archive Parquet 出力に列追加なし (= schema 不変)
- GA 評価フロー / fitness 計算 / Stage 通過判定に影響なし

## 期待効果

- T058 contract の半実装解消 (4 field のうち 3 つが populated に、 残る archive_role は PR2)
- 後続 PR (PR2: persistence_score_shadow / PR3: canonical_metrics shadow / PR4: legacy_pnl_smoke) の archive audit 基盤
- 個体の最終評価 stage が archive 上で観測可能になる (= 例: 「Stage A pass だが Stage B 未評価」 vs 「Stage A pass ∧ Stage B fail」 の区別)

## 非目的

- archive_role 値入力 (PR2 でやる)
- bc_result 計算 (PR2 以降)
- 既存 GA 動的への影響

## 実装方針

### 変更点

- `src/alpha_factory/archive.py:_mark_stage()` で row 内の private field `_MAX_STAGE_KEY` を更新するとき、 同時に `row["source_stage"]` を小文字 stage label ("a" / "b" / "c") で書き込む
- 既存挙動 (max stage tracking) は不変
- `_new_row()` で template 初期化時の `source_stage = None` も維持 (= 評価開始前は None、 collect_stage_a 以降で populated)

### schema コメントの整合性

`GENOMES_SCHEMA` の `source_stage` コメント:
> `source_stage: 個体評価の最終 stage ("a" / "b" / "c_lite" / "c")、 T063-T064 で書込`

"c_lite" は zenigame-fx には未実装の概念 (= zenigame の Stage C lite に相当)。 PR1 では "a" / "b" / "c" の 3 値のみ書き込む。 将来 c_lite が導入されたら値追加。

## テスト計画

`tests/alpha_factory/test_archive.py` に以下を追加:
- collect_stage_a 後の row["source_stage"] == "a"
- collect_stage_a → collect_stage_b の row["source_stage"] == "b"
- collect_stage_a → collect_stage_b → collect_stage_c の row["source_stage"] == "c"
- Stage A pass のみで終わった row の source_stage == "a"
- 既存テスト破壊なし確認 (= 全 test_archive 系 pass)

## 段階的展開

PR1 は単独 merge で runtime 影響なし。 PR2 以降の archive_role 値入力で T058 contract が完全実装される。

## 関連 TODO (12 段統合)

| 順 | TODO | 状態 |
|---|---|---|
| 1 | **PR1: source_stage 値入力** | **本 TODO** |
| 2 | PR2: archive_role + Stage B persistence_score_shadow | 未着手 |
| 3 | PR3: canonical_metrics / mission_inf_gap shadow | 未着手 |
| 4 | PR4: legacy_pnl_smoke opt-in + anti-luck guard | 未着手 |
| 5 | PR5: Stage B gate pfr_only opt-in A/B | 未着手 |
| 6+ | docs progress_criteria / out-of-cluster audit / grammar downweight 等 | 未着手 |

詳細議論ログ: `tmp/codex-debate-round2/` (Round 1-5、 各論点 5 ラウンド × 3 論点 = 15 セッション)
