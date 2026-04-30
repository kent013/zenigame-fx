# 概念設計: T069 — Calibrate-gate scope (epoch key + 3 Run freeze + Δ ≤ 0.03)

**作成日時**: 2026-04-30 17:04 JST (Round 2 改訂: 17:18 JST、 Round 3 改訂: 17:25 JST)
**設計者**: Claude
**M4 残**: 1/3 (T067/T068 完了、 本 TODO で M4 完了)
**前提**: synthesis Round 21 改訂後 (`devnotes/20260428-2300-cascade-port-debate/synthesis.md`)、 main@`c4119b6`
**改訂履歴**: Round 1 [C1-C4] / [W1-W3] / [S1-S3] + Round 2 [C5] / [W1-W2] 全反映 (`conceptual-review-round-1.md` / `conceptual-review-round-2.md` 参照)

**前提検証** (C4):
- synthesis § 8.6 「凍結窓 3 Run / 4 Run 目で更新 / |Δ| ≤ 0.03 / scope key=`dataset_epoch_id`」 が確定文 ✓
- synthesis § 9.3 「big-bang のため migration なし、 v2 で空 history から start」 が確定文 ✓
- synthesis § 12.1 「旧 `scripts/alpha_factory/calibrate_gate.py` を 3 Run freeze + epoch scope 仕様に置換」 が確定文 ✓
- T058 conceptual-design § 217 で `calibrate_gate_history.py` HistoryRecord に `dataset_epoch_id` 追加 + `calibrate_history_schema_version=2` bump が確定 ✓
- T058 conceptual-design § 218 で `load_calibrated_threshold` scope key に `dataset_epoch_id` 追加が確定 ✓
- T067 で Emergency mode trigger (mission=0 3 連続 + MA3<MA6-0.05) は EmergencyState 機構として担保済 (synthesis § 8.5)。 T069 では emergency 判定には触れない (synthesis § 8.6 のみ担当) ✓
- T059 (Epoch Manager) が `dataset_epoch_id` 値を生成、 T058 (RunContext) が caller に伝搬。 T069 はその値を「入力契約」 として扱うのみ (生成・伝搬は責務外) ✓

## 1. ゴール

synthesis § 8.6 を厳密準拠した **calibrate-gate scope の big-bang 改訂**:
1. **凍結窓 3 Run** (Run 単位、 record 単位ではない): epoch 内 最初 3 Run は threshold 適用せず (`decision="skip_frozen"`)、 4 Run 目以降から calibrate を有効化
2. **更新幅制限 |Δ| ≤ 0.03**: `threshold_delta_abs_max` を 0.03 に SSOT 化、 config validation で範囲制約を contract 化
3. **scope key = `dataset_epoch_id`** (synthesis § 8.6 厳密 1 軸): epoch 跨ぎでの threshold 再利用を fail-closed で阻止
4. **big-bang migration**: v1 history JSONL を read で skip (T058 で確定済の挙動を T069 で再確認)、 v2 record で空 epoch から start
5. **big-bang atomic cut**: T069 PR で **library + default.yaml + docs** を同時に更新 (caller 配線 = run_ga.py / scripts/calibrate_gate.py のみ Phase 2)

T912 (synthesis § 18.2) のうち calibrate-gate scope 相当のみが T069 範囲。 Emergency mode trigger は T067 で別途実装済 (T912 を T069/T067 に分割する形で扱う)。

## 2. C2 parallel-path 5 段階 grep + Consumer Inventory (Round 1 [W1] 反映)

T069 は既存 calibrate-gate path を改訂する。 並列実装の有無 + decision 値 / history 行数を読む下流 consumer を**両方**点検:

### 2.1 並列実装検証 (5 段階)

| 段階 | 検査 | 結果 |
|---|---|---|
| 直 import | `from src.alpha_factory.calibrate_gate import` 検索 | scripts/alpha_factory/calibrate_gate.py / src/ test 群のみ |
| alias | `import calibrate_gate as` | 不在 |
| relative | `from .calibrate_gate import` | 不在 |
| 再エクスポート | `__init__.py` 経由 | 不在 (src/alpha_factory/__init__.py で再 export なし) |
| runtime シンボル | `getattr(... "calibrate_gate"` | 不在 |

→ calibrate-gate path は単一系統。

### 2.2 Consumer Inventory (decision label / history row を読む経路、 Round 1 [W1] 反映)

