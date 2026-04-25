# 最終改善計画: Run 10 → Run 11

> **⚠️ SUPERSEDED (2026-04-25 15:xx 復旧時注記)**
>
> マシンクラッシュ復旧時に状況再評価。本 cycle (cycle 2) の前提だった「Run 11 = コード変更なし再現性検証 RUN」は、cycle 1 由来の post-review-codex 5 design (0937-* / 0939-* / 0956-* / 0958-*) が新規 TODO として登録され、コードベースが変わるため陳腐化した。
>
> - 本 cycle で計画した Stage B shadow 診断 / trade_count 寄与分解ログ / PnL 集計監査ログは、次 cycle で改めて評価し直す（新規 TODO 群との優先順位を再検討）
> - Run 11 実行は保留。新規 TODO 群を実装してから次 RUN を計画する
> - 本ファイルは履歴として保持

## 合議ステータス: CONSENSUS REACHED (Round 1, cycle 2)

## 確定施策一覧

| # | 施策名 | 内容 | 変更分類 | 優先度 | target_metric | 合議結果 |
|---|--------|------|---------|--------|--------------|---------|
| 1 | Stage B shadow 診断 | 実ゲート不変。同一候補に wf_train_days={60,90,120}×median_oos_sharpe_min={0.10,0.20,0.30} の pass 率を shadow 計測 | Structural | Critical | stage_b_pass_rate / shadow_stage_b_pass_rate | APPROVE |
| 2 | trade_count 寄与分解ログ | fitness 内の trade_count 項寄与率を計測（挙動変化なし） | Structural（観測強化） | Warning | trade_count_p50 / trade_count>=50 比率 / 寄与率 | MODIFY |
| 3 | PnL 集計監査ログ（軽量版） | swap/spread 含む集計差分を再計算してログ出力 | Structural | Warning | pnl_recompute_diff | APPROVE |

## 却下された提案

| # | 提案 | 却下理由 |
|---|------|---------|
| 旧4 | データ窓拡大 | 禁止事項1抵触リスク。Stage B 診断完了後に再審議 |

## 反証可能仮説（H11）

**Stage B 全滅の主因は「median_oos_sharpe_min 閾値」より「WF 構成ミスマッチ（wf_train_days=120 が窓 14 日に対して大きすぎる）」である**

判定基準:
- wf_train_days=120 のみ壊滅・短縮で回復 → WF 構成起因を支持
- すべて壊滅 → 閾値 / 特徴量 / 分布側を疑う

## 保留事項

1. trade_count 不足の構造化対策（Principled Parametric の十分性ペナルティ）— Stage B 切り分け後
2. データ窓拡大 — Stage B 診断で「サンプル不足」が示されたら再審議

## 実装経路（重要）

施策 1 と 3 は **Structural 変更** で `src/alpha_factory/` のコード変更が必要。本 cycle では:
- TODO リストが 0 件のため Phase 3 implement は走らない
- 施策の実装は次サイクル以降で TODO 経由（`/zenigame-fx-alpha-design` + `/zenigame-fx-todo-add`）が正規ルート
- post-run-review BG agent (5 theme、cycle 1 起動) の出力が次サイクルで TODO 化される見込み

## Run 11 実行

本 cycle の Run 11 は **コード変更なしの再現性検証 RUN**。Run 10 と同じ条件で best_fitness/Stage A pass rate/trade_count 分布の再現性を見る。
