# 概念設計: Stage A→B Pipeline Health Fix（calibrate 伝搬不全 + Stage B 全 fold unavailable）

## 0. 前提検証表（C4）

本概念設計の前提を **verified / unverified** に分け、調査 phase で潰す対象を明確にする。

| # | 前提 | 状態 | 根拠 |
|---|---|---|---|
| P1 | calibrate-gate `history.jsonl` に本番 RUN の threshold 記録が存在 | **verified** | history.jsonl 本文（§1.2 参照） |
| P2 | run-24 archive で `n_fold_effective=0` が 3745/3745 | **verified** | archive Parquet 集計（§1.3 参照） |
| P3 | 環境は Python 3.11.15 / Numba 0.65.1 / NumPy 2.4.4 / T053 main マージ済 | **verified** | `.python-version` / `uv.lock` / git log |
| P4 | run summary の `stage_a_threshold` フィールドは「実際に評価で使われた effective threshold」を表す | **unverified** | run_report 生成元の field 意味は要 source-code 確認 |
| P5 | calibrate-gate の伝搬経路が「無い」または「壊れている」 | **unverified** | 経路自体は存在する可能性あり（条件未充足 / 別 source of truth / summary 表示ずれ） |
| P6 | run-24 の Stage B は実際に 18 ヶ月分の bar を取得できている | **unverified** | dataset.start/end 6 ヶ月設定との整合性に疑念あり、`bars_stage_b` の実 length と日付範囲は要実測 |
| P7 | `all_folds_unavailable` はコード回帰（commit 単一原因） | **unverified** | 単一切替点（834→0）は n=2 の境界、データ regime / 仕様変更でも起こり得る |
| P8 | 本番 4 時間の支配コストは Stage B | **unverified** | profile 観測なし。Stage B が「早く失敗」しているだけなら正常化後 wall-clock が **増える**可能性すらある |

→ **P4-P8 を確定するための investigation phase を施策 0 として明示的に置く**（Round 1 [Critical] 反映）。

---

## 1. 背景・課題

### 1.1 主目的（Round 1 [Warning] 1 反映で再定義）

**Stage B evaluability の回復**を最優先とする。すなわち「Stage A pass 個体が Stage B で `all_folds_unavailable` 一色になる現状を解消し、Stage B が pass/reject の意味のある分布を返す状態」に戻すこと。

副次目標として、calibrate-gate 結果が次 RUN に正しく反映され Stage A 通過率が target_pass_rate に近づくこと。

**速度改善は副次仮説に格下げ**: Stage B 機能修復後に stage-wise wall-clock を再計測してから判断する。事前見積りはしない。

### 1.2 観測 (Facts) — Stage A 通過率と calibrate-gate 履歴

直近本番 RUN の Stage A 通過率（target_pass_rate=0.15）:

| RUN | A pass / 5856 | rate | summary stage_a_threshold |
|---|---|---|---|
| run-20 | 2750 | 47.0% | (推定 0.0) |
| run-21 | 2395 | 40.9% | 0.0 |
| run-22 | 1758 | 30.0% | 中間 |
| run-23 | 2238 | 38.2% | 0.0 |
| run-24 | 3745 | 64.0% | 0.0 |

calibrate-gate `history.jsonl` 本番 record（時系列）:

| applied_at | run_id | actual | prev_thr | new_thr | decision | stage_b_pass |
|---|---|---|---|---|---|---|
| 2026-04-26 17:45 | run_20260426_145502 | 69.8% | 0.0 | 0.0778 | tighten | **834** |
| 2026-04-26 20:42 | run_20260426_183119 | 50.8% | 0.0778 | 0.1778 | tighten (clamped) | **0** |

Interpretation: history と summary の表示値が乖離している（history では 0.0778 → 0.1778 と遷移、summary では 0.0 のまま）。「経路なし」と「summary 表示が effective threshold を反映していない」のどちらが真かは不明。

### 1.3 観測 (Facts) — Stage B reason codes

run-24 archive Parquet で Stage A pass 個体 3745 全員が同一 reason code:
```
median_oos_sharpe<min ; positive_fold_ratio<min ; all_folds_unavailable
```
- `n_fold_effective = 0`（3745/3745）
- `positive_fold_ratio_effective = NaN`（3745/3745）
- `dsr = NaN`（3745/3745）
- `trade_sharpe_stage_b` のみ値あり（mean ≈ 0.20、min ≈ -0.17、max ≈ 0.29）