| Consumer | ファイル | 読む対象 | T069 影響 |
|---|---|---|---|
| `compute_drift` | `src/alpha_factory/calibrate_gate_history.py:150-194` | `r.decision == "tighten" / "loosen" / "in_band"` で count | `skip_frozen` を新規 decision として認識すべし。 既存 count に影響しない (= count されないだけ)、 ただし W2 反映で `n_skip_frozen` を追加して可視化 |
| `load_calibrated_threshold` | `src/alpha_factory/calibrate_state.py:184-255` | `r.decision in {"tighten", "loosen"}` filter | `skip_frozen` は filter で自然除外 (= load 対象外、 §6.7 改訂後の SSOT)。 既存挙動と一貫 |
| `calibrate_gate_drift` CLI | `scripts/alpha_factory/calibrate_gate_drift.py` | `compute_drift` 経由 | 上記と同等、 監視出力に `skip_frozen` 件数を表示 (Phase 2 申し送り) |
| `_resolve_stage_a_threshold` | `scripts/alpha_factory/run_ga.py:1054-1089` | `load_calibrated_threshold` 経由 | freeze 中は `load_calibrated_threshold == None` (= scope match record 全 skip_frozen) で自然に config 値 fallback (= prev_threshold) |
| `scripts/alpha_factory/calibrate_gate.py` | (CLI) | `decide()` 結果を `HistoryRecord` に書き込み + yaml 更新 | Phase 2 で `evaluate_freeze_status` + `decide_with_freeze` 呼び替え + skip_frozen record append |
| `report.md` 出力 | (run report 経路) | calibrate-gate 関連 metric 表示 | run report 側は `decision` 文字列を機械的に表示するため `skip_frozen` 表示で問題なし。 Phase 2 で docs 更新 |
| `monitoring` (T915) / DSR / alpha_sieve | grep 結果上 calibrate-gate を読む import なし | — | T069 影響なし |

→ T069 影響は **2.2 の上記 6 経路のみ**、 並列実装なし。

## 3. アーキテクチャ概要

### 3.1 機能分割 (新設 1 module + 既存 module 拡張)

```
src/alpha_factory/
├── calibrate_freeze.py  ← 新設 (T069 中核)
│   ├── FreezeStatus       (dataclass, immutable)
│   ├── evaluate_freeze_status()  (pure function、 distinct Run 数で count)
│   └── decide_with_freeze()      (pure function、 既存 decide() を skip_frozen 経路と委譲経路に分岐)
├── calibrate_gate.py    ← 既存拡張
│   ├── DecisionLabel に "skip_frozen" 追加
│   └── CalibrateConfig.__post_init__ で |Δ| ≤ 0.03 contract 強化
├── calibrate_gate_history.py  ← T058 で改訂済 + T069 で軽追加
│   └── compute_drift に n_skip_frozen 追加 (Round 1 [W2] 反映、 任意)
└── calibrate_state.py    ← T058 で改訂済、 T069 で確認のみ
    └── load_calibrated_threshold は decision in {tighten, loosen} filter のため skip_frozen は自然除外

config/alpha_factory/default.yaml  ← T069 PR で同時更新 (Round 1 [C4] 反映)
└── stage_gate.stage_a.calibrate.threshold_delta_abs_max: 0.03
```

### 3.2 freeze 判定の scope key (Round 1 [C1] 反映、 synthesis § 8.6 厳密準拠)

```
scope_key = dataset_epoch_id   # synthesis § 8.6 SSOT、 1 軸単独
```

freeze 判定は **dataset_epoch_id 単独** で record をグループ化。 Round 1 [C1] の指摘どおり「synthesis 拡大解釈」 を排除し、 4 軸 composite scope は採用しない。

base_config_hash / instrument / stage_gate_version の整合性は **T058 `load_calibrated_threshold._record_matches`** が別途 verify する (= 別 layer の責務)。 freeze 判定と適用判定の責務を完全分離:
- **freeze 判定 (T069)**: 「epoch 内で何 Run calibrate-gate が走ったか」 だけを問う
- **適用判定 (T058)**: scope match + decision filter + range check の cross-run guard

これにより synthesis § 8.6 を 1 軸 SSOT で守りつつ、 T058 の 4 軸 cross-run guard も維持できる (= 多層防御)。

### 3.3 freeze 判定 (Round 1 [C2] 反映、 distinct Run 数で count)

```python
freeze_window = 3
matching_records = [r for r in history if r.dataset_epoch_id == current_epoch_id]
# Round 1 [C2] 反映: record 数ではなく distinct Run 数で count
distinct_run_ids = {r.applied_from_run_id for r in matching_records if r.applied_from_run_id}
epoch_distinct_run_count = len(distinct_run_ids)
is_frozen = (epoch_distinct_run_count < freeze_window)

is_frozen=True (= count ∈ {0, 1, 2}) → decision="skip_frozen"
is_frozen=False (= count >= 3)        → 通常 decide() に委譲
```

`applied_from_run_id` は T054 既存 field (`HistoryRecord.applied_from_run_id`) で、 重複 append / retry / backfill が起きても同 run_id は 1 度しか count されない。

`applied_from_run_id` が None (= 旧 record) は count から除外 (= v1 record skip と整合、 既存挙動)。

#### 3.3.1 applied_from_run_id 欠落の継続 (Round 2 [W1] 反映)

Round 2 [W1] 指摘: `applied_from_run_id is None` を count 除外する設計は、 欠落が続くと freeze が永久継続する。 対処:

