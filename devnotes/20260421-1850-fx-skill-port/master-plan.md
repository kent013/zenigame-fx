# zenigame-fx Alpha Factory 移植・構築マスタープラン

**作成日時**: 2026-04-21 21:00 (JST)
**根拠**:
- [design.md](design.md) — skill 移植全体設計
- [ga-architecture.md](ga-architecture.md) — GA 2 軸の判断
- [debate-synthesis.md](debate-synthesis.md) — Codex × Claude 3 ラウンド議論の確定仕様
- ユーザーとの追加合意: スイムレーン設計、ペア特化プリミティブ、OANDA 外部データ（FRED 補助）

---

## フェーズ構成（全 7 フェーズ）

| Phase | 名称 | 内容 | 想定工数 | 依存 |
|-------|------|------|---------|------|
| 0 | DROP 退避 | 7 skill を `_archived/` へ | 5 分 | なし |
| 1 | 基盤 skill 移植 | RENAME-ONLY 5 skill | 30 分 | Phase 0 |
| 2 | FX Alpha Factory 基盤構築 | Clause / Stage Gate / Archive / プリミティブ / スイムレーン等 | 大（複数セッション） | Phase 1 |
| 3 | Skill 内容移植 | CONTENT-ADAPT 12 skill + RENAME 残り 4 skill | 中 | Phase 2 |
| 4 | INFRA-ADAPT skill 実装 | calibrate-gate / post-run-review / alpha-sieve | 中 | Phase 3 |
| 5 | MVP 通し動作確認 | improve-cycle 1 サイクル dry-run | 30 分 | Phase 4 |
| 6 | 本格運用層 | PBO-lite / RC/SPA / hard gate 化 / rollback 自動化 / 移行トリガー | 大 | 実測データ（5-10 Run） |

---

## Phase 0: DROP skill 退避（5 分）

### 0-1. `.claude/skills/_archived/` ディレクトリ作成
```bash
mkdir -p .claude/skills/_archived
```

### 0-2. 7 skill を git mv で退避
対象: `zenigame-enqueue-task`, `zenigame-manage-alert`, `zenigame-manage-timer`, `zenigame-restart-worker`, `zenigame-troubleshoot-worker`, `zenigame-primitive-ic-eval`, `zenigame-primitive-ic-sync`

### 0-3. 退避理由を記録
`.claude/skills/_archived/README.md` に「なぜ archive したか」「復活条件」を記録。

### 0-4. コミット
```
chore(skills): archive 7 zenigame skills that depend on systemd/Dramatiq/J-Quants
```

---

## Phase 1: 基盤 skill 移植 RENAME-ONLY（30 分）

依存の少ない順:

### 1-1. `zenigame-fx-codex-vscode`
- 元: `zenigame-codex-vscode`
- 改修: description の project 名差し替えのみ（使命記述が無い汎用 skill）

### 1-2. `zenigame-fx-codex-review`
- 元: `zenigame-codex-review`
- 改修:
  - 使命セクション: 日本株 → FX（両方向許容、イントラデイ優先、スワップコスト反映）
  - 禁止事項: ショート禁止を削除、代わりに「オーバーナイト保有を前提にしない」
  - C1-C9 discipline はそのまま
  - `docs/alpha-factory/` 参照 → `docs/alpha_factory/`

### 1-3. `zenigame-fx-manage-sessions`
- 元: `zenigame-manage-sessions`
- 改修: description のみ

### 1-4. `zenigame-fx-clear-cache`
- 元: `zenigame-clear-cache`
- 改修: namespace が FX 側のものに（`alpha_factory`, `http` 等）

### 1-5. `zenigame-fx-snapshot`
- 元: `zenigame-snapshot`
- 改修: パス参照を FX 側に

### 1-6. コミット
```
feat(skills): port foundational zenigame skills to zenigame-fx namespace
```

---

## Phase 2: FX Alpha Factory 基盤構築（大）

Phase 2 は複数サブフェーズに分割。各サブフェーズで独立コミット。

### Phase 2A: ドキュメント骨格（30 分）

既存 `docs/` 構造に `alpha_factory/` を新設:

```
docs/alpha_factory/
├── README.md              # 設計思想、使命、Stage A/B/C、改善サイクル
├── clause-architecture.md # Clause 構造詳細
├── stage-gates.md         # Stage A/B/C 仕様（期間・通過率・ペナルティ）
├── swim-lane.md           # スイムレーン設計
├── primitives.md          # プリミティブ 32 個のカタログ
├── statistics.md          # DSR/PBO/Reality Check 仕様
├── migration-triggers.md  # (b)×(i) → (ii) 移行条件
├── terminology.md         # 用語集
├── runbook.md             # 運用ガイド
├── codex-discipline.md    # Codex 合議の原則（zenigame の C1-C9 を FX 用に）
├── TODO.md                # Open タスク一覧（テーマ定義含む）
└── TODO-closed.md         # Closed/Obsoleted
```

### Phase 2B: 外部データ基盤（1-2 時間）

#### 2B-1. FRED ingest 実装
- `src/ingest/fred.py` 新設（httpx ベース、~100 行）
  - `fetch_series(series_id, start, end)` 関数
  - レート制限・リトライ
- `scripts/fetch_fred.py` CLI
  - `--series VIXCLS,DTWEXBGS,DGS10,DGS2,T10YIE` 一括取得

#### 2B-2. DB スキーマ
- alembic migration で `macro_index_daily` テーブル追加
  - columns: `id, series_id (TEXT), date (DATE), value (NUMERIC), fetched_at (TIMESTAMPTZ)`
  - インデックス: `(series_id, date)` UNIQUE

#### 2B-3. 初回取得
```bash
uv run python scripts/fetch_fred.py --series VIXCLS,DTWEXBGS,DGS10,DGS2,T10YIE \
  --from 2023-04-23 --to 2026-04-21
```
3 年分 × 5 シリーズ = ~4,000 行。

#### 2B-4. OANDA CFD 疎通試験
- `scripts/oanda_ping.py` 拡張で SPX500_USD / WTICO_USD / XAU_USD / XCU_USD の candles エンドポイント疎通試験
- 403 returned なら → **FX データ完結方式に切替**（realized_vol, usd_strength_synthetic で代替）
- 200 returned なら → OANDA で CFD 取り込み継続

### Phase 2C: ゲノム・Clause 構造（2-3 時間）

#### 2C-1. `src/dsl/` 再構築
- 既存 `Genome`（flat 4 Expr）を `_legacy` リネーム
- 新規 `Genome = WhenConfig + HowConfig + Position + Risk + Meta` 構造
- `HowConfig.clauses: list[ClauseConfig]` （max_clause=1 初期）
- `ClauseConfig`: `directional: list[SignalConfig]`, `local_gate: list[SignalConfig]`, `weight: float`
- `SignalConfig`: `name, weight, params`
- composite score 計算:
  `composite = Σ(clause_weight × clause_score) / Σ|clause_weight|`
  `clause_score = dir_score × gate`
  `dir_score = Σ(w_i × signal_i) / Σ|w_i|`
  `gate = Π gate_fn(gate_signal_j)`

#### 2C-2. `src/backtest/` 改修
- DslStrategy が composite score 計算 → ヒステリシス判定 → エントリー/エグジット
- entry_threshold / exit_threshold を Position に保持
- 1 ポジション制約は維持
- long/short 対称（パラメータ別途）

#### 2C-3. `src/ga/` 改修
- `GaConfig` に `max_clause`, `max_depth_per_clause`, `complexity_penalty_alpha` 追加
- operators (crossover/mutate) を Clause 構造対応に
- `random_gen` で Clause 構造を初期化
- 複雑度ペナルティ付き fitness

### Phase 2D: プリミティブ実装（2-3 時間、並列可）

32 プリミティブを `src/alpha_factory/primitives/` に実装。1 プリミティブ = 1 ファイル程度。

#### 汎用 Directional (14)
- TrendEMA, MACDSignal, DonchianBreak, ADXTrend, VolatilityBreak, SessionMomentum
- RSIRevert, BollingerRevert, StochRevert, ZScoreRevert, MeanReversionRange
- RealizedVolZScore, ReturnAutocorrLag, TrendStrengthRatio

#### 汎用 Modulator (6)
- ATRRegimeGate, SessionGate, SpreadConditionGate, EconomicEventGate, VIXRegimeGate (FRED VIXCLS), TrendStrengthGate

#### ペア特化 (12)
- EUR_USD: LondonNYOverlapMomentum, IntradayRangeFade
- USD_JPY: TokyoOpenReversal, YenFixingBias
- EUR_JPY: CrossPairTriangulation, EuroHourVolRegime
- AUD_JPY: RiskOnOffProxy (SPX/VIX), CommodityFlowBias
- USD_CAD: OilPriceInverseFlow (WTI), NADataSurpriseGate
- USD_ZAR: EmergingMarketStressGate, GoldCorrelationBias (XAU)

