# T073 — Audit layer (DSR 先行 + PBO/SPA scaffold) 概念設計

**作成日時**: 2026-04-30 23:01 JST
**親 TODO**: T073 (synthesis § 18.2 T916 — Audit layer: DSR 先行実装 (zenigame `_dsr.py:126` 同等) + PBO/SPA は schema scaffold + 「未実装」 タグ)
**Milestone**: M6 開始 (T073 / T074 / T075 で M6 完了 → cascade port 設計 18 件完了)
**前提 commit**: `main@975a7ea` (T072 設計完了時点)

**関連設計 (前提)**:
- `devnotes/20260428-2300-cascade-port-debate/synthesis.md` § 10.2 / § 18.2 T916
- `devnotes/20260429-1912-todo-T058-schema-v2-contract/` (= T058 schema v2 / archive_role / source_stage / dataset_epoch_id)
- `devnotes/20260430-1810-todo-T070-backtest-engine-extension/` (= T070 SessionBlock / SessionBlockBucket)
- `devnotes/20260430-1925-todo-T071-observability/conceptual-design.md` § 4.2 (= RunObservabilityReport)
- `devnotes/20260430-2036-todo-T072-dst-holiday-boundary/conceptual-design.md` § 4.6 / § 4.7 (= SessionBlock 拡張、 collider bias 規範)
- 既存 zenigame-fx 実装: `src/alpha_factory/statistics.py:148` `deflated_sharpe_ratio` (Bailey & López de Prado 2014、 値域 [0, 1])
- 既存 archive schema: `src/alpha_factory/archive.py:81` (`pa.field("dsr", pa.float64(), nullable=True)` field 既存)
- zenigame 参照: `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/runner/_dsr.py:126` `calc_dsr` (= Φ 適用前 z-score、 zenigame v1)

---

**Round 2 概念レビュー反映 (2026-04-30 23:50 JST、 Round 3 改訂)**: C1-C5 / W1-W5 / S1-S4 全反映:
- Round R2 [C1]: `trial_counting_policy` SSOT 化 (= 「unique canonical genome_id」、 retry/fold/cache replay 別 trial にしない)
- Round R2 [C2]: Phase 1 で `AuditNullModelKind` から `archive_sample` を削除、 standard_normal のみ。 archive_sample は Phase 2 で追加と概念で明記
- Round R2 [C3]: standard_normal の位置付けを「Phase 1 monitor-only placeholder null」 と明示 (= Bailey 原著 null との区別)
- Round R2 [C4]: PBO/SPA scaffold から数値 field 削除 (= status + audit_calc_version のみ、 S3 採用)、 fail-closed 強化
- Round R2 [C5]: T073 PR で `audit.py` wrapper docstring に「数式は汎用、 v1/v2 尺度は null_model SSOT で固定」 を明記。 既存 statistics.py docstring 同期更新も DoD に
- Round R2 [W1]: stratification は marginal 集計デフォルト、 interaction は事前登録少数
- Round R2 [W2]: AuditGenomeRecord に sessionization_version / cost_model_version / pnl_net_calc_version provenance を Phase 2 で追加 (= Phase 1 では SessionBlock 内に保持前提、 T070 SSOT 整合)
- Round R2 [W3]: GenomeAuditInput.session_blocks は Phase 1 in-memory transport SSOT、 Phase 2 persistence は別 PR (T058 拡張時)
- Round R2 [W4]: AuditMetricStatus を `AuditDSRStatus` (5 値) と `AuditScaffoldStatus` (1 値) に分離
- Round R2 [W5]: AUDIT_REPORT_SCHEMA_VERSION bump 規約を概念で明記 (= MAJOR/MINOR/PATCH ポリシー)
- Round R2 [S1]: AuditNullModel に `sr_scale` field 追加
- Round R2 [S2]: AuditNullModel に `n_trial_candidates_raw` / `n_trial_candidates_unique` 区別
- Round R2 [S3]: 採用 (= 上記 [C4] と同義)
- Round R2 [S4]: C2 parallel-path grep を DoD に明記

## 0. 結論 (TL;DR、 Round 3 改訂)

T073 は新規 DSR 実装ではなく、 **既存 `deflated_sharpe_ratio` を v2 cascade port (= T058 schema v2 / T070 SessionBlock / T071 RunObservabilityReport) と整合する audit layer の純ライブラリ設計**:

1. **新規 module (純ライブラリ)**: `src/alpha_factory/audit.py` (= AuditNullModel / AuditDSRMetric / AuditPBOMetric (scaffold) / AuditSPAMetric (scaffold) / AuditGenomeRecord / RunAuditReport / compute_run_audit_report)。 **Phase 1 は library + 単体テストのみ**、 runtime / archive / report / RunObservabilityReport 拡張は **全て Phase 2 別 PR** (Round 1 [C1] [S4] 反映、 Phase 1/2 境界明確化)
2. **DSR 入力意味論を v2 移行**: `compute_audit_dsr_for_genome` で T070 SessionBlock の pnl_net 列 (= **`open_minutes > 0` の block のみ filter**、 Round 1 [C4] 反映) を Sharpe 入力源。 既存 `statistics.py:148` の `deflated_sharpe_ratio` を呼出 (数式不変)
3. **null model provenance を SSOT 化** (Round 1 [C2] [S2] 反映): `AuditNullModel` dataclass を新設、 `null_model_kind: Literal["standard_normal", "archive_sample"]` / `mean_sr_trials` / `std_sr_trials` / `trial_source` (= n_trials の母集合の provenance) / `n_trials` を一括保持。 Phase 1 default = `null_model_kind="standard_normal"` / `mean=0` / `std=1`、 `trial_source="run_evaluated_genomes"` (= **Round 1 [C3] 反映、 保守的な multiple testing correction**)
4. **n_trials SSOT** (Round 1 [C3] 反映): その Run で **performance selection 対象になり得た全評価 genome の数** = `trial_source="run_evaluated_genomes"`。 archive cardinality / Stage A 通過数を使うと survivor 条件付けで過少補正、 「全評価 genome」 が保守的で使命整合
5. **PBO / SPA は scaffold のみ**: `AuditPBOMetric` / `AuditSPAMetric` dataclass を新設。 status は `"not_implemented"` 固定、 値フィールドは **Decimal("0") 固定 sentinel** (Round 1 [C6] [S6] 反映、 NaN を避けて hash/eq/JSON round-trip 安全) + audit_calc_version="scaffold-v1"。 計算関数は status return のみ (NotImplementedError 投げない)。 Phase 2 で実装時の **field 追加余地** を schema comment で明示 (Round 1 [W5])
6. **early gate ではない**: synthesis § 10.2 厳密準拠
7. **collider bias 規範継承** (= T072 申し送り) + stratification key 候補を概念で固定 (Round 1 [W4]): `holiday_markets` 単独 drop 禁止、 stratification 候補 = `(holiday_markets, dst_transition_markets, schedule_status)` の任意組合せ、 caller responsibility
8. **archive 配線は Phase 2 で `dsr_v1` / `dsr_v2` 併存** (Round 1 [W2] 反映): 既存 `archive.py:81` `dsr` field は v1 入力で計算済、 Phase 2 では `dsr_v2` field 追加 + `dsr_v1` rename 保持 (= 履歴比較互換) + `sharpe_calc_version` 厳格運用
9. **status を 6 値に拡張** (Round 1 [C7] [S3] 反映): `ok / insufficient_data / insufficient_trials / degenerate_variance / input_non_finite / not_implemented` で観察事実を分離
10. **per_genome 集約は `AuditGenomeRecord`** (Round 1 [C5] [S1] 反映): `tuple[AuditGenomeRecord, ...]` で `genome_id`, `archive_role`, `source_stage`, `dsr_metric` を T058 と join 可能
11. **SessionBlock transport SSOT** (Round 1 [C8] 反映): T070 BacktestResult.session_blocks transport SSOT (= caller 再計算禁止) を継承、 audit は **archive admission 時に SessionBlock 列を保存して Run 末尾で audit 計算**。 Run 末尾再計算は禁止 (= sessionization version / cost model version の二重 drift 防止)。 詳細 transport 経路は Phase 2 別 PR で archive schema 拡張 (T058 申し送り)
12. **status field 方式継承** (= T071 SSOT)

