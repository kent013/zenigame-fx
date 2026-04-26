# Phase 0 / T042 — Sharpe 閾値再標準化（概念設計）

**起点監査**: [audit-codex-round-2.md §3-1](../20260426-1010-ga-audit-r16/audit-codex-round-2.md)

## 仮説

**Stage A pass=0 / live_criteria 全未達は、threshold が GA fitness と単位が違うことが上流原因**。コードが自ら未完了を宣言しているのに放置。

## 検証済み事実

[stage_gate.py:574-577](../../src/alpha_factory/stage_gate.py#L574-L577) コメント:
> NOTE: live_criteria.sharpe_min=1.0 は v1 bar-level Sharpe スケール前提。
> Phase 1B replay で v2 trade-level スケールに再校正する。

GA fitness と Stage 評価は v2 trade-level Sharpe (`bt.trade_sharpe_raw`) に移行済だが、`stage_a.threshold` (Run 16 actual=0.4655) / `stage_b.median_oos_sharpe_min=0.20` / `live_criteria.sharpe_min=1.0` は v1 スケールのまま。

## 北極星制約との接続

AGENTS.md 禁止事項 #4「live_criteria 閾値をいたずらに緩和してステージを飛ばす」に **抵触しないことを明示**: 本タスクは外形的な緩和ではなく **単位整合化**。換算式と前提を docs に固定し、北極星基準（年率 Sharpe 1.0 以上の戦略を見つける）が変わらないことを保証する。

## 解決方針

学術文献 Lo (2002) "The Statistics of Sharpe Ratios" の標準的な trade-level → annualized 換算:
```
S_annual ≈ S_trade × √(λ_day × 252 / (h̄ × adj_corr))
```
`λ_day`=日次平均 trade 数、`h̄`=平均保有時間、`adj_corr`=自己相関補正係数。

Run 14-16 archive を replay して population 統計から換算式を実装、`stage_a.threshold` / `stage_b.median_oos_sharpe_min` / `live_criteria.sharpe_min` を換算後値で再設定。

## 成功判定

- replay スクリプトが Run 14-16 の換算前後分布を出す
- 換算後 `stage_a.threshold` が `target_pass_rate=0.15` を満たす水準
- 換算式・前提・引用が `docs/alpha_factory/sharpe-rescale.md` に固定される
- 北極星基準（年率 Sharpe 1.0）が trade-level 換算後値で同等に判定される

## scope 外

- calibrate-gate ratchet（再校正完了まで凍結、別 cycle で再起動）
- 多通貨化での換算（Phase 1 以降）

## 詳細設計

[detailed-design.md](detailed-design.md) 参照。
