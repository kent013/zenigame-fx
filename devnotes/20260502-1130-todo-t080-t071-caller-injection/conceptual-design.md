# 概念設計 (skeleton): T080 — T071 caller 注入式 Phase 2 配線 (= run_ga.py から build_run_observability_report 呼出追加)

**作成日時**: 2026-05-02 11:30 JST
**起源**: cascade port v2 Phase 2 配線 handoff § 6 残作業 4
**性質**: 配線追加 (= run_ga.py に build_run_observability_report 呼出 + caller-supplied 値の収集)
**位置付け**: cascade port v2 follow-up (= observability 経路の最終配線、 smoke 5 Run の DoD 観測 SSOT 取得経路)
**status**: **skeleton (= 後続セッションで zenigame-fx-alpha-design による Codex review で詳細化)**

---

## 背景・課題

### 現状

T071 で `src/alpha_factory/observability/run_metrics.py` に `RunObservabilityReport` (集約 dataclass) と `build_run_observability_report` (aggregator 関数、 L1098-) が実装済み。 ただし **`scripts/alpha_factory/run_ga.py` から呼ばれていない**:

```bash
$ grep -nE "build_run_observability_report" /Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py
(出力なし = 呼出経路なし)
```

### Phase 2 配線が中途半端な状態

T071 の docstring (run_metrics.py L48-55):

```
Use:
    - ``scripts/alpha_factory/run_ga.py``: build_run_observability_report 呼び出し
    - ...
    - run report Markdown 化: RunObservabilityReport を report.md に整形
```

= run_ga.py からの呼出が **意図された配線**、 ただし未実装。 = handoff § 6 の「T071 caller 注入式 Phase 2 配線 (= run_ga.py で必要な値を計算して T071 関数に注入)」。

### 影響

- smoke 5 Run で DoD 観測 SSOT (= `SmokeObservabilityProjection` field 群) の元値が **収集されない**
- A→B 乖離 / archive churn / bypass / front1 cardinality / feasible_ratio_ema 等の監視値が runtime で取得不可
- T071 の SSOT が「定義はあるが使われていない」 状態

---

## 改善アイデア

### 改訂 1: run_ga.py の Run 終了処理に build_run_observability_report 呼出追加

```python
# scripts/alpha_factory/run_ga.py の Run 終了処理 (= 場所要特定)

from src.alpha_factory.observability.run_metrics import (
    build_run_observability_report,
)

# Run 終了時:
ab_divergence = compute_a_b_correlation(a_proxy_scores, b_pooled_scores)  # T064 既存
archive_churn = compute_archive_churn(archive_history)  # 要収集
bypass_ratio = compute_bypass_ratio(stage_a_passes)  # 要収集
front1_cardinality = compute_front1_cardinality(pareto_front)  # 要収集
feasible_ratio_ema = compute_feasible_ratio_ema(run_history)  # T066 既存

run_observability_report = build_run_observability_report(
    ab_divergence_value=ab_divergence,
    archive_churn_value=archive_churn,
    bypass_ratio_value=bypass_ratio,
    front1_cardinality_value=front1_cardinality,
    feasible_ratio_ema_value=feasible_ratio_ema,
    # ... その他 caller-supplied 値
)
```

### 改訂 2: caller-supplied 値の収集経路確立

各 metric の元値を run_ga.py で計算するために、 関連経路の grep + 配線:
- A→B 乖離: `compute_a_b_correlation` (T064 で実装済) を Run 終了で呼出
- archive churn: archive admission/eviction の history から計算
- bypass ratio: Stage A の bypass count から計算
- front1 cardinality: Pareto front 1 の size から計算
- feasible_ratio_ema: T066 既存

### 改訂 3: report Markdown 化経路 (= 任意)

`RunObservabilityReport` を `reports/run-reports/run-{N}.md` に整形して出力する経路を追加 (= 既存の run-report skill との統合)。

---

## 期待効果

- **smoke 5 Run で DoD 観測 SSOT 元値が取得可能** (= cascade port v2 完全完了の前提条件)
- **observability 経路の最終配線完了** (= T071 SSOT が runtime で活用される)
- **Run-26 崩壊原因の追跡可能性向上** (= ab_divergence や bypass_ratio が記録される)

---

## 実装方針 (概要)

### 変更ファイル

1. `scripts/alpha_factory/run_ga.py`: Run 終了処理に build_run_observability_report 呼出 + caller-supplied 値計算 (= 場所要特定、 概念設計時に grep)
2. (= 任意) `scripts/alpha_factory/run_ga.py` または別 script: RunObservabilityReport の Markdown 出力経路
3. tests/: run_ga.py の build_run_observability_report 呼出経路の test
4. 関連 module 確認: 各 metric の compute 関数が既存か、 新規実装が必要か

### 影響範囲

- run_ga.py の Run 終了処理 (= 既存ロジックの最後に追加)
- 各 metric compute 関数の存在確認 (= 一部は T058-T075 で実装済、 一部は新規必要)

---

## 制約・前提

- run_ga.py への追加は incremental (= 既存ロジック touch なし、 末尾に追加)
- caller-supplied 値は run_ga.py が計算 (= T071 module は受け取るのみ、 keyword 引数注入規範 = T071 設計規範継承)
- Phase 2 切替前に完了させる (= smoke 5 Run の DoD 観測経路として必須)

---

## スコープ外

1. RunObservabilityReport の Markdown 出力 lint / 自動 CI (= 別 TODO)
2. 観測値分布の dashboard 化 (= 別 TODO)
3. 各 metric の数値 threshold 確定 (= smoke 後再校正、 別 TODO)

---

## リスク

| リスク | 影響 | 緩和 |
|---|---|---|
| 各 metric compute 関数が未実装 (= 新規必要) | 中 | 概念設計時に既存関数の grep で全件確認、 不在分は別 sub-TODO 化 |
| run_ga.py の Run 終了処理の正確な場所が不明 | 低 | grep + Read で特定、 detail-design で line range 明示 |
| caller-supplied 値の計算で run 中の state を参照できない設計差異 | 中 | T071 関数は keyword-only 引数で柔軟、 必要に応じて中間 dict 経由 |

---

## 参考資料

- handoff: `devnotes/20260502-0710-cascade-port-v2-phase2-complete-handoff/handoff.md` § 6 残作業 4
- T071 detailed-design: `devnotes/20260502-0338-cascade-port-T071-complete-handoff/handoff.md`
- 実装: `src/alpha_factory/observability/run_metrics.py` L1098-1115 (build_run_observability_report)
- caller 候補: `scripts/alpha_factory/run_ga.py` Run 終了処理

---

## skeleton から本格設計への昇格手順

1. zenigame-fx-alpha-design skill 起動 (= topic="t080-caller-injection")
2. run_ga.py の Run 終了処理 grep + 各 metric compute 関数の存在確認
3. caller-supplied 値の収集経路マトリクス作成
4. Codex 概念 + 詳細設計レビュー → APPROVED まで
5. zenigame-fx-implement で実装 (worktree todo/T080)