---

## 1. T073 が解決する問題

### 1.1 synthesis § 10.2 / § 18.2 T916 で確定済の責務

| 項目 | synthesis 文言 | T073 対応 |
|---|---|---|
| DSR | 先行実装、 zenigame `_dsr.py:126` 同等 | 既存 `deflated_sharpe_ratio` 統合 + 入力 v2 化 (SessionBlock 駆動) |
| PBO (Bailey CSCV 2015) | 未実装タグ、 schema scaffold のみ、 smoke 後段階追加 | `AuditPBOMetric` (= status="not_implemented" sentinel) |
| SPA (Hansen 2005) | 未実装タグ、 schema scaffold のみ、 smoke 後段階追加 | `AuditSPAMetric` (= status="not_implemented" sentinel) |
| 配置 | archive / report 層 (= early gate ではない) | T073 では **selection 経路に touch しない**、 RunObservabilityReport 拡張のみ |

### 1.2 既存 zenigame-fx 実装との整合 (= 重要)

zenigame-fx には既に DSR 実装あり:

```python
# src/alpha_factory/statistics.py:148
def deflated_sharpe_ratio(
    sharpe_ratio: float,         # SR_obs (bar-level non-annualized)
    n_trials: int,                # >= 2
    n_observations: int,          # >= 2
    skew: float,
    kurtosis: float,              # non-excess (= 4次中心モーメント / sigma^4)
    mean_sr_trials: float,
    std_sr_trials: float,
) -> float:                       # ∈ [0, 1] (Φ 適用済)
    """Bailey & López de Prado (2014) DSR、 v1 bar-level annualized Sharpe 入力前提."""
```

既存 archive schema にも `dsr` field 存在 (= `archive.py:81`)。 T073 PR は:
- 既存 `deflated_sharpe_ratio` 関数は **そのまま使用** (= Eq.(7) (9) 数式は不変、 値域 [0, 1] 保持)
- 入力経路 (= sharpe_ratio / skew / kurtosis 等の **算出元データ**) を v2 cascade port (T058 + T070) に整合
- archive `dsr` field の値は Phase 2 で v1 → v2 切替 (= sharpe_calc_version 連動)

### 1.3 zenigame 実装との比較 (synthesis 文言「同等」 の意味)

| 項目 | zenigame `_dsr.py:126` `calc_dsr` | zenigame-fx `statistics.py:148` `deflated_sharpe_ratio` |
|---|---|---|
| 戻り値 | DSR z-score (= Φ 適用前) | DSR ∈ [0, 1] (= Φ 適用済) |
| 入力 | `daily_returns: list[float]` (= 直接 returns) | `sharpe_ratio / skew / kurtosis / ...` (= moment 引き渡し) |
| n_trials | 引数、 sr_benchmark 自動計算は z_q から | 引数、 expected_max_sr を Bailey Eq.(7) で計算 |
| Sharpe ベンチマーク | `sr_benchmark = z_q / sqrt(T-1)` | `expected_max_sr = mean_sr_trials + std_sr_trials × ((1-γ)q1 + γq2)` |
| moment 推定 | 関数内部で計算 | 引数で受領 (= caller 責務) |
| エラー処理 | `n < 4` / `variance < 1e-20` で NaN | `n_trials < 2` 等で ValueError |

zenigame-fx は **moment を引数化** + **値域 [0, 1] (= Φ 適用済)** の方が API として優れている (= caller が moment を T070 SessionBlock 駆動で計算可能、 値域固定で audit 解釈容易)。 zenigame `_dsr.py` は zenigame v1 (= 日次 returns 直接入力) で、 zenigame-fx の方が SSOT 設計が成熟。

→ **synthesis 文言「zenigame `_dsr.py:126` 同等」 は数式 (Bailey & López de Prado 2014) 同等の意味**、 API は zenigame-fx 既存を維持。

### 1.4 v1 → v2 入力意味論移行 (= Phase 2 申し送り)

既存 `deflated_sharpe_ratio` は v1 bar-level annualized Sharpe を前提とし、 archive `dsr` field は v1 経路で計算済 (= `T-sharpe Phase 1A` 段階で v2 trade-level Sharpe 入力に未対応)。 T073 PR の責務:

- v2 入力 SSOT を定義 (= SessionBlock pnl_net 列、 expected_bar_count > 0 のみ、 holiday_markets stratified)
- 既存 archive `dsr` field の v1 経路は **touch しない** (= 後方互換)
- Phase 2 別 PR で `sharpe_calc_version="v2"` + 既存 `dsr` field を v2 入力で再計算 + 旧 v1 値は schema 上 `dsr_v1_compat` 等で保持

これは synthesis §10.2「early gate ではない」 と整合 (= selection 経路に影響しない、 archive 経路の値変更だけ)。

---

## 2. 設計の SSOT 原則

### 2.1 不変 (T058 / T070 / T071 / T072 / 既存 SSOT)

- T058 schema v2: archive_role / source_stage / dataset_epoch_id / schema_version=2
- T070 SessionBlock / SessionBlockBucket / BLOCK_BUCKET_RANGES_UTC / aggregate_session_blocks
- T071 RunObservabilityReport (= status field 方式、 None 経路完全排除)
- T072 ObservabilityFlags (= holiday_markets / dst_transition_markets) / open_minutes / expected_bar_count
- 既存 `deflated_sharpe_ratio` 数式 (= Bailey & López de Prado 2014 Eq.(7) (9))、 値域 [0, 1]、 Φ 適用済

### 2.2 T073 で新設 (SSOT、 Round 2 改訂)

#### 型・定数

- `AuditDSRStatus = Literal["ok", "insufficient_data", "insufficient_trials", "degenerate_variance", "input_non_finite"]` (Round R2 [W4] 反映で分離、 5 値、 not_implemented を含まない)
- `AuditScaffoldStatus = Literal["not_implemented"]` (Round R2 [W4] 反映、 PBO/SPA 専用 1 値)
- `AuditNullModelKind = Literal["standard_normal"]` (Round R2 [C2] 反映で Phase 1 では standard_normal のみ、 archive_sample は Phase 2 で追加 + AUDIT_REPORT_SCHEMA_VERSION MINOR bump 予定)
- `AuditSRScale = Literal["session_block_non_annualized"]` (Round R2 [S1] 新設、 Phase 1 SSOT、 Phase 2 で v1 互換等が必要なら追加)
- `AuditTrialSource = Literal["run_evaluated_genomes_unique_canonical"]` (Round R2 [C1] [S2] 反映、 「unique canonical genome_id selection 投入数」 を SSOT 化、 retry/fold/cache replay は別 trial にしない)
- `AUDIT_DSR_MIN_OBSERVATIONS: Final[int] = 30` (= 運用最低観測数、 Round 1 [W1] 反映で「統計理論ではなく運用閾値」 と明記)
- `AUDIT_DSR_MIN_TRIALS: Final[int] = 2` (= 既存関数 invariant、 N=1 は insufficient_trials sentinel)
- `AUDIT_REPORT_SCHEMA_VERSION: Final[str] = "1.0.0"`
- `AUDIT_DSR_CALC_VERSION: Final[str] = "v2"`
- `AUDIT_SCAFFOLD_CALC_VERSION: Final[str] = "scaffold-v1"`
- `SCAFFOLD_SENTINEL_VALUE: Final[Decimal] = Decimal("-1")` (Round R2 [C4] 反映、 値域 [0, 1] 外 sentinel で「非実装」 を fail-closed mark、 status check 漏れ時に「最良値」 と誤読されない)

#### dataclass (frozen)

