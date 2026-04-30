**更新点（Round 1 から）**
- 維持: `(f) regime_pass_pattern は P2 に入れない`、`(d) cross-pair は validation axis`。
- 更新: P2 主軸を `volatility` から **`session` 主軸**へ変更。`volatility` は副次タグ化。
- 更新: spectral は固定 `[0.40,0.35,0.25]` ではなく **support-aware（クリップ付き）**へ変更。

---

### 1. 反論1（vol vs session）への回答

**採用: (D) `session 3` を主軸、`volatility` は tag（非主軸）**

`Fact`
- Andersen & Bollerslev (1998), Ito & Hashimoto (2006) は、FX intraday の活動・変動が時刻帯に強く依存することを示す。
- `session` は bar 時刻で決定できる外生ラベル。`volatility` は推定窓依存の内生ラベル。

`Interpretation`
- P2 の「難易度正規化軸」は、まず外生で安定な軸を主軸に置くべき。  
- 単一ペア・`pop=40` では `session×vol=6` は疎化しやすい。Stage B（test 20日×fold）で 6分割すると1セル当たり取引数が薄くなりやすい。  
- よって主軸は `session 3`、`volatility` は archive metadata / 診断タグに留めるのが妥当。

`反証条件`
- session主軸で Stage C 精度が改善せず、vol主軸の方が一貫して高い。
- session主軸だと特定高難度局面（高vol）でのみ崩壊し、vol情報を主軸化しないと再現的に回避できない。

---

### 2. 反論2（lookahead）への回答

**最も危険な経路**
- `vol bucket` の閾値を「全期間分位点」で先に決める実装。
- centered window（`t-k ... t+k`）で realized vol を計算する実装。
- aux の publish lag を無視して regime を確定する実装。
- holdout/C の情報で B/C-lite の regime重みや閾値を再推定する実装。

**安全実装指針**
- regime_label は **per-bar で時点確定**: `label_t = f(info_<=t)`。
- session は `UTC hour -> bucket` の純関数で固定。
- vol は「過去のみ」EWMA/rolling で算出し、閾値は run開始時に固定（または fold train 内で固定して test に適用）。
- aux は `effective_from_utc` 契約を厳守。
- stage間で閾値再学習しない。特に C 情報を B/C-lite に逆流させない。

---

### 3. 反論3（適用 stage）への回答

**採用: (b) `Stage B + C-lite + Sieve`**

`理由`
- Stage A（60日）は窓が短く、regime分割すると1 regimeあたりの有効取引数が薄くなる。
- Stage B は fold集約で regime別統計を確保しやすい。
- C-lite は temporal 3窓と組み合わせて regime頑健性を測る本丸。
- Sieve は archive 側の難易度正規化に使える。

`反証条件`
- Stage A 非適用で A通過個体の質が悪化し、Bでの大量淘汰が常態化する。
- 逆に Stage A へ regime を入れても安定改善が出るなら (c) へ拡張再検討。

---

### 4. 反論4（spectral weight）への回答

**採用: support-aware（クリップ付き）**

固定 `[0.40, 0.35, 0.25]` は今回は不採用。

推奨式:
- `w_i_raw = n_i / Σ n_i`
- `w_i = clip(w_i_raw, 0.25, 0.45)` 後に再正規化

`理由`
- 主軸が session 3 でも欠損・休場・実取引密度で support はズレる。
- fixed重みは support が薄い regime を過大評価しやすい。
- ただし完全 support 比例だけだと難しい regime が埋もれるため、下限クリップを置く。

`反証条件`
- support-aware で難局面の検出力が落ち、Stage C で高vol崩壊が増える。
- その場合のみ小さな難度ブースト（例: +0.03〜0.05）を追加検討。

---

### 5. 反論5（regime_pass_pattern）への回答

**確定: P2 には入れない。archive diversity 軸で使用。**

- outcome-derived なので P2 に入れると循環（collider）を起こしやすい。
- 使い道は archive 選抜・warmstart 多様性制約のみ。

---

### 6. 反論6（cross-pair）への回答

**確定: validation axis + archive metadata**

- Stage C/AS で評価し、A/B/C-lite の selection objective には入れない。
- archive には `cross_pair_pass_tag` を保存し、warmstart 注入優先度に使うのは有効。

---

### 7. P2 Regime Taxonomy 確定表

| regime軸 | bucket数 | spectral weight | 適用stage | lookahead安全性 | sample size前提 |
|---|---:|---|---|---|---|
| `session_bucket` (Tokyo/London/NY) | 3 | support-aware clip `[0.25,0.45]` | B, C-lite, Sieve | 時刻のみで確定、漏洩しにくい | B全fold合算で各bucket `trade_count >= 15` 推奨 |
| `volatility_tag` (low/mid/high) | 3 | なし（P2主軸外） | B, C-lite, Sieve（metadata） | 過去窓のみ計算、centered禁止 | 各bucket `trade_count < 10` は `INCONCLUSIVE` 扱い |
| `aux_regime_tag` (risk-on/off等) | 2-3 | なし（将来拡張） | Sieve（metadata中心） | `effective_from_utc` 厳守 | 欠損率と遅延で実効サンプル確認が前提 |
| `period_bucket` (old/mid/recent) | 3 | なし（P2主軸外） | Sieve | 時系列分割固定で安全 | archive多様性評価用、A/B gateには使わない |
| `regime_pass_pattern` | 可変 | なし（P2禁止） | Archive/Warmstartのみ | outcome-derivedのためP2不可 | 多様性タグ用途のみ |
| `cross_pair_pass_tag` | 可変 | なし（validation軸） | C, AS, Archive metadata | Stage C評価後に付与 | warmstart優先度に利用可 |

---

この確定案での設計意図は、**P2を「外生で安定な難易度正規化」に限定し、内生・結果由来の軸は archive 側へ分離**することです。これで collider と lookahead の主要リスクを同時に潰せます。