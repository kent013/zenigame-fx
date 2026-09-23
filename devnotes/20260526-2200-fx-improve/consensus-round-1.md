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