- `AuditNullModel` (Round 1 [C2] [S2] / Round R2 [C3] [S1] [S2] 反映): null_model_kind / sr_scale / mean_sr_trials / std_sr_trials / trial_source / n_trials / n_trial_candidates_raw / n_trial_candidates_unique を一括保持
- `AuditDSRMetric`: status (AuditDSRStatus、 5 値) / dsr_value / n_observations / sharpe_ratio / skew / kurtosis / null_model / audit_calc_version
- `AuditPBOMetric` (scaffold、 Round R2 [C4] [S3] 反映): **status (AuditScaffoldStatus、 固定="not_implemented") + audit_calc_version のみ**、 数値 field なし。 Phase 2 で performance_matrix / cscv_n_splits 等を追加 + AUDIT_REPORT_SCHEMA_VERSION MINOR bump
- `AuditSPAMetric` (scaffold、 同 SSOT): status + audit_calc_version のみ、 Phase 2 で loss_differential / block_bootstrap_size 等追加
- `AuditGenomeRecord` (Round 1 [C5] [S1] 新設): genome_id / archive_role / source_stage / dsr_metric (= T058 と join 可能)
- `RunAuditReport`: run_id / dataset_epoch_id / n_genomes / per_genome: tuple[AuditGenomeRecord, ...] / pbo / spa / audit_report_schema_version

#### 関数

- `compute_audit_dsr_for_genome(session_blocks, *, null_model: AuditNullModel) -> AuditDSRMetric`: SessionBlock 列 (= 単一 genome の Run 中の全 block) から moment 計算 + `deflated_sharpe_ratio` 呼出
- `compute_audit_pbo_scaffold(*, audit_calc_version="scaffold-v1") -> AuditPBOMetric`: scaffold (= status="not_implemented"、 計算しない)
- `compute_audit_spa_scaffold(*, audit_calc_version="scaffold-v1") -> AuditSPAMetric`: 同上
- `compute_run_audit_report(*, run_id, dataset_epoch_id, per_genome: Mapping[str, GenomeAuditInput], null_model: AuditNullModel) -> RunAuditReport`: archive 全 genome を走査して per-genome AuditDSRMetric を AuditGenomeRecord で集約

### 2.3 T073 で扱わない (Phase 2 / T074 / T075 以降)

- 既存 archive `dsr` field の v2 入力切替 (= Phase 2 別 PR、 sharpe_calc_version="v2" 同期)
- PBO / SPA の **計算実装** (= smoke 後別 PR、 schema scaffold のみ T073 で確定)
- selection 経路への影響 (= early gate でない、 synthesis § 10.2 厳密準拠)
- T071 RunObservabilityReport.audit field 配線 (= Phase 2、 RunObservabilityReport 拡張は T071 が SSOT)

---

## 3. アーキテクチャ概観

```
src/alpha_factory/
├── statistics.py              [既存、 T073 で touch しない]
│   └── deflated_sharpe_ratio  (= Bailey & López de Prado 2014、 値域 [0, 1])
│
├── archive.py                  [既存、 T073 で touch しない]
│   └── GENOMES_SCHEMA          (= "dsr" field 既存、 v1 入力)
│
└── audit.py                    [T073 新規]
    ├── AuditMetricStatus       [T073 SSOT]
    ├── AUDIT_DSR_MIN_OBSERVATIONS / AUDIT_DSR_MIN_TRIALS    [T073 SSOT]
    ├── AuditDSRMetric          [T073 SSOT、 frozen dataclass]
    ├── AuditPBOMetric          [T073 scaffold、 frozen dataclass]
    ├── AuditSPAMetric          [T073 scaffold、 frozen dataclass]
    ├── RunAuditReport          [T073 SSOT、 frozen dataclass]
    ├── compute_audit_dsr_for_genome    [SessionBlock 駆動、 既存関数 wrapper]
    ├── compute_audit_pbo_scaffold      [NotImplementedError 系]
    ├── compute_audit_spa_scaffold      [同上]
    └── compute_run_audit_report        [archive 全 genome 集約]
```

### 3.1 T073 で touch する既存ファイル

| ファイル | 改造内容 | 既存挙動への影響 |
|---|---|---|
| (なし) | T073 PR は新規 module + 単体テストのみ | 既存ファイルへの影響なし (= early gate 不在) |

### 3.2 T073 で新設するファイル

| ファイル | 内容 | 行数概算 |
|---|---|---|
| `src/alpha_factory/audit.py` | 上記 SSOT 群 | +250 |
| `tests/alpha_factory/test_audit.py` | F1-F30 + happy path | +350 |

---

## 4. データ構造 SSOT

### 4.1 AuditMetricStatus (Round 1 [C7] [S3] 反映で 6 値)

```python
AuditMetricStatus = Literal[
    "ok",                    # 計算成功
    "insufficient_data",     # n_observations < AUDIT_DSR_MIN_OBSERVATIONS (= 観測不足)
    "insufficient_trials",   # n_trials < AUDIT_DSR_MIN_TRIALS (= N=1 等、 multiple testing correction 不可)
    "degenerate_variance",   # variance < 1e-20 (= 退化分散、 観測事実として独立分類、 Round 1 [C7])
    "input_non_finite",      # 入力に NaN / Inf
    "not_implemented",       # PBO / SPA scaffold (= synthesis 「未実装タグ」 厳密準拠)
]
```

T071 SSOT (= status field 方式) を継承。 None 経路完全排除、 **scaffold/sentinel 値は `SCAFFOLD_SENTINEL_VALUE = Decimal("0")` 固定** (Round 1 [C6] [S6] 反映、 Decimal("NaN") の hash/eq/JSON round-trip 問題を回避)。

### 4.1b AuditNullModel (Round 1 [C2] [S2] 新設)

```python
@dataclass(frozen=True)
class AuditNullModel:
    """DSR 計算の null model provenance (Round R2 [C3] [S1] [S2] 反映).

    位置付け (Round R2 [C3]): standard_normal は **Phase 1 monitor-only の保守的 placeholder null**。
    Bailey 原著 (2014) の「trial SR 分布の mean/std を用いて expected max SR を補正」 という
    意図とは完全には合致しない (= 原著は archive_sample null 相当)。 Phase 2 で
    archive_sample null を追加し AUDIT_REPORT_SCHEMA_VERSION MINOR bump 予定。

    Phase 1 default (Round R2 [C2] 反映で archive_sample 削除):
        null_model_kind = "standard_normal"
        sr_scale = "session_block_non_annualized"  (Round R2 [S1])
        mean_sr_trials = 0.0
        std_sr_trials = 1.0
        trial_source = "run_evaluated_genomes_unique_canonical"  (Round R2 [C1])
        n_trials = Run 中の unique canonical genome_id の selection 投入数 (= retry/fold/cache replay 別 trial にしない)
        n_trial_candidates_raw = 評価 attempt 総数 (= 重複含む、 監査用)
        n_trial_candidates_unique = unique canonical genome_id 数 (= n_trials と同値)
    """

    null_model_kind: AuditNullModelKind         # = "standard_normal" (Phase 1 SSOT、 archive_sample は Phase 2)
    sr_scale: AuditSRScale                       # = "session_block_non_annualized" (Round R2 [S1])
    mean_sr_trials: Decimal                      # = Decimal(0) (standard_normal で固定)
    std_sr_trials: Decimal                       # = Decimal(1) (standard_normal で固定、 > 0)
    trial_source: AuditTrialSource               # = "run_evaluated_genomes_unique_canonical"
    n_trials: int                                # >= AUDIT_DSR_MIN_TRIALS、 == n_trial_candidates_unique
    n_trial_candidates_raw: int                  # 評価 attempt 総数 (= 重複含む)
    n_trial_candidates_unique: int               # unique canonical genome_id 数 (= n_trials)

    def __post_init__(self) -> None:
        # invariant:
        #   null_model_kind == "standard_normal" → mean_sr_trials == 0, std_sr_trials == 1
        #   sr_scale == "session_block_non_annualized" (Phase 1 SSOT)
        #   std_sr_trials > 0
        #   n_trials == n_trial_candidates_unique (= 重複除外後の母集団)
        #   n_trial_candidates_raw >= n_trial_candidates_unique
        #   n_trials >= AUDIT_DSR_MIN_TRIALS (= 2)、 違反は AuditDSRStatus="insufficient_trials" sentinel で AuditDSRMetric 側が表現
        ...
```

**重要 (Round 1 [C3])**: `n_trials` の母集合は **「その Run で performance selection 対象になり得た全評価 genome 数」**。 archive cardinality (= survivor) や Stage A 通過数を使うと **survivor 条件付け過少補正** で audit が緩くなる。 「全 GA 評価 genome」 が保守的で multiple testing correction として正当。

### 4.2 AuditDSRMetric (Round 1 [C2] [C5] [C6] [C7] 反映)

