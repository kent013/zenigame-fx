# 概念設計: Stage B 統計可観測性ハード契約 (Metric Completeness Gate)

## 参照済み一覧 (Design-first / C1)

- `docs/alpha_factory/stage-gates.md` (Stage B reason code 語彙、metric envelope)
- `docs/alpha_factory/statistics.md` (`fold_sign_ratio` 既存定義 = 隣接 fold 間 Sharpe 符号反転比率)
- `docs/alpha_factory/concepts/genome-archive-schema.md` (archive 列定義 SSOT)
- `docs/alpha_factory/swim-lane.md` (LaneManager の Stage 実行フロー)
- `devnotes/20260423-1540-stage-gate-implementation/` (Stage A/B/C 初期実装の前提)
- `devnotes/20260423-2324-run-ga-full-rewrite/` (run_ga / dataset bundle 契約)
- `src/alpha_factory/stage_gate.py:348-471` (現行 `evaluate_stage_b`)
- `src/alpha_factory/walk_forward.py:75-114` (`make_wf_folds` sufficiency 契約 = `fold_len = train_days + embargo_days + test_days` 観測日)
- `src/alpha_factory/swim_lane.py:483-503` (`LaneManager` 内の Stage B 実行 + archive.collect_stage_b 経路)
- `src/alpha_factory/archive.py:80-138, 348-403` (現行 archive schema と Stage B 集約)
- `src/alpha_factory/statistics.py:234` (`fold_sign_ratio` 実装)
- `scripts/alpha_factory/generate_run_report.py:406-415` (run-report `fold_sign_ratio / dsr` 表示)
- `scripts/alpha_factory/run_ga.py:250-330, 600-755` (`bars_stage_b` 供給経路 / `Tier1Lane.bars_18m`)
- git log: T014 (`0f7aa06`), T015 (`39619ec`), T018 (`efaf365`), T021 (`ad925d0`), T027 (`7f2894e`)

## 前提表 (C4 Verified/Unverified)

| # | 前提 | 状態 | 参照 |
|---|------|------|------|
| 1 | `evaluate_stage_b` は `no_folds` / `insufficient_folds` / `all_folds_unavailable` で fail-closed する | Verified | `stage_gate.py:428-444` |
| 2 | archive Parquet schema には既に `fold_sign_ratio: float64?` と `dsr: float64?` が存在 | Verified | `archive.py:80-81` |
| 3 | `fold_sign_ratio` は「隣接 fold 間 Sharpe 符号反転比率」(0=完全反転, 1=完全同符号) | Verified | `statistics.py:234`, `statistics.md:115` |
| 4 | run-report は既に `fold_sign_ratio` / `dsr` の n/mean/median/std/min/max を出力 | Verified | `generate_run_report.py:406-415` |
| 5 | Stage B `metrics.payload["oos_sharpes"]` は `tuple[float]` で、archive 側は length=0 なら `fold_sign_ratio=None` を書き込む | Verified | `archive.py:386-390` |
| 6 | Stage B `metrics.payload["dsr"]` は現状 hard-coded `None` (`stage_gate.py:460`) | Verified | `stage_gate.py:460`, `archive.py:392` |
| 7 | Stage B は LaneManager の generate ループで Stage A pass 個体にのみ実行される | Verified | `swim_lane.py:483-487` |
| 8 | Run 7-9 は Stage B pass=0/120、Run 9 は Stage A pass=0/120、Run 7/8 は Stage A pass≥48 | Verified | `run-7.md:55`, `run-8.md:55`, `run-9.md:55` |
| 9 | Run 7-9 archive で `fold_sign_ratio: n=0`, `dsr: n=0` が記録されている | Verified | `run-7.md:80`, `run-8.md:80`, `run-9.md:81` |
| 10 | Run 7-9 でも Stage B 自体は呼ばれている (Stage A pass 個体は確実に B 評価される)、ただし `oos_sharpes=()` 経由で `fold_sign_ratio=None` が書かれているのが `n=0` の原因 | Unverified (推論、実 archive parquet 確認は別 TODO) | `swim_lane.py:483`, `archive.py:386-390` から推論 |
| 11 | `bars_stage_b` は `LaneManager` 経由で `Tier1Lane.bars_18m` に載る | Verified | `run_ga.py:755`, `swim_lane.py:489` |
| 12 | 現行 default は `wf_train_days=120, wf_test_days=20, wf_step_days=20, wf_embargo_days=1` | Verified | `stage_gate.py:79-82` |
| 13 | `make_wf_folds` の sufficiency は **観測日数** ベース: `fold_len = train_days + embargo_days + test_days` で `fold_len > n_unique_dates` なら `[]` を返す。1 fold 最小は `120 + 1 + 20 = 141` 観測日、2 fold 最小は `+ step_days = 161` 観測日 | Verified | `walk_forward.py:85-88, 96-103` |
| 14 | Run 7-9 dataset は 2026-03-01〜2026-03-15 の 15 観測日のみ。`make_wf_folds` の最小 141 観測日要件を著しく下回るため、現状ほぼ確実に `folds=[]` で `no_folds` reason が発火する経路に入っている | Verified (P12 + P13 + Run report dataset 期間) | `run-7.md:4`, `run-8.md:4`, `run-9.md:4`, P13 |

