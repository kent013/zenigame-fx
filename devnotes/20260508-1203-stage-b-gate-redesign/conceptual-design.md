# 概念設計: Stage B gate redesign — noise-floor 整合化 + DSR + trade_count scale 整合化

**改版履歴**:
- v1 (2026-05-08 12:06 JST): 初版
- v2 (2026-05-08 12:18 JST): Codex Round 2 review (CHANGES_REQUESTED) を反映
  - Critical 1: DSR の N (trial 数) 定義を「同一 RUN Stage A pass 個体数」 に固定、 dsr_method/dsr_trials/dsr_observations/dsr_skew/dsr_kurtosis/dsr_valid 列を archive に追加
  - Critical 2: trade_count_full_dataset を Stage A unique + Stage B 全期間 1pass unique で canonical 定義 (fold 合算は禁止)
  - Critical 3: H_A1 を「2 個体のうち 1 件以上 pass」 に修正、 H_A3 を archive replay の top-K 比較に変更、 H_A4 (trade_count median 上昇) を追加
  - Warning 1: 確率計算を 84% → 60% に修正
  - Warning 2: --allow-holdout-short を二重 opt-in (CLI + env var) + archive marker + graduate 禁止に強化
  - Warning 3: 成功判定を Layer 1 (replay) / Layer 2 (次 RUN) / Layer 3 (使命達成 = Phase 1 単独では十分条件にならず) に整理
  - Suggestion: 実装順序を threshold replay → trade_count → DSR → partition guard に再整理

## 背景・課題

### 観察された事実 (FACT)

20 RUN improve-cycle (RUN 34-53) 後の archive parquet 直読調査 (commit 5b30eed `devnotes/20260508-1130-post20run-investigation/`) で以下が確定:

**F1. run-52 archive に使命適格個体 7 件が既に存在** (Stage A pass + trade>=50 + total_pnl>=50,000)

| name | trade | total_pnl | pfre | n_fold_eff | blocked by |
|---|---:|---:|---:|---:|---|
| g70_i9 | 138 | 56,930 | **0.7** | 10 | median_oos_sharpe<min |
| g71_i36 | 65 | 58,830 | 0.5 | 10 | median_oos_sharpe<min;positive_fold_ratio<min |
| g72_i64 | 65 | 58,830 | 0.5 | 10 | 同上 |
| g89_i36 | 124 | 57,590 | 0.5 | 10 | 同上 |
| g88_i12 | 124 | 57,590 | 0.5 | 10 | 同上 |
| g65_i88 | 116 | 53,750 | 0.4 | 10 | 同上 |
| g83_i12 | 127 | 50,820 | 0.7 | 10 | median_oos_sharpe<min |

**F2. trade_count vs Stage B pass の極端二極化** (run-52, archive 直読)

| trade_bin | count | sb_pass | sb_rate | pfre_med | pnl_max |
|---|---:|---:|---:|---:|---:|
| (10,20] | 97 | 97 | **100%** | 0.70 | 23,910 |
| (20,30] | 37 | 35 | 95% | 0.70 | 27,260 |
| (50,80] | 725 | 0 | **0%** | 0.50 | 58,830 |
| (80,120] | 1,020 | 0 | **0%** | 0.45 | 53,750 |
| (120,200] | 433 | 0 | **0%** | 0.30 | 57,590 |

**F8. median_oos_sharpe noise floor 不整合** (config/alpha_factory/default.yaml の Lo, 2002 引用)
- `stage_b_fold_trade_count_min: 10` で per-fold trade-Sharpe SE ≈ √((1+0.5×SR²)/10) ≈ 0.32
- 10-fold median SE ≈ 0.32/√10 ≈ 0.10
- 現行 `median_oos_sharpe_min = 0.05` は noise floor とほぼ同じ → 真の robust signal を弾く

**F7. trade_count scale 不整合**
- archive `trade_count` は **Stage A 60日 window のみ**
- selection feasibility は Stage A trade_count>=50 を要求 (= 6.5 trades/day = 年 1,627 trades 相当)
- mission criteria.trade_count_min=50 はデータセット全期間想定 (180日 → 1 trade/day)
- → **selection と mission の trade_count 参照系が別スケール**で判定