```python
@dataclass(frozen=True)
class AuditDSRMetric:
    """genome ごとの DSR 監査結果.

    SSOT (= synthesis § 10.2 / § 18.2 T916):
        - 既存 deflated_sharpe_ratio (statistics.py:148) を呼出、 数式不変
        - 入力 v2: T070 SessionBlock の pnl_net 列 (= **`open_minutes > 0` のみ filter**、 Round 1 [C4])
        - n_observations: filter 後の block 数 (= caller の stratified audit 前の母集団)
        - 値域 [0, 1] (Φ 適用済)
        - status="ok" 以外は dsr_value = SCAFFOLD_SENTINEL_VALUE (= Decimal("0")、 Round 1 [C6])
        - null model は AuditNullModel で SSOT 保持 (Round 1 [C2])
    """

    status: AuditDSRStatus            # 5 値 (= ok / insufficient_data / insufficient_trials / degenerate_variance / input_non_finite、 Round R2 [W4] 分離)
    dsr_value: Decimal               # status="ok" 以外は SCAFFOLD_SENTINEL_VALUE (= Decimal("-1") 値域外、 Round R2 [C4])
    n_observations: int              # status="ok" 以外でも n は記録
    sharpe_ratio: Decimal            # SR_obs (= sr_scale 駆動、 Phase 1 = session_block_non_annualized)
    skew: Decimal                    # 3次中心モーメント / sigma^3
    kurtosis: Decimal                # non-excess
    null_model: AuditNullModel       # null model provenance (Round 1 [C2] / Round R2 [C3])
    audit_calc_version: str          # = "v2"

    def __post_init__(self) -> None:
        # status invariant (Round 1 [C7] [S3] / [C6] 反映):
        #   "ok"                   → 0.0 <= dsr_value <= 1.0、 全 input finite
        #   "insufficient_data"    → dsr_value == SCAFFOLD_SENTINEL_VALUE、 n_observations < AUDIT_DSR_MIN_OBSERVATIONS
        #   "insufficient_trials"  → dsr_value == SCAFFOLD_SENTINEL_VALUE、 null_model.n_trials < AUDIT_DSR_MIN_TRIALS
        #   "degenerate_variance"  → dsr_value == SCAFFOLD_SENTINEL_VALUE、 variance 退化
        #   "input_non_finite"     → dsr_value == SCAFFOLD_SENTINEL_VALUE、 sharpe / skew / kurtosis に NaN/Inf
        #   "not_implemented"      → AuditDSRMetric では使用禁止 (= scaffold 用途は別 dataclass)
        #   else: raise ValueError
        # audit_calc_version == AUDIT_DSR_CALC_VERSION (= "v2")
        ...
```

### 4.3 AuditPBOMetric (scaffold、 Round R2 [C4] [S3] 反映で数値 field 削除)

```python
@dataclass(frozen=True)
class AuditPBOMetric:
    """PBO (Bailey CSCV 2015) scaffold.

    SSOT (synthesis § 10.2 / Round R2 [C4] [S3]):
        - status は常に "not_implemented" 固定 (AuditScaffoldStatus 1 値)
        - **数値 field なし** (Round R2 [C4]、 status check 漏れで誤読 risk 排除、 fail-closed 強化)
        - audit_calc_version = "scaffold-v1" で「未実装」 を構造的明示
        - 計算関数 compute_audit_pbo_scaffold は NotImplementedError raise しない (= status return のみ)

    Phase 2 拡張余地 (Round 1 [W5] / Round R2 [W5] 反映):
        Bailey, Borwein, López de Prado, Zhu (2015) PBO 実装時に追加する field:
        - performance_matrix: tuple[tuple[Decimal, ...], ...] (= CSCV split 単位の loss/perf 行列)
        - cscv_n_splits: int
        - cscv_logit_estimate: Decimal
        - pbo_value: Decimal (実装時にのみ追加)
        Phase 2 で field 追加時 → AUDIT_REPORT_SCHEMA_VERSION **MINOR bump** (= 後方互換、 既存 caller は新 field を ignore)
        意味変更時 → MAJOR bump.
    """

    status: AuditScaffoldStatus    # = "not_implemented" 固定
    audit_calc_version: str         # = "scaffold-v1"

    def __post_init__(self) -> None:
        if self.status != "not_implemented":
            raise ValueError(f"AuditPBOMetric.status must be 'not_implemented' (scaffold), got {self.status!r}")
        if self.audit_calc_version != AUDIT_SCAFFOLD_CALC_VERSION:
            raise ValueError(f"AuditPBOMetric.audit_calc_version must be {AUDIT_SCAFFOLD_CALC_VERSION!r}, got {self.audit_calc_version!r}")
```

### 4.4 AuditSPAMetric (scaffold、 同 SSOT)

```python
@dataclass(frozen=True)
class AuditSPAMetric:
    """SPA (Hansen 2005) scaffold.

    Phase 2 拡張余地:
        Hansen (2005) SPA 実装時に追加する field:
        - loss_differential: tuple[Decimal, ...] (= benchmark との loss 差分系列)
        - block_bootstrap_size: int (= Politis & White 2004 dependent bootstrap block 長)
        - bootstrap_p_value: Decimal
        - spa_value: Decimal (実装時にのみ追加)
        Phase 1 では status + audit_calc_version のみ.
    """
    status: AuditScaffoldStatus
    audit_calc_version: str         # = "scaffold-v1"

    def __post_init__(self) -> None:
        # 同 invariant (status / audit_calc_version 固定)
        ...
```

### 4.5 AuditGenomeRecord (Round 1 [C5] [S1] 新設)

```python
@dataclass(frozen=True)
class AuditGenomeRecord:
    """genome 単位の audit record (= T058 archive_role / source_stage と join 可能).

    SSOT (Round 1 [C5] 反映): genome_id を内包し、 RunAuditReport に集約しても
    どの metric がどの genome のものか復元可能. archive / report / log 配線で
    join key として使う.

    T058 (archive_role / source_stage / dataset_epoch_id) は genome admission 時の
    値をそのまま保持 (= audit-only、 selection 経路に影響しない).
    """

    genome_id: str                # = T058 genome_entry の id (or hash) と同一
    archive_role: str              # = T058 archive_role (Literal: "convergence" | "diversity" | ...)
    source_stage: str              # = T058 source_stage (Literal: "stage_c" | "score_bypass" | ...)
    dsr_metric: AuditDSRMetric

    def __post_init__(self) -> None:
        # genome_id は non-empty
        # archive_role / source_stage は T058 SSOT 値 (= 詳細設計で値域固定)
        ...
```

### 4.6 RunAuditReport (Round 1 [C5] [S1] 反映)

```python
@dataclass(frozen=True)
class RunAuditReport:
    """1 Run 全体の audit 集約 (= T071 RunObservabilityReport.audit Phase 2 配線対象).

    SSOT (Round 1 [C5]):
        - per_genome: AuditGenomeRecord tuple (= genome_id 内包)
        - pbo / spa は scaffold (= 1 個の Metric に集約、 Run 全体)
        - dataset_epoch_id (T058) で epoch スコープ固定
    """

    run_id: str
    dataset_epoch_id: str
    n_genomes: int                                    # archive 内 genome 数
    per_genome: tuple[AuditGenomeRecord, ...]         # len == n_genomes
    pbo: AuditPBOMetric                                # scaffold (1 個)
    spa: AuditSPAMetric                                # scaffold
    audit_report_schema_version: str                   # = "1.0.0"

    def __post_init__(self) -> None:
        # invariant:
        #   len(per_genome) == n_genomes
        #   全 per_genome[i].dsr_metric.audit_calc_version == AUDIT_DSR_CALC_VERSION
        #   pbo.audit_calc_version == AUDIT_SCAFFOLD_CALC_VERSION
        #   spa.audit_calc_version == AUDIT_SCAFFOLD_CALC_VERSION
        #   audit_report_schema_version == AUDIT_REPORT_SCHEMA_VERSION
        #   全 per_genome[i].dsr_metric.null_model は同一 instance (= Run 内一様 null、 Phase 1 default)
        ...
```

---

## 5. 主要関数 API SSOT (§ 11.2 SSOT 規約準拠)

