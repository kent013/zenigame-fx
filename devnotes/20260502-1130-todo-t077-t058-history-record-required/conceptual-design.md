# 概念設計 (skeleton): T077 — T058 detailed-design 改訂 + HistoryRecord.applied_from_run_id v2 必須化

**作成日時**: 2026-05-02 11:30 JST
**起源**: cascade port v2 Phase 2 配線 handoff § 6 残作業 (= `devnotes/20260502-0710-cascade-port-v2-phase2-complete-handoff/handoff.md` § 6)
**性質**: schema 厳密化 (= type signature 変更 + caller 整合確認 + detailed-design 改訂)
**位置付け**: cascade port v2 follow-up (= 設計品質向上、 fail-closed 強化)
**status**: **skeleton (= 後続セッションで zenigame-fx-alpha-design による Codex review で詳細化)**

---

## 背景・課題

### 現状

`src/alpha_factory/calibrate_gate_history.py` L97 で:

```python
applied_from_run_id: str | None = None
```

= **Optional** (= None 許容)。 コメント (L88-90):

```
# T054: cross-run contamination guard 用メタデータ (optional、後方互換)。
# 既存 record (これらが None) は state file load 時に schema_version 不一致で
# 適用 skip となる (fail-closed)。新規書き込みでは必ず set される。
```

つまり「v1 record (= schema_version=None) では None 許容、 v2 record (= schema_version=1) では新規書込で必須」 の運用。 しかし type signature 上は **v2 でも None を受け入れる** = 設計と実装の乖離。

### T058 detailed-design の認識

T058 詳細設計 (`devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md`) で「v2 必須化」 が宣言されているが、 type 上は Optional のまま。 handoff § 6 で「detailed-design 改訂依頼 (HistoryRecord.applied_from_run_id v2 必須化)」 と申し送り済。

### 影響

- v2 record で `applied_from_run_id=None` が runtime に書き込まれると、 後続の calibrate_freeze.py で `None` を `distinct_run_ids.add(...)` に加算しようとして「異常 record」 として 1 件カウントされる (= L156-167 の hot-fix 経路)
- 本来は v2 record で None 不可 (= type で fail-fast) が望ましい

---

## 改善アイデア

### 改訂 1: HistoryRecord.applied_from_run_id を必須化

**Before** (Round 21):
```python
applied_from_run_id: str | None = None
```

**After** (本 TODO):
```python
applied_from_run_id: str  # v2 record では必須 (None 不可)
```

ただし既存 v1 record (= dataset_epoch_id 不在 record) は `from_dict_or_none` で早期 None return されるため、 v2 record のみが本 dataclass で構築される。 = v1 互換は維持されたまま、 v2 で必須化される。

### 改訂 2: detailed-design 改訂

T058 detailed-design の HistoryRecord 説明箇所を「v2 で applied_from_run_id 必須」 と明記。 schema 表で `Optional` → `Required` に。

### 改訂 3: caller 整合確認

`scripts/alpha_factory/calibrate_gate.py` L454 の `applied_from_run_id=run_id_resolved` で `run_id_resolved` が None になる経路がないか確認。 もしあれば fail-closed (= ValueError) または default 値 (= "unknown") を導入。

### 改訂 4: calibrate_freeze.py の hot-fix 経路削除

L156-167 の「None / 空文字 record は異常」 として skip する経路は、 必須化後は **不要** (= type で防がれる)。 削除して fail-fast に切替。

---

## 期待効果

- **fail-closed 強化**: v2 record で applied_from_run_id 漏れが type level で防がれる (= runtime に到達しない)
- **設計と実装の乖離解消**: T058 detailed-design 文言と type signature が一致
- **calibrate_freeze.py のロジック簡素化**: hot-fix 経路削除で見通し改善

---

## 実装方針 (概要)

### 変更ファイル

1. `src/alpha_factory/calibrate_gate_history.py`: `applied_from_run_id` 必須化
2. `scripts/alpha_factory/calibrate_gate.py`: caller の None 経路確認 + 修正
3. `src/alpha_factory/calibrate_freeze.py`: hot-fix 経路削除
4. `devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md`: 該当箇所改訂
5. tests/: 既存 test の `applied_from_run_id=None` ケース更新 (= 必須エラー検証に変更)

### 影響範囲

- caller 全件 (= calibrate_gate.py + 関連 test) の `applied_from_run_id` 渡し方を確認
- calibrate_freeze.py の `_distinct_run_ids` 計算経路の整合性

---

## 制約・前提

- v1 record 互換は維持 (= `from_dict_or_none` の早期 return 経路は不変)
- T058 detailed-design 改訂は本 TODO の中で実施 (= synthesis Round 22 改訂とは別軸、 詳細設計層のみ)
- 既存 calibrate-gate test の挙動変更は許容 (= None 渡しは ValueError raise が新仕様)

---

## スコープ外

1. v1 record 経路の deprecation (= 別 TODO、 Round 23 以降)
2. CALIBRATE_HISTORY_SCHEMA_VERSION の bump (= 必要に応じて本 TODO 内で判断、 デフォルトは bump なし)
3. calibrate_gate.py 全体のリファクタリング (= 本 TODO は applied_from_run_id 周辺のみ)

---

## リスク

| リスク | 影響 | 緩和 |
|---|---|---|
| 既存 test で applied_from_run_id=None ケースが多数あり、 修正範囲が広い | 中 | grep で全件特定 + 一括修正、 mypy 通過で網羅性確認 |
| calibrate_gate.py の caller で run_id 取得経路に bug あり None になる可能性 | 中 | 必須化前に caller 経路を全件確認、 None 出る経路があれば別 TODO で修正 |
| CALIBRATE_HISTORY_SCHEMA_VERSION bump 要否の判断 | 低 | type 制約変更のみ、 schema_version bump は不要 (= field 追加・削除なし) と判断 |

---

## 参考資料

- handoff: `devnotes/20260502-0710-cascade-port-v2-phase2-complete-handoff/handoff.md` § 6 残作業 5
- T058 detailed-design (改訂対象): `devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md`
- 実装: `src/alpha_factory/calibrate_gate_history.py` L85-131
- 関連: `src/alpha_factory/calibrate_freeze.py` L156-167 (hot-fix 経路、 削除候補)
- 関連: `scripts/alpha_factory/calibrate_gate.py` L454 (caller)

---

## skeleton から本格設計への昇格手順 (= 後続セッション)

1. `zenigame-fx-alpha-design` skill 起動 (= topic="t077-history-record-required")
2. 本 conceptual-design を 既存ファイルとして指定 (= `devnotes/20260502-1130-todo-t077-t058-history-record-required/conceptual-design.md`)
3. Codex 概念設計レビュー (gpt-5.4 / medium) → APPROVED まで
4. detailed-design.md 起草 (= 本 skeleton を本格化、 caller 全件マトリクス + 機械検証 grep + テスト計画)
5. Codex 詳細設計レビュー (gpt-5.3-codex / xhigh) → APPROVED まで
6. `zenigame-fx-implement` skill で実装 (worktree todo/T077)