- **T069 が T058 v2 schema に申し送り**: `HistoryRecord.applied_from_run_id: str` を **v2 で必須化** することを T058 詳細設計に追加要請 (= optional ではなく required field、 None は v2 record では発生しない)
  - これにより count 除外対象は「v1 record (= read_history で skip 済)」 のみとなり、 v2 record が連続欠落するシナリオが構造的に消える
- **T069 内の異常 log**: `evaluate_freeze_status` 内で `applied_from_run_id is None` の v2 record を発見した場合、 `calibrate_freeze.invalid_run_id` warning log を出力 (defense-in-depth)
- 異常 log がでた場合は call site (Phase 2) でアラート発報できるよう、 § 7 の log 契約に含める

### 3.4 skip_frozen の state 反映経路 (Round 1 [C3] / Round 2 [C5] 反映、 SSOT 統一 + 跨ぎ再利用遮断)

**SSOT**: `skip_frozen` record は `load_calibrated_threshold` の **load 対象外** (= `_record_matches` の `decision in {tighten, loosen}` filter で自然除外)。

#### 3.4.1 epoch 跨ぎ再利用の遮断 (Round 2 [C5] 反映、 重要)

Round 2 [C5] 指摘: 「freeze 中 → load=None → config 値 fallback」 だけでは「前 epoch の calibrate で yaml 書き換えられた threshold」 が config 経由で次 epoch に流入する。

これを概念で塞ぐため、 T069 では **「T069 自体は yaml への threshold 書き戻し経路を作らない」** + **「Phase 2 で yaml 更新方式の見直しを義務化」** の 2 段で対処する:

##### (a) T069 (Phase 1) の責務範囲

T069 PR では:
- `evaluate_freeze_status` / `decide_with_freeze` の library 実装
- `default.yaml` の `threshold_delta_abs_max: 0.03` SSOT のみ touch
- **`stage_a_threshold` (= calibrate 対象値) への yaml 書き戻し経路は touch しない** (= 既存 `update_threshold_atomic` の caller 配線は Phase 2)

これにより T069 単独では「config (yaml) の threshold 値が変化する」 経路は発生しない。

##### (b) Phase 2 (cascade port 切替) で確定する跨ぎ再利用遮断方式

Phase 2 で次のいずれかを採用 (= synthesis § 12.3 の「`stage_gate.stage_a.threshold` を動的 q_force に置換」 と整合する形で確定):

| 案 | 内容 | 評価 |
|---|---|---|
| **A: yaml threshold は immutable seed、 calibrate は state file (history JSONL) 専用** | yaml は initial seed、 calibrate-gate は yaml に書き戻さず history JSONL のみで状態管理。 freeze 中は config 値 (= immutable seed) が採用されるので跨ぎ再利用なし | synthesis § 12.3 (stage_a.threshold 削除) と整合、 推奨 |
| **B: epoch 切替時に yaml の threshold を factory default にリセット** | T059 epoch manager の epoch 切替フックで yaml を reset | yaml mutation 残るため fragile |
| **C: cascade port 後 architecture で stage_a_threshold 自体を削除** | synthesis § 12.3 厳密準拠、 calibrate 対象 parameter を変更 (= q_force base 値 / target_pass_rate などへ) | architecture 大改訂、 Phase 2 で別途設計 |

**推奨**: 案 A (yaml = immutable seed、 calibrate は history JSONL 専用)。 Phase 2 で確定するが、 概念上はこの方向で T069 が組まれる前提。

##### (c) T069 自身の防御 (concept-level)

T069 (library 単独) でも以下を防御:
- skip_frozen の new_threshold は `config.prev_threshold` を **caller 側で T069 PR では yaml ではなく state-only に取得する想定** で docstring 化 (= caller 注入の意味を明示)
- `load_calibrated_threshold` の `_record_matches` で `base_config_hash` 不一致 record は除外 (T058 既存挙動) → epoch 切替で base_config_hash 変化があれば前 epoch の history record も自動除外 (4 軸 verify の副次効果)
- ただし「同じ config / 同じ instrument で epoch だけ rollover」 した場合は、 history 経路は遮断されるが yaml 経由は遮断されない → 案 A での Phase 2 確定を必須とする旨を docstring + § 12 #11 申し送りで固定

##### (d) §6.7 の旧記述削除

§6.7 の旧記述 (load_calibrated_threshold が skip_frozen を返す) は **削除/訂正**。 状態は単一系統 = 「freeze 中 → load_calibrated_threshold=None → config 値 (= immutable seed の前提)」 で確定。

### 3.5 Δ ≤ 0.03 contract 強化 (Round 1 [C4] 反映、 atomic cut)

T069 PR では **library + default.yaml を同時更新** (big-bang 原則):
- `CalibrateConfig.__post_init__` の contract: `0 < threshold_delta_abs_max <= 0.03`
- `default.yaml` の `stage_gate.stage_a.calibrate.threshold_delta_abs_max: 0.03` を SSOT 化 (現値が 0.03 超なら同 PR で書き換え、 0.03 以下ならそのまま維持)
- 同時更新により Phase 1 単独 merge でも fail-closed が起きない

