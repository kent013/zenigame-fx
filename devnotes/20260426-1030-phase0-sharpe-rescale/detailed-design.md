# Phase 0 / T042 — Sharpe 閾値を v2 trade-level スケールへ再標準化

**設計種別**: 概念設計 + 詳細設計（合議結果を正式化、Codex Round 2 で承認済）
**起点**: [audit-codex-round-2.md §3-1](../20260426-1010-ga-audit-r16/audit-codex-round-2.md)

## 問題（観測事実）

[stage_gate.py:574-577](../../src/alpha_factory/stage_gate.py#L574-L577) コメント:
```
# T-sharpe Phase 1A: trade_sharpe_raw (v2) を使用
# NOTE: live_criteria.sharpe_min=1.0 は v1 bar-level Sharpe スケール前提。
# Phase 1B replay で v2 trade-level スケールに再校正する。
```

GA fitness と Stage A/B/C 内部評価は v2 trade-level Sharpe (`bt.trade_sharpe_raw`) に移行済だが、`stage_a.threshold` (Run 16 actual=0.4655) / `stage_b.median_oos_sharpe_min=0.20` / `live_criteria.sharpe_min=1.0` の数値は **v1 bar-level annualized Sharpe スケール前提のまま放置**。コードが自ら「Phase 1B で再校正する」と宣言しているのに未実施。

→ Stage A pass=0（Run 16）は **threshold > 観測 fitness の単位ズレ**で発生。stage_gate-mid のスケール乖離が plateau の上流原因。

## 北極星制約との関係

AGENTS.md 禁止事項 #4「live_criteria 閾値をいたずらに緩和してステージを飛ばす」**外形的な緩和ではなく単位整合化**であることを docs に明示することが必須要件。

## 設計

### 換算式（Codex Round 2 §3-1）

trade-level → annualized 換算:
```
S_annual ≈ S_trade × √(λ_day × 252 / (h̄ × adj_corr))
```
- `S_trade`: trade-level Sharpe (`bt.trade_sharpe_raw`)
- `λ_day`: 1 営業日あたり平均 trade 数（archive から実測）
- `h̄`: 平均保有時間（trade 単位、日換算）
- `adj_corr = 1 + 2Σ_{k=1}^{q} ρ_k`: Lo (2002) 自己相関補正係数（lag 1〜q）

学術引用: Andrew W. Lo (2002), "The Statistics of Sharpe Ratios", Financial Analysts Journal 58(4), 36-52. — trade-level → annualized 変換と自己相関補正の標準的な定式化。

### 実装ステップ

#### Step 1: replay スクリプト作成
新規: `scripts/alpha_factory/replay_sharpe_rescale.py`
- 入力: Run N の archive Parquet（Run 14, 15, 16 を対象）
- 出力: `reports/sharpe-rescale/run-{N}-distribution.json`
  - 各個体の `trade_sharpe_raw` 分布（hist）
  - `λ_day`, `h̄`, `adj_corr` の population 統計
  - 換算後 `S_annual` 分布
- 既存 archive スキーマで読めるフィールドのみ使用（schema 拡張なし）

#### Step 2: 換算後閾値の設定
Run 14-16 の換算後分布を見て:
- `stage_a.threshold`: 換算前後で「同じ pass rate target=0.15」を満たす値に再設定
- `stage_b.median_oos_sharpe_min`: 換算後 mission_pass 個体の最低水準で再設定
- `live_criteria.sharpe_min`: 1.0（年率ベース）を **trade-level 換算後** で 1.0 を意味する数値に変換

ratchet logic（calibrate-gate）は本タスク中は **凍結**（cycle 4 と同様）、再校正完了後に新分布で 1 サイクル回し直す。

#### Step 3: docs 更新
新規 `docs/alpha_factory/sharpe-rescale.md`:
- 換算式・前提・引用
- 「緩和ではなく単位整合化」の論理（北極星制約遵守の説明）
- Run 14-16 の換算前後 distribution グラフ参照

[stage_gate.py:574-577](../../src/alpha_factory/stage_gate.py#L574-L577) のコメントを更新（「Phase 1B 完了」「換算式は sharpe-rescale.md 参照」）。

### 変更箇所

1. `scripts/alpha_factory/replay_sharpe_rescale.py`（新規）
2. `tests/scripts/test_replay_sharpe_rescale.py`（新規、合成 archive で換算ロジックを unit test）
3. `config/alpha_factory/default.yaml` の `stage_a.threshold` / `stage_b.median_oos_sharpe_min` / `live_criteria.sharpe_min` 更新（換算後値）
4. `docs/alpha_factory/sharpe-rescale.md`（新規）
5. `docs/alpha_factory/stage-gates.md` から sharpe-rescale.md へリンク
6. `src/alpha_factory/stage_gate.py:574-577` コメント更新

### DoD（Codex Round 2 §3-5 ②）

- [ ] `replay_sharpe_rescale.py` が Run 14, 15, 16 archive を読み hist + 統計を出力
- [ ] 換算後 `stage_a.threshold` が **`target_pass_rate=0.15` を満たす**水準で yaml 更新
- [ ] `live_criteria.sharpe_min` が trade-level 換算後値で更新（北極星制約満たす個体の sharpe を hard 評価）
- [ ] `docs/alpha_factory/sharpe-rescale.md` 作成（換算式・前提・引用 Lo 2002）
- [ ] unit test が単純 archive で換算ロジックを検証

## 反証（C9）

- 反証仮説 1: 「換算後でも Run 14-16 の best 個体は sharpe_min を満たさない（=機能不全は閾値スケール外の他要因）」
  - 検証: replay で換算後分布を出した時点で判明。満たさないなら次の論点（H1 underexploration / H3 aux pipeline）への bridge。
- 反証仮説 2: 「λ_day や h̄ が個体間で大きく分散し、population 平均で換算するのは不当」
  - 検証: 個体ごとに換算するか population 平均かは replay スクリプト内で **両方計算**。差異が大きい場合は per-individual 換算を採用。
- INCONCLUSIVE 受容: 学術上、trade-level → annualized 換算には複数流儀がある（Lo 2002 / Bailey-Lopez de Prado DSR / 簡易 √trades_per_year）。本タスクでは Lo 2002 を採用するが、複数式併記して docs に残す。

## 関連 TODO

- T037 (active-clause): 並行投入可（依存なし、Codex Round 2 §3-2）
- T041 (max_spread_bps): 先行 or 並行（独立）
- T043 (mission_score): 後続（4 軸 soft 集計時に再校正後 Sharpe を使う）

## 実装モード

`incremental` — replay スクリプト + yaml 値更新 + docs。1 worktree、複数 commit 許容（replay 実装 / 値再設定 / docs を分離可能）。
