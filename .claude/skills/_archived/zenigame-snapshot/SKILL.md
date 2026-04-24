---
name: zenigame-snapshot
description: Winners/Candidates/Configスナップショット管理（create/restore/list/delete）
argument-hint: '<create|restore|list|delete> [name] [--description "..."]'
user-invocable: true
---

# スナップショット管理

Alpha Factoryの Winners/Candidates/Config のスナップショットを作成・復元・一覧・削除する。
Before/After比較実験でのロールバック用。

**スクリプト**: `scripts/trading/snapshot_manager.py`

---

## 対象ファイル

| ファイル | パス |
|---------|------|
| Winners | `.cache/alpha_factory/runs/winners_latest.json` |
| Candidates | `.cache/alpha_factory/runs/candidates_latest.json` |
| Config | `config/alpha_factory/default.yaml` |

## 手順

### Step 1: 操作の実行

引数 `action` に応じて `snapshot_manager.py` を実行する。

#### create（スナップショット作成）

```bash
uv run python scripts/trading/snapshot_manager.py create {{name}} --description "{{description}}"
```

- 対象3ファイルを `.cache/alpha_factory/snapshots/{{name}}/` にコピー
- SHA256チェックサムを `snapshot_meta.json` に記録
- `git rev-parse HEAD` でgitコミットハッシュを記録
- アトミック: 一時ディレクトリにコピー→checksum→rename

#### restore（復元）

```bash
uv run python scripts/trading/snapshot_manager.py restore {{name}}
```

- 復元前に現在のファイルを `_pre_restore_{YYYYMMDD_HHMMSS}/` にバックアップ
- SHA256チェックサムで整合性検証
- 3ファイルを元の場所に上書きコピー

**重要**: restore後は warmstart 対象のRunが変わるため、次のGA実行で意図通りのseedが使われることを確認すること。

#### list（一覧表示）

```bash
uv run python scripts/trading/snapshot_manager.py list
```

#### delete（削除）

```bash
uv run python scripts/trading/snapshot_manager.py delete {{name}}
```

### Step 2: 結果報告

コマンドの出力をユーザーに表示する。エラーが発生した場合はエラー内容を報告する。

---

## ストレージ

```
.cache/alpha_factory/snapshots/
  {name}/
    winners_latest.json
    candidates_latest.json
    default.yaml
    snapshot_meta.json    # {name, created_at, source_run_id, git_commit, description, file_checksums}
  _pre_restore_{YYYYMMDD_HHMMSS}/   # restore時の自動バックアップ
    winners_latest.json
    candidates_latest.json
    default.yaml
    backup_meta.json
```
