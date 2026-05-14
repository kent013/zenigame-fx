# 詳細設計: Run 75 施策 (cycle 22)

## 合議ステータス: **APPROVED (Round 3, 2026-05-13 20:38)**

design-review 合議:
- Round 1 (2026-05-13 20:32): CHANGES_REQUESTED — 3 Critical / 3 Warning / 1 Suggestion
- Round 2 (2026-05-13 20:36): CHANGES_REQUESTED (残り小) — 2 Warning (sum_oos_total_pnl 追加 / finite guard 隔離)
- **Round 3 (2026-05-13 20:38): APPROVED** — 全 Critical / Warning RESOLVED

### Round 3 実装時受入条件 (Codex 追加要求)

- **`len(oos_total_pnls) < n_fold_effective` のケースを fail-closed にする** — 非有限 PnL fold を黙って除外したまま残り fold だけで profit_safe_pfr 判定 pass を許さない。reason code: **`oos_total_pnl_unavailable`** を追加。

```python
# evaluate_stage_b 内、profit_safe_pfr 判定の前 (4 条件チェック前) に追加:
if stage_config.stage_b_gate_kind == "profit_safe_pfr":
    if len(oos_total_pnls) < n_fold_effective:
        reasons.append("oos_total_pnl_unavailable")  # Round 3 fail-closed
    # 続いて 4 条件 AND...
```

new known_reason_codes に `"oos_total_pnl_unavailable"` も追加 (合計 5 個追加)。


## 使命・制約（絶対遵守）

`zenigame-fx-codex-review` 継承の使命・禁止事項。FX 固有制約:
- イントラデイ前提（オーバーナイト保有を前提にする設計は避ける）
- ロング・ショート両方向許容
- スワップ・スプレッドを fitness に反映（純利益）

---

## 施策一覧

| # | 施策名 | 変更ファイル | target_metric |
|---|--------|------------|--------------|
| C1 | T099 MODIFY: Stage B gate に `profit_safe_pfr` opt-in mode 追加 | `config.py` / `stage_gate.py` / `archive.py` / `run_ga.py` / tests / `stage-gates.md` | Stage B median_oos_total_pnl ≥ 0 達成率 / Stage C pass count / Stage B 通過群 median total_pnl |

---

## C1: Stage B gate `profit_safe_pfr` opt-in mode

## Codex Round 1 (2026-05-13 20:32) で REQUEST_CHANGES → Round 2 修正適用
## Codex Round 2 (2026-05-13 20:36) で CHANGES_REQUESTED (残り小) → Round 3 追加修正

Round 1 + Round 2 統合修正点:
1. **post-filter (trade_sharpe_stage_b > 0) を削除** (Round 1 Critical 解消)
2. **config 4 段伝搬** (Round 1 Critical 解消)
3. **NaN/finite guard**: fold loop で `math.isfinite(bt.total_pnl)` check
4. **test_archive.py 列集合 assertion 更新** (Round 1 Warning)
5. **generate_run_report.py known codes 追加** (Round 1 Warning)
6. **StageGateConfig.__post_init__ 範囲検証** (Round 1 Suggestion)
7. **fold_exception 時の total_pnl 扱い**: unavailable 扱い (= 中央値計算から除外)
8. **(Round 3 新規) `sum_oos_total_pnl >= 0` を gate 条件に追加** (Round 2 Warning): median だけだと「11 fold 小プラス + 9 fold 大マイナス」で aggregate 赤字を許容するため、sum も判定
9. **(Round 3 新規) finite guard を profit_safe_pfr 専用に隔離** (Round 2 Warning): `fold_total_pnl` 非有限でも `fold_sharpe` / `fold_reason` を変えず、`oos_total_pnls` に入れないだけ。legacy 判定経路は完全不変

### target_metric / failure_mode / causal_path / falsification / success_criterion

- **target_metric**: profit_safe_pfr mode で
  - Stage B 通過群の `median_oos_total_pnl >= 0` (実利益保証)
  - Stage C trade_sharpe median が legacy 18 RUN 平均以上
  - Stage B pass 数 ≥ 10 (運用可能水準)
  - Stage C pass count ≥ 1 (18 RUN 累積 0 を破る)
