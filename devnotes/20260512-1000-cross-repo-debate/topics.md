# 論点まとめ: zenigame vs zenigame-fx 構造差分 と次の打ち手

## 背景

zenigame-fx で 18 RUN (Run 57-74、 cycle 4-21) を実施したが mission 達成 0/18。
3 agent 並行調査の結果、 zenigame 側との構造差分が明らかになった。

### 観測サマリー (zenigame-fx 18 RUN)

| 指標 | 範囲 | 達成率 |
|------|------|------:|
| best fp | 0.03 - 0.54 | - |
| best sharpe | 0.05 - 0.58 | 0/18 (vs ≥1.0) |
| best total_pnl | -48k - +36k | 0/18 (vs ≥50000) |
| best max_dd | 0% - 6.6% | 18/18 (vs ≤20%) |
| best trade_count | 30 - 75 | 5/18 (vs ≥50) |
| best Stage B pass | True or False | 12/18 (67%) |
| Stage C pass | 0 | 0/18 |
| DSR proxy pass | 0 | 0/18 (Bonferroni 5856 trials) |
| **mission (live_criteria 全達成 + Stage C pass + graduation>0)** | **0** | **0/18** |

### zenigame 側 実績 (Agent 3 報告)

- **mission 達成 RUN: 203 RUN** (Run 1340-1743 期間)
- **累計 amp (mission 達成個体): 250 体**
- Run 1597 最高: amp=27 体 (歴代最多)、 C-Sharpe 0.80 で達成

### zenigame と zenigame-fx の主要差分 (Agent 1 + 3 報告)

| 項目 | zenigame | zenigame-fx |
|------|---------|------------|
| 銘柄 | 複数銘柄 (CPPS+Forex) | EUR_JPY 単一 |
| population | 96 | 96 (= 同じ) |
| generations | 60 | 60 (= 同じ) |
| mutation_rate | 0.26 | 0.5 |
| elite_count | 5 | 2 |
| live_criteria.min_sharpe | 1.0 | 1.0 |
| live_criteria.min_net_return | **3.0% (相対)** | **50000 円 (絶対額)** |
| live_criteria.max_dd | -2.0% | 20% |
| live_criteria.min_trades | 50 | 50-5000 |
| **live_criteria.min_win_rate** | **0.55 (必須)** | **削除** |
| adaptive_mission_pass 列 | 有 (全窓 AND 認証) | **削除** (mission_inf_gap で代替) |
| Mission Shortfall fitness (T501-T506) | 有 (fitness_pen に mission_gap 組込) | **未移植** |
| Regime-aware penalty (T336) | 有 | **削除** |
| canonical_five engine | 無 | 有 (T061) |
| T540 sharpe annualization fix | **未** (broken) | 適用済 |
| cross_pair shadow | 無 | 有 (mode='shadow') |
| graduation_criteria.require_cross_pair_pass | - | true (ただし shadow mode で進出不能の懸念) |
| DSR audit (SessionBlock 駆動) | 配線済 | **scaffold 未配線** (T073) |
| n_fold<5 個体の Stage A pass | 不明 | **artifact 残存** (Run 60 best n_fold=4 で fp 0.54) |

---

## 論点 7 つ

### Q1. mission 定義の現実性

**現状**: zenigame-fx の live_criteria は sharpe≥1.0 / total_pnl≥50000円 (絶対額) / max_dd≤20% / trade_count≥50。
**観察**: 18 RUN で sharpe top=0.58、 total_pnl top=+36030。 1.0 まで **5 倍**、 50000 まで **40%**。
**zenigame 側**: min_net_return=3.0% (相対指標)。 50000 円絶対額は FX 円建て + イントラデイ条件で「過酷」設定の可能性。

**仮説**: 
- A) **live_criteria 絶対額→相対指標化** が必要 (禁止事項 4 抵触の可能性は要評価)
- B) sharpe>=1.0 は妥当、 ただし absolute PnL 要件が過酷で structural infeasible

**Codex への問い**:
- zenigame の min_net_return=3.0% を FX イントラデイに翻訳すると何になるべきか
- 50000 円絶対額は FX 純利益として妥当な mission 水準か、 それとも構造的に達成困難な値か
- 緩和は禁止事項 4 抵触か、 それとも「FX 固有制約への適切な翻訳」として正当化可能か

---

### Q2. adaptive_mission_pass 復活

**現状**: zenigame-fx で削除 (Phase 2 で mission_inf_gap + constraint_violation に置換)。
**zenigame 側**: archive 列の `adaptive_mission_pass`、 全窓 AND で「全評価窓で live_criteria 達成」を strict 認証。
**寄与**: zenigame で 250 体の amp 達成の認証基準として中核。

**仮説**: 
- mission_inf_gap は Pareto 序列化に有用だが、 「mission 達成個体」の **明確なラベル付け** が無くなった
- zenigame-fx archive に「mission pass」 boolean 列を復活させ、 GA selection で優先する

**Codex への問い**:
- mission_inf_gap を **保持しつつ** adaptive_mission_pass 相当 boolean 列を archive に追加するべきか
- Pareto 序列化 (現行 mission_inf_gap) と strict boolean 認証 (旧 adaptive_mission_pass) は両立すべきか

---

### Q3. min_win_rate (0.55) の復活

**現状**: zenigame-fx で削除、 mission_inf_gap は 4 指標 (sharpe, pnl, dd, tc) のみ。
**zenigame 側**: live_criteria.min_win_rate=0.55 (必須条件)、 robustness 担保の中核。
**寄与**: 「コスト後利益」の本質を担保 = lucky run なら 50%、 真に edge があれば >55%。

