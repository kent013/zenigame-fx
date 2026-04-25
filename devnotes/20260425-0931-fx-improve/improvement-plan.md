# 最終改善計画: Run 9 → Run 10

## 合議ステータス: CONSENSUS REACHED (Round 1)

## 確定施策一覧

| # | 施策名 | 内容 | 変更対象 | 優先度 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion | 合議結果 |
|---|--------|------|---------|--------|---------|--------------|-------------|------------|---------------|-------------------|---------|
| 1 | 無取引ペナルティの構造的導入 | trade_count=0 を fitness 上で劣後（または不適格化）する構造変更 | `src/alpha_factory/` の fitness/penalty 計算（要 plan-and-design Phase C 詳細化） | Critical | Structural | trade_count=0 個体比率を Run 10 で 30% 未満 | 無取引が相対優位で GA が「沈黙」へ収束 | trade_count=0→fitness_pen=0 が取引する負 Sharpe より上位 | 変更後も上位 10 個体の過半が trade_count=0 | 上位 10 個体で trade_count>0 が過半、かつ Stage A 通過 1 件以上 | APPROVE |
| 2 | PnL 集計経路の数値整合性監査 | 挙動非変更で監査ログを追加 | `src/alpha_factory/` PnL 集計箇所 | Warning | Structural（Run 10 は監査のみ） | trade_count>0 で total_pnl=0 の比率原因特定 | 集計経路破綻を見逃す | PnL 計算/集約の不整合 → Sharpe/fitness が無効化 | 既知期待値テストで再現できず実ランでも整合 | 監査ログで「どの段で 0 化したか」特定または破綻なし証明 | MODIFY |

## 却下された提案

| # | 提案 | 却下理由 |
|---|------|---------|
| 3 | primitive 多様性の世代追跡（介入） | Round 1 では計測のみ最小化。介入は無取引優位解消後 |
| 4 | cross-pair shadow の実測検証 | 単独ペア RUN で skip 仕様。前提（Stage A 通過）未達のため対象外 |

## 保留事項（次 Run 検証申し送り）

| # | 仮説 | 最小変更案 | 検証条件 |
|---|------|----------|---------|
| 1 | Run 9 崩壊の主因は「無取引が目的関数上で優位」な構造欠陥 | trade_count=0 を構造的に劣後させる 1 変更のみ | Run 10 で trade_count=0 比率 < 30%、Stage A 通過 ≥ 1 件 |

## 次フェーズへの申し送り

- TODO リストは現状 0 件のため、施策 1 の構造変更を実装する **TODO を別途登録する必要がある**（post-run-review BG agent の出力を待つか、本サイクル内で `/zenigame-fx-todo-add` 経由で追加）
- 本 cycle では Phase 3 で実装される TODO がない場合、Run 10 はコード変更なしのまま実行される
- Run 10 結果を再分析して cycle 2 で実装フェーズに進む流れを想定

## 使命チェック

- ✅ 施策 1: trade_count を増やす方向（live_criteria.trade_count_min=50 達成への前進）
- ✅ 施策 2: 数値整合性監査（live_criteria 評価の信頼性向上）
- ✅ 禁止事項違反なし（取引回数削減 / 期間延長 / 閾値緩和なし）