```python
# src/alpha_factory/audit.py

AuditMetricStatus = Literal["ok", "insufficient_data", "not_implemented", "input_non_finite"]
AUDIT_DSR_MIN_OBSERVATIONS: Final[int] = 30
AUDIT_DSR_MIN_TRIALS: Final[int] = 2
AUDIT_REPORT_SCHEMA_VERSION: Final[str] = "1.0.0"
AUDIT_DSR_CALC_VERSION: Final[str] = "v2"
AUDIT_SCAFFOLD_CALC_VERSION: Final[str] = "scaffold-v1"


@dataclass(frozen=True)
class AuditDSRMetric: ...
@dataclass(frozen=True)
class AuditPBOMetric: ...
@dataclass(frozen=True)
class AuditSPAMetric: ...
@dataclass(frozen=True)
class RunAuditReport: ...


def compute_audit_dsr_for_genome(
    session_blocks: Sequence[SessionBlock],
    *,
    null_model: AuditNullModel,
) -> AuditDSRMetric:
    """genome の SessionBlock 列から DSR を計算.

    SSOT (T072 collider bias 規範継承、 Round 1 [C2] [C4] 反映):
        - 入力 block の filter: open_minutes > 0 のみ (= broker 配信ありの block)
        - holiday_markets 単独で除外しない (= caller の stratified audit、 § 11.4 規範)
        - n_observations = filter 後の block 数
        - sharpe / skew / kurtosis は filter 後 pnl_net 列の moment 推定 (unbiased、 非年率化)
        - null_model.mean_sr_trials / std_sr_trials は AuditNullModel に集約 (Round 1 [C2])

    Returns:
        AuditDSRMetric (status / dsr_value / n_observations / ... / null_model).
    """
    ...


def compute_audit_pbo_scaffold(*, audit_calc_version: str = AUDIT_SCAFFOLD_CALC_VERSION) -> AuditPBOMetric:
    """PBO scaffold (= status="not_implemented" / pbo_value=SCAFFOLD_SENTINEL_VALUE)."""
    ...


def compute_audit_spa_scaffold(*, audit_calc_version: str = AUDIT_SCAFFOLD_CALC_VERSION) -> AuditSPAMetric:
    ...


@dataclass(frozen=True)
class GenomeAuditInput:
    """compute_run_audit_report の per-genome 入力 (Round 1 [C5] [C8])."""
    genome_id: str
    archive_role: str
    source_stage: str
    session_blocks: Sequence[SessionBlock]


def compute_run_audit_report(
    *,
    run_id: str,
    dataset_epoch_id: str,
    per_genome: Mapping[str, GenomeAuditInput],   # genome_id -> input
    null_model: AuditNullModel,
) -> RunAuditReport:
    """archive 全 genome を走査して RunAuditReport を構築.

    SSOT (Round 1 [C5] [C8]):
        - per-genome AuditDSRMetric を AuditGenomeRecord で wrap (= genome_id 内包)
        - PBO / SPA は scaffold metric を 1 個ずつ (Run 全体共有)
        - dataset_epoch_id で epoch スコープ固定 (T058)
        - null_model は Run 内一様 (Phase 1 default)、 全 genome で同一 AuditNullModel instance
    """
    ...
```

---

## 6. アルゴリズム詳細 (擬似コード)

### 6.1 compute_audit_dsr_for_genome (Round 1 [C2] [C4] [C6] [C7] 反映)

```python
def compute_audit_dsr_for_genome(session_blocks, *, null_model: AuditNullModel):
    # Step 0: insufficient_trials 判定 (Round 1 [C7] / [W3] 反映)
    if null_model.n_trials < AUDIT_DSR_MIN_TRIALS:
        return _make_audit_metric_with_status(
            status="insufficient_trials", null_model=null_model,
            n_observations=0,
        )

    # Step 1: T072 collider bias 規範継承 — open_minutes > 0 の block のみ filter
    # holiday_markets は単独で除外しない (= caller の stratified audit、 § 11.4)
    relevant = [b for b in session_blocks if b.open_minutes > 0]
    n = len(relevant)

    # Step 2: insufficient_data 判定 (C7 規範、 Round 1 [W1] 「運用閾値」 SSOT)
    if n < AUDIT_DSR_MIN_OBSERVATIONS:
        return _make_audit_metric_with_status(
            status="insufficient_data", null_model=null_model, n_observations=n,
        )

    # Step 3: pnl_net 列の moment 推定 (unbiased)
    pnls = [float(b.pnl_net) for b in relevant]
    mean = statistics.fmean(pnls)
    variance = statistics.variance(pnls)  # n-1 unbiased

    # Step 3a: degenerate_variance 判定 (Round 1 [C7] 分離)
    if variance < 1e-20:
        return _make_audit_metric_with_status(
            status="degenerate_variance", null_model=null_model, n_observations=n,
        )

    stdev = math.sqrt(variance)
    sharpe = mean / stdev   # SR_obs (bar-level non-annualized)
    skew_val = sum((r - mean) ** 3 for r in pnls) / (n * stdev ** 3)
    kurt_val = sum((r - mean) ** 4 for r in pnls) / (n * stdev ** 4)  # non-excess

    # Step 3b: input_non_finite 判定 (= moment が NaN/Inf)
    for v in (sharpe, skew_val, kurt_val):
        if not math.isfinite(v):
            return _make_audit_metric_with_status(
                status="input_non_finite", null_model=null_model, n_observations=n,
            )

    # Step 4: 既存 deflated_sharpe_ratio 呼出 (= Bailey 数式不変)
    try:
        dsr = deflated_sharpe_ratio(
            sharpe_ratio=sharpe,
            n_trials=null_model.n_trials,
            n_observations=n,
            skew=skew_val,
            kurtosis=kurt_val,
            mean_sr_trials=float(null_model.mean_sr_trials),
            std_sr_trials=float(null_model.std_sr_trials),
        )
    except ValueError:
        return _make_audit_metric_with_status(
            status="input_non_finite", null_model=null_model, n_observations=n,
        )

    # Step 5: 成功 case
    return AuditDSRMetric(
        status="ok",
        dsr_value=Decimal(str(dsr)),
        n_observations=n,
        sharpe_ratio=Decimal(str(sharpe)),
        skew=Decimal(str(skew_val)),
        kurtosis=Decimal(str(kurt_val)),
        null_model=null_model,
        audit_calc_version=AUDIT_DSR_CALC_VERSION,
    )


def _make_audit_metric_with_status(*, status, null_model, n_observations):
    """Round 1 [C6] [S6] 反映: status != "ok" 時の sentinel SSOT.
    全 dsr_value / sharpe_ratio / skew / kurtosis を SCAFFOLD_SENTINEL_VALUE 固定.
    """
    return AuditDSRMetric(
        status=status,
        dsr_value=SCAFFOLD_SENTINEL_VALUE,
        n_observations=n_observations,
        sharpe_ratio=SCAFFOLD_SENTINEL_VALUE,
        skew=SCAFFOLD_SENTINEL_VALUE,
        kurtosis=SCAFFOLD_SENTINEL_VALUE,
        null_model=null_model,
        audit_calc_version=AUDIT_DSR_CALC_VERSION,
    )
```

### 6.2 compute_audit_pbo_scaffold / compute_audit_spa_scaffold

```python
def compute_audit_pbo_scaffold(*, audit_calc_version="scaffold-v1") -> AuditPBOMetric:
    return AuditPBOMetric(
        status="not_implemented",
        pbo_value=Decimal("NaN"),
        audit_calc_version=audit_calc_version,
    )


def compute_audit_spa_scaffold(*, audit_calc_version="scaffold-v1") -> AuditSPAMetric:
    return AuditSPAMetric(
        status="not_implemented",
        spa_value=Decimal("NaN"),
        audit_calc_version=audit_calc_version,
    )
```

scaffold は **NotImplementedError raise しない** (= caller が catch せずに dataclass 経由で「未実装」 を判定可能、 status field 方式)。

### 6.3 compute_run_audit_report (Round 1 [C5] [C8] 反映で AuditGenomeRecord 使用)