caller 配線 (run_ga.py / scripts/calibrate_gate.py) のみ Phase 2 申し送り (= cascade port 切替 commit、 synthesis § 12.4)。

## 4. データモデル

### 4.1 FreezeStatus (新規、 Round 1 [S1] 反映で命名変更)

```python
@dataclass(frozen=True)
class FreezeStatus:
    """epoch 内 freeze 判定結果 (immutable, pure data).

    Round 1 [S1] 反映: epoch_distinct_run_count に命名統一 (record 数との誤読防止).
    """

    is_frozen: bool
    epoch_distinct_run_count: int   # 現 dataset_epoch_id にマッチした
                                     # distinct applied_from_run_id 数
    freeze_window: int               # 凍結窓 (default 3、 synthesis § 8.6 SSOT)
    next_run_index_in_epoch: int     # 現 Run が epoch 内で何 Run 目になるか (1-indexed)
                                     # = epoch_distinct_run_count + 1
```

不変条件:
- `is_frozen ⇔ (epoch_distinct_run_count < freeze_window)`
- `next_run_index_in_epoch == epoch_distinct_run_count + 1`
- `freeze_window >= 1` (= 0 だと freeze 機構が無効化される、 contract violation で ValueError)

### 4.2 DecisionLabel 拡張

```python
DecisionLabel = Literal[
    "tighten",
    "loosen",
    "in_band",
    "skip_disabled",
    "skip_sample_size",
    "skip_zero_variance",
    "skip_frozen",          # ← T069 新設
]
```

`skip_frozen` semantics (Round 1 [C3] / [S2] / [S3] 反映):
- epoch_distinct_run_count < freeze_window で発火
- new_threshold = config.prev_threshold (= caller 注入の現行 threshold、 docstring 明記)
- raw_target_threshold = None (decide() の quantile-snap を呼ばない)
- effective_sample_size = sample.n_rows_used (集計済 sample があっても適用しない)
- 既存 in_band / skip_* と同じく history record として記録される (drift 監視のため、 [S3] 反映で全 consumer 共通の文字列 `"skip_frozen"`)
- **load_calibrated_threshold で filter 除外** (T058 既存挙動で `decision in {tighten, loosen}` のみ採用)

### 4.3 HistoryRecord (T058 で確定済、 T069 では確認のみ)

T058 detailed-design で:
- `dataset_epoch_id: str` 必須化
- `calibrate_history_schema_version: int = 2` 必須化
- v1 record (`calibrate_history_schema_version` 不在) は `read_history` で skip
- `applied_from_run_id` は T054 既存 (T058 で削除されない)

T069 では新 field 追加なし。 ただし `decision == "skip_frozen"` を新規 decision 値として書き込む経路を確認 (validate_schema には影響なし、 文字列値のため)。

### 4.4 compute_drift 拡張 (Round 1 [W2] 反映、 任意)

`DriftAnalysis` に `n_skip_frozen: int` を追加 (任意 field、 既存 caller 影響なし):
```python
@dataclass(frozen=True)
class DriftAnalysis:
    records: tuple[HistoryRecord, ...]
    alerts: DriftAlerts
    n_tighten: int
    n_loosen: int
    n_in_band: int
    n_skip_frozen: int  # ← T069 追加
    n_clamped_floor_ceiling: int
    max_abs_gap: float
```

これで drift 監視で「freeze 中の Run 数」 を可視化できる。 alerts ロジックは変更なし (skip_frozen は alert 対象外、 = 期待動作)。

## 5. API シグネチャ (§ 11.2 SSOT 規約: 本節が正本)

### 5.1 evaluate_freeze_status

```python
def evaluate_freeze_status(
    records: Sequence[HistoryRecord],
    *,
    dataset_epoch_id: str,
    freeze_window: int = 3,
) -> FreezeStatus:
    """epoch 内 calibrate freeze 判定を行う (pure function).

    scope key = dataset_epoch_id (synthesis § 8.6 厳密 1 軸) で history record を filter し、
    distinct applied_from_run_id 数が freeze_window 未満なら is_frozen=True を返す.

    Args:
        records: 全 history record (caller で read_history 済の list).
                 read_history で v1 record は skip 済前提 (T058 確定挙動).
        dataset_epoch_id: 現 RUN の epoch 識別子 (T058 / T059 担当の値).
                          空文字 / None は ValueError (caller 運用契約: dataset_epoch_id 空なら
                          calibrate-gate 自体を起動しない、 Round 1 [W3] 反映).
        freeze_window: 凍結窓サイズ (synthesis § 8.6 で 3 確定、 default=3、 1 以上必須).

    Returns:
        FreezeStatus.

    不変条件:
        - records 内の v1 record は read_history で既に skip 前提 (T058 SSOT).
        - dataset_epoch_id が str 必須 (空文字 / None は ValueError raise).
        - freeze_window >= 1 (0 / 負は ValueError raise).
        - distinct count: applied_from_run_id が None の record は count から除外.
    """
```

