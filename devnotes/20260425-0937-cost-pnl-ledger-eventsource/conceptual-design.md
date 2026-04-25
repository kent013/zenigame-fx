# 概念設計: cost-pnl-ledger-eventsource (Stage A 記録整合性監査 — sidecar 版)

> **改訂履歴**
> - Round 1 → Round 2: PnL ledger SSOT 化を棄却、Stage A 投影仕様問題に焦点化
> - Round 2 → Round 3: archive Parquet schema extension を棄却、sidecar diagnostics に変更
> - Round 3 → Round 4: dataflow を明文化 (DiagnosticsCollector パターン)、`metric_stage` は collector 側で最終確定、sidecar 主キーを複合キー (lane_id, generation, individual_name) に変更

## 背景・課題

Run 9 (run_20260425_002330) の Codex 独立分析で `trade_count > 0 ∧ archive.total_pnl == 0.0` が観測された。

**前提検証 (verified)**:
- 現行 backtest 側では `total_pnl = sum(Trade.pnl)` で正しく集計されている (`src/backtest/metrics.py#L85-L89`)
- `Trade.pnl` には closing 時点で `raw_pnl - holding_cost` の net_pnl が入る (`src/broker/mock.py#L327-L353`)
- Stage A の payload は `trade_count` と `sharpe_raw` のみで `total_pnl` を持たない (`src/alpha_factory/stage_gate.py#L268-L333`)
- archive への Stage A collect も `trade_count / sharpe` のみで `total_pnl` を書かない (`src/alpha_factory/archive.py#L322-L346`)
- 設計文書もこの仕様を明示している (`docs/alpha_factory/clause-architecture.md#L356-L365` — Stage A: `total_pnl - / trade_count ○`、Stage B/C で上書き)
- **archive schema は 28 カラム固定** (`src/alpha_factory/archive.py#L51-L101` `GENOMES_SCHEMA`、import-time assert で template と完全一致を要求、`tests/alpha_factory/test_archive.py#L165` でも 28 カラム前提)
- 既存合意は「Run 10 では監査のみ、挙動非変更」 (`devnotes/20260425-0931-fx-improve/improvement-plan.md#L7-L10`)

**前提検証 (unverified, 棄却された旧仮説)**:
- 「PnL 集計経路の破綻」を当初疑ったが、最新コード上では成立しない (集計自体は正しく動いている)

**真の課題 (observability gap)**:
- Stage A 段階で archive に `total_pnl` が転記されない設計のため、Stage A で落ちた個体は archive 上 `total_pnl=0.0` のように見える
- これが「PnL 集計バグ」「Stage A 落ち個体」「コスト過大計上」のいずれによる 0 なのか、post-run 分析で切り分けが困難
- **Run 10 blocker ではない observability task** として位置付ける (Run 10 Critical は no-trade penalty 側)

## 改善アイデア (sidecar diagnostics 版)

### Phase A (本 TODO スコープ): Stage A 記録整合性監査 (sidecar, audit-only, fail-open)

**archive Parquet schema は touch しない** (28 カラム fixed schema と既存テスト・SSOT 文書を尊重)。

代わりに、`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet` を **sidecar ファイル**として出力する。

#### データフロー (DiagnosticsCollector パターン)

1. **DiagnosticsCollector の導入** (Round 4 追加):
   - 新規 `src/alpha_factory/diagnostics_collector.py`: in-memory に generation 中のステージ別 metrics を蓄積
   - 各個体について複合キー `(lane_id, generation, individual_name)` で以下を蓄積:
     - Stage A 評価時: `trade_count`, `total_pnl`, `sharpe`, `stage_a_pass` (boolean)
     - Stage B 評価時: `stage_b_pass` (boolean、 該当した場合のみ)
     - Stage C 評価時: `stage_c_pass` (boolean、該当した場合のみ)
   - collector は `run_ga.py` のスコープで生成され、`run_generation()` 経由で stage_gate に渡される
   - **`metric_stage` は collector が flush 時に確定** (post-hoc derivation):
     - `stage_c_pass=True` → `"stage_c_evaluated"`
     - `stage_b_pass=True ∧ stage_c_pass=False/None` → `"stage_b_evaluated"`
     - `stage_a_pass=True ∧ stage_b_pass=False/None` → `"stage_a_evaluated"`
     - `stage_a_pass=False` → `"stage_a_only"`

2. **Stage A backtest 結果の payload 補足 (最小限)**:
   - `src/alpha_factory/stage_gate.py` の Stage A payload に `total_pnl` / `sharpe` のみを追加 (in-memory のみ、archive には書かない)
   - **`metric_stage` は payload に含めない** (collector 側で最終確定するため、後段結果の逆流を避ける)

3. **sidecar 出力 (GA 完了時 flush)**:
   - 出力ファイル: `reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`
   - schema: `lane_id, generation, individual_name, metric_stage, trade_count, total_pnl_stage_a, sharpe_stage_a, stage_a_pass, stage_b_pass, stage_c_pass`
   - 主キー: `(lane_id, generation, individual_name)` (既存 archive の複合主キーと整合)
   - 書き込み失敗時: warning ログのみ、GA は完走 (fail-open)

