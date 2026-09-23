1. 最適選択は **(D) frontier確定+総括** です。  
理由（期待値ベース）:
- mission整合: すでに North Star を大量達成（R101で723個体）。
- 期待効果: 追加改善の実証済み余地が小さい（dd2%以外は飽和/崩壊、nsga2は中央値退行）。
- コスト効率: 最小コストで再利用可能な知見を固定化できる。
- 成功確度: 最も高い（実績を文書化する作業）。

2. 現時点は **一区切り（D）優先** が妥当です。  
構造的手段（新primitive/cross-pair）は「次フェーズの研究テーマ」として分離すべきです。  
根拠:
- cross-pairは7連敗、nsga2は失敗で、直近の追加投資の期待値が低い。
- まず frontier を基準線として固定しないと、次の構造変更の因果評価が崩れます。

3. (D)でAGENTS.mdに残す最重要知見 top3
- **dd2%（max_drawdown_max=2%）だけが真に品質向上をもたらした閾値**（Stage C量・品質が同時改善）。
- **pnl閾値は70kがfrontier、74kで崩壊する pivotal 軸**（連続改善でなく相転移的）。
- **selectionはtournamentがmission優位、nsga2はtail改善のみで中央値を悪化**（採用不適）。

4. もし(A)/(B)を選ぶなら成功基準（反証可能）
- **(A) 探索効率変更**: 3 seed以上で、`mission_count +15%以上` かつ `ann median +0.3以上` かつ `pnl median +5,000以上`、さらに `mission_per_compute`（例: mission/1k eval）悪化5%以内。未達なら棄却。
- **(B) 新primitive追加**: default bit-exact維持（OFFで完全一致）を前提に、ON時3 seed以上で `mission_count +20%以上` または `pnl median +10,000以上` を再現。DD2%/live_criteria維持を必須。未達なら棄却。

**全体判定: (D) を実行し、dd2% frontier を公式基準として確定・総括する。**