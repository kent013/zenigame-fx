**Section A: 各施策判定（Run 10→11）**

1. **Stage B 全滅の原因切り分け（Critical）**
- 判定: **APPROVE**
- 分類: **Structural**
- target_metric: `stage_b_pass_rate`（実ゲート）/ `shadow_stage_b_pass_rate`（診断用）
- failure_mode: Stage A 通過後に Stage B が 0% のまま
- causal_path: WF 構成（`wf_train_days=120` と 14日窓の不整合）で OOS Sharpe が構造的に出ない
- falsification: 同一個体群に対する shadow 評価で `wf_train_days` を短くしても pass が有意に増えない
- success_criterion: 「どの条件で落ちるか」を 1 つに特定（例: train_days依存 or Sharpe閾値依存）

2. **trade_count を 50 に押し上げるフィットネス調整（Warning）**
- 判定: **MODIFY**（Run 11 では直接適用しない）
- 分類: 現提案は **Reactive Parametric → REJECT**
- 構造化代替案: **Structural** として「寄与分解ログ（fitness内の trade_count寄与率）」を追加し、次Runで **Principled Parametric** に移行判断
- target_metric: `trade_count_mean`, `trade_count_p50`, `trade_count>=50 比率`
- failure_mode: 高Sharpe少数取引個体に探索が偏る
- causal_path: 目的関数の重み/形状が頻度不足を許容
- falsification: 寄与分解で trade_count 項が十分効いているならこの仮説は棄却
- success_criterion: 次Runで調整要否を定量判定できる状態になる

3. **データ窓拡大検討（Warning, Structural）**
- 判定: **REJECT（現時点）**
- 分類: **Structural** だが禁止事項1（期間延長根拠なし）に抵触
- target_metric: なし（今は実施しない）
- failure_mode: 根拠なき期間延長で過学習/解釈不能
- causal_path: ボトルネック未特定のまま探索空間だけ拡張
- falsification: Stage B 診断で「サンプル不足」が明確に示された場合のみ再提案
- success_criterion: 根拠付きでのみ再審議

4. **PnL 集計監査（cycle1保留, Warning）**
- 判定: **APPROVE（軽量版）**
- 分類: **Structural**
- target_metric: `pnl_recompute_diff`, `cost_component_consistency`
- failure_mode: swap/spread 含む計算不一致で fitness 解釈が歪む
- causal_path: 集計経路差異（バックテスト vs 評価）
- falsification: 再計算差分がゼロ近傍なら監査仮説棄却
- success_criterion: 差分ゼロ（許容誤差内）を確認

---

**Section B: Run 11 への組み込み（最小変更で切り分け）**

- 反証可能仮説（1つ）:  
  **H11**: Stage B 全滅の主因は「閾値そのもの」より「WF構成ミスマッチ（`wf_train_days=120`）」である。
- 最小変更（1つ）:  
  **Stage B shadow診断を追加**（実ゲート条件は一切変更しない）。  
  同一候補に対して `wf_train_days={60,90,120}` × `median_oos_sharpe_min={0.10,0.20,0.30}` の pass 率を記録。
- 判定基準:
  - 120のみ壊滅・短縮で回復 → WF構成起因を支持
  - すべて壊滅 → 閾値/特徴量/分布側を疑う

---

**Section C: 保留事項（次Runで検証する仮説+最小変更）**

1. **trade_count不足**
- 仮説: 頻度不足は目的関数形状由来
- 最小変更候補: `trade_count` 項を **Principled Parametric**（50を中心にした滑らかな十分性ペナルティ）で1回だけ導入

2. **データ窓拡大**
- 仮説: サンプル不足が真因
- 最小変更候補: Stage B 診断で不足が確認できた場合のみ、根拠付きで窓拡大を再審議

---

**Section D: cycle_focus**

- 推奨: **`ga_improvements`**
- 理由: TODO が 0 件、BG agents 完了通知未着のため、今ラウンドは Run 11 の反証実験を優先して収束させるのが最短。  
- 補足: FX 制約（イントラデイ、ロング/ショート、swap/spread fitness反映）は現行維持。live_criteria 緩和は実施しない。