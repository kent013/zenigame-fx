# マージ分析: Run 27

**作成日時**: 2026-05-04 12:43 JST
**入力**: analysis-claude.md / analysis-codex.md
**全体判定**: 両者 CRITICAL_DRIFT 一致

## 合意事項 (両者一致)

| # | 合意点 | Claude | Codex |
|---|---|---|---|
| C1 | Stage A pass=0 全 640 個体 = 集団全壊滅 | F1 | Facts |
| C2 | best fitness_pen=-0.0079 で gen 11-15 停滞 | F2 | Facts |
| C3 | trade_count >= 1500 が 90% (構造的 over-trading) | F5 | Facts |
| C4 | trade_sharpe_raw 99.8% が <= 0.0 | F6 | Facts |
| C5 | active_clause=1 / n_nodes mean=2.4 (genome 表現力低) | F7 | Facts |
| C6 | archive_role / source_stage 全 NaN (= 観測異常あり) | F4 | Facts |
| C7 | single instrument (tier1_EUR_JPY のみ) | F3 | Facts |
| C8 | run-26 → run-27 で performance 劣化 | F9 | Facts |
| C9 | 全体判定 CRITICAL_DRIFT | 判定 | 判定 |

## Claude 独自の発見

| # | 発見 | 検証要否 |
|---|---|---|
| Cl1 | step 1.5-1.8 dual-path 配線が複雑化シグナル (禁止事項 #5) | 検証要 |
| Cl2 | sentinel value -1e9 (NO_EXPOSURE_FITNESS) 9 個体 | 観察済 |
| Cl3 | n_nodes が generation 進行で単調減少 (3.05 → 2.18) | 観察済 |

## Codex 独自の発見・指摘 (= Claude 修正点)

| # | 指摘 | 重要度 | C ルール |
|---|---|---|---|
| Cx1 | **Stage A 判定契約を最優先で監査せよ**: trade_sharpe_raw max=0.001134 が threshold=0 を上回るのに pass=0 = 判定指標の取り違え or 別ゲート存在の可能性 | Critical | C1 (design-first), C2 |
| Cx2 | 「archive NaN = 死にコード = loop_closure 不到達」 と即決は **C2 違反**。 評価系 vs 観測系の切り分けが先 | Warning | C2 |
| Cx3 | 「max_clause 拡張」 を即 Critical に置くのは **「仕組み未検証で値弄り」 思考原則違反** | Warning | 思考原則 |
| Cx4 | 「全個体 trade_sharpe_raw <= 0 で A 失敗」 は提示値 max=0.001134 と矛盾 (= 判定指標の取り違え/丸め/別ゲート) | Critical | C2 |
| Cx5 | run-26 → run-27 比較は pop/gen の差が大きく交絡を含む = 単純比較は危険 | Warning | C3 (collider/confounder) |
| Cx6 | 先人の知恵: Bailey et al. (2014) Probability of Backtest Overfitting / López de Prado (2018) Advances in FinML / Poli et al. (2008) GP Field Guide (= 早熟収束/表現力) | Reference | — |

## 矛盾・要議論

| # | 論点 | Claude | Codex | 判定 |
|---|---|---|---|---|
| M1 | I1 「集団 trade_sharpe_raw 上限ゼロは primitive 限界」 | 強支持 | 「一部支持だが確定不可、 まず判定契約監査」 | **Codex 採用** (= 判定契約を先に監査) |
| M2 | I2 「max_clause=1 は genome 表現力不足」 | 強支持 | 「現データだけでは過主張、 同一 seed 帯で AB テスト必要」 | **Codex 採用** (= 小幅 AB で検証) |
| M3 | I4 「archive NaN = loop_closure 死にコード」 | 強支持 | 「未確定、 切り分け監査が先」 | **Codex 採用** |
| M4 | I6 「dual-path 副作用」 | Concern | 「証拠不足 INCONCLUSIVE (C8)」 | **Codex 採用** (= INCONCLUSIVE 第一級) |

## 統合改善提案 (優先度順)

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | causal_path | falsification | success_criterion | 期待効果 |
|---|---|---|---|---|---|---|---|---|---|
| **P1** | **Stage A 判定契約の監査** (= 判定式・入力指標・失敗理由内訳・archive 出力の一致確認) | **Critical** | Codex Cx1, Cx4 | (前段) Stage A pass>0 の前提条件 | trade_sharpe_raw max=0.001 > threshold=0 なのに pass=0 | 判定式が trade_sharpe_raw 以外を見ている / 別ゲート存在 / 丸め誤差 | 監査で「判定式は正しい」 と確認できれば棄却 = primitive 仮説 (P3) へ進む | (a) 判定式の SSOT 文書化 (b) 個体毎 fail reason 集計が出る (c) archive 観測値と評価時値の一致 | 「評価系正しい」 を反証不能化 → 後続施策の前提固める |
| **P2** | **archive 伝搬漏れの切り分け監査** (= 評価時 in-memory metric vs parquet 出力の差分監査) | Warning | Codex Cx2 | (観測) archive_role / source_stage / sharpe / total_pnl が値を持つ | archive 列全 NaN | 観測経路 (archive write) のバグ or 評価経路 (loop_closure 不到達) | 評価時に値があれば「観測系バグ」、 評価時にもなければ「評価系バグ」 | 切り分け結果が log で確認可能 | 誤診防止 → 次サイクルで適切な fix を選択 |
| **P3** | **小幅 AB で表現力拡張** (max_clause 1→2 のみ、 max_depth 不変) | Warning | Codex 推薦 | (探索能力) trade_sharpe_raw max が右シフト | trade_sharpe_raw max=0.001 が天井 | 1 clause では複合 signal 不可 → 2 clause で intersection 可能 | AB で trade_sharpe_raw max 改善なければ棄却 | trade_sharpe_raw max > 0.005 が観測される | Stage A 通過率の因果を最小変更で確認 |
| **P4** | **cross-pair (ii-lite) 有効化準備** (= multi-instrument config) | Warning | Codex Cx, Claude I5 | (mission 最終条件) cross_pair_runtime_mode != skipped | single instrument のため cross-pair 評価不可 | tier1_EUR_JPY 単独 lane → cross-pair anchor 不在 | ただし Stage A 全滅では一次 ボトルネックではない | tier1 6 ペア展開後 cross_pair shadow が emit | mission の最終ブロッカー除去準備 (= 中期) |

**提案数**: 4 件、 Codex の優先順位推奨 (P1 > P2 > P3 > P4) を採用。

## 次フェーズへの申し送り

- B-2 改善策合議では **P1 を最優先で議論**、 P3 (max_clause 拡張) は P1 監査結果次第で gate 判断
- P4 cross-pair は中期、 今サイクルでは「準備のみ」 (= 実装ではなく config / lane 設計の review)
- P2 archive 伝搬漏れは P1 監査と同時実行可能 (= 並列、 同一監査セッション内で扱う)
- メタ過学習ガード: 全提案が「数値弄り」 ではなく「監査・切り分け・最小 AB」 = Reactive Parametric ではない
