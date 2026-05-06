# 調査ノート: g26_i95 (run-35) trade<50 で stage_a_pass=True 経路の確認

cycle 3 / 20 — Phase 3 (実装) 内 C2 施策。 実コード非変更、 アーキテクチャ確認のみ。

## 観察事実 (g26_i95 archive row、 run-35)

| 列 | 値 | 注 |
|---|---|---|
| fitness_raw | 0.2894 | Stage A 内部評価結果 |
| fitness_pen | 0.2699 | fitness_raw - α·size_norm |
| **stage_a_pass** | **True** | 通過 |
| stage_b_pass | False | 不通過 |
| stage_c_pass | False | 不通過 |
| **sharpe (archive 列)** | **NaN** | 別経路の値、 Stage A 評価とは独立 |
| **trade_sharpe_raw** | **0.2894** | Stage A 内部の sharpe_raw、 fitness_raw と一致 |
| trade_sharpe_stage_b | -0.179 | Stage B fold 評価結果 |
| sharpe_calc_version | v2_trade_level | trade-level Sharpe を使用 |
| **trade_count** | **44** | live_criteria.trade_count_min=50 を下回る |
| total_pnl | 29560 | 取引はしている (cycle 1 fix で正しい値) |
| active_clause | 1 | 単一 clause |
| n_nodes | 4 | 構文木 4 ノード |
| fold_sign_ratio | 0.0 | fold sign 反転なし (= 全 fold 同方向) |
| n_fold_effective | 1.0 | **fold が 1 個しか機能していない** (要注意) |
| positive_fold_ratio_effective | 0.0 | 機能 fold で positive 0 件 |

## アーキテクチャ確認 (`src/alpha_factory/stage_gate.py`)

### Stage A pass 判定条件 (line 836 周辺)

```python
if exception_caught:
    reasons.append("system_failure")
elif trade_count < stage_config.min_exposure_trade_count:  # default 1
    reasons.append("no_exposure")
elif sharpe_raw is None:
    reasons.append("metric_unavailable")
else:
    fitness_raw = sharpe_raw
    fitness_pen = fitness_raw - stage_config.stage_a_alpha * size_norm_val
    if fitness_pen <= stage_config.stage_a_threshold:
        reasons.append("below_threshold")

passed = len(reasons) == 0
```

`stage_a_pass=True` の必要十分条件:
1. system_failure なし
2. `trade_count >= min_exposure_trade_count` **= 1** (default、 stage_gate.py:392)
3. `sharpe_raw is not None`
4. `fitness_pen > stage_a_threshold`

### live_criteria.trade_count_min=50 の使用範囲

- **live_criteria は Stage A 評価には使われない**
- live_criteria.trade_count_min=50 は live 適合判定 (graduation 判定 / mission 達成判定) のみで使用
- Stage A の `min_exposure_trade_count=1` (より緩い閾値) との不変条件: `min_exposure_trade_count < trade_count_min` を `__post_init__` で検証 (stage_gate.py:386-392)

→ 設計通り。 trade_count=44 で stage_a_pass=True は **bug ではない**。

### sharpe (archive 列) と sharpe_raw (Stage A 内部) の差

- **`sharpe` (archive 列)**: full-period の trade-level Sharpe か legacy Sharpe (推定)。 trade_count<30 (`trade_count_min_for_sharpe`) で None になる経路あり (config.py:435)
- **`sharpe_raw` (Stage A 内部)**: `trade_sharpe_raw` と同等、 fitness_raw として使われる
- g26_i95 では trade_sharpe_raw=0.289 (Stage A 内部値、 fitness_pen 計算経路)、 sharpe (archive 列)=NaN は **別系統の値**

→ 設計通り。 sharpe=NaN でも stage_a_pass=True は矛盾ではない (sharpe_raw が None でなければ Stage A は pass)。

## 設計通り / bug 判定

### 設計通り (NOT bug)
- ✅ trade_count=44 で stage_a_pass=True: `min_exposure_trade_count=1` の閾値で、 live_criteria.trade_count_min=50 とは別軸
- ✅ archive 列 `sharpe`=NaN で stage_a_pass=True: archive `sharpe` は Stage A 内部の sharpe_raw と異なる経路
- ✅ Top-3 (g26_i95, g39_i74, g32_i47) trade<50 で fitness_pen 上位: fitness_pen 単独 ranking と selection_score 6 要素辞書式 best (g56_i28) が異なるのは設計通り (T031 RPC Phase 1)

### 観察すべき副作用 (NOT bug、 ただし concern)

- ⚠️ **n_fold_effective=1**: g26_i95 は Stage B fold 評価で 11 fold 中 1 fold しか機能しなかった。 残り 10 fold は all_folds_unavailable。 これは「短期間に集中した取引」の signature
- ⚠️ **fold_sign_ratio=0.0** + **trade_sharpe_stage_b=-0.179** (Stage B で負): fold 多様性が無く、 Stage B 期間 (Stage A 外) で逆方向に動く危険な signal

## cycle 4 での fix 必要性

**判定: Defer (cycle 4 では不要)**

理由:
- 設計通りで bug ではない
- ただし「fitness_pen ranking で trade<50 が top に来る」現象は **GA 目的関数と live 適合性のギャップ** を示唆 (Codex Round 1 C2 警告)
- これは cycle 3 P1 (sidecar) の集計で生成別に追跡可能になっている
- cycle 4 で sidecar データを分析して、 「Stage A 上位選抜が live_criteria 整合的か」 を統計的に判定してから対策を決める

**cycle 4 候補施策 (judgment 用、 採用は次 cycle で議論)**:
- 案 1: selection_score の trade_count_min 重み調整 (Stage A 内部評価で trade_count_min を考慮)
- 案 2: fitness_pen 計算式に soft live_criteria penalty 追加 (見栄え改善 ≠ 構造的整合)
- 案 3: 何もしない (selection_score 6 要素辞書式 best が SoT であり、 fitness_pen 単独 top は archive 視点での観察に過ぎない、 仕組み的に問題なし)

cycle 4 で Codex 合議で判断する。

## 結論

g26_i95 の trade<50 + stage_a_pass=True は **設計通り**。 bug ではない。 観察した副作用 (live 適合性ギャップ) は cycle 4 sidecar データで定量化してから対策を決める方針。 cycle 3 では実コード非変更でクローズ。
