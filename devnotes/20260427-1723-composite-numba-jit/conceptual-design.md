# 概念設計: composite per-bar 計算の Numba JIT 化（dict → ndarray, fused kernel）

## 1. 背景・課題

### 1.1 観測事実（cProfile, profile_20260427_171823）

- 計測条件: `python -m cProfile` で `run_ga.py --no-report --max-workers 1 --population-size 8 --generations 1 --instrument EUR_JPY --start 2026-03-01 --end 2026-03-15`（profile 整合性のため worker 並列を 1 に固定。skill 規約準拠）
- 総時間: 5.246s / 16 backtests / 14351 bars per backtest
- Stage A pass = 0/16 → Stage B/C コストは観測不可（**INCONCLUSIVE**）
- Stage A 経路 (`engine.py:run_backtest`) cumtime = 3.427s（全体の 65%）

#### Stage A 内の主要関数 cumtime
| 関数 | cumtime | tottime | ncalls |
|------|---------|---------|--------|
| `strategy.py:on_bar` | **1.165s (22%)** | 0.512s | 229616 |
| `mock.py:fill_pending` | 0.747s (14%) | 0.098s | 229616 |
| `strategy.py:prepare` (precompute) | 0.622s (12%) | — | 16 |
| `mock.py:_snapshot_at` | 0.697s | 0.350s | 918480 |
| `composite.py:compute_clause_score` | 0.402s | 0.120s | 459232 |
| `composite.py:compute_composite` | 0.379s | 0.145s | 229616 |
| `composite.py:compute_dir_score` | 0.251s | 0.208s | 459232 |

**`on_bar` 内で composite 経路（`compute_composite` + `compute_clause_score` + `compute_dir_score`）が cumtime ベースで dominated している。**

### 1.2 本番外挿（pop=96, gen=60, stage_a window=60d）

外挿の精度向上のため、bars 比は **calendar day 比ではなく実 bar 数比** で計算する（Round 1 [High] H2 反映: FX は週末欠損のため day 比 = bar 数比とは限らない）。

- profile_total_evals = 8 × (1+1) = 16
- prod_total_evals = 96 × (60+1) = **5856**
- evals_scale = **366×**
- profile bars/backtest = 14351（実測）
- bars_scale_a = `actual_stage_a_bars / 14351`（**詳細設計時に baseline run の Stage A bar 数を実測して確定**。暫定推定: 60 日 stage_a window で M1 数 ≈ 60d × 24h × 60min × 営業日比 0.71 ≈ 61300 bars → 約 4.27×。ただし暫定値であり、最終外挿は実測値を使う）
- 複合スケール（暫定）= ~1560×

#### 本番 96×60 での Stage A 推定（Stage B/C は INCONCLUSIVE）
- on_bar cumtime 外挿（暫定）: 1.165 × 366 × 4.27 ≈ **1820s ≒ 30 分**
- run_backtest 全体外挿（Stage A、暫定）: 3.427 × 366 × 4.27 ≈ **5360s ≒ 89 分**

**single-process（`--max-workers 1`）で 90 分前後。並列化（`--max-workers 6`）でも Stage A だけで 15-25 分のオーダー。**

> ⚠ **bars_scale_a の確定**: Phase 7 の効果評価では bars_scale_a を **実測 bar 数比**で再計算し、暫定値による誤差を排除する。詳細設計でこの計算手順を明文化する。

### 1.3 ボトルネックの構造的原因

`on_bar` の prepared path（src/dsl/strategy.py:285-308）:

```python
for dir_entries, gate_entries in prepared.clauses:
    vals: dict[str, float] = {}
    for name, arr in dir_entries:
        v = arr[idx] if 0 <= idx < len(arr) else 0.0
        vals[name] = 0.0 if not math.isfinite(v) else float(v)
    for name, arr in gate_entries:
        v = arr[idx] if 0 <= idx < len(arr) else 0.0
        vals[name] = 0.0 if not math.isfinite(v) else float(v)
    values_per_clause.append(vals)
composite = compute_composite(self._genome.clauses, values_per_clause)
# 観測用にもう一度 compute_clause_score を呼ぶ (T037)
for ci, (clause, vals) in enumerate(...):
    if compute_clause_score(clause, vals) != 0.0:
        self._active_clause_indices.add(ci)
```

