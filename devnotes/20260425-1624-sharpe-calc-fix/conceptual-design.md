# 概念設計: Sharpe Ratio 計算の根本修正 (bar-level annualized → trade-level + threshold)

## 背景・課題

### 観察事実 (Fact, run-9 / run-10 横断)

- Run 10 best 個体: `trade_count=3`, `total_pnl=18860`, `sharpe=18.49`, `fitness=18.48`（[reports/run-reports/run-10.md](../../reports/run-reports/run-10.md)）
- Run 9 では trade_count=0 個体が 75% を占め、Stage A 全滅（pop=20×gen=5 の小規模も寄与）
- 現実の戦略の年率 Sharpe は伝説的なファンドでも 2〜4 程度。Sharpe 18 という観測値は計算式の artifact の可能性が高い
- live_criteria は `sharpe_min=1.0` を要求 → 現状の Sharpe 計算ベースでは sharpe>=1.0 が事実上無意味化している

### コード側の前提検証 (C4 前提検証)

[src/backtest/metrics.py:34-52](../../src/backtest/metrics.py#L34-L52):

```python
BARS_PER_YEAR_M1 = int(24 * 60 * 365 * 5 / 7)  # ≈ 375,428

def _bar_returns(equity_curve):
    rets = []
    prev = None
    for _, eq in equity_curve:
        if prev is not None and prev > 0:
            rets.append(float((eq - prev) / prev))
        prev = eq
    return rets

def _sharpe(returns, periods_per_year=BARS_PER_YEAR_M1):
    if len(returns) < 2: return None
    mean = sum(returns) / len(returns)
    var = sum((r - mean)**2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(var)
    if std == 0: return None
    return (mean / std) * math.sqrt(periods_per_year)
```

`equity_curve` は **M1 全 bar**（ポジ無し時間も含む）から生成。`√375428 ≈ 612.7` で annualize。

### 解釈 (Interpretation)

- 14 日 backtest = 約 20,160 M1 bar。trade_count=3 個体ではポジ保有時間 < 1% → bar return の 99% 以上が `0`
- 「ほぼゼロの母集団 + 数本の大きな正リターン」で `mean/std` が高くなり、さらに √375428 で増幅されたと解釈する
- **i.i.d. 仮定の崩壊**: 連続的に同じリスクを取り続ける前提で annualize しているが、実態は「無ポジ時間が大半」
- GA は fitness=sharpe で選抜しているため、「スパース取引で高い sharpe を出す個体」が優遇された可能性が高い
- **注意 (C8)**: 「Run 9-10 の探索結果がすべてハック個体」とは断定しない。H2 検証（後述）で replay し反証を探すことが先決

## 影響範囲 (Fact)

| 経路 | 場所 | 用途 |
|---|---|---|
| GA fitness `metric=sharpe` | [src/ga/fitness.py:78-87](../../src/ga/fitness.py#L78) | 選抜の主軸 |
| 単一ペア Stage A | [src/alpha_factory/cross_pair.py:122-148](../../src/alpha_factory/cross_pair.py#L122) | per-pair Sharpe |
| Cross-pair (ii-lite) shadow | [src/alpha_factory/cross_pair.py](../../src/alpha_factory/cross_pair.py) | mean/min Sharpe 集計 |
| Stage C / Alpha Sieve OOS | [scripts/alpha_factory/run_alpha_sieve.py:401-402](../../scripts/alpha_factory/run_alpha_sieve.py#L401) | OOS Sharpe 判定 |
| calibrate_gate monitoring | [src/alpha_factory/calibrate_gate.py:411](../../src/alpha_factory/calibrate_gate.py#L411) | Stage A 動的閾値 |
| DSR (Deflated Sharpe) | [src/alpha_factory/statistics.py:148-198](../../src/alpha_factory/statistics.py#L148) | bar-level Sharpe 前提で計算 |
| live_criteria | config | `sharpe_min=1.0` 等の閾値 |
| 既存 archive | parquet | 過去 Run の Sharpe 列は旧計算値 |

**全 Stage の評価軸が同じバグの上に乗っている。**

## 改善アイデア — Phase 1: trade_sharpe_raw + sample-size guard

### 採用する指標の定義

**trade_sharpe_raw**（名称を `sharpe` ではなく専用名にして意味論の誤読を防ぐ）:
- 各クローズドトレードの **return 単位 = net pnl（spread/swap/slippage 控除後） / entry 直前口座 equity**（1 本に固定）
- `trade_sharpe_raw = mean(trade_returns) / std(trade_returns)`（annualize なし）
- annualize しない理由: GA fitness の比較には絶対値ではなく相対順序が重要なため選抜は機能する。短期バックテストでは trades_per_year 推定も不安定で annualize がかえって誤解を招く
- 業界標準との乖離リスク: live_criteria の閾値は `trade_sharpe_raw` ベースの値に別途再校正が必要（Phase 1B で実施）

### return 単位固定の根拠

- `pnl / equity_at_open`: 口座基準通貨に換算した net pnl を分母に entry 時点 equity を使う → cross-pair 比較可能、equity 規模に不変
- `pnl / risk_unit`: risk_unit の定義・算出経路が別途必要で複雑性が増す → Phase 1 では不採用
- **採用**: `net_pnl_base_currency / equity_at_entry`

### `equity_at_entry` の取得方法（SSOT 設計）

現行の `Trade` オブジェクトには `equity_at_entry` フィールドが存在しない。また、現行実装では `Trade` はクローズ時に `Position` から生成されるため、`Trade` に直接フィールドを追加しても multi-bar position では entry 時点 equity をクローズまで持ち越せない。

**採用**: `Position` に `equity_at_entry: float` フィールドを追加し、broker が entry 時（`Position` 生成時）に bar 開始時 pre-fill equity を記録する。`Trade` はクローズ時に `Position.equity_at_entry` をコピーして受け取る。`compute_metrics(trades)` は `trade.equity_at_entry` を使う。

- same-bar 複数 fill 時: bar 開始時の pre-fill equity を全注文共通に固定（fill 順依存不可）
- SSOT: `Position.equity_at_entry`（broker が記録）→ `Trade.equity_at_entry`（クローズ時にコピー）

代替案（`equity_curve` から引く案、sidecar map 案）は詳細設計で比較し最終決定するが、概念方針は `Position` 経由での伝搬とする。

### サンプルサイズ・ガード

- `trade_count < N_MIN` → **`trade_sharpe_raw = None`** を返す
  - GA fitness で None なら `_FAILURE_FITNESS` ✓ 既存の `metric_unavailable` 経路に乗る
  - N_MIN のデフォルト=30 は Andrew W. Lo, 2002 *The Statistics of Sharpe Ratios* が示す推定の不安定性と経験則を参照
  - ただし 30 は arbitrary な面もある → config 化し N=20/30/50 での感度分析を replay で実施（Phase 1B）

### dispatch matrix (排他)

| 条件 | trade_sharpe_raw |
|---|---|
| `trade_count < trade_count_min_for_sharpe` (default 30) | `None` |
| std(trade_returns) == 0 | `None` |
| else | `mean(trade_returns) / std(trade_returns)` |

### cross-pair における None 処理

- per-pair `trade_sharpe_raw = None` → cross-pair 集計で **fail-fast**（skip 扱い禁止）
- 理由: skip 扱いを許すと「難しいペアで無取引」が抜け道になり得る

### archive 後方互換 + canonical accessor 設計

- `sharpe` 列を上書きしない。新指標は **`trade_sharpe_raw`** という別名列として追加
- `sharpe_calc_version` 列も追加（旧=`v1_bar_annualized`、新=`v2_trade_level`）
- **reader 側 hard-fail**: 旧 archive を新版 reader で読む時に `sharpe_calc_version` が未知なら例外（warning ログだけでは不十分）

#### canonical accessor の設計

現行の `run_alpha_sieve.py`、`run_ga.py`、`calibrate_gate.py` 等が `row["sharpe"]` を直接参照しているため、`load()` 時の hard-fail だけでは v1/v2 混在を静かに通す恐れがある。

**accessor 設計（2本立て）**:

- `GenomeArchive.get_trade_sharpe(row)` — **比較用**。v2 archive → `row["trade_sharpe_raw"]` を返す。v1 archive → **必ず例外**（None を返さない）。これにより v1 行が live criteria / calibrate_gate 判定に混入することを防ぐ
- `GenomeArchive.get_legacy_bar_sharpe(row)` — **閲覧専用**（比較・判定禁止）。v1 archive → `row["sharpe"]` を返す。v2 archive → 例外。H2 検証など旧値の参照専用

全 consumer（GA fitness / Stage Gate / cross_pair / calibrate_gate / `run_ga.py` / `run_alpha_sieve.py` 含む）が `get_trade_sharpe()` 経由に切り替え、`row["sharpe"]` 直接参照は廃止。

#### `BacktestMetrics.sharpe` フィールドと report 系の扱い

`compute_metrics()` が返す `BacktestMetrics` は `report.py`、`ensemble_report.py`、`grid_search.py`、`walk_forward.py` 等の非 AF consumer も参照している。Phase 1A では **Phase 2 まで `sharpe` を壊さない** 方針を採る。

**採用方針（案X）**: `compute_metrics()` は Phase 2 まで既存の bar-level annualized `sharpe` を計算し続け、`BacktestMetrics.sharpe` フィールドに埋め続ける。新フィールド `trade_sharpe_raw` を追加し、AF consumer のみがこれを参照する。非 AF consumer（report/grid/ensemble/walk_forward）は Phase 2 まで `sharpe`（旧値）を参照し続けることで Phase 1A で破壊しない。

- `BacktestMetrics` に `trade_sharpe_raw: Optional[float]` + `sharpe_calc_version: str` フィールドを追加
- `sharpe: Optional[float]` フィールドは**維持**（Phase 2 まで旧計算値を継続して格納）
- Phase 1A の AF consumer（GA fitness / Stage Gate / cross_pair / calibrate_gate / run_ga.py / run_alpha_sieve.py）は `trade_sharpe_raw` を参照
- 非 AF consumer（report/grid/ensemble/walk_forward）は Phase 2 の別 TODO で `trade_sharpe_raw` に切り替え

**注意**: Phase 1A 完了後、システム内に `sharpe`（bar-level、非 AF consumer 用）と `trade_sharpe_raw`（trade-level、AF consumer 用）の 2 指標が共存する状態になる。混在状態はドキュメントに明記し Phase 2 で解消する。

#### `equity_at_entry` の same-bar 複数 fill 時の扱い

`equity_at_entry` は **bar 開始時の pre-fill equity**（その bar で発生した全 fill より前の equity 水準）を全注文共通に固定する。fill 順依存の可変 equity は使わない。これにより同一 bar 内複数 fill 時の実装ぶれを防ぐ。

## Phase 区切り（改訂版）

| Phase | 内容 | 本 TODO のスコープ |
|---|---|---|
| Phase 1A | `trade_sharpe_raw` 実装（`compute_metrics`）+ reader hard-fail + 全 consumer 切替 | ✅ |
| Phase 1A | GA fitness / Stage A / Stage C / Alpha Sieve / cross_pair / calibrate_gate を `trade_sharpe_raw` に切り替え | ✅ |
| Phase 1A | archive schema に `trade_sharpe_raw` + `sharpe_calc_version` 追加 | ✅ |
| Phase 1A | DSR: 呼び出し側を変えず「現状 DSR は v1 Sharpe 前提」コメントのみ追記 | ✅ |
| Phase 1B | archive replay で H1/H2 検証 + N_MIN 感度分析 (N=20/30/50) | ✅（Phase 1A 後に実施） |
| Phase 1B | live_criteria.sharpe_min の暫定再校正（replay 根拠あり） | ✅（Phase 1B で実施） |
| Phase 2 | daily-equity Sharpe (annualized) を併記オプションとして追加 | ❌ 別 TODO |
| Phase 2 | DSR の入力意味論再定義 + Phase 4 の DSR 計算統合 | ❌ 別 TODO |
| Phase 2 | live_criteria.sharpe_min の本格的なバックテスト校正 | ❌ 別 TODO |

**Phase 1B の live_criteria 変更は 禁止事項4 (閾値緩和) への抵触を防ぐため、必ず replay 根拠を先に取ること。**

## 値伝搬チェックリスト (propagation checklist)

Phase 1A 実装時に以下 7 点すべてが接続されていることを DoD の前提とする:

| # | チェック点 | 確認対象 |
|---|---|---|
| 1 | config 定義 | `trade_count_min_for_sharpe` が `default.yaml` に追加されているか |
| 2 | metrics API | `compute_metrics()` が `trade_sharpe_raw` を返すか |
| 3 | genome.meta | `trade_sharpe_raw` が genome の meta dict に注入されているか |
| 4 | archive schema | `GENOMES_SCHEMA` に `trade_sharpe_raw` と `sharpe_calc_version` が定義されているか |
| 5 | row_template / collect / flush | archive 書き込みの 4 点セットが完結しているか |
| 6 | reader hard-fail | 未知 `sharpe_calc_version` で例外を発生させるか |
| 7 | logger | `trade_sharpe_raw` の値伝搬に対応するログが追加されているか |

## 反証可能仮説 (Falsifiable hypotheses)

- **H1**: 旧 bar-level Sharpe の高い個体（>5 以上）の `trade_sharpe_raw` は大半が 0.3〜1.0 程度に縮む
- **H2**: 既存 Run 10 の best 個体 (sharpe=18.49) の `trade_sharpe_raw` を再計算すると 1 桁以下になる（Phase 1B で検証）
- **H3**: `trade_sharpe_raw` で再選抜しても上位個体の総 PnL は大きく入れ替わらない（PnL は別軸の真実）

## 成功基準 / kill criteria

### Success
- 既存 best 個体の `trade_sharpe_raw` が現実的な範囲に収まる（H2 確認）
- GA fitness が artifact を選抜しなくなる（trade_count<N_MIN 個体の上位淘汰）
- live_criteria の再校正根拠を replay で取得できる（Phase 1B 後）

### Kill
- `trade_sharpe_raw` でも全個体が同じ値（distribution flat）→ 識別性なし → 別の fitness 軸へ
- `trade_count_min_for_sharpe` を厳しくしすぎて GA が初期世代から枯渇 → N_MIN 感度分析で緩和値を特定

## 禁止事項

- bar-level annualized Sharpe を残したまま新指標を併用しない（評価軸混在を避ける）
- 既存 archive の `sharpe` 列を削除しない（旧値は残し `trade_sharpe_raw` 列を追加）
- Phase 1A で live_criteria.sharpe_min を直接変更しない（replay 根拠なしの閾値緩和は禁止事項4違反）
- Phase 1 で daily Sharpe や DSR の意味論変更まで踏み込まない（scope creep 防止）
- `trade_sharpe_raw` を外部向けに "Sharpe" と呼ばない（誤読防止）

## DoD (Definition of Done) Checklist — Phase 1A

- [ ] `compute_metrics` に `trade_sharpe_raw` (trade-level, no annualize) + `trade_count_min_for_sharpe` 引数追加
- [ ] 既存 bar-level Sharpe 計算 (`_bar_returns` / `_sharpe`) は削除（archive は旧値列 `sharpe` で残存）
- [ ] GA fitness の `metric=sharpe` 経路が `trade_sharpe_raw` を使用
- [ ] cross_pair / Alpha Sieve / calibrate_gate の Sharpe 参照を `trade_sharpe_raw` に統一
- [ ] cross-pair 集計で `trade_sharpe_raw=None` は fail-fast（skip 扱い禁止）
- [ ] archive schema に `trade_sharpe_raw` + `sharpe_calc_version="v2_trade_level"` 追加
- [ ] reader hard-fail: 未知 `sharpe_calc_version` で例外
- [ ] DSR は呼び出し側を変えず「現状 DSR は v1 Sharpe 前提、Phase 2 で対応」コメントを明記
- [ ] 値伝搬チェックリスト 7 点すべて確認
- [ ] `tests/backtest/test_metrics.py` で `trade_sharpe_raw` / sample-size guard / None 伝搬の動作テスト
- [ ] `tests/ga/test_fitness.py` で sharpe metric が `trade_sharpe_raw` を使用していることを確認
- [ ] archive schema test 更新

## DoD (Definition of Done) Checklist — Phase 1B（Phase 1A 完了後）

- [ ] H2 検証: Run 10 best 個体の bar Sharpe vs `trade_sharpe_raw` を devnote に記録
- [ ] N=20/30/50 の感度分析実施（GA 枯渇リスクと識別性のトレードオフ確認）
- [ ] replay 根拠をもとに以下の全 Sharpe 系閾値を再校正（`live_criteria.sharpe_min` だけでなく Stage Gate 系も対象）:
  - `live_criteria.sharpe_min`
  - `stage_a_threshold`（Stage A での Sharpe gate 閾値）
  - `stage_b_median_oos_sharpe_min`（Stage B 中央値 OOS Sharpe 閾値）
  - `spread_stress_min_sharpe`（スプレッドストレス時 Sharpe 閾値）
  - cross-pair の Sharpe 系 pass criteria
- [ ] 再校正は replay 根拠必須（禁止事項4: 閾値緩和の根拠なし変更禁止）

## 補足: run_ga.py summary.json の混在状態への対処

Phase 1A 完了後、`summary.json` 内に `sharpe`（bar-level、旧値）と `trade_sharpe_raw`（trade-level）が混在する状態になる。最低限 `sharpe_calc_version` を summary.json に追記し、どの世代まで旧計算か追跡可能にする。
