**1. 検査1〜5の診断**

1. **検査1（Stage間スケール整合）: 修正が必要**  
理由: `Sharpe` と `profit_factor` と `max_dd` の期間依存が未正規化。Stage A/B/C-lite/C で同一 gap 尺度になっていない。  
反証: 同一個体で Stage A→B→C-lite→C の `margin_inf` 順位がスケール変換前後で安定するなら問題は小さい。  
必要修正:
- Sharpe を全Stageで「日次リターン年率換算」に統一。
- max_dd は horizon 補正（例: `dd_norm = dd / sqrt(T_days/60)`）。
- profit_factor は安定化（`log_pf = log((GP+eps)/(GL+eps))`、`GL=0` 無限大対策）。

2. **検査2（cross-stage lookahead）: 一部整合、一部修正が必要**  
(i) Stage C結果で Stage B閾値再校正: **修正必要**（meta-overfit経路）。  
(ii) support-aware重みの全期間計算: **修正必要**（C holdout混入）。  
(iii) archive→warmstart時系列整合: **整合可能だが実装規約が必要**。  
(iv) calibrate-gate history適用: **INCONCLUSIVE**（lookaheadではないが同一dataset過適応の懸念）。  
反証: 「run開始時スナップショット固定」「holdout除外重み」で成績が変わらなければ懸念は小さい。

3. **検査3（硬直化/デッドロック）: 修正が必要**  
理由: `target_inflow=10` と `per_run_max=8` は構造的衝突（毎runで2体を自動棄却）。  
反証: 実運用で制約違反ゼロなら成立だが、設計上は矛盾が残る。  
必要修正:
- `per_run_max: 8 -> 10` に変更。
- 制約充足不能時の明示的緩和順を追加（pattern -> run -> family）。

4. **検査4（cycle健全性 vs selection圧）: 修正が必要**  
理由: bypass補充で枯渇は防げるが、品質劣化ループの防波堤が弱い。  
反証: bypass比率が高くても Stage C到達率が落ちなければ現行でも可。  
必要修正:
- bypass候補に品質床（例: run内 `margin_inf` 上位70%以内 + invariant可行）。
- 強制通過率を固定線形ではなく feasible_ratio連動へ（下記）。

5. **検査5（前提連鎖）: INCONCLUSIVE + 一部修正必要**  
(a) Stage B session bucketごとの `trade_count>=15` は取引密度依存で未確定。  
(b) profit_factor の低取引不安定性は修正必要。  
(c) margin_inf の分母設計は未確定。  
反証: 24か月データで実測 `trades/day` が十分なら解消。現時点は未確証。

---

**2. 修正が必要な項目（具体値）**

- `per_run_max = 10`（旧8）
- `support-aware weight` は **development spanのみ**で計算（C holdout除外）
- run開始時に `archive_snapshot_id` を固定し、run中の新規entryは次runからのみ注入可
- bypass動的Kは維持しつつ候補品質床を追加  
  `eligible_bypass := invariant_feasible && margin_inf_percentile <= 70`
- 強制通過率を可変化  
  `q_force = clamp(0.15 + 0.15 * max(0, 0.10 - feasible_ratio_ema)/0.10, 0.15, 0.30)`  
  （feasibleが薄い時だけ 0.30 まで拡張）
- profit_factor安定化  
  `log_pf = log((GP+1e-6)/(GL+1e-6))` を使用、`trade_count < TC_pf_min` は `INCONCLUSIVE penalty`
- margin_inf 正規化分母を明示  
  各指標の `gap = signed_slack / denom_m`（`denom_m` は stage横断固定）

---

**3. 未解決 gap リスト（Round 8 で詰めるべき）**

- `denom_m` の最終仕様（Sharpe, net_return, max_dd, trade_count, profit_factor）
- Stage B での実測取引密度に基づく `session 3 bucket` 妥当性
- calibrate-gate の更新周期と凍結期間（meta-overfit抑制）
- eviction score の最終式（quality / recency / diversity の重み）
- 緊急モード発動条件の閾値（3run連続悪化の定量定義）

---

**4. failure mode 候補（横断統合）**

- **FM1: スケール不整合崩壊**  
  兆候: Stage A高順位が Stage Cで一貫して崩れる。  
- **FM2: meta-lookahead汚染**  
  兆候: 閾値更新直後だけ成績上昇し、次runで剥落。  
- **FM3: archive硬直化**  
  兆候: 制約充足不能で注入8体を満たせないrunが増える。  
- **FM4: bypass品質希釈**  
  兆候: bypass比率上昇とともに mission_pass率が低下。  
- **FM5: regime疎化**  
  兆候: session別評価が `INCONCLUSIVE` だらけになる。

---

**5. risk-ordered top 3（先に潰す順）**

1. **指標スケール不整合（FM1）**  
先に潰す方法: `margin_inf` の分母仕様を固定し、同一個体で Stage横断の順位安定性テストを最初に実施。  
2. **meta-lookahead/循環最適化（FM2）**  
先に潰す方法: run開始時スナップショット固定、holdout除外重み、threshold更新の凍結窓導入。  
3. **archive品質希釈（FM4）**  
先に潰す方法: bypass品質床 + eviction tier（mission/progress/bypass）を先に実装。

---

C1-C9 観点では、今回の未確証点は意図的に `INCONCLUSIVE` としました。特に `trade_count 密度` と `denom_m` は、設計仮説のまま確定すると後段を壊すため、Round 8 の最優先検証項目です。