切り替わり点（n=2 で十分でないことは Round 1 [Warning] 反映で承知）:
- `run_20260426_145502`: stage_b_pass=834
- `run_20260426_183119`: stage_b_pass=0
- run-22 〜 run-24: 継続的に 0

Interpretation: 「単一 commit による回帰」と決め打ちせず、施策 0 で **前後 3-5 RUN の現象差分**（reason code 分布、bars_stage_b 期間、fold 数）を固定してから commit 調査に入る。

### 1.4 解釈と問題定義

- 評価 pipeline の Stage B が機能していないため、Stage C 通過個体が **構造的に出現不可能**
- 結果として live_criteria 全充足ゲノム（使命達成）への到達経路が閉じている
- これは「速度問題」の皮を被った「**Pipeline 機能不全**」問題であり、本来の使命達成可能性の前提が崩れている

---

## 2. 施策

### 2.1 施策 0 — Source-of-Truth と現象差分の調査（最優先、修正前 deliverable）

**Round 1 [Critical] 反映**: 修正方針を実装する前に、以下を investigation note (`devnotes/{dir}/investigation.md`) として固定する。

#### 2.1.1 Stage A threshold の source of truth 図

- threshold 値の **source of truth は何か**を 1 つに固定:
  - 候補 1: `config/alpha_factory/default.yaml` の `stage_a.threshold`（永続反映型）
  - 候補 2: `reports/calibrate-gate/history.jsonl` の最新 record（state file 型）
  - 候補 3: runtime CLI override（揮発型）
- run_ga.py の startup で **どの値が effective として使われているか**をログから verify
- summary.json `stage_a_threshold` field が effective threshold を表すかを source code 確認

成果物: `Stage A threshold 経路図`（config → GaConfig → stage_gate evaluator のどこで上書きが起こるか）

#### 2.1.2 Stage B 実 bar 期間と fold 構築数の実測

`run_20260426_145502`（Stage B pass=834）と `run_20260426_183119`（Stage B pass=0）の両 RUN について以下を集計:

| 項目 | 必須出力 |
|---|---|
| `bars_stage_b[0].time` | 開始タイムスタンプ |
| `bars_stage_b[-1].time` | 終了タイムスタンプ |
| `len(bars_stage_b)` | bar 数 |
| `constructed_fold_count` | WF fold 構築数（valid + invalid 合計） |
| `invalid_fold_count_by_reason` | invalid fold の reason 別カウント |
| `n_fold_effective` 分布 | 個体ごとの effective fold 数の hist |
| `commit_hash` | 実行時の git HEAD commit hash（Round 2 [Suggestion] 反映: 仕様変更起因の切り分け強化） |

成果物: `Stage B bar/fold 実測結果`（両 RUN の数値表）

#### 2.1.3 前後 3-5 RUN の現象差分固定（C7 反映）

run-19 / run-20 / run-21 / run-22 / run-23 / run-24 の 6 RUN について:
- stage_a_pass_rate
- stage_b_pass_count
- stage_b_reason_codes 分布（top-3）
- bars_stage_b 実期間
- 同 RUN で Stage B pass が出た個体（あれば）の fold 数

→ 「現象が突然変わった」のか「徐々に劣化」かを n>=5 で確認。

#### 2.1.4 git diff 範囲の特定

施策 0 の §2.1.2 / §2.1.3 で「機能していた RUN」と「機能していない RUN」の境界を確定してから:
- `git log --all -S "all_folds_unavailable" --since="<切替前 RUN 日時>" --until="<切替後 RUN 日時>"`
- `git log --all -S "n_fold_effective" --since=...`
- 対象ファイル: `src/alpha_factory/stage_gate.py` / `src/backtest/walk_forward.py`（または相当の WF 実装） / `scripts/alpha_factory/run_ga.py`

成果物: 候補 commit 一覧 + 各 commit の影響範囲メモ

---

### 2.2 施策 A — Stage A calibrate_gate の伝搬経路修正（施策 0 で source of truth 確定後）

**Round 1 [Critical] 反映**: 実装方針は施策 0 の結果次第。**現時点では具体的 hook 案を固定しない**。

