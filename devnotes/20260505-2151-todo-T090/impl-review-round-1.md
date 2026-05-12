前提（C4）  
- 実ファイル実行は行わず、提示された設計書・差分・テストログのみを根拠にレビューしています。  
- C1 Design-first として、まず詳細設計との整合を起点に判定しました。  

### 1. [src/alpha_factory/primitives/_bars_cache.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T090/src/alpha_factory/primitives/_bars_cache.py)  
判定: **概ね妥当**

- [Critical] なし
- [Warning] なし
- [Suggestion] docstring の「現行と完全に一致する」は「数値結果（有限値/quiet NaN）に関して一致」とスコープを限定すると誤読が減ります。`float()` 例外の発生タイミング（cast順序変更の影響）まで“完全同一”と読める表現は避けるのが安全です。

### 2. [tests/alpha_factory/primitives/test_bars_cache.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T090/tests/alpha_factory/primitives/test_bars_cache.py)  
判定: **要修正**

- [Critical] なし
- [Warning] `test_compute_microbenchmark_non_regression` が通常テストに hard assert で入っており、「非 blocker/観測」の設計意図と不一致です。CI ノイズで false positive を起こすリスクがあります（固定順序計測・共有環境ジッタ）。  
- [Suggestion] このテストは `@pytest.mark.benchmark` + デフォルトskip（例: 環境変数有効時のみ実行）に変更し、PR gate から外すのが妥当です。必要ならローカル観測用に残してください。

---

4段伝搬・スキーマ重点チェック  
- `config → GaConfig → genome.meta → consumer`: **本PRは対象外（変更なし）**  
- `GENOMES_SCHEMA → template → collect_stage_* → flush`: **本PRは対象外（変更なし）**  
- 新規カラム追加時4点セット: **該当なし**  
- logger追加要件: **新規伝搬値がないため該当なし**

全体判定: **CHANGES_REQUESTED**

理由  
- 主ロジック（_compute の local 化）は設計整合・数値同値性テストともに妥当。  
- ただし性能テストの扱いが設計意図（観測）と運用（gate）で不整合のため、テスト運用方針の修正を要求します。