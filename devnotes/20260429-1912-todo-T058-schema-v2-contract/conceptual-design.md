# 概念設計: T058 — Schema v2 contract (dataset_epoch_id 供給 + artifact 別契約)

**Round 1 修正反映** (Codex CHANGES_REQUESTED → CHANGES_APPLIED)。

## 背景・課題

zenigame-fx の selection cascade を big-bang baseline で全面再構築するにあたり、 **「epoch-rolling 24m dataset の epoch 識別子が複数 artifact 経路で永続化される schema」** を最優先で確立する必要がある。

具体的な課題:

1. **既存 archive schema (`GENOMES_SCHEMA` in `src/alpha_factory/archive.py:54`) には `dataset_epoch_id` が無い**。 zenigame `genome_archive.py:540` も同様。
2. **複数の永続化 artifact** (Parquet archive / calibrate-gate history JSONL / monitor / report / future warmstart filter / diagnostics sidecar / FSP archive / population.jsonl / run cache JSON / extract_batch_metrics 派生 JSON) で **`dataset_epoch_id` を必須化する仕組み (schema lint) が無い**。
3. **後段 TODO (T059-T075) のすべてが Schema v2 contract に依存する**。
4. **禁止事項 8 (ゲノム archive スキーマ変更時の値伝搬漏れ)** の最重要ポイント。 `config → runtime context → meta → consumer` の 4 段接続が全経路で揃わないと epoch 跨ぎ汚染が起きる。

## 前提検証 (C4)

| 前提 | verified | 出典 |
|---|---|---|
| `DatasetConfig` に dataset_epoch_id 不在 | ✓ | `src/alpha_factory/config.py:51` |
| `GenomeArchive._new_row()` は run_id/run_number/generation/instrument/lane_id のみ受取 | ✓ | `src/alpha_factory/archive.py:698` |
| `summary.json` に既存 `schema_version: "1.1"` あり (report 用) | ✓ | `scripts/alpha_factory/run_ga.py:875`, `tests/scripts/test_run_ga_parallel.py:172` |
| `calibrate_state` の scope は `base_config_hash + dataset_span + instrument + stage_gate_version` | ✓ | `src/alpha_factory/calibrate_state.py:44` |
| FSP updater は `pq.read_table()` を直接呼んで archive を書き換える | ✓ | `src/alpha_factory/fsp_updater.py:114` |
| diagnostics sidecar は独自 schema で Parquet を書く | ✓ | `src/alpha_factory/diagnostics_sidecar.py:34` |

## 改善アイデア

**「artifact 共通の最小契約」 + 「artifact 別の追加契約」 の二層構造**で fail-closed scheme を構築。 さらに **`dataset_epoch_id` の最上流供給源**を `RunContext` として T058 で追加する。

### 設計方針

1. **artifact 共通の最小契約** = `dataset_epoch_id` のみ (string、 grammar 固定)
2. **artifact 別契約** = artifact-local version + 必要に応じて role/stage 等の field を追加
3. **`schema_version` 名前衝突回避** = 既存 summary.json `schema_version` は維持、 cascade contract 用には別 key を新設
4. **T058 のスコープ** = `contract 定義 + source 導入 + passive validation` まで。 hard fail (fail-closed) は後段 (T067 合流時) で activate。 T058 段階では log warning + Counter 計測のみ。

### Artifact inventory (2 層構造)

Codex Round 2 推奨に従い、 「contract 必須 artifact」 (Tier 1) と「派生表示 artifact」 (Tier 2) を分離。

#### Tier 1: contract 必須 artifact (9 経路、 直接 lint 対象)