### 5.2 decide_with_freeze

```python
def decide_with_freeze(
    sample: AggregatedSample,
    config: CalibrateConfig,
    *,
    freeze_status: FreezeStatus,
) -> Decision:
    """freeze 判定込みで decide() を呼ぶ wrapper.

    freeze_status.is_frozen=True なら decision="skip_frozen" + new_threshold=config.prev_threshold で
    即時返却 (Round 1 [S2] 反映: new_threshold は caller 注入の prev_threshold = current threshold).
    False なら既存 decide(sample, config) を委譲呼び出し.

    Args:
        sample: 集計結果 (集計失敗時も skip_sample_size 経路があるため呼び側で必須).
        config: calibrate 設定 (config.prev_threshold が freeze 中の new_threshold ソース).
        freeze_status: §5.1 で計算した結果.

    Returns:
        Decision. freeze 中は raw_target_threshold=None / clamped_*=False / delta=0.0 で固定.
    """
```

### 5.3 既存 decide() は変更しない

`decide()` 自体は freeze logic を持たない。 freeze 機構は `decide_with_freeze()` の caller で完結。

## 6. 関連 module 変更点

### 6.1 calibrate_gate.py (既存拡張)

- `DecisionLabel` に `"skip_frozen"` 追加
- `CalibrateConfig.__post_init__` の `threshold_delta_abs_max` check を `> 0` から `0 < value <= 0.03` に強化
- 既存 `decide()` は変更なし (freeze logic は decide_with_freeze に分離)

### 6.2 calibrate_freeze.py (新規)

- 5.1 `evaluate_freeze_status`
- 5.2 `decide_with_freeze`
- 公開 API は 2 関数 + FreezeStatus dataclass = 3 公開シンボル

### 6.3 default.yaml (T069 PR 内で同時更新、 Round 1 [C4] 反映)

```yaml
stage_gate:
  stage_a:
    calibrate:
      threshold_delta_abs_max: 0.03  # synthesis § 8.6 SSOT
      # その他既存値は維持
```

T069 PR で library + default.yaml を atomic cut (big-bang)。 caller 配線 (run_ga.py / scripts/calibrate_gate.py) のみ Phase 2 申し送り。

### 6.4 calibrate_gate_history.py (T058 範囲 + T069 軽追加)

- T058 範囲: `HistoryRecord.dataset_epoch_id`, `read_history` v1 skip
- T069 軽追加: `DriftAnalysis.n_skip_frozen` field、 `compute_drift` で `n_skip_frozen = sum(1 for r in rec_tuple if r.decision == "skip_frozen")`

### 6.5 calibrate_state.py (T058 範囲、 T069 影響なし)

- T058 範囲: `load_calibrated_threshold(*, dataset_epoch_id, ...)` scope key 拡張、 `_record_matches` の dataset_epoch_id 必須化
- T069 影響なし: `_APPLY_DECISIONS = frozenset({"tighten", "loosen"})` で skip_frozen は自然除外 (既存挙動)

### 6.6 docs/alpha_factory/stage-gates.md (T069 PR 内で同時更新)

- 「T069: epoch key + 3 Run freeze + Δ≤0.03」 仕様の追記
- AGENTS.md `## calibrate-gate と state file 経由の自動適用 (T054)` の延長として T069 を追記

### 6.7 scripts/alpha_factory/calibrate_gate.py (Phase 2 申し送り)

T069 (Phase 1) では touch しない。 Phase 2 で:
- `RunContext` 注入 (T058 / T059 完了後)
- `evaluate_freeze_status` 呼び出しを startup 直後に追加
- `decide_with_freeze` を `decide` の代わりに使用
- HistoryRecord に dataset_epoch_id / applied_from_run_id 詰め替え (T058 で対応済)

### 6.8 scripts/alpha_factory/calibrate_gate_drift.py (Phase 2 申し送り)

T069 (Phase 1) では touch しない。 Phase 2 で:
- `DriftAnalysis.n_skip_frozen` を出力に追加 (display のみ)

### 6.9 run_ga.py (Phase 2 申し送り)

T069 (Phase 1) では touch しない。 Phase 2 で:
- `_resolve_stage_a_threshold` は **変更不要** (load_calibrated_threshold は freeze 中 None を返すため自然に config 値 fallback)
- 任意で `freeze 中` の log 出力追加 (Round 1 [W2] 反映: `freeze.status` 構造化 log)

## 7. ログ契約 SSOT (Round 1 [W2] / Round 2 [W2] 反映)

T069 が必須出力する構造化 log:

| event | 必須 fields | 出力タイミング |
|---|---|---|
| `calibrate_freeze.status` | `dataset_epoch_id`, `epoch_distinct_run_count`, `freeze_window`, `next_run_index_in_epoch`, `is_frozen`, `applied_from_run_id` (current) | freeze 判定直後 (Phase 2 で scripts/calibrate_gate.py 起動時) |
| `calibrate_freeze.invalid_run_id` (新規、 Round 2 [W1] 反映) | `dataset_epoch_id`, `n_v2_records_with_null_run_id` | v2 record で applied_from_run_id=None を発見時 (warning level、 monitor alert 候補) |
| `calibrate_gate.decision` (既存) | `decision`, `new_threshold`, `delta`, ... + `dataset_epoch_id` | decide_with_freeze 後 (skip_frozen 含む全 decision で出力) |
| `calibrate_gate.applied` (既存) | `applied`, `reason`, ... | yaml 更新後 (skip_frozen は applied=False, reason="frozen") |

`applied_from_run_id` (current) は freeze 判定の対象 Run の id を log に明示することで、 F5 (二重 append) の監査容易性を上げる (Round 2 [W2] 反映)。

これらの log 契約は T069 PR の docstring + Phase 2 の scripts/calibrate_gate.py 配線で固定。

## 8. C3 Collider bias 観点

freeze 判定は「distinct Run 数」 で決まる単純な count であり、 因果解釈は不要。 conditioning set:
- 入力: history record の dataset_epoch_id と applied_from_run_id
- 出力: is_frozen (bool)
- collider な中間集団なし

→ collider bias リスク 0。

## 9. C7 Sample size 観点

freeze 判定は本質的に sample-based ではなく count-based。 freeze 解除直後 (epoch_distinct_run_count == 3) の最初の calibrate は **n_used >= min_sample_size** が config で contract 化されている既存仕様で吸収される。 freeze と sample size 制約は直交。

## 10. C9 Falsification-first

T069 が壊れる経路を **先に列挙** (Round 1 失敗モード追加候補も統合):

| 失敗モード | 検出方法 | 対処 |
|---|---|---|
| F1: scope_key 不一致で count 過大 | unit test: 異なる dataset_epoch_id record を mix し count=正しい value | `evaluate_freeze_status` で dataset_epoch_id 完全一致のみ採用 |
| F2: v1 record が count に混入 | T058 read_history skip 後の records を入力前提 | docstring で「v2 record only」 を明記 |
| F3: epoch 切替で count reset 失敗 | unit test: epoch_id 変更で count=0 を確認 | dataset_epoch_id 不一致 record は filter で除外 |
| F4: skip_frozen が history に append されない | scripts/calibrate_gate.py 既存挙動で全 decision を append (in_band 含む) | Phase 2 で skip_frozen も同経路で append、 docstring で固定 |
| F5: 同一 Run の二重 append で freeze が早期解除 (Round 1 追加) | distinct applied_from_run_id count で吸収 | `epoch_distinct_run_count = len({r.applied_from_run_id for r in matching})` |
| F6: 同 dataset_epoch_id で base_config_hash 変化 (Round 1 追加) | T058 `load_calibrated_threshold` で base_config_hash 不一致 → load 対象外 | freeze 判定は dataset_epoch_id 単独で count、 適用判定 (T058) は 4 軸 verify、 多層防御 |
| F7: skip_frozen の state 解決が分裂 (Round 1 追加) | §3.4 SSOT で「load 対象外 → config 値 fallback」 一本化 | §6.7 旧記述削除、 unit test で確認 |
| F8: |Δ| > 0.03 の config を読む | `CalibrateConfig.__post_init__` で fail-closed | ConfigError raise |
| F9: freeze_window 引数で 0 / 負を受ける | `evaluate_freeze_status` 内で `freeze_window >= 1` check | ValueError raise |
| F10: dataset_epoch_id 空文字 / None で混入 (Round 1 [W3] 追加) | caller 運用契約 + `evaluate_freeze_status` 内で str + 非空 check | ValueError raise |
| F11: 同 scope record が多数 (epoch_distinct_run_count >> 3) | freeze 判定は count >= 3 のみ確認 (上限なし) | 通常 calibrate に流れる、 issue なし |
| F12: monitoring/report が `skip_frozen` を未知 label として reject (Round 1 追加) | DecisionLabel 集計は機械的 string 一致のみ、 未知 label を reject する consumer なし (Consumer Inventory § 2.2 で確認済) | T069 PR で `compute_drift.n_skip_frozen` 追加で先行対応 |
| F13: Phase 1 単独 merge で default.yaml 0.03 超のため fail-closed (Round 1 [C4] 追加) | T069 PR で library + default.yaml を atomic cut | big-bang 原則統一 |
| F14: epoch 跨ぎで前 epoch 由来 threshold が config 経由で再利用 (Round 2 [C5] 追加) | T069 単独で yaml 書き戻し経路を作らない (Phase 2 で案 A: yaml=immutable seed 確定)。 base_config_hash 不一致は T058 4 軸 verify で別 layer 除外 | concept-level 明文化 (§3.4.1)、 Phase 2 必須申し送り |
| F15: applied_from_run_id None v2 record で freeze 永久継続 (Round 2 [W1] 追加) | T058 v2 schema で applied_from_run_id 必須化を申し送り + T069 内で異常 log emit (calibrate_freeze.invalid_run_id) | concept + Phase 2 申し送り (§3.3.1, §7) |

