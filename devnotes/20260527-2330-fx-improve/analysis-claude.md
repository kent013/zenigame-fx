# 分析 (cycle 27): 低DOF regime primitive は既存 M1/M2/M6 と冗長 — 総括最終化の検討

## 結論 (先出し)
Codex Round2 が「将来唯一の方向」とした **低自由度 regime 条件 primitive (時間帯/vol regime)** は、
**既存 default 32-primitive の M1/M2/M6 で大幅にカバー済**。frontier (R101=723個体) はこれらの regime
ゲートを持った状態で達成・収束しており、新規 regime primitive 追加の EV は低い。Codex 設計合議で
「真に直交な低DOF信号が残るか」を確認し、無ければ総括 D' を最終化する。

## 観察事実 (Facts): 既存 regime/time/vol primitive (全て default 32本に含、R101 で使用済)
- **M1 ATRRegimeGate** (MODULATOR, pure OHLC, 4 params): `sigmoid(±(atr/close - threshold)/scale)`。
  **vol regime ゲートそのもの** (高vol/低vol を prefer_high で選択)。
- **M2 SessionGate** (MODULATOR, pure OHLC, 2 params): Tokyo/London/NY セッション UTC hour ゲート
  + soft edge。**低DOF time-of-day ゲートそのもの**。
- **M6 TrendStrengthGate** (MODULATOR, pure OHLC, 3 params): ADX ベース trend regime ゲート。
- **F6 SessionMomentum** (TREND_FOLLOW, 3 params): セッション内モメンタム (time-of-day directional)。
- **F12 RealizedVolZScore** (NEUTRAL, 3 params): realized-vol z-score (vol metric)。
- M5 VIXRegimeGate は外部 VIX 依存 (本番でしばしば欠損→0.5 default)。

MODULATOR は乗算ゲート (composite.py: gate=Π gate_j, [0,1] bounded, dir_score×gate)。

## 解釈・推論 (Interpretations)
1. **regime 条件付けは既に表現可能**: vol regime=M1, session/time=M2, trend regime=M6。GA はこれらを
   genome に組み込む自由を持ち、pop96×gen60×warmstart で探索した結果が frontier 723個体。
   = 「regime ゲートを足せば holdout 改善」という仮説は、既にゲートがある以上、棄却寄り。
2. **F15 の教訓との整合**: F15(高DOF MTF)は holdout overfit。低DOF にすれば過学習容量は減るが、
   M1/M2 が示す通り低DOF regime ゲートは既存で、frontier はそれでも頭打ち。新規追加の限界効用は小。
3. **真に直交な低DOF 候補 (Explore 示唆)**: M7 ClosingPositionGate (close の daily range 内位置、1param)
   等は M1(vol level)と直交だが、これは regime でなく intrabar pressure 信号。Codex の「regime 条件」
   とは別物で、かつ単一弱信号が frontier を動かす見込みは更に低い。
4. **総括 D' との関係**: cycle24-26 で構造手段2方向 (F15/robust) が holdout 壁で否定。本 analyze は
   「Codex の残した最後の方向すら既存カバー」を示し、**frontier=頑健上限の結論を補強**する。

## 次サイクル候補 (Codex 設計合議で決定)
- (i) 真に直交な低DOF信号が1つ特定でき、frontier を動かす反証可能仮説が立つなら実装 (反証条件先固定:
  3seed, stage_c<687 or ann中央値<5.38 で REJECT, 成功=pnl74k達成2/3seed+ann非劣化)。
- (ii) 既存 M1/M2/M6 で regime カバー済・直交信号なし → **総括 D' 最終化** (構造手段全否定確定、
  frontier 最終固定、AGENTS.md に「regime も既存カバー」を追記)。

## 全体判定
**低DOF regime primitive は M1(vol)/M2(session)/M6(trend) で既にカバーされ、frontier はこれらを持って
収束した** = 新規 regime 追加の EV は低い。Codex 設計合議で「既存と直交し frontier を動かしうる低DOF信号」
の有無を確定し、無ければ総括 D' を最終化する (構造手段の探索を正式に閉じ、frontier を最終上限とする)。
