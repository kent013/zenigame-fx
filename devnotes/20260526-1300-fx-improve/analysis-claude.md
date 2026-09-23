# 分析 (cycle 22): 閾値引き上げキャンペーン (cycle12-21) 総括 → 次の本質的レバー

## ★ 閾値引き上げキャンペーン全結果 (cycle12-21、R94-R103、10 full run)
| 軸 | 探索 | 結論 | 種別 |
|----|------|------|------|
| sharpe_min | 1.0→1.5 | 達成 ann med5.2-5.6 >> 1.5、形式的 | hollow |
| total_pnl_min | 50k→70k→74k | 70k=3seed frontier、74k=in-loop崩壊(holdout犠牲) | frontier+崩壊 |
| max_drawdown_max | 20%→5%→3%→2%→1.5% | **dd2%が真の品質向上(StageC634→723/ann5.205→5.582)**、dd1.5%over-tighten | **唯一の実質向上軸** |
| trade_count_min | 50→100→50 | 100=構造的到達不能(R94 StageC0)、50 floor最適 | floor |
| profit_safe_pfr | 0.4→0.55→0.4 | 0.55はholdout非連動(pnl/ann微減)、打ち切り | 非連動 |

## ★ 確立した知見
1. **閾値の pivotal 性で in-loop 挙動が決まる**: pnl(74k)=pivotal→holdout犠牲崩壊、dd2%=pivotal→holdout改善、dd5%/3%=non-pivotal(ビット同一hollow)、fold一貫性=非連動。
2. **post-hoc sweep は pivotal 閾値で無効** (74k教訓、dd2%でも実証)。in-loop 反実仮想 (同一seed) のみ妥当。
3. **dd2% が唯一の真の品質向上引き上げ**。低dd選抜圧がrobust個体を促進する好循環。他軸は飽和/崩壊/非連動。
4. **確定 frontier**: sharpe1.5/pnl70k/dd2%/trade50/pfr0.4。R101(dd2%)で723個体達成 (holdout ann med5.582/pnl med82k/dd全<2%)。North Star (live_criteria全達成個体) を robust に多数達成。

## 解釈・推論（Interpretations）
既存の全閾値軸 (live_criteria 4軸 + fold一貫性) の引き上げ余地は出尽くした。North Star の継続的「閾値引き上げ」は、現フレーム (32-primitive・EUR_JPY・固定探索) では dd2% を最後に限界。さらなる品質向上には**フレーム自体の拡張**が必要:
- (A) **探索効率改善**: warmstart/pop/gen/NSGA2 等で達成分布をさらに上へ押し上げ → 上がれば将来の gate 引き上げ余地再生。
- (B) **新 primitive 追加**: 32-primitive 戦略空間を拡張 → 表現力向上で高pnl or cross-pair 汎化の可能性。大コスト・Codex設計レビュー必須。
- (C) **cross-pair 汎化 別framework**: 7サイクル未達 (ii_lite=0) の本丸。graduation 要件。最も野心的だが過去の負の結果が重い。
- (D) **frontier 確定+総括**: dd2% frontier を最終成果とし、キャンペーンを文書化。

## 次サイクル候補
- **[Critical] Codex 戦略合議 (high)**: (A)-(D) を mission整合・期待効果・コスト・過去の負の結果で1つに収束。「既存閾値飽和後、North Star (品質向上) をフレーム拡張で継続するか、frontier確定するか」。
- 運用ルール (確立済): 閾値引き上げ採用は独立2seed以上再現 + in-loop検証 (post-hoc禁止)。

## 全体判定
**閾値引き上げキャンペーン収束 (重要マイルストーン)**: cycle12-21 で全閾値軸を in-loop 特性把握、dd2% が唯一の真の品質向上引き上げ。frontier (sharpe1.5/pnl70k/dd2%/trade50) で723個体の robust 達成。既存軸は飽和 → North Star 継続にはフレーム拡張 (探索効率/新primitive/cross-pair) が必要。Codex 戦略合議で次の本質的レバーを決定。