**F10/Q8. archive `dsr` column が常時 null**
- `evaluate_stage_b` の metrics_envelope で `"dsr": None  # Phase 4 で hard 化` と明示 (stage_gate.py:1266)
- 統計的整合性検証 (Bailey & López de Prado, 2014, "The Deflated Sharpe Ratio") が未稼働
- archive にも常時 null のまま flush され、replay 分析できない

### 解釈 (INTERPRETATION)

報告書の最終結論「Stage B + feasible は探索空間内に存在しない (構造的限界)」 は **誤読**。 真因は **Stage B median_oos_sharpe gate が noise-floor 整合性を欠いて真の robust signal を排除している** こと (Codex Q1 H_A=CONFIRMED)。

trade<=30 個体 100% Stage B pass / trade>=50 個体 0% pass の二極化は、 fold_trade_count_min=10 ぎりぎりの個体での Sharpe 推定 SE が大きすぎて median が偶発的に >0.05 を超えることに起因する **survivor bias** (Codex Q2 CONFIRMED)。 Stage C holdout で全員 sharpe<=0 という事実が survivor bias の傍証。

trade_count スケール不整合は、 Stage A 60日 trade_count>=50 を要求すると **selection が高頻度 trader 方向に過剰バイアス**する根因。 mission criteria の意図 (1 trade/day 程度) と乖離。

### 課題

このまま gate を維持すると:
1. 既に存在する mission-eligible 個体を構造的に排除し続ける (graduate=0 が継続)
2. low-trade survivor bias 個体に selection 圧が偏り、 真の robust signal が育たない
3. selection の trade_count 参照系が mission と整合しない → 探索方向が乖離

---

## 改善アイデア

**Stage B gate を 4 つの観点で同時に noise-floor 整合化する**:

### A. median_oos_sharpe_min を SE-aware に再校正

`stage_b_median_oos_sharpe_min: 0.05 → 0.025` の 1 パラメータ sweep。

- mission criteria sharpe_min=1.0 (annualized, T042 換算後) は trade-level scale で 0.05〜0.10 程度
- gate は mission criteria の **半分以下** にしないと検出力 (statistical power) が確保できない

**SE 計算の修正** (Codex Round 2 で確率計算誤りを指摘済み):

- Lo (2002) SE ≈ √((1+0.5×SR²)/N)、 N=10 で SE ≈ 0.32
- 10-fold median SE ≈ 0.32 / √10 ≈ 0.10
- 真値 SR=0.05 の個体の median 推定値が 0.025 以上になる確率 (片側):
  - z = (0.025 - 0.05) / 0.10 = -0.25
  - P(estimate >= 0.025) ≈ Φ(0.25) ≈ **60%** (1-σ ではなく 0.25-σ 下回る位置)
- 0.05 を維持した場合の確率: P(estimate >= 0.05) = 50% (median == true value 期待)
- → 0.05 では真値 0.05 個体すら 50% しか通過しない厳密性、 0.025 で 60%、 0.0 で 69% (Φ(0.5))

**0.025 は「真値 0.05 個体の検出力を 50% → 60% に拡張」 する保守的調整**。 noise-floor 完全整合 (= 0) ではないが、 1 sweep step として妥当な保守値。

**禁止事項 4 「live_criteria 閾値をいたずらに緩和」** との関係:
- 変更対象は `stage_b_median_oos_sharpe_min` (Stage B gate **内部閾値**)
- live_criteria.sharpe_min (annualized=1.0) は **変更しない**
- 「いたずらに」 ではなく **Lo (2002) の SE 公式に基づく noise-floor 整合化** (検出力 50%→60% への保守的拡張)
- T042 docs/alpha_factory/sharpe-rescale.md で trade-level vs annualized scale が別管理されていることを引用

### B. DSR (Deflated Sharpe Ratio) を計算 + archive 記録 (monitor only)

