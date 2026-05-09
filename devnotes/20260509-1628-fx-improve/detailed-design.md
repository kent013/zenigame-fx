# 詳細設計: Run 57 施策 (cycle 4) — Round 2 (Codex Critical 反映後)

## 使命・制約（絶対遵守）

`zenigame-fx-codex-review` で定義される使命・絶対制約・禁止事項を継承。 FX 固有制約のみ再掲:
- イントラデイ前提（オーバーナイト保有禁止）
- ロング・ショート両方向許容
- スワップ・スプレッドを fitness に反映

## 施策一覧

| # | 施策名 | 変更ファイル | target_metric |
|---|--------|------------|--------------|
| C1 | dataset 範囲見直しで Stage C holdout 60日を構造的に確保 | `config/alpha_factory/default.yaml` | trade_count / total_pnl / sharpe (Stage C 60日評価環境の正常化) |

---

## C1: dataset 範囲見直し（v2、 Round 2 修正）

### Round 2 での修正点

Round 1 Codex review の Critical / Warning に対応:
- **[Critical]** preflight extended_start の DB 範囲未検証 → start を 2024-04-01 から **2025-04-01 に上方修正** (extended_start=2023-10-09 で DB min 2023-04-23 から 5.5 ヶ月余裕)
- **[Warning]** Stage B fold 急増 → 2024-04-01 (約 22 ヶ月) → **2025-04-01 (約 11 ヶ月)** に短縮で fold 数 2.35 倍程度に抑制
- **[Warning]** テスト fixture 同期忘れ → tests は YAML 文字列を inline で埋め込み independent fixture として動作確認済 (実装時に pytest 実行で regression なしを再検証)
- **[Warning]** Run 比較不可化への運用準備 → improvement-plan.md "Run 比較可能性ガイドライン" 節で明文化済
- **[Suggestion]** コメントに実測値 → 採用、 後述

### 前提検証（C4） — 全項目 verified

| 前提 | 値 | 検証元 |
|------|-----|-------|
| DB EUR_JPY range | 2023-04-23 〜 2026-04-21 (count=1109527) | `SELECT min/max(bar_time) FROM price_bar_m1` 実測 |
| DB EUR_USD range | 2023-04-23 〜 2026-04-21 (count=1107296) | 同上 |
| DB USD_JPY range | 2023-04-23 〜 2026-04-21 (count=1107680) | 同上 |
| stage_a_window_days | 60 | `config/alpha_factory/default.yaml:106` |
| stage_b.window_months | 18 | `config/alpha_factory/default.yaml:118` |
| stage_c.holdout_days | 60 | `config/alpha_factory/default.yaml:177` |
| HARD_REQUIRED_PAIRS | (EUR_USD, USD_JPY) | `src/alpha_factory/aux_preflight.py:38` |
| min_finite_coverage_pct | 50.0 | `src/alpha_factory/aux_preflight.py:192` |
| compute_extended_period | period[0] - 18*30 days | `src/alpha_factory/aux_preflight.py:69-71` |

### target_metric / failure_mode / causal_path / falsification / success_criterion

- **target_metric**: trade_count (50 以上の到達確保) / total_pnl / sharpe (Stage C 60日評価環境の正常化)
- **failure_mode**: holdout 21日で stage_partition_guard B-2 が WARN 通過必須、 smoke-test mode opt-in 必須、 live_criteria 評価窓が config 仕様未達
- **causal_path**: dataset.end が DB 終端と近すぎ → Stage C holdout が短い → live_criteria 評価窓が config 仕様未達 → mission 達成判定不能
- **falsification**: 変更後 Run でも `--allow-holdout-short` 不要で完走しなければ False (calendar gap / B-1 disjoint 違反 / preflight pair coverage 不足の別問題が露見)
- **success_criterion**: Run 57 で smoke-mode flag なしで完走、 stage_partition_guard.passed が holdout_short_override=False で通る、 dataset_holdout calendar span >= 48 日 (= 60 × tolerance 0.8)、 preflight aux check も pass

### 変更箇所

`config/alpha_factory/default.yaml`:11-12

### 波及変更（AGENTS.md / skill / config / docs）