**仮説**:
- 18 RUN の best 個体の win_rate を archive から確認 (現在の sharpe high 個体が win_rate 低なら lucky draw)
- win_rate を live_criteria に追加すれば、 lucky draw の filter 強化
- ただし FX イントラデイで win_rate 0.55 達成が「コスト後」で現実的かは要検証

**Codex への問い**:
- FX イントラデイで spread/swap 控除後の win_rate 0.55 達成の歴史的可能性
- zenigame-fx live_criteria に min_win_rate を追加すべきか、 値は 0.50 か 0.55 か

---

### Q4. Mission Shortfall fitness 配線 (T501-T506)

**現状**: zenigame-fx で **未移植**。 fitness_pen は canonical_five + mission_signed_margin の lex 順。
**zenigame 側**: T501-T506 で fitness_pen に mission_gap (= mission 達成までの distance) を組込み、 mission 近接個体に選択圧。
**寄与**: zenigame で amp 達成加速の **直接寄与** (Run 1450-1597 期で達成数 急増)。

**仮説**:
- 現在 zenigame-fx は「Stage C pass を最優先、 mission 達成は副次」の selection
- T501-T506 を移植すれば、 GA が「mission gap 最小化」を direct objective として扱う
- 5856 個体試験で Bonferroni に届かない現状を打破できるか

**Codex への問い**:
- T501-T506 の zenigame-fx 移植は意味があるか
- 現行 mission_signed_margin との衝突 / 重複は無いか
- 「mission_gap を fitness に組込む」設計は zenigame-fx の Phase 2 selection logic と整合するか

---

### Q5. GA params 再校正 (mutation 0.5→0.26、 elite 2→5)

**現状**: zenigame-fx 直近 18 RUN は mutation_rate=0.5、 elite_count=2。
**zenigame 側**: mutation_rate=0.26、 elite_count=5 (5% of pop=96)。
**観測**: 18 RUN で unique fp ratio 9.5%-30% (elite collapse 悪化)。

**仮説**:
- mutation=0.5 (高) は exploration 偏重で良 genome の探索が散漫
- elite=2 (低) は GA dynamics で良 genome の保護が弱く、 次世代に伝播しない
- zenigame 設定に揃えると elite collapse 改善 + 良 genome の伝播強化

**Codex への問い**:
- mutation 0.26 + elite 5 への変更は妥当か (Reactive Parametric 抵触の懸念は無いか)
- これは「zenigame で機能している先人の値」として Principled Parametric として正当化可能か

---

### Q6. cross_pair shadow→hard 切替 OR graduation_criteria.require_cross_pair_pass=false

**現状**: cross_pair_runtime_mode='shadow' (Stage C pass 判定に影響しない、 archive 記録のみ)。
**Agent 1 仮説**: `graduation_criteria.require_cross_pair_pass=true` だが shadow mode で ii_lite_pass は記録のみ → **graduation pool 進出不能** の論理矛盾。
**観測**: 18 RUN すべて graduation=0 で一致 (この仮説と整合)。

**仮説**:
- A) cross_pair を hard mode に切替 (Phase 4 前倒し)
- B) graduation_criteria.require_cross_pair_pass=false (削除)
- C) require_cross_pair_pass は ii_lite_pass=True が出現したときのみ有効に、 NaN は素通り (現行が NaN なので素通り想定だが、 実装確認必要)

**Codex への問い**:
- 18 RUN graduation=0 は cross_pair shadow ロジックの矛盾起因か、 別の原因か
- どの選択肢が「禁止事項 5 (過剰複雑化)」に最も適合するか

---

### Q7. n_fold<5 個体の Stage A pass artifact (Run 60 best fp 0.54 問題)

**現状**: Run 60 best g34_i33 fp=0.5418 だが n_fold_effective=4 (wf_min_safe_folds=5 未満)。
**問題**: Stage B 評価が成立しないまま Stage A pass → archive に残り、 selection で best として浮上。
**観測**: live_criteria sharpe 0.58 (mission 接近) は **artifact** の可能性 (cycle 9 best-genome-comparison.md で報告済)。

**仮説**:
- Stage A gate に「n_fold_effective>=wf_min_safe_folds」 hard guard を追加
- これが無いと「偶発的に Stage B fold 不足の個体が高 fp 出してミスリード」する

**Codex への問い**:
- Stage A pass の hard guard 追加は妥当か、 これは「閾値緩和」ではなく「artifact 排除」として禁止事項抵触なし
- 既存 stage_gate.py のどこに追加すべきか (適切な位置の特定)

---

## 統合質問

**Q-Final**: 上記 Q1-Q7 のうち、 「次の cycle で取り組むべき優先度トップ 3」 を選び、 各々の implementation 複雑性 (低 / 中 / 高) と期待効果 (mission 達成への寄与: 低 / 中 / 高) を評価してほしい。

特に注目:
- ユーザー要求「20 RUN フルサイズで続けて」は 18 RUN まで完走 (Run 75 はユーザー停止)
- 今後は seed sweep 継続より **structural 施策** に転換すべきか
- 「先人の知恵」= zenigame で達成済の logic を逆移植する方が、 zenigame-fx で新規設計するより効果的か

---

## Codex 全体判定要求

- 次 cycle の Critical 施策 1 個 + Warning 施策 2 個
- 棄却すべき提案 (もしあれば)
- 「禁止事項 4 (閾値緩和)」 / 「禁止事項 5 (過剰複雑化)」抵触の懸念がある提案の指摘
