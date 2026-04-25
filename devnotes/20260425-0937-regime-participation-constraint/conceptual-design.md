# 概念設計: regime-participation-constraint (RPC) — Phase 1 minimal

## 背景・課題 (観察事実)

直近 3 Run (Run 7/8/9) で確認された構造的問題:

- Run 9 (Fact): best 個体 g0_i1 は trade_count=0、Stage A pass 0/120、全120個体で total_pnl=0.0、90/120 個体で trade_count=0
- Run 8/7 (Fact): best は trade_count=1〜2 で sharpe>9.6
- Codex 独立分析の仮説1 (Interpretation): `trade_count=0` 個体の `fitness_pen=0` が、取引する個体 (負 Sharpe) より相対優位になり、選抜圧が「無取引方向」に働いている
- Codex 独立分析の仮説2 (Fact 候補): `trade_count>0 ∧ total_pnl=0` の整合性疑義 (PnL 集計経路の不整合の可能性)

**根本原因 (Interpretation)**: 現行 fitness は「取引した結果の損益」のみを評価し、**「取引しなかったこと」自体を評価していない**。
そのため `tc=0` 個体は損益ゼロで安全 (fitness_pen=0)、取引する個体は失敗時に大きな負 fitness を被るため、選抜は「取引しない」を学習する。

**現行選抜の事実 (Fact)**: `scripts/alpha_factory/run_ga.py` L111-117 において、選抜は NSGA-II ではなく辞書式タプル `selection_score = (stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen)` の tournament。
fitness_pen が同値 0.0 の `tc=0` 個体と取引失敗個体 (負 fitness_pen) を比較すると、`tc=0` 側が確実に勝つ構造になっている。

## 改善アイデア (Phase 1 最小版)

**Phase 1 は mission 直接達成ではなく、mission を阻害している no-trade attractor の反証実験**である (low-trade quality 問題は本 Phase スコープ外、Phase 2+ で対処)。

**Regime Participation Constraint (RPC) Phase 1**: 「**`trade_count=0` 個体を構造的に下位化する feasibility 制約**」を現行 `selection_score` の先頭に追加する最小変更。

- 各個体に `feasible: bool` (= `trade_count >= entry_count_min`、初期 `entry_count_min=1`) と `violation_magnitude: float` (= `max(0, entry_count_min - trade_count)`) を計算
- `selection_score` を **6 タプル** に拡張:
  `(feasible_int, -violation_magnitude, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen)`
  - `feasible_int = 1 if feasible else 0` (大きいほど良い)
  - `-violation_magnitude` で違反量小さい方を優先
- 既存 fitness 関数・Stage 通過判定・archive 構造は変更しない (penalty 追加なし)

**Phase 2 (本 TODO スコープ外、別 TODO に分離)**:
- 9 セル regime 分類 (時間帯 × ボラ) に拡張
- archive へ participation 列永続化
- セル別エントリー回数最低保証 + min_cell_bars ノイズ対策

## 期待効果 (反証可能仮説のみ列挙)

- H1 (主目的): Run 10 の archive で `trade_count=0` 個体比率 (90/120 = 75%) について、**運用上の成功基準として < 50% を置く** (1 run の archive 行は独立標本ではないため統計的有意性は主張しない、3-5 seed の再現確認は次段検証計画)
- H2: best 個体が `trade_count=0` になる事象の頻度低下 (Run 9 の best=g0_i1 のような結果が再発しない)
- H3: Stage A pass 数の増加可能性 (Run 9 の 0/120 から脱却)。**ただし Stage A pass の閾値分布も影響を受け得るため副次効果として観察に留める**

**期待しない (検証仮説に降格)**: `trade_count=45/50` に直接到達 (これはセル別最低参加率の Phase 2 成果であり、Phase 1 では「無取引淘汰」のみ)。

**trade_count 影響予測: 増 (H1 が真なら確実)**

## 実装方針 (Phase 1 最小版の概要)

1. **trade_count 取得**:
   - `_update_cache()` (`scripts/alpha_factory/run_ga.py` L437-475) は既に archive row の `trade_count` 列を読んでいるので、それを利用 (`BacktestResult.trades` 直接アクセスは不要、archive 経由が実装に忠実)
   - 取得した `trade_count` から `feasibility` と `violation_magnitude` を計算

2. **selection_score 拡張**:
   - `_GenomeMetrics.selection_score` プロパティ (L111-117) に feasibility/violation を先頭追加
   - tournament (L363-370) と best 選択 (L380-396, L475) は `selection_score` 経由なので追加修正不要

3. **config 追加** (YAML だけでは機能しない、loader まで含める):
   - `config/alpha_factory/default.yaml` に `ga.feasibility.entry_count_min` (初期値 1) と `ga.feasibility.apply_from_generation` (初期値 0) を追加
   - `src/alpha_factory/config.py` L101 (`GAConfig` dataclass) に `feasibility: GAFeasibilityConfig` フィールド追加
   - 同 L243 (`load_config()`) で feasibility section の読み込み実装
   - 新規 `GAFeasibilityConfig(entry_count_min: int, apply_from_generation: int)` 小 dataclass を切る
   - Phase 2 で `ga.feasibility.cells = [...]` を追加する placeholder のみ予約