- **failure_mode**: Run 74 で Stage B 通過 96 個体全例赤字、ρ(median_oos_sharpe→stage_c_sharpe)=-0.361 (curve-fit 逆予測)、18 RUN 累積 Stage C pass=0
- **causal_path**: 現行 sign-based gate (median_oos_sharpe + positive_fold_ratio AND) → curve-fit 選好 → 赤字許容 → Stage C で剥落
- **falsification**: profit_safe_pfr mode Run 75 で (a) Stage B pass 数 < 10、または (b) Stage B 通過群 median total_pnl が依然 negative、または (c) Stage C trade_sharpe median が legacy 18 RUN 平均より悪化 → 仮説否定 (cycle 23 で legacy に戻す)
- **success_criterion**: profit_safe_pfr mode Run 75 で **Stage B median total_pnl ≥ 0** ∧ **Stage B pass ≥ 10** ∧ **Stage C trade_sharpe median ≥ legacy** を全て満たせば → cycle 23-24 で再現確認、3 RUN 比較で default 化判断

### 変更箇所

#### 1. `src/alpha_factory/config.py` (StageGateConfig 拡張)

**変更箇所**: 既存 `StageGateConfig` クラス (line 540 付近、`stage_b_positive_fold_min` の直後)

**追加 field 3 個**:

```python
# cycle 22 (improve-cycle T099 MODIFY): Stage B gate に opt-in mode 追加。
# 詳細: devnotes/20260513-2007-fx-improve/detailed-design.md
# - legacy: 現行 (median_oos_sharpe + positive_fold_ratio AND)
# - profit_safe_pfr: positive_fold_ratio_effective + median_oos_total_pnl + n_fold_effective
#   (median_oos_sharpe は observe-only に降格)
# 根拠: archive 実測 Spearman ρ(median_oos_sharpe → trade_sharpe_stage_c) = -0.361 (curve-fit 逆予測)
stage_b_gate_kind: Literal["legacy", "profit_safe_pfr"] = "legacy"
profit_safe_pfr_threshold: float = 0.4  # positive_fold_ratio_effective 最小要件
profit_safe_pfr_min_n_fold: int = 20  # trade_sharpe 解釈安定化用 fold 数下限 (Codex MODIFY)
```

#### 2. `src/alpha_factory/stage_gate.py` (evaluate_stage_b 改修)

**変更箇所**: `evaluate_stage_b` 内 fold loop (line 1339 付近) と判定 (line 1489 付近)

**変更 1**: fold loop で `fold_total_pnl` を集計 + finite guard (Round 3 修正: legacy 経路完全分離)

```python
# 既存 (line 1339 付近) に追加:
import math
oos_total_pnls: list[float] = []  # 新規: profit_safe_pfr 専用、finite な fold-level total_pnl のみ

# fold loop 内 (既存 fold_sharpe 代入直後、 legacy 経路の fold_sharpe/fold_reason は触らない):
# legacy 経路完全不変。 profit_safe_pfr 用の PnL 集計のみ追加。
fold_total_pnl_candidate: float | None = None
if bt.total_pnl is not None:
    candidate = float(bt.total_pnl)
    if math.isfinite(candidate):
        fold_total_pnl_candidate = candidate
if fold_total_pnl_candidate is not None:
    oos_total_pnls.append(fold_total_pnl_candidate)
# else: 非有限/None は oos_total_pnls に入れない (fail-closed for profit_safe_pfr)
# legacy 経路は完全不変 (fold_sharpe / fold_reason / reason_counts は触らない)
```

**変更 2**: 集計時に `median_oos_total_pnl` と `sum_oos_total_pnl` を計算 (line 1483 付近、effective fold のみで計算)