```python
def compute_run_audit_report(*, run_id, dataset_epoch_id, per_genome, null_model):
    """per_genome は Mapping[genome_id, GenomeAuditInput].
    null_model は Run 内一様 (Phase 1 default = standard_normal H0)、 全 genome で同一 instance.
    """
    records = tuple(
        AuditGenomeRecord(
            genome_id=inp.genome_id,
            archive_role=inp.archive_role,
            source_stage=inp.source_stage,
            dsr_metric=compute_audit_dsr_for_genome(
                inp.session_blocks, null_model=null_model,
            ),
        )
        for genome_id, inp in sorted(per_genome.items())  # deterministic by genome_id
    )
    return RunAuditReport(
        run_id=run_id,
        dataset_epoch_id=dataset_epoch_id,
        n_genomes=len(records),
        per_genome=records,
        pbo=compute_audit_pbo_scaffold(),
        spa=compute_audit_spa_scaffold(),
        audit_report_schema_version=AUDIT_REPORT_SCHEMA_VERSION,
    )
```

---

## 7. 既存挙動への影響 (C2 parallel-path verification)

### 7.1 直 import 経路

`src/alpha_factory/audit.py` は **新規ファイル**。 既存ファイル touch なし (= early gate 不在 SSOT、 synthesis § 10.2 厳密準拠)。 `deflated_sharpe_ratio` を import するが既存関数の呼出のみ。

### 7.2 5 段階 grep 検証 (Phase 1 PR 内)

- 直 import: `from src.alpha_factory.audit import ...` は Phase 1 では tests のみ
- alias / relative / 再エクスポート: なし
- runtime シンボル: T073 dataclass / 関数の caller は Phase 2 で T071 RunObservabilityReport 拡張から (= まだ実装されていない)

### 7.3 既存 archive `dsr` field との関係

- 既存 `archive.py:81` `dsr` field は v1 (bar-level annualized Sharpe) 入力で計算済 (= sharpe_calc_version 不一致)
- T073 PR は archive 経路に touch しない
- Phase 2 別 PR で v2 入力切替 (= sharpe_calc_version="v2" 同期 + 旧 v1 値は別 field or 削除)

### 7.4 fail-closed 経路

- `n_trials < AUDIT_DSR_MIN_TRIALS` (= 2) → `AuditDSRMetric.__post_init__` で ValueError (= 既存 deflated_sharpe_ratio invariant 継承)
- 入力 SessionBlock が空 → status="insufficient_data"
- `expected_bar_count > 0` の block が AUDIT_DSR_MIN_OBSERVATIONS 未満 → status="insufficient_data"
- 入力に NaN/Inf → deflated_sharpe_ratio が ValueError raise → caller で catch → status="input_non_finite"
- variance < 1e-20 → status="input_non_finite"

---

## 8. 不変条件 (invariant)

| ID | 不変条件 | 担保 |
|---|---|---|
| I1 | T058 / T070 / T071 / T072 / 既存 statistics.py の SSOT は T073 で touch しない | 新規 module、 既存ファイルへの touch 不在 |
| I2 | early gate ではない (= selection 経路に影響しない) | T073 PR は selection 経路 (Stage A/B/C / GA / archive admission) に touch しない |
| I3 | AuditDSRMetric.status は AuditMetricStatus 4 値のみ | __post_init__ で値検証 |
| I4 | status="ok" → dsr_value ∈ [0, 1] (Φ 適用済) | __post_init__ |
| I5 | status="insufficient_data" → dsr_value is sentinel (Decimal("NaN")) | __post_init__ |
| I6 | status="input_non_finite" → dsr_value is sentinel | __post_init__ |
| I7 | AuditPBOMetric.status == "not_implemented" 固定、 audit_calc_version == "scaffold-v1" | __post_init__ |
| I8 | AuditSPAMetric も同 invariant (PBO 同様) | __post_init__ |
| I9 | RunAuditReport.per_genome_dsr 全て audit_calc_version == AUDIT_DSR_CALC_VERSION | __post_init__ |
| I10 | RunAuditReport.pbo / spa の audit_calc_version == AUDIT_SCAFFOLD_CALC_VERSION | __post_init__ |
| I11 | compute_audit_dsr_for_genome の入力 block filter は `open_minutes > 0` のみ (= holiday_markets 単独除外しない、 T072 collider bias 規範) | 関数 logic + 単体テスト |
| I12 | n_trials >= AUDIT_DSR_MIN_TRIALS (= 2) | __post_init__ で ValueError |
| I13 | AUDIT_DSR_MIN_OBSERVATIONS = 30 (= C7 規範、 sample size guard) | Final 定数 |
| I14 | RunAuditReport.audit_report_schema_version == AUDIT_REPORT_SCHEMA_VERSION (= "1.0.0") | __post_init__ |
| I15 | scaffold metric は NotImplementedError raise しない (= status field 方式で「未実装」 を表現) | 関数 logic + 単体テスト |

---

## 9. リスクと緩和

| リスク | 影響 | 緩和 |
|---|---|---|
| F1 既存 `deflated_sharpe_ratio` の v1 入力意味論との不整合 | T073 v2 入力で archive `dsr` field の値が変わる | T073 PR は archive 経路 touch しない、 Phase 2 別 PR で sharpe_calc_version="v2" 同期 |
| F2 PBO/SPA scaffold が「未実装」 と分かりづらい | 後段 caller が誤って scaffold metric を信頼する | status="not_implemented" + audit_calc_version="scaffold-v1" の二重 SSOT、 docstring 明示 |
| F3 holiday_markets 単独除外で collider bias | T072 規範違反 | I11 で `open_minutes > 0` のみを filter SSOT、 holiday は caller の stratified audit |
| F4 n_observations 不足 (< 30) で n=20 等の DSR 計算が走る | 統計的に無意味な値が archive に残る | C7 規範 (= AUDIT_DSR_MIN_OBSERVATIONS=30) で status="insufficient_data" sentinel |
| F5 既存 archive `dsr` field の v1 値を T073 v2 と混同 | audit log で誤解釈 | audit_calc_version で v1/v2 を明示分離、 archive 経路は Phase 2 で sharpe_calc_version="v2" 同期 merge |
| F6 mean_sr_trials / std_sr_trials の H0 値固定 (= 0/1) | 別 null hypothesis では誤った Bailey Eq.(7) 値 | docstring で「H0 標準正規 null SSOT」 を明記、 Phase 2 で別 null 検討時に audit_calc_version bump |
| F7 statistics.py 既存関数の数式変更 | T073 が影響を受ける | T073 は数式不変前提、 数式変更は別 TODO + audit_calc_version bump |
| F8 PBO/SPA scaffold を実装する Phase 2 PR で schema 互換性破壊 | audit consumer breakage | AUDIT_REPORT_SCHEMA_VERSION の MAJOR bump で migration 経路を明示 |
| F9 collider bias 規範 (T072 申し送り) の伝搬漏れ | 後段で holiday_markets 単独 drop | T071 / T064 / T066 詳細設計改訂申し送りに同規範を継承、 PR description テンプレート (= T072 § 9.6) を T073 でも使用 |
| F10 既存 statistics.py docstring が「Phase 1A monitor only」 と書いてある | T073 で audit-only 用途と再定義する整合 | T073 docstring で「audit-only、 selection 経路に影響しない」 を明記 |

---

## 10. テスト計画 (概要、 詳細は detailed-design.md で)

### 10.1 pure function tests

- F1: `compute_audit_dsr_for_genome` happy path (= n=100、 status="ok"、 dsr_value ∈ [0, 1])
- F2: 入力 block 0 個 → status="insufficient_data"
- F3: open_minutes > 0 が 30 個未満 → status="insufficient_data"
- F4: 全 SessionBlock の pnl_net がゼロ (variance < 1e-20) → status="input_non_finite"
- F5: T072 collider bias: bucket=ny / Tokyo holiday の block も `open_minutes > 0` なら audit に含める (= 単独除外しない)
- F6: n_trials < 2 → ValueError (= 既存関数 invariant)
- F7: audit_calc_version="v2" 固定

### 10.2 scaffold tests

- F8: AuditPBOMetric(status="ok", ...) → __post_init__ ValueError
- F9: AuditPBOMetric(status="not_implemented", audit_calc_version="v2") → __post_init__ ValueError
- F10: compute_audit_pbo_scaffold() → status="not_implemented" / audit_calc_version="scaffold-v1"
- F11: compute_audit_spa_scaffold() → 同上 (SPA)
- F12: scaffold は NotImplementedError raise しない (= status return SSOT)

