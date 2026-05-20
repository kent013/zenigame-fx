# 引き継ぎ書: backtest エンジンの columnar-numpy + numba 化 (wall-time 削減)

作成 2026-05-20 (JST)。 context 上限のため新セッションへの引き継ぎ。
**この文書だけ読めば再開できる**ことを目標に自己完結で書く。

---

## 0. 一行サマリ

production GA Run が wall ~6-7.6h かかる根本原因は **backtest エンジンが純 Python
の per-bar ループ over Decimal オブジェクト**であること。 姉妹プロジェクト zenigame
は同じ分足でも **numpy columnar 配列 + numba `@njit`** で <1h を達成している。
**zenigame の backtest エンジン方式を zenigame-fx に移植する**のがゴール。

---

## 1. なぜこれをやるか (診断の根拠、 全て実測/grep 済み)

### 1-1. wall-time の内訳 (Run 82 summary.json per_generation 集計, verified)
- Stage A: 7,342s / Stage B: **45,507s (83%)** / Stage C: 1,733s
- 合計 54,582s ≈ **15.2h CPU**、 max_workers=2 で wall ≈ **7.6h**
- Stage B per-bar: 60µs/bar (Stage A 12.8µs/bar の 5×) ← 構造的に複数パス
  (フル 242k IS-monitor + canonical + 8 fold)

### 1-2. zenigame との決定的な差 (両 repo を grep 実証)
| | zenigame (<1h, 9 worker) | zenigame-fx (~7.6h, 2 worker) |
|---|---|---|
| bar 解像度 | 分足 (.cache/minute_bars) | 分足 (同じ) |
| 評価対象 | stock universe を loop (多銘柄) | 単一ペア |
| **backtest ループ** | **numpy columnar + numba @njit** | **純 Python per-bar ループ** |
| bar 表現 | `DayMinuteBars.volume_array/high_array`, `close_arr=np.array([...])` | `list[PriceBar]` (Decimal × 8/bar dataclass) |
| hot path | `@numba.njit` JIT, `np.maximum.accumulate` 等ベクトル化 | `for i,bar in enumerate(bars_list)` → `bar.bid.close` (Decimal) |

- zenigame-fx の `src/backtest/engine.py` / `src/broker/mock.py` には
  **numba も numpy ベクトル化も無い** (grep 空、 verified)。
- → per-bar 10〜50× の速度差。 これが「worker 数を揃えても残るオーダーの違い」
  の正体。 **worker を増やすのは症状の希釈で根治でない** (ユーザーが worker 増を
  却下した理由)。

### 1-3. 重要: なぜ「メモリの B (scaled-int)」とは別物か
- 本セッション前半でメモリ目的の scaled-int 化を検討したが、 B-1 実測で「Decimal
  churn は RSS を暴走させない」と判明し **メモリ目的では不要**と結論
  (devnotes/20260520-1358-backtest-decimal-churn-broker/b1-findings.md)。
- しかし **wall-time 目的では、 まさに backtest hot loop の numpy/numba 化が本丸**。
  メモリと speed で結論が逆になる点に注意。 今回は **speed が目的**。

---

## 2. 現在のリポジトリ状態 (2026-05-20 時点)

- HEAD = `8ddeb3d` (branch main)。 **push なし** (SSH 鍵未ロード、 全てローカル
  コミットのみ)。
- 直近で完了済 (本セッション):
  - **T106** DB load streaming 化 (merge 済)
  - **T107** aux_pair_bars columnar 化 (merge 済) → worker RSS 9.5GB→2.5GB,
    total 23.7GB→5.8GB
  - メモリ問題は解決済。 **24GB どころか実環境は 64GB RAM / 12 physical core**
    (skill template の「24GB/6worker」は誤り)。
- `config/alpha_factory/default.yaml` の `max_workers: 2` (worker 増は revert 済、
  触らない方針)。
- worktree: `worktrees/todo-T081` が残置 (本件と無関係、 放置で可)。

### 関連 devnotes (読むと文脈が深まる)
- `devnotes/20260520-1358-backtest-decimal-churn-broker/b1-findings.md`
  (B-1 実測: churn 非支配、 scaled-int 不要)
- `devnotes/20260520-1653-stage-b-skip-nongate/conceptual-design.md`
  (Stage B skip は feasibility 逆流でブロック、 末尾に「真の解は別物」と記載)

---

## 3. 移植元 (zenigame) のキーファイル

repo: `/Users/ishitoya/repository/zenigame` (.claude/settings.local.json の
additionalDirectories で参照可)

