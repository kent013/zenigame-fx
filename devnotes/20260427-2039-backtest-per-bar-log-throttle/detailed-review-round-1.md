**前提（C4）**
- `verified`: 現行実装では per-bar の `logger.info` が 3 箇所ある（[engine.py:127](/Users/ishitoya/repository/zenigame-fx/src/backtest/engine.py:127), [engine.py:159](/Users/ishitoya/repository/zenigame-fx/src/backtest/engine.py:159), [mock.py:172](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py:172)）。
- `verified`: `drop_pending_open` の呼び出し元は提示 grep 上 `run_backtest` のみ。
- `verified`: 本変更は売買ロジック・価格計算ではなく observability 変更。
- `unverified`: `backtest.finished` の consumer が追加 field を常に無視できること（設計では検証計画止まり）。
- `unverified`: ruff で未使用引数 `reason` が許容される設定かどうか。

**C9 Falsification-first（反証先行）**
- 反証仮説1: 「ログ削減で壊れる」→ 仕様上は壊れない可能性が高いが、consumer 互換未検証なので完全反証はできず。
- 反証仮説2: 「性能改善は誇張」→ 妥当。改善量は INCONCLUSIVE（行数削減は確実、wall-clock は未確証）。
- 反証仮説3: 「テストで担保不足」→ 一部成立。consumer 互換と lint 設定依存の穴が残る。

**指摘（重大度順）**
- [Warning] `backtest.finished` 追加フィールドの downstream 互換は未証明。V7 を「計画」ではなく「実測結果」まで必須化すべき。
- [Warning] `drop_pending_open(reason=...)` はログ削除後に未使用引数化。`ARG001` ルール有効時に CI 失敗リスク。
- [Suggestion] 性能説明の「ns 単位」断定は根拠が弱いので、設計文では相対比較（logger呼び出し削減）に留めると安全。

**施策判定**
1. 施策1（per-bar log 削除 + 集計）: **REQUEST_CHANGES**
2. 施策2（テスト整備）: **APPROVE**（ただし consumer 互換検証テスト/確認ログを追加推奨）

**全体判定**
- **REQUEST_CHANGES**

**Fact**
- per-bar INFO 3 箇所削除案と `backtest.finished` 集約案は一貫している。
- 既存呼び出し元範囲は狭く、改修スコープは局所。

**Interpretation**
- 方針自体は妥当で、主目的（ログ騒音削減）は達成可能。
- ただし「互換性の実証不足」と「lint 設定依存リスク」が残るため、このまま即承認は避けるべき。  
- 上記2点を埋めれば承認可能。