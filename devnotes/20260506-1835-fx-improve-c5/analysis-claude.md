# RUN run_20260506_080007 (run-37) 分析（Claude 自己分析）

cycle 5 / 20 — cycle 4 介入 (selection_score fold_robust 9-tuple 化) の効果検証 + 次介入策定。

## 観察事実（Facts）

### 1. Stage 通過数 (cycle 4 介入の効果)

| Stage | run-36 (cycle 3) | run-37 (cycle 4) | 差分 |
|---|---|---|---|
| Stage A pass | 1,999 | 1,647 | -18% (selection 厳格化) |
| **Stage B pass** | **0** | **6** 🎉 | **+6** |
| Stage C pass | 0 | 0 | — |
| graduation | 0 | 0 | — |

### 2. fold_robust 個体生成

| metric | run-36 | run-37 | 差分 |
|---|---|---|---|
| pfre>=0.4 個体 | 77 (4.05%) | **606 (36.8%)** | **9倍** |
| pfre>=0.6 (Stage B 閾値) | 13 | 134 | 10倍 |

GA 進化が「fold robust 個体を作る」 方向に確実にシフト。

### 3. Best 個体 (run-37 g54_i2)

| metric | 値 |
|---|---|
| fitness_pen | 0.199 (run-36 0.222 から -10%) |
| trade_count | 57 (entry_count_min=50 通過) |
| total_pnl | 32160 (positive!) |
| **pfre** | **1.0** (= fold_robust=True) |
| stage_b_pass | False (Stage B 通過は別個体群) |
| stage_a_pass | True |

→ best が **fold_robust=1 個体** に変わった = cycle 4 selection_score 9-tuple が機能

### 4. **Stage B pass 6 個体の品質 (CRITICAL)**

| individual | gen | fitness_pen | trade_count | total_pnl | pfre | feasible (>= 50) |
|---|---|---|---|---|---|---|
| g33_i6 | 33 | 0.011 | 14 | -8,850 | 0.70 | False |
| g42_i12 | 42 | 0.077 | 30 | -20,680 | 0.64 | False |
| g53_i25 | 53 | 0.036 | 22 | -14,420 | 0.64 | False |
| g53_i53 | 53 | 0.097 | 26 | -16,890 | 0.73 | False |
| g55_i9 | 55 | 0.124 | 28 | -12,360 | 0.70 | False |
| g55_i55 | 55 | -0.003 | 22 | -28,360 | 0.64 | False |

**全員**:
- total_pnl < 0 (損失)
- trade_count < 50 (entry_count_min=50 不達 → feasible=False)
- sharpe = NaN (trade_count_min_for_sharpe=30 接近)
- 全員 Stage C 不通過

### 5. Best (g54_i2) が Stage B 不通過なのに選ばれた理由 (selection_score 解析)

selection_score 9-tuple lexicographic order:
1. feasible: g54_i2=1 (trade=57) vs Stage B pass 全員=0
2. -violation: g54_i2 violation=0 vs Stage B pass 大きい violation
3. ...

→ **要素 1 (feasible) で勝負がつく**。Stage B pass 6 個体は全員 feasible=0 で最優先順位下位、 g54_i2 が feasible=1 で best 選定。

## 解釈・推論（Interpretations）

### 仮説 H1 (cycle 3): 探索圧不整合 — **VERIFIED ✅**

cycle 4 介入で Stage B pass 0→6 達成、 H1 検証完了。 fold_robust selection_score 拡張は **設計通り機能**。

### 仮説 H7 (NEW): fold_robust と feasibility の同時達成困難

**根拠**:
- Stage B pass 6 個体 全員 trade_count 14-30 で entry_count_min=50 不達
- これらの個体は「短期間に集中して trading 行い fold robustness を出す noise pattern」
- fitness_pen は -0.003 〜 0.124 で全員 run-36 best (0.222) より低い

**示唆**:
- fold_robust selection で「真の robust signal」 ではなく「noise だが fold で偶然 positive な個体」を拾っている可能性
- 「fold robust AND adequate trade」 を同時達成する個体は探索空間内に少ない / 困難

**反証可能性**:
- cycle 5 介入後、 Stage B pass 個体の trade_count 分布が >= 50 寄りにシフトすれば確証 (= cycle 5 介入が機能)
- 不変なら別の構造的問題 (primitive / feasibility 緩和不可で別経路)

### 禁止事項チェック

| # | 禁止事項 | 兆候 |
|---|---|---|
| 6 | 取引回数削減 | **Stage B pass 6 個体全員 trade_count<50** で **疑い顕著** |

ただしこれは GA 探索結果であり、 設計の「取引回数削減で見栄え改善」 には該当しない (見栄えではなく構造的に出てきた現象)。 ただし要観察。

## 次サイクル候補

### [Critical] C1: selection_score に「fold_robust AND feasible」 複合条件追加

**設計案**:
- selection_score の 8 要素目を `fold_robust` から `fold_robust_and_feasible` (= `fold_robust AND feasible`) に変更
- これにより GA は **「pfre>=0.4 かつ trade_count>=50 (entry_count_min)」** 個体を最優先に
- 既存 fold_robust 個体で trade_count<50 のものは selection 順位下がる
- target: Stage B pass 個体の trade_count 分布が >= 50 寄りにシフト

**falsification**: cycle 6 で Stage B pass 個体の median trade_count >= 50 になれば確証
**success_criterion**: Stage B pass + feasible 個体が 1 件以上 (= total_pnl > 0 で entry_count adequate)
**変更分類**: **Structural** (selection_score の AND 合成、 既存条件の組み合わせ)

### [Warning] W1: live_pass 達成までの遠さの定量化

run-37 best total_pnl = 32160 (live_criteria 50000 の 64%)、 sharpe = NaN (live_criteria 1.0 不達)。 cycle 5 介入で Stage B pass + feasible 個体が出てきても、 live_pass までの距離は大きい。

## 全体判定

**ACTIONABLE** — cycle 4 H1 verified、 cycle 5 で次介入 (fold_robust AND feasible 複合化) を策定。 「機能の名前に立ち返れ」 原則: fold_robust だけでなく feasible との同時達成を要求すべき。
