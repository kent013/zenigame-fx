# マージ分析: cycle 2 (Run-28 → Run-29)

**作成日時**: 2026-05-04 14:35 JST
**前提**: analysis-claude.md / analysis-codex.md
**全体判定**: Claude=PROGRESSING / Codex=CONCERN (= CRITICAL_DRIFT 未到達、 #6 監視)

## 合意事項 (両者一致)

| # | 合意点 |
|---|---|
| C1 | Run-27 → Run-28 で Stage A pass 0 → 142 (= calibrate-gate threshold 改善が支配的) |
| C2 | Run-28 best=g11_i31 trade_count=48 < live_criteria.trade_count_min=50 (= mission 基準未達) |
| C3 | Stage A pass 142 個体の median trade_count=55 = 低 trade 寄り |
| C4 | 142 個体中 88% (125/142) が fold_trade_count_min=10 未満で Stage B fail |
| C5 | Stage A min_exposure_trade_count=1 と live_criteria.trade_count_min=50 のスケール乖離 |
| C6 | 禁止事項 #6 (= 取引回数削減で見かけ向上) の構造的萌芽あり |
| C7 | cycle 1 真の root cause = (Q) threshold 設計、 仮説 P1/P2/P3 全部外れ |

## Codex 独自の重要指摘 (= Claude 修正)

| # | 指摘 | C ルール |
|---|---|---|
| Cx1 | **I1 は有力だが単独根因ではない**: fold 不足は説明できるが fold 成立後の Sharpe/ratio 不足は別問題 | C9 反証可能性 |
| Cx2 | 禁止事項 #6 兆候は real 寄り (= INCONCLUSIVE)、 本物 signal 断定不可 | C8 |
| Cx3 | Stage B AND 条件は厳しいが、 現時点では「入力個体品質不足」 が主寄与 | C9 |
| Cx4 | H1 (= I1) 反証テスト: min_exposure=50 同期 → 予測「Stage A pass 急減、 fold 不足減、 ただし性能不足残存可能」 | C9 |
| Cx5 | cycle 2 は「高情報量の単一変更」 + 反証条件先固定 (= I1) | C4 / C9 |

## 統合改善提案 (= 1 つに絞る、 Codex Cx5 推薦)

### P1 (Critical, 単一変更): Stage A min_exposure_trade_count を 1 → live_criteria.trade_count_min (= 50) と同期

- **target_metric**: Stage B pass>0 の前提条件確立
- **failure_mode**: Stage A 通過個体 median trade_count=55 / fold 内 trade=7 < fold_trade_count_min=10 / 88% Stage B fail with `trade_count_below_min`
- **causal_path**: Stage A min_exposure=1 → low-trade individual 通過 → Stage B fold 内 trade 不足 → fail
- **falsification (= H1 反証テスト、 Codex Cx4)**:
  - 予測 (a): Stage A pass 数大幅減 (= 142 → ?)
  - 予測 (b): `trade_count_below_min` 大幅減 (= 125 → ?)
  - 反証条件: Stage A pass 急減 + fold 不足解消後も `median_oos_sharpe<min` が支配的 → H1 棄却 = root cause は signal 品質
- **success_criterion**:
  - Stage A pass 個体の median trade_count >= 50
  - `trade_count_below_min` 件数 < 10 (= 大幅減)
  - Stage B fail 理由が `trade_count_below_min` から `median_oos_sharpe<min` 主体へシフト (= signal 品質問題が露出)
- **変更分類**: **Structural** (= 整合性回復、 Reactive Parametric ではない、 live_criteria SSOT との同期)
- **補助監視**: low-trade cluster (trade_count 48-51) の fold 安定性 = 禁止事項 #6 早期検知 (= Codex Cx5)

### 却下 / 保留

- **Stage B 判定式の閾値緩和**: 設計通り AND condition、 緩和は禁止事項 #4 (= live_criteria 緩和の派生)
- **fold_trade_count_min=10 緩和**: T054 で「機能していた当時の挙動を意図的に再現する設計判断」 と記載、 緩和は SSOT 違反
- **primitive 改革**: post-run-review 担当 (= 当 cycle 範囲外、 中期キュー)
- **cycle 1 副次 bug** (= run_number 上書き / archive vs summary run_id ズレ): 別 TODO 切り出し、 当 cycle 主題ではない

## 反証条件 (= cycle 2 事前登録、 Codex Cx5)

Run-29 後に以下を確認:
1. Stage A pass 数 ≈ 142 → 5-30 (= 大幅減を予測、 もし ≈ 142 のまま = entry_count_min と min_exposure_trade_count の経路独立性 bug)
2. Stage A pass median trade_count >= 50 (= must)
3. fold `trade_count_below_min` 件数 < 10 (= 大幅減)
4. Stage B fail 理由分布: `trade_count_below_min` < `median_oos_sharpe<min`

これらが満たされなければ H1 棄却、 別仮説 (= signal 品質 / Stage B 厳しさ等) へ進む。

## 次フェーズへの申し送り

- B-2 で「単一変更 + 反証条件先固定」 を Codex に APPROVE 確認
- Phase C 詳細設計: config 1 行修正 (= `stage_gate.stage_a.min_exposure_trade_count: 1` → `50`) + テスト追加
- Phase 4 RUN: 完全同条件で再走、 reverse condition 観察
