# 詳細設計 (skeleton): T080 — T071 caller 注入式 Phase 2 配線

**作成日時**: 2026-05-02 11:30 JST
**status**: **skeleton (= 後続セッションで zenigame-fx-alpha-design による Codex review で詳細化)**
**改訂対象**: `scripts/alpha_factory/run_ga.py` (= Run 終了処理に build_run_observability_report 呼出追加) + 各 metric compute 関数の存在確認 + tests/

---

## 1. 使命・制約

T071 RunObservabilityReport の SSOT を runtime で活用、 smoke 5 Run の DoD 観測経路として必須。

## 2. 概念設計リファレンス

`/Users/ishitoya/repository/zenigame-fx/devnotes/20260502-1130-todo-t080-t071-caller-injection/conceptual-design.md`

## 3. 改訂対象一覧 (skeleton、 後続詳細化)

| # | 改訂名 | 変更箇所 | 性質 | 優先度 |
|---|---|---|---|---|
| 1 | run_ga.py の Run 終了処理に build_run_observability_report 呼出追加 | `scripts/alpha_factory/run_ga.py` (= 場所要特定) | 配線追加 | 高 |
| 2 | caller-supplied 値の収集 (= ab_divergence / archive_churn / bypass_ratio / front1_cardinality / feasible_ratio_ema 他) | run_ga.py 内ロジック追加 | 計算追加 | 高 |
| 3 | (任意) RunObservabilityReport の Markdown 出力経路 | run-report skill との統合 | 任意 | 低 |
| 4 | 既存 metric compute 関数の存在確認 + 不在分の補完 | (= 各 module、 grep で確認) | 確認 + 場合により実装 | 中 |
| 5 | tests/ で配線経路の test | tests/scripts/test_run_ga.py 等 | test 追加 | 中 |

## 4. 詳細実装方針 (skeleton)

### 4.1 run_ga.py 配線

```python
# Run 終了処理 (= 場所要特定、 detail-design で line range 明示)
from src.alpha_factory.observability.run_metrics import (
    build_run_observability_report,
)

run_observability_report = build_run_observability_report(
    # caller-supplied 値の keyword 引数注入
    ...
)

# 任意: report.md 出力
write_observability_report_markdown(run_observability_report, output_path)
```

### 4.2 各 metric compute 関数の調査結果 (= 後続詳細化)

| metric | compute 関数 | 存在確認 |
|---|---|---|
| ab_divergence | compute_a_b_correlation (T064) | 既存 |
| archive_churn | (= 要調査) | 後続 grep |
| bypass_ratio | (= 要調査) | 後続 grep |
| front1_cardinality | (= 要調査、 NSGA-II core で計算) | 後続 grep |
| feasible_ratio_ema | T066 (CPPS FSM) | 既存 |

## 5. 機械検証手順 (skeleton)

```bash
# run_ga.py から呼出があることを確認
grep -qE "build_run_observability_report" scripts/alpha_factory/run_ga.py \
  || { echo "FAIL: run_ga.py から呼出不在"; exit 1; }

# 各 metric の caller-supplied 値が計算されていることを確認
for metric in ab_divergence_value archive_churn_value bypass_ratio_value front1_cardinality_value feasible_ratio_ema_value; do
  grep -qE "${metric}=" scripts/alpha_factory/run_ga.py \
    || { echo "FAIL: ${metric} caller 渡し不在"; exit 1; }
done

# pytest
uv run pytest tests/scripts/test_run_ga.py -x
```

## 6. テスト計画 (skeleton)

- 新規 test: run_ga.py が Run 終了で build_run_observability_report を呼出すことを確認
- 新規 test: caller-supplied 値が正しく集計されていることを確認
- 既存 test 互換性確認

## 7. リスク (= 概念設計と同じ)

## 8. 実装モード

**incremental** (= 既存 run_ga.py に追加、 worktree todo/T080)

## 9. 後続セッションでの本格化手順

1. zenigame-fx-alpha-design skill 起動
2. run_ga.py の Run 終了処理を grep + Read で特定
3. 各 metric compute 関数の存在確認 + 不在分の補完計画
4. Codex 概念 + 詳細レビュー → APPROVED
5. zenigame-fx-implement で実装
