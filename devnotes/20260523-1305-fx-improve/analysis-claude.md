# 分析 (cycle 13): trade_count 閾値の構造的限界 + 達成可能な閾値再設計

## 前提
cycle 12 で live_criteria 引き上げ (sharpe1.5/trade_count_min100/entry_count_min100) → R94 で Stage C=0、entry_count_min=100 逆効果。本分析で trade_count と品質の関係を定量化。

## 観察事実（Facts）

### R94 (引き上げ後) の負の結果
- A/B/C = 2238/1361/**0**。trade_count_min=100 で Stage C 全滅。best: sharpe3.80/pnl47020/dd1.45/**trade45**。
- entry_count_min=100 逆効果: R94 Stage B trade_count median44/max97/≥100:0 vs R89(entry50) median50/**max668/≥100:15**。短い Stage A 窓 (stage_a_window_days=1) で 100 entries 強制が hyper-active-1day 戦略を選抜し、高取引数 tail を抹殺・分布左シフト。

### ★ trade_count vs 品質の単調トレードオフ (R89 Stage C 892 個体)
| trade_count 帯 | n | annualized sharpe median | pnl median |
|---------------|---|--------------------------|-----------|
| [50,60) | 850 | **4.64** | **69970** |
| [60,80) | 36 | 3.56 | 57875 |
| [80,98) | 6 | 3.42 | 54880 |

- R89 Stage B の trade_count≥100 個体 15 → **Stage C pass 0**。holdout trade_sharpe median 0.026/max 0.133 (極低) で Stage C 品質 gate (sharpe/pnl/dd) に落ちる。

## 解釈・推論（Interpretations）

### 1. trade_count_min=100 は現戦略空間で構造的に到達不能
高取引数 (≥100) 個体は holdout 品質 (sharpe/pnl) が崩壊 (median sharpe 0.026)。trade_count↑ で sharpe/pnl が単調劣化 (4.64@50 → 3.42@80-98)。現 32-primitive・EUR_JPY では「高頻度取引 = 低 per-trade 品質」のトレードオフが steep。trade_count_min=100 は品質基準と両立せず Stage C=0。

### 2. ★「lucky-few-trade 過学習」仮説の部分棄却
cycle 12 で「50-trade floor 張り付き = lucky 過学習」と解釈したが、50-trade 帯は **850 個体・median sharpe 4.64・pnl 69970** = robust な品質最適点 (少数の lucky 外れ値でない)。floor 張り付きは「過学習」でなく「品質最適が低取引数域にある」構造。

### 3. entry_count_min=100 は誤レバー (revert 確定)
短い Stage A 窓で 100 entries 強制は不適切 (hyper-active 選抜、高取引数 tail 抹殺)。R89 (entry50) は既に max668 trade 個体を持つ。→ entry_count_min 100→50 revert。

### 4. ★ 達成可能 & 意味ある閾値引き上げ = total_pnl_min
trade_count_min=100 / sharpe1.5 (hollow、既達4.64) でなく、**total_pnl_min 50000→70000** が binding (50-trade 帯 median 69970) かつ達成可能 (約半数 pass)。pnl は品質直結で、緩和でなく引き上げ・robustness 向上。

## 次サイクル候補
- **[Critical] config 調整**: (a) entry_count_min 100→50 revert (逆効果確定)、(b) trade_count_min 100→50 revert (構造的到達不能)、(c) sharpe_min 1.5 維持 (引き上げ済、緩和しない) + **total_pnl_min 50000→70000 引き上げ** (binding & 達成可能な意味ある robustness 強化)。
- **[Warning] cross-pair shadow 観測継続**、メタ過学習回避 (pnl 引き上げで品質最適個体を選抜、取引数操作でない)。

## 全体判定
**負の結果が閾値設計を精緻化** — trade_count_min=100/entry_count_min=100 は構造的に不適切 (品質トレードオフ + Stage A 短窓歪み)。50-trade は品質最適点で lucky でない。達成可能 & 意味ある引き上げは total_pnl_min 50000→70000。Codex 合議で revert + pnl 引き上げを確定。