#### プリミティブ registry
- `src/alpha_factory/primitives/_registry.py` で全 32 個を列挙
- category, domain, required_data を明示

### Phase 2E: Stage Gate / Archive（1-2 時間）

#### 2E-1. `src/alpha_factory/stage_gate.py`
- Stage A/B/C それぞれの evaluate 関数
- walk-forward OOS (train 120d / test 20d / step 20d / embargo 1d)

#### 2E-2. `src/alpha_factory/archive.py`
- GENOMES_SCHEMA 定義（Parquet）
- 必須 columns: `run_id, run_number, generation, individual_name, instrument, lane_id, parent_a, parent_b, genome_json, fitness_raw, fitness_pen, stage_a_pass, stage_b_pass, stage_c_pass, trade_count, total_pnl, sharpe, sortino, calmar, max_drawdown_pct, active_clause, n_nodes, bootstrap_ci_lower, bootstrap_ci_upper, fold_sign_ratio, dsr, ii_lite_pass, graduated`
- 書き込みヘルパ `collect_stage_a/b/c`, `flush`

### Phase 2F: 統計検定最小セット（1-2 時間）

#### 2F-1. `src/alpha_factory/statistics.py`
- `block_bootstrap_sharpe_ci(returns, block_size, n_bootstrap)` 
- `fold_sign_ratio(fold_sharpes)`
- `deflated_sharpe_ratio(sr, n_trials, skew, kurt, n_obs)`
- PBO 関連は Phase 6 で実装（遅延）

### Phase 2G: スイムレーン・マネージャ（2-3 時間）

#### 2G-1. `src/alpha_factory/swim_lane.py`
- `SwimLane` クラス: population, instrument, generation_count, state
- `Tier1Lane`: per-instrument GA
- `GraduationLane`: 卒業者の集合で universal 探索
- 各 lane を順次 or 並列実行
- graduate 条件: Stage C 通過 AND (ii-lite) shadow 基準超え

### Phase 2H: (ii-lite) Cross-pair 評価（1 時間）

#### 2H-1. `src/alpha_factory/cross_pair.py`
- `evaluate_cross_pair(genome, target, anchor_pairs, start, end)`
- 主目的関数: `F = mean(Sharpe_i) - 0.5 × std(Sharpe_i)`
- 監査: `min(Sharpe_i)`, 流動性重み付き mean
- 通過基準チェック（Sharpe_target_cross / mean / min 3 条件）
- 初期は shadow = 記録のみ、hard gate は Phase 6 で発動

### Phase 2I: エントリポイント統合（1 時間）

#### 2I-1. `scripts/alpha_factory/run_ga.py` 全面改修
- Clause ゲノムの GA ループ
- スイムレーン実行
- archive への書き込み
- (ii-lite) shadow 呼び出し
- Stage A/B/C 判定
- 統計指標計算

#### 2I-2. `config/alpha_factory/default.yaml` 再設計
```yaml
dataset:
  start: "2023-04-23T00:00:00Z"
  end: "2026-04-21T00:00:00Z"
  instruments: [EUR_USD, USD_JPY, EUR_JPY, AUD_JPY, USD_CAD, USD_ZAR]

ga:
  max_clause: 1           # 初期 1、max 3 まで段階解放
  max_clause_upper: 3
  max_depth_per_clause: 5
  complexity_penalty:
    alpha_stage_a: 0.03
    alpha_stage_bc: 0.05
  population_size_tier1: 30
  population_size_graduation: 40
  generations: 15
  crossover_rate: 0.7
  mutation_rate: 0.3
  elite_count: 2

stage_gate:
  stage_a:
    window_days: 60
    target_pass_rate: 0.15
  stage_b:
    wf_train_days: 120
    wf_test_days: 20
    wf_step_days: 20
    wf_embargo_days: 1
    pass_criteria:
      median_oos_sharpe_min: 0.20
      positive_fold_min: 0.60
      dsr_min: 0.0  # Phase 6 で発動
  stage_c:
    live_criteria:
      sharpe_min: 1.0
      total_pnl_min: 50000
      max_drawdown_max: 0.2
      trade_count_min: 50
      trade_count_max: 5000

ii_lite:
  mode: shadow  # shadow | hard（Phase 6 で hard へ）
  anchors:
    EUR_USD: [EUR_JPY, USD_CAD]
    USD_JPY: [USD_CAD, EUR_JPY]
    EUR_JPY: [EUR_USD, USD_JPY]
    AUD_JPY: [USD_JPY, EUR_USD]
    USD_CAD: [USD_JPY, EUR_USD]
    USD_ZAR: [USD_CAD, USD_JPY]
  pass_criteria:
    sharpe_target_cross_ratio_min: 0.8
    mean_sharpe_cross_min: 0.15
    min_sharpe_cross_min: -0.20

improve_cycle:
  target_priority: [EUR_USD, USD_JPY, EUR_JPY, AUD_JPY, USD_CAD, USD_ZAR]
```

