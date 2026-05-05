# 最終改善計画: Run 34 (新) → Run 35 (cycle 2 / 10)

## 合議ステータス: CONSENSUS REACHED (Round 1)

cycle 1 で C2 H1/M1 verified (archive total_pnl 0→40140)。 cycle 2 で同設定 RUN 結果から Stage B WF 窓と新 partition の構造的不整合 (CRITICAL_DRIFT) を発見。 Round 1 で APPROVED 取得。

## 反証可能仮説 H_c2

「Stage B 偽陽性 (pass 群 total_pnl mean=-14,303、 trade_count 急減) の主因は WF 窓 (`wf_train_days=60 / wf_test_days=10 / wf_step_days=10 / wf_min_folds_required=2`) が新 partition (B 期間 97003 bars≈67日 disjoint) の幾何制約と整合せず、 fold max=2 で小サンプル偽陽性が量産されているため」

**falsification**: WF 窓を fold>=5 を満たす最小セット (例: train=20d/test=5d/step=5d) に変更し、 同 RUN で:
- Stage B pass 群の total_pnl mean が non-negative になる → 仮説 verify
- 依然 negative なら別経路 (selection_score_schema, fold_trade_count_min, primitive 設計等) が真因 → cycle 3 で深掘り

## 確定施策一覧

| # | 施策 | 内容 | 変更対象 | 優先度 | 分類 | target_metric | 合議結果 |
|---|------|------|---------|--------|------|--------------|---------|
| **P1-1** | Stage B window 契約 guard | `validate_stage_b_window` 関数追加。 B 期間 ≥ wf_train + (wf_min_folds-1)*wf_step + wf_test + wf_embargo の幾何整合を検証、 不整合なら RuntimeError fail-closed | `src/alpha_factory/stage_partition_guard.py` (or `stage_b_evaluator.py`) + 起動 log で「必要最小 bars / 実 bars / 算出 fold」明示 | Critical | Structural | Stage B fold 生成可能性 | Round 1 APPROVE |
| **P1-2** | WF 窓の幾何整合化 | `config/alpha_factory/default.yaml` の `stage_b.wf_train_days / wf_test_days / wf_step_days` を「現データ B=97003 bars で fold>=5 を満たす最小セット」に変更。 実データで算出して確定 (例: train=20d/test=5d/step=5d を出発点) | `config/alpha_factory/default.yaml` | Critical | Principled Parametric | Stage B fold 生成可能性 | Round 1 APPROVE |
| **P4** | per_generation observability 補修 | 7/8 key (best_fitness_raw / median_fitness_pen / stage_X_pass_count / population_diversity) の null 原因を経路別に特定、 計測値は既存再利用で writer 経路を補修。 計測ロジック不変。 null 率 < 10% を達成 | summary writer 経路 (`scripts/alpha_factory/run_ga.py` の per_generation 構築部) | Warning | Structural | 観測性 | Round 1 APPROVE |
| **P2 (分析のみ)** | Stage B pass 品質の trade_count 層別監査 | trade_count 層別 (10-20 / 20-40 / 40+) で Stage B pass 優位が再現するか分析。 効果量 (中央値差、 符号率) を併記、 mean 単独評価避ける。 INCONCLUSIVE 許容 (n=22<30) | 分析 script + analysis 出力 (devnotes 内) | Warning | Structural (分析ガード) | Stage B 偽陽性検出 | Round 1 MODIFY APPROVE |

## 却下された提案

| # | 提案 | 却下理由 |
|---|------|---------|
| P5 | reason_code 集計正規化 | cycle 2 の最小変更原則に対してスコープ超過、 cycle 3 以降の可観測性改善バッチに統合 |

## 保留事項 (次サイクル検証申し送り)

| # | 仮説 | 最小変更案 | 検証条件 |
|---|------|----------|---------|
| P3 | selection_score_schema (`v3_1_stage_b_priority`) が Stage B 偽陽性増加時に best 選定を歪める | schema 改変 (例: 偽陽性ガード追加) | cycle 2 の P3 (上位占有率の実測監査) 結果次第。 偽陽性が上位占有しない or 構造改善で偽陽性減少なら schema 改変不要 |
| P3 (持ち越し) cycle 1 | C1: T087 partition 監査 | (新 schema で **解消済**) | cycle 2 で確認済 (`bars_stage_b_excludes_stage_a: true` + timestamp range disjoint) |
| W3 (持ち越し) cycle 1 | per_generation observability schema 拡張 | (cycle 2 P4 で実装) | cycle 2 で実装 |
| P3 (cycle 1) | Stage A 選別力厳格化 | `stage_a.threshold` 単独変更 | cycle 1 fix verify 後の cycle 2 で再判定 → **保留継続**: cycle 2 では Stage B 構造問題 (P1) が優先、 Stage A は selectivity が現状で機能している (Stage A pass 群 mean PnL +17,013 positive) |
| P4 (cycle 1) | max_clause=2 A/B | max_clause=2 の対照 RUN 1 件 | cycle 3 以降、 P1 評価後 |
| P5 (cycle 1) | cross-pair shadow multi-instrument | multi 2-3 pair RUN | cycle 3 以降 |

## 次フェーズへの申し送り (Phase C 詳細設計)

- **TODO 由来施策なし** (Open/Conditional 0 件) → Phase C-0 はスキップ
- **P1-1**: 既存 `stage_partition_guard.py` を拡張 or 新規 guard モジュール追加。 既存テスト走破必須
- **P1-2**: yaml 値変更 + 既存テスト走破 (どこで read されているか確認)
- **P4**: `run_ga.py` の per_generation 構築箇所を read で経路特定
- **P2 (分析のみ)**: `devnotes/20260505-1529-fx-improve-c2/audit_*.py` で archive を読んで層別

## 使命チェック

| 禁止事項 | 抵触有無 | 根拠 |
|---|---|---|
| 1. 評価期間延長 | なし | partition 不変、 WF 窓は B 期間内で再分配 |
| 2. 見た目数値改善 | なし | 構造的修正、 cycle 1 fix で真値が見えるようになった上での次の構造修正 |
| 3. GA ハック | なし | GA 設定 (population/generations/mutation) 不変 |
| 4. 閾値緩和でステージ飛ばし | **要注意** | WF 窓短縮 (train=60d→20d 等) は「より短期で評価」 = 緩和の側面あり。 ただし「fold>=5 を満たす最小変更」 という Principled 根拠あり、 「数値をよくしようとする緩和」 ではない |
| 5. 複雑案 | なし | guard 1 関数 + yaml 変更 + per_generation 修正 + 分析 1 本 (4 件) |
| 6. 取引回数削減で見かけ改善 | **対策側** | 本施策は「取引回数削減個体が偽陽性 pass する構造」 を修正する |
| 7. オーバーナイト保有前提 | なし | 戦略不変 |

→ 4. の「WF 窓短縮 = 緩和」 は注意要。 Principled Parametric として **B 期間幾何制約から algebraic に算出される最小値** で、 「閾値を緩めて pass 数を増やす」 とは異なる。 detailed-design で明示。
