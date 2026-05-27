# 分析 (cycle 26): 構造手段(B)=MTF の有効な反証 → 次レバー Codex 合議

## 結論 (先出し)
構造手段(B) 新primitive の最有力候補 F15 MTFTrendPullback を **registry バグ修正後に正しく評価**し、
有意に **REJECTED**。失敗様式は「in-sample/fold で勝つが holdout で全滅 (overfit)」。これは閾値引き上げ
(pnl74k 崩壊)・cross-pair (ii_lite=0) と **同一の holdout 非汎化の壁**。次レバーを Codex 合議で決める。

## 観察事実 (Facts)
### R106 (F15 treatment、実評価、seed70) vs R101 control (F15 OFF)
- stage_c_pass: **534** (control 723) — F15 探索が予算浪費し収量低下。
- median ann sharpe: **5.1995** (control 5.5818) — 退行。
- median total_pnl: **78990** (control 82150) — 退行。
- F15 含み genome: 248 行生成・実評価 (KeyError=0)。Stage A pass **76** / Stage B pass **41** /
  Stage C pass **0**。
- tail p90 95320 (>control 91020) だが単一 genome の 55重クローンによる見かけ (warmstart 低多様性)。
- Codex 5 条件: 1,2,3,4 FAIL、5 は artifact。→ REJECTED。

### R105 は INVALID だった (前cycle訂正)
- spawn worker registry に register_experimental() 不伝播 → F15 genome 全て Stage A KeyError 全滅。
- 修正済 (parallel_eval._init_worker enable_experimental, OFF bit-exact, 171 tests pass)。

## 解釈・推論 (Interpretations)
1. **ボトルネックは in-sample 表現力ではなく holdout 汎化**。F15 は表現力を足し、Stage A(76)・
   fold-CV Stage B(41) を通過させた = 「より複雑な当てはめ」は作れる。だが Stage C(60日holdout) 通過 0
   = その edge は未来データに残らない。MTF trend-pullback は過学習装置として働いた。
2. **同一の壁の再確認**: pnl74k(in-sample利益↑も holdout崩壊)、cross-pair(汎化0)、F15(holdout0)。
   いずれも「探索力不足」ではなく「EUR_JPY M1 intraday + この期間の汎化限界」を示唆。
3. **確定 frontier (sharpe1.5/pnl70k/dd2%/trade50) ~723個体 @ ann5.58/pnl82k は頑健な達成上限**
   である可能性が高い。表現力拡張 (別 primitive family b/c/d) も同じ holdout 壁に当たる公算大。
4. ただし F15 は「MTF」という単一仮説の否定。family b(時間帯)/c(vol regime)/d(非線形トレンド) は
   直交仮説であり、holdout 汎化する可能性はゼロではない。EV は低下したが完全には潰れていない。

## 次サイクル候補 (Codex 合議で決定)
- (B') 別 primitive family を1つ試す: b 日中時間帯 / c vol regime 明示分岐 / d 非線形トレンド。
  F15 と同じ holdout 壁のリスク高。だが直交仮説なら汎化余地あり。
- (C) cross-pair 汎化 framework: 8+ 連敗、EV 極低。
- (D) 総括: 構造-primitive 路線を一旦結論 (holdout 汎化が真の壁) し、frontier を頑健上限として文書化、
  別の改善軸 (例: 既存 frontier 個体の anti-overfit 選択, holdout 直接最適化の是非, データ期間外要因) を提起。

## 全体判定
**F15(MTF) は holdout 非汎化で REJECTED (valid)**。構造-primitive(B) の最有力が落ちたことで、
失敗様式が「holdout 汎化の壁」に収斂。次レバーは Codex 合議で (B' 別family / C cross-pair / D 総括) を
EV・holdout汎化見込み・過去の負の結果で1つに収束させ、決定する。