**Bailey & López de Prado (2014) "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality" の DSR を実装。**

DSR は **selection bias / multiple testing / non-normality** を補正する指標 (ドローダウン補正ではない、 Round 2 で誤記指摘済)。 PSR (Probabilistic Sharpe Ratio) を「複数試行」 で deflated したもの。

#### DSR 数式 (Bailey & López de Prado 2014)

PSR (Probabilistic Sharpe Ratio):
```
PSR(SR*) = Φ( (SR_observed - SR*) × √(N-1) / √(1 - skew × SR_observed + ((kurt-1)/4) × SR_observed²) )
```

DSR の SR* (expected max under null):
```
SR* = sqrt(V[SR]) × ((1 - γ) × Φ⁻¹(1 - 1/N_trials) + γ × Φ⁻¹(1 - 1/(N_trials × e)))
```
ここで γ = Euler-Mascheroni 定数 (0.5772)、 V[SR] = trial 間 SR 分散。

#### Per-fold DSR の N (trial 数) 定義

**concrete 規定 (Round 2 修正)**:
- **N_trials = 同一 RUN 内 Stage B 評価対象個体数** (= 各 RUN で Stage A pass した個体数、 archive `stage_a_pass=True` の row count)
- **observations = fold あたり trade_count** (per-fold で計算)
- **skew / kurtosis = fold 内 trade returns 分布の標本歪度・尖度** (per-fold で計算)
- **valid フラグ = (trade_count >= 30 AND skew/kurtosis 推定有限)** (Lo 2002 の N>=30 推奨に基づく)

#### archive 列追加 (Round 2 指摘の N 等同時記録)

`dsr` 単独では再解釈できないため、 以下を同時に追加:
- `dsr` (float, 実値、 null は `valid=False` 時のみ)
- `dsr_method` (string, "bailey_lopez_de_prado_2014_per_fold_median")
- `dsr_n_trials` (int, 同一 RUN Stage A pass 個体数)
- `dsr_observations` (int, per-fold trade_count の median across folds)
- `dsr_skew` (float, fold 内 trade returns skew の median across folds)
- `dsr_kurtosis` (float, fold 内 trade returns kurtosis の median across folds)
- `dsr_valid` (bool, 各 fold で valid フラグが立った割合 >= 0.5)

#### Phase 1 ではどう使う

- **archive に記録のみ** (gate の hard 化はしない、 monitor only)
- Phase 1 では **median_oos_sharpe ベースの既存 gate を維持**、 DSR は観察用
- Phase 2 で「DSR > 0 OR median>=0.025」 等の OR gate 化を検討

#### per-fold trade=10 では skew/kurtosis 推定不安定 → valid=False で archive null

Codex Round 2 指摘: per-fold trade 数が fold_trade_count_min=10 近辺だと skew/kurtosis 推定不安定。
→ **valid=False 時は dsr=null を維持**、 dsr_observations / dsr_skew / dsr_kurtosis は記録 (post-hoc 分析用)。 trade>=30 個体のみ DSR が信頼できる前提で運用。

### C. selection feasibility の trade_count 参照を Stage A 60日 → データセット全期間に整合

**archive に `trade_count_full_dataset` column 追加** (Round 2 指摘で canonical 定義を確立)。

#### canonical 定義 (Round 2 修正)

**`trade_count_full_dataset = trade_count_stage_a_unique + trade_count_stage_b_unique`**

ここで:
- `trade_count_stage_a_unique` = Stage A 60日 backtest 1 回分の **unique entry timestamp 数** (現行 `trade_count` と同等)
- `trade_count_stage_b_unique` = Stage B 全期間 (window_months=18 だが本データセットでは Stage B partition 全体 ≈ 67日) を **1 回だけ OOS 相当で再評価**した unique entry timestamp 数

**重要**: walk-forward fold trade の合算は **使わない** (Round 2 指摘の重複カウントリスク)。 Stage B 全期間 backtest を 1 回追加実行する。

#### 計算手順

