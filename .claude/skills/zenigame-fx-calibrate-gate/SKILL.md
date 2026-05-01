---
name: zenigame-fx-calibrate-gate
description: 前 Run の archive Parquet から Stage A 実 pass rate を集計し、stage_gate.stage_a.threshold を deterministic に動的調整する (T027)
argument-hint: "[run_id] [--dry-run]"
---

# zenigame-fx Stage A Gate キャリブレーション

前 Run の archive Parquet (`.cache/alpha_factory/runs/genomes_{run_id}.parquet`) から
Stage A 実 pass rate を集計し、`config/alpha_factory/default.yaml` の
`stage_gate.stage_a.threshold` を **deterministic な制御則** で次 Run 用に更新する。

**判断主体は数式 (deterministic)**。Phase 2 では LLM 判断を導入しない。
詳細は `docs/alpha_factory/concepts/calibrate-gate.md` 参照。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `run_id` ($1) | No | 分析対象の run_id (例: `run_20260423_195917`)。省略時は最新 Parquet を自動選択 |
| `--dry-run` | No | 提案出力のみで yaml を更新しない |

---

## 手順

### Step 1: スクリプト呼び出し

```bash
uv run python scripts/alpha_factory/calibrate_gate.py [--run-id RUN_ID] [--dry-run]
```

exit code:

| code | 意味 |
|------|------|
| 0 | 成功 (in_band / tighten / loosen) |
| 2 | invalid arg |
| 3 | no archive |
| 4 | calibrate disabled (`stage_gate.stage_a.calibrate.enabled=false`) |
| 5 | yaml IO error |
| 6 | sample size insufficient (n < `min_sample_size`) |
| 7 | zero variance (var(fitness_pen) <= eps_var) |
| 8 | schema mismatch (Parquet schema 不一致 / 不正 null / NaN) |

### Step 2: ログと報告の解釈

stderr に JSONL ログ (`calibrate_gate.input` / `calibrate_gate.monitoring` /
`calibrate_gate.decision` / `calibrate_gate.applied`) が出力される。
stdout に human-readable レポート (Markdown 表) が出力される。

### Step 3: 結果報告 (ユーザー向け)

スクリプトの出力をそのままユーザーに転送する。decision 種別ごとに次のアクションを示唆:

- `in_band`: dead-band 内のため変更なし。次 Run はそのまま実行
- `tighten`: pass 率が高すぎ → threshold を上げた
- `loosen`: pass 率が低すぎ → threshold を下げた
- `skip_*`: 安全側に倒して未変更。skip 理由を確認

---

## 制御則の概要

```
target_pass_rate = 0.15 (config SSOT)
tol = 0.05 (dead-band 半幅)
actual = aggregate_pass_rate(rows, mode, window)

if abs(actual - target) <= tol:
    decision = "in_band"
elif var(fitness_pen) <= eps_var:
    decision = "skip_zero_variance"
else:
    q_target = quantile(fitness_pen_pool, 1 - target)
    delta = clamp(q_target - prev_threshold, -max_delta, +max_delta)
    new_threshold = clamp(prev_threshold + delta, floor, ceiling)
    decision = "tighten" if actual > target + tol else "loosen"
```

aggregation_mode の既定は `last_k_generations` (window=5)。
`generation_weighted_mean` / `all_generations` も SSOT で切替可能。

---

## 注意事項

- 編集対象は `stage_gate.stage_a.threshold` のみ。他キーは触らない
- yaml の atomic update + flock で同時実行衝突を回避
- monitoring 指標 (Stage B/C 通過数 / live_criteria gap) は **観察記録のみ**。
  threshold 変更の判断には使わない (C3 collider bias 回避)
- `calibrate.enabled=false` で全停止可能（緊急時の fallback）
- LLM 判断による動的調整は別 TODO (本 skill は deterministic 専用)

### T054: state file 経由の自動適用

calibrate-gate は yaml 直接書き戻しに加え、`reports/calibrate-gate/history.jsonl`
に cross-run contamination guard 用 metadata 付き record を書き込む。

T058 (2026-04-30) で record schema は **v2 に bump** された:
- `calibrate_history_schema_version=2` (T058 で必須化、 `__post_init__` で値固定検証)
- `dataset_epoch_id` (T058 で必須化、 grammar `[a-z0-9_]+`、 epoch-rolling 識別子)
- T054 既存 metadata: `schema_version`, `base_config_hash`, `full_config_hash`,
  `dataset_span`, `instrument`, `stage_gate_version`, `applied_from_run_id`

`read_history` は v1 record (`calibrate_history_schema_version` / `dataset_epoch_id`
を欠く record) を **skip + warning log** (`calibrate_history.v1_or_invalid_record_skipped`)
で扱う。 v1 record はそのまま filter 処理に流れず、 cross-run scope key 評価は
v2 record のみが対象となる。

run_ga.py 起動時、history の最新適用可能 record (decision in tighten/loosen,
全 metadata 一致, value isfinite + range 内) から effective threshold を
自動 override する。yaml 値を chore commit で reset しても、history 経由で
最新の calibrate decision が継承される (cross-run 一貫性)。

T058 段階で scope key は **`dataset_span` 一致 + `dataset_epoch_id` 一致 (AND 結合)**
に拡張された。 T058 段階では `dataset_epoch_id` は `generate_epoch_id_stub`
(= `"epoch_legacy"` 固定) なので実質的に従来挙動のまま (transitional 設計)。

T067 (将来) で T058 transitional 設計から定常設計に完全置換予定。 移行 3 点セット:

1. `schema_contract.enforcement_mode` を `log_only` → `fail_closed` に切替え
2. cross-run scope key から `dataset_span` を **完全撤廃**
3. cross-run scope key を `dataset_epoch_id` **単独化** (T059 deterministic
   epoch_id 生成と組合せ)

CLI override 優先順位 (高 → 低): `--stage-a-threshold X` > history > yaml。
詳細: `docs/alpha_factory/stage-gates.md` § "T054: state file 経由の自動適用" /
`devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md` § 施策 5-6。

## 関連

- 概念設計: `docs/alpha_factory/concepts/calibrate-gate.md`
- 詳細設計: `devnotes/20260424-1759-port-calibrate-gate/`
- 親文書: `docs/alpha_factory/stage-gates.md`
- improve-cycle 接続: Phase 2.5
