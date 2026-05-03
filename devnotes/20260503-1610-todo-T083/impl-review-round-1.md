保存先 `devnotes/20260503-1610-todo-T083/impl-review-round-1.md` への書き込みは、今回の制約（コマンド実行・ファイル書き込み禁止）により実施していません。以下に、そのまま保存可能なレビュー本文を出します。

## Round 1 Review (Falsification-first)

### 前提検証 (C4)
- Verified: 設計書 Round 4 の要求（helper再利用、Stage B/C追加、21ケース）を確認。
- Verified: commit A は rename+docstring+1 caller 更新のみ（pure refactor）。
- Verified: commit B 差分は Stage B IS / Stage C base の dual-path 配線＋テスト追加のみ。
- Unverified: B2/B3（smoke 5 のRSS/時間）は実測ログ未提示のため INCONCLUSIVE。
- Unverified: ruff/mypy/pytest は提出結果を事実として採用（再実行はしていない）。

---

## Findings

### [Critical] A5（fixture-locked回帰）の要件をテストが満たしていない
**Fact**
- 設計は「canonical sidecar の fixture-locked 期待値一致」を要求（[detailed-design.md:603](/Users/ishitoya/repository/zenigame-fx/devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/detailed-design.md:603), [detailed-design.md:547](/Users/ishitoya/repository/zenigame-fx/devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/detailed-design.md:547)）。
- 実装テストは `finite` / `isinstance(bool)` / `trade_count` 程度で、固定期待値比較をしていない（[test_stage_gate_canonical_dual_path.py:870](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T083/tests/alpha_factory/test_stage_gate_canonical_dual_path.py:870), [test_stage_gate_canonical_dual_path.py:912](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T083/tests/alpha_factory/test_stage_gate_canonical_dual_path.py:912), [test_stage_gate_canonical_dual_path.py:965](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T083/tests/alpha_factory/test_stage_gate_canonical_dual_path.py:965)）。

**Interpretation**
- canonical式の退行（係数変更・丸め・universe計算のズレ）を検知できず、A5達成主張を反証できる。

**修正案**
- 6本の golden テストを「`CanonicalFiveResult` の主要 field（`net_pnl_after_cost`, `max_dd`, `sr_session_worst_block_scale`, `session_block_win_rate_worst`, `gate_worst_gap`, `gate_pass`）の固定値比較」に変更。
- 浮動小数は `pytest.approx` で許容差を明示。
- 境界ケースは `isinstance(bool)` ではなく期待真偽値を固定。

---

### [Warning] 「canonical raise時もlegacy不変」の検証が弱い
**Fact**
- 設計文言は「non-monkeypatch版と一致」を要求（[detailed-design.md:499](/Users/ishitoya/repository/zenigame-fx/devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/detailed-design.md:499)）。
- 実テストは `stage == "B"/"C"` と一部キー存在のみ（[test_stage_gate_canonical_dual_path.py:551](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T083/tests/alpha_factory/test_stage_gate_canonical_dual_path.py:551), [test_stage_gate_canonical_dual_path.py:733](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T083/tests/alpha_factory/test_stage_gate_canonical_dual_path.py:733)）。

**Interpretation**
- 例外注入時の「legacy値不変」を十分に証明していない。

**修正案**
- baseline結果と monkeypatch結果で `passed/reason_codes/payload` の deep equality を追加。
- もし仕様上「不変」ではなく「no-crash」なら、設計書文言を明確に修正。

---

### [Warning] ログ検証が文字列包含ベースで、B5/C1-C3の契約検証として弱い
**Fact**
- 現状は `capsys` で `"B_IS"` / `"C_base"` 文字列を探索（[test_stage_gate_canonical_dual_path.py:632](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T083/tests/alpha_factory/test_stage_gate_canonical_dual_path.py:632), [test_stage_gate_canonical_dual_path.py:812](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T083/tests/alpha_factory/test_stage_gate_canonical_dual_path.py:812)）。

**Interpretation**
- event名・必須キー（`stage/genome/error/error_type`）の欠落を取りこぼしうる。

**修正案**
- structlog capture でイベント dict を直接検証し、B5/C1-C3のキー契約を明示アサート。

---

### [Suggestion] 設計書のケース数記述にドリフトあり
- [detailed-design.md:686](/Users/ishitoya/repository/zenigame-fx/devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/detailed-design.md:686) が「+10 ケース」となっており、他箇所の「+21」と不一致。監査時の混乱要因になるため統一推奨。

---

## ファイル別判定

- `devnotes/.../conceptual-design.md`: **APPROVE**
- `devnotes/.../detailed-design.md`: **REQUEST_CHANGES**（A5検証要件と実テスト実態の乖離、記述ドリフト）
- `src/alpha_factory/stage_gate.py`: **APPROVE**（helper再利用・Stage A同型配線・archive非変更を満たす）
- `src/alpha_factory/canonical_adapter.py`: **APPROVE**（step 1 凍結契約を維持）
- `src/alpha_factory/canonical_metrics.py`: **APPROVE**（本stepで未変更、契約整合）
- `tests/alpha_factory/test_stage_gate_canonical_dual_path.py`: **REQUEST_CHANGES**（A5固定値回帰不足、例外隔離検証の強度不足）

---

## 追加観点チェック

- 設計一致性: 部分一致（実装配線は一致、検証強度が不足）
- 正確性: 実装ロジック自体は大きな破綻なし
- パフォーマンス: **INCONCLUSIVE**（B2/B3実測未確認）
- 一貫性: 命名・dual-path pattern は整合
- テスト網羅性: 件数は満たすが、受入基準の質的達成が不足
- ruff/mypy: 提出結果ベースで問題なし
- 禁止事項違反: 明確な違反は未検出

---

## 全体判定

**CHANGES_REQUESTED**