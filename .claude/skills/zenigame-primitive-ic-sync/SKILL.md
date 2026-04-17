# Primitive IC Sync

IC summary を読んで schema.py/_registry.py への schema 変更を**ユーザー承認後にコミット**する。
improve-cycle から呼ばれる（analyze-run と plan-and-design の間）。単独でも実行可能。

## Verdict 閾値（スキルから変更不可・Python コード定数として固定）

```
RETIRE: 全horizon t_stat < 1.0 かつ IC平均 < 0.01
WATCH:  主要horizon t_stat < 2.0 → IC-score低下のみ（schema変更なし）
RETAIN: 主要horizon t_stat >= 2.0 → 変更なし
```

---

## フロー

### Step 1: IC summary チェック

- `.cache/alpha_factory/primitive_ic/latest_summary.json` が存在するか確認
- 存在しない → 「IC 評価未実施（`/zenigame-primitive-ic-eval` を先に実行）」と報告してスキップ
- `generated_at` が 30 日超 → 「IC summary が古いです（{date}）。参考値として処理を続行します」と警告

### Step 2: 変更案の生成

**RETIRE 候補**（全 horizon t_stat < 1.0 かつ IC 平均 < 0.01）:
- `_registry.py` の `PRIMITIVE_REGISTRY` から削除
- `_registry.py` の import 行をコメントアウト
- `schema.py` の `SIGNAL_PARAM_RANGES` から削除
- 変更箇所にコメント追記: `# IC-RETIRE {generated_at}: t_stat={値}`

**WATCH 候補**（主要 horizon t_stat < 2.0）:
- schema 変更なし（IC-score が自動的に低くなるため）
- ユーザーへの情報提供のみ

**変更なし（RETAIN）**:
- 報告のみ

### Step 3: ユーザーへの変更案提示

```markdown
## IC Sync 変更案

### RETIRE 対象（schema.py から削除）
| Primitive | t_stat(h5) | IC_mean(h5) | 理由 |
|-----------|-----------|------------|------|

### WATCH 対象（情報のみ、schema 変更なし）
| Primitive | t_stat(h5) | 推奨 |
|-----------|-----------|------|

→ 変更を適用しますか？ (y/N)
```

### Step 4: ユーザー確認

- "y" → Step 5 へ
- "N" or その他 → 「スキップしました」と報告して終了
- improve-cycle から呼ばれた場合は自動的にスキップ（改善サイクルを止めない）

### Step 5: 変更の適用

- Edit ツールで `_registry.py` と `schema.py` を変更
- `uv run pytest tests/alpha_factory/ -x` で確認（FAIL ならロールバック案内）
- コミット:
  ```bash
  git add src/trading/alpha_factory/dsl/primitives/_registry.py
  git add src/trading/alpha_factory/dsl/schema.py
  git commit -m "chore: IC-sync - retire {N}個のプリミティブ ({date}評価結果に基づく)"
  ```

### Step 6: 完了報告

- 実施した変更の一覧
- 次のステップ（plan-and-design への引継ぎ）
