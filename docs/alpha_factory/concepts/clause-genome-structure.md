# Concept: clause-genome-structure

## 目的

FX GA のゲノム表現を現行フラット 4 式（entry_long/short, exit_long/short）から **Clause ベース合成** 構造に再構築する。zenigame 日本株 Alpha Factory の Clause 設計を踏襲（Codex 3 ラウンド議論で確定）。

## 設計

### 新 Genome 構造（`src/dsl/genome.py`）

```
Genome = WhenConfig + HowConfig + Position + Risk + Meta

HowConfig:
  clauses: list[ClauseConfig]  # 1-3 個（max_clause=1 開始、段階解放）

ClauseConfig:
  directional: list[SignalConfig]  # TREND_FOLLOW / MEAN_REVERT / NEUTRAL
  local_gate:  list[SignalConfig]  # MODULATOR（sigmoid gate）
  weight: float

SignalConfig:
  name: str      # primitive ID
  weight: float  # directional: [0.1, 2.0] 正のみ or local_gate: [-2.0, 2.0]
  params: dict   # primitive 固有パラメータ

Position:
  entry_threshold: float  # θ_on
  exit_threshold: float   # θ_off（ヒステリシス: θ_on > θ_off）
  max_pos: int
  time_stop_min: int

Risk:
  stop_atr: float
  take_atr: float
```

### Composite Score 計算

```
dir_score[k] = Σ(w_i × signal_i) / Σ|w_i|         # directional 加重和
gate[k]      = Π gate_fn(gate_signal_j)            # local_gate の積
clause_score[k] = dir_score[k] × gate[k]

composite = Σ(clause_weight × clause_score) / Σ|clause_weight|
```

### 発注条件

- long: composite ≥ θ_on → エントリー（long 保有中は composite < θ_off で exit）
- short: -composite ≥ θ_on → エントリー
- time_stop 経過で強制クローズ

## 制約

- max_clause=1 開始、上限 3
- max_depth=5（合成式深さ）
- directional の weight は正のみ（[0.1, 2.0]）
- modulator は正負両方（[-2.0, 2.0]）

## 実装範囲

- `src/dsl/genome.py` 再構築（既存は `_legacy` リネーム）
- `src/dsl/serialize.py` 新構造対応
- テスト: ClauseConfig / composite 計算 / ヒステリシス遷移

## 優先度・モード

- Priority: Critical
- Mode: standalone（複数ファイル協調変更のため単独セッション）
- テーマ: ga-architecture
