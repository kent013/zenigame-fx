# PR4: legacy_pnl_smoke fitness opt-in + anti-luck guard (= 初の行動変更 PR)

## 背景

PR1-PR3 で観測基盤 (= source_stage / persistence_score_shadow / canonical/mission shadow 6 列) を整備完了。 Codex Y/Z Round 5 で確定した 12 段統合 TODO の **PR4 (= 初の「行動変更」 PR、 fitness 関数の opt-in 切替)** に進む。

## 現状認識 (= 動かない、 verify 済 / handoff § 確定事実)

### 現 Stage A fitness 関数 (`evaluate_stage_a`)

```python
fitness_raw = sharpe_raw  # trade_sharpe_raw (v2)
fitness_pen = (
    fitness_raw
    - stage_config.stage_a_alpha * size_norm_val
    - trade_count_penalty  # γ * (entry_count_min - trade_count) / entry_count_min if below min
)
```

GA selection は `fitness_pen` で行う (= 大きいほど優先)。

### archive 実測の問題 (handoff § archive 実測)

- fitness_pen ↔ slack_sharpe ρ=+0.85 (= sharpe 偏重)
- fitness_pen ↔ slack_pnl ρ=+0.59 (= PnL volume 副次)
- fitness_pen ↔ slack_trade ρ=-0.27 (= trade_count 逆相関、 = entry_threshold 過剰引き上げ傾向)
- Stage A only で total_pnl ≥ 30k = 10,646 個体 (2.9%、 持続性なし lucky run)
- mission_shortfall_proxy top 1% で all 4 pass = 165 個体、 ただし全部 max_dd=0.0% の lucky run