施策 0 §2.1.1 の結果に応じて:
- 経路あり / 条件未充足: 条件を満たすように config / 運用テンプレートを修正
- 経路あり / 別 source of truth が優先: source of truth を整理（重複管理を解消）
- 経路なし: 設計判断として state file 型を採用（理由: history.jsonl が既に存在し、再現性も保てる）。ただし record に **以下のメタデータを必須追加**:
  - `config_hash`: その RUN で使われた config の hash
  - `dataset_span`: 使用 dataset の `(start, end)`
  - `instrument`: 通貨ペア
  - `stage_gate_version`: Stage gate ロジックの version 識別子
  - `applied_from_run_id`: 適用元 RUN
  - **不一致時は適用しない**（cross-run contamination 防止、Round 1 [Warning] 反映）
  - **`decision` フィルタの明文化**（Round 2 [Warning] 反映）: 適用対象は `decision in ("tighten", "loosen")` のみ。`in_band` / `skip_sample_size` の record は適用しない（既存閾値を維持）

期待効果（**機能目標のみ**、性能予測なし）:
- Stage A 通過率が target_pass_rate ± tolerance の範囲に収まる
- 同一 config・同一 dataset の連続 RUN で threshold が monotonic に収束する

### 2.3 施策 B — Stage B all_folds_unavailable の修正

施策 0 §2.1.2 / §2.1.4 の調査結果次第:
- B-1（bars_stage_b slicing バグ）: slicing ロジックを修正、bar 数 invariant の test を追加
- B-2（fold validation が厳しくなった）: 「動いていた当時の意図」を別途 design し直す。**緩めるだけの hack は禁止**（Round 1 [Suggestion] / 禁止事項 4）
- B-3（fold time index 計算バグ）: index 計算を修正、time-axis 不変条件 test を追加
- B-4（仕様変更の retro 不整合）: 仕様変更の意図を再確認し、変更が正しいなら他の評価 path を再設計、誤りなら revert + bug 化

期待効果（**機能目標のみ**）:
- Stage A pass 個体の少なくとも一部で `n_fold_effective > 0`
- reason codes が `all_folds_unavailable` 単色から複数 reason に分散

### 2.4 施策 C — 観測テンプレート更新は **別 TODO に分離**

Round 1 [Warning] 反映: 本 TODO のスコープから外す。施策 A/B の root cause 確定 + 修正完了後に `T-future-pipeline-health-monitoring`（仮）として別途登録。

---

## 3. 期待効果（機能目標と性能目標の二分化、Round 1 [Critical] 反映）

### 3.1 機能目標（必須、本 TODO の合格条件）

- **`all_folds_unavailable` 一色の解消**: 同一 RUN 内で複数 reason code が分布
- **Stage A 通過率の target 整合**: target_pass_rate ± tolerance（n>=30 or 複数 seed で確認）
- **Stage B pass 個体の出現可能性**: 0 強制ではないが、構造的に pass 可能な状態に戻る

### 3.2 性能目標（副次、修正後に再計測してから設定）

- 修正後に **stage-wise wall-clock profile を取り直して**から目標値を確定
- 事前推定はしない（Stage B が「早く失敗」していた場合、機能修復で wall-clock が**増える**可能性もある）

### 3.3 使命への貢献

- live_criteria 数値を一切操作せず、**評価 pipeline の機能不全を治す**
- Stage C 通過個体出現の構造的可能性を回復 → 使命達成への到達経路を再開
- T053（composite Numba 化）の本番効果を Stage B 経由で正しく測定可能に

---

## 4. 実装方針（概要）

### 4.1 進行順序（評価切り分け、Round 1 [Suggestion] 反映）

1. **施策 0**: investigation note 作成（A/B 共通の root cause 切り分け）
2. **施策 B 単独**: fold validation 修正 → 修正前の calibrate-gate threshold 適用なしで再実測（A の影響を分離）
3. **施策 A 単独**: threshold 反映経路を整える（B 修正後の calibrate-gate run record で適用）
4. **A+B end-to-end**: 本番 1 RUN で機能目標を確認、stage-wise wall-clock 再計測

### 4.2 実装単位

施策 0（investigation） / 施策 B（実装） / 施策 A（実装） を **別 commit / 別 PR**として分離（incremental）。施策 C は別 TODO。

---

## 5. 制約・前提

### 5.1 数値・絶対制約