## 11. 期待効果

### 11.1 synthesis § 8.6 厳密準拠

- 凍結窓 3 Run: 新 epoch 開始直後の small-sample による誤 calibrate を抑止 (distinct Run count で robust)
- |Δ| ≤ 0.03: threshold の急変動を fail-closed で抑止 (config violation で起動拒否)
- scope key=dataset_epoch_id: epoch 跨ぎ汚染を fail-closed で阻止 (T058 と統合、 多層防御)

### 11.2 副次効果

- big-bang 切替で v1 history を完全分離、 cascade port の整合性向上
- decide() の単体テストへの影響 0 (freeze 機構は別 wrapper に分離)
- distinct Run count で retry / 二重 append への耐性向上 (Round 1 [C2] 反映)
- Phase 2 配線時に最小変更 (caller で `decide` → `decide_with_freeze` に置換、 `evaluate_freeze_status` を startup に追加)

## 12. Phase 1 / Phase 2 申し送り (合計 12 項目、 Round 2 反映で T058 schema 改訂申し送り + yaml 書き戻し方式 Phase 2 確定 を追加)

### Phase 1 (T069 PR で同時更新、 big-bang atomic cut)

| # | 箇所 | 変更内容 |
|---|---|---|
| 1 | `src/alpha_factory/calibrate_freeze.py` | 新設 (FreezeStatus + 2 関数) |
| 2 | `src/alpha_factory/calibrate_gate.py` | DecisionLabel + CalibrateConfig contract 強化 |
| 3 | `src/alpha_factory/calibrate_gate_history.py` | DriftAnalysis.n_skip_frozen 追加 |
| 4 | `config/alpha_factory/default.yaml` | threshold_delta_abs_max=0.03 SSOT |
| 5 | `docs/alpha_factory/stage-gates.md` | T069 仕様追記 |
| 6 | `tests/alpha_factory/test_calibrate_freeze.py` | F1-F13 unit test |

### Phase 2 (cascade port 切替 commit、 synthesis § 12.4)

| # | 箇所 | 変更内容 | 担当 |
|---|---|---|---|
| 7 | `scripts/alpha_factory/calibrate_gate.py` | `evaluate_freeze_status` + `decide_with_freeze` 配線、 `RunContext.dataset_epoch_id` 注入、 skip_frozen record append、 **yaml 書き戻し方式の確定 (案 A: immutable seed 推奨、 Round 2 [C5] 反映)** | Phase 2 |
| 8 | `scripts/alpha_factory/calibrate_gate_drift.py` | n_skip_frozen を出力に追加 | Phase 2 |
| 9 | `scripts/alpha_factory/run_ga.py` | freeze 中の log 追加 (任意)、 _resolve_stage_a_threshold は変更不要 | Phase 2 |
| 10 | caller 運用契約 | dataset_epoch_id 空なら calibrate 起動しない preflight check (Round 1 [W3] 反映) | Phase 2 |
| 11 | T058 詳細設計 申し送り | `HistoryRecord.applied_from_run_id: str` を v2 で **必須化** (Round 2 [W1] 反映、 None 排除) | T058 詳細設計改訂 |
| 12 | Phase 2 確定: yaml threshold 跨ぎ再利用遮断 | 案 A (yaml=immutable seed) / B (epoch reset) / C (architecture 改訂) のいずれか確定 (Round 2 [C5]) | Phase 2 (cascade port 切替) |

## 13. 制約 / 非目標 (T069 範囲外)

| 項目 | 担当 |
|---|---|
| Emergency mode trigger (mission_pass=0 3 連続 + MA3<MA6-0.05) | T067 で実装済 |
| Emergency 時の warmstart_share boost (25%) | T067 |
| dataset_epoch_id 値生成 | T059 epoch manager |
| RunContext / dataset_epoch_id 伝搬 | T058 |
| HistoryRecord schema v2 必須化 / v1 read skip | T058 |
| load_calibrated_threshold scope key 拡張 (4 軸) | T058 |
| run_ga.py / scripts/calibrate_gate.py への配線 | Phase 2 (cascade port 切替 commit) |

## 14. 削除対象 (Big-bang)

synthesis § 12.1 の旧 `scripts/alpha_factory/calibrate_gate.py` 「3 Run freeze + epoch scope 仕様に置換」 を T069 で実現するための **library 基盤** + **default.yaml SSOT** + **docs** が T069 PR の責務。 caller 自体の置換 (= 旧 path 削除 / scripts 改造) は cascade port 切替 commit (synthesis § 12.4) で同日実施。

T069 PR では `scripts/alpha_factory/calibrate_gate.py` の **削除 / 大改造は行わない**。

## 15. テスト方針 (Phase 1)

### 15.1 新規 `tests/alpha_factory/test_calibrate_freeze.py`

