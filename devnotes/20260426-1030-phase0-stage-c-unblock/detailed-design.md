# Phase 0 / T041 — Stage C `max_spread_bps` 設定で stress 関門を機能させる

**設計種別**: 概念設計 + 詳細設計（合議結果を正式化、Codex Round 2 で承認済）
**起点**: [audit-claude.md](../20260426-1010-ga-audit-r16/audit-claude.md) / [audit-codex.md](../20260426-1010-ga-audit-r16/audit-codex.md) / [audit-codex-round-2.md](../20260426-1010-ga-audit-r16/audit-codex-round-2.md)

## 問題（観測事実）

[stage_gate.py:630-632](../../src/alpha_factory/stage_gate.py#L630-L632):
```python
if backtest_config.max_spread_bps is None:
    stress_payload["skipped"] = True
    reasons.append("spread_stress_skipped")
```

[config.py:76](../../src/alpha_factory/config.py#L76): `max_spread_bps: Decimal | None = None`、`config/alpha_factory/default.yaml` に override なし。

→ **Run 1〜16 全 Run で Stage C は `spread_stress_skipped` 付きで fail**。Stage C pass=0 はバグでなく仕様（gate 閉塞）。

## 北極星制約との関係

AGENTS.md「絶対制約: スワップ・スプレッドを fitness に反映（見かけの PnL ではなく純利益）」に対し、現状は spread/swap が一切反映されていない。**Stage C を開けることは緩和ではなく規約遵守**。

## 設計

### 値の決定（Codex Round 2 §3-3 準拠）

EUR_JPY / USD_JPY tier1 broker (OANDA 等) の典型 spread 1.0〜2.0 pips ≈ 6〜12 bps。

- **`backtest.max_spread_bps = 10`**（約 1.4 pips、保守的中央値）
- Stage C `spread_stress_multiplier = 1.5`（既存）→ stress base 15 bps（≈ 2.1 pips）で評価
- `holding_cost_per_day_bps = 0` 維持（**イントラデイ前提**で overnight 持ち越さない設計、AGENTS.md 制約遵守）

通貨ペア別 override は Phase 1 で `per_pair_overrides` を検討、Phase 0 では共通 10 bps。

### 変更箇所

1. `config/alpha_factory/default.yaml` の `backtest:` セクションに以下追加:
   ```yaml
   backtest:
     # ...既存...
     # Codex audit (Round 2) 指摘: Stage C は max_spread_bps 未設定で
     # spread_stress_skipped により常時 fail だった。
     # EUR_JPY tier1 (OANDA) の典型 spread 1.0-2.0 pips ≈ 6-12 bps の保守的中央値。
     # AGENTS.md「スワップ・スプレッドを fitness に反映」遵守のための最小実装。
     max_spread_bps: "10"
     holding_cost_per_day_bps: "0"
   ```
   - `Decimal | None` 型なので yaml は文字列で渡す（既存 initial_cash と同じ規約）

2. **テスト追加**: `tests/alpha_factory/test_stage_gate.py`（新規 or 既存追記）
   - `test_stage_c_pass_when_max_spread_bps_set`: 「make-feasible」既存テスト genome を min spread で通すケース
   - `test_stage_c_skip_reason_when_max_spread_bps_none`: 既存規約の保護（現挙動の retest）

### DoD（Codex Round 2 §3-5 ①）

- [ ] yaml に `max_spread_bps`/`holding_cost_per_day_bps` 設定済（type-check 通過）
- [ ] `test_stage_c_pass_when_max_spread_bps_set` がテスト追加で通る
- [ ] 既存 stage_gate test 全 pass
- [ ] Run 14-16 archive を replay して `spread_stress_skipped` reason が出ない個体が 1 件以上出ることを確認（quick replay）
- [ ] docs/alpha_factory/stage-gates.md に「Phase 0 で max_spread_bps を有効化した経緯」追記

## 反証（C9）

- 反証仮説: 「`max_spread_bps=10` でも全個体が他の Stage C 条件で fail する」
- 検証: Run 14-16 archive replay で `live_criteria.*` reason 分布を見る。spread 以外の条件で fail するなら別 TODO（Sharpe 再校正 = T042）への接続を確認。
- INCONCLUSIVE 受容: 個体が出ないこと自体は「Stage C unblock の責務外」。次タスク（T042 Sharpe 再校正）への正常な引き継ぎ。

## scope 外（次タスク）

- Sharpe 閾値の trade-level 再校正 → T042
- T037 active-clause / T043 mission_score → 並行タスク

## 実装モード

`incremental` — config 変更 + テスト追加のみで小規模。1 worktree 1 commit。
