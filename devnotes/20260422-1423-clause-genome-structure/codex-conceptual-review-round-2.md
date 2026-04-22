## 各レビュー項目への所見（1〜8）
1. 目的との整合性（`max_clause=1` でも非等価）  
Fact: 現行は `entry_long/entry_short/exit_long/exit_short` の4式ブール評価です。新設計は `Clause = directional × local_gate × weight`、`composite` の連続値、`θ_on/θ_off` による状態遷移、`time_stop/session close` を導入しています。  
Interpretation: `max_clause=1` でも「連続値 + 状態機械 + 時間制約」のため、旧4式と表現能力は一致しません。目的整合は満たしています。

2. 必須5要素の網羅  
Fact: 本文 2.2 に 5 要素と責務配置が明示されています。`spread` は genome 内ではなく backtest 入力依存として定義されています。  
Interpretation: 概念レベルでは網羅できています。要素5（spread）は本TODO外実装なので、後続TODOでの実装保証（受け渡し契約）が必要です。

3. ヒステリシス動作（`θ_on > θ_off`）  
Fact: `PositionConfig(entry_threshold, exit_threshold)` と `DslStrategy` 遷移表で、無保有時は `θ_on`、保有時は `θ_off` を使用する設計です。`enforce_consistency` で違反時 swap 規則も定義されています。  
Interpretation: 配置は妥当です。チャタリング抑制はイントラデイのノイズ環境に適合します。Clause層ではなく Position/遷移層に置いた判断も一貫しています。

4. `PrimitiveEvaluator Protocol` の抽象レベル  
Fact: primitive未実装の段階で `Protocol` を置き、テストは `StubEvaluator` を使う設計です。  
Interpretation: 妥当です。`strategy/composite` の概念検証を primitive 実装から分離でき、T007 のスコープを守れています。

5. `enforce_consistency` の配置  
Fact: `src/dsl/enforce.py` の pure function とし、ランダム生成・交叉・変異・後処理で適用可能と定義されています。  
Interpretation: GAとの整合は良好です。repairを純関数化する方針はテスト容易性・再現性に有利です。  
Fact: ただし「directional空のClause」の扱いが「除去 or ダミー挿入」の選択肢のまま未確定です。  
Interpretation: ここは詳細設計前に1案へ固定すべきです（非決定のままだと挙動差が大きい）。

6. スコープ境界  
Fact: T007の対象/非対象が明確に分離され、`clause-ga-operators`、`clause-backtest-integration`、`primitives-*` へ委譲されています。  
Interpretation: 分割は妥当です。概念設計として過不足が少なく、禁止事項5（過度な大規模化）にも抵触しません。

7. 旧Genome削除方針（`_legacy` なし、skip運用）  
Fact: 旧構造を残さず置換し、依存テストを一時skipして後続TODOで復旧する方針です。  
Interpretation: 二重系の長期併存を避ける判断は妥当です。skip増加による検証空白はリスクなので、復旧期限と対象一覧を明示すれば運用可能です。

8. `session close` を `DslStrategy` 引数 `default=None` にする件  
Fact: 本TODOでは `None` 時は無効、後続TODOで FX セッション close を default化予定と記載されています。`time_stop_min` は同時導入されています。  
Interpretation: 「backtest engine 側でEOD強制クローズを必ず担保する」という前提が明文化されるなら整合します。前提が欠けるとイントラデイ絶対制約に穴が残るため、契約条件（どちらが最終責務か）を明示すべきです。

## 致命的指摘 (Blockers)
- なし（概念方針自体を差し戻すレベルの矛盾は見当たりません）。

## 改善提案 (Non-blocking)
- `session close=None` を許容する条件を明文化してください。  
`session_close_utc is not None` または `engine_eod_force_close=True` のどちらか必須、という不変条件を設計文に追加するのが安全です。
- `enforce_consistency` の「directional空Clause」処理を 1 つに固定してください。  
「除去」か「reject（例外）」を推奨します（ダミー挿入は探索空間の意味を歪めやすい）。
- 要素5（spread/swap/slippage反映）は後続TODO依存なので、受け渡しI/Fを先に1行でも規定してください。  
例: `BacktestInput` に `spread_bps` / `swap_cost` 必須。

## 判定: APPROVED_WITH_COMMENTS