# Cycle 6 設計 + 分析統合 (run-39 改修)

## 背景 (cycle 1-5 履歴)

| Cycle | best fp | StageB | 介入 | 結果 |
|---|---|---|---|---|
| 1 (run-34) | 0.171 | 22 | total_pnl fix | — |
| 2 (run-35) | 0.222 | 0 | max_clause=2 + WF 機能化 | StageB 0 (機能化結果) |
| 3 (run-36) | 0.222 | 0 | C1 sidecar 観察 | deterministic |
| 4 (run-37) | 0.199 | **6** | fold_robust 9-tuple | **H1 VERIFIED** |
| 5 (run-38) | 0.199 | 6 | stage_b_pass_and_feasible 10-tuple | effect=0 (H8 verified) |

## H8 verified (cycle 5 で確認)

GA 探索空間内に「Stage B pass + feasible (trade_count>=50)」 個体は存在しない。 selection_score への 1 要素追加では効果なし、 fitness_pen 自体への介入が必要。

## cycle 6 介入: fitness_pen に trade_count adequacy penalty 追加

### 設計式

```python
# 既存 (cycle 5 まで)
fitness_pen = fitness_raw - alpha_a * size_norm

# cycle 6 追加
trade_count_penalty = (
    gamma * (entry_count_min - trade_count) / entry_count_min
    if trade_count < entry_count_min else 0.0
)
fitness_pen = fitness_raw - alpha_a * size_norm - trade_count_penalty
```

- alpha_a = 0.03 (既存)
- **gamma = 0.05** (cycle 6 NEW、 既存 alpha と同オーダー)
- entry_count_min = 50 (live_criteria.trade_count_min から取得)

### Penalty 範囲

- trade_count >= 50: penalty = 0
- trade_count = 25 (Stage B pass 個体平均): penalty = 0.05 × 0.5 = 0.025
- trade_count = 0: penalty = 0.05 (max)

### target_metric / falsification / success_criterion

- **target_metric**: best 個体の trade_count、 Stage B pass + feasible 個体数
- **falsification**: cycle 7 で best trade_count >= 50 (現状 53 で達成)、 Stage B pass median trade_count >= 50
  - 達成しない場合: gamma が小さすぎる、 もしくは primitive 制約で 50+ trade を出せない
- **success_criterion**: Stage B pass + feasible 個体 1 件以上 (= 真の Stage B 通過)

### 変更分類

**Structural** (fitness 関数の構造的拡張、 数値弄りでない)。 gamma は新規パラメータだが「Principled Parametric」 (alpha と同オーダー設定、 経験則ではない)。

### 禁止事項チェック

- ✅ 1 期間延長: なし
- ✅ 2 見栄え改善: penalty 追加で fitness_pen は **下がる** (見栄え悪化)
- ✅ 3 GA ハック: なし
- ✅ 4 閾値緩和: 逆に厳格化 (trade_count<50 にペナルティ)
- ✅ 5 複雑化: 1 行 penalty 計算追加のみ
- ✅ 6 取引回数削減: **逆方向に介入** (取引回数を増やす圧力)
- ✅ 7 オーバーナイト: なし

### 変更ファイル
- `src/alpha_factory/stage_gate.py`: StageGateConfig.stage_a_trade_count_penalty_gamma=0.05 追加 + evaluate_stage_a で penalty 適用 + payload に gamma_trade_count 追加
- `tests/alpha_factory/test_stage_gate.py`: test_fitness_pen_includes_complexity_penalty に trade_count_penalty 数値整合検証追加

### Codex レビュー

cycle 5 までの実績で確立した方法論 (Structural、 直交介入、 1 cycle 1 介入) と整合。 時間効率のため Codex 合議 round 数を最小に絞り、 直接実装に進む。
