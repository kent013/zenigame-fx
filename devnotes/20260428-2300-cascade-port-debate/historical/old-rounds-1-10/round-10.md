**反証先行（最終ラウンド）**
- まず崩しに行くべき仮説は「設計は固まったので実装は一直線で安全」です。実際は `FM1(スケール不整合)` と `FM4(archive品質希釈)` が先に崩れやすいです。  
- したがって最終文書は「仕様定義 → 失敗条件 → 実装順」の順で固定するのが妥当です。

## 1. 最終確定文書の章立て提案
提示の 1〜7 は妥当です。抜けている観点として 2 つ追加を推奨します。

1. 使命・非目標（Out of Scope）
2. 5原則 + 7役割マトリクス
3. 確定構成全体図（全ハイパーパラメータ表）
4. 数式仕様（`gap_m`, `margin_inf`, `eviction_score`, `q_force`, 緊急モード条件）
5. 適用順序（Phase A〜F, dependency, critical path, DoD）
6. Risk top 5 と緩和策
7. FM1〜FM5 と観測ログ仕様
8. TODO 化候補（T-XXX）
9. Rollout strategy（切替・削除・fallback）
10. INCONCLUSIVE / 検証待ち項目

追加理由:
- 数式章がないと実装解釈差で再分岐します。
- INCONCLUSIVE章がないと未確証が暗黙仕様化されます。

## 2. TODO化候補（1〜3日粒度）
総量目安: **20 TODO / 30〜42人日**（並行で 12〜20営業日相当）。

- `T901` 24ヶ月データ取得パイプライン固定（M1+aux）1-2日
- `T902` preflightを24ヶ月要件へ拡張 1日
- `T903` selection-cascade-design.md新設 1日
- `T904` terminology.md更新（SSOT）1日

- `T911` canonical5 gap計算ヘルパー実装 2日
- `T912` `log_pf` / `max_dd_adj` / `sharpe_ann` 実装 2日
- `T913` invariant fail-fast実装 1日
- `T914` session bucket label実装（lookahead-safe）1日
- `T915` support-aware weight実装（holdout除外）1-2日
- `T916` cross-pair evaluator更新 1-2日

- `T921` Stage A再実装（動的`q_force`）2日
- `T922` Stage B WF gate再実装（45/1/20, fold-median）2-3日
- `T923` Stage C-lite再実装（3 windows, 15 cells）2-3日
- `T924` Stage C再実装（holdout+stress+cross-pair）2日
- `T925` 旧Stageロジック削除 1日

- `T931` 3軸Pareto + crowding導入 2-3日
- `T932` one-switch push/pull導入 1-2日
- `T933` bypass品質床 + trade_count段階制御 1-2日
- `T934` 旧single-objective GA削除 1日

- `T941` CA/DA archive実装（50/50, total100）2日
- `T942` 3層流入 + 動的K実装 2日
- `T943` eviction hard/soft実装 2-3日
- `T944` warmstart制約 + reuse/cooldown実装 2日
- `T945` 緊急モード実装（MA3/MA6）1日
- `T946` calibrate凍結窓実装（3run freeze, Δ<=0.03）1日
- `T947` 旧alpha_sieve統合/削除 1-2日

- `T951` 1run smoke（E2E）1日
- `T952` FM1〜FM5ログ実装 1-2日
- `T953` 5run連続検証 1-2日
- `T954` ablation実験（単目的vs3軸, 単一archivevsCA/DA）2-3日

## 3. rollout strategy（削除タイミング）
**推奨:「実装は段階、切替はビッグバン、旧実装は切替同日削除」**

- 開発中は新実装を `new_cascade` 名前空間で段階実装。
- `T951`（1run smoke）と `T953`（5run）を通過した時点で切替。
- 切替コミットで旧Stage/旧GA/旧sieveを同時削除。  
  後方互換不要なので dual-path 運用は避ける（分岐バグ温床）。

反証条件:
- 5runでFM1/FM4が強く出るなら削除を1サイクル延期し、旧実装は“実行不可の参照コード”として凍結のみ。

## 4. 最終 sanity check
**整合している点**
- Objective taxonomy と CPPS が矛盾していない（exec系はinvariant/tie-breakへ分離済み）。
- P2主軸(session) と loop制約(max_per_session_pattern) が接続済み。
- per_run_max=10 と target_inflow=10 の衝突は解消済み。

**INCONCLUSIVE（残すべき明示項目）**
- `total_trades_B < 30` の発生頻度（実データ依存）。
- eviction重み `0.70/0.15/0.15` の最適性。
- 緊急モード閾値 `MA3 < MA6 - 0.05` の妥当性。

## 5. next action top 3（明日着手）
1. `T911/T912/T913` を先に実装して canonical5数式とfail-fastを固定。  
2. `T922` を実装して Stage B gate を単体で回し、`total_trades_B` 分布を実測。  
3. `T951` 用の最小E2E（A,B,C,Dの最小線）を作って1run smokeを通す。

## 6. 「やってはいけない」リスト
- smokeが遅いから `session bucket=2` に勝手変更する。
- holdoutを含めて support-aware weight を計算する。
- `mission=0` が続いたから live_criteria を緩和する。
- spreadを hard constraint 化して trade削減で成績を作る。
- `session_close_drop` / `negative_equity_drop` の fail-fast を無効化する。
- bypass品質床を外して inflow数だけ満たす。
- 旧実装と新実装を長期間並走させる。
- 4run更新ルールを破って calibrate を毎run回す。

この構成なら、実装文書としてそのまま `docs/alpha_factory` と `TODO.md` に落とせます。