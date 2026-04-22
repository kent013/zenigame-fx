# Concept: clause-backtest-integration

## 目的

Clause ベース Genome を backtest engine に統合し、composite score → ヒステリシス判定 → 発注のフローを実装。

## 前提

- `clause-genome-structure` 完了後に着手

## 設計

### DslStrategy の再実装（`src/backtest/engine.py` or `src/dsl/eval.py`）

```python
class DslStrategy:
    def __init__(self, genome: Genome): ...

    def on_bar(self, bar, snapshot) -> list[OrderSignal]:
        # 1. 各 Clause の composite score を計算
        # 2. ヒステリシス判定（entry_threshold / exit_threshold）
        # 3. セッション時間・スプレッドフィルタ
        # 4. time_stop チェック
        # 5. 発注シグナル生成
```

### 状態管理

- 保有ポジションの has_entry_above_theta_on フラグ
- time_stop 用の entry_time
- session close 時刻の追跡

## テスト

- composite > θ_on でエントリー、< θ_off で exit
- θ_off < composite < θ_on で保有継続（ヒステリシス）
- time_stop 到達で強制クローズ
- セッションクローズ時に保有なしになる

## 優先度・モード

- Priority: Critical
- Mode: standalone
- テーマ: ga-architecture