4. **既存契約への追従** (selection_score 6 要素化に伴う):
   - `scripts/alpha_factory/run_ga.py` L653 `summary.json.selection_score` 出力を 6 要素対応
   - `scripts/alpha_factory/generate_run_report.py` L451 の説明文 (旧 4 要素ハードコード) を 6 要素に更新
   - `tests/scripts/test_alpha_factory_run_ga.py` L394 の selection_score smoke test を 6 要素期待値に更新

5. **診断ログ**:
   - run-report に「全個体の `trade_count=0` 比率」「best individual の trade_count」を追加 (既に run-9.md に該当情報あり、format 維持)
   - `feasible` 個体数を per-generation summary に追加 (archive Parquet schema 変更なし、`summary.json` のみ拡張)

6. **Phase 2 への接続**: Phase 2 の Regime cell 拡張が来たとき `entry_count_min` を `cell_entry_count_min[cell_id]` のリストに昇格できる構造で書く (extension point を抽象化)

### 影響先 inventory (affected consumers)

`config/alpha_factory/default.yaml`, `src/alpha_factory/config.py` (GAConfig + load_config), `scripts/alpha_factory/run_ga.py` (selection_score + _update_cache + summary.json), `scripts/alpha_factory/generate_run_report.py` (説明文), `tests/scripts/test_alpha_factory_run_ga.py` (smoke test)

## 制約・前提 (検証済み事実 = Fact / 解釈 = Interpretation 分離)

### Fact
- 現行 GA 選抜実体は `scripts/alpha_factory/run_ga.py` (NSGA-II 化されていない)
- `selection_score = (C_pass, B_pass, A_pass, fitness_pen)` 辞書式 tuple
- `BacktestResult.trades` のみで trade_count 計算可能 (`position_timeline` は不要)
- `ga/operators.py` は現 repo に存在しない (修正対象は `run_ga.py` のみ)
- 既存 T016 (cross-pair shadow), T017 (swim-lane), T025 (sieve), T027 (calibrate-gate) は本 Phase 1 と直接の重複なし

### Interpretation
- `tc=0` 優位の主因は selection_score の `fitness_pen=0.0` 同値構造 (証拠: Run 9 best=g0_i1 が gen 0、即収束)
- selection_score 先頭への feasibility 追加で勾配を保ったまま `tc=0` 個体は構造的に下位化される (constraint dominance 文脈の一般原理)
- Stage A pass 通過率分布は副次的に変化し得る (閾値変更ではなく入力個体分布の変化経由)

### 前提制約 (Verified / Assumed / Out-of-scope の三値分離)
- メモリ (Verified): feasibility/violation は `_GenomeMetrics` に float×2 追加のみ → 24GB × 6 ワーカー制約に対し支配的ではない
- 並列性 (Assumed): tournament 内の selection_score 比較は GIL 影響なし (既存と同等の操作)
- 後方互換 (Verified): 現行 `run_ga.py` には旧 summary 復元経路が存在しない (L555 周辺で確認) ため後方互換問題は発生しない。新規 summary は新形式のみで生成される

## スコープ外 (Phase 1)

- 9 セル時間帯 × ボラ分類 (Phase 2 別 TODO)
- セル別最低エントリー数保証 (Phase 2 別 TODO)
- archive Parquet schema 拡張 (Phase 2 別 TODO; Phase 1 は summary.json のみ)
- ATRRegimeGate の意味再定義 (将来の設計帰結、本 TODO の直接効果ではない)
- live_criteria.trade_count_min=50 直接達成 (Phase 2+ の累積効果)
- `trade_count>0 ∧ total_pnl=0` 整合性監査 (別 TODO; ただし本 TODO の効果測定にこの不整合が干渉するリスクを文書化)
- NSGA-II / Pareto 多目的化 (Codex 提案 #4 別 TODO)
- Opportunity Head / Execution Head 二段モデル化 (Codex 提案 #6 別 TODO)
- min_participation_rate の動的 calibrate (T027 風、RPC 安定後に検討)

## リスクと対策

- **R1**: `trade_count>0 ∧ total_pnl=0` 不整合が併存すると、H1 検証で false positive (trade_count は増えたが PnL ゼロのまま) が発生し効果評価が混乱する
  - 対策: Phase 1 完了後の Run report で `trade_count>0 ∧ total_pnl=0` の同時集計を必須化 (別 TODO で監査するまでの暫定観測)
- **R2**: 全個体 infeasible の世代では feasible_int=0 で同値 → violation_magnitude のみで選抜され、収束加速の副作用
  - **緩和策** (solve ではない): `apply_from_generation` で初期世代の制約導入を遅らせる。全個体 infeasible が発生したら feasibility 軸を無効化して旧 4 要素 `selection_score` にフォールバックするロジックを実装側で検討 (詳細設計で確定)
- **R3**: 短期保有でも `entry_count_min=1` をクリアできるため、本質的に「regime 横断で動く」ところまでは Phase 1 では到達しない
  - 対策: 期待効果から「regime 横断参加」を外し、「無取引淘汰のみ」と効果記述を弱めた (Phase 2 で対処)