1. Stage A backtest 完了後、 既存の trade_count を `trade_count_stage_a` として archive に保存 (現行と同じ)
2. Stage B 全期間 backtest を **1 回追加** (Stage B partition の `[stage_b_start, stage_b_end)` を train なしの evaluation 経路で 1 pass)
3. その backtest 結果の `trade_count` を `trade_count_stage_b` として archive に保存
4. `trade_count_full_dataset = trade_count_stage_a + trade_count_stage_b`

**de-duplicate 契約**:
- Stage A 期間 `[end - 60d, end)` と Stage B 期間 `[start, end - 60d)` は disjoint partition guard で時系列上重複しない契約 (T087 検証済み)
- → unique entry timestamp は instrument 別で disjoint、 単純合算で重複なし

**コスト見積**:
- Stage B 1 pass evaluation = Stage A 1 pass evaluation × (97003 / 86400) ≈ 1.12x のコスト
- 各個体に Stage B fold 評価 (~10 fold) が既にあるので、 全期間 1 pass 追加で trade evaluation 全体 ~10% 増
- 24GB / 6 worker 制約 (1 worker 3GB) は worker 数に影響しないため許容

#### archive schema 4 点セット遵守

- **GENOMES_SCHEMA**: `trade_count_stage_a` (rename from `trade_count`)、 `trade_count_stage_b` (新)、 `trade_count_full_dataset` (新) を追加
  - 後方互換: 既存 archive の `trade_count` 列読み込みは backwards-compat layer で `trade_count_stage_a` にマップ
- **_create_row_template**: 各列の初期値 (0 または null) 追加
- **collect_stage_a / collect_stage_b**: 各 stage 完了後に書き込み
- **flush 出力 + replay/report consumer**: archive Parquet と report 生成側 (`generate_run_report.py`) も新列を読む
- **selection cache (run_ga.py `_update_cache`)**: `IndividualCacheEntry.trade_count_full_dataset` を archive 行から読み込み、 feasible 判定に使用

#### selection_score `feasible` の変更

```python
# 現行
feasible = (trade_count >= entry_count_min)  # entry_count_min=50, trade_count=Stage A 60日

# 変更後
feasible = (trade_count_full_dataset >= entry_count_min)  # entry_count_min=50, trade_count_full_dataset=Stage A + B 合算
```

`entry_count_min=50` は変更しない。 ただし参照スコープが Stage A 60日 から データセット ~127日 (Stage A 60d + Stage B 67d) に拡張される。

→ 60日換算で従来の trade>=50 = 6.5 trades/day (年 1,627 trades) という過剰要件は、 ~127日換算で 50/(127/60) = 23.6 trades/60日 = 0.39 trades/day = 年 142 trades 程度に整合化。

**期待効果**: selection 圧が「高頻度 trader」 から「データセット全体で適度に取引する個体」 に整合。

### D. stage_partition_guard に holdout_days 検証追加 (副次)

config `stage_c.holdout_days=60` vs 実データ `bars_holdout=20,457 (~14日)` の不整合を **起動時 fail-closed**。

- Phase 1 では Stage C 評価機構自体は redesign しない (Phase 2 タスク)
- 起動時に config と実データの不整合を検出するガードのみ追加

#### escape hatch の運用ガード (Round 2 修正)

Round 2 指摘の **二重 opt-in + archive marker** に強化:

**二重 opt-in 必須**:
1. CLI フラグ `--allow-holdout-short` を **明示**
2. **AND** 環境変数 `ZENIGAME_FX_SMOKE_TEST=1` を設定

両方無いと escape hatch は無効 (= production RUN で誤指定不可)。

**archive marker 強制記録**:
- escape hatch 発動時、 archive (summary.json) に `holdout_short_override: true` を必須記録
- 同 RUN の全個体 archive 行に `holdout_short_override` 列追加 (T058 schema_contract に従う)

**graduate 判定禁止 + calibrate 反映禁止**:
- `holdout_short_override=true` の RUN では:
  - mission 達成判定を強制 SKIP (graduate=0 を維持)
  - calibrate-gate history への append を強制 SKIP (cross-run contamination 防止)
  - reports/run-reports/ には `[SMOKE TEST]` prefix を付加
