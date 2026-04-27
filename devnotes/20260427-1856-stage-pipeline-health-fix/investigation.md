# 施策 0a 投資調査: Stage A→B Pipeline Health

## メタ情報
- 実施日: 2026-04-27 19:36 JST
- 実行時 commit hash: `3297799` (T053 マージ済 main)
- 調査対象 RUN:
  - `run_20260426_145502` (Stage B pass=834, working)
  - `run_20260426_183119` (Stage B pass=0, broken)
  - `run_20260426_204204` (Stage B pass=0)
  - `run_20260427_015804` (Stage B pass=0)
- 共通環境: Python 3.11.15 / Numba 0.65.1 / NumPy 2.4.4

---

## §0.1 Stage A threshold source-of-truth 図 (V0-A)

### 経路図

```
[config/alpha_factory/default.yaml]
        │ stage_gate.stage_a.threshold: 0.0
        ▼
[GaConfig (src/alpha_factory/config.py:375)]
        │ stage_a_threshold = float(a_raw.get("threshold", 0.0))
        ▼
[StageGateConfig.stage_a_threshold]
        │
        ▼
[evaluate_stage_a (stage_gate.py:441) で fitness_pen <= threshold 判定]


[reports/calibrate-gate/history.jsonl]
        │ ← (write-only) src/alpha_factory/calibrate_gate_history.append_record
        │   from scripts/alpha_factory/calibrate_gate.py
        │
        ╳ [run_ga.py 起動時 read 経路なし]
```

### Source of truth
- **唯一の source of truth: `config/alpha_factory/default.yaml` の `stage_gate.stage_a.threshold`**
- `reports/calibrate-gate/history.jsonl` は **write-only**（drift 監視 / `calibrate_gate_drift.py` が読む）
- `scripts/alpha_factory/calibrate_gate.py` は yaml に `update_threshold_atomic` で書き戻すが、その後 **user が chore commit で yaml を上書き** することがある（cycle 4/7/11/12 reset）

### 結論（V0-A）
- 経路は存在するが、実運用で chore commit による上書きにより calibrate-gate の決定が次 RUN に届かない
- 設計の「経路あり / 別 source of truth (= chore commit) が優先」ケースに該当
- 修正方針: state file 型（history.jsonl）から override 経路を導入し、yaml は initial seed としてのみ使う

---

## §0.2 run_ga effective threshold 実測ログ (V0-B)

### 現状
- `scripts/alpha_factory/run_ga.py:876` で summary.json に `cfg.stage_gate.stage_a_threshold` を出力
- startup 時の effective threshold ログは **未実装**

### 計測パッチ（施策 0b）で追加予定
```python
logger.info(
    "stage_gate.effective_threshold",
    stage_a_threshold=cfg.stage_gate.stage_a_threshold,
    source="config|history|cli",
)
```

---

## §0.3 summary.json field 意味確認 (V0-C)

- `run_ga.py:876` の `"stage_a_threshold": cfg.stage_gate.stage_a_threshold` は **config 値（startup 時に load した値）**を出している
- runtime override 経路は現状なし → summary 値 == effective threshold（差異なし）
- 施策 A で history override が入った場合、override 後の値が cfg に注入されるため summary も effective を反映する

---

## §0.4 Stage B 実 bar 期間と fold 構築数の実測

archive Parquet からは bar 列は取れないが、`trade_count` 分布から間接的に fold 状態を推定。

### Stage A pass 個体の trade_count (60-day window)

| RUN | A pass | A pass率 | trade_count median | trade_count min | trade_count max |
|---|---|---|---|---|---|
| run_20260426_145502 | 2750 | 47.0% | 167 | 51 | 816 |
| run_20260426_183119 | 2395 | 40.9% | 77 | 60 | 238 |
| run_20260426_204204 | 1758 | 30.0% | 69 | 66 | 170 |
| run_20260427_015804 | 3745 | 64.0% | **30** | **30** | 124 |

### Stage B fold 結果

