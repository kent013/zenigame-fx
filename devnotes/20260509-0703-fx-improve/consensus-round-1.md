**前提検証（C4）**
- Verified Fact: 現状は `Stage B pass=0`, `n_fold_effective=0` 上位化, `seed依存のprimitive collapse`, `T091単独未検証`。
- Verified Fact: 失敗の主因は「評価可能性不足の個体が選抜上位に残る構造」。
- Interpretation: 先に Stage B ゲート構造を正し、因果を切り分けるのが最短経路（Reactive調整回避）。

**改善計画（本cycle確定）**

| # | 判定 | target_metric | failure_mode | causal_path | falsification | success_criterion |
|---:|---|---|---|---|---|---|
| 1 T091 | **APPROVE** | Stage B pass率、Sharpe/PnL必要条件充足率 | median+pfre 同時トリガーで全滅 | ゲートを「必要条件の分離 + 過剰同時失格抑制」に再設計すると、評価可能個体がStage Bに残る | run-52 archive replayで pass=0 継続なら仮説棄却 | Layer1 replayで Stage B pass>=1、Layer2で `trade_count_full>=50` かつ `pnl>=50,000` 個体>=1 |
| 2 n_fold_effective=0ガード | **MODIFY**（今cycleは概念設計のみ） | best個体の評価可能性 | `n_fold_eff=0` でも上位化 | 選抜scoreへ「評価可能性ペナルティ」1要素を追加し、評価不能上位化を抑制 | T091後でも best が `n_fold_eff=0` のままなら棄却 | 次cycle実装後、bestが `trade>=50 & n_fold_eff>=5` を満たす |
| 3 entropy監視 | **REJECT（Phase1内実装）/ Phase2へ移動はAPPROVE** | 探索多様性監査 | seed別機能多様性低下 | まずゲート正常化前に監視追加しても処方が不明確 | T091後に collapse再現しないなら優先度低下 | Phase2開始後に entropy>=1.5 維持を検証 |
| 4 cross-pair shadow復帰 | **REJECT（Phase1内実装）/ Phase2へ移動はAPPROVE** | ii-lite監査性 | cross-pair判定INCONCLUSIVE | Stage B未解決のままshadow追加は因果混線 | T091後に単体で mission未達なら必要性再評価 | Phase2でarchiveにshadow記録を必須化 |

## A. 提案1（T091）合議
- `target_metric / failure_mode / causal_path / falsification / success_criterion` は妥当。
- 既存Round 5設計は**実装着手に十分**。追加は1点のみ: 「失格理由の分解ログ（どの条件で落ちたか）」を必須化。
- 実装監視ポイント:
1. Stage B失格理由の分布（単一条件集中か）
2. `n_fold_effective` 分布の世代推移
3. `trade_count_full` 下限違反率
4. spread/swap反映後のPnL符号反転率
5. Stage Cへの通過母数（0張り付き監視）

## B. 提案2 合議
- **今cycle開始は概念設計のみ**が妥当（実装は次cycle）。
- 最小設計は **selection_score追加要素1つ** を推奨。`IndividualCacheEntry` field追加はスキーマ衝突リスクが高い。
- T091同時期の schema bump 競合は高リスク。`v3_4→v3_5` をT091専用にし、提案2は次版へ分離。

## C. 提案3,4 Phase2移動
- 妥当。理由: Phase1未完で入れると collider bias と責務混線が増え、反証不能になる。
- Phase2開始トリガー:
1. T091実装完了
2. Layer1 replayで Stage B pass>=1 を確認
3. Layer2で少なくとも1 runが `trade_count_full>=50` を満たす
4. Stage C評価が実行可能（母数ゼロでない）

## D. 次RUN戦略
- **APPROVE**: まず Layer1 archive replay（run-52）を先行。
- Layer2 seed戦略は別議論で決定、今回計画では固定しない。
- run_argsはまず前RUN同一（`seed=100, gens=60`）で因果同定を優先。比較seedはその後の別実験として分離。