- これらは `run_ga.py` 起動時 / 完了時の post-processing で hard 強制

#### 想定される運用 (smoke test only)

```bash
# smoke test
ZENIGAME_FX_SMOKE_TEST=1 uv run python scripts/alpha_factory/run_ga.py --allow-holdout-short --generations 5

# production (fail-closed)
uv run python scripts/alpha_factory/run_ga.py  # holdout 不整合 → RuntimeError
uv run python scripts/alpha_factory/run_ga.py --allow-holdout-short  # env var 無し → escape hatch 無効、 RuntimeError
```

→ production 経路で誤って escape hatch が発動するリスクを構造的に排除。

---

## 期待効果

### 直接効果

1. **mission graduate 1 件以上達成**: run-52 archive replay で median_oos_sharpe_min=0.025 適用 → 7 個体のうち g70_i9 (pfre=0.7) と g83_i12 (pfre=0.7) が確実候補。 期待 1-3 件 Stage B pass
2. **selection の質向上**: trade_count_full_dataset 参照で「Stage A 60日に集中する高頻度 trader」 への偏りが解消、 Stage B noise survivor の選好減少
3. **DSR archive 蓄積**: 後続 Phase の SE-aware gate 設計に必要なデータ収集
4. **設計 vs 実態の不整合検出**: holdout_days 14 vs 60 が起動時に fail-closed で報告される

### 間接効果

- 「mission-eligible 個体は既に存在する」 という事実を運用に組み込み、 報告書の誤読を是正
- Codex 議論で確定した **「探索ではなく gate の問題」** という解釈を実装で確認

---

## 実装方針 (概要)

### 変更コンポーネント

1. **`config/alpha_factory/default.yaml`** (`stage_gate.stage_b`)
   - `median_oos_sharpe_min: 0.05 → 0.025` (1 パラメータ調整)
   - 設計コメントで Lo (2002) SE 公式と noise-floor 計算を明示

2. **`src/alpha_factory/stage_gate.py`** (`evaluate_stage_b`)
   - DSR 計算ロジック追加 (per-fold で deflated sharpe を計算、 median across folds)
   - metrics_envelope の `dsr` を None → 実値
   - 既存 median_oos_sharpe gate ロジックは保持 (DSR は monitor only)

3. **`src/alpha_factory/archive.py`** (`GENOMES_SCHEMA`)
   - 新 column `trade_count_full_dataset` 追加
   - 既存 `dsr` column の null 上書き禁止 (実値が来たら必ず書き込む)
   - `_create_row_template` に初期値追加
   - `collect_stage_*` で値伝搬

4. **`scripts/alpha_factory/run_ga.py`**
   - `IndividualCacheEntry.feasible` 判定で `trade_count_full_dataset >= entry_count_min` を使用
   - `_update_cache` で archive 行から `trade_count_full_dataset` を読み込み
   - selection_score docstring 更新

5. **`src/alpha_factory/stage_partition_guard.py`** (`validate_stage_partition`)
   - `holdout_days` vs actual `bars_holdout` の整合性検証追加
   - 不整合時 `RuntimeError` (escape hatch: `--allow-holdout-short`)

### archive schema 拡張時の値伝搬 4 点セット (禁止事項 8 遵守)

`trade_count_full_dataset` 追加時:
- ✅ `GENOMES_SCHEMA` フィールド定義 (archive.py)
- ✅ `_create_row_template` 初期値 (archive.py)
- ✅ `collect_stage_a` / `collect_stage_b` 書き込み (stage_a_evaluator.py / stage_gate.py)
- ✅ `flush` 出力確認 (archive.py)

`dsr` の null → 実値:
- ✅ `evaluate_stage_b` で計算 → metrics_envelope.payload.dsr
- ✅ `collect_stage_b` で archive 行に書き込み
- ✅ archive replay 時に dsr が実値で読める

---

## 制約・前提

### 絶対制約 (使命遵守)

