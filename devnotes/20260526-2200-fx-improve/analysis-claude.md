# 分析 (cycle 24): 次フェーズ「構造的手段」— 32-primitive 戦略空間のギャップ特定

## 前提
閾値引き上げ+探索効率キャンペーン (cycle14-22) 完結。dd2% frontier 確定 (R101 723個体、ann med5.582/pnl med82k)。既存レバー (閾値/selection) 限界 → 構造的手段で達成分布の上限を上げる次フェーズ。

## 観察事実（Facts）
### 現 32-primitive 戦略空間の構成
- TREND_FOLLOW (12): F1 EMA / F2 MACD / F3 Donchian / F4 ADX / F5 VolatilityBreak / F6 SessionMomentum + pair_specific P1/P4/P7/P8/P9/P12。
- MEAN_REVERT (8): F7 RSI / F8 Bollinger / F9 Stoch / F10 ZScore / F11 Range + P2/P3/P5。
- NEUTRAL (3): F12 RealizedVolZScore / F13 ReturnAutocorrLag / F14 TrendStrengthRatio。
- MODULATOR (9): M1-M6 + P6/P10/P11 (ゲート/スケール)。
- データ: M1 OHLC (bid/ask)、EUR_JPY。出力 [-1,+1] bounded、recurrence で過去のみ参照、max_clause=2。

### キャンペーンが示した上限の兆候
- R104 nsga2 の Pareto tail で pnl max 108810 (R101 92360 超) = **戦略空間は高pnl個体を表現可能**だが median 探索が届きにくい。
- 達成分布: ann med5.582 で頭打ち、pnl med82k。dd は 2% で robust 飽和。

## 解釈・推論（Interpretations）
### 1. 古典テクニカル信号は概ね網羅、明確なギャップ候補
- **(a) マルチタイムフレーム合成**: 現 primitive は単一 bar 系列の指標。fast/slow TF 確認 (例 上位足トレンド × 下位足エントリ) は未実装。表現力拡張の有力候補。
- **(b) 日中シーズナリティ/時間帯**: F6 SessionMomentum のみ。時間帯条件 (Tokyo/London/NY セッション別の方向バイアス) を細かく扱う primitive は薄い。
- **(c) ボラティリティ regime 切替**: M 系ゲートはあるが、regime 明示分岐 (高vol/低vol で別ロジック) の表現は限定的。
- **(d) 価格-ボラ非線形** (例 keltner, supertrend, parabolic SAR 系) は未実装。
### 2. (B)新primitive vs (C)cross-pair の EV
- (C) cross-pair は cycle12 まで7連敗 + 本キャンペーン全run ii_lite=0、74k副作用でも holdout 逆相関。成功確度極低・過去の負の結果が重い。
- (B) 新primitive は表現力拡張で達成上限を上げうる唯一の構造的手。R104 tail が「空間は高pnl可能」を示唆 → 適切な新信号で median も押し上げる余地。bit-exact 維持 (opt-in) で安全。
### 3. リスク
新primitive は default挙動 bit-exact 維持 (OFF時完全一致) が必須。genome 表現・evaluator・テストへの影響を Codex impl-review で精査。成功確度は中 (Codex反証基準 mission+20% or pnl med+10k は高いバー)。

## 次サイクル候補
- **[Critical] Codex 戦略合議 (high)**: (B) 新primitive (どの信号ファミリー: マルチTF/シーズナリティ/regime/非線形トレンド) vs (C) cross-pair別framework を、EV・成功確度・実装コスト・過去の負の結果で1つに収束。(B)なら具体的 primitive 1 つを特定。
- 反証基準 (Codex既定): bit-exact維持・ON時3seedで mission_count+20% or pnl med+10k・dd2%/live_criteria維持・未達棄却。

## 全体判定
**次フェーズ=構造的手段の入口**: 32-primitive は古典信号を網羅、明確なギャップは (a)マルチTF (b)シーズナリティ (c)regime切替 (d)非線形トレンド。R104 tail が空間の高pnl余地を示唆 → (B)新primitiveが達成上限を上げる有力候補 (cross-pairは7連敗で EV 低)。Codex 戦略合議で (B) の具体 primitive or (C) を決定し、技術設計→impl-review→bit-exact実装→seed70反実仮想 full run へ。
