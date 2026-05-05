# 概念設計: Stage A/B fold disjoint 化 + Stage Partition fail-closed guard

## 本設計の位置づけ（Round 1 review 反映）

**live_criteria 達成への直接効果は持たない**。本設計は「現状の Stage B 判定が IS の再分解になっている偽陽性源を構造的に排除し、改善ループを正常化する」変更である。期待効果は使命達成寄与ではなく**評価基盤の整合化**であり、成功判定は数値改善ではなく**構造条件の達成**で行う（成功判定の具体は「成功条件」セクション参照）。

López de Prado (2018) Ch.7 は purged k-fold CV と embargo を提唱しているが、本設計はそれを完全導入するものではない。あくまで **IS と OOS の disjoint 性という基礎契約**の最低限の実装担保である。

---

## 背景・課題

### 直前の Run 33 リーク監査で確認された致命的構造汚染

[reports/run-reports/run-33.md](../../reports/run-reports/run-33.md) を対象に、コードとデータ両側からリーク監査を実施したところ、**バーレベルの未来参照型リークは無い**ものの、Stage A IS と Stage B "OOS" fold の重複による**選択汚染（selection-induced contamination）** が定量的に確認された。

### 観測された事実（Run 33 / EUR_JPY / 2025-10-01〜2026-04-01）