## 背景・課題

### Fact

- Run 7-9 archive `fold_sign_ratio: n=0`、`dsr: n=0` が連続 (P9)
- Run 7/8 は Stage A pass=48-66/120、Stage B pass=0/120 (P8)
- Run 7-9 dataset は 15 観測日 (P14)、現行 default で 1 fold 取るには 141 観測日必要 (P13)
- Stage B `oos_sharpes` が length=0 の場合、archive は `fold_sign_ratio=None` を書き込む (P5)
- Stage B `dsr` は現行 hard-coded `None` (P6)
- 現行 archive / report には Stage B `reason_codes` を永続化する経路がない (Round 2 review #3 指摘)

### Interpretation

- Stage B pass=0 の現観測 Run については「窓 (観測日数) 不足で `make_wf_folds=[]` → `no_folds` reason」 がほぼ確実な機械的原因 (P14 から導出)
- 一方で「窓不足以外で Stage B が落ちる Run」(P14 が満たされる長期データセット) では、`reason_codes` が永続化されないため事後分析でどの reason で落ちたか分離不能
- 結果として、Stage B 通過率の構造改善には gate semantics 変更ではなく
  1. **upstream**: Stage B 入力窓充足を `make_wf_folds` SSOT と同じ判定式で `LaneManager` 段に契約化 (Run 7-9 の現状に対する応答)
  2. **永続化**: Stage B `reason_codes` を archive に保存 (今後の Run で fail 原因を分離可能化)
  3. **gate**: 有効 fold 数 (`n_fold_effective = n_fold - n_fold_unavailable`) と `positive_fold_ratio_effective` を独立メトリクスとして可視化 (実測分布収集)
  4. **report**: 世代別 reason histogram + `n_fold_effective` 分布を出す

の 4 点を **観測 → 監査 → (実測後) hard 化** の順で進める必要がある。

C7 警告: 3 Run の観測のみで P10 を断定する設計は不可。本案は「**観察可能性確保 + 入力契約検査**」を優先し、新たな hard threshold は実測分布が出るまで導入しない。

## 改善アイデア

**設計方針**: 既存の reason code・metric semantics は破壊しない。観測経路と入力契約のみ追加する。

### A. Stage B 入力窓充足契約 (LaneManager 側)

- 配置場所: `src/alpha_factory/swim_lane.py` の `LaneManager.generate()` 内、`evaluate_stage_b` 呼び出しの直前
- 判定式は **`make_wf_folds` と同じ observed-day 契約** を使う。共通 helper を `walk_forward.py` に切り出し:
  ```python
  def wf_min_unique_dates(stage_cfg) -> int:
      return stage_cfg.wf_train_days + stage_cfg.wf_embargo_days + stage_cfg.wf_test_days
  ```
- `LaneManager` 側で `n_unique_dates(lane.bars_18m)` を計算し、`< wf_min_unique_dates(self._stage_gate_config)` のときは `evaluate_stage_b` を skip して `StageResult(stage="B", passed=False, metrics=<envelope with n_unique_dates>, reason_codes=("stage_b_window_underfilled",))` を **LaneManager 側で構築** して `archive.collect_stage_b` に渡す
- 既存 reason code (`no_folds` / `insufficient_folds` / `all_folds_unavailable`) は維持。`stage_b_window_underfilled` は **独立 canonical code** として `stage-gates.md` Reason Code 語彙に追加
  - Round 2 #5 指摘への応答: 「runner alias」ではなく独立 code とし、taxonomy を明示。`no_folds` は「データはあるが folds 計算結果が空」、`stage_b_window_underfilled` は「LaneManager が `evaluate_stage_b` を呼ぶ前に観測日数不足を検出」と意味を分離

### B. Stage B 観察可能性メトリクス追加 (monitor only、hard gate なし)

- `evaluate_stage_b` の `metrics.payload` に追加:
  - `n_fold_effective: int` (= `n_fold - n_fold_unavailable`)
  - `positive_fold_ratio_effective: float | None` (= 有効 fold のうち sharpe>0 の割合。`fold_sign_ratio` とは別物)
- 既存 `fold_sign_ratio` (隣接符号反転比率) 意味は **一切変更しない**
- 既存 `no_folds` / `insufficient_folds` / `all_folds_unavailable` reason は維持
- `passed` 判定への影響なし (monitor only)

### C. archive schema 拡張 — `reason_codes` 永続化を含む

- archive Parquet に以下を **追加** (削除・型変更なし、既存行は `null` で前方互換):
  - `n_fold_effective: int64?`
  - `positive_fold_ratio_effective: float64?`
  - `stage_b_reason_codes: string?` (= `";".join(reason_codes)`、空タプルは `null`)
- `archive.collect_stage_b` を改修し、`StageResult.reason_codes` を文字列化して `stage_b_reason_codes` 列に書き込む
- これにより Round 2 #3 で指摘された「世代別 reason 集計のデータ経路欠落」を解消

### D. run-report 強化

- run-report の Stage B セクションに以下を追加:
  - **世代別 Stage B reason histogram**: `gen | n_total | n_pass | no_folds | insufficient_folds | all_folds_unavailable | stage_b_window_underfilled | other`
  - `n_fold_effective` 分布 (n / mean / median / std / min / max)
  - `positive_fold_ratio_effective` 分布 (同上)
- データソース: 新規列 `stage_b_reason_codes` / `n_fold_effective` / `positive_fold_ratio_effective`

### E. テスト追加

- `tests/alpha_factory/test_stage_gate.py`:
  - `n_fold_effective` / `positive_fold_ratio_effective` の値が `metrics.payload` に正しく入る
  - 全 fold unavailable のとき `n_fold_effective=0` かつ既存 `all_folds_unavailable` reason が継続発火
- `tests/alpha_factory/test_walk_forward.py`:
  - `wf_min_unique_dates(stage_cfg)` が `train + embargo + test` を返す
- `tests/alpha_factory/test_swim_lane.py` (or 同等):
  - `bars_18m` 観測日数 < `wf_min_unique_dates` のとき `evaluate_stage_b` が呼ばれず、archive に `stage_b_reason_codes="stage_b_window_underfilled"` の行が入る
- `tests/alpha_factory/test_archive.py`:
  - 新列 `stage_b_reason_codes` / `n_fold_effective` / `positive_fold_ratio_effective` が schema に含まれ、Stage B 後の row に値が入る

## 期待効果

- live_criteria 達成への貢献:
  - `stage_b_window_underfilled` reason により、現状 Run (15 観測日) で Stage B = 0 の機械的原因を観測可能化 (window 不足を他要因から分離可能にする — 因果断定はしない)
  - `stage_b_reason_codes` 永続化により、今後の Run で window が十分な場合に「弱さ vs 評価失敗」を世代別 histogram で診断可能化
- 過学習耐性:
  - `n_fold_effective` 分布が実測されることで、将来の `dsr` / `pbo` hard gate 化に必要な「サンプル数の現実分布」を把握できる
  - 本提案自体は新 threshold を導入しないため fail-open / fail-closed の semantics 反転は起こさない (現行を維持)

## 実装方針 (概要・依存順)

実装順序 (Round 2 #6 指摘への応答 — `契約判定 → 永続化 → 可視化` の 3 段):

| 段階 | 変更先 | 内容 | 依存 |
|------|-------|------|------|
| 1-A | `src/alpha_factory/walk_forward.py` | `wf_min_unique_dates()` helper 切り出し | — |
| 1-B | `src/alpha_factory/swim_lane.py` | LaneManager で観測日数充足検査、不足時 `stage_b_window_underfilled` で skip | 1-A |
| 1-C | `src/alpha_factory/stage_gate.py` | `evaluate_stage_b` の metrics.payload に `n_fold_effective` / `positive_fold_ratio_effective` を追加 (monitor only) | — |
| 2-A | `src/alpha_factory/archive.py` | schema に 3 列追加 (`n_fold_effective`, `positive_fold_ratio_effective`, `stage_b_reason_codes`) + `collect_stage_b` で書き込み | 1-B, 1-C |
| 3-A | `scripts/alpha_factory/generate_run_report.py` | 世代別 reason histogram + `n_fold_effective` / `positive_fold_ratio_effective` 分布 | 2-A |
| 4 | `tests/alpha_factory/` | A/B/C/D の挙動テスト | 各段 |
| 5 | `docs/alpha_factory/stage-gates.md` | Reason Code 語彙に `stage_b_window_underfilled` を追加 (独立 canonical code として) | — |

`StageGateConfig` への threshold 追加は **本 TODO ではしない** (実測分布を見てから別 TODO で判断)。

## 制約・前提

- 既存 `evaluate_stage_b` のシグネチャ・戻り値型 (`StageResult`) は維持
- 既存 reason code (`no_folds` / `insufficient_folds` / `all_folds_unavailable`) は維持、置換しない
- archive schema 拡張は追加のみ、Parquet 後方互換 (旧 reader が新列を見ない構成)
- `fold_sign_ratio` の既存意味 (符号反転比率) は維持、新指標 `positive_fold_ratio_effective` は別名で追加
- `stage_b_window_underfilled` は独立 canonical reason code (`no_folds` の alias ではない)
- メモリ: 個体あたり追加 16 byte (int64 + float64) + 文字列 (典型 < 64 byte)、120 個体 × 6 lane = < 50KB、問題なし

## スコープ外

- DSR / PBO の値そのものを hard gate 化する (本提案は観測可能性のみ)
- `n_fold_effective` を hard gate threshold 化する (実測分布収集後の別 TODO)
- Stage A / C への同等契約導入
- WF fold 設計の改善 (regime stratification 等) — 別 TODO
- Sieve OOS 期間動的化 — 別 TODO
- `dsr` を実際に計算する経路の追加 (現行 hard-coded `None` を解消する) — 別 TODO
- 過去 Run の archive parquet 直接確認による P10 の Verified 化 — 監査作業として別 TODO

## reason code 拡張 (canonical 追加 1 件)

| reason_code | 意味 | 発火元 | 追加先 |
|------------|------|-------|-------|
| `stage_b_window_underfilled` | LaneManager が Stage B 評価前に `n_unique_dates(bars_18m) < wf_min_unique_dates(stage_cfg)` を検出 | `swim_lane.py` (`evaluate_stage_b` 外) | `stage-gates.md` Reason Code 語彙 |
