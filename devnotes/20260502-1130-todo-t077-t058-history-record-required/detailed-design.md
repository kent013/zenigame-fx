# 詳細設計 (skeleton): T077 — T058 detailed-design 改訂 + HistoryRecord.applied_from_run_id v2 必須化

**作成日時**: 2026-05-02 11:30 JST
**status**: **skeleton (= 後続セッションで zenigame-fx-alpha-design による Codex review で詳細化)**
**改訂対象**: `src/alpha_factory/calibrate_gate_history.py` (1 file 直接編集) + `src/alpha_factory/calibrate_freeze.py` (hot-fix 経路削除) + `scripts/alpha_factory/calibrate_gate.py` (caller 確認) + `devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md` (T058 設計改訂) + 既存 test 更新

---

## 1. 使命・制約

zenigame-fx Alpha Factory 使命に従う。 docs-only ではなく **実装変更 + schema 厳密化 + 既存 test 更新** を伴う。

## 2. 概念設計リファレンス

`/Users/ishitoya/repository/zenigame-fx/devnotes/20260502-1130-todo-t077-t058-history-record-required/conceptual-design.md`

## 3. 改訂対象一覧 (skeleton、 後続詳細化)

| # | 改訂名 | 変更箇所 | 性質 | 優先度 |
|---|---|---|---|---|
| 1 | HistoryRecord.applied_from_run_id 必須化 | `src/alpha_factory/calibrate_gate_history.py` L97 | type 変更 | 高 |
| 2 | calibrate_freeze.py hot-fix 経路削除 | `src/alpha_factory/calibrate_freeze.py` L156-167 | コード削除 | 中 |
| 3 | T058 detailed-design 改訂 | `devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md` 該当箇所 | docs 改訂 | 中 |
| 4 | caller 整合確認 + 修正 | `scripts/alpha_factory/calibrate_gate.py` L454 | 確認 + 必要なら修正 | 中 |
| 5 | 既存 test 更新 | `tests/alpha_factory/test_calibrate_*.py` 等 | test 修正 | 中 |

## 4. 詳細実装方針 (skeleton、 後続詳細化)

各改訂の Before/After は後続セッションで本格化:
- 改訂 1: `applied_from_run_id: str | None = None` → `applied_from_run_id: str` (= default なし、 keyword-only 必須化)
- 改訂 2: L156-167 削除
- 改訂 3: T058 detailed-design 内の該当 schema table を「Required」 に変更
- 改訂 4: `run_id_resolved` の None 経路精査
- 改訂 5: 既存 `test_*.py` で `applied_from_run_id=None` 渡しを修正

## 5. 機械検証手順 (skeleton)

```bash
# applied_from_run_id Optional → Required 確認
grep -nE "applied_from_run_id: str$" src/alpha_factory/calibrate_gate_history.py \
  || { echo "FAIL: 必須化未完"; exit 1; }
! grep -nE "applied_from_run_id: str \| None" src/alpha_factory/calibrate_gate_history.py \
  || { echo "FAIL: Optional 残存"; exit 1; }

# calibrate_freeze.py hot-fix 経路削除確認
! grep -nE "applied_from_run_id is None" src/alpha_factory/calibrate_freeze.py \
  || { echo "FAIL: hot-fix 残存"; exit 1; }

# T058 detailed-design 改訂確認
grep -qE "applied_from_run_id.*Required" devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md \
  || { echo "FAIL: T058 改訂未完"; exit 1; }

# pytest regression
uv run pytest tests/alpha_factory/test_calibrate_*.py -x
uv run mypy src/alpha_factory/
```

## 6. テスト計画 (skeleton)

- 既存 test 更新: `applied_from_run_id=None` ケースを ValueError 検証に変更
- 新規 test: v2 record で None 渡し時に TypeError raise 確認

## 7. リスク (= 概念設計と同じ)

## 8. 実装モード

**incremental** (= 1 caller 単位の変更、 test 整合確認、 worktree todo/T077)

## 9. 後続セッションでの本格化手順

1. zenigame-fx-alpha-design skill 起動 (= 本 skeleton を input)
2. caller 全件マトリクス (= grep + 影響範囲確認) を詳細化
3. test 修正範囲を全件確定
4. 機械検証 grep を完成形に展開
5. Codex 概念 + 詳細設計レビュー → APPROVED まで
6. zenigame-fx-implement で実装