1. `bars_stage_a = bars_stage_b[-86400:]` で Stage A は Stage B 末尾の単純スライス [scripts/alpha_factory/run_ga.py:497-498](../../scripts/alpha_factory/run_ga.py#L497-L498)
2. DB 実値検証:
   - Stage B: 156 trading days (2025-10-01 〜 2026-03-31)
   - Stage A: 73 trading days (2026-01-06 〜 2026-03-31, Stage B 末尾のサブセット)
3. Stage B walk-forward (train=60, test=10, step=10, embargo=1) で 9 fold 生成、各 fold test 区間の Stage A 重複率:

   | fold | test (trading day index) | Stage A 重複率 |
   |---:|:---|:---|
   | 0 | [61, 71) | 0% |
   | 1 | [71, 81) | 0% |
   | 2 | [81, 91) | 80% (partial) |
   | 3 | [91, 101) | **100%** |
   | 4 | [101, 111) | **100%** |
   | 5 | [111, 121) | **100%** |
   | 6 | [121, 131) | **100%** |
   | 7 | [131, 141) | **100%** |
   | 8 | [141, 151) | **100%** |

   → 9 fold 中 6 fold (66.7%) が Stage A 完全内部、計 6.8/9 fold ぶん重複
4. GA fitness = `trade_sharpe_raw` on Stage A IS（Run 33 best `g15_i7`: fitness_raw=0.1291=trade_sharpe_raw）
5. Stage B 各 fold は `run_backtest(test_bars, ...)` で同じ genome を test_bars だけで再評価（fold ごとの train_bars は完全未使用、embargo は機能していない可能性あり — **要一次確認 / Round 1 留保**）
6. 結果: Stage B 通過判定の `median_oos_sharpe` / `positive_fold_ratio` は**独立 OOS 統計ではなく、GA が選択した IS 統計の再分解**になっている

### Round 1 留保事項

以下は本概念設計の直接的根拠だが、概念設計レビュー時点で **Codex 側からの一次確認は未取得**。詳細設計フェーズで確認する:
- `docs/alpha_factory/` 配下の Stage A/B/C 契約明文
- `devnotes/` の Stage B 設計意図（特に train_bars が概念上どう扱われる前提か）
- `git log -S "bars_stage_b"` での意味変更履歴

これらの一次確認が前提を覆した場合、本設計は再評価となる。

### zenigame 参照実装との比較で失われている防御層

[/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/runner/_runner.py:1953-2065](../../../zenigame/src/trading/alpha_factory/runner/_runner.py#L1953-L2065):
- `date_sampler.set_exclude_dates(c_date_set | oos_date_set)` で GA 用 pool から OOS 期間を**強制除外**
- [_holdout.py:13-34](../../../zenigame/src/trading/alpha_factory/runner/_holdout.py#L13-L34) `validate_holdout_protection` で起動時 fail-closed CI guard

zenigame-fx には**両方とも存在しない**。bars_stage_b 全体が GA に露出し、起動時の holdout 保護検証も無い。

### 設計前提の bullet 化（C4 反映）

- **前提 A**: `stage_a_window_days=60` の取り扱いは現実装で `_BARS_PER_DAY=1440` × 60 = 86400 minute-bars であり、FX 24×5 営業のため**実 trading 日数で約 73 日**となる（暦 60 日 ≠ 取引 60 日）。この換算契約は現状コードで暗黙化されており、本設計はその暗黙契約を**追認した上で disjoint 化**を導入する。換算契約自体の見直しは**スコープ外**。
- **前提 B**: 6m データセット（2025-10-01〜2026-04-01）の trading 日数は約 156 日（DB 実測）。
- **前提 C**: `make_wf_folds(bars, train_days=T, embargo_days=E, test_days=Te, step_days=S)` は `(N - (T+E+Te))/S + 1` 個の fold を生成（observed-day index ベース、[walk_forward.py:48-69](../../src/alpha_factory/walk_forward.py#L48-L69)）。

前提 A〜C が成り立つ条件下で、本設計の効果と副作用は次節以降で記述する。前提のいずれかが破れる場合は別 TODO で再評価する。

## 改善アイデア

**最低限の修正として 2 点を同時導入**（致命度の高い構造汚染源を排除）:

### A. Stage A / Stage B fold を時系列上 disjoint にする

`bars_stage_b`（Stage B fold および IS monitor 用）から末尾 Stage A 期間を**除外**する。

| | 現状 | 修正後 |
|---|---|---|
| `bars_stage_a` | `[end - stage_a_window, end)`（末尾固定） | 同左（変更なし） |
| `bars_stage_b` | `[start, end)`（全期間 = Stage A を内包） | `[start, end - stage_a_window)`（Stage A 期間を除外） |
| `bars_holdout` | `[end, end + holdout_days)` | 同左（変更なし） |

これにより:
- Stage B fold tests は時系列上 Stage A と完全 disjoint
- GA が選択している Stage A IS の bars は Stage B fold で一切再評価されない
- Stage B IS monitor (`run_backtest(bars_stage_b, ...)`) も短縮された Stage B のみを観測

### B. Stage Partition 整合性の起動時 fail-closed guard（強化版）

Round 1 [Critical] / Round 2 [Critical] 反映: 「holdout 侵入検知」だけではなく Stage A↔B↔Holdout の三者 partition 整合性検証であるため、命名・モジュール構成は **stage partition** で統一する（旧称 `holdout_guard` / `HoldoutLeakError` は不採用）。

#### B-0. 入力健全性検査（B-1 の前提条件、必須）

`bundle = LaneBarsBundle(bars_stage_a, bars_stage_b, bars_holdout)` の各 stage に対し以下を先に検証:

1. `non_empty`: 各 stage が空でない（**本 TODO では holdout も含めて 3 stage すべて必須**。Alpha Factory の Stage C / holdout 保護を最優先とする方針で、optional 化は将来 TODO で別途検討）
2. `timezone`: すべての `bar_time` が tz-aware かつ UTC（`utcoffset() == timedelta(0)`）
3. `not_null`: `bar_time` に NaT / None が無い
4. `monotonic`: 各 stage 内で `bar_time` が単調増加
5. `unique_within_stage`: 各 stage 内で `bar_time` が一意（重複なし）

これらが破れている場合は B-1 検証に進まず、**`StagePartitionInputError(RuntimeError)`** で raise（B-1 の境界・集合条件と意図を分離するため別例外型）。

#### B-1. partition 整合性条件（必須、すべて満たすこと）

B-0 通過後、以下を検証:

**境界条件（chronological partition の検出）**:

1. `max(stage_b.bar_time) < min(stage_a.bar_time)`（B が A より時系列で前 = 修正 A の構造条件）
2. `max(stage_a.bar_time) < min(stage_holdout.bar_time)`（A が holdout より時系列で前）
3. `max(stage_b.bar_time) < min(stage_holdout.bar_time)`（B が holdout より時系列で前。1 と 2 から導出可能だが冗長 fail-fast）

**集合条件（exact timestamp contamination の検出）**:

4. `set(stage_a.bar_time) ∩ set(stage_b.bar_time) == ∅`（A と B に同一 timestamp が無い）
5. `set(stage_a.bar_time) ∩ set(stage_holdout.bar_time) == ∅`（A と holdout に同一 timestamp が無い）
6. `set(stage_b.bar_time) ∩ set(stage_holdout.bar_time) == ∅`（B と holdout に同一 timestamp が無い）

**冗長性の意図（Round 2 [Warning] 反映）**:
- 境界条件 1-3 は「stage 間の chronological order」を検出
- 集合条件 4-6 は「同一 timestamp の混入」を検出（理論上、bar_time の monotonic 単調増加と境界条件が両方成立すれば集合条件は満たされるが、片側 stage の DB クエリ範囲ミスや bar_time 重複バグを早期検出するための独立 fail-fast）

#### B-2. 違反時の挙動

- B-1 のいずれか違反時は **`StagePartitionLeakError(RuntimeError)` を raise**（fail-closed、escape hatch なし）
- error message には違反した条件番号・該当する具体的 bar_time（最大 3 個まで）を含む
- 起動シーケンス（`_load_lane_bars` 直後）で必ず実行される

#### B-3. 将来の Stage A 確率化との関係（Round 2 [Warning] 反映）

本 TODO は「Stage A 末尾固定」を前提に chronological order（境界条件 1-3）を検証する。**Stage A 位置を確率化する別 TODO 着手時には、境界条件 1（B が A より前）を撤去し、disjoint-only guard（集合条件 4-6 + Stage C 順序のみ）に再設計が必要**。本 TODO の guard は将来の前提変更に対する書き換えポイントを明示する形で実装する（コメント or 構造上の分離）。

#### B-4. 二契約分離（Round 1 [Critical] 反映）

zenigame の参照実装では「partition 侵入検知」と「OOS sampling pool からの除外」は別契約。本設計では:

- **本 TODO の責務**: 上記 B-1 の partition 整合性検証（侵入検知）。
- **別 TODO の責務**: GA selection 用の sampling pool から Stage B fold test 期間相当を除外する仕組み（zenigame の `set_exclude_dates` 相当）。これは確率化 / Stage A 動的位置決めとセットで議論する。

本概念設計は**侵入検知のみ**を導入し、sampling pool 除外契約は別 TODO に分離する。

## 期待効果（観測項目に格下げ、Round 1 [Warning] 反映）

### live_criteria 達成への寄与

直接的寄与は無い。**偽陽性源除去による改善ループの正常化**が間接効果。

### 観測項目（成功判定とは別）

以下は**変更後に観測されることを期待する項目**であり、改善成功の判定基準ではない:

1. Stage B `n_fold_effective` の母数が現在 9 → 修正後 約 2 に減少
2. Stage B pass 個体数の急減（現在の Stage B pass は IS 重複によるもの、という説明の検証）
3. Stage A IS Sharpe と Stage B IS monitor Sharpe の値が乖離（現在 Run 33 best で 0.1291 vs 0.1263 でほぼ一致 → disjoint 化後は別期間の評価値となる）

これらは**観測**であり、数値の上下動それ自体は成功・失敗を意味しない。

### 受け入れる副作用（Round 1 [Critical] 反映）

- **Stage B 判定力の低下**: 2 fold での `median_oos_sharpe` / `positive_fold_ratio` は探索上の暫定ゲートに留まり、**強い統計的解釈はしない**。
- **偽陰性 / 高分散判定の増加**: ゲートが偽陽性を減らす代わりに、生存戦略を過剰に弾く可能性がある。これは改善ループの**学習速度低下**につながり得るが、汚染除去のために容認する。
- **後続 TODO 候補の整理**: 上記副作用を緩和する次段の方策として以下 3 択を準備:
  1. dataset 期間の延長（24m 化）
  2. Stage A 期間の短縮（73 日 → 30〜45 日）
  3. Stage B gate ロジックの再設計（INCONCLUSIVE 状態の導入、bootstrap CI 等）

これらは本 TODO 完了後、Stage B が真の OOS として機能した状態の観測値に基づき優先順位を決める。

### `n_fold_effective < 3` 時の inconclusive 伝搬（Round 2 [Critical] / Round 3 [Warning] 反映）

「report 表示にしか伝搬しないと downstream consumer が誤読する」という指摘に基づき、summary レベルまで構造データとして伝搬させる:

- **summary.json**: Stage B 評価結果ブロック（既存の `n_fold_effective` と同じ階層）に `stage_b_statistical_inconclusive: true|false` フラグを追加（`n_fold_effective < 3` で true）。複数 candidate / lane 構造を扱う場合は candidate ごと / lane ごとに本フラグを持つ
- **archive parquet schema**: 既存の `n_fold_effective` 列が残るため新規列追加なし。**archive 単体 consumer は `n_fold_effective < 3` 判定で同等の inconclusive 判定が可能であることを docs に明記**（summary フラグは「正本」ではなく「事前計算済み convenience」と位置づける）
- **archive metadata 必須化**（Round 3 [Warning] / Round 4 [Warning] 反映、契約強化）: archive parquet の metadata に `stage_gate_version` および `bars_stage_b_excludes_stage_a: bool` を**必ず記録する（summary 経由の代替は不可）**。記録されていない既存実装の場合は本 TODO で metadata 追加を施策化。archive 単体 consumer の誤読防止のため、本契約は弱化しない
- **run report**: summary フラグを参照して Stage B verdict 表示に「statistical inconclusive」注記を付ける

archive schema（列定義）変更は避け、metadata（key-value）の追加で対応する（schema 変更による波及を最小化）。

## 成功条件（構造条件 / Round 1 [Warning] 反映）

数値改善ではなく、以下の構造条件で成功を判定する:

1. **disjoint 性**: 任意の dataset configuration で `set(stage_a.bar_time) ∩ set(stage_b.bar_time) == ∅` がテストで verified
2. **partition 侵入時の fail-closed**: B-0 違反時は `StagePartitionInputError`、B-1 各条件違反時は `StagePartitionLeakError` が必ず raise されることがテストで verified
3. **既存テスト退行ゼロ**: 既存の Stage A/B/C 評価テストが通る（壊れる場合は意味的に妥当な範囲で update され、変更理由が PR に記録される）
4. **運用ログ可観測性**: bundle 構築完了時のログから `bars_stage_a` と `bars_stage_b` の `[first, last]` bar_time が読み取れ、disjoint 性が即時確認できる

## 実装方針（概要）

### 変更コンポーネント

1. [scripts/alpha_factory/run_ga.py](../../scripts/alpha_factory/run_ga.py) `_load_lane_bars`
   - `bars_stage_b` 構築時に末尾 `stage_a_n_bars` 本を除外
   - 除外結果が空（dataset 不十分）なら明示的 RuntimeError
2. 新規モジュール `src/alpha_factory/stage_partition_guard.py`（zenigame `_holdout.py` 相当だが zenigame-fx では partition 全体の integrity を扱うため命名を変更）
   - `validate_stage_partition(bundle) -> None` （違反時 `StagePartitionLeakError` raise）
   - `class StagePartitionLeakError(RuntimeError): ...`（B-1 違反）
   - `class StagePartitionInputError(RuntimeError): ...`（B-0 違反）
   - 起動シーケンスから呼び出し
   - docstring に「zenigame `_holdout.py` 相当、ただし holdout だけでなく Stage A↔B↔Holdout 三者の partition integrity を検証する」と明記
3. ログ出力強化
   - `_load_lane_bars` 完了時に `stage_a` / `stage_b` / `holdout` の `[first_bar_time, last_bar_time]` を info ログ出力
   - structured log のキー名は `stage_a_bar_first/last` / `stage_b_bar_first/last` / `holdout_bar_first/last` を採用（ログ集約系での grep を容易にする）

### 波及範囲（Round 1 [Warning] 反映）

`LaneBarsBundle.bars_stage_b` の意味変化（「全期間」→「Stage A を除く Stage B」）が触れる箇所:

| 系統 | 該当箇所 | 必要な対応 |
|---|---|---|
| summary.json | `_summary["dataset"]["bars_stage_b"]` 出力 ([run_ga.py:914-916](../../scripts/alpha_factory/run_ga.py#L914-L916)) | bar 数のみ記録、意味変化を `dataset.bars_stage_b_excludes_stage_a=true` フラグで明示。Stage B 評価ブロックに `stage_b_statistical_inconclusive` フラグも追加 |
| stage_gate | `evaluate_stage_b(bars_18m, ...)` の `bars_18m` argument ([stage_gate.py:908+](../../src/alpha_factory/stage_gate.py#L908)) | **引数名 `bars_18m` → `bars_stage_b`**（"18m" は実態と乖離）。**スコープは `evaluate_stage_b` 周辺の semantic rename に限定**（呼び出し元 / 同関数の docstring / 関連テスト / fixture）。historical naming のグローバル cleanup（grep 全件検出など）は別 TODO に逃がす。実装時の網羅性は `git grep -n "bars_18m" -- 'src/' 'tests/' 'scripts/alpha_factory/'` のスコープで確認 |
| report | `generate_run_report.py:345` の `bars_stage_b` 値出力 | summary 経由で取得、追加対応として「Stage B excludes Stage A window」一行注記、`stage_b_statistical_inconclusive=true` 時に Stage B verdict に注記 |
| logger | run_ga.py 起動時 log と bundle 構築 log | structured log key を `stage_a_bar_first/last`, `stage_b_bar_first/last`, `holdout_bar_first/last` に統一、disjoint 性が grep で即確認可能に |
| archive | parquet schema には bar 数記録なし、`stage_gate_version` は既存メタとして書かれるか要確認 | **詳細設計で確認必須**: archive metadata に `stage_gate_version` および新規 `bars_stage_b_excludes_stage_a: bool` が記録されるかを点検。記録されない場合は metadata に追加する変更を施策に含める（schema 変更を避けたい場合は summary 経由で代替） |
| calibrate-gate history | `stage_gate_version` の version bump | **実施**（Round 2 [Suggestion] 反映、原則 → 実施に格上げ）。Stage B 指標の意味が変わるため過去 history が新条件下で誤適用されるのを防ぐ。例: `"v3_stage_b_fold_min_trade_count" → "v4_stage_b_disjoint"` |
| cross_pair / ii-lite | Stage C 評価系で Stage B 結果を入力に使う経路 ([cross_pair.py](../../src/alpha_factory/cross_pair.py)) | **詳細設計で確認必須**: cross-pair / ii-lite 評価が Stage B summary を参照する経路があるか grep で確認。参照あれば `stage_b_statistical_inconclusive` および `bars_stage_b_excludes_stage_a` の伝搬経路を施策に追加 |

### 運用者の誤解防止（Round 1 [Warning] / Round 2 [Suggestion] 反映）

意味変化を運用者に明示するため、以下を導入:

- summary.json に `dataset.bars_stage_b_excludes_stage_a: true` フラグ追加（Round 2 [Suggestion] で `bars_stage_b_disjoint` から rename、意味がより直接的）
- summary.json に `stage_b_statistical_inconclusive: bool` フラグ追加（`n_fold_effective < 3` で true）
- run report の dataset セクションに「Stage B excludes Stage A window」一行追加、Stage B verdict 表示に inconclusive 注記
- 起動 log の key 名は `stage_a_bar_first/last`, `stage_b_bar_first/last`, `holdout_bar_first/last` に統一

### 変更しない範囲

- Stage gate 設定値（threshold, window, min_folds 等）
- Stage A の位置決め（末尾固定のまま、確率化は別 TODO）
- Stage B fold 生成ロジック（`make_wf_folds` 自体は変更なし、入力 bars が短縮されるのみ）
- Stage C / holdout 取得ロジック
- aux loader / preflight
- fold ごとの train_bars 利用ロジック（WF が strict walk-forward でない可能性は別 TODO で扱う、本設計は留保のみ）

### テスト計画

- `_load_lane_bars` の disjoint 性を assert する単体テスト（成功条件 1）
- stage partition guard の正常系（B-0 / B-1 全条件満たす）/ 異常系（B-0 各項目で `StagePartitionInputError`、B-1 条件番号別に `StagePartitionLeakError` raise）のテスト（成功条件 2）
- 既存 Stage B fold テストで `bars_stage_b` 全期間前提のものを事前 grep でリストアップし、disjoint 化に伴う必要 update を施策内に明示（成功条件 3）
- 起動 log 出力テスト（成功条件 4）

## スコープ外（Round 1 反映で再整理）

以下は別 TODO として分離（明示的に今回扱わない）:

1. Stage A 位置の確率化（毎 generation での sampling 切替）
2. Stage C multi-window / bucket rotation（zenigame T454 相当）
3. audit_dates / mixing window の実装
4. fitness_metric の見直し（`total_pnl=0` でも sharpe>0 を許す問題、Run 33 g15_i7 の整数 JPY round 0 問題）
5. WF fold で train_bars を使わない問題の解消（per-fold parameter fitting の導入 or WF 用語撤去）
6. 設定名のリネーム（`stage_a_window_days` の trading day vs calendar day 不整合 — 60日設定が実 trading 73日になる問題、前提 A の暗黙契約の明示化）
7. dataset 拡張（24m 化）の検討
8. calibrate-gate cross-run history の dataset_epoch_id 不整合修正
9. **GA selection 用 sampling pool からの OOS 期間除外**（zenigame `set_exclude_dates` 相当 = 本設計の B-3 で分離した契約）

これらは本 TODO 完了後、Stage B が真の OOS として機能する状態で観測した結果に基づき優先順位を再評価して着手する。

## 参考

- 監査根拠: 本セッション直前で完了した Run 33 リーク監査（コード+データ両側）
- zenigame 参照実装:
  - `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/runner/_runner.py:1953-2065` (date_sampler.set_exclude_dates)
  - `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/runner/_holdout.py:13-34` (validate_holdout_protection)
- zenigame-fx 該当コード:
  - `scripts/alpha_factory/run_ga.py:_load_lane_bars` (lines 426-507)
  - `src/alpha_factory/stage_gate.py:evaluate_stage_b` (lines 908+)
  - `src/alpha_factory/walk_forward.py:make_wf_folds` (lines 72-164)
- 学術根拠: López de Prado, M. (2018) *Advances in Financial Machine Learning*, Ch.7 (purged k-fold cross-validation, embargo)。本タスクは同書の完全導入ではなく、IS と OOS の disjoint 性という基礎契約を実装で担保する最低限の措置。