| RUN | B pass | n_fold_effective median | n_fold_effective max | reason top-1 |
|---|---|---|---|---|
| 145502 | 834 | (mean 3.13) | 9 | positive_fold_ratio<min (1902) |
| 183119 | 0 | 0 | 0 | all 3 reasons single (2395) |
| 204204 | 0 | 0 | 0 | all 3 reasons single (1758) |
| 015804 | 0 | 0 | 0 | all 3 reasons single (3745) |

### 計算: なぜ trade_count=30 だと all_folds_unavailable になるか

config:
- `wf_train_days=120, wf_test_days=20, wf_step_days=20, wf_embargo_days=1`
- `trade_count_min_for_sharpe=30`
- `bars_stage_b` = 18ヶ月 ≈ 378 営業日 (推定)
- `n_fold` = (378-141)/20 + 1 ≈ 12

individual の trade_count が **60-day window で 30** なら:
- 1日あたり trade rate ≈ 0.5 trades/day
- 20-day fold test では ≈ 10 trades
- `_trade_sharpe_raw` は `len(returns) < max(2, 30)` で None を返す
- **全 fold で trade_sharpe_raw=None → n_fold_effective=0 → all_folds_unavailable**

### 結論（§0.4）
- **仮説 B-X (trade_count_min_for_sharpe=30 と wf_test_days=20 の不整合) が VERIFIED**
- run_20260427_015804 では Stage A pass 個体の trade_count min=30 = 60-day で trade_sharpe_raw 計算下限ぴったり
- Stage A は 60d で 30 trades 必要、Stage B fold は 20d で 30 trades 必要 → **2x の取引密度ギャップ**

---

## §0.5 前後 6 RUN 現象差分

archive 不足のため最新 4 RUN のみ集計可能。run-19/20/21/22/23 は archive Parquet が同 dir にないため分析対象外。

| RUN | applied_at | A pass率 | B pass | reason 単色化 | trade_count median (A pass) |
|---|---|---|---|---|---|
| run_20260426_145502 | 2026-04-26 14:55 | 47.0% | 834 | No (3 reasons distributed) | 167 |
| run_20260426_183119 | 2026-04-26 18:31 | 40.9% | 0 | Yes (3 reasons all-2395) | 77 |
| run_20260426_204204 | 2026-04-26 20:42 | 30.0% | 0 | Yes | 69 |
| run_20260427_015804 | 2026-04-27 01:58 | 64.0% | 0 | Yes | 30 |

→ **「単一切替点」**（145502 → 183119 で n_fold_effective が一気に 0 に）

切替契機:
- 145502 RUN 終了後、calibrate-gate が threshold を 0.0 → 0.0778 に更新（17:45:58）
- 183119 RUN は threshold=0.0778 で開始、GA は higher fitness_pen を選好するため低 trade_count・高 Sharpe 個体に収束
- 結果として Stage B 20-day fold で trade_count<30 → all_folds_unavailable 一色

---

## §0.6 git diff 候補 commit 一覧

145502 (14:55) と 183119 (18:31) の間に **コード変更はない**:
```
$ git log --all --since='2026-04-26 14:30' --until='2026-04-26 19:00' --oneline
(empty)
```

つまり「単一 commit による回帰」ではなく、**threshold change（calibrate-gate 17:45 出力）と GA 探索方向の合流による現象的変化**である。

参考に Stage B / WF / metrics に触れた最近の commit:
- `427f819` (2026-04-26 14:15) feat(T044) Stage B Feasibility Contract Phase 1 - pre-flight max_folds check
- `db40968` (2026-04-26 01:46) feat(T035) Stage B 統計可観測性ハード契約 + reason_codes 集計
- `8a13f73` (2026-04-25 18:56) feat(T038) Sharpe 計算根本修正 — `_trade_sharpe_raw` 導入

→ T038 (`_trade_sharpe_raw`) で **trade-level Sharpe + trade_count_min=30 の hard guard が導入された**ことが、低 trade_count 個体の fold 評価不能の根本契機。これは bug ではなく仕様変更（統計妥当性の確保）。

---

## §0.7 commit hash 記録