#### 2I-3. `config/alpha_factory/focus-theme.json` 新設
```json
{
  "themes": {
    "signal-quality": "エントリーシグナルの的中率・期待値",
    "speed": "スリッページ・約定遅延を考慮した現実的 fitness",
    "regime-awareness": "セッション・ボラレジーム切替の精度",
    "robustness": "多通貨ペア・多期間での安定性",
    "cost-efficiency": "スワップ・スプレッドを含めた純利益",
    "risk-management": "ドローダウン・Kelly・ポジションサイズ制御"
  },
  "current_focus": null,
  "current_target_instrument": "EUR_USD"
}
```

### Phase 2 完了判定

Phase 2 完了 = 以下が全部 pass:
1. `scripts/fetch_fred.py` で VIXCLS 3 年分取得成功
2. `scripts/alpha_factory/run_ga.py --instrument EUR_USD --generations 3 --population-size 10` で 1 サイクル完走（Clause 構造、archive 書き込み、(ii-lite) shadow 実行、Stage A/B/C 判定）
3. 生成された archive Parquet が GENOMES_SCHEMA に準拠
4. 単体テスト: primitive 32 個全て、Clause composition、Stage Gate、block bootstrap CI、cross-pair 評価がテスト通過

---

## Phase 3: Skill 内容移植（中）

Phase 2 の基盤が揃ったら skill を移植。各 skill はほぼ独立作業。

### 3-1. `zenigame-fx-run-ga` (旧 run-alpha-factory)
- スイムレーン対応、Clause Genome 前提、archive 書き込み、(ii-lite) shadow 実行

### 3-2. `zenigame-fx-run-report`
- 1 銘柄 1 レポート、Clause 構造 summary、Stage 通過率、live_criteria 判定

### 3-3. `zenigame-fx-analyze-genome-archive`
- Parquet 読込、Clause 構造分析（n_clauses 分布、active_clause）、primitive 別貢献度

### 3-4. `zenigame-fx-analyze-run`
- 前 Run との差分、focus-theme 観点の観察、post-run-review BG 起動フック

### 3-5. `zenigame-fx-todo-add` / `zenigame-fx-todo-close`
- `docs/alpha_factory/TODO.md` 管理、`scripts/alpha_factory/todo_manager.sh` 作成

### 3-6. `zenigame-fx-alpha-design`
- 概念設計 → Codex レビュー → 詳細設計 → Codex レビュー の 4 段階

### 3-7. `zenigame-fx-plan-and-design`
- 分析マージ、改善策合議、詳細設計、TODO 選定

### 3-8. `zenigame-fx-implement`
- worktree 実装、pytest、Codex 実装レビュー、コミット、TODO クローズ

### 3-9. `zenigame-fx-batch-ga`
- 銘柄ループモード、クロスラン統計

### 3-10. `zenigame-fx-profile-optimize`
- プロファイル → ボトルネック → 設計 → 実装 → 再プロファイル

### 3-11. `zenigame-fx-recent-trends`
- 横断観測、銘柄別 best B-Sharpe 推移

### 3-12. `zenigame-fx-set-focus`
- テーマ + ターゲット銘柄

### 3-13. `zenigame-fx-strategic-codex-debate`
- Clause / primitive / 銘柄選択 を議論ターゲットに

### 3-14. `zenigame-fx-update-docs` / `zenigame-fx-update-run-metrics`
- docs/alpha_factory/ 配下の陳腐化チェック

### 3-15. `zenigame-fx-improve-cycle`（最後）
- Phase 1-5 フェーズ構造、スイムレーン対応、上記全 skill を連携

---

## Phase 4: INFRA-ADAPT skill 実装（中）

### 4-1. `zenigame-fx-calibrate-gate`
- Stage B/C の閾値を実測 gate_stats で調整
- `stage_a_pass_rate` が目標 15% から外れたら α_A を調整
- Stage B `dsr_min` を実測ばらつきで調整