| # | Artifact | 経路 | 必須 field |
|---|---|---|---|
| 1 | Parquet archive | `src/alpha_factory/archive.py: GENOMES_SCHEMA` (`flush()` / `load()`) | `dataset_epoch_id`, `genome_entry_schema_version`, `archive_role`, `source_stage` |
| 2 | calibrate-gate history JSONL | `src/alpha_factory/calibrate_gate_history.py` (`append_record()`) | `dataset_epoch_id`, `calibrate_history_schema_version` |
| 3 | summary.json (run report) | `scripts/alpha_factory/run_ga.py:875` | `dataset_epoch_id`, `cascade_contract_version` (既存 `schema_version: "1.1"` は維持) |
| 4 | diagnostics sidecar Parquet (含 stage_a_provenance) | `src/alpha_factory/diagnostics_sidecar.py:34, :50` (`build_sidecar_table()`, `write_stage_a_provenance()`) | `dataset_epoch_id`, `diagnostics_schema_version` |
| 5 | FSP archive rewrite | `src/alpha_factory/fsp_updater.py:114` (`_read_archive_with_fsp_compat`, `_atomic_write_parquet`) | `dataset_epoch_id` (read 時 propagate、 write 時必須) |
| 6 | population.jsonl | `scripts/alpha_factory/run_ga.py:1008` | `dataset_epoch_id` (run-level metadata) |
| 7 | .cache/alpha_factory/runs/{run_id}.json | `scripts/alpha_factory/run_ga.py:1479` | `dataset_epoch_id` |
| 8 | extract_batch_metrics 派生 JSON | `scripts/alpha_factory/extract_batch_metrics.py:134` | `dataset_epoch_id` (read-side propagation) |
| 9 | run_alpha_sieve loader | `scripts/alpha_factory/run_alpha_sieve.py:220` | `dataset_epoch_id` (T058 段階は log_only、 T067 で fail_closed に切替) |

注: Round 1 で 4/5 を別行にしていたが、 sidecar と stage_a_provenance は同一実体 (`diagnostics_sidecar.py` 内の関数群) なので 1 行に統合。

#### Tier 2: 派生表示 artifact (summary.json 参照で dataset_epoch_id を間接保持、 直接 lint なし)

これらは Tier 1 (主に summary.json) を読んで派生生成される表示用 artifact。 直接 lint は不要だが、 生成元の Tier 1 artifact が v2 contract を満たせば自動的に dataset_epoch_id が伝搬する。 ただし**生成 logic で dataset_epoch_id を必ず引用すること**を契約として明記:

| # | Artifact | 生成元 | 引用方針 |
|---|---|---|---|
| D1 | history.json | `scripts/alpha_factory/run_ga.py:998` | run-level state、 dataset_epoch_id を含めて記録 |
| D2 | best_genome.json | `scripts/alpha_factory/run_ga.py:1003` | best individual snapshot、 dataset_epoch_id を含めて記録 |
| D3 | run-{N}.md | `scripts/alpha_factory/generate_run_report.py:800` | summary.json 由来の表示、 dataset_epoch_id をヘッダに表記 |
| D4 | batch_summary.json | `scripts/alpha_factory/compare_batch_runs.py:252` | 複数 run 集約、 各 run の dataset_epoch_id を保持 |
| D5 | comparison_report.md | `scripts/alpha_factory/compare_batch_runs.py:256` | batch_summary.json 由来 |
| D6 | analysis-claude.md | `scripts/alpha_factory/analyze_run.py:168` | summary.json 由来の解析、 dataset_epoch_id 表記 |
| D7 | sieve-R{N}.md | `scripts/alpha_factory/run_alpha_sieve.py:699` | sieve 派生レポート、 dataset_epoch_id 引用 |
| D8 | extract_batch_metrics --report Markdown | `scripts/alpha_factory/extract_batch_metrics.py:280` | 任意 Markdown 出力、 dataset_epoch_id 引用 |
| D9 | compare_batch_runs --output Markdown | `scripts/alpha_factory/compare_batch_runs.py:262` | compare モードの任意 Markdown 出力、 dataset_epoch_id 引用 |

**Tier 2 contract**: 「Tier 1 artifact から生成する際に dataset_epoch_id を含める」 を実装規約として明記、 直接 lint なし。 ただし Codex Round 3 [Suggestion] 反映で **軽量 non-blocking ガード** `assert_epoch_id_present_for_display(report_obj)` を Tier 2 生成スクリプト共通で適用。 引用漏れを log warning + Counter 計測 (fail させない、 表示用なので運用事故化しない)。

### artifact 別 contract 定義