### 10.3 RunAuditReport tests

- F13: 1 genome / 100 block → n_genomes=1 / per_genome_dsr len=1 / status="ok"
- F14: 3 genome / 各々異なる block 数 → n_genomes=3 / per_genome_dsr len=3 / order is sorted by genome_id (deterministic)
- F15: pbo / spa は同一 instance (= 1 Run 1 個) / audit_calc_version="scaffold-v1"
- F16: AUDIT_REPORT_SCHEMA_VERSION="1.0.0" 固定

### 10.4 invariant tests

- F17: AuditDSRMetric(status="ok", dsr_value=Decimal("1.5")) → ValueError (I4)
- F18: AuditDSRMetric(status="insufficient_data", dsr_value=Decimal("0.5")) → ValueError (I5)
- F19: AuditDSRMetric(status="ok", n_trials=1) → ValueError (I12)
- F20: RunAuditReport audit_report_schema_version 不一致 → ValueError

### 10.5 既存 statistics.py との整合 tests

- F21: `compute_audit_dsr_for_genome` の出力 dsr_value は同入力で `deflated_sharpe_ratio` 直呼出と一致 (= wrapper 整合)
- F22: 既存 archive `dsr` field の値は T073 PR で touch しない (= grep 確認、 PR diff lint)

### 10.6 collider bias 規範 tests (T072 申し送り)

- F23: `holiday_markets={"tokyo"}` の block も open_minutes > 0 なら DSR 計算に含める
- F24: stratified audit テスト helper: holiday_markets 値別に AuditDSRMetric を生成可能 (= caller responsibility 確認)

---

## 11. Phase 1 / Phase 2 分離

### 11.1 Phase 1 (T073 PR、 Round 1 [C1] [S4] 反映で純ライブラリ統一)

含む (= **library + 単体テストのみ**、 runtime surface 不在):
- `src/alpha_factory/audit.py` 新規 (上記 SSOT 群)
- `tests/alpha_factory/test_audit.py` 新規
- 単体テストのみで runtime 未組込

含まない (= 全て Phase 2 / 別 TODO):
- T071 RunObservabilityReport.audit field 配線 (= Phase 2)
- archive `dsr` field の v2 入力切替 (= Phase 2 別 PR、 dsr_v1/dsr_v2 併存 + sharpe_calc_version="v2" 同期、 Round 1 [W2])
- run_ga.py / backtest_runner で compute_run_audit_report 呼出 (= Phase 2)
- PBO / SPA の計算実装 (= smoke 後別 TODO、 PBO は Bailey CSCV 2015 / SPA は Hansen 2005 + Politis & White 2004 dependent bootstrap)
- selection 経路への接続 (= 永久に不在、 synthesis § 10.2 厳密準拠)
- archive admission 時の SessionBlock 列保存経路 (= Phase 2 で T058 schema 拡張)

### 11.2 Phase 2 (別 TODO)

- T071 RunObservabilityReport に `audit: RunAuditReport` field 追加
- run_ga.py で run 末尾に compute_run_audit_report 呼出 + RunObservabilityReport に同梱
- archive `dsr` field の v2 入力切替 + sharpe_calc_version 同期
- run report / archive で AuditDSRMetric の log/report 露出

### 11.3 Phase 2 申し送り (詳細設計で明文化、 Round 1 反映)

- T071 詳細設計改訂申し送り: RunObservabilityReport に `audit: RunAuditReport` field 追加 (= status field 方式整合)
- T058 詳細設計改訂申し送り (Round 1 [W2] 反映):
  - archive `dsr` field を `dsr_v1` に rename + 新 field `dsr_v2` 追加 (= 履歴比較互換、 sharpe_calc_version 厳格運用)
  - genome admission 時の SessionBlock 列保存 (= T070 BacktestResult.session_blocks transport SSOT 継承、 Run 末尾再計算禁止)
- T064 / T066 / T067 詳細設計改訂申し送り: 必要なし (= T073 は selection 経路 touch しない)
- T071 / T072 collider bias 規範を audit consumer 側でも継承

### 11.5 既存 statistics.py docstring 整合 (Round R2 [C5] 反映)

T073 PR で **`audit.py` wrapper 関数 docstring に明文化**:
> 既存 `statistics.py:148` `deflated_sharpe_ratio` の数式 (Bailey & López de Prado 2014 Eq.(7) (9)) は **汎用**。 入力 SR の尺度 (= v1 bar-level annualized vs v2 session_block non-annualized) は本 wrapper の `null_model.sr_scale` SSOT で固定。 数式変更は別 TODO + AUDIT_DSR_CALC_VERSION bump.

加えて、 既存 `statistics.py` docstring の「v1 / Phase 1A monitor only」 注記は **同 PR で更新** (or 直後の別 PR で同期):
> "Phase 2: T073 audit layer (= v2 session_block non-annualized SR + AuditNullModel) で本関数を呼び出し、 archive `dsr` field の v1 入力切替も Phase 2 別 PR で実施 (sharpe_calc_version / audit_calc_version 同期)."

DoD § 11.6 で grep DoD を明示 (Round R2 [S4]):
- `audit.py` 経路と既存 `archive.py:81` `dsr` field 計算経路が **干渉しない** (= T073 module の import なし) を grep 確認
- 既存 statistics.py を呼出す経路が T073 audit のみで増えることを grep DoD として PR diff lint

### 11.6 AUDIT_REPORT_SCHEMA_VERSION bump 規約 (Round R2 [W5])

```
MAJOR (1.x.y → 2.0.0): 既存 field 削除 / 意味変更 / nested path 変更 (= 既存 caller 互換性破壊)
MINOR (1.0.y → 1.1.0): field 追加 (= 既存 caller は新 field を ignore で動作可)
PATCH (1.0.0 → 1.0.1): 出力値 bug fix のみ (= schema 不変)
```

Phase 2 例:
- `archive_sample` null_model_kind 追加 → MINOR bump (1.0.0 → 1.1.0)
- PBO/SPA に `pbo_value` / `performance_matrix` 等 field 追加 → MINOR bump (1.0.0 → 1.1.0)
- AuditDSRMetric から field 削除 / nested 変更 → MAJOR bump

### 11.4 collider bias / stratification 規範 (Round 1 [W4] / Round R2 [W1] 反映)

T072 § 9.6 の collider bias 規範を T073 audit consumer (= T071 / 後段 analytic) でも継承。 stratification key 候補を **概念で 1 行明示**:

> **stratification key (= caller responsibility)**:
>   - `holiday_markets`: frozenset[MarketCode] (T072)
>   - `dst_transition_markets`: frozenset[MarketCode] (T072)
>   - `schedule_status`: Literal["regular", "closed_full", "closed_partial"] (T072 derived)
> caller は上記 key の任意組合せで group_by して per-stratum AuditDSRMetric を計算可能。
> 単一 key で drop / filter ではなく、 **stratified report** で「holiday=tokyo 群 / no holiday 群」 のような split で集計する。
>
> **Round R2 [W1] 反映**: default は **marginal 集計のみ** (= 各 key 独立 1 軸 group_by、 sparse strata 量産防止)。 interaction (= 2 軸以上 cross product) は **事前登録した少数のみ**。 各 stratum で C7 規範 (n >= 30) を満たさない場合は status="insufficient_data"。

具体例:
```python
# T071 / T064 / T066 / 後段 analytic で実装 (default = marginal 集計)
marginal_by_holiday = collections.defaultdict(list)   # key = holiday_markets
marginal_by_dst = collections.defaultdict(list)       # key = dst_transition_markets
marginal_by_schedule = collections.defaultdict(list)  # key = schedule_status

# pre-registered interactions のみ (例: holiday × schedule_status の 2 軸)
PRE_REGISTERED_INTERACTIONS = (("holiday_markets", "schedule_status"),)

# → per-stratum DSR 分布を audit log に出力 (= 単独 drop しない、 各 stratum の n を audit に出力)
```

---

## 12. 設計判断 SSOT (synthesis 確定値 vs T073 設計判断値)

### 12.1 synthesis 確定値 (= 厳密準拠)

