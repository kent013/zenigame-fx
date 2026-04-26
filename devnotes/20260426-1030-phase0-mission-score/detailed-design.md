# Phase 0 / T043 — `mission_score` 4 軸 soft 合算で連続的進捗指標を導入

**設計種別**: 概念設計 + 詳細設計（合議結果を正式化、Codex Round 2 で承認済）
**起点**: [audit-codex-round-2.md §3-4](../20260426-1010-ga-audit-r16/audit-codex-round-2.md)

## 問題（観測事実）

`live_criteria` は 4 軸の hard pass/fail 判定のみ:
```yaml
sharpe_min: 1.0
total_pnl_min: 50000
max_drawdown_max: 0.2
trade_count_min: 50  / trade_count_max: 5000
```

GA fitness は `sharpe` 単軸で、他 3 軸（pnl, dd, trade_count）は **fitness に直接寄与しない**。
- Run 14: total_pnl=0
- Run 15: total_pnl=8,660 / sharpe=0.069
- Run 16: total_pnl=0
- 各 Run の「使命達成までの距離」が 0/1 でしか分からず、Run 間比較が困難（86 Run 連続未達でも勾配が見えない）

zenigame は `amscore`（adaptive mission score）で 4 軸を soft 化し、Run 1260 で `amscore=0.7731` のような連続値で進捗を観測している。

## 設計

### スコア定義（Codex Round 2 §3-4）

各軸 `i` ∈ {sharpe, total_pnl, max_drawdown, trade_count} に対し:

```
score_i = clip((metric_i - lower_i) / (target_i - lower_i), 0, 1)
score_i' = 0.1 + 0.9 × score_i      # 0 を避けて log 表示可能化
mission_score = (Π score_i')^(1/4)   # 幾何平均 (0.1 〜 1.0)
```

軸別パラメータ:

| 軸 | lower | target | 備考 |
|----|------|--------|------|
| sharpe | 0.0 | live_criteria.sharpe_min (T042 換算後値) | 負 sharpe は 0 score |
| total_pnl | 0.0 | live_criteria.total_pnl_min (50,000) | 負 PnL は 0 score |
| max_drawdown | live_criteria.max_drawdown_max (0.2) | 0.0 | **逆向き**: dd 小さいほど score 高 |
| trade_count | 0 | live_criteria.trade_count_min (50) | trade_count > max は 0 score（範囲制約） |

### 性質

- 全軸 target 達成で `mission_score = 1.0`
- 全軸 lower 以下で `mission_score = 0.1^1 = 0.1`（log 化に対応）
- 1 軸でも 0 score だと幾何平均が小さくなる（min に近い、合成の困難さを反映）
- **Run 16 の現状値**:
  - sharpe=0.341 / target≈X(換算後) → score≈0.5
  - total_pnl=0 / target=50000 → score=0
  - dd=0 / 0.2 → score=1.0
  - trade_count=30 / 50 → score=0.6
  - 0.1〜1.0 にスケール後幾何平均 ≈ 0.1〜0.4 → 「distance to mission」が連続値で見える

### スコープ（Phase 0）

- archive Parquet スキーマに `mission_score: float` カラム追加（GENOMES_SCHEMA）
- `_create_row_template`、`collect_stage_*` で値伝搬（4 段接続：Codex 既知パターン）
- `generate_run_report.py` で「best mission_score 個体」と分布を report 表示
- **GA fitness には反映しない**（当面は観測のみ、selection 圧変更は別 cycle）

### 変更箇所

1. `src/alpha_factory/archive.py`
   - `GENOMES_SCHEMA` に `pa.field("mission_score", pa.float64(), nullable=True)`
   - `_create_row_template` で `"mission_score": None`
   - 計算関数 `_compute_mission_score(stage_c_payload, lc) -> float | None` を追加（Stage C base metrics から計算）
   - `collect_stage_c` で書き込み

2. `scripts/alpha_factory/generate_run_report.py`
   - 「mission_score」セクション追加: best/median/distribution
   - top-5 個体表に `mission_score` カラム追加

3. `scripts/alpha_factory/run_ga.py`
   - report 用 best 個体選定: `mission_score` 降順 also-show（fitness は変えず併記）

4. `tests/alpha_factory/test_archive.py`
   - `_compute_mission_score` の 4 軸 unit test（hard 達成 / 全軸 lower / 範囲外 trade_count 等）

5. `docs/alpha_factory/mission-score.md`（新規）— 数式・性質・GA fitness と分離している理由

### DoD（Codex Round 2 §3-5 ④）

- [ ] archive に `mission_score` カラム追加（schema → template → write の 4 段確認）
- [ ] Run 14, 15, 16 archive を replay して `mission_score` 分布を出力
- [ ] report で best mission_score / median / hist 表示
- [ ] unit test 通過
- [ ] docs 作成

## 反証（C9）

- 反証仮説 1: 「幾何平均は 1 軸 0 で score 全体が小さくなりすぎ、識別力が出ない」
  - 検証: `0.1 + 0.9 × score_i` で底上げしているため最小 0.1。Run 14-16 で識別力を測定し、分散が小さければ調和平均や算術平均に切替検討。
- 反証仮説 2: 「max_drawdown=0 が常時 score 1.0 になり drawdown 改善圧が効かない」
  - 検証: Run 16 の dd=0 は trade_count=30 で実質 dd 計算対象が薄い結果。trade_count score と複合で評価可能。本 TODO の責務外（dd モデル拡張は別タスク）。
- INCONCLUSIVE 受容: 「mission_score を GA fitness に組み込むべきか」は本タスク外。当面 observation only、Phase 1 以降に re-evaluate。

## 関連

- T042 (Sharpe 再校正): 完了後 `live_criteria.sharpe_min` の換算後値が確定するので mission_score の sharpe 軸 target はそれに合わせる。**T042 と並行実装可、target 値だけ T042 完了時に置換**。
- T037 (active-clause): 並行可、独立指標。

## 実装モード

`incremental` — archive スキーマ変更を含むため値伝搬 4 段の confirmation 必須（Codex 規約）。1 worktree、複数 commit 推奨。