```python
# src/alpha_factory/schema_contract.py (新規)

class ArchiveRole(StrEnum):
    MISSION_PASS = "mission_pass"
    PROGRESS_PASS = "progress_pass"
    SCORE_BYPASS = "score_bypass"

class SourceStage(StrEnum):
    A = "a"
    B = "b"
    C_LITE = "c_lite"
    C = "c"

# Common required (全 artifact)
COMMON_REQUIRED = {"dataset_epoch_id"}

# Artifact-specific contracts
GENOME_ENTRY_CONTRACT_V2 = COMMON_REQUIRED | {
    "genome_entry_schema_version",  # = 2
    "archive_role",
    "source_stage",
}

CALIBRATE_HISTORY_CONTRACT_V2 = COMMON_REQUIRED | {
    "calibrate_history_schema_version",  # = 2
}

RUN_REPORT_CONTRACT_V2 = COMMON_REQUIRED | {
    "cascade_contract_version",  # = 2 (既存 schema_version: "1.1" と別キー)
}

DIAGNOSTICS_CONTRACT_V2 = COMMON_REQUIRED | {
    "diagnostics_schema_version",  # = 2
}

# Validation
def assert_genome_entry_v2(record: dict) -> None: ...
def assert_calibrate_history_v2(record: dict) -> None: ...
def assert_run_report_v2(report: dict) -> None: ...
def assert_diagnostics_v2(record: dict) -> None: ...

# Grammar
DATASET_EPOCH_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")
def validate_epoch_id(value: str) -> None:
    """空文字禁止、 lowercase、 [a-z0-9_]+。"""
```

### dataset_epoch_id 最上流供給源 (RunContext)

`src/alpha_factory/run_context.py` (新規) で `RunContext` を定義:

```python
@dataclass(frozen=True)
class RunContext:
    """1 Run 全体で固定される runtime context。

    `run_ga.py` の startup で生成、 全 component (GA loop, archive, calibrate,
    diagnostics, FSP, sieve) が同じ source から読む。
    """
    run_id: str
    run_number: int
    dataset_epoch_id: str  # T059 (Epoch Manager) が決定論的に生成
    base_config_hash: str
    instrument: str
    # ... 必要最小限
```

T059 (Epoch Manager) は `RunContext.dataset_epoch_id` を生成して `RunContext` を組み立てる。 T058 では **`RunContext` の構造定義 + 最上流の受け皿**だけ実装、 値生成ロジック自体は T059 担当。

### grammar 固定

```python
DATASET_EPOCH_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")
# 例: "epoch_20260301_p1", "epoch_20260401_p2"
# 禁止: 空文字、 大文字、 ハイフン、 スペース
# 制約: 同一 epoch (= 同 dataset window 範囲) では決定論的に同一値を返す (T059 担当)
```

### Validator 配置 (T058: read/write 両方 log_only 統一、 T067 で fail_closed activate)

Codex Round 2 [Critical] 受入: T058 段階では **read/write 両方とも `enforcement_mode=log_only` で統一**。 「sieve loader で fail_closed」「read 時 v1 fail」 等の例外は T058 から削除、 T067 一斉切替に統合。

```python
# T058: 全経路 passive validation
def assert_genome_entry_v2(record: dict, mode: SchemaEnforcementMode) -> None:
    missing = GENOME_ENTRY_CONTRACT_V2 - record.keys()
    if missing:
        if mode == SchemaEnforcementMode.FAIL_CLOSED:
            raise SchemaContractError(f"missing fields: {missing}")
        else:  # LOG_ONLY (T058 default)
            logger.warning("schema_contract.passive_validation_failed", missing=missing, artifact="genome_entry", ...)
            _validation_failure_counter.inc()
```

read 経路 (sieve loader、 FSP read、 schema_version=1 archive 検出) も同じ `enforcement_mode` に従う:
- T058 段階 `LOG_ONLY`: v1 archive 発見 → warning + skip (read 結果から除外)、 fail させない
- T067 切替後 `FAIL_CLOSED`: v1 archive 発見 → `SchemaVersionError` raise

これで T058 単独で writer/reader が破綻しない。 移行整合性は T067 で一斉確保。

### enum 永続値 lower_snake_case (Codex Round 1 提案)

| field | enum member | 永続値 |
|---|---|---|
| ArchiveRole.MISSION_PASS | (Python) | "mission_pass" |
| ArchiveRole.PROGRESS_PASS | | "progress_pass" |
| ArchiveRole.SCORE_BYPASS | | "score_bypass" |
| SourceStage.A | | "a" |
| SourceStage.B | | "b" |
| SourceStage.C_LITE | | "c_lite" |
| SourceStage.C | | "c" |

downstream join/filter で揺れない lower_snake_case で統一。

## 期待効果

### live_criteria 達成への貢献 (間接)