```python
median_oos_total_pnl: float | None = None
sum_oos_total_pnl: float | None = None
if len(oos_total_pnls) >= 2:
    median_oos_total_pnl = float(_stats.median(oos_total_pnls))
    sum_oos_total_pnl = float(sum(oos_total_pnls))
elif len(oos_total_pnls) == 1:
    median_oos_total_pnl = float(oos_total_pnls[0])
    sum_oos_total_pnl = float(oos_total_pnls[0])
# = effective fold 0 の場合は None (= profit_safe_pfr mode は fail-closed)
```

**変更 3**: 判定分岐 (line 1489-1492 を以下に置き換え)

trade_sharpe_stage_b > 0 条件は **Round 2 で削除**。理由: `evaluate_stage_b` 内では trade-level sharpe を直接計算せず post-filter が必要だが、Codex Critical 指摘 (post-filter で stage_b/stage_c 不整合) を回避するため。`median_oos_total_pnl >= 0` で核心問題 (赤字許容) は十分解消。trade_sharpe 条件は次サイクル別 TODO へ。

```python
if stage_config.stage_b_gate_kind == "legacy":
    # 現行: median_oos_sharpe + positive_fold_ratio AND (完全不変)
    if median_oos < stage_config.stage_b_median_oos_sharpe_min:
        reasons.append("median_oos_sharpe<min")
    if positive_ratio < stage_config.stage_b_positive_fold_min:
        reasons.append("positive_fold_ratio<min")
elif stage_config.stage_b_gate_kind == "profit_safe_pfr":
    # cycle 22 T099 MODIFY: profit_safe_pfr mode (Round 3 修正)
    # 条件 4 つ (AND):
    #   1. positive_fold_ratio_effective >= profit_safe_pfr_threshold (0.4)
    #   2. median_oos_total_pnl >= 0 (実利益保証、effective fold のみで計算)
    #   3. sum_oos_total_pnl >= 0 (aggregate 赤字防止、 Round 3 追加)
    #   4. n_fold_effective >= profit_safe_pfr_min_n_fold (20)
    # median_oos_sharpe は observe-only (gate 判定に使わないが payload に記録)
    if positive_ratio_effective is None or positive_ratio_effective < stage_config.profit_safe_pfr_threshold:
        reasons.append("positive_fold_ratio_effective<min")
    if median_oos_total_pnl is None or median_oos_total_pnl < 0:
        reasons.append("median_oos_total_pnl<min")
    if sum_oos_total_pnl is None or sum_oos_total_pnl < 0:
        reasons.append("sum_oos_total_pnl<min")
    if n_fold_effective < stage_config.profit_safe_pfr_min_n_fold:
        reasons.append("n_fold_effective_below_profit_safe_min")
else:
    raise ValueError(f"unknown stage_b_gate_kind: {stage_config.stage_b_gate_kind}")
```

**変更 4**: payload に新規 key 追加 (line 1533-1551 付近、Round 3 修正)

```python
"payload": {
    # 既存 key 完全不変 ...
    "stage_b_gate_kind": stage_config.stage_b_gate_kind,
    "median_oos_total_pnl": median_oos_total_pnl,  # 新規
    "sum_oos_total_pnl": sum_oos_total_pnl,  # 新規 (Round 3)
    "oos_total_pnls": tuple(oos_total_pnls),  # 新規 (effective fold only)
    "profit_safe_pfr_threshold": stage_config.profit_safe_pfr_threshold,
    "profit_safe_pfr_min_n_fold": stage_config.profit_safe_pfr_min_n_fold,
}
```

#### 3. `src/alpha_factory/archive.py` (collect_stage_b 拡張) + tests/archive 更新

archive Parquet に optional column として `median_oos_total_pnl` / `stage_b_gate_kind` を追加。
GENOME_ENTRY_SCHEMA_VERSION は **v2 のまま据え置き** (新規列は nullable、optional column 追加は backward compatible)。

**変更箇所 (Round 2 追加)**: `collect_stage_b` 関数内で payload から抽出 + `tests/alpha_factory/test_archive.py:183` 付近の列集合 assertion 更新。

```python
# src/alpha_factory/archive.py collect_stage_b 内 (Stage B 評価 payload 抽出時、Round 3 修正):
entry["median_oos_total_pnl"] = payload.get("median_oos_total_pnl")
entry["sum_oos_total_pnl"] = payload.get("sum_oos_total_pnl")  # Round 3 追加
entry["stage_b_gate_kind"] = payload.get("stage_b_gate_kind", "legacy")
```