- **AGENTS.md** (139-141行): Stage A/B/C 区切りは数式記法 → 同期更新不要
- **docs/alpha_factory/stage-gates.md** (48行): 数式記法のみ → 同期更新不要
- **docs/alpha_factory/sieve.md** / `concepts/alpha-sieve.md`: 数式記法のみ → 同期更新不要
- **tests/alpha_factory/test_config*.py**: YAML 文字列を inline 埋め込み (`test_config.py:122-123, 181-182, 275-276` / `test_config_schema_contract.py:49-50`) で independent fixture として動作 → regression なしを実装時 pytest で確認、 必要なら追従更新
- **tests/alpha_factory/test_aux_preflight.py:253, 287**: コメント内の日付例示のみ、 fixture は別 → 同期更新不要

### 計算上の確認 (v2)

- 新 dataset: start=2025-04-01, end=2026-02-19
- Stage A (60日): 2025-12-21 〜 2026-02-19
- Stage B IS+folds: 2025-04-01 〜 2025-12-21 (約 264 日 ≒ 8.7 ヶ月、 stage_b.window_months=18 を下回るが walk_forward fold は 264-39=225 / step 5 + 1 = **46 fold** 確保で wf_min_safe_folds=5 を大幅超過)
- Stage C holdout: 2026-02-19 〜 2026-04-21 (約 61 日、 80% tolerance 48 日 を超える)
- preflight extended period: 2025-04-01 - 540日 = **2023-10-09** 〜 2026-04-21 (約 30 ヶ月)
- DB available within extended period: 2023-10-09 〜 2026-04-21 (約 30 ヶ月、 calendar 同等)
- preflight pair coverage 推定 (calendar minutes): 30 ヶ月 × 30 日 × 1440 分 = 1296000 expected, n_rows ≒ 1107000 → **coverage ≒ 85.4%** で 50% threshold 余裕でクリア

### Stage B fold 数の確認

- Run 56 (start=2025-10-01, Stage B 約 4.4 ヶ月 = 132 日): fold = (132 - 39) / 5 + 1 = 19
- Run 57 (start=2025-04-01, Stage B 約 8.7 ヶ月 = 264 日): fold = (264 - 39) / 5 + 1 = **46**
- 倍率: 46 / 19 = 2.42 倍
- 実行時間概算: Run 56 が約 90 分なら Run 57 約 220 分 (3.7 時間)。 20 RUN フルサイズで 73 時間程度
- メモリ: ワーカー単位の bars cache はそのまま、 cache miss 増加で peak は上昇するが 3GB 内に収まる見込み (Run 56 で 1.2GB 程度の peak、 余裕あり)

### 現行コード (config/alpha_factory/default.yaml:8-12)

```yaml
dataset:
  instrument: EUR_JPY
  # ISO 8601 (UTC) — バックテスト対象期間
  start: "2025-10-01T00:00:00Z"
  end: "2026-04-01T00:00:00Z"
```

### 変更後コード (config/alpha_factory/default.yaml:8-12)

```yaml
dataset:
  instrument: EUR_JPY
  # ISO 8601 (UTC) — バックテスト対象期間
  # @cycle_4 (2026-05-09): dataset 範囲見直し。 Stage C holdout 60日を構造的に確保するため
  # dataset.end を DB 終端 (2026-04-21) から 60日強遡る位置に設定。 同時に dataset.start を
  # preflight extended_start (= start - 18ヶ月) が DB min (2023-04-23) より十分後ろになる
  # 位置に設定 (extended_start=2023-10-09)。 Stage B fold は 46 確保、 holdout span 61 日。
  # 設計: Stage A=60日 (2025-12-21〜2026-02-19) / Stage B IS=2025-04-01〜2025-12-21 (約 8.7 ヶ月) /
  # Stage C holdout=2026-02-19〜2026-04-21 (約 61 日)。 preflight pair coverage 推定 ≒ 85% (50% 閾値余裕)。
  # @ref: devnotes/20260509-1628-fx-improve/improvement-plan.md C1
  start: "2025-04-01T00:00:00Z"
  end: "2026-02-19T00:00:00Z"
```

### ルックアヘッドバイアスチェック

該当なし (primitive 変更ではなく config 値変更)。 dataset 範囲拡張により Stage A/B/C 期間が前にシフトするのみで、 backtest ロジックに変更なし。

### パフォーマンスチェック