- F1-F13 + F15 各失敗モードの unit test (Phase 1 範囲)
- F14 (epoch 跨ぎ yaml 書き戻し再利用) は Phase 2 配線後の integration test 範囲 (Phase 2 申し送り)
- Happy path:
  - epoch 内 0/1/2 distinct Run で freeze、 3/4/5 で通常 decide
  - distinct count: 同 run_id 二重 append で count 増えない (F5)
  - dataset_epoch_id 切替で count=0 reset (F3)
  - applied_from_run_id None record は count 除外 + `calibrate_freeze.invalid_run_id` warning 出力 (F15)
  - freeze 解除直後 (count=3) で `decide_with_freeze` が `decide` に完全委譲

### 15.2 既存 `tests/alpha_factory/test_calibrate_gate.py` 拡張

- DecisionLabel に "skip_frozen" 追加に伴う型 check
- `CalibrateConfig.__post_init__` の `threshold_delta_abs_max > 0.03` で ConfigError raise (F8)
- `threshold_delta_abs_max == 0.03` で OK
- `threshold_delta_abs_max == 0.0` (= 0 以下) で ConfigError raise

### 15.3 既存 `tests/alpha_factory/test_calibrate_gate_history.py` 拡張

- `DriftAnalysis.n_skip_frozen` field check
- skip_frozen record が monotone alert に**含まれない**ことを確認

外部通信 (Parquet read / yaml write) は本 PR では触らない (Phase 2 で integration test)。

## 16. 実装影響範囲 (LOC 概算、 Round 1 反映後)

| ファイル | 追加 | 削除 | 備考 |
|---|---|---|---|
| `src/alpha_factory/calibrate_freeze.py` | +130 | 0 | 新規 (FreezeStatus + 2 関数 + docstring) |
| `src/alpha_factory/calibrate_gate.py` | +5 | 0 | DecisionLabel 拡張、 contract 強化 |
| `src/alpha_factory/calibrate_gate_history.py` | +5 | 0 | n_skip_frozen 追加 |
| `config/alpha_factory/default.yaml` | +1 | -1 | 0.03 値書き換え (現値が異なる場合) |
| `docs/alpha_factory/stage-gates.md` | +30 | 0 | T069 仕様追記 |
| `tests/alpha_factory/test_calibrate_freeze.py` | +220 | 0 | 新規 (F1-F13 + happy path) |
| `tests/alpha_factory/test_calibrate_gate.py` | +25 | 0 | DecisionLabel + contract test |
| `tests/alpha_factory/test_calibrate_gate_history.py` | +15 | 0 | n_skip_frozen test |
| **合計** | **+431** | **-1** | |

## 17. 主要な設計判断サマリー (Round 1 反映後)

1. **scope key を synthesis § 8.6 厳密 1 軸 (dataset_epoch_id) に固定** (Round 1 [C1]): 4 軸拡張は採用せず、 base_config_hash 等の整合は T058 load_calibrated_threshold (4 軸 verify) で別 layer 担保。 多層防御で synthesis 準拠
2. **distinct Run count で freeze 判定** (Round 1 [C2]): record 数ではなく `applied_from_run_id` の distinct set 数。 二重 append / retry に耐性
3. **skip_frozen state 解決は load 対象外で SSOT 統一** (Round 1 [C3]): freeze 中 → load=None → config 値 fallback。 §6.7 旧記述削除、 単一系統
4. **big-bang atomic cut** (Round 1 [C4]): T069 PR で library + default.yaml + docs を同時更新、 Phase 1 単独でも fail-closed 起こさない。 caller 配線のみ Phase 2
5. **|Δ| ≤ 0.03 を contract 強化**: SSOT を CalibrateConfig.__post_init__ に固定、 違反 yaml で fail-closed
6. **decide() は変更しない、 decide_with_freeze() を新設**: 既存 unit test 影響 0、 単一責任の分離
7. **skip_frozen も history record に append**: drift 監視継続のため、 ただし `_record_matches` の `decision in {tighten, loosen}` filter で load 対象外 (= 自然に config 値 fallback)
8. **Consumer Inventory 棚卸し** (Round 1 [W1]): compute_drift / load_calibrated_threshold / drift CLI / run_ga / scripts/calibrate_gate / report の 6 経路を概念で固定
9. **ログ契約 SSOT 化** (Round 1 [W2] / Round 2 [W2]): `calibrate_freeze.status` + `calibrate_freeze.invalid_run_id` event 必須 fields を概念で固定 (applied_from_run_id 含む)
10. **caller 運用契約: dataset_epoch_id 空なら calibrate 起動しない** (Round 1 [W3]): preflight check は Phase 2 申し送り
11. **epoch 跨ぎ再利用遮断: T069 では yaml 書き戻し経路を作らない** (Round 2 [C5]): Phase 2 で案 A (yaml=immutable seed) を推奨確定、 史実上の前 epoch threshold 流入を構造的に防ぐ
12. **applied_from_run_id v2 必須化を T058 に申し送り** (Round 2 [W1]): None 欠落の永久 freeze を構造的に消す + 異常 log emit で defense-in-depth
