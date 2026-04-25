## Q5. Clause 複雑度制約の定量設計
### 観察された事実 / 文献根拠 (Facts)
- F1: GP は `bloat` が構造的に起きやすく、深さ制限だけでは十分でない場合がある（Koza, 1992; Poli et al., 2008; Luke & Panait, 2006）。
- F2: 有効サンプルを 250 日程度とみなすと、BIC の 1 パラメータ罰則は `ln(250)≈5.52`。自由度を増やす設計は強い証拠が必要。
- F3: Allen & Karjalainen (1999) は主に木構造制約と取引コスト評価で設計されており、現代的な大規模探索（多数世代・多数候補）では明示的 parsimony 追加が有利という実務報告が多い（詳細は要確認）。
- F4: 1銘柄学習では「式の複雑化=市場構造学習」ではなく「ノイズ当て」の確率が上がりやすい。

### 解釈・推論 (Interpretations)
- I1 (from F1, F2, F4): FX 1銘柄では `max_clause=2` をデフォルト、`max_clause=3` は昇格条件付きが妥当。  
- 反証可能性(I1): `max_clause=3` が `2` に対して、同計算予算で OOS DSR を有意改善できなければ `3` 常用は棄却。
- I2 (from F1, F3): 深さ制限のみでなく、明示的複雑度項が必要。推奨式は以下。  
  `fitness_pen = fitness_raw - α * size_norm`  
  `size_norm = (nodes + 0.5*depth + 2*(n_clause-1) + 0.5*gate_nodes) / size_ref`
- I3 (from F1, F4): αは固定より適応が安定。初期推奨は `α=0.03~0.08`（Sharpe尺度）または共分散型 parsimony（Poli 系, 要確認）。
- 反証可能性(I2/I3): α強化で top-k の多様性が急減し OOS が改善しないなら、size 定義か α が過剰。

### 暫定判定 (Verdict)
- 推奨設定:
1. `max_clause=2`（Phase 2 標準）、`3` は条件付き解放。  
2. `max_depth=4~5`（合成式深さ）。  
3. Stage A から弱いペナルティを入れる（`α_A≈0.03`）、Stage B/C で中程度（`α_BC≈0.05~0.08`）。
- 見直し条件（反証トリガー）:
1. 連続 3 run で `Jaccard(top20_t, top20_t+1)<0.2` かつ OOS DSR 改善なし。  
2. `active_clause_mean` が 1.1 未満に張り付く（Clause 機構が使われていない）。  
3. パフォーマンス維持率（penalty有/無）<70% が継続。
- Round 1 との整合: **矛盾なし**（Round 1 の「複雑度管理必須」を数値化しただけ）。

---

## Q6. (ii-lite) 常設ベンチマークの具体設計
### 観察された事実 / 文献根拠 (Facts)
- F1: 横断評価は過学習耐性を上げるが計算コストはほぼ `N_pairs` 倍。
- F2: 6ペアは少数だが、USD 共通因子で相関があるため「完全独立系列」ではない。
- F3: 集約関数は実質的に最適化目的そのものを変えるため、champion の顔ぶれが変わるのは正常。
- F4: per-instrument 最適化に横断ゲートを後段追加すると、過剰特化を落としやすい一方で「二重罰」リスクがある。

### 解釈・推論 (Interpretations)
- I1 (from F1, F4): 実行タイミングは **Stage B 直後〜Stage C 前**（B2ゲート）が最適。C直前で落とすのが実運用リスク最小。
- I2 (from F1, F2): 評価ペアは「全6ペア」が理想。計算制約があるならアンカー3ペアで開始し、`target + 同基軸1 + 同決済通貨1` を原則化。
- I3 (from F3): 集約は単一関数固定より、感度監査を組み込むべき。推奨主目的関数:  
  `F = mean(Sharpe_i) - 0.5*std(Sharpe_i)`  
  併記監査: `min(Sharpe_i)`, `weighted mean`（流動性重み）。
- 反証可能性(I3): 集約関数を変えると rank 相関（Kendall τ）が恒常的に低い（例 `<0.5`）なら、目的関数依存が強すぎる。

### 暫定判定 (Verdict)
- 通過基準（初期案）:
1. `Sharpe_target_cross >= 0.8 * Sharpe_target_single`  
2. `mean Sharpe_cross >= 0.15`  
3. `min Sharpe_cross >= -0.20`  
- 二重罰の判定基準:
1. (ii-lite) 追加後に target Sharpe が 20%以上低下。  
2. それでも DSR/PBO が改善しない（`ΔDSR<0.05` かつ `ΔPBO>-0.05`）。  
  この場合は hard gate を一時停止し、shadow gate に戻す。
- Round 1 との整合: **矛盾なし**（「常設ベンチマーク」を実装手順化）。

---

## Q7. 移行トリガーの事前固定（CONDITIONAL の条件化）
### 観察された事実 / 文献根拠 (Facts)
- F1: DSR は「試行回数込みの有意性補正」に有効（Bailey & López de Prado, 2014）。
- F2: PBO は過学習確率の直接指標で、0.5超は強い警告（Bailey et al., 2014）。
- F3: White Reality Check / SPA はデータスヌーピング補正に有効だが計算コストが高い（White, 2000; Hansen, 2005）。
- F4: 単一指標での判定は誤検知しやすく、複合条件が必要。

### 解釈・推論 (Interpretations)
- I1 (from F1): DSR は単発でなく連続で判定すべき。推奨は `k=3` 連続。  
- I2 (from F2): PBO は `>0.4` を警戒、`>0.5` を強トリガー。  
- I3 (from F3): Reality Check/SPA は Stage B 毎回フル実行でなく、候補圧縮後に実行が現実的。
- 反証可能性(I1-I3): 指標群が悪化しても live/OOS が安定改善するなら、閾値設計が厳しすぎる可能性。