問題点:
1. **per-bar に dict allocation + hashing**: clause × signal 個の dict 構築が 229616 回
2. **composite.py 内で `values[sig.name]` の dict lookup を多重に行う**（compute_dir_score / compute_gate / compute_clause_score の各層）
3. **観測用 `compute_clause_score` の重複呼び出し**: clause score を per-bar に **2 回**計算（composite 内で 1 回 + active_clause 集計で 1 回）
4. **Numba 未導入**: パターン7（NumPy fused kernel）が未適用

### 1.4 Stage B/C への波及（INCONCLUSIVE）

**[Round 1 High H1 反映: 線形効果主張を削除]**

Facts:
- profile では Stage B/C 通過個体ゼロのため、Stage B/C の per-genome コストは観測されていない（**INCONCLUSIVE**）
- Stage B/C も `engine.run_backtest` → `DslStrategy.on_bar` を通る（同 engine 経路の共有）

Interpretation:
- 同じ engine 経路を kernel 化するため、**同方向の改善が期待できる**（per-bar overhead が支配的なら）
- ただし**効果量（倍率）は未検証**である。Stage B/C が dominant な fold/window 構成のため、Stage A と異なるオーバーヘッド成分（fold 切替、window slicing 等）が比率を変える可能性がある
- 効果量の確定は **Stage B/C 通過個体が出た RUN での実測**を待つ（Phase 7 効果評価で観測可能なら数値を入れる、観測できなければ INCONCLUSIVE 維持）

注: 前提 config では `dataset` 期間（約 6 ヶ月）が `stage_b.window_months=18` より短い。Stage B が前提通り 18 ヶ月 window で評価されているか自体も詳細設計時に再確認すべき要件であり、本概念設計では**踏み込まない**。

---

## 2. 改善アイデア

zenigame の高速化メソドロジー **パターン2（Numba JIT 化）+ パターン7（NumPy fused kernel）+ パターン4（precompute）** のハイブリッドを適用する。

### 2.1 中核アイデア

**`prepare()` 時に Genome 構造を flat ndarray に展開し、`on_bar` の per-bar 計算を Numba njit fused kernel に集約する。**

- per-bar `dict` → **flat ndarray** + offset 配列で表現
- per-bar Python ループ → **`@numba.njit(cache=True)` の単一 kernel 呼び出し**
- composite + per-clause score を **同一 kernel 内で同時計算**（観測用の重複計算排除）

### 2.2 zenigame の実証パターン

- clause-composite Numba fused kernel 化: **46s → 18s（60% 削減）**
- ATR pandas-ta → Numba: **214× 高速化**
- これを FX の composite per-bar に適用する（FX で初の Numba 導入になる）

---

## 3. 期待効果

### 3.1 定量目標（Round 1 Medium 反映で一段保守側に下方修正）

**on_bar 1.165s と composite path tottime 0.473s の差分（≈0.69s）の全額を Numba 化対象とは仮定しない**（warmup 判定 / prepared 分岐 / T037 集計 / ヒステリシス / 発注ロジック等が含まれる）。Numba 化で削減できる対象は composite path 0.473s + dict allocation/lookup 寄与分（Phase 7 で実測する）。

- on_bar cumtime 削減率: **40-65%**（保守目標 40%、stretch 65%。zenigame clause-composite 実績は 60% だが Stage A engine 全体 vs composite per-bar の構造差を考慮）
- 本番 96×60 stage_a での短縮: **~12-20 分/run**（30 分 → 10-18 分相当、暫定 bars_scale=4.27 を Phase 7 で実測補正）
- Stage A 全体の `run_backtest` 削減: **14-22%**（理論上限。on_bar/run_backtest = 1.165 / 3.427 ≈ 34% × on_bar 削減率 40-65%）
- Stage B/C への波及効果: **INCONCLUSIVE**（同方向の期待はあるが効果量は未検証。Phase 7 で観測可能なら実測）

