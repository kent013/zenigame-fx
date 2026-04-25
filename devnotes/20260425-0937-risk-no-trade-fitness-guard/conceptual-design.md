# 概念設計: 無取引優位の遮断設計 (risk-no-trade-fitness-guard)

## 背景・課題

### Run 9 で観測された Verified な現象

- 全 120 行 (6 世代 x 20 個体) で `stage_a_pass=0`, `stage_b_pass=0`, `stage_c_pass=0`, `graduated=0`
- best 個体: `g0_i1`, `selection_score=[0,0,0,0.0]`, `trade_count=0`
- archive 集計: `trade_count=0` が 90 個体 (75%)、`trade_count>0` が 30 個体
- `trade_count>0` 個体の sharpe は全て負 (min=-93.10, max=-4.76) → `fitness_pen` 大きく負
- `trade_count=0` 個体は archive 上で `fitness_pen=0.0` (fact 経路は下記)
- best_fitness は全 6 世代で 0.0 plateau

### Verified な因果列 (C4)

1. `evaluate_stage_a` で `trade_count<1` の場合、`reasons=("no_trades",)` で `fitness_pen=None` のまま `payload` に格納される (`src/alpha_factory/stage_gate.py:302-307`)
2. archive `collect_stage_a` は payload を `_required_float(default=0.0)` で読み込むため、`fitness_pen=None` → **0.0 として archive 行に格納** (`src/alpha_factory/archive.py:339`、`_required_float` は `:212-216`)
3. `run_ga._update_cache` が archive 行から `fitness_pen` を float 化して `IndividualCacheEntry.fitness_pen` に格納 (`scripts/alpha_factory/run_ga.py:456-467`)
4. `selection_score = (stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen)` の辞書式比較で、全員 stage_*_pass=0 の場面では fitness_pen が tie-break (`scripts/alpha_factory/run_ga.py:110-118`)
5. `_tournament` (`:363-370`) と elite sort (`:382-386`) と `_select_best` (`:470-475`) が全てこの selection_score を使うため、**`trade_count=0, fitness_pen=0.0` 個体が `trade_count>0, fitness_pen<0` 個体に勝つ**

### 構造的根本原因

`evaluate_stage_a` は `no_trades` reason を出すが、その `fitness_pen` は **None → 0.0** として archive に正規化される。Stage 通過 bit が全員 0 の局面で fitness_pen tie-break が走ると、無取引個体が不当に survive する。

これは禁止事項 #6「取引回数を削減して見かけの成績を上げる」の構造的・自然発生バージョン。ルール緩和をしていなくても、評価関数の正規化規則が「取引しないほど有利」を生む。

### 副次的問題

- `max_drawdown=0.0` が常態化（取引が極端に少ないため）→ リスク制御の動作テストすら未到達
- Stage B/C 通過がゼロ → live_criteria 同時充足パスの設計欠陥が発見できない
- DD 制御 / max_pos 等のリスク統制機能の検証性そのものが失われている

## 改善アイデア

`stage_a` の `no_trades` (および `min_exposure_trade_count` 未達) 個体について、archive 行の `fitness_pen` を **明示的に大きい負値 sentinel** で書き込む。これにより GA selection_score の tie-break で取引する個体が必ず勝つ。

### 具体仕様

- `StageGateConfig` に `min_exposure_trade_count: int = 1` を追加 (不変条件: `0 < min_exposure_trade_count < live_criteria.trade_count_min`)
- `evaluate_stage_a` 内で `trade_count < min_exposure_trade_count` の判定を **`no_trades` の代わりに / と並んで** 行い、payload の `fitness_pen` に **有限な大負値 sentinel** を入れる (例: `_NO_EXPOSURE_FITNESS = -1e9` — 後述の sentinel 序列で確定)
- `_required_float` 経路を変更しない (sentinel をきちんと payload に入れることで 0.0 fallback を回避)
- `reason_codes` に `no_exposure` を追加 (既存 `no_trades` を置き換え or 並存)
- `config/alpha_factory/default.yaml` に `stage_gate.min_exposure_trade_count` を追加し、`config.py` の loader (`StageGateConfig` 構築箇所) でも読み込む

### Sentinel 序列の明確化（全 fitness_pen=None 経路を網羅）