- DSR: 先行実装、 zenigame `_dsr.py:126` 同等 (= Bailey & López de Prado 2014 数式)
- PBO / SPA: 未実装タグ、 schema scaffold のみ、 smoke 後段階追加
- archive / report 層 (= early gate ではない)

### 12.2 T073 設計判断値 (= synthesis 未明示、 Phase 2 / smoke 後再校正)

- AUDIT_DSR_MIN_OBSERVATIONS = 30 (= C7 規範、 n<30 の相関 claim 禁止)
- mean_sr_trials = 0.0 / std_sr_trials = 1.0 (= H0 標準正規 null)
- 入力 block filter = `open_minutes > 0` (= T072 collider bias 規範継承、 holiday_markets 単独除外しない)
- audit_calc_version = "v2" (= cascade port v2 切替時の SSOT)
- AUDIT_REPORT_SCHEMA_VERSION = "1.0.0"
- AUDIT_SCAFFOLD_CALC_VERSION = "scaffold-v1" (= PBO/SPA 実装時の SSOT 移行用)
- per-Run 集約は archive 内全 genome 走査 (= cardinality 制限なし、 後段 evaluator が必要に応じて filter)

---

## 13. T074 / T075 への申し送り

- **T074 Graduation lane**: T073 RunAuditReport を graduation gate の参考情報として参照 (= early gate ではないので gate 判定には使わない)
- **T075 smoke**: 5 Run 連続で AuditDSRMetric の deterministic 性検証 (= 同 dataset で同 dsr_value、 hash 一致)
- **synthesis Round 22 改訂候補**: § 10.2 「DSR 先行実装」 の入力意味論を v2 (= SessionBlock 駆動) に明文化 (= T073 完了後に検討)

---

## 14. open questions (詳細設計で解消)

1. **mean_sr_trials / std_sr_trials の null 選択**: H0 標準正規 (= 0, 1) で固定するか、 archive 内 SR 分布の moment を渡すか。 後者は collider bias を呼ぶ可能性
2. **n_trials の入力源**: archive cardinality / Stage A 通過数 / 全 GA 評価数 のいずれか。 detail で SSOT 確定
3. **Decimal vs float**: AuditDSRMetric の dsr_value / sharpe_ratio 等は Decimal で SSOT (= 既存 statistics.py は float)。 conversion での精度損失検討
4. **per_genome_session_blocks の入力 source**: archive admission 時に保存するか / Run 末尾で再計算するか
5. **AUDIT_DSR_MIN_OBSERVATIONS=30 の妥当性**: C7 規範 (= n<30 で因果解釈避ける) と整合だが、 audit-only なので 30 で過剰か / 50 / 100 の trade-off
6. **scaffold metric の hash / eq 整合**: PBO / SPA scaffold は値固定なので全 instance が等価、 重複生成しても同 hash になるか
7. **既存 archive `dsr` field の deprecation 経路**: Phase 2 で v2 切替時に旧 v1 値を schema 削除 / 別 field 移行 / 上書きのいずれか
8. **PBO / SPA 実装 PR のタイミング**: smoke 完了 (T075) 後に T076 / T077 等で実装するか

---

## 15. references / cross-cut

| 項目 | 場所 |
|---|---|
| synthesis § 10.2 (Audit layer 段階導入) | `devnotes/20260428-2300-cascade-port-debate/synthesis.md` |
| synthesis § 18.2 T916 (= 本 TODO の親条文) | 同上 |
| 既存 deflated_sharpe_ratio (= Bailey & López de Prado 2014) | `src/alpha_factory/statistics.py:148` |
| 既存 archive `dsr` field (v1 入力) | `src/alpha_factory/archive.py:81` |
| zenigame `calc_dsr` (= z-score、 Φ 適用前) | `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/runner/_dsr.py:126` |
| T058 archive_role / source_stage / dataset_epoch_id | `devnotes/20260429-1912-todo-T058-schema-v2-contract/` |
| T070 SessionBlock | `devnotes/20260430-1810-todo-T070-backtest-engine-extension/` |
| T071 RunObservabilityReport | `devnotes/20260430-1925-todo-T071-observability/conceptual-design.md` § 4.2 |
| T072 collider bias 規範 (= holiday_markets 単独 drop 禁止) | `devnotes/20260430-2036-todo-T072-dst-holiday-boundary/detailed-design.md` § 9.6 |

---

## 15b. Round 1 → Round 2 対応マトリクス

| Round 1 | Round 2 対応 |
|---|---|
| C1 TL;DR と Phase 1 自己矛盾 | TL;DR を「純ライブラリ PR」 に統一、 § 11.1 で「runtime surface 不在」 明記 |
| C2 null model provenance 不在 | AuditNullModel dataclass 新設、 null_model_kind / mean / std / trial_source / n_trials を一括保持 (Phase 1 default = standard_normal H0) |
| C3 n_trials 母集合 SSOT 不在 | trial_source="run_evaluated_genomes" 第一値固定 (= 保守的、 multiple testing correction 整合) |
| C4 TL;DR と invariant の filter 条件不整合 | TL;DR を `open_minutes > 0` のみに統一、 expected_bar_count 言及削除 |
| C5 per_genome_dsr が genome_id 不持 | AuditGenomeRecord 新設、 RunAuditReport.per_genome は tuple[AuditGenomeRecord, ...]、 T058 archive_role / source_stage と join 可 |
| C6 Decimal("NaN") sentinel 問題 | SCAFFOLD_SENTINEL_VALUE = Decimal("0") 固定、 全 sentinel field で同値、 hash/eq/JSON round-trip 安全 |
| C7 input_non_finite と degenerate_variance 統合不適切 | status 6 値 (ok / insufficient_data / insufficient_trials / degenerate_variance / input_non_finite / not_implemented) で分離 |
| C8 SessionBlock transport 契約未固定 | T070 BacktestResult.session_blocks transport SSOT 継承、 archive admission 時保存 / Run 末尾再計算禁止、 GenomeAuditInput dataclass で input 一括 |
| W1 AUDIT_DSR_MIN_OBSERVATIONS 理論閾値か運用閾値か | docstring で「運用最低観測数」 と明記 |
| W2 archive.dsr の Phase 2 切替方針 | dsr_v1 / dsr_v2 併存 SSOT (= 履歴比較互換、 sharpe_calc_version 厳格運用) を § 11.3 / TL;DR で明記 |
| W3 N=1 PSR fallback | 採用しない、 "insufficient_trials" sentinel に倒す |
| W4 stratification key 候補 | § 11.4 で `(holiday_markets, dst_transition_markets, schedule_status)` の任意組合せ SSOT 明示 |
| W5 PBO/SPA scaffold field 拡張余地 | AuditPBOMetric / AuditSPAMetric docstring に Phase 2 field 候補 (performance_matrix / cscv_n_splits / loss_differential / block_bootstrap_size 等) 明記 |
| S1 AuditGenomeRecord | 採用 (= C5 と同義) |
| S2 AuditNullModel | 採用 (= C2 と同義) |
| S3 status 6 値 | 採用 (= C7 と同義) |
| S4 Phase 1 純ライブラリ統一 | 採用 (= C1 と同義) |
| S5 synthesis Round 22 改訂 | § 10.2 文言を「audit DSR 入力は v2 SessionBlock cascade port」 と追記候補 |
| S6 scaffold sentinel = Decimal("0") | 採用 (= C6 と同義) |

## 16. 学術文献

- Bailey, D. H. & López de Prado, M. M. (2014). *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality.* Journal of Portfolio Management 40(5).
- Bailey, D. H. & López de Prado, M. M. (2012). *The Sharpe Ratio Efficient Frontier.* Journal of Risk 15(2). (PSR 参照)
- Bailey, D. H., Borwein, J. M., López de Prado, M. M., & Zhu, Q. J. (2015). *The Probability of Backtest Overfitting.* Journal of Computational Finance 20(4). (PBO / CSCV 一次資料、 T073 scaffold)
- Hansen, P. R. (2005). *A Test for Superior Predictive Ability.* Journal of Business & Economic Statistics 23(4). (SPA 一次資料、 T073 scaffold)

---

これで T073 概念設計の枠組みは完成。 Codex 概念レビュー (gpt-5.4 / medium) で falsification を試みる。
