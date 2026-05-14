# 最終改善計画: Run 75 → Run 76 (cycle 23)

## 合議ステータス: CONSENSUS REACHED (Round 1)

## 確定施策一覧

| # | 施策名 | 内容 | 変更対象 | 優先度 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion | 合議結果 |
|---|--------|------|---------|--------|---------|--------------|-------------|------------|---------------|-------------------|---------|
| **C1** | **🚨 live_criteria.sharpe 単位整合性修正 (annualize + trade_sharpe_stage_c 優先)** | `_check_live_criteria` に `holdout_days` 引数追加、 比較値は `trade_sharpe_stage_c` 第一優先 (無ければ `trade_sharpe_raw` fallback)、 `_annualize_trade_sharpe` で年率化、 `value` は annualized、 `value_trade_level` 併記、 `sharpe_calc_version` 更新 | `scripts/alpha_factory/run_ga.py:916` `_check_live_criteria` + caller / tests | **Critical** | **Structural** (bug fix + 正規化) | live_criteria.sharpe.pass / live_criteria.all_pass / mission達成個体数 | trade-level vs annualized 1.0 単位不整合で sharpe pass=False に固定 (= 構造的 bug)、 Stage A スコープの `trade_sharpe_raw` を Stage C 判定に流用 | 比較が誤単位で固定 False → all_pass False → mission 達成 0 | 修正後 Run 76 best 個体で sharpe 判定が継続 False なら別仮説 (Stage C で真に sharpe 低い) | Run 76 best 個体で sharpe pass=True、 過去 19 RUN 再評価で mission 達成個体多数発見 | APPROVED Round 1 |
| **C2** | **graduation KPI 分離 (stage_c_pass_count + mission_candidate_count 表示)** | `generate_run_report.py` で `## 使命判定` セクションに 3 KPI 並列表示: (a) graduation_count (現状仕様、 cross_pair AND)、 (b) stage_c_pass_count (Stage C 単独通過)、 (c) mission_candidate_count (live_criteria.all_pass、 = C1 修正後の真値) | `scripts/alpha_factory/generate_run_report.py` / tests | Warning | Documenting | KPI 誤読率 (= graduation=0 を mission=0 と誤読する判断ミス) | single-instrument 運用では graduation 構造的 0 で KPI 誤読 | graduation=0 を「mission=0」と誤認 | KPI 分離後も判断改善しない | run report で 3 KPI が分離表示される、 mission_candidate_count が真の mission 達成個体数を反映 | APPROVED Round 1 |
| **C3** | **過去 19 RUN (Run 57-75) live_criteria retroactive 再評価 script** | 新規 script `scripts/alpha_factory/audit_live_criteria_retroactive.py` で archive Parquet を再評価し annualized sharpe で live_criteria.all_pass 個体数を集計、 reports/audit-live-criteria-retroactive.md 生成 | 新規 script / 既存 archive 読み取り | Warning | Audit script (no behavior change) | 過去 19 RUN の真の mission 達成個体数 | 18 RUN 累積 mission 0/19 が bug 由来の過小評価 (= 単位不整合) | 再評価で真値を取得 | 再評価しても全 RUN で mission 0 が継続 | 過去 RUN の retroactive mission 候補数を一覧で提示 | APPROVED Round 1 |
| **C4** | **trade_count 境界張り付き調査 (report 化のみ、 閾値変更なし)** | `generate_run_report.py` で Stage C 通過群の trade_count 分布を histogram で表示、 `trade_count==trade_count_min` 群の PnL/Sharpe 分布を別 table 化 | `scripts/alpha_factory/generate_run_report.py` | Suggestion | Audit (no behavior change) | 境界張り付き群 (trade_count==min) と非張り付き群の性質差 | Stage C 通過 217 中 173 が trade_count=51 で境界張り付き = 取引回数最適化偏り | hard constraint 近傍に探索集中 | 51 群が他群より実績優位なら「悪性張り付き」仮説弱まる | 次 cycle で構造対策要否を判定可能な証拠が揃う | APPROVED Round 1 |

## 却下された提案

| # | 提案 | 却下理由 |
|---|------|---------|
| 別 (旧 #4) | deceit 検知列追加 (long/short / overnight / swap / spread) | cycle 23 では schema/計測経路変更が広く 1 ラウンド収束阻害。 cycle 24 で Structural な監査列追加として実施するため、 **新 TODO 起票で繰り越し** |
| 旧 #5 (trade_count 閾値変更) | live_criteria.trade_count_min 値の変更 | Reactive Parametric (= 直近 Run で X が悪かったから Y を調整) になりやすい。 構造的対策に変換のため調査のみ (= C4) |

## 保留事項 (合議収束ルールにより次 Run 検証申し送り)

| # | 仮説 | 最小変更案 | 検証条件 |
|---|------|----------|---------|
| H-deceit | Stage B 通過群の黒字化はイントラデイ逸脱 / ショート偏重 / コスト未反映で稼いでいる可能性 | TradeRecord / archive に long/short / overnight / spread / swap 集計列追加 | cycle 24 で実装、 archive 再評価で逸脱兆候検出 |
| H-trade_count_concentration | trade_count=51 集団が live_criteria.trade_count_min 狙い撃ちの「悪性張り付き」か、 単に hard constraint 近傍に自然分布しているか | trade_count==51 vs >51 群の PnL/Sharpe 分布比較 (C4 で report 化) | cycle 23 report で初期データ取得、 cycle 24 以降で構造対策要否判断 |
| H-cross_pair | single-instrument 運用での graduation 0 は仕様通りだが、 multi-instrument lane への拡張で mission 達成個体を「卒業」させる必要性 | --instrument-list で multi-instrument mode 起動 + cross_pair pass 条件確認 | cycle 25 以降 (Run 75 結果が seed sweep で再現性あれば) |

## 次フェーズへの申し送り

- **Phase C-1**: detailed-design.md 作成 (C1-C4 の実装範囲確定)
- **Phase C-2/3**: Codex design-review (最小 1 ラウンド APPROVED 目標)
- **Phase 3 (実装)**: cycle 23 worktree で C1-C4 を 1 commit に統合実装
- **Phase 4**: Run 76 (`--instrument EUR_JPY --population-size 96 --generations 60 --mutation-rate 0.5 --seed 61 --max-workers 2 --stage-b-gate-kind profit_safe_pfr`)
- **Phase 5**: run-report で 3 KPI 分離 + retroactive 再評価結果も併載

期待される結果:
- Run 76 best 個体で live_criteria.sharpe.pass=True (= bug fix 効果)
- mission_candidate_count > 0 (= 真の mission 達成個体数)
- 過去 19 RUN retroactive 再評価で Run 60, 65, 70 等の「sharpe 0.4-0.5 個体」が実は mission 達成相当だったことを発見する可能性
