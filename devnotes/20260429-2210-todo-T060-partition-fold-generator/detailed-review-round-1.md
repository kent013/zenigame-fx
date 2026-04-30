**前提検証 (C4)**
- Verified: T060 設計は Phase 1 を `partition.py` + `test_partition.py` に限定し、runtime 非影響を明記しています（[detailed-design.md:28](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/detailed-design.md:28), [detailed-design.md:461](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/detailed-design.md:461)）。
- Verified: C3/C7 N/A の扱いは設計に明記済みです（[detailed-design.md:362](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/detailed-design.md:362)）。
- **INCONCLUSIVE**: T059 前提依存は明記されていますが、現HEADには `epoch_manager.py` が存在せず、依存解決後の実コード成立性は未検証です（[detailed-design.md:64](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/detailed-design.md:64), [detailed-design.md:371](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/detailed-design.md:371), [src/alpha_factory](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory)）。

**施策1: `partition.py` 新規**  
判定: **REQUEST_CHANGES**

- [Critical] Phase 2 申し送り「7箇所」は現行コード整合の観点で不足です。  
  Fact: 設計は Stage B 旧 field 削除を宣言（[detailed-design.md:465](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/detailed-design.md:465)）。一方、`stage_b_window_months` / `wf_*` は `calibrate_state.py` と `aux_preflight.py` でも参照中です（[calibrate_state.py:74](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_state.py:74), [aux_preflight.py:52](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/aux_preflight.py:52), [aux_preflight.py:189](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/aux_preflight.py:189)）。  
  Interpretation: Phase 2 で7箇所だけ更新すると、属性欠落/契約不整合を残す可能性が高いです。申し送り対象へ上記2ファイル（少なくとも）を追加してください。

- [Warning] UTC厳密性が仕様文言より緩いです。  
  Fact: `Period.__post_init__` は「tzinfoあり」しか検証していません（[detailed-design.md:129](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/detailed-design.md:129)）。  
  Interpretation: `+09:00` など非UTC aware値が通るため、将来の境界比較で時差混入リスクがあります。`utcoffset()==timedelta(0)` まで縛る方が安全です。

- [Suggestion] C2 parallel-path の明示を一段強化してください。  
  Fact: 旧経路 (`walk_forward`) と新経路 (`Partition/Fold`) が Phase 2 まで並立します（[detailed-design.md:464](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/detailed-design.md:464)）。  
  Interpretation: 「旧経路に新定数を逆流させない」「新経路を run-time に配線しない」チェック項目を DoD に1行追加すると移行事故を減らせます。

**施策2: `test_partition.py` 新規**  
判定: **APPROVE**

- [Suggestion] UTC厳密性のテストを1件追加推奨です。  
  `UTC aware は許可、非UTC aware（例: JST）は拒否` を入れると、上記 Warning を設計段階で閉じられます。

**全体判定**  
**CHANGES_REQUESTED**