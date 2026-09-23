# RUN run_20260521_061439 (Run 87) 分析（Claude 自己分析）

## 前提差分
なし。R87 は T114 cross-pair enable + warmstart(0.1, motif=R86) + seed=68 の検証 run。

## 観察事実（Facts）

### T114 cross-pair enable の動作確認（cycle 5 の主眼、成功）
- cross_pair_runtime_mode = **enabled**（anchors = EUR_USD + USD_JPY、n_pairs=3）。
- ii_lite_pass が None→bool 化: 全体 {None:3886, False:1970}、Stage B 通過群は全件 False に評価された（cross-pair が実走）。

### ★ 汎化定量化（cycle 6 の核心）
R87 Stage A/B/C = 2495/1970/**599**。Stage C 通過 599 個体の cross-pair:
| 指標 | 値 |
|------|-----|
| ii_lite_pass=True（cross-pair 汎化） | **0 / 599** |
| graduation | **0** |
| mission_signed_margin_c_shadow | **中央値 -1.367**、min -15.622、max 0.919、**正は 4/599 のみ** |
| mission_signed_margin_b_shadow | 中央値 -3.147（Stage B 期間ではさらに悪い） |

→ EUR_JPY の mission/Stage-C 個体は **0% が cross-pair 汎化**。しかも margin は限界的失敗（≈0）でなく **深い負（中央値 -1.37）** = 強い in-sample 過学習。

## 解釈・推論（Interpretations）

### 1. mission 個体は EUR_JPY 特化の過学習で、汎化フロンティアは未踏（決定的確証）
4-5 サイクルで mission を 達成可能(R83)+cost-robust(R85)+再現可能(R86) にしたが、R87 で **多ペア汎化は 0/599** と確定。warmstart は in-sample winner を増幅するだけで汎化に寄与しない（設計時に明記済の通り）。margin median -1.37 は「あと少しで通る」でなく「全く通らない」水準。
- 反証可能性: 汎化施策後に ii_lite_pass=True が 1 個体でも出れば前進。0 のままなら施策が効いていない。

### 2. 根本原因: GA fitness/selection に汎化への選択圧がゼロ
- 現 fitness_pen = EUR_JPY in-sample sharpe − α·size。GA は EUR_JPY 単一ペアの in-sample 成績のみで選択 → 純粋な in-sample winner に収束。
- cross-pair は **最終 Stage C でしか評価されない**（GA ループ内に汎化シグナルが入らない）。∴ GA は汎化方向に一切探索圧を受けない。
- これは「機能の名前に立ち返れ」: graduation = 多ペア汎化ゲートだが、GA はそのゲートを意識せず探索している。

### 3. 汎化を促す構造介入が次の施策（cycle 6 の方向）
GA に汎化シグナルを与える必要がある。候補:
- **(a) multi-pair training**: fitness を複数ペアの成績で評価（構造的・本質的だが大規模・メモリ/速度大。R87 は cross-pair 最終評価だけで ~7h）。
- **(b) cross-pair を in-loop selection pressure 化**: GA 選択キー or fitness に cross-pair 結果を反映（最終 gate でなく探索中に汎化を促す。中規模だが cross-pair eval ×3 を毎世代は高コスト → 間引き/近似が要点）。
- **(c) overfit penalty**: in-sample 特化を fitness で抑制（安価な汎化 proxy が必要。cross-pair eval が高コストなので proxy 設計が鍵）。

### 4. 禁止事項違反の兆候
なし。汎化施策は評価の厳格化（緩和でない）。閾値引き上げは汎化達成後。

## 次サイクル候補
- **[Critical] 汎化を促す GA 構造介入**: (b) cross-pair in-loop selection pressure を軸に、コスト対策（間引き世代・top-N のみ cross-pair eval・近似 proxy）込みで設計。低リスク段階導入（default OFF、まず弱い圧から）。
- **[Warning] (a) multi-pair training**: より本質的だが大規模。コスト次第で将来。
- **[Warning] (c) overfit penalty proxy**: 安価な汎化 proxy（例: regime/sub-period 分割の成績分散）を fitness に。cross-pair eval なしで近似できれば低コスト。

## 全体判定
**OK（T114 成功、汎化フロンティアを定量化）** — mission は in-sample で 達成可能+cost-robust+再現可能 だが cross-pair 汎化 0/599（margin median -1.37 = 深い過学習）。次は GA に汎化への選択圧を与える構造介入（cross-pair in-loop pressure / multi-pair training / overfit penalty proxy）を低リスク段階導入で。コスト（cross-pair eval ×3 は高い）が設計の主制約。
