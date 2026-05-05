# マージ分析: Run 34 新 (cycle 1 後 RUN, run_id=run_20260505_043320)

cycle 2/10。 Codex の C4 前提是正を全面採用し、 Claude の H_c2_2 (cycle 1 副作用疑い) を棄却寄りに更新。

## 合意事項（両者一致）

| # | 観察 | 含意 |
|---|------|------|
| M1 | Stage B pass 群 (n=22) で total_pnl mean=-14,303、 trade_count mean=16.5 (Stage A 65.5 から急減) | Stage B が「品質保証」になっていない |
| M2 | T087 partition は新 schema で完全整合 (`bars_stage_b_excludes_stage_a: true`、 timestamp range disjoint) | cycle 1 C1 持ち越し問題は **解消済** |
| M3 | per_generation の 7/8 key が全 null (best_fitness_pen のみ記録) | W3 (持ち越し) 依然 broken |
| M4 | 禁止事項 6 (取引回数削減で見かけ改善) の構造抵触兆候あり | n=22<30 で因果断定不可 (C7)、 だが構造的 risk |

## **Claude の前提誤り → Codex により是正 (C4)**

| Claude 主張 (H_c2_2) | Codex 是正 |
|---|---|
| 「旧 R34 と新 R34 は同設定 deterministic 再現」 | **棄却**: bars_stage_b が **183403 (旧) → 97003 (新)** で Stage B 評価期間が違う、 同条件比較不可 |
| 「`all_folds_unavailable` 216→2248 (10倍増) は cycle 1 fix の副作用疑い」 | **棄却寄り**: partition 差分 (B 期間短縮) で WF fold 数が減ったのが主因。 n_fold_effective max が **旧 9 → 新 2** に低下 (B 期間 67 日に WF train=60d+test=10d の窓を当てると fold 1-2 個が構造的必然) |

→ Claude の C4 違反 (前提未検証) を Codex が指摘。 真因は **Stage B WF 窓設計と新 partition の構造的不整合**。

## Codex 独自の発見

| # | 観察 | Claude が見落とした要因 |
|---|------|---------------------|
| C1 | n_fold_effective 分布: 旧 max=9 (`{0,1,2,3,...,9}`) vs 新 max=2 (`{0:2248, 1:623, 2:58}`) | Claude は B 期間短縮で fold 数が減る構造を看過 |
| C2 | `wf_min_folds_required 2→4` 引き上げは現データ幾何 (max=2) で fail-closed 化、 偽陽性対策にならない | Claude H_c2_1 提案 ("min_folds 2→4") は **不適切**、 fold 生成可能性を先に契約化すべき |
| C3 | Stage B window 設計 (期間長 + WF 窓) を契約化していない → DB データ拡張時 / partition 変更時に fold 数が予測不能 | 設計レベルの欠落 |
| C4 | reason code がセミコロン連結文字列 (例: `median_oos_sharpe<min;positive_fold_ratio<min;all_folds_unavailable`) で primary/any 集計の解釈齟齬を生みやすい | 集計ロジックの曖昧さ |
| C5 | Stage B pass 偽陽性の selection_score を全世代で実測すれば歪みの有無が verify 可能 | 量的検証手順 |

## 矛盾・要議論

| # | Claude | Codex | 結論 |
|---|---|---|---|
| D1 | H_c2_2 (cycle 1 副作用疑い) | partition 差分主因 (棄却寄り) | **Codex 採用**。 真因切り分けは「同 partition で fix 有無の A/B」 のみで verify 可能 (実用上は不要、 partition 差分主因が圧倒的に確からしい) |
| D2 | wf_min_folds_required 2→4 (H_c2_1 minimum 変更案) | 現データ幾何で fail-closed 化、 不適切 | **Codex 採用**。 fold 生成可能性 (B 期間 + WF 窓) の契約化が先 |

## 統合改善提案 (cycle 2 候補、 Codex 提示を中核に)

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | causal_path | falsification | success_criterion |
|---|------|--------|------|--------------|-------------|-----------|--------------|------------------|
| **P1** | **Stage B WF 窓設計の契約化** | **Critical** | Codex C2/C3 + Claude H_c2_1 修正 | Stage B fold 生成可能性 | B 期間 97003 bars (67 日) に WF train=60d+test=10d を当てると fold max=2 が構造的必然、 wf_min_folds_required 引き上げは fail-closed 化 | partition (T087) と WF 窓 (`wf_train_days / wf_test_days / wf_step_days / wf_min_folds_required`) の幾何的整合が契約化されていない | 契約化 (例: 「B 期間 ≥ wf_train + (wf_min_folds-1)*wf_step + wf_test」 の guard 追加) を実装し、 データ不足時に fail-closed 化、 充足時に WF 設計を健全化 (train/test 短縮 or B 期間拡張 or step 縮小) | 契約 guard が実装され、 現データ (B=97003 bars) で fold 数 ≥ 5 が達成 (wf_train=20d+test=5d+step=5d 程度に短縮) |
| **P2** | **Stage B pass 品質監査 (trade_count 層別)** | **Warning** | Codex Warning + Claude H_c2_3 | Stage B 偽陽性検出 | Stage B pass 群 trade_count mean=16.5 (Stage A の 4 分の 1)、 total_pnl mean=-14,303 | fold が成立した稀な小サンプル個体が positive_fold_ratio=1.000 で偽陽性 pass | trade_count 層別 (10-20 / 20-40 / 40+) で Stage B pass 優位が消えなければ「回数削減主因」棄却 | 層別後 「trade_count 40+ 帯で Stage B pass の total_pnl mean が positive」 確認、 もしくは構造改善で偽陽性減少 |
| **P3** | selection_score_schema 感度分析 | Warning | Codex Warning + Claude H_c2_3 | best 選定の歪み防止 | `v3_1_stage_b_priority` で stage_b_pass が tuple 上位かつ重複キーで偏重 | Stage B 偽陽性が増えると selection 圧が偽陽性に偏る | 偽陽性 22 件 (n=22<30) と Stage A 単独 pass 群の selection score を実測し、 上位占有が起きないか確認 | 偽陽性が上位占有しない or schema 改善案を文書化 |
| **P4** | per_generation observability schema 拡張 (W3 持ち越し) | Warning | 両者 | 観測性 | 7/8 key 全 null (best_fitness_raw / median_fitness_pen / stage_X_pass_count / population_diversity) | recording 経路で writer に値を渡していない、 or schema に存在しない | schema 確認 + 必要なら計測経路追加 (計測ロジックは不変) | per_generation null 率 < 10% (現状 100%) |
| **P5** | reason_code 集計正規化 | Suggestion | Codex C4 | 集計透明性 | `stage_b_reason_codes` がセミコロン連結文字列で primary/any 解釈齟齬 | parse 経路が複数ある可能性 | reason_code を構造化 (list of enum) で記録、 集計関数を SSoT 化 | 単一の集計関数で primary/any 両方が一意に取得可能 |

## 全体判定

**CRITICAL_DRIFT** (Codex 判定継承)

根拠: Stage B WF 窓と新 partition の不整合 (P1) は構造的設計欠陥で、 これが解消されない限り Stage B 偽陽性 (P2) も改善しない。 cycle 2 では P1 を **Critical 1** として最優先、 P2-P5 は Warning。

## 滞留 TODO 判断

Open / Conditional 共に 0 件、 棚卸し対象なし。

## Conditional 昇格チェック

Conditional 0 件、 評価対象なし。