4. **`summary.json` schema 拡張 (最小限)**:
   - 新規 optional field `diagnostics_sidecar` (path 文字列のみ)
   - **書き込み成功時のみ出力** (失敗時は field 自体を出さない、consumer は missing field を無視)

5. **run-report skill での可視化**:
   - run-report が sidecar を optional で読み、「Stage A 落ち個体の total_pnl 分布」セクションを追加
   - sidecar 不在時の表示: section 自体は固定で出し、内容は「Stage A provenance: not available」と明記 (契約ぶれ回避)

### Phase B (将来 TODO 化, 本 TODO スコープ外): コスト分解の可視化基盤

`PriceBar` は bid/ask を持ち、MockBroker の fill ルールは決定論 (`src/domain/price.py#L16`、`src/broker/mock.py#L201, L363`)。
ただし exit が `open`/`close` のどちらかを `exit_reason` から復元する仕様を先に固定しないと `spread_implicit` は不安定。
これは Phase A の sidecar による観測結果を踏まえて再判定する。

### Phase C (将来 TODO 化, 本 TODO スコープ外): invariant 監査 (CI 限定)

`summary.diagnostics.invariant_violations` の追加は現行 `summary.json` SoT に存在しないため、初回実装は `logger.warning` または sidecar diagnostics ファイルに限定する。

## 期待効果

- **直接効果**: Run report で「Stage A 落ち個体の total_pnl 分布」が可視化され、`trade_count>0 ∧ archive.total_pnl=0` の正体 (Stage A 投影仕様 vs 真のバグ) が即座に切り分け可能になる
- **副次効果**: Phase B/C 着手前のベースラインデータ (Run 10 以降の sidecar 蓄積) が得られる
- **副次効果2**: 後続 cost-efficiency 改善 (5 件) の効果測定における基準点を提供

## 実装方針 (Phase A 最小変更)

### 変更コンポーネント

- `src/alpha_factory/stage_gate.py`: Stage A payload に `total_pnl` / `sharpe` のみを追加 (in-memory のみ、ゲート判定ロジック不変)
- 新規: `src/alpha_factory/diagnostics_collector.py` (DiagnosticsCollector class、ステージ別 metrics 蓄積)
- 新規: `src/alpha_factory/diagnostics_sidecar.py` (sidecar writer、純粋関数 + 単一書き込み)
- `src/alpha_factory/swim_lane.py`: `run_generation()` 経由で collector を stage_gate に渡す (個体ごとの Stage A payload を保持する経路追加)
- `scripts/alpha_factory/run_ga.py`: collector 生成 + GA 完了後に sidecar writer を呼び出し
- `.claude/skills/zenigame-fx-run-report/SKILL.md`: 固定セクション「Stage A provenance 分布」の追加 (sidecar 不在時は "not available" 明記)
- 新規テスト: `tests/alpha_factory/test_diagnostics_collector.py`, `tests/alpha_factory/test_diagnostics_sidecar.py` (純粋関数テスト)

### 不変条件 (CI invariant のみ)

- I1: sidecar 行数 == backtest 評価された個体数
- I2: `metric_stage` の値が enum 内
- I3: `total_pnl_stage_a` が finite (NaN/Inf なら sidecar に diagnostics として記録)

production GA では fail-open: sidecar 書き込みエラーは warning ログのみ、GA 自体は止めない。

## 制約・前提

- **archive Parquet schema は完全に touch しない**: 28 カラム fixed schema、既存 import-time assert、既存テスト、SSOT 文書すべてと整合
- **summary.json schema 拡張は最小限**: optional field `diagnostics_sidecar` (path 文字列) のみ。consumer は missing field を無視できる
- **fitness / 選抜への影響ゼロ**: payload 拡張は in-memory only、ゲート判定ロジックは不変
- **絶対制約**: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映と整合
- **trade_count 不変**
- **既存 Stage A/B/C ゲートロジックは touch しない**
- **Run 10 blocker ではない observability task**

## スコープ外

- archive Parquet schema 拡張 (28 カラム fixed schema を尊重)
- production GA での invariant penalty
- スプレッドサーフェス導入 (別 TODO 候補#2)
- 約定 2 層化 (別 TODO 候補#3)
- セッションクローズ実行ポリシー (別 TODO 候補#4)
- Swap アクルーアル化 (別 TODO 候補#5)
- Live-BT パリティ検証ハーネス (別 TODO 候補#6)
- Stage A/B/C 通過率改善
- fitness 関数の tc=0 ペナルティ (Run 10 Critical 側、別ループ)
- Phase B (コスト taxonomy) と Phase C (CI invariant) の本実装

## TODO 起票方針

- **A. Stage A provenance sidecar 記録** (Medium, 短) ← 本 TODO
- **B. コスト taxonomy + sidecar 拡張** (将来 TODO、A の sidecar 観測後に再判定)
- **C. CI invariant ハーネス** (将来 TODO、A 完了後に分離)

優先度: **Medium** (observability task, Run 10 blocker ではない)
