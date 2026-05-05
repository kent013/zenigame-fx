# 最終改善計画: Run 34 → Run 35 (cycle 1 / 10)

## 合議ステータス: CONSENSUS REACHED (Round 2)

Round 1: CHANGES_REQUESTED (P3-P5 修正要請)
Round 2: APPROVED (cycle 1 = C1+C2+W3 の構造検証に絞り込み合意)

## 反証可能仮説 H_c1

「run-34 で観測された total_pnl=0.0 / dsr 全 NaN / per_generation null 多発 / stage_b=183403=全期間 という事実は、 計測経路 (recording / display / partition guard summary 集計) の structural bug に起因し、 GA 探索アルゴリズムや stage gate threshold の問題ではない」

**falsification**: C1+C2+W3 調査で計測経路 bug がなければ仮説は **棄却**、 探索アルゴリズム / stage gate が真の問題 → cycle 2 で P3 (Stage A 厳格化) を実施。

## 確定施策一覧

| # | 施策名 | 内容 | 変更対象 | 優先度 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion | 合議結果 |
|---|--------|------|---------|--------|---------|--------------|-------------|------------|---------------|-------------------|---------|
| C1 | Stage partition/holdout 実測監査 | partition 境界 timestamp で実測しdisjoint 検証。 contract 違反なら修正 | scripts/alpha_factory/run_ga.py / src/alpha_factory/stage_partition_guard.py / 関連 docs | Critical | Structural | データ境界の正当性 | `stage_b=183403=全期間` で T087 disjoint 契約と矛盾、 holdout bars=20457 が holdout_days=60 と乖離 | partition guard が validate しているが summary 表示集計が contract と異なる経路を通る、 もしくは guard 自体に bug | partition 境界 timestamp で実測し disjoint なら正常、 重複なら structural bug | partition disjoint で stage_b range ⊂ Stage A 期間外、 holdout bars が 60 日 ≈ 86400 程度に修正 | Round 2 APPROVE |
| C2 | total_pnl=0.0 計測経路の健全性チェック | best 個体を local 再評価し trade ledger を集計。 0 固定化/単位不整合の切り分け、 必要なら修正 | scripts/alpha_factory/run_ga.py 集計経路 / reports/run-reports/run-{N}/summary.json 出力 | Critical | Structural | total_pnl_min=50000 判定の正当性 | best 個体で trade_count=67, sharpe=0.24 (positive) なのに total_pnl=0.0 | trade-level Sharpe → summary 集約で PnL 単位変換 / 集計欠陥の疑い | best 個体 g54_i35 を local 再評価し trade ledger を集計、 0 でなければ計測経路 bug | 集計後 PnL > 0 で recording / display 整合 (or trade-level Sharpe 計算経路に応じた数学的整合) | Round 2 APPROVE |
| W3 | per_generation observability 整備 | per_generation の median_fitness_pen / stage_X_pass_count / population_diversity の null 多発を解消。 dsr 全 NaN / archive_role/source_stage/fsp_* 空も同様に観測経路欠陥として整理。 計測経路のみ修正、 計測ロジックは変更しない | summary.json / archive Parquet の writer 経路 | Warning | Structural | 観測性 | per_generation の median_fitness_pen / stage_X_pass_count などほぼ全行 null | recording 経路で null フィールドを上書きしないまま fallback 値で書き出している恐れ | 各フィールドが計測されているか、 writer 経路でどこで null になるか実測 | per_generation の null 率 < 10% (現状 100% から改善)、 dsr 計算が動く、 archive_role/source_stage/fsp_* が値を持つ | Round 2 APPROVE |

## 却下された提案

| # | 提案 | 却下理由 |
|---|------|---------|
| P4 | max_clause=2 A/B (cycle 1) | 計測未確定下では effect 判定不能、 collider/confounding 疑い、 「最小変更」原則違反。 cycle 2 以降再エントリ可 |
| P5 | cross-pair shadow multi-instrument (cycle 1) | 因果経路長すぎ、 cycle 1 「1 仮説 + 最小変更」原則違反。 cycle 2 以降再エントリ可 |

## 保留事項（次サイクル検証申し送り）

cycle 1 design-review (Round 1) で Codex が以下を指摘し、 cycle 1 を **C2 H1/M1 のみ** に絞り込む形に絞り込み合意:

| # | 元提案 | 仮説 | 最小変更案 | 検証条件 / 持ち越し理由 |
|---|------|-----|----------|---------|
| C1 (持ち越し) | partition 監査 | run-34 が旧 schema の可能性 → cycle 2 RUN を新 schema で取り直してから監査 / holdout 24/5 cadence で coverage guard 強化 | T087 artifact 互換性確認 + holdout coverage guard | cycle 2 で再エントリ。 cycle 1 で run-34 を直接根拠に使えない |
| W3 (持ち越し) | per_generation observability | `archive_role/source_stage/fsp_*` は nullable 契約、 `median_fitness_pen / population_diversity / stage_X_pass_count` は per_generation schema に存在しない | per_generation schema 拡張提案 + 観測対象再定義 | cycle 2 以降、 schema 拡張議論として再エントリ |
| P3 | Stage A 選別力厳格化 | Stage A selectivity 不足が Stage B 落下率 99.2% の原因 | `stage_a.threshold` 単独変更 (厳格化のみ) | cycle 2 で C2 修正完了後再判定 |
| P4 | max_clause=2 A/B | max_clause=1 が Stage B 制約の寄与仮説 | max_clause=2 の対照 RUN 1 件 | cycle 2 以降、 P3 評価後 |
| P5 | cross-pair shadow multi | multi-instrument で shadow が情報を加える | multi 2-3 pair RUN 1 件 | cycle 3 以降、 P3/P4 評価後 |

cycle 1 で実装する施策は **C2 (絞り込み版)** = `collect_stage_a` で `total_pnl` を archive に伝搬 + 回帰テスト 1 本のみ。 detailed-design.md 参照。

## 次フェーズへの申し送り (Phase C 詳細設計)

- **TODO 由来施策なし** (Open/Conditional 0 件) → Phase C-0 (TODO 詳細設計読み込み) はスキップ
- **C1/C2/W3 は調査主導** で、 修正は調査結果次第。 詳細設計には「調査手順」「bug found 時の修正方針」「調査結果のフォーマット」 を含める
- **テスト計画**: 修正がある場合のみ追加テスト、 修正なしなら既存テストの再走確認のみ
- **波及変更**: C1 は T087 の docs/skill 更新、 C2/W3 は記録経路 docs 更新の可能性

## 使命チェック

| 禁止事項 | 抵触有無 |
|---------|---------|
| 1. 評価期間延長 | なし (期間変更なし) |
| 2. 見た目数値改善 | なし (調査・bug 修正主導) |
| 3. GA ハック | なし |
| 4. 閾値緩和でステージ飛ばし | なし (cycle 1 では threshold 変更なし) |
| 5. 複雑案 | なし (3 件、 構造検証中心) |
| 6. 取引回数削減で見かけ改善 | なし |
| 7. オーバーナイト保有前提 | なし |

cycle 1 は「数値改善より計測経路と境界整合の検証」が目的。 mission alignment OK。