- **epoch 跨ぎ汚染防止 (構造的)**: 過去 epoch の archive entry が新 epoch の warmstart で誤注入される事故を fail-closed で防ぐ。 cascade selection inflation 抑制
- **archive metadata の層別観測可能化**: archive_role と source_stage で「どの経路で archive 入りしたか」「どの stage で評価された個体か」 を後段 observability で**層別観測**できる (Codex Round 1 で「品質低下を検出可能」 から下方修正)
- **calibrate-gate epoch scope 厳密化**: zenigame T54 の `base_config_hash` ベース scope を `+ dataset_epoch_id` で一般化、 epoch 跨ぎ stale threshold 適用を防ぐ

### 副次効果

- **artifact 横断の epoch 識別**: 9 経路全て同一 `dataset_epoch_id` で揃うので、 後段 audit (PBO/SPA、 T073) や observability (T072) で epoch 跨ぎ集計が安全
- **zenigame 逆輸入候補**: synthesis § 19 の 4 候補のうち最先頭 (zenigame 側 T54 の一般化として持ち帰り価値あり)

## 実装方針 (概要)

### コンポーネント変更

| ファイル | 変更内容 |
|---|---|
| `src/alpha_factory/schema_contract.py` | **新規**。 4 contract 定義、 4 assert 関数、 ArchiveRole / SourceStage enum、 DATASET_EPOCH_ID_PATTERN、 SchemaEnforcementMode enum (LOG_ONLY / FAIL_CLOSED)、 SchemaContractError / SchemaVersionError 例外 |
| `src/alpha_factory/run_context.py` | **新規**。 `RunContext` dataclass (run_id / run_number / dataset_epoch_id / base_config_hash / instrument)。 T059 で `dataset_epoch_id` 値生成、 T058 では受け皿のみ。 全 component API に `run_context` 必須注入 (**最終到達点**。 T058 では主要 3 component (archive / calibrate / diagnostics) のみ適用、 全 component 必須化は T059/T063 合流時に段階的) |
| `src/alpha_factory/config.py` | `AlphaFactoryConfig` に `schema_contract: SchemaContractConfig` を追加 (Codex Round 2 [Warning] 反映)。 `SchemaContractConfig.enforcement_mode: SchemaEnforcementMode = LOG_ONLY` (default)。 T067 で `FAIL_CLOSED` に切替 |
| `config/alpha_factory/default.yaml` | `schema_contract.enforcement_mode: log_only` を新設 |
| `src/alpha_factory/archive.py` | `GENOMES_SCHEMA` に 4 field 追加 (`dataset_epoch_id`, `genome_entry_schema_version`, `archive_role`, `source_stage`)、 `_create_row_template` に default 追加、 `flush()` 冒頭に `assert_genome_entry_v2(mode=run_context.enforcement_mode)`、 `load()` で v1 検出時は mode に従って warning or fail |
| `src/alpha_factory/calibrate_gate_history.py` | record dataclass に `dataset_epoch_id` 追加、 `calibrate_history_schema_version=2` に bump、 `append_record()` 冒頭に `assert_calibrate_history_v2(mode=run_context.enforcement_mode)` |
| `src/alpha_factory/calibrate_state.py` | `find_latest_applicable` の scope key を `base_config_hash + dataset_epoch_id + instrument + stage_gate_version` に変更、 v2 必須 |
| `src/alpha_factory/diagnostics_sidecar.py` | `build_sidecar_table()` / `write_stage_a_provenance()` で `dataset_epoch_id` を必須 metadata、 `assert_diagnostics_v2(mode=run_context.enforcement_mode)` |
| `src/alpha_factory/fsp_updater.py` | `_read_archive_with_fsp_compat()` で v2 verify (mode に従って warning or fail)、 `_atomic_write_parquet()` で `dataset_epoch_id` propagate |
| `scripts/alpha_factory/run_ga.py` | `RunContext` 生成 (T059 完了後)、 `summary.json` に **`cascade_contract_version: 2` (int 固定)** + `dataset_epoch_id` 追加 (既存 `schema_version: "1.1"` は string 維持、 Codex Round 2 [Suggestion] 反映)、 `population.jsonl` / run cache JSON / history.json / best_genome.json にも propagate |
| `scripts/alpha_factory/run_alpha_sieve.py` | loader で `assert_genome_entry_v2(mode=run_context.enforcement_mode)` (T058 段階は LOG_ONLY、 T067 で FAIL_CLOSED) |
| `scripts/alpha_factory/extract_batch_metrics.py` | 派生 JSON 出力に `dataset_epoch_id` propagate (Tier 2、 引用方針) |
| `scripts/alpha_factory/generate_run_report.py` | run-{N}.md ヘッダに `dataset_epoch_id` 表記 (Tier 2 引用) |
| `scripts/alpha_factory/compare_batch_runs.py` | batch_summary.json / comparison_report.md に各 run の `dataset_epoch_id` 保持 (Tier 2 引用) |
| `scripts/alpha_factory/analyze_run.py` | analysis-claude.md に `dataset_epoch_id` 表記 (Tier 2 引用) |