- 本修正は閾値伝搬と fold validation の修正であり、**composite / primitive / broker の数値演算には触らない**
- T053 の数値同値性 bit-exact 検証結果を破壊しない（**ただし Stage A/B 判定値そのものは変わってよい** — 本修正の目的が判定 path を治すことなので、archive Parquet の Stage A/B/C 関連 field の同値性は acceptance test に**しない**。Round 1 [Critical] 5 反映）
- イントラデイ / ロング・ショート / swap・spread 反映の絶対制約は不変

### 5.2 禁止事項の遵守

- live_criteria 緩和禁止（禁止 4）
- Stage B fold validation を **緩めて** pass を増やす hack 禁止（禁止 4）
- A・B・C 評価期間延長禁止（禁止 1）
- 過度な複雑化禁止（禁止 5）。新フレームワーク・大規模リファクタは却下
- GA ハック禁止（禁止 3）
- 取引回数操作で見せ方を変えるのも禁止（禁止 6）

### 5.3 後方互換

- 既存テスト `tests/alpha_factory/test_calibrate_gate*.py` / `test_stage_gate*.py` を破壊しない（修正後の挙動が真の意図と一致するならテスト更新は OK、ただし更新理由を明記）
- archive Parquet スキーマは追加のみ
- run_report スキーマは追加のみ

### 5.4 cross-run contamination 防止（Round 1 [Warning] 反映）

施策 A で history record を読む経路を導入する場合、最低限 `config_hash / dataset_span / instrument / stage_gate_version / applied_from_run_id` を verify。不一致なら適用しない（fail-closed）。

---

## 6. スコープ外

- 施策 C（観測テンプレート更新）→ 別 TODO
- T053 follow-up の `mock.py` Decimal 化等の高速化
- composite 以外の primitive 改善
- Stage C 通過率の改善（B が機能してから議論）
- live_criteria 閾値そのものの調整
- Cross-pair (ii-lite) 評価系の修正

---

## 7. 検証計画（Round 1 [Critical] 反映で再構成）

| # | 項目 | 合格基準 |
|---|---|---|
| V0-A | threshold source-of-truth 図 | 施策 0 で 1 枚の経路図を作成し、source of truth が 1 つに固定されている |
| V0-B | run_ga effective threshold ログ | startup で「使われた effective threshold」が log に出るようにする |
| V0-C | summary field 意味確認 | summary.json の `stage_a_threshold` field が effective threshold を表すか確認、表していなければ field 名・意味を修正 or 補完 |
| V1 | 原因 commit / 仕様変更の特定 | 施策 0 §2.1.4 で commit 候補一覧、または「commit ではなく仕様/データ regime 変更」と結論 |
| V2 | 小規模 RUN 機能確認 | pop=8, gen=2 の小規模では **pass-rate 近似判定はしない**（n=24 < 30 で C7 違反）。代わりに以下を確認: (a) override が読まれた、(b) effective threshold が期待値、(c) reason code が単色でない、(d) `n_fold_effective > 0` の個体が少なくとも 1 出る |
| V3 | 本番 RUN 機能確認 | pop=96, gen=60 で **必須**: (a) `n_fold_effective > 0` の個体が出現、(b) reason code が単色 (`all_folds_unavailable` 一色) を解消、(c) stage_a_pass_rate が target ± tolerance。**参考 KPI（必須にしない）**: `stage_b_pass_count >= 1` — 相場レジーム依存で偽陰性になり得るため Round 2 [Warning] 反映で必須から外す |
| V4 | 数値同値性（適用範囲限定） | T053 の composite/backtest 数値契約は **不変**（同一 genome × 同一 bars に対する `compute_composite` 結果が allclose）。Stage A/B/C 判定値・archive Parquet の stage_*_pass フィールドは **比較対象外**（修正の目的が判定 path 自体を治すこと） |
| V5 | 既存テスト | `uv run pytest tests/alpha_factory/ tests/backtest/ tests/dsl/ -x` 全パス |
| V6 | 新規テスト | 施策 A: override hook（または source of truth 1 化）の挙動 / cross-run contamination ガード。施策 B: fold validation 不変条件、time-axis 不変条件、bar 数 invariant |

INCONCLUSIVE 扱い:
- 施策 0 §2.1.4 で「単一 commit ではなくデータ regime / 仕様変更」と判明した場合、施策 B の方針を「動いていた当時の挙動を再現する仕様の再 design」に切り替える。ここで設計の Round 増しが必要なら本 TODO を一旦 close し、仕様再 design を別 TODO として登録する