- **イントラデイ前提維持**: Stage B fold 期間 wf_test_days=18 等は変更しない
- **ロング・ショート両方向許容**: gate ロジックは方向中立
- **スワップ・スプレッド反映**: backtest_config を Stage B でも適用

### 禁止事項遵守

- **禁止事項 1 (期間延長禁止)**: Stage B window_months / wf_test_days / fold 構造は **変更しない**。 median_oos_sharpe_min の閾値調整のみ
- **禁止事項 2 (見た目の数値改善)**: 0.05→0.025 の根拠は Lo (2002) SE 公式 → noise floor 整合化。 「graduate を出すため」 の閾値弛緩ではない
- **禁止事項 4 (live_criteria 緩和)**: live_criteria.sharpe_min / trade_count_min は **変更しない**
- **禁止事項 5 (やたらに複雑)**: NSGA-II / 大規模 refactor は Phase 2-3 で扱う。 Phase 1 は最小スコープ
- **禁止事項 8 (値伝搬漏れ)**: archive schema 拡張は 4 点セット遵守

### 前提検証 (C4)

- **前提 1**: Lo (2002) SE 公式は trade-level Sharpe にも適用可能 → 元論文では daily return Sharpe が想定だが、 サンプル独立性を仮定すれば trade-level でも N=trade_count として近似可。 ただし autocorrelation がある場合は SE が過小評価される (要観察)
- **前提 2**: archive `trade_count` は Stage A 60日のみ計測 → 確認済み (collect_stage_a で書き込み、 stage_b は別 column へ)
- **前提 3**: trade_count_full_dataset は Stage A + Stage B trade の合算で計算可能 → fold-level trade はあるが Stage B 全体 backtest は別途必要 → 詳細設計で具体化
- **前提 4**: bars_holdout が config holdout_days と一致しないのは run-52 で確認済み (14日 vs 60日)。 stage_partition_guard で検証可能

---

## スコープ外 (Phase 2 以降)