```python
# tests/alpha_factory/test_archive.py:183 付近の expected_columns に 3 列追加 (Round 3 修正):
expected_columns = {
    # ... 既存全列 ...
    "median_oos_total_pnl",
    "sum_oos_total_pnl",  # Round 3 追加
    "stage_b_gate_kind",
}
```

`schema_contract.py` 側は GENOME_ENTRY_CONTRACT_V2 (frozenset) 不変 (= 必須 4 field は変更なし、新規列は optional)。

#### 4. `scripts/alpha_factory/run_ga.py` (CLI 追加)

**変更箇所**: argparse セクション (line 303-389 付近)

```python
# T099 MODIFY (cycle 22): Stage B gate kind opt-in
p.add_argument(
    "--stage-b-gate-kind",
    choices=["legacy", "profit_safe_pfr"],
    default=None,  # None = yaml/default 値を使用
    help="Stage B gate kind. legacy=現行 sign-based, profit_safe_pfr=profit-safe (cycle 22 opt-in)",
)
```

main 内で CLI override → StageGateConfig 上書き (calibrate-gate の pattern を踏襲):

```python
if args.stage_b_gate_kind is not None:
    config = replace(config, stage_gate=replace(config.stage_gate, stage_b_gate_kind=args.stage_b_gate_kind))
```

#### 5. (Round 2 削除) post-filter は廃止

Round 1 で「post-filter 配置の stage_b/stage_c 不整合」が Critical 指摘されたため、**post-filter は廃止**。`evaluate_stage_b` 内 3 条件 (pfr + median_oos_total_pnl + n_fold_effective) のみで判定し、trade_sharpe_stage_b > 0 条件は次サイクル別 TODO へ。

#### 6. config 4 段伝搬 (Round 2 新規対応)

Codex Critical 指摘: `_build_stage_gate` に新 field を追加しないと yaml/default 値が読まれない。

**変更箇所**: `src/alpha_factory/config.py:508` 付近 `_build_stage_gate`:

```python
# 既存パターン (stage_b_median_oos_sharpe_min) を踏襲して 3 field 追加:
kwargs["stage_b_gate_kind"] = str(raw.get("stage_b_gate_kind", "legacy"))
kwargs["profit_safe_pfr_threshold"] = float(raw.get("profit_safe_pfr_threshold", 0.4))
kwargs["profit_safe_pfr_min_n_fold"] = int(raw.get("profit_safe_pfr_min_n_fold", 20))
```

**変更箇所**: `src/alpha_factory/calibrate_state.py:56` 付近 `compute_base_config_hash`:

```python
# 新 field を hash 計算に含める (= cross-run history guard が正しく機能):
hash_input = {
    # 既存全 field ...
    "stage_b_gate_kind": stage_gate.stage_b_gate_kind,
    "profit_safe_pfr_threshold": stage_gate.profit_safe_pfr_threshold,
    "profit_safe_pfr_min_n_fold": stage_gate.profit_safe_pfr_min_n_fold,
}
```

これにより gate kind 切替時に history record が誤適用されない。

#### 7. StageGateConfig.__post_init__ 範囲検証 (Round 2 Suggestion 採用)

```python
# src/alpha_factory/stage_gate.py:653 付近 (StageGateConfig.__post_init__):
import math
if not math.isfinite(self.profit_safe_pfr_threshold):
    raise ValueError(f"profit_safe_pfr_threshold must be finite, got {self.profit_safe_pfr_threshold}")
if not (0.0 <= self.profit_safe_pfr_threshold <= 1.0):
    raise ValueError(f"profit_safe_pfr_threshold must be in [0, 1], got {self.profit_safe_pfr_threshold}")
if self.profit_safe_pfr_min_n_fold < 1:
    raise ValueError(f"profit_safe_pfr_min_n_fold must be >= 1, got {self.profit_safe_pfr_min_n_fold}")
if self.stage_b_gate_kind not in ("legacy", "profit_safe_pfr"):
    raise ValueError(f"stage_b_gate_kind must be 'legacy' or 'profit_safe_pfr', got {self.stage_b_gate_kind!r}")
```