Stage A で `fitness_pen=None` のまま payload に入る経路は **3 つ存在**:

| 経路 | 現状 (archive 経由後) | 本提案後 |
|------|---------------------|---------|
| system_failure (例外) | 0.0 fallback (悪性) | sentinel `_SYSTEM_FAILURE_FITNESS = -1e12` を payload に入れる |
| no_trades / no_exposure (trade_count < min_exposure_trade_count) | 0.0 fallback (悪性) | sentinel `_NO_EXPOSURE_FITNESS = -1e9` を payload に入れる |
| metric_unavailable (sharpe is None) | 0.0 fallback (悪性) | sentinel `_METRIC_UNAVAILABLE_FITNESS = -1e6` を payload に入れる |
| below_threshold | 実値 (正常) | 変更なし |

**序列**:

```
system_failure (-1e12) < no_exposure (-1e9) < metric_unavailable (-1e6) < below_threshold (実値) < 通常 fitness_pen
```

**意味**:
- system が壊れた個体は再現性がないため最も厳しく罰する
- 取引が成立しなかった個体は次に厳しく罰する (リスク評価不能)
- metric が計算不能な個体 (取引はあるが std=0 等) は中程度に罰する (取引するだけ no_exposure よりはマシ)

**重要**: Round 2 指摘を受け、`no_exposure` だけ sentinel 化すると `system_failure` / `metric_unavailable` の 0.0 fallback が残り、序列定義が自己矛盾になる。本提案では **3 経路全てに sentinel を導入**して整合性を取る。

### 重要な設計原則