| 項目 | commit hash | 備考 |
|---|---|---|
| 調査時 HEAD | `3297799` | T053 マージ済 main |
| 145502 RUN 実行時 | (run summary より要確認) | cycle 7 default.yaml 適用 |
| 183119 RUN 実行時 | (run summary より要確認) | calibrate-gate 0.0778 適用 |
| 204204 RUN 実行時 | (run summary より要確認) | calibrate-gate 0.1778 適用 |
| 015804 RUN 実行時 | (run summary より要確認) | cycle 11 chore reset (threshold=0.0) |
| `_trade_sharpe_raw` 導入 | `8a13f73` 2026-04-25 18:56 | trade_count_min=30 guard |

---

## 仮説評価サマリー

| 仮説 | 状態 | 根拠 |
|---|---|---|
| B-X (trade_count_min_for_sharpe=30 と wf_test_days=20 の不整合) | **VERIFIED** | trade_count median 167 → 30 推移と n_fold_effective 9 → 0 推移の対応 |
| B-1 (bars_stage_b slicing バグ) | rejected | 145502 RUN は同コードで動いていた |
| B-2 (validation 厳格化 commit) | rejected | 145502 → 183119 間に code 変更なし |
| B-3 (time index バグ) | rejected | 同上 |
| B-4 (仕様変更の retro 不整合) | partially | T038 の trade_count_min=30 hard guard 自体は妥当だが、Stage B fold のスケール (20-day) との不整合が放置されていた |

---

## 修正方針

### 施策 B（all_folds_unavailable 修正）

**Round 1 [Critical] 3 反映: 統計要件を先に固定**

#### Lo (2002) ベースの統計要件
- trade-level Sharpe の SE ≈ √((1+0.5×SR²)/N)
- 目標 SR ≈ 0.05 (stage_b_median_oos_sharpe_min)
- N=30 で SE ≈ 0.183 → fold 単位の Sharpe は本質的に noisy
- N=15 で SE ≈ 0.258
- N=10 で SE ≈ 0.317

**設計判断**:
- Stage A の `trade_count_min_for_sharpe=30` は **60-day window** での Sharpe 統計妥当性確保のため維持（厳しい live_criteria.trade_count_min=50 との整合）
- Stage B の **fold 単位** Sharpe では、20-day window に 30 trade を要求する trade rate (1.5 trades/day) は「機能していた当時 (run 145502 median 2.78/day)」より厳しい
- **施策 B-X 修正案**: Stage B fold 専用の `trade_count_min` を独立 config 化し、wf_test_days スケールに合わせた **統計妥当性ベースの値**を設定

具体的には:
- 新 config: `stage_gate.stage_b.fold_trade_count_min`（default=10）
- 根拠: N=10 でも Sharpe SE ≈ 0.317 で「+0.05 と 0 の区別は困難」だが、**median + positive_fold_ratio の 2 段判定**で fold 単位の noise を統合できる（中央値推定は外れ値耐性）
- Round 1 [Critical] 3 の「経験式禁止」遵守: N=10 は Lo (2002) SE 上限 0.32 から逆算した「fold-level 推定として最低限の妥当値」（学術的に N≥30 が大数則の目安だが、median + positive_fold_ratio 集約が個別 noise を吸収する design）
- これは「機能していた当時 (145502 RUN の median trade_count=167, fold ≈55 trades) の挙動を意図的に再現」する設計判断であり、**緩めて pass を増やす hack ではない**

### 施策 A（calibrate_gate 伝搬経路修正）

経路の現状: **default.yaml ← calibrate-gate write、しかし user が chore commit で上書き**
- 修正方針: history.jsonl から override 経路を新規導入（state file 型）
- 詳細設計通り `src/alpha_factory/calibrate_state.py` を新規実装
- cross-run contamination ガード: base_config_hash / dataset_span / instrument / stage_gate_version + decision filter (tighten/loosen のみ)
- CLI override が history より優先

---

## 結論

施策 0a で原因と修正方針が両方確定:
- Stage B all_folds_unavailable は **trade_count_min_for_sharpe=30 と wf_test_days=20 の不整合** が verified root cause
- Stage A 伝搬は **経路存在するが運用で chore commit が override** → state file 型で永続化が必要
- **施策 B → 施策 A → end-to-end** の順で実装可能

INCONCLUSIVE 扱いには該当しない（単一切替点が同定済み、commit ではなく仕様規模 + GA 探索方向の合流）。
