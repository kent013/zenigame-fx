## 前提差分 (C4)
- 前提1: `run-35` と `run-36` は `fitness_pen` / `stage_a_pass` 一致率 100.0% で、cycle 3 介入は純観察だった（verified）。
- 前提2: 今回の主データは「Stage A 上位20% sidecar」であり、**条件付き集団**の観察である（C3）。
- 前提3: 早期 `top_n=1,3` を含むため、単点世代の解釈は弱く、世代帯平均（5–15 vs 50–60）を主根拠にする（C7）。
- 前提4: 判定対象H1は「探索圧が Stage B 要件（fold頑健性）と不整合か」であり、「絶対性能改善」自体ではない。

## 観察事実 (Facts、 C6)
- 後期で `fitness_pen_mean` は `0.051 -> 0.207`（+306%）。
- 同期間で `fold_sign_mean` は `0.297 -> 0.237`（-20%）。
- `pfre_mean` は `0.241 -> 0.296` と上がるが、Stage B 閾値 0.6 の約49%に留まる。
- `fold_sign_nonzero_ratio` は上昇（0.879 -> 0.985）だが、`n_fold_effective_mean` は微減（7.6 -> 7.0）。
- Best個体（g56_i28）は run-35/36 同一で Stage B pass=0 のまま。

## 仮説 H1 verified/falsified 判定
- **判定: verified（条件付き・中〜高信頼）**  
  Stage A 上位群で「`fitness_pen` 改善圧が強まる一方、fold頑健性指標が Stage B 閾値に収束しない」ため、探索圧不整合の観察と整合。

## 解釈・推論 (C9 反証可能性付き)
- 解釈: 現行目的は「利益/サイズ」寄りで、fold頑健性を十分に報酬化していない可能性が高い。
- 反証可能性:
  - 反証1: 同設定で複数runにて、後期 `fitness_pen_mean` 上昇と同時に `pfre_mean >= 0.4` が安定達成される。
  - 反証2: 上位20%だけでなく全体分布でも `pfre` が改善し、Stage B pass が自然発生（>0）する。
  - 反証3: 目的関数を変えずに、初期条件差だけで Stage B pass が再現的に出る。

## 次サイクル候補
- **採用候補（最有力）**: `fitness_pen` に fold-aware penalty 追加  
  `fitness_pen = fitness_raw - α·size_norm - β·max(0, 0.4 - pfre_clamped)`  
  `α=0.03` 維持、`β=0.05` 初期は妥当（最大追加ペナルティ0.02で過大ではない）。
- 検証基準（事前固定）:
  - 主KPI: `Stage B pass > 0`
  - 副KPI: 後期 `pfre_mean > 0.4`
  - ガード: trade数・overnight・複雑度の禁止事項を監視

## 全体判定: OK / CONCERN / CRITICAL_DRIFT / ACTIONABLE
- **ACTIONABLE**  
  問題は特定でき、単一介入で反証可能な次手が明確。

## Claude 分析との差分 (最後に確認)
- 現時点で Claude 側の独立分析本文が未提示のため、**厳密な差分照合は未実施**。  
- 暫定差分要約: 本判定は「H1 verified（条件付き）」かつ「cycle 4 は fitness_pen 拡張のみを唯一介入として承認」。