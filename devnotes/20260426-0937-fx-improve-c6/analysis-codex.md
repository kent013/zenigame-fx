**推奨案（1件）**  
Cycle 6 は **案A: `threshold_delta_abs_max` を `0.5 -> 0.1`** を優先してください。  
理由: reset（案D）依存を避けつつ、再tightenの過補正だけを直接止められるため、最小変更で ratchet 再発リスクを下げられます。

**質問への回答**
1. ratchet即効策: **案A推奨**（B/Cは次段の微調整候補、Dは対症療法）。  
2. T031 `entry_count_min`: **50へ引き上げるべき**です。  
   これは「見栄え調整」ではなく、`live_criteria.trade_count_min=50` との整合を取る**実行可能性制約の修正**です。  
3. Cycle 6 の1施策（実行可能）  
   - 施策: `threshold_delta_abs_max=0.1`  
   - target_metric: 次Runで `A_pass_rate` を **10–30%帯**に戻す（0%脱却）  
   - falsification: `A_pass_rate=0%` または post-gate が再び急上昇（再tighten過剰）  
   - success_criterion: 連続2Runで `A_pass_rate>0` かつ gate変動が安定（急激な締め直しなし）

**全体判定**  
- Aは**制御不安定（運用バグ）**、Bは**制約不整合（設計バグ）**、Run-15で示された真因は引き続き**signal品質（median_oos_sharpe）**です。  
- まずAを止血し、その直後にBを必須整合として適用する順序が妥当です。