### スコープ縮小ポリシー (Codex Round 1-3 提案受入)

T058 で実施するもの:
- contract 定義 (assert / enum / grammar / SchemaEnforcementMode)
- `RunContext` 受け皿実装 (値生成は T059 担当)。 ただし**必須注入は段階導入** (T058 では archive / calibrate / diagnostics の主要 3 component のみ、 全 component 必須化は T059/T063 合流時に段階的に締める)
- Tier 1 9 artifact 経路に passive validation (LOG_ONLY) を仕込む。 **read/write 両方 LOG_ONLY 統一** (read 時 v1 検出も warning + skip、 fail させない)
- Tier 2 軽量 non-blocking ガード (`assert_epoch_id_present_for_display`)
- `summary.json` 名前衝突回避 (`cascade_contract_version: int = 2` 別キー、 既存 `schema_version: "1.1"` (string) は維持)
- `SchemaContractConfig.__post_init__` で値検証 (許容値以外で ValueError)、 loader fallback 規約、 unknown key 拒否方針

T058 で実施しない (= 後段 TODO):
- T059: dataset_epoch_id 値生成ロジック + 「同一 window で同一 ID / window 違えば変化」 テスト
- T067 合流時: enforcement_mode を `LOG_ONLY` → `FAIL_CLOSED` に切替 activation。 **v1 archive を発見したら fail はこの段階で初めて実施** (T058 では fail させない)
- T063-T066: archive_role / source_stage 値書き込みロジック
- T067 合流時: 全 component への RunContext 必須注入完成
- T075: 旧 v1 archive Parquet 削除実行

## 制約・前提

- **passive validation (LOG_ONLY) で start**: T058 単独で fail-closed 有効化すると T063/T066 前の writer が全滅するため、 enforcement_mode で切替制御。 **read/write 両方 LOG_ONLY 統一** (Codex Round 3 [Critical] 受入)
- **v1 archive 排除は T067 で実施**: T058 段階では v1 検出時も warning + skip (fail させない)。 v1 を fail として扱うのは T067 で `enforcement_mode=FAIL_CLOSED` に切り替えた後
- **dataset_epoch_id 値生成は T059 担当**: T058 は受け皿 (RunContext) と grammar (regex) のみ
- **archive_role / source_stage の値書き込みは T063-T066 担当**: T058 は enum 定義 + lint のみ
- **RunContext 必須注入は段階導入**: T058 で `RunContext` 構造定義 + 主要 3 component (archive / calibrate / diagnostics) への注入のみ。 全 component 必須化は T059/T063 合流時に段階的に
- **既存 GENOMES_SCHEMA の他 field は維持** (run_id / instrument / lane_id 等)
- **Python 3.13 環境前提** (StrEnum は 3.11+)
- **memory 制約 24GB / 6 ワーカー / 1 ワーカー 3GB**: lint overhead は軽微 (Codex Round 1 確認済)
- **`SchemaContractConfig` 値検証**: `enforcement_mode` の許容値は `{"log_only", "fail_closed"}` のみ、 `__post_init__` で ValueError raise。 YAML 欠落時 fallback default = `log_only`、 unknown key は config loader で拒否

## スコープ外

- T059: epoch_id 値生成 / window manager
- T066: archive_role 判定ロジック (mission_pass / progress_pass / score_bypass)
- T063-T064: source_stage 値書き込みロジック
- T067: passive → fail_closed 切替 activation
- T075: 旧 v1 archive Parquet 削除
- v3 へのアップグレード経路 (将来検討)
- migration 経路 (big-bang のため不要)

## 学術引用 / 先行知見

- zenigame T54 (`docs/alpha-factory/stage-gates.md` § "T054: state file 経由の自動適用"): `base_config_hash` ベース scope。 fx は `dataset_epoch_id` を加えて一般化
- zenigame `genome_archive.py:540`: dataset_epoch_id 不在を Round 19 確認、 fx で先行
- 禁止事項 8 (archive スキーマ伝搬漏れ): zenigame audit (T508/T511) で繰り返し identify、 fail-closed で根絶
- Codex Round 1 (`devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-review-round-1.md`): artifact class 分割、 schema_version 名前衝突、 source 供給、 passive validation の 4 修正