### 4-2. `zenigame-fx-post-run-review`
- Claude Code の Agent (local-agent) BG セッションで走らせる
- テーマ別（signal-quality / regime / robustness 等）に分析
- 結果を devnotes に書き出し、設計・TODO 登録まで自動完結

### 4-3. `zenigame-fx-alpha-sieve`
- `scripts/alpha_factory/run_alpha_sieve.py` 新設
- Stage C 通過個体 → 別期間（直近 3 ヶ月）で backtest
- 通過: sharpe > 0.5 AND trade_count > 10 AND total_pnl > 0
- `reports/alpha-sieve/{yyyy-mm}/sieve-R{run_number}.md`

---

## Phase 5: MVP 通し動作確認（30 分）

### 5-1. `fx-improve-cycle --instrument EUR_USD` 1 サイクル実行
- 小構成: pop=20 × gen=5 / 直近 6 ヶ月データ
- 成功条件:
  - analyze-run → plan-and-design → calibrate-gate → implement (skip-todo mode) → run-ga → run-report → alpha-sieve の全 phase が完走
  - archive Parquet 書き出し
  - (ii-lite) shadow ログ出力
  - run-1.md 生成

### 5-2. 問題修正 → 再実行
- エラー箇所を特定・修正
- 2 回目の dry-run 成功で Phase 5 完了

---

## Phase 6: 本格運用層（大、実測データ後）

Phase 5 完了後、5-10 Run 蓄積してから実施。

### 6-1. `n_eff` 実測 → α キャリブレーション
- 実測 `n_eff` に基づく α の連動式を確定

### 6-2. PBO-lite 実装
- top-M=20 候補に絞った CSCV (S=6-8)
- `src/alpha_factory/statistics.py` に `pbo_lite` 関数追加
- 移行トリガーの一部として監視

### 6-3. Reality Check / SPA 実装
- ブートストラップ B=1000
- 候補圧縮後に実行
- Phase 4 まで monitor-only

### 6-4. (ii-lite) hard gate 化判定
- 30 run + 各 target 5 run 蓄積
- 通過率 median 30-70%、std ≤15pp 確認
- shadow 通過群の予測力 +0.15 / p<0.10 確認
- 条件満たせば `ii_lite.mode: hard` に切替

### 6-5. rollback 自動化
- hard 化後 10 run 以内に Sharpe 25% 低下 × 2 窓連続で shadow 戻し
- または通過率 <10% / >90% × 10 run 連続

### 6-6. 移行トリガー自動判定
- `PBO > 0.5 AND (DSR < 0 3 連続 OR fold 負比率 ≥ 0.4)` の自動監視
- 発動したら improve-cycle にアラート、(ii) への移行提案

### 6-7. max_clause 段階解放
- `active_clause_mean ≥ 1.3` 安定なら max_clause=2 解放
- さらに OOS 改善確認で max_clause=3 解放

---

## 並列化と成果物

### Phase 0-1 は直列（短時間）

### Phase 2 内で並列化可能
- 2A (docs) ← 単独
- 2B-1 (FRED ingest) ← 単独
- 2C (Clause 構造) ← 2D, 2E, 2F, 2H に先行必要
- 2D (primitives) ← 2B 完了後、32 個は並列実装可
- 2F (statistics) ← 単独

### Phase 3 内で並列化可能
- skill 移植は基本 skill 間依存で直列だが、独立 skill（recent-trends, set-focus, codex-* 等）は並列可

### 成果物

- **コード**: `src/alpha_factory/`, `scripts/alpha_factory/`, `src/ingest/fred.py`
- **ドキュメント**: `docs/alpha_factory/`
- **Skills**: `.claude/skills/zenigame-fx-*`（24 個）
- **設定**: `config/alpha_factory/default.yaml`, `focus-theme.json`
- **テスト**: `tests/alpha_factory/`, `tests/ingest/test_fred.py` 等
- **Devnotes**: 本 Phase 毎の設計 md
- **Reports**: `reports/run-reports/`, `reports/alpha-sieve/`

---

## 開始点

今セッション中に確実に終わらせたい **最小ターゲット**:

1. Phase 0（5 分）
2. Phase 1（30 分）
3. Phase 2A（ドキュメント骨格、30 分）
4. Phase 2B-1〜3（FRED ingest、1 時間）

ここまでで「基盤が立つ状態」にし、Phase 2C 以降は次セッション以降で継続。

各 Phase 完了時に独立コミット、コンテキスト圧縮対策として `.cache/alpha_factory/current_cycle_state.json` に進捗を保存。
