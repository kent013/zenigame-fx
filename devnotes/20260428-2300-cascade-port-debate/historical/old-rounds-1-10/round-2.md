**前提整理（Round 1 からの継続）**
- `Round 1 で据え置き`: `canonical 5` を pass/fail の核に置く、FX固有指標はまず `constraint/tie-break` 側で扱う、`reverse pyramid` は解消する。
- `Round 2 で更新`: dataset 方針と Stage B 役割を再確定する。

---

**1. 反論1（hybrid vs 先行延長）への回答**

`結論`: **D'（先行延長）に賛同**します。Round 1 の hybrid は撤回します。  
理由は「6カ月のまま C-lite を入れると、設計目的（window過学習防止）を満たせない zombie cascade になりやすい」ためです。

`Fact`
- 6カ月（約127営業日）では、embargo込みで `3 disjoint windows` を安定運用する余地が薄い。
- PBO/DSR/SPA 系の論点は「同一履歴での選抜反復」に厳しい。窓を増やすだけでは独立な情報を増やせない（Bailey et al., 2015/2017; Bailey & López de Prado, 2014; Hansen, 2005）。

`Interpretation`
- C-lite を「実装しただけ」で、guard が機能しないなら設計原則違反。
- よって **full cascade の前提データ長を先に固定**するのが筋。

`反証条件（この結論が崩れる観測）`
- 6カ月運用でも、window定義を変えても上位個体集合が安定し、かつ outer holdout 成績が劣化しない。
- 6カ月版と24カ月版で、PBO proxy（rank反転率、run間winner再現性）が同等。

---

**2. 反論2（Stage B α/β/γ）への回答**

`結論`: **(γ) WF gate 化**を推します。  
ただし現行の「full IS monitor」ではなく、**OOS中心のWF gate**へ置換します。

`採用理由`
- (α) 完全撤廃は A→C 直結になり、短期適合が C で初めて落ちる構造になりやすい。
- (β) 診断専用化は計算は軽いが、中流の頑健性圧が消える。
- (γ) は「fold間頑健性」を selection 圧として残せる。zenigame の B の役割を fx 文脈で再定義した形として整合的。

`反証条件`
- (γ) 導入後も Stage C 到達率が不安定で、B通過がC通過の予測力を持たない。
- (γ) が計算コストを押し上げ、Aより重い逆ピラミッドを再発させる。

---

**3. 反論3（fold構造: 60d vs 30d）への回答**

`結論`: **30d短縮は採らない**。`60d固定`でもなく、**45d前後 + 複数fold集約**を推します。  
提案テンプレートは `train 45 + embargo 1 + test 20`（Stage B）。

`量的根拠（Lo 2002のIID近似、要確認）`
- 近似式: `SE(SR) ≈ sqrt((1 + 0.5 SR^2) / N_eff)`  
- `SR=1` とすると `SE ≈ sqrt(1.5 / N_eff)`  
- 低頻度（0.3 trade/day）だと、30d train の期待約9トレードは不安定。60dでも約18でまだ粗い。  
- したがって **fold単体のSharpeで厳格判定しない**で、複数foldの `worst gap` 集約と総取引数下限を併用するのが妥当。

`PBO側のトレードオフ`
- train を短くしすぎると1foldのノイズが増え、選抜反復で lucky hit を拾いやすくなる。
- foldを増やすだけでは万能ではない。**fold集合は固定**し、外側 holdout（Stage C）を汚さない運用が必須。

---

**4. 反論4（aux制約）への回答**

`結論`: 24カ月延長の技術的ボトルネックは **FREDではなくM1価格・スプレッド履歴**です。

`制約として明示すべき項目`
- `EUR_JPY`（anchor）と shadow（`EUR_USD/USD_JPY` 等）の **24カ月M1連続性**。
- bid/ask または spread 復元に必要な履歴粒度。
- 欠損率、DST/タイムゾーン整合、週末fill方針の一貫性。
- `effective_from_utc` 契約適用後の実効サンプル減少（月次は+35d遅延）。
- preflight HARD_REQUIRED の対象と実データ可用性の整合。

`判断`
- 上記が満たせるなら D' は実行可能。
- 満たせないなら、6カ月で凌ぐのではなく「full cascade 開始条件未達」として明示し、縮退モード運用に留めるべきです。

---

**5. 論点1の確定案（committal）**

`最終提案`
1. **データ前提を先に固定**: full cascade の実行条件を `dataset >= 24 months`（最低でも18カ月）に設定。  
2. **Topology は A→B→C-lite→C を維持**。ただし Stage B は (γ) のWF-OOS gateに置換。  
3. **Stage B定義**: `train45/embargo1/test20` の固定fold群で `canonical 5 worst` を fold単位評価し、`median worst_gap` + `pass fold count` + `total test trade_count floor` で判定。  
4. **Stage C-lite定義**: 開発区間で `3 disjoint temporal windows` の 15セル worst を実施し、top30%強制通過を保持。  
5. **Stage C定義**: 最新60d holdout + spread stress + cross-pair shadow を mission gate として固定。  
6. **6カ月運用の扱い**: full cascade としては**使わない**。必要なら「配線検証用の縮退3段（A+B簡易+C）」に限定し、選抜結果を archive/warmstart の本流へ流さない。

`この確定案の反証条件`
- 24カ月化しても Stage B/C-lite の追加で OOS 改善が出ず、A→C 直結と同等。
- Stage B のWF gateが C 成績の予測力を示さない。
- 24カ月版で run間再現性が改善せず、むしろ winner の不安定性が増す。

---

この論点1で次に必要なのは、`Stage B fold群の固定方法（時系列インデックスをどう凍結するか）` と `C-lite 3窓の具体座標` の2点です。ここが決まれば、論点2以降の objective taxonomy に接続できます。