- `src/trading/alpha_factory/evaluation/_backtest_stock.py`
  - `run_single_stock` (L179): メイン backtest。 numpy columnar 配列を事前構築
    (`_suffix_max_high = np.maximum.accumulate(...)`, `volume_array`,
    `close_arr = np.array([b.close for b in bars.bars])` L601 等)
  - `_liq_band_scale_jit` (L108): `@numba.njit(cache=True)` の hot path
  - `DayMinuteBars` (bars.bars + volume_array 等の columnar 構造) ← per-day 分足
- `src/trading/alpha_factory/evaluation/shared_bar_store.py`
  - mmap 共有 bar ストア (T474)。 worker 間で bar をコピーせず共有。 wall でなく
    RSS/起動向けだが、 numpy columnar 化と相性が良い (別途検討余地)
- `src/trading/alpha_factory/ga/parallel_eval.py` (worker dispatch, mmap attach)

注: zenigame は **株 universe**、 zenigame-fx は **単一 FX ペア + イントラデイ
強制クローズ + スワップ/スプレッド**。 ロジックは異なるので「方式 (columnar+numba)
を参考に」する。 コード共有は禁止 (AGENTS.md)。

---

## 4. 移植先 (zenigame-fx) の改修対象

### 4-1. 中心: backtest エンジン
- `src/backtest/engine.py`
  - `run_backtest(bars, strategy, broker, config)` (L95)。 hot loop は L147
    `for i, bar in enumerate(bars_list):` → 各 bar で broker.fill_pending /
    mark_to_market / apply_bar_holding_cost / strategy.on_bar を呼ぶ
  - **これを numpy columnar 配列ベース + numba JIT に再設計するのが核心**
- `src/broker/mock.py`
  - `mark_to_market` (L274): `(bar.ask.close + bar.bid.close)/Decimal(2)`,
    spread_bps 計算 → per-bar Decimal 生成
  - `apply_bar_holding_cost` (L285): per-position Decimal
  - `_snapshot_at`, fill ロジック (path-dependent な position/equity 更新)
- `src/domain/price.py`: `PriceBar` (pair_name/bar_time/bid:Ohlc/ask:Ohlc/
  volume/complete), `Ohlc` (open/high/low/close: **Decimal**)。
  → columnar 表現 (bar_time int64 epoch + bid/ask OHLC float64 or scaled-int
  配列) を新設するか検討
- `src/dsl/eval.py` (L25-32) / `src/dsl/strategy.py`:
  `DslStrategy.on_bar` / `prepare`。 mid 計算に Decimal(2) 除算。
  ※ primitive 自体は **T030 で既に float64 numpy cache 化済**
  (`src/alpha_factory/primitives/_bars_cache.py`)、 触らない。 問題は
  primitive ではなく **broker/engine の約定シミュレーション部**。

### 4-2. 呼び出し側 (backtest を回す箇所)
- `src/alpha_factory/stage_gate.py`
  - `evaluate_stage_a` (L958): `run_backtest(bars_60d, ...)` 1 回
  - `evaluate_stage_b` (L~1250-1620): フル IS-monitor `run_backtest(bars_stage_b)`
    (L1313) + 8 fold `run_backtest(test_bars)` (L1399)。 ここが 83% の本体
  - `evaluate_stage_c` (holdout backtest, L1842 / stress L1965)
- これらは `run_backtest` を呼ぶだけなので、 エンジン内部を速くすれば全 stage
  が速くなる。

---

## 5. 絶対制約 (設計時に厳守)

1. **GA 結果完全不変** (正確性最優先、 ユーザー明言)。 baseline:
   seed=9999 smoke で **best=g2_i2 / fitness=-0.02894014223533147**、 各 generation
   の A/B pass count・pass/fail vector が一致すること。 これが崩れたら即 reject。
2. **金額計算の正確性**: PnL/drawdown/Sharpe は現行 Decimal と一致が必要。
   - float64 化は丸め誤差を生む → **bit-identical が崩れる**。 使命「スワップ・
     スプレッド反映の純利益」に関わる。
   - 選択肢: (a) scaled-int (pip 整数) で exact を保つ、 (b) float64 + 許容誤差
     検証 (但し bit-identical は諦め、 GA 選抜が変わらない範囲か要検証)。
     **どちらにするかが最大の設計判断**。 ユーザーは正確性最優先と明言したので
     scaled-int 寄りだが、 numba は float64 が最も速い。 トレードオフを Codex
     合議で詰めること。
3. **feasibility 逆流に注意** (Stage B skip がブロックされた教訓):
   `is_full_trade_count → trade_count_full_dataset → _update_cache (run_ga.py:935)
   → feasibility → selection_score`。 trade 数・約定タイミングが 1 つでも変われば
   GA 選抜が変わる。 numba 化で約定判定が微妙に変わらないよう厳密一致が必要。
4. **イントラデイ強制クローズ / ロング・ショート両方向 / スワップ・スプレッド**
   を維持 (絶対制約)。
