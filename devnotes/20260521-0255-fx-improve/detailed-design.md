# 詳細設計: Run 84 施策

## 使命・制約（絶対遵守）
- 使命: live_criteria 全達成個体を見つける。達成後は robustness 確認後に閾値引き上げ（緩和禁止）。
- FX 固有制約: イントラデイ前提 / ロング・ショート両方向許容 / スワップ・スプレッド控除後純益。

## 施策一覧
| # | 施策名 | 変更ファイル | target_metric |
|---|--------|------------|--------------|
| R84-1 | 再現性検証（seed perturbation only） | **なし（コード変更なし）** | mission_count / genotype 多様性 |

## R84-1: 再現性検証（seed perturbation only）

### target_metric / failure_mode / causal_path / falsification / success_criterion
- target_metric: mission_count（別 seed での live 全達成個体数）、genotype_family_count。
- failure_mode: Run83 の mission 達成が lucky seed 依存で、別 seed では mission 消失。
- causal_path: seed のみ変更し他を完全固定 → seed 感度を直接観測。
- falsification: 別 seed で mission=0 かつ多様性も増えない → 「seed-lucky で脆弱」仮説を支持。
- success_criterion: 別 seed run で mission 個体≥1 再出現 → 達成が seed 非依存と判定。

### 変更箇所
**コード変更なし。** GA 実行引数のみ変更（seed 68→69）。ロジック・gate・閾値・fitness は完全不変。

### 波及変更（AGENTS.md / skill / config / docs）
なし（公開インターフェース・config・docs いずれも変更なし）。

### テスト計画
コード変更がないため新規/既存テストへの影響なし。R84 完走と sidecar（T109 gap diagnostic 列）の出力で検証。

### リスク
**極小**。seed 変更のみ。GA dynamics は seed 差で変わるが、これは検証目的そのもの（seed 感度の観測）。

## Run 84 実行パラメータ
| パラメータ | 値 | R83 からの変更 |
|-----------|-----|--------------|
| instrument | EUR_JPY | 不変 |
| population-size | 96 | 不変 |
| generations | 60 | 不変 |
| mutation-rate | 0.5 | 不変 |
| seed | **69** | **68 → 69（再現性検証、唯一の変更）** |
| max-workers | 2 | 不変 |
| stage-b-gate-kind | profit_safe_pfr | 不変 |

> Phase 3 (implement) はスキップ（実装対象なし）。Phase 4 で直接 R84 を実行する。