### 3.2 使命への貢献

- 直接的な live_criteria 達成への貢献はない（**速度改善であって閾値・指標の操作ではない**）
- ただし RUN 1 回あたりの所要時間短縮 → **同じ wall-clock 予算でより多くの GA generation / population / lane を回せる** → 探索空間カバレッジ向上 → 使命達成確率の向上（間接効果）
- Phase 2 で計画されている `pop=96, gen=60` スケールアップを現実的な実行時間（30-60 分/run）に収めるための前提整備

---

## 4. 実装方針（概要）

### 4.1 データ構造の前計算（`prepare()` 時）

**[Round 1 High H3 反映: unique signal matrix + index indirection]**

現行 `prepare()` は同一 `(name, params)` の ndarray を `arrays` dict で **共有キャッシュ**している。同 primitive が複数 clause に出現してもメモリは 1 個のみ（`PreparedSignals.arrays`）。本設計はこの不変条件を維持する。

Genome の clause/signal 構造を以下の通り展開:

- `clause_weights: float64[n_clauses]` — 各 clause の weight
- `dir_weights_flat: float64[total_dir]` — 各 clause の directional signal weight を連結（occurrence 順）
- `dir_offsets: int64[n_clauses+1]` — clause 境界（CSR 形式）
- `dir_signal_idx: int64[total_dir]` — 各 directional occurrence の **unique signal matrix 行 index**
- `gate_offsets / gate_signal_idx` — local_gate 用（**gate に weight は無い**: 既存 `compute_gate` と同じ「値の積のみ」仕様。Round 2 Warning 反映）
- `unique_signal_matrix: float64[n_unique_signals, n_bars]` — **unique (name, params) 毎に 1 行**のみ（既存 `arrays` dict を行スタックして構築）

これらは prepare() の最後で 1 回だけ構築（per-bar コストなし）。`PreparedSignals` を拡張して保持。

**メモリ概算（Stage A, n_bars=86400, n_unique_signals=10 想定）**:
- `unique_signal_matrix`: 10 × 86400 × 8B = **6.6 MB / genome**
- duplicate signal がある場合でもメモリ重複なし（既存設計と同じ）

**メモリ概算（Stage B, n_bars=540万 ÷ 5min ≈ 100万 / M1 で約 39万 bars 想定）**:
- 上記の数倍（~30 MB / genome）— ただし詳細設計時に Stage B の実 bar 数を実測する

### 4.2 Numba njit fused kernel

```python
@numba.njit(cache=True, fastmath=False)
def compute_composite_at_bar_jit(
    idx: int,
    clause_weights: np.ndarray,        # [n_clauses]
    dir_weights_flat: np.ndarray,      # [total_dir_occurrences]
    dir_offsets: np.ndarray,           # [n_clauses+1]
    dir_signal_idx: np.ndarray,        # [total_dir_occurrences] - row index
    # gate side does NOT carry weights (gate is product, not weighted sum)
    gate_offsets: np.ndarray,          # [n_clauses+1]
    gate_signal_idx: np.ndarray,       # [total_gate_occurrences] - row index
    unique_signal_matrix: np.ndarray,  # [n_unique_signals, n_bars]
    out_clause_scores: np.ndarray,     # [n_clauses] — 観測用 buffer (preallocated)
) -> float:
    # 1 関数内で:
    # 1) 各 clause の dir_score = Σ(w × x) / Σ|w|（x は unique_signal_matrix[dir_signal_idx[k], idx] で参照）
    # 2) gate = Π gate_j （非有限値・0 ガード保持。weight は使わない: 既存 compute_gate と同じ「値の積のみ」契約を維持）
    # 3) clause_score = dir_score × gate を out_clause_scores[ci] に書き込み（毎 bar 全 clause を上書き）
    # 4) composite = Σ(cw × cs) / Σ|cw|
    # を fused に実行する
    ...
```

