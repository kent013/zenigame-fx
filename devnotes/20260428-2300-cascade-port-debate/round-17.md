**Cross-Cutting 診断（検査1〜7）**

1. **検査1: gate/search 関係**
診断: **整合（軽微修正あり）**。  
あなたの理解で正しいです。`gate fail` 個体が archive に入る経路は `score_bypass` のみであるべきです。  
修正点は1つで、`score_bypass` 候補を **Stage B評価済み個体に限定** してください。A-only proxy 個体を bypass で入れると gate/search 分離が崩れます。

2. **検査2: Stage A 時間配置と warmstart**
診断: **整合**。  
`genomeのみ継承、評価値は継承しない` が守られていれば時間整合は成立します。  
必須は `origin_epoch_id` と `reval_epoch_id` の分離保持です。

3. **検査3: Stage A→B 連動と Pareto 評価値ソース**
診断: **修正必要**。  
選択は **(iii) ハイブリッド**。ただし運用は明確に分けます。  
`GA内 selection 圧は A proxy`、`archive/昇格判定は B pooled`。  
混在比較を避けるため、同じ順位計算で A/B の数値を直接混ぜない設計にします。これで逆ピラミッドを回避できます。

4. **検査4: 緊急モード × epoch-rolling**
診断: **修正必要**。  
選択は **(b)**。`35%` は現行の `prev_epoch 20%` 制約下で供給不足リスクが高いです。  
緊急時 warmstart は `20% -> 25%`（1 runのみ）に下げるのが整合的です。

5. **検査5: profit_factor tie-break**
診断: **修正必要**。  
`raw PF` は `GL=0` で不安定なので、tie-break は `log_pf_clip` に統一してください。  
`log_pf = clip(log((GP+1e-6)/(GL+1e-6)), -2, 2)`。

6. **検査6: dataset_epoch_id 伝搬**
診断: **修正必要（実装前に契約固定が必要）**。  
`archive`, `calibrate-gate history`, `warmstart filter`, `report/monitor` の全経路で必須キーにします。  
ここは禁止事項8（伝搬漏れ）の最重要ポイントです。

7. **検査7: 残存 default 固執**
診断: **INCONCLUSIVE が残る**。  
残っているのは `stride=4w`, `archive=120`, `inflow比率0.04/0.06`, `HAC q=5`, `trade=0→0.5`。  
全部「合理的初期値」ではあるが、まだ強い実証根拠ではありません。smoke 後に再同定前提で固定してください。

---

**検査3 の最終回答（要求2）**
選択は **(iii)**。  
定義は次のとおりです。

- `search source`: Stage A proxy（全個体、全世代）
- `gate/admission source`: Stage B pooled（A通過の候補群のみ）
- `score_bypass`: B評価済み個体のみ対象

これで compute は軽く、かつ archive 品質は B基準で担保できます。

---

**検査4 の最終回答（要求3）**
選択は **(b)**。  
緊急時は `warmstart_share=25%`（1 run限定）、`CA:DA=1:1`、`prev_epoch 20%上限は維持`。  
`(a)` は stale 注入を増やし、`(c)` はさらに汚染リスクが高いので不採用です。

---

**論点G 確定（要求5）**

1. **Phase 1: Contract 固定**
DoD: `dataset_epoch_id` を含む共通スキーマ（run/eval/archive/history/report）を確定し、型定義を1箇所化。

2. **Phase 2: Dataset/Epoch/Partition 実装**
DoD: `24m rolling(4w stride, max 6 runs/epoch)` と `B62+A8+emb+C-lite*3+emb+C12` を再現可能。

3. **Phase 3: Metric Engine 実装**
DoD: canonical5, mission_inf_gap, slack_to_range, log_pf_clip を同一APIで算出可能。

4. **Phase 4: Stage Evaluator 実装**
DoD: A/B/C-lite/C の評価器が動作し、Bは5fold pooled主判定、fold fail-fast補助を満たす。

5. **Phase 5: NSGA-II + CPPS Core**
DoD: 3-state FSM, CA/DA再配分, pop192/256両対応スケーリングが動作。

6. **Phase 6: Loop Closure**
DoD: archive admission/eviction、inflow、bypass K、warmstart ramp、epoch-aware filter が仕様通り動作。

7. **Phase 7: Emergency + Calibrate Gate 統合**
DoD: 緊急モード（25%）と凍結窓/Δ制限/epoch-scope が干渉なく動作。

8. **Phase 8: Observability + Audit Scaffold**
DoD: PBO/DSR/SPA 用の集計スキーマとレポート雛形が生成される（判定ロジックは後追い可）。

9. **Phase 9: Graduation Lane Scaffold**
DoD: batch起動条件（graduates>=24, 3 epoch, mission連続）で起動判定まで実装。

並行可能性:
- Phase2 と Phase3 は並行可能。
- Phase5 と Phase6 は Contract固定後に並行可能。
- Phase8 は Phase1完了後、他Phaseと並行可能。

---

**Risk Top 5（要求6）**

1. A-proxy と B-pooled の乖離で探索が誤誘導される。  
緩和: `A→B 乖離メトリクス` を毎run記録し、閾値超過で q_force を引き上げ。

2. epoch_id 伝搬漏れで cross-epoch 汚染が起きる。  
緩和: スキーマ lint（必須フィールド欠落で fail）。

3. 緊急時 warmstart 供給不足で実質動作しない。  
緩和: 35%を廃止し25%固定、rampと整合。

4. archive が bypass 偏重で品質低下する。  
緩和: bypass を B評価済み＋品質床必須に限定。

5. DA 多様性が形骸化する。  
緩和: DA eviction に novelty と coverage を主キー化し、週次で entropy 監視。

---

**TODO候補（要求7, fresh番付）**

- `T901` Schema Contract: `dataset_epoch_id` 全経路必須化
- `T902` Epoch/Window Manager: 24m rolling + run cap
- `T903` Partition Engine: B/A/C-lite/C splitter + embargo
- `T904` Metric Core: canonical5 + mission_inf_gap + slack_to_range
- `T905` Sharpe HAC: q=5 実装 + source tag
- `T906` Stage A Evaluator: trade_rate中心 proxy
- `T907` Stage B Evaluator: 5fold pooled + fail-fast
- `T908` NSGA-II Core: rank/crowding + pop192/256
- `T909` CPPS FSM: explore/bridge/pull + refine flag
- `T910` Archive Engine: CA/DA別 eviction + log_pf tie-break
- `T911` Warmstart Engine: 20% ramp + epoch-aware filter
- `T912` Emergency Mode: 25% one-run boost +解除条件
- `T913` Calibrate Gate Scope: epoch key + freeze/Δ制限
- `T914` Shadow Robustness: 連続score + per-pair保存
- `T915` Observability: A/B乖離・entropy・inflow監視
- `T916` Audit Scaffold: PBO/DSR/SPA レポート枠
- `T917` Graduation Batch Scaffold: 起動条件判定
- `T918` F-1 Smoke Matrix: pop/gen/workers の実測実験

この状態で、次は `T901-T904` を先に固定すれば、後続実装の手戻りを最小化できます。