#### 8. generate_run_report.py known reason codes 追加 (Round 2 Warning 対応)

```python
# scripts/alpha_factory/generate_run_report.py:534 付近 known reason codes (Round 3 修正):
known_reason_codes = {
    # 既存全 codes ...
    "positive_fold_ratio_effective<min",  # cycle 22 T099 (profit_safe_pfr)
    "median_oos_total_pnl<min",  # cycle 22 T099 (profit_safe_pfr)
    "sum_oos_total_pnl<min",  # cycle 22 T099 (profit_safe_pfr Round 3 追加)
    "n_fold_effective_below_profit_safe_min",  # cycle 22 T099 (profit_safe_pfr)
}
```

### 波及変更（AGENTS.md / skill / config / docs）

- **docs/alpha_factory/stage-gates.md**: cycle 22 T099 セクション追加 (profit_safe_pfr mode の定義・閾値・smoke 手順)
- **AGENTS.md**: § calibrate-gate と state file 経由の自動適用 と同様に、stage_b_gate_kind の effective 値を log 出力 (`stage_gate.stage_b_gate_kind kind=X` log)
- **config/alpha_factory/default.yaml**: `stage_gate.stage_b_gate_kind` / `stage_gate.profit_safe_pfr_threshold` / `stage_gate.profit_safe_pfr_min_n_fold` の 3 field を documenting 追加 (default "legacy" / 0.4 / 20)
- **CLI / skill**: `zenigame-fx-run-alpha-factory` skill の引数仕様に `--stage-b-gate-kind` を明記

### 現行コード (抜粋)

`src/alpha_factory/stage_gate.py:1489-1492`:
```python
if median_oos < stage_config.stage_b_median_oos_sharpe_min:
    reasons.append("median_oos_sharpe<min")
if positive_ratio < stage_config.stage_b_positive_fold_min:
    reasons.append("positive_fold_ratio<min")
```

### 変更後コード (上記 §変更 3 参照)

### ルックアヘッドバイアスチェック

primitive 変更なし。Stage B gate 判定のみの変更で fold 評価方法 (rolling window 方向、未来バー参照) は完全不変。

- [x] 未来バー参照なし (fold loop 内 backtest は既存)
- [x] 当日確定値の先取りなし
- [x] rolling window 方向が過去方向
- [x] 正規化にローカル window 使用
- [x] バケット / グループ平均が因果的
- [x] cumsum/accumulate が因果的方向

### パフォーマンスチェック

- `fold_total_pnl` 集計は既存 `bt.total_pnl` の参照のみで追加コストほぼゼロ
- `median_oos_total_pnl` 計算は n_fold 個の median = O(n log n) ≪ fold 1 個の backtest コスト
- post-filter (trade_sharpe_stage_b mask) は O(N_genome) で軽量

- [x] compute_all_bars() 実装変更なし
- [x] 内側ループ内で NumPy 関数を呼んでいない (median は 1 回のみ)
- [x] SoA プロパティ使用
- [x] 同一配列のキャッシュ

### テスト計画

- バグ修正ではなく機能追加
- 既存テスト更新:
  - `tests/alpha_factory/test_stage_gate.py` の Stage B 関連 fixture で `stage_b_gate_kind="legacy"` を明示 (default の確認)
