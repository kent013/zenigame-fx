# 最終改善計画: Run 28 → Run 29 (cycle 2)

**作成日時**: 2026-05-04 14:50 JST (Round 2 grep 後の修正版)
**合議ステータス**: **PARTIAL (Round 2 + grep で当初仮説が連続反証、 control rerun に切替)**
**前提**: analysis-merged.md / consensus-round-1.md / consensus-round-2.md
**北極星**: live_criteria 充足 FX イントラデイ戦略個体を 1 つ見つけ出す
**現在地**: Run-28 stage_a_pass=142, best fitness_pen=0.098

## エグゼクティブサマリー (= Phase B/C 直前で発生した仮説連続反証)

cycle 2 当初仮説 P1 (= Stage A min_exposure 1→50 で構造的不整合解消) は **2 段階で反証**:

1. **Round 2 反証 1**: T034 invariant `min_exposure < live_criteria.trade_count_min` (strict less than) で **50 への変更は ValueError 起動不能**。 設計意図 = 「Stage A で trade_count gate 化 = 禁止事項 #4 派生」 を回避するガード
2. **Round 2 反証 2** (= grep + summary 確認): summary.json の actual best = **g14_i29 trade_count=51 feasible=True** (= 既存 feasibility 圧は機能、 best は infeasible ではない)。 当初仮説の「infeasible 個体が elite で温存」 が反証

**真の root cause 候補** (= 反証条件 (c) が支持される観察):

- Stage A pass median trade_count=55 = `>= 50` だが、 fold 内 trade=7 (= fold_trade_count_min=10 未満) で 88% Stage B fail
- = **trade の時間分布が時間集中で fold 内不均一** (= signal が時期に偏在)
- これは config / GA selection の修正範囲外 = **primitive / signal の時間分布問題** (post-run-review 担当)

= cycle 2 改善策合議の結論: **Run-29 = control rerun (= 設定完全不変)** に切替

## 確定施策 (1 件、 control rerun)

| # | 施策名 | 内容 | 変更対象 | 優先度 | 変更分類 |
|---|---|---|---|---|---|
| **C1** | **control rerun + diagnostic 再適用** | Run-29 を **完全同条件** で実行 (= cycle 1 後の calibrate-gate threshold -0.0172 のみ適用)、 diagnostic を Run-29 archive に再適用、 cycle 1 と Run-29 の **結果安定性** を比較 | なし (= GA / config 完全不変) | Critical | **observational** (= 構造変更なし、 結果再現性確認) |

**target_metric**: Run-28 と Run-29 の Stage A pass 数 / best fitness_pen / fail 理由分布の安定性
**failure_mode**: Run-28 で観察された 88% `trade_count_below_min` が Run-29 で再現するか / 結果が大きくブレるか
**causal_path**: 同条件で再走 → 結果再現 = 観察された pattern が安定 / ブレ → run-by-run variance が支配的 (= seed の影響大)
**falsification**:
  - (a) Stage A pass 数が 142 と大きく異なる (= ±30 以上) → variance 問題、 seed 固定が必要
  - (b) `trade_count_below_min` が大幅減 (= 125 → < 50) → cycle 1 と Run-29 で異なる pattern = 再現性なし
  - (c) `median_oos_sharpe<min` が支配的に変化 → primitive 偶然性の影響
**success_criterion**:
  - Run-28 と Run-29 の Stage A pass / fail 理由分布が ±10% 範囲内
  - 真の cause = time-concentrated 取引 仮説の検証材料が揃う (= fold 別 trade 分布の集計強化)

## cycle 2 で得た重要な learning (= 北極星に向けた knowledge accumulation)

| # | learning | 影響 |
|---|---|---|
| L1 | T034 invariant ガードが正しく機能 (= min_exposure < live_criteria.trade_count_min strict) | 「config 1 行で解決」 という安易な手は防がれた |
| L2 | GA selection の feasibility 圧 (= entry_count_min=50) も正しく機能 | best=trade_count=51 feasible=True、 「infeasible 個体温存」 仮説は反証 |
| L3 | **真の Stage B failure cause = time-concentrated 取引 (反証条件 c)** | config / GA selection 修正範囲外、 primitive / signal の時間分布問題 |
| L4 | cycle 1 と cycle 2 で **連続して当初仮説が反証** | improvement loop の正しい運用 (= 仮説 → 反証 → 学習 → 次仮説) |
| L5 | cycle 2 では「単一変更」 を実装する前に grep + Read で仮説を反証完了 | 思考原則「仕組み未検証で値弄らず」 が働いた = Phase 4 RUN 前の design 段階で仮説を絞り込み |

## 却下 (= Round 2 後)

- **min_exposure 1 → 50**: T034 invariant で起動不能 (= ValueError)
- **invariant `<` → `<=`**: 禁止事項 #4 ガード破棄、 設計意図逸脱
- **min_exposure 1 → 49**: ガード回避の Reactive Parametric (Codex REJECT)
- **elite acceptance guard 追加** (Codex 案 C): grep + summary 確認で「既存 feasibility 圧は機能」 が判明、 前提反証
- **fold_trade_count_min 緩和**: T054 SSOT 違反

## 保留事項 (= cycle 3 以降)

| # | 仮説 | 最小変更案 | 検証条件 |
|---|---|---|---|
| H1 (cycle 3 候補) | time-concentrated 取引 仮説の検証 | Stage A pass 個体の **fold 別 trade 分布** を archive parquet で集計 (新規 diagnostic) | trade_count >= 50 でも fold 内 trade が不均一 (例: 1 fold に 30 trade、 残 4 fold に 5 trade) なら time-concentrated が真因 |
| H2 (cycle 3 候補) | primitive / signal 時間分布の改革 | post-run-review 担当 (= 当 cycle 範囲外) | H1 で time-concentrated が確認された場合 |
| H3 (cycle 4+) | Stage B 計算式 SSOT 監査 (= Codex Round 2 推奨) | C1 Design-first で Stage B 計算経路 / リーク 確認 | Run-29 結果次第 |
| H4 (中期) | cross-pair multi-instrument | 同前 | Stage C 通過後 |

## メタ過学習ガード適合性

| 項目 | 評価 |
|---|---|
| C1 (observational、 control rerun) | OK = 構造変更なし、 数値弄りなし |
| 取引回数削減で見栄え向上 (#6) | C1 で観察継続 (= low-trade cluster の fold 安定性監視) |
| 期間延長で過学習隠蔽 (#1) | N/A |
| live_criteria 緩和でステージ skip (#4) | **C1 は介入なしで完全適合** |
| 見栄え改善 (#2) | N/A |
| オーバーナイト前提 (#7) | N/A |
| archive スキーマ伝搬漏れ (#8) | 不変 |
| やたらに複雑な案 (#5) | **介入なし = 最小変更原則の極致** |

## 次フェーズへの申し送り

- Phase 2.5 calibrate-gate: Run-28 の Stage A pass=142/640=22% を target=15%±5% に対して評価、 in_band ならスキップ、 tighten ならさらに threshold を厳格化
- Phase 3 implement: **何も実装しない** (= control rerun)
- Phase 4 RUN-29: 完全同条件で再走
- Phase 5 run-report + diagnostic 再適用: Run-28 vs Run-29 の安定性比較
- Phase 6 cycle 3 への持ち越し: H1 (= fold 別 trade 分布 diagnostic) を新 diagnostic script として実装する流れ
