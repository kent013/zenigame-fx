# Sharpe スケール変換 (trade-level → annualized)

**TODO**: T042 (Phase 0)
**実装**: `src/alpha_factory/stage_gate.py::_annualize_trade_sharpe`
**関連**: `scripts/alpha_factory/replay_sharpe_rescale.py`、`docs/alpha_factory/mission-score.md`、`docs/alpha_factory/stage-gates.md`
**起点監査**: [audit-codex-round-2.md §3-1](../../devnotes/20260426-1010-ga-audit-r16/audit-codex-round-2.md)

## 問題

GA fitness と Stage A/B 内部評価は **trade-level Sharpe (v2)** = `trade_sharpe_raw = μ_trade / σ_trade` に統一されている一方、`live_criteria.sharpe_min=1.0` は **bar-level annualized Sharpe** スケール前提のまま放置されていた（[stage_gate.py:574-577](../../src/alpha_factory/stage_gate.py#L574-L577) のコード自身が「Phase 1B replay で再校正する」と宣言）。Run 1〜16 で Stage A pass=0 / Stage C pass=0 が常時発生していた構造的原因の一つ。

Run 14-16 archive replay 観測（`reports/sharpe-rescale/`）:
| Run | trade_sharpe_raw median | q85 | max | annualized max |
|----:|------------------------:|----:|----:|---------------:|
| 14 | 0.047 | 0.140 | 0.140 | 2.23 |
| 15 | -0.020 | 0.041 | 0.184 | 3.01 |
| 16 | 0.186 | 0.341 | 0.341 | 4.86 |

すべての Run で **annualized では best 個体が live_criteria.sharpe_min=1.0 を超える** が、trade-level スケールのまま比較すると常時 fail していた。

## 換算式（Phase 0 minimum）

```
S_annual ≈ S_trade × sqrt(λ_day × 252)
```

- `S_trade`: trade-level Sharpe ratio (`bt.trade_sharpe_raw`)
- `λ_day = trade_count / window_days`: 1 営業日あたり平均 trade 数
- `252`: 1 営業年営業日数

実装: [`stage_gate.py::_annualize_trade_sharpe`](../../src/alpha_factory/stage_gate.py)

## scope 外（Phase 1+ で導入予定）

完全な Lo (2002) 公式は **自己相関補正係数** を含む:
```
S_annual = S_trade × sqrt(λ_day × 252) / sqrt(adj_corr)
adj_corr = 1 + 2 × Σ_{k=1}^{q} (1 - k/q) × ρ_k
```
`ρ_k` は trade returns の lag-k 自己相関。

Phase 0 では archive スキーマに trade-level 時系列を持たないため `adj_corr=1` 固定で運用。Phase 1 で trade-level returns を archive に格納する設計を行った時点で導入する。

学術引用:
- Andrew W. Lo (2002), "The Statistics of Sharpe Ratios", *Financial Analysts Journal* 58(4), 36-52.

## 実装の境界条件

`_annualize_trade_sharpe` は以下のとき `None` を返す（caller 側で「換算不能 = lc.sharpe 判定不能 = 失格」扱い）:
- `trade_sharpe_raw` が None / NaN / inf
- `trade_count <= 0`
- `window_days <= 0`

これは「base 評価で trade を出せず Sharpe 計算不能だった個体」を defensive に lc.sharpe pass から除外する。

## 適用箇所

| 比較対象 | 評価スケール | window |
|---------|------------|--------|
| `live_criteria.sharpe_min` (= 1.0) | **annualized** | `stage_c.stage_c_holdout_days` (60 日) |
| `stage_a.threshold` | trade-level (fitness_pen) | calibrate-gate で動的調整 |
| `stage_b.median_oos_sharpe_min` | trade-level (per-fold) | `wf_test_days` |

**`live_criteria.sharpe_min` のみ annualized で比較**。Stage A/B threshold は内部の calibrate gate or 経験的設定で動的に決まるため trade-level のまま。

## 北極星制約との整合（AGENTS.md 禁止事項 #4）

「閾値の不当な緩和」に **抵触しない**:

- `live_criteria.sharpe_min=1.0` の **数値は不変**、annualized Sharpe を比較対象に変えただけ
- 「年率 1.0 以上の戦略を見つける」という mission の意味的内容は変わらない
- 換算式は学術文献 (Lo 2002) を引用、第三者検証可能
- 換算根拠は本 docs に固定、calibrate-gate の自動調整外（手動調整禁止）

## yaml の現状（Phase 0 完了時）

```yaml
live_criteria:
  sharpe_min: 1.0          # annualized (T042 換算後比較)
  total_pnl_min: 50000
  max_drawdown_max: 0.2
  trade_count_min: 50
  trade_count_max: 5000

stage_gate:
  stage_a:
    threshold: 0.0          # trade-level (calibrate-gate 管理)
  stage_b:
    median_oos_sharpe_min: 0.025  # trade-level (T091 で 0.05 → 0.025 に noise-floor 整合化)
```

### T091 noise-floor 整合化の根拠 (Lo 2002 SE 公式 heuristic)

- per-fold Sharpe SE ≈ √((1 + 0.5×SR²)/N)、 N=stage_b_fold_trade_count_min=10 で SE ≈ 0.32
- 10-fold median SE ≈ 0.32/√10 ≈ 0.10 (独立 fold 仮定)
- 真値 SR=0.05 個体の median 推定値 >=0.025 確率: z=(0.025-0.05)/0.10=-0.25 → P=Φ(0.25)≈0.60
- 0.05 維持時の検出力: 50% (median == true value 期待)
- → 0.025 で「真値 0.05 個体の検出力 50% → 60% への保守的拡張」 (Lo 近似 heuristic)
- 緩和ではなく noise-floor 整合化 (Stage B 内部閾値、 live_criteria.sharpe_min は不変)

詳細: `devnotes/20260508-1203-stage-b-gate-redesign/conceptual-design.md` (v2 APPROVED at Codex Round 3)

## replay スクリプト

```bash
# Run 16 archive を換算
uv run python scripts/alpha_factory/replay_sharpe_rescale.py \
    --parquet .cache/alpha_factory/runs/genomes_run_20260425_235717.parquet \
    --window-days 60 \
    --target-pass-rate 0.15 \
    --output reports/sharpe-rescale/run-16-distribution.json
```

出力 JSON は trade-level / annualized の population 分布、推奨閾値（target_pass_rate=0.15 達成時の 85%ile）を含む。

## 変更履歴

- 2026-04-26: T042 Phase 0 初期実装。Codex Round 2 §3-1 で換算式合意（Lo 2002）。stage_b.median_oos_sharpe_min を v1 bar-level 想定 0.20 → trade-level 経験値 0.05 に再校正。Stage C lc.sharpe を annualized 比較に切替。
- 2026-05-08: T091 cycle_phase1 (Stage B gate redesign Phase 1)。 stage_b.median_oos_sharpe_min を 0.05 → 0.025 に noise-floor 整合化 (Lo 2002 SE 公式 heuristic、 真値 SR=0.05 検出力 50%→60%)。 緩和ではなく検出力整合化 (Stage B 内部閾値、 live_criteria.sharpe_min は不変)。 詳細: devnotes/20260508-1203-stage-b-gate-redesign/。