- 新規テスト (`tests/alpha_factory/test_stage_gate.py` に追加、~12 件 Round 2 拡張):
  - `test_stage_b_legacy_mode_unchanged`: default `legacy` で従来挙動完全一致
  - `test_stage_b_profit_safe_pfr_pfr_min_fail`: `positive_fold_ratio_effective < 0.4` で fail
  - `test_stage_b_profit_safe_pfr_median_pnl_negative_fail`: `median_oos_total_pnl < 0` で fail
  - `test_stage_b_profit_safe_pfr_n_fold_too_small_fail`: `n_fold_effective < 20` で fail
  - `test_stage_b_profit_safe_pfr_all_pass`: 3 条件全 pass で pass
  - `test_stage_b_profit_safe_pfr_observe_only_median_oos_sharpe`: median_oos_sharpe<min でも profit_safe_pfr mode は pass (observe-only)
  - `test_stage_b_profit_safe_pfr_n_fold_threshold_exact`: 境界値 n_fold=20 で pass、19 で fail
  - `test_stage_b_profit_safe_pfr_threshold_exact`: 境界値 pfr=0.4 で pass、0.3999 で fail
  - `test_stage_b_payload_contains_new_keys`: payload に `median_oos_total_pnl` / `stage_b_gate_kind` 等が含まれる
  - `test_stage_b_unknown_kind_raises`: 不明な `stage_b_gate_kind` で ValueError
  - **(Round 2 追加)** `test_stage_b_profit_safe_pfr_nonfinite_fold_total_pnl`: fold 内 `bt.total_pnl` が NaN/Inf のとき該当 fold が unavailable 扱いになる
  - **(Round 2 追加)** `test_stage_gate_config_post_init_validation`: 範囲外 threshold / min_n_fold で ValueError
  - **(Round 2 追加)** `test_build_stage_gate_reads_new_fields`: `_build_stage_gate` が yaml の 3 field を読む

archive / CLI 統合テスト:
  - **(Round 2 修正)** `tests/alpha_factory/test_archive.py:183` 付近の expected_columns に `median_oos_total_pnl` / `stage_b_gate_kind` を追加
  - `tests/alpha_factory/test_run_ga_cli.py` (or 既存テスト): `--stage-b-gate-kind profit_safe_pfr` CLI override 動作
  - **(Round 2 追加)** `tests/alpha_factory/test_compute_base_config_hash.py` (既存があれば拡張): 新 field 変更で hash が変わること

run-report テスト:
  - **(Round 2 追加)** `tests/alpha_factory/test_generate_run_report.py`: 新 reason code 3 個が known_reason_codes に入っており `other` に吸われないこと

### リスク

1. **Stage B pass 数の崩壊リスク**: `median_oos_total_pnl >= 0` 条件は厳しく、Run 74 の Stage B 通過 96 個体 (全例赤字) はゼロになる可能性。falsification 条件 (a) で検知。
2. **(Round 2 解消) post-filter 配置問題**: post-filter は Round 2 で廃止。`evaluate_stage_b` 内のみで判定し、stage_b/stage_c 不整合を完全回避。
3. **archive schema 互換性**: 新規 column 2 個 (`median_oos_total_pnl` / `stage_b_gate_kind`) を v2 schema に nullable column として追加。test_archive.py の列集合 assertion 更新。既存 v2 archive Parquet との後方互換性を tests/archive で確認。
4. **legacy mode の完全不変保証**: 既存全テストが pass することを確認。default `legacy` で従来挙動 100% 再現。
5. **(Round 2 追加) base_config_hash 影響**: 新 field 3 個を `compute_base_config_hash` に追加するため、cycle 22 以降の history record は base_config_hash が変わる。cycle 21 以前の history record と区別される (= cross-run guard 正常動作)。これは設計通りで影響範囲は calibrate-gate history の cycle 22 以降のみ。

## Run 75 実行パラメータ

| パラメータ | 値 | Run 74 からの変更 |
|-----------|-----|----------------|
| instrument | EUR_JPY | 不変 |
| population-size | 96 | 不変 |
| generations | 60 | 不変 |
| mutation-rate | 0.5 | 不変 |
| seed | **60** | 59 → 60 (cycle_index+38 規約) |
| max-workers | 2 | 不変 |
| **stage-b-gate-kind** | **profit_safe_pfr** | **新規** (default legacy から smoke 用に上書き) |

実行コマンド:
```bash
uv run python scripts/alpha_factory/run_ga.py \
  --instrument EUR_JPY \
  --population-size 96 --generations 60 \
  --mutation-rate 0.5 --seed 60 --max-workers 2 \
  --stage-b-gate-kind profit_safe_pfr
```