- **DSR を hard gate 化** (現状 monitor only 維持、 archive に記録のみ)
- **median_oos_sharpe_min の SE-aware 動的補正** (まずは固定値 0.025 sweep。 SE-based 動的閾値は Phase 2)
- **Niching / clauses ハッシュ duplicate penalty** (Phase 1 別タスク #2 で別途設計)
- **plateau adaptive mutation の GA 配線** (Phase 2 タスク)
- **NSGA-II 多目的最適化** (Phase 3 タスク)
- **Stage C 評価機構の本格再設計** (Phase 2-3 タスク、 dataset 延長と並行)
- **mission criteria 自体の変更** (使命変更は別議論)
- **archive_role / source_stage の埋め込み** (F10 indicates always null but separate cleanup task)

---

## 関連ファイル

### 主要変更対象

- `src/alpha_factory/stage_gate.py` (`evaluate_stage_b`, `StageGateConfig`, line 950-1300)
- `src/alpha_factory/stage_partition_guard.py` (`validate_stage_partition`)
- `src/alpha_factory/archive.py` (`GENOMES_SCHEMA`, `_create_row_template`, `collect_stage_*`)
- `scripts/alpha_factory/run_ga.py` (`IndividualCacheEntry`, `_update_cache`, selection_score)
- `src/alpha_factory/config.py` (config loader)
- `config/alpha_factory/default.yaml` (`stage_gate.stage_b.median_oos_sharpe_min`)

### 参考資料

- Lo, A. W. (2002). "The Statistics of Sharpe Ratios". Financial Analysts Journal, 58(4), 36-52.
- Bailey, D. H. & López de Prado, M. (2014). "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality". The Journal of Portfolio Management, 40(5), 94-107.
- `devnotes/20260508-1130-post20run-investigation/codex-discussion-summary.md` (Codex Q1-Q8 議論結果)
- `docs/alpha_factory/sharpe-rescale.md` (T042 trade-level vs annualized 換算)
- `docs/alpha_factory/stage-gates.md` (Stage A/B/C 設計 SSOT)

---

## 検証計画

### 設計検証 (Phase 1 実装前)

- run-52 archive (`.cache/alpha_factory/runs/genomes_run_20260507_112309.parquet`) を **コードフリーで replay 試算**:
  - median_oos_sharpe>=0.025 適用 → mission-eligible 7 個体のうち何件が pass するか確認
  - 期待: g70_i9 (pfre=0.7) と g83_i12 (pfre=0.7) は positive_fold_ratio>=0.6 で AND 条件を満たす可能性
  - g71_i36 / g72_i64 / g89_i36 / g88_i12 / g65_i88 (pfre=0.4-0.5) は positive_fold_ratio<0.6 で別途引っかかる

### 実装後の RUN 検証

次 RUN (Phase 1 完了後) で:
- **成功条件**: `Stage B pass + total_pnl>=50,000 + trade_count>=50` の個体が **1 件以上** 出現 (= 使命達成 1 件)
- **副次条件**: archive `dsr` が non-null で記録されている / `trade_count_full_dataset` 列存在
- **失敗条件**: graduate=0 が継続 → Phase 1 タスク #2 (niching) を含めて再 RUN
- 同 seed (seed=42 が望ましい) で baseline 比較

### 反証可能性 (C9) — Round 2 修正版

**Round 2 指摘**: H_A1 が「7/7 pass」 で過大、 設計本文の「5件は positive_fold_ratio<min も blocked」 と矛盾。 H_A3 は single RUN で stochastic noise と区別不能。 修正版を以下に示す。

- **仮説 H_A1' (修正版)**: run-52 archive の mission-eligible 7 個体のうち、 **`positive_fold_ratio<min` が blocking reason に含まれない** 2 個体 (g70_i9 pfre=0.7, g83_i12 pfre=0.7) は median_oos_sharpe_min=0.025 適用で **少なくとも 1 件以上 Stage B pass する**
  - 反証: replay で 0 件 pass なら、 median 推定値が 0.025 未満で blocked されている (より低い閾値、 例 0.0 が必要) → gate 設計を再検討
  - g70_i9 / g83_i12 は positive_fold_ratio_effective=0.7 が pfre threshold 0.6 を超えており、 median のみ blocked と推定可能

- **仮説 H_A2 (改題: pfre AND 確認)**: g70_i9 / g83_i12 の Stage B blocking reasons に `positive_fold_ratio<min` が **含まれない** ことを archive `stage_b_reason_codes` で verify
  - 反証: 含まれていれば、 median 緩和だけでは pass しない (positive_fold_ratio gate も別途緩和が必要)
  - run-52 archive の `stage_b_reason_codes` 列を読めば即時確認可能 (replay 不要)

- **仮説 H_A3' (修正版)**: archive replay の **top-K (K=20) selection before/after** で、 trade>=120 over-trading 個体の比率が **20% 以上低下する**
  - **before**: 現行 selection_score (feasible=Stage A trade>=50) で archive ranking、 top-20 の trade>=120 比率測定
  - **after**: 新 selection_score (feasible=trade_count_full_dataset>=50) で archive ranking、 top-20 の trade>=120 比率測定
  - 反証: 比率変化 <20% なら、 selection 圧整合化の効果が低い (別の selection 要素が支配)
  - **single RUN ではなく archive replay** での測定 → stochastic noise なし

- **仮説 H_A4 (新): Stage B pass 人口の trade 数中央値**
  - **期待**: 新 gate 適用 archive replay で Stage B pass 個体の trade_count 中央値が現行 (15) から 50 以上に上昇
  - 反証: 中央値変化 <30 なら、 gate 緩和だけで feasibility 問題は解決しない
  - 統計検定: Mann-Whitney U test (n_before≈136, n_after は要 replay)

---

## 実装モード (Round 2 修正版)

Codex Round 2 [Suggestion]: Phase 1 に threshold / DSR / selection / partition guard を同時投入すると原因帰属が濁る。 段階適用順序を以下に再整理。

| 項目 | 内容 |
|------|------|
| 推奨モード | **incremental** (4 段階で段階適用、 Round 2 推奨順序を採用) |
| 実装順序 | (1) **threshold replay** (median_oos_sharpe_min=0.025 + archive replay 検証、 副作用なし) → (2) **trade_count_full_dataset 定義** (archive 列追加、 selection 切替、 schema bump) → (3) **DSR monitor** (per-fold 計算 + archive 列追加) → (4) **partition guard** (holdout_days 検証、 二重 opt-in escape hatch) |
| 各段階の独立検証 | 段階 (1)→(4) の各段階で archive replay または unit test で副作用ゼロ確認 |
| 競合リスク | Phase 1 タスク #2 (niching) と selection_score 変更で軽微競合 (selection_score schema bump で差分マージ可能)。 別ブランチで段階マージ |
| 想定実装時間 | 中〜長 (各段階 1.5-3 hours、 計 8-12 hours) |
| Codex review | 各段階で 1 回 (詳細設計で全体合議 → 各段階の実装で段階レビュー) |

---

## 成功判定 (Round 2 修正版)

Round 2 指摘: 成功条件が Stage B pass に寄りすぎ。 Stage C / live_criteria / cross-pair ii-lite を明示せよ。

### Layer 1: Replay 検証 (Phase 1 実装直後)

1. ✅ run-52 archive replay で mission-eligible 個体 (g70_i9 / g83_i12) のうち **1 件以上**が改訂後の Stage B gate (median>=0.025 + pfre>=0.6) を通過する
2. ✅ archive replay の selection ranking で trade>=120 over-trading 個体の top-20 比率が 20% 以上低下する (H_A3')
3. ✅ archive `dsr` / `dsr_method` / `dsr_n_trials` / `dsr_observations` / `dsr_skew` / `dsr_kurtosis` / `dsr_valid` が non-null で記録される (valid=True 個体に限る)
4. ✅ archive `trade_count_full_dataset` / `trade_count_stage_a` / `trade_count_stage_b` が non-null で記録される
5. ✅ stage_partition_guard が holdout_days 不整合を起動時に fail-closed する (二重 opt-in escape hatch のみで bypass 可)

### Layer 2: 次 RUN 検証 (Phase 1 完了後の最初の本格 RUN)

6. ✅ Stage B pass 個体の trade_count 中央値が 15 (run-52) → **50 以上**に上昇 (H_A4)
7. ✅ Stage B pass 個体のうち **trade_count_full_dataset >= 50 かつ total_pnl_stage_a >= 50,000** な個体が 1 件以上出現
   - これは「Stage A 期間で mission criteria 達成 かつ Stage B でも fold robustness 確保」 個体の出現を意味する

### Layer 3: 使命達成判定 (Phase 1 + 後続 Phase の累積効果)

**注**: Phase 1 単独で使命達成 (Stage C pass + cross-pair ii-lite pass + live_criteria 全充足) を期待しない。 Stage C 14日問題 (Phase 2 タスク) と mode collapse (Phase 1 タスク #2 niching) の解決と組合せて初めて mission graduate。

Phase 1 単独で達成すべきは以下の **必要条件** (十分条件ではない):
- Stage B pass + trade>=50 の個体が出現 (現状は構造的に 0)
- → これが達成されれば、 後続 Phase 2 で Stage C 評価機構を整えれば graduate に至る

**使命達成 (使命定義による)**: live_criteria 全指標同時充足 + Stage C pass + cross-pair (ii-lite) pass。
- Phase 1 の貢献: Stage B 評価で「真の robust + feasible」 個体を見落とさない gate に整合化
- Phase 2-3 の貢献: Stage C / cross-pair ii-lite の評価機構を有効化し、 graduate 経路を完成させる

### 反証 (失敗判定)

- Layer 1 の (1) で 0 件 pass → gate 仮説 (H_A) が弱い、 別の根因を再調査
- Layer 2 の (6) で trade_count median が 30 未満 → trade_count_full_dataset 整合化の効果不足、 selection_score 全体の再設計が必要
- Layer 2 の (7) で 0 件 → Phase 1 タスク #2 (niching) の前倒し実装が必要