= 現 fitness は sharpe 主軸で、 mission target (= live_criteria total_pnl_min=50,000) との不整合あり (Codex X' = fitness が mission AND と非整合、 CONFIRMED)。

## 目的

Stage A fitness 関数に opt-in flag を導入し、 mission_shortfall 方向への探索圧 (= clipped_pnl_slack 加算) と anti-luck guard (= max_dd≈0 lucky run の連続抑制) を加える。 default は legacy (= 行動完全不変)。

### opt-in 形式の理由

1. **smoke validation 必須**: 行動変更は archive 全 RUN 横断分析の前提を壊す可能性があるため、 1 RUN smoke で baseline 比較 (handoff § テスト実行単位ガイド) を行わずに default 化しない。
2. **rollback 容易**: smoke で `Stage B pass 数 < baseline×50%` 等の rollback 条件に該当した場合、 flag off で即時復旧。
3. **A/B 比較容易**: PR5 (= Stage B gate pfr_only opt-in) との直交独立した実験設計。

## 推奨式 (Codex Y Round 3-5 確定)

### Stage A fitness (= 本 PR の中核)

```python
# legacy 部分 (= 現状不変)
sharpe_term = fitness_raw - stage_a_alpha * size_norm_val

# PR4 新規: PnL 方向の探索圧
pnl_slack = compute_clipped_pnl_slack(total_pnl_a)
pnl_term = beta * pnl_slack * persistence_weight  # beta=0.05、 pw=0.5 固定 (PR4 minimal scope)

# PR4 新規: anti-luck guard (二段)
lucky_penalty = compute_lucky_run_penalty(total_pnl_a, max_dd_a, trade_count_a)

# 合算
fitness_pen = sharpe_term + pnl_term - trade_count_penalty - lucky_penalty
```

### `compute_clipped_pnl_slack` (二層 PnL target、 Codex Y Round 3-5 確定)

```python
def compute_clipped_pnl_slack(total_pnl: float) -> float:
    short_target = 12000.0  # archive p95 近辺 = 探索勾配あり
    long_target = 50000.0   # mission (= live_criteria.total_pnl_min) = 方向付け
    short_slack = clip((total_pnl - short_target) / short_target, -1.0, 2.0)
    long_slack = clip((total_pnl - long_target) / long_target, -1.0, 1.0)
    return 0.7 * short_slack + 0.3 * long_slack
```

- short 主圧 (重み 0.7)、 long を方向付け (重み 0.3)
- short clip [-1.0, +2.0]: 達成超過余裕は最大 +2.0 (= incentive top out で Goodhart 抑制)
- long clip [-1.0, +1.0]: mission 達成は +1.0 で頭打ち

### `compute_lucky_run_penalty` (二段 anti-luck guard、 Codex Y Round 4 確定)

```python
def compute_lucky_run_penalty(
    total_pnl: float, max_dd_pct: float, trade_count: int,
) -> float:
    """anti-luck guard 二段:
    - hard_lucky_flag: total_pnl > 12000 AND max_dd_pct == 0.0 → 強く抑制
    - soft_lucky_penalty: total_pnl > 12000 AND max_dd_pct < 0.5% AND trade_count < 80
      → 連続的に抑制
    """
    HARD_THRESHOLD = 1.0    # 強い penalty
    SOFT_THRESHOLD = 0.3    # soft penalty
    if total_pnl <= 12000.0:
        return 0.0
    if max_dd_pct <= 1e-9:  # ≒ 0.0% (epsilon 判定)
        return HARD_THRESHOLD
    if max_dd_pct < 0.5 and trade_count < 80:
        return SOFT_THRESHOLD
    return 0.0
```

- HARD 値 1.0 / SOFT 値 0.3 は **初回 smoke の暫定値**、 baseline 比較で調整余地
- `total_pnl > 12000` で発火 = short_target 達成個体のみ対象 (= legitimate fitness ≥ short_target に対するペナルティ)

### `persistence_weight` (PR4 minimal scope = 固定 0.5)

- Codex Y Round 3 推奨: 「Stage A only でも 0 にしない。 初期値 0.5〜1.0。 Stage B pass 個体は 1.0」
- PR4 minimal scope では **Stage A fitness 計算時点で persistence_score_shadow が未計算** (= Stage B 評価後の値のため不可)
- 初回は固定 0.5 で実装。 Stage B pass 個体への 1.0 引き上げは別 PR (= 親子継承 / archive lookup 必要)
- PR5 / future PR で persistence_score_shadow を Stage A fitness にフィードバックする経路を追加検討

## 期待効果

### 直接的

- Stage A fitness に PnL 方向の探索圧が加わる → top decile の `total_pnl` 上昇期待
- max_dd≈0 lucky run が hard penalty で順位低下 → robust 候補が elite に残りやすい
- 1 RUN smoke で「mission 達成方向への探索」 が実証可能

### 間接的

- PR5 (Stage B gate pfr_only opt-in) との組合せで「fitness × gate」 両方向の最適化
- archive 横断分析で「fitness_pen ↔ canonical_gate_pass_b/c_shadow」 (PR3 由来) の相関を再評価可能
- mission 達成個体出現の最初の実験

### live_criteria 達成への寄与

- 直接的: **行動変更 PR の中核**、 smoke 成功なら mission 50k target 達成への第 1 歩
- 間接的: opt-in を default 化すれば GA 全体が mission-aligned に

## スコープ縮小判断

PR4 minimal scope は:
- Stage A fitness のみ修正 (= Stage B/C は不変)
- persistence_weight 固定 0.5 (= Stage B pass 反映は別 PR)
- lucky_penalty 暫定値 HARD=1.0 / SOFT=0.3 (= smoke 後に調整)
- opt-in default OFF (= 行動不変が default)
- 1 RUN smoke 必須 (= ユーザー実行待ち、 PR 自体は smoke 前に merge 可)

= PR4 が merged されても **default flag が OFF なので RUN 動作は完全不変**。 smoke はユーザーが任意のタイミングで `--fitness-mode legacy_pnl_smoke` で実行。

## 非目的

- Stage B / Stage C fitness 修正 (= 別 PR)
- persistence_score_shadow を Stage A fitness に反映 (= persistence_weight 動的化、 別 PR)
- mission_shortfall hard gate 化 (= 別 PR)
- Stage B gate `pfr_only` 切替 (= PR5、 別 PR)
- F6 grammar downweight (= PR6、 別 PR)

## 関連 TODO (12 段)

| 順 | TODO | 状態 |
|---|---|---|
| 1 | PR1: source_stage 値入力 | Completed (`e81dc85`) |
| 2 | PR2: persistence_score_shadow 追加 | Completed (`c18551e`) |
| 3 | PR3: canonical_metrics / mission_inf_gap shadow | Completed (`dcec109`) |
| 4 | **PR4: legacy_pnl_smoke + anti-luck guard** | **本 TODO** |
| 5 | PR5: Stage B gate pfr_only opt-in A/B | 未着手 (= PR4 smoke 後) |
| 6 | docs: progress_criteria 明文化 | 未着手 |
| 7+ | scripts / Stage C allocation / warmstart / Phase 2 統合 / primitive 拡張 | 未着手 |

詳細議論: `tmp/codex-debate-round2/` (Y debate Round 1-5)、 `devnotes/20260513-1511-handoff-pr3-postimpl/handoff.md`

## リスク

| リスク | 影響 | 緩和 |
|---|---|---|
| Stage A fitness 変更で archive 横断分析の前提が壊れる | 中 | opt-in default OFF + payload に `fitness_mode` 文字列を記録、 archive 分析時に分離可能 |
| lucky_penalty 暫定値が広すぎて robust 候補も抑制 | 中 | 1 RUN smoke で `max_dd<0.5% high_pnl` 比率を観測、 rollback or HARD/SOFT 値再調整 |
| pnl_slack 偏重で trade_count=50 張り付き再発 | 中 | smoke で top decile の trade_count 分布確認、 該当時は tc_penalty 強化 (γ 増) |
| beta=0.05 が小さすぎて pnl_slack の効果が見えない | 低 | smoke で「fitness_pen ↔ total_pnl」 ρ 上昇が baseline と差がなければ β 増 (= 0.10 まで) |
| persistence_weight=0.5 固定が将来式と非整合 | 低 | payload に persistence_weight 値を記録、 別 PR で 1.0 引き上げ時に migration 容易 |
| Codex Y Round 3 spec 内の trade_count_penalty 二重控除誤解釈 | 低 | 詳細設計で `sharpe_term = fitness_raw - α×size_norm` (tc 除く) と明示、 tc は最終合算で 1 回のみ控除 |

## 検証戦略

### 実装時 (= 本 PR スコープ)

- pytest 全件 pass
- legacy mode で fitness_pen 完全一致 (= regression 0)
- legacy_pnl_smoke mode で期待値テスト 5 件以上 (= 各項の境界網羅)
- ruff / mypy clean

### smoke 時 (= ユーザー実行待ち、 PR4 merge 後)

baseline (= **直近 5 RUN の archive 累積値の median** = 詳細設計 § smoke 条件 § Baseline 定義 を SSOT) と PR4 (= legacy_pnl_smoke mode の 1 RUN) を同 instrument / 同 seed range で比較:

合格条件 (Codex Y Round 3-5 確定):
- Stage B pass 数 ≥ baseline median × 80%
- Stage C `pips/day p99` ≥ 5.0
- Stage C `total_pnl p95/p99` ≥ baseline
- trade_count median が 50-70 に潰れず、 p75/p90 維持または上昇
- max_dd=0.0% 比率 ≤ baseline、 または `max_dd<0.3% && high_pnl` 比率 ≤ baseline

rollback 条件:
- Stage B pass 数 < baseline median × 50%
- top decile が trade_count=50 近傍へ集中
- lucky high-PnL 比率が baseline 1.5 倍超
- pips/day 上昇が trades/day 増加だけで説明される
- canonical_gate_pass_b/c_shadow=False 比率上昇 (= PR3 で追加した観測列を活用)

## 参考資料

- `tmp/codex-debate-round2/.codex-output-debate-Y-round-3.md` (= Step 0 = legacy_pnl_smoke 0-C + 連続 lucky penalty 確定)
- `tmp/codex-debate-round2/.codex-output-debate-Y-round-4.md` (= lucky_run_penalty 二段確定、 HARD/SOFT 閾値)
- `tmp/codex-debate-round2/.codex-output-debate-Y-round-5.md` (= 6 PR 順序、 smoke 合格条件)
- `devnotes/20260513-1511-handoff-pr3-postimpl/handoff.md` (= PR3 完了後 handoff)
- `src/alpha_factory/stage_gate.py:782-922` (= 現 evaluate_stage_a)
- `src/alpha_factory/config.py:271-299` (= Phase2Config 既存 pattern)
