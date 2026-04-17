---
name: zenigame-set-focus
description: Alpha Factoryフォーカステーマの設定・確認・クリア
argument-hint: '[theme] [--policy "..."] (speed, live-trading, performance, japan-market, signal-predictive-power, general, clear)'
user-invocable: true
---

# zenigame-set-focus

Alpha Factory改善サイクルのフォーカステーマを設定・確認する。

## 使い方

```
/zenigame-set-focus                                          # 現在の設定を表示
/zenigame-set-focus performance                              # テーマを変更
/zenigame-set-focus performance --policy "EVALフィルタ追加禁止"  # テーマ+ポリシーを設定
/zenigame-set-focus clear                                    # フォーカスなしに戻す
```

## コマンド

### 表示（引数なし）

`.cache/alpha_factory/focus-theme.json` を `Read` して現在の設定を表示する。
ファイルが存在しない場合は「フォーカスなし（優先度順のみ）」と表示。

### テーマ設定

引数で指定されたテーマを設定する。オプションで `--policy "..."` を指定するとポリシーメッセージも保存される。

**有効なテーマ**: `speed`, `live-trading`, `performance`, `japan-market`, `signal-predictive-power`, `general`

無効なテーマが指定された場合はエラーを表示して何もしない。

```bash
# 例: performanceに設定（ポリシーなし）
cat > .cache/alpha_factory/focus-theme.json << 'FOCUSEOF'
{
  "theme": "performance",
  "reason": "ユーザー指定",
  "policy": null,
  "updated_at": "TIMESTAMP"
}
FOCUSEOF

# 例: ポリシー付きで設定
cat > .cache/alpha_factory/focus-theme.json << 'FOCUSEOF'
{
  "theme": "signal-predictive-power",
  "reason": "ユーザー指定",
  "policy": "EVALフィルタの新規追加を禁止。シグナルのgross/tradeがcost/tradeを超えることだけに集中",
  "updated_at": "TIMESTAMP"
}
FOCUSEOF
```

`TIMESTAMP` は実行時の日時（`date +%Y-%m-%dT%H:%M:%S%z` 相当）に置き換える。
`--policy` が指定されていない場合は `"policy": null` とする。

設定後に以下を表示:
```
フォーカステーマを「{theme}」に設定しました。
{policy が null でない場合: ポリシー: 「{policy}」}
次回のimprove-cycleから {theme} テーマのTODOが最優先で選定されます。
```

### クリア（`clear`）

フォーカスなしに戻す。

```bash
rm -f .cache/alpha_factory/focus-theme.json
```

設定後に以下を表示:
```
フォーカステーマをクリアしました。TODOは優先度順のみで選定されます。
```

## 影響範囲

- `improve-cycle` Phase 1-1b: フォーカステーマとポリシーの読み込み
- `improve-cycle` Phase 1-6: TODO選定時にフォーカステーマのTODOを最優先 + ポリシーを選定文脈に反映
- `improve-cycle` Phase 1-7: Codexプロンプトにフォーカステーマとポリシーを反映
- `post-run-review` Phase 1-1c: フォーカスポリシーの読み込み
- `post-run-review` Phase 2-2: Codexプロンプトにフォーカスポリシーを反映（新TODO生成の制約）