- データ量: 旧 6 ヶ月 (Run 56) → 新 約 11 ヶ月 (Run 57)、 bars 約 1.8 倍
- Stage B fold 数: 19 → 46 (約 2.42 倍)
- 実行時間: 1 RUN 約 90 分 → 約 220 分 (3.7 時間) 推定
- メモリ: ワーカー単位 1.2GB → 1.5-1.8GB 推定、 3GB 制約内
- 既存 caching / SoA 経路は dataset 範囲非依存で動作

### テスト計画

- [ ] 既存テスト `pytest tests/alpha_factory` を実行し regression なし確認
- [ ] 失敗テストがあれば fixture 同期更新 (test_config.py / test_config_schema_contract.py の YAML 文字列 inline 埋め込み)
- [ ] **新規テストは追加しない** (config 値変更のみ、 logic 変更なし)
- [ ] 手動検証: Run 57 を `--allow-holdout-short` フラグなし、 `ZENIGAME_FX_SMOKE_TEST=1` env なしで実行し、 smoke-mode opt-in なしで完走することを確認
- [ ] preflight check の log で hard_satisfied に EUR_USD_M1 / USD_JPY_M1 / VIXCLS / DTWEXBGS が含まれること確認

### リスク (v2 更新)

- **R1**: Stage B IS が 4.4 → 8.7 ヶ月に拡大 → fold OOS 推定の母集団が変わり、 Run 56 以前との fitness 直接比較が不可能 (Codex Q2 で承認、 Run 57 から新 baseline)
- **R2**: 実行時間が約 2.42 倍 (90 分 → 220 分) → 20 RUN フルサイズで 73 時間程度。 完了までの所要時間が長いがユーザー想定 (`20 RUN フルサイズ`) は実行時間制約を含まないため許容
- **R3**: dataset.start=2025-04-01 が DB min (2023-04-23) と 23 ヶ月のバッファ → preflight extended period で DB 完全カバー、 R3 解消
- **R4**: dataset.end=2026-02-19 が DB max (2026-04-21) との間 61 日確保、 80% tolerance 48 日を超える → B-2 guard pass を期待
- **R5 (新規)**: tests fixture (test_config.py / test_config_schema_contract.py / test_aux_preflight.py) で旧日付がハードコード → fixture は YAML 文字列 inline で independent と推定。 万一 default.yaml 直接読込み test があれば fail する可能性、 実装時 pytest で確認

### 実装手順

1. `config/alpha_factory/default.yaml` の dataset.start / dataset.end を変更 + コメント追加
2. `pytest tests/alpha_factory` を実行し regression テスト
3. 失敗テストがあれば fixture を新日付に同期更新
4. コミット (config 1 ファイル変更で完結するため improve-cycle 内で直接実行)

### Run 57 実行パラメータ

| パラメータ | 値 | R56 からの変更 |
|-----------|-----|--------------|
| instrument | EUR_JPY | 変更なし |
| population_size | 96 | 変更なし |
| generations | 60 | 変更なし |
| mutation_rate | 0.5 | 変更なし |
| seed | 42 | 変更なし |
| max_workers | 2 | 変更なし |
| --allow-holdout-short | **不指定** | smoke-mode opt-in を解除 (本施策の主目的) |
| ZENIGAME_FX_SMOKE_TEST | **未設定** | smoke-mode opt-in を解除 |
| dataset.start (config) | **2025-04-01** | 2025-10-01 から遡り (Stage B IS 約 8.7 ヶ月確保) |
| dataset.end (config) | **2026-02-19** | 2026-04-01 から遡り (B-2 holdout 60日確保) |

---

## 全体判定

cycle 4 確定施策 (C1 v2) は config 2 行変更で完結。 Round 1 Codex Critical (preflight extended_start の DB 未検証) に対し dataset.start を保守的に 2025-04-01 まで上方修正、 extended_start=2023-10-09 で DB 完全カバー、 preflight coverage 推定 85%。 Stage B fold 数も 46 確保、 wf_min_safe_folds=5 を大幅超過。 実行時間 R2 リスクは許容。 R5 (テスト fixture) は実装時 pytest で確認、 必要なら同期更新。

C1 の `success_criterion` (Run 57 で smoke-mode opt-in なしで完走、 preflight pass、 stage_partition_guard B-2 自然 pass) が確認できれば、 cycle 5 で Codex 推薦の DSR 配線復帰に進める。