- **`live_criteria.trade_count_min` の閾値は弄らない** (禁止事項 #4)
- **`min_exposure_trade_count` 初期値は 1** (live_criteria_min=50 の 2% — ハードゲート効果を最小化)
- **`fitness_raw` は変更しない** (観察値は保持。ペナルティは `fitness_pen` のみ)
- **GA 選択ロジック (`run_ga.py` の `selection_score` 等) は触らない** (sentinel を archive 経由で渡すだけ)
- **archive schema 変更は今回行わない** (Phase 1 は selection 修復のみ)

## 期待効果

### Verified な効果 (確実に言える範囲)

- **`trade_count=0` 個体の構造的優位を解消**: selection_score tie-break で取引する個体が常に勝つ (混合集団前提)

### 仮説に降格

- **`best` 個体が `trade_count=0` 状態で plateau する現象の解消** — 全個体 no-trade の場合は依然 plateau し得る。混合集団かつ少なくとも 1 個体が trade_count > 0 で正の fitness_pen を持つ場合に成立

### 仮説 (反証実験で要確認)

- **正 sharpe 個体の発生**: 取引する個体に GA 選択圧が向くことで、世代を経て正 sharpe 個体が現れる素地
- **Stage A pass の改善**: stage_a_threshold 超え個体が選抜されやすくなる
- **max_drawdown 実測値の出現**: 取引する個体が選ばれることでリスク制御の動作テストが入る

### 反証設計

- 3-5 seed で `best_no_trade_rate`、`stage_a_pass_count`、`trade_count=0 比率` を比較
- 成功判定: `best_no_trade_rate=0` かつ `stage_a_pass_count > 0` (緩い閾値)
- 仮説の追加検証: 正 sharpe 個体出現 / Stage B 到達は **次サイクル以降の観察対象**

## 実装方針（概要）

| コンポーネント | 変更内容 | 必須度 |
|---------------|---------|--------|
| `src/alpha_factory/stage_gate.py` | `StageGateConfig` に `min_exposure_trade_count` 追加 / `evaluate_stage_a` の `trade_count` 判定強化 / `fitness_pen=_NO_EXPOSURE_FITNESS` を payload に入れる / `reason_codes` に `no_exposure` 追加 | Critical |
| `src/alpha_factory/config.py` | `StageGateSection` (or 同等) に `min_exposure_trade_count` 追加 / loader 経路 | Critical |
| `config/alpha_factory/default.yaml` | `stage_gate.min_exposure_trade_count: 1` の追加 | Critical |
| `tests/alpha_factory/test_stage_gate.py` | 既存 `no_trades` テストの更新 + 新規 `no_exposure` 振る舞いテスト | Critical |
| `tests/alpha_factory/run_ga` 系 | 「`trade_count=0, fitness_pen=sentinel` 個体が `trade_count>0, fitness_pen=負実値` 個体に負ける」回帰テスト | High |
| `src/ga/runner.py` | **変更なし** (Alpha Factory 本流からは呼ばれない別系統) | — |
| `src/alpha_factory/archive.py` | **変更なし** (sentinel が payload に乗ることで `_required_float` の default fallback が回避される) | — |
| `scripts/alpha_factory/run_ga.py` | **変更なし** (selection_score ロジックは現状維持) | — |
| `src/alpha_factory/calibrate_gate.py` | **sentinel 値を `fitness_pen_pool` 集計から除外する** (現状は archive 全行をそのまま quantile に入れる為 sentinel 混入で threshold が不当に低くなる)。**フィルタ条件: 3 sentinel 値 `{_SYSTEM_FAILURE_FITNESS, _NO_EXPOSURE_FITNESS, _METRIC_UNAVAILABLE_FITNESS}` への明示一致除外** (閾値分離ではなく値一致 set membership で判定 — `fitness_pen` の通常実値 (=sharpe - α·size_norm) は sharpe に下限 clamp が無いため理論上 sentinel 帯と被る可能性があり、閾値分離は安全でない) | Critical |
| `docs/alpha_factory/stage-gates.md` | reason_codes canonical 語彙に `no_exposure` を追加、`min_exposure_trade_count` 仕様、sentinel 序列を SSOT 化 | Critical |

## 制約・前提

- イントラデイ前提 (変更なし)
- ロング・ショート両方向 (変更なし)
- `evaluate_stage_a` の `payload['fitness_pen']` が None ではなく sentinel 値で通る (archive 側の `_required_float` 挙動は変更しない)
- 既存テスト：`reason_codes` の集合論として `no_trades` が `no_exposure` に置き換わる場合は影響あり (要更新)
- C4 検証で確認した因果列が次回 Run でも再発する前提

## スコープ外

- `live_criteria.trade_count_min` の変更 (禁止事項 #4)
- `live_criteria` 全般の閾値変更
- Stage B/C の閾値変更
- `fitness_raw` の変更
- `_FAILURE_FITNESS` 値の変更
- max_pos / max_dd / time_stop 等の他リスク統制 (別 TODO)
- 評価指標の根本変更 (sharpe → 別 metric)
- complexity penalty (`α * size_norm`) の構造変更
- archive schema への列追加 (例: `no_exposure_penalty` 列) — 必要ならフェーズを分けて別 TODO
- `src/ga/runner.py` の修正 (Alpha Factory 本流からは使われない別系統)

## 学術引用・先人の知恵

- López de Prado (2018) "Advances in Financial Machine Learning" Ch.7 — backtest overfitting 防止に「取引せず」設計の除外を含む
- Luke & Panait (2006) "A Comparison of Bloat Control Methods for GP" — penalty による選択圧設計の基礎
- 本提案は「取引不能個体を有限 sentinel で罰し、selection_score tie-break で活性個体に劣後させる」という GP/GA 分野の死戦略除外則の zenigame-fx への具体化

## 想定リスク・副作用

- **risk-1**: `min_exposure_trade_count` を高く設定しすぎると、初期世代で全員 sentinel → GA 機能不全。**緩和策**: 初期値は 1 (live_criteria_min=50 の 2%) に固定、不変条件 `min_exposure_trade_count < live_criteria.trade_count_min` を `__post_init__` で強制
- **risk-2**: sentinel 値選択ミスで数値演算の副作用 → **緩和策**: 有限値 (-1e9) に統一し、sentinel 序列を design doc に明記
- **risk-3**: `calibrate_gate.py` の `fitness_pen_pool` 集計に sentinel が混入し threshold が不当に低くなる → **3 sentinel 値の明示一致 set membership 除外で対処** (閾値分離は通常実値が sentinel 帯と被るリスクがあるため不採用)
- **risk-4**: 既存テストの `reason_codes` assert が破壊される → **詳細設計で全 stage_gate テストを棚卸し、no_trades / no_exposure の関係を整理**
- **risk-5**: archive 上で `trade_count=0` 個体の `fitness_pen` 値が大きく変わる → 過去 archive との比較解析時に解釈ガイドが必要 (run-report への注記で対応)