## Round 1 → Round 2 → Round 3 の改訂点

### Round 1 → Round 2

| Round 1 [Critical/Warning] | 修正対応 |
|---|---|
| 4 field 全経路必須は誤り | artifact 別 contract に分割、 共通必須は dataset_epoch_id のみ |
| dataset_epoch_id 最上流供給源欠如 | `RunContext` 新設、 T058 で受け皿実装 |
| schema_version 名前衝突 | `cascade_contract_version` 別キー新設、 既存 `schema_version: "1.1"` は維持 |
| T058 単独 fail-closed で writer 全滅 | passive validation (log_only) で start、 T067 で activate |
| validator 配置 coverage 不足 | 全 artifact 経路を inventory 表に明示 |
| 期待効果文言が強すぎる | 「品質低下を検出可能」 → 「役割別に層別観測可能」 |
| enum 永続値 mixed case + hyphen | 全部 lower_snake_case に修正 |
| dataset_epoch_id grammar 未定義 | `^[a-z0-9_]+$`、 lowercase、 空文字禁止、 deterministic に固定 |

### Round 2 → Round 3

| Round 2 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [Critical] passive と read-fail の混在 | T058 では read/write 両方 `LOG_ONLY` で統一、 sieve loader / FSP read / v1 検出も `enforcement_mode` 連動。 fail_closed 一斉切替は T067 |
| [Warning] inventory 件数不一致 (9 と 10) | 4/5 (sidecar / stage_a_provenance) を 1 行統合、 件数 9 経路に修正 |
| [Warning] coverage 抜け (history.json, best_genome.json, run-{N}.md, batch_summary.json, comparison_report.md, analysis-claude.md) | 2 層 inventory 構造に再編。 Tier 1 (contract 必須 9 経路) + Tier 2 (派生表示 6 経路、 引用方針) |
| [Warning] enforcement_mode 着地点未定義 | `config/alpha_factory/default.yaml` の `schema_contract.enforcement_mode` セクション + `AlphaFactoryConfig.schema_contract` (`SchemaContractConfig`) で明示 |
| [Suggestion] RunContext は API 注入必須化 | 全 component API シグネチャに `run_context: RunContext` 必須注入を契約として明記 |
| [Suggestion] cascade_contract_version の型契約 | `cascade_contract_version: int = 2` (int 固定)、 既存 `schema_version: "1.1"` (string) と型空間を分離する旨を契約文に明記 |
| [Suggestion] dataset_epoch_id 決定論性 | T058 文書化 (本概念設計の grammar 節)、 T059 DoD で「同一 window で同一 ID / window 違えば ID 変化」 テストを規定 (T059 概念設計に申し送り) |

### Round 3 → Round 4

| Round 3 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [Critical] LOG_ONLY 統一と「read 時 v1 fail」 文言の二重化 | 「T058 で実施するもの」 から `read 時 v1 fail` 削除、 「制約・前提」 から「既存 v1 は読まない」 を「v1 検出時 warning + skip、 fail は T067」 に修正。 v1 fail 表記は T067 セクションのみに残す |
| [Warning] Tier 2 coverage 抜け (sieve-R{N}.md, extract_batch_metrics --report) | Tier 2 inventory に D7 (sieve-R{N}.md) と D8 (extract_batch_metrics --report) 追加 |
| [Warning] enforcement_mode の値検証 / fallback / unknown key | `SchemaContractConfig.__post_init__` で許容値検証 (ValueError)、 YAML 欠落時 fallback `log_only`、 unknown key は config loader で拒否 |
| [Warning] RunContext 必須注入の T058 一括実施は破壊半径過大 | 段階導入: T058 で `RunContext` 追加 + 主要 3 component (archive / calibrate / diagnostics) への注入。 全 component 必須化は T059/T063 合流時 |
| [Suggestion] Tier 2 軽量 non-blocking ガード | `assert_epoch_id_present_for_display(report_obj)` を Tier 2 生成スクリプト共通適用、 引用漏れを log warning + Counter 計測 (fail させない) |
| [Suggestion] `cascade_contract_version` 型固定テスト | JSON schema or pytest property test で `schema_version: str` と `cascade_contract_version: int` の型を固定 |
