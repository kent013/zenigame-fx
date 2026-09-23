1. **(B) vs (C) の収束**
- **採用: (B) 新 primitive 追加**。
- 理由（Fact）: cross-pair は cycle12 まで7連敗 + 今回キャンペーン全体でも `ii_lite_pass=0` 継続、74k副作用時も holdout 品質と逆相関。
- 理由（Interpretation）: (C) は目的関数・学習枠組みの再設計が必要で、現 mission（単一ペア holdout 品質向上）に対する EV が低すぎる。  
一方 (B) は frontier を維持したまま表現力を増やせるので、成功確度/実装コスト比で優位。

2. **(B) で最有力の信号ファミリー**
- **(a) マルチタイムフレーム合成**が最有力。
- 具体 primitive: **`F15 MTFTrendPullback`**（TREND_FOLLOW）。
- 根拠: 現32 primitiveは実質 single-TF（時間帯ゲートやvolゲートはあるが、上位足構造×下位足エントリがない）。  
  直交性が最も高く、ノイズの多い M1 で「方向（HTF）とタイミング（LTF）」を1 primitiveで同時に持てるため、**中央値改善**の期待値が高い。

3. **最小実装方針**
- **カテゴリ**: `TREND_FOLLOW`
- **再利用**: `_indicators.py` の `ema`, `atr`, `_EPS` を再利用（新規依存なし）。
- **新規最小 helper**: `M1 -> 完了済みHTF OHLC` 変換（未確定HTFバーは参照しない）。
- **計算**:
  - `trend = tanh((ema_htf_fast - ema_htf_slow)/(atr_htf + eps))`
  - `pullback = tanh((ema_ltf - close)/(k_entry*atr_ltf + eps))`
  - `align = max(0, trend * pullback)`
  - `out = trend * align`（`[-1,+1]`）
- **ParamSpec（最小）**:
  - `htf_min` (5..30, int)
  - `trend_fast_n` (2..12, int)
  - `trend_slow_n` (8..36, int)
  - `entry_n` (5..40, int)
  - `k_entry` (0.5..3.0, float)
- **bit-exact維持**:
  - `default OFF` の opt-in flag（例: `ga.experimental.mtf_trend_pullback_enabled=false`）
  - random_gen で当該IDを flag ON 時のみ母集団へ投入（OFF時は既存32本と同一挙動）。

4. **反証可能な R105 成功基準（frontier維持 + 上限向上）**
- 検証設計: **同一 seed 反実仮想**（control=OFF, treatment=ON）を2 seedで実施。
- **合格条件（全て必須）**:
  1. `mission_candidate_count_treat >= 0.85 * control`（両seed）
  2. `stage_c_pass_count_treat >= 0.85 * control`（両seed）
  3. pooledで `median(annualized_sharpe)` が `+0.20` 以上改善
  4. pooledで `median(total_pnl)` が `+5,000` 以上改善
  5. tail確認として `p90(total_pnl)` 改善（または `max_pnl > 108,810` 更新）
- いずれか未達なら **REJECTED**（INCONCLUSIVEを避けない）。

**全体判定: (B) を採用し、次の一手は `F15 MTFTrendPullback` を opt-in で最小実装して R105 反実仮想検証。**
---
## 実装チェックリスト (cycle24 → implement)
- [ ] directional_generic.py: F15 MTFTrendPullback 関数 + F15_SPEC (category=TREND_FOLLOW)。
- [ ] HTF resampling helper: M1→完了済みHTF OHLC (htf_min分足)。★look-ahead防止: 未確定HTFバー非参照 (現bar時刻が属するHTFバケットは前回確定値のみ使用、recurrence整合)。
- [ ] 計算: trend=tanh((ema_htf_fast-ema_htf_slow)/(atr_htf+eps)); pullback=tanh((ema_ltf-close)/(k_entry*atr_ltf+eps)); align=max(0,trend*pullback); out=trend*align ∈[-1,+1]。
- [ ] ParamSpec: htf_min(5..30,int)/trend_fast_n(2..12,int)/trend_slow_n(8..36,int)/entry_n(5..40,int)/k_entry(0.5..3.0,float)。_indicators.py ema/atr/_EPS 再利用。
- [ ] opt-in flag: ga.experimental.mtf_trend_pullback_enabled=false (default OFF)。random_gen は flag ON 時のみ F15 を母集団投入 → OFF で既存32本とbit-exact。
- [ ] テスト: (1)flag OFF で primitive 集合=既存32本(bit-exact)、(2)F15 計算の look-ahead なし(過去のみ参照、HTF未確定非参照)、(3)出力[-1,+1] bounded、(4)ParamSpec範囲。
- [ ] ★Codex impl-review (gpt-5.3-codex high): look-ahead bug (HTF resampling の最重要リスク)・recurrence整合・bit-exact・determinism を精査。
- [ ] commit (feat、末尾 Co-Authored-By)。
- [ ] R105 full run: pop96/gen60/EUR_JPY/dd2% frontier/seed70、flag ON (treatment) vs R101/seed70再現(control OFF)。さらに別seed(71)で control/treatment 各1本=2seed反実仮想。

## R105 成功基準 (Codex、全必須・未達でREJECTED)
1. mission_candidate_treat ≥ 0.85×control (両seed)。
2. stage_c_pass_treat ≥ 0.85×control (両seed)。
3. pooled median(ann sharpe) +0.20以上改善。
4. pooled median(total_pnl) +5000以上改善。
5. tail: p90(total_pnl)改善 or max_pnl>108810更新。
