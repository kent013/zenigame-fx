**前提 (C4)**
- 監査は提示された差分テキストを主対象に実施しました（手元 `main` 実ファイルは step1.5 状態）。
- 実行検証（pytest/ruff/mypy）は再実行していません。提示結果を前提に静的レビューしています。

**ファイル別判定**
- [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py): **APPROVE**
- [test_stage_gate_canonical_dual_path.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_stage_gate_canonical_dual_path.py): **REQUEST_CHANGES**
- [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260503-2049-B-phase2-step1.6-stage-b-per-fold-dual-path/detailed-design.md): **APPROVE**

**指摘**
- [Critical] なし。
- [Warning] `D1` 検証が 1 ケース弱いです。`test_stage_b_per_fold_canonical_log_helper_isolation_when_log_raises` は `stage == "B"` と payload key 存在しか見ておらず、`fold_sharpe / fold_reason / reason_counts` 不変を実質的に担保していません。`disabled` baseline との `passed / reason_codes / n_bars / payload deep equality` 比較に揃えるべきです。  
  対象: [test_stage_gate_canonical_dual_path.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_stage_gate_canonical_dual_path.py)
- [Suggestion] `fold_index` 契約をより厳密にするなら、`stage_label != "B_fold"` で `fold_index is not None` も reject すると誤用検知が早くなります。  
  対象: [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:173)
- [Suggestion] A4 の補強として、新規 test で `B_IS` / `C_base` についても `fold=` 不在を明示確認すると、optional kwarg 追加の後方互換性証明がより強くなります。  
  対象: [test_stage_gate_canonical_dual_path.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_stage_gate_canonical_dual_path.py)

**質問で指定された重点項目の判定**
- 物理隔離（別 try）: **成立**。`fold_sharpe/fold_reason/reason_counts` 更新経路と dual-path 経路は分離されており、干渉しにくい実装です。  
  対象: [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:920)
- `_log_canonical_dual_path` の `fold_index` ValueError: **helper 単体では成立**（D5）。  
- `n_fold_expected` 動的取得: **成立**（固定 fold 前提の反証に耐える）。  
- D3 monkeypatch が `stage_label='B_fold'` 限定か: **成立**（B_IS 透過の意図に整合）。

**C1-C9 監査**
- C1/C2/C3/C4/C6/C9: 準拠確認。
- C5: 該当薄。
- C7: 本差分は相関因果主張なしで問題なし。
- C8: 実行再検証未実施のため一部 **INCONCLUSIVE**。

**全体判定**
- **CHANGES_REQUESTED**（主因: D1 の log-raise 系テスト厳密性不足）。