### 暫定判定 (Verdict)
- 実装しきい値（提案）:
1. **DSR**: `DSR<0` が同一ペアで 3 run 連続、または直近5 run中4回。  
2. **PBO**: `PBO>0.4` 警戒、`PBO>0.5` で即移行候補。  
3. **符号反転率**: walk-forward で `m/N >= 0.4`（OOS Sharpe負のfold比率）。  
4. **RC/SPA**: `p>0.10` が 2 run 連続で警戒、3連続で強トリガー。
- 計算設定:
1. CSCV 分割 `S=8`（`C(8,4)=70` 組合せ）を最低ライン。余力あれば `S=10`。  
2. RC/SPA ブートストラップ回数は `B=1000`（通常）、重要判定時 `B=3000`。
- 複合トリガー（推奨）:
1. **Hard migrate to (ii)**: `PBO>0.5` AND (`DSR<0` 3連続 OR `m/N>=0.4`)。  
2. **Soft migrate / monitor強化**: 上記未満でも警戒条件2つ同時発火。
- Round 1 との整合: **矛盾なし**（Round 1 の定性条件を定量化）。

---

## Q8. Currency common factor への対応
### 観察された事実 / 文献根拠 (Facts)
- F1: FX には共通因子（USD要因、リスク要因）が存在する証拠がある（Lustig et al., 2011; Menkhoff et al., 2012）。
- F2: 完全 per-instrument 最適化は、共通因子情報を構造的に捨てる。
- F3: 三角関係 `EUR/JPY ≈ EUR/USD × USD/JPY` は価格整合の恒等制約で、複数ペア同時運用で通貨エクスポージャ不整合を起こし得る。
- F4: 因子導入は有効だが、時系列整列・リーク管理が難しく、実装ミスで逆効果になる。

### 解釈・推論 (Interpretations)
- I1 (from F1, F2, F4): 推奨は **(α)+(β) の段階導入**。  
  まず評価時フィルタ（β）で検証し、効く因子だけ DSL 変数（α）へ昇格。
- I2 (from F3): per-instrument GA 単体では三角裁定問題は顕在化しにくいが、複数champion同時運用で顕在化。execution 層で通貨ネットエクスポージャ制約が必要。
- I3 (from F4): (γ)「GAが自力発見」は現実的でない。DSL 入力に存在しない情報は探索できない。
- 反証可能性(I1-I3): 因子追加後に `ΔDSR<0.05` かつコスト悪化（turnover+10%以上）なら因子導入は一旦撤回。

### 暫定判定 (Verdict)
- 実装優先:
1. Phase 2: β（評価時レジームフィルタ）  
2. Phase 3: α（DSLに `dxy_ret`, `risk_proxy` など遅行特徴を追加）  
3. Phase 4: 同時運用時の通貨エクスポージャ上限制約（例 `|net_USD| <= L`）
- Round 1 との整合: **矛盾なし**（「共通因子を無視するな」を実装分解）。

---

## Q9. 実装順序と「最小動く状態」
### 観察された事実 / 文献根拠 (Facts)
- F1: 早期に全統計検定を詰め込むと、移植初期はデバッグ困難になる。
- F2: ただし「後で入れる」だけでは閾値の事後最適化が起こり、falsification-first に反する。
- F3: Clause は段階解放の方が障害切り分けしやすい。
- F4: (ii-lite) は hard gate と shadow gate を分けると開発速度と検証厳密性を両立しやすい。

### 解釈・推論 (Interpretations)
- I1 (from F1, F2): MVP でも「指標計算の枠組み」と「しきい値設定ファイル」は先に固定すべき。発動だけ遅らせる。
- I2 (from F3): `max_clause=1 -> 2 -> 3` の段階展開は妥当。ただし gate と重み機構は最初から実装し、単なるフラット4式に戻さない。
- I3 (from F4): (ii-lite) は Phase 2 で shadow 実装、Phase 4 で hard gate 化が現実解。
- 反証可能性(I1-I3): 段階展開後も `active_clause` が増えず、性能差も出ないなら Clause 方針を再評価。

### 暫定判定 (Verdict)
- MVP 定義（「improve-cycle が1サイクル回る」最小要件）:
1. Clause genome（`max_clause=1` で開始）  
2. Stage A/B/C の最小実装（BはWF-OOS必須）  
3. archive に `instrument` と複雑度メトリクス保存  
4. (ii-lite) shadow 評価（非ブロッキング）  
5. DSR/PBO/符号反転率の計算器と固定閾値ファイル（発動は保留可）
- 発動タイミング:
1. 移行トリガー hard 発動は **最低 30 run または各ペア5 run の遅い方** から。  
2. それまでは monitor-only。
- 「結局フラット式」化の防止:
1. Phase 2 末で `max_clause=2` 解放テストを必須。  
2. `active_clause_mean >=1.3` を達成できなければ設計見直し。
- Round 1 との整合: **原則一致**。優先順位は「Round 2 の具体化」を優先（Round 1 は方針、Round 2 は実装条件）。

---

## 【Round 2 総合判定】
- 判定: **STILL_VALID**
- 理由: Round 1 の「(b)×(i) + (ii-lite) 並走」は、Round 2 の定量化（複雑度制約、B2ゲート、複合移行トリガー）で実装可能な運用設計に落ちた。
- 修正提案（重要）:
1. `(ii-lite)` は Phase 2 で **shadow 必須**、Phase 4 で **hard gate 化**。  
2. 移行トリガーは最初に固定し、発動のみウォームアップ後。  
3. Clause は `1→2→3` 段階解放だが、gate/weight 機構は初日から有効化。  

この3点を守れば、falsification-first と開発速度の両立が可能です。