**[Round 2 Warning 反映]** kernel 引数から `gate_weights_flat` は削除した。既存 `compute_gate` 仕様（値の積のみ、weight 不使用）と整合させ、将来の意図しない回帰（gate に weight を掛けてしまう）を構造的に防ぐ。gate weight を本当に使う場合は別 TODO で composite.py の API 拡張から始めるべき。

`fastmath=False` で IEEE 754 演算順序を保ち、既存の純 Python 実装に対し `np.allclose(atol=1e-6, rtol=0)` を満たす。

**[Round 1 Medium 反映: bit-identical 主張を削除]**: 完全に bit-wise 同一は保証せず、tolerance-based equivalence（`atol=1e-6, rtol=0`）を契約とする。

### 4.3 on_bar の prepared path 切替

- dict 構築 ＋ `compute_composite` 呼び出し ＋ active_clause ループ → **`compute_composite_at_bar_jit(...)` 1 回**で置換
- 戻り値の `out_clause_scores` 配列から `active_clause_indices.add(ci) if score != 0.0` を判定（**T037 semantics 維持**: exact `!= 0.0`、判定を `abs(score) > eps` 等に変えてはいけない。Round 1 Low 反映）
- kernel は **毎 bar に out_clause_scores 全体を上書き**する（途中 clause で計算をスキップしない）
- unprepared path（live feed / paper trading）は **既存実装をそのまま残す**（Numba 化のリスクを後段に隔離）

### 4.4 既存 Pure Python 関数の扱い

`composite.py` の純 Python 関数（`compute_dir_score`, `compute_gate`, `compute_clause_score`, `compute_composite`）は **削除しない**:
- unprepared path（live feed）が引き続き使う
- 既存テスト互換性
- 純 Python リファレンス実装として Numba kernel の数値同値性 oracle にも使う

---

## 5. 制約・前提

### 5.1 数値精度（既存契約の保持）

- 演算順序を変更しない（Σ(w × x) / Σ|w|、weight 0 ガード、math.isfinite 処理）
- `np.allclose(atol=1e-6, rtol=0)` で baseline と一致
- `fastmath=False` で IEEE 754 を厳守

### 5.2 既存契約の保持

- ValueError 契約（clauses 空、長さ不一致）→ **prepare() 時に validate**（per-bar に raise しない）
- non-finite 値 → 0.0 への置換 → **kernel 内で `if not isfinite(v): v = 0.0`**
- signal.name 一意性 → **既存 `_validate_unique_names_in_clauses` を維持**（kernel 入力前提）
- Genome immutability → **既存 frozen dataclass + MappingProxyType を維持**

### 5.3 Stage A/B/C 通過判定の不変性（最重要）

**[Round 1 Medium 反映: bit-identical → tolerance-based equivalence に統一]**

- aggregate metrics: backtest 完了時の summary（fitness_pen, sharpe, sortino, calmar, trade_count, max_drawdown_pct, stage_a_pass, stage_b_pass, stage_c_pass）が baseline と `np.allclose(atol=1e-6, rtol=0)`
- 同一 seed・同一 config で **archive Parquet の per-genome 値が tolerance-based equal**（baseline run_id の Parquet と diff）
- T037 active_clause_indices: per-bar exact `clause_score != 0.0` semantics を維持（exact parity test を別途用意。tolerance を入れない）
- **ゼロ近傍ケースの取扱い（Round 2 Warning 反映）**: aggregate が allclose を満たし、かつ T037 だけが exact parity を破るケース（例: 純 Python では `score = +0.0`、kernel では `score = -0.0` で `!= 0.0` 判定が等価でも、極小値で `1e-300` 等の "denormal noise" が出る）が出た場合は、**T037 parity を優先**し詳細設計でフラグを立てる。原因究明（演算順序差・rounding mode 差）まで進めて修正案を出してから merge する。allclose だけで合格としない

### 5.4 FX 絶対制約（不変）

- イントラデイ強制クローズ → 触らない（engine.py / strategy.py 上位ロジック）
- ロング・ショート両方向 → 触らない
- swap・spread 反映 → 触らない（broker mock は対象外）
- 本変更は **数値計算のみ**

### 5.5 Numba 導入に伴う前提（Round 1 Medium 反映で詳細化）

- **FX 初の Numba 依存**追加（pyproject.toml に numba を追加）
- **JIT compile cache** (`.numba_cache/` or 既存 cache パス) のディレクトリ管理
- numba バージョン互換: **Python 3.13 + numpy 2.x との互換性を詳細設計時に verify**（numba 0.61+ が必要、要確認）

**ベンチマーク条件の分離（Phase 7 効果評価で必須）**:
1. **warm cache 条件**（`.numba_cache/` 既にあり）— 通常運用想定。本評価が削減率の primary metric
2. **cold cache 条件**（cache 削除後の初回起動）— CI / 短時間検証 run のリスク評価
3. **`--max-workers 6` 並列条件** — worker fork 後の cache 共有 / 再 compile 挙動の検証

これら 3 条件を分けないと「短時間 run で改悪」を見逃す。Phase 7 では少なくとも warm + cold 2 条件で計測し、改悪が出る場合は受容可否を別途判断。

### 5.6 メモリ制約

- 24GB マシン × 6 ワーカー（1 ワーカー最大 3GB）
- `unique_signal_matrix[n_unique_signals, n_bars]`（**Round 1 High H3 反映: occurrence ベースではなく unique signal ベース**）:
  - Stage A: n_unique_signals=10 想定, n_bars=61300（実 bar 数で再計算予定） → 約 4.7 MB / genome
  - Stage B: n_unique_signals=10 想定, n_bars=詳細設計で実測 → ~30 MB / genome（暫定）
- duplicate signal によるメモリ重複は発生しない（既存 `arrays` dict 共有キャッシュと同じ不変条件）

---

## 6. スコープ外（今回扱わない）

- `mock.py:fill_pending` / `_snapshot_at` の Decimal 演算最適化（候補 #2、別 TODO）
- `_indicators.py` の Numba JIT 化（`_wilder_smooth`, EMA, RSI, ADX 等。候補 #3、別 TODO）
- per-bar info ログの DEBUG 降格（候補 #4、別 TODO）
- Stage B/C 専用の評価経路最適化（INCONCLUSIVE。実測再評価後に判断）
- `compute_all_bars` 段の primitive 計算最適化（既に prepare 時 1 回キャッシュ済）

これらは **本 TODO の効果検証後（Phase 7 再プロファイル）**、改善率と残ボトルネックを見て次サイクルで判断する。

---

## 7. 検証計画（概要、詳細設計で具体化）

1. **同値性テスト**（必須）: 既存 `compute_composite` と新 kernel の比較を pytest で（property-based / sample genome）。aggregate は `np.allclose(atol=1e-6, rtol=0)`、T037 active_clause は exact parity（`!= 0.0` semantics）。
2. **既存テスト全パス**: `uv run pytest tests/alpha_factory/ tests/backtest/ tests/dsl/ -x`
3. **archive Parquet diff**: baseline run と最新 run で genome 単位の主要指標が `np.allclose(atol=1e-6, rtol=0)`
4. **再プロファイル効果評価**:
   - **warm cache 条件**で on_bar cumtime 削減率 40-65% を満たすか
   - **cold cache 条件**での悪化幅を計測（CI / 短時間検証 run のリスク評価）
   - **bars_scale_a を実測 bar 数比で再計算**して本番外挿時間を Phase 7 で確定
5. **Stage A/B/C pass 数の不変**: 同一 seed・config で counts が一致（数値精度内）