5. 禁止事項: 評価期間延長 / 閾値緩和 / GA ハック / 取引回数削減 / オーバーナイト。

---

## 6. 想定される設計判断ポイント (Codex 合議で詰める)

1. **数値表現**: scaled-int (exact, 厳密一致) vs float64 (numba 最速だが丸め)。
   → 正確性最優先なら scaled-int。 但し path-dependent な約定/equity 更新を
   numba で書けるか (numba は Decimal 非対応、 int64/float64 のみ)。
2. **ベクトル化できる部分 / できない部分の切り分け**:
   - 約定判定・position・equity は path-dependent (逐次) → numba njit ループ
   - mid/spread/indicator は事前ベクトル化可能 (一部 T030 で済)
3. **PriceBar columnar 化の波及範囲**: PriceBar を読む全箇所 (primitives は
   T030 済だが、 broker/metrics/stage_gate)。 T107 の `aux_pair_mid_close` 移植
   が良い先例 (consumer inventory → 契約 swap → 段階移植)。
4. **numba 導入コスト**: 既に依存に numba あり (zenigame と同じ環境、
   `.venv` に numba 確認済)。 JIT cache (`cache=True`) で起動コスト緩和。
5. **検証戦略**: golden test (同 seed で全 stage の決定結果・fitness が
   baseline byte 一致)。 T106/T107 で使った semantic equivalence digest パターン
   が流用できる。

---

## 7. 推奨の進め方

1. **調査先行 (低コスト)**: zenigame `_backtest_stock.py` の `run_single_stock`
   を精読し、 「どの計算を numpy 事前ベクトル化し、 どの逐次部を numba njit に
   したか」を構造マッピング。 zenigame-fx の `run_backtest` の各ステップ
   (fill_pending / mark_to_market / on_bar / holding_cost / snapshot) と対応付け。
2. **プロファイル実測**: `run_backtest` 1 本を cProfile して、 Stage B の
   60µs/bar の内訳 (どの関数が hot か) を確定。 移植の優先順位付け。
   - 簡易ハーネスは `devnotes/20260520-1358-backtest-decimal-churn-broker/
     b1_memory_attribution.py` が流用可 (real bars で run_backtest を loop)。
3. **設計フロー**: `/zenigame-fx-alpha-design` で概念設計 → Codex(gpt-5.4) →
   詳細設計 → Codex(gpt-5.3-codex)。 数値表現の判断 (5,6) を必ず Codex で詰める。
4. **実装フロー**: `/zenigame-fx-todo-add` → `/zenigame-fx-implement` (worktree
   分離、 impl-review、 merge)。 T106/T107 と同じパイプライン。
5. **検証**: golden (best=g2_i2 一致) + smoke wall-time before/after
   (stage_b_seconds_total) + 既存テスト全 pass。

---

## 8. 落とし穴 / 既知の事実 (本セッションで判明)

- primitives は **T030 で既に float64 numpy cache 済** (`_bars_cache.py:
  bars_to_mid_ohlc`)。 ここは触らない。 ボトルネックは broker/engine の約定部。
- backtest は **RNG 不使用** (engine/strategy/eval/mock grep 済) → 乱数順序の
  心配なし。
- `run_backtest` 内で `strategy.prepare()` が compute_all_bars を呼ぶ (L131)。
  Stage B は 1 IS + 8 fold = 9 回 run_backtest → 9 回 prepare。 fold ごとに
  prepare 再計算 (warmup 境界が違うので単純 slice 不可)。
- Stage B の IS-monitor (242k full backtest) は **feasibility のため skip 不可**
  (trade_count が selection に逆流)。 = 計算を減らすのでなく速くする方向が正解。
- max_workers は触らない (ユーザー却下)。 wall は per-bar を速くして解く。
- 環境: 64GB RAM / 12 core / macOS / Python 3.11 + numpy + numba。
- uv 必須。 ruff check src/ tests/ + mypy src/ 通過。 既存の pre-existing 失敗:
  `test_v31_selection_key_includes_stage_b_priority` (base main から、 無関係)、
  `archive.py:350` mypy (既存)、 `run_ga.py:196` E501 (既存) — これらは触らない。

---

## 9. baseline 数値 (検証用)
- smoke 条件: `--population-size 24 --generations 5 --max-workers <N> --seed 9999
  --no-report`
- GA 結果 baseline: **best=g2_i2, fitness_pen=-0.02894014223533147, stage_c=False**
- DB は docker `zenigame-fx-db-1` (port 15433)。 落ちてたら `docker start
  zenigame-fx-db-1` + healthy 待ち。
- production stage timing: Stage A 7342s / B 45507s / C 1733s (Run 82)
