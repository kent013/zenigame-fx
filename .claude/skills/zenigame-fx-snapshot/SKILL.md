---
name: zenigame-fx-snapshot
description: zenigame-fx Alpha Factory の Winners/Candidates/Config スナップショット管理（create/restore/list/delete）
argument-hint: '<create|restore|list|delete> [name] [--description "..."]'
user-invocable: true
---

# zenigame-fx スナップショット管理

zenigame-fx Alpha Factory の Winners/Candidates/Config のスナップショットを作成・復元・一覧・削除する。
Before/After 比較実験でのロールバック用。

**スクリプト**: `scripts/alpha_factory/snapshot_manager.py`

## 思考原則 / 使命 / 禁止事項

`zenigame-fx-codex-review` で定義される内容を適用する。

## 実行前提チェック

### script (必須)
- `scripts/alpha_factory/snapshot_manager.py`

### artifact (参照依存・skill では直接チェックしない)
- `.cache/alpha_factory/runs/winners_latest.json`
- `.cache/alpha_factory/runs/candidates_latest.json`
- `config/alpha_factory/default.yaml`

### related skill
- なし

### 未充足時挙動
本 skill は `scripts/alpha_factory/snapshot_manager.py` の不在を検出した時点でアボートし、不足依存を明示する。

artifact (`winners_latest.json` 等) 不足時の挙動は `scripts/alpha_factory/snapshot_manager.py` 側の責務であり本 skill の範疇外。snapshot_manager.py が config-only モードを許容するか厳格に 3 ファイル必須とするかは scripts 側で判定する。

zenigame 側スクリプトをフォールバック参照しない。

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
uv run python scripts/alpha_factory/snapshot_manager.py create {{name}} --description "{{description}}"
```

- 対象 3 ファイルを `.cache/alpha_factory/snapshots/{{name}}/` にコピー
- SHA256 チェックサムを `snapshot_meta.json` に記録
- `git rev-parse HEAD` で git コミットハッシュを記録
- アトミック: 一時ディレクトリにコピー→checksum→rename

#### restore（復元）

```bash
uv run python scripts/alpha_factory/snapshot_manager.py restore {{name}}
```

- 復元前に現在のファイルを `_pre_restore_{YYYYMMDD_HHMMSS}/` にバックアップ
- SHA256 チェックサムで整合性検証
- 3 ファイルを元の場所に上書きコピー

**重要**: restore 後は warmstart 対象の Run が変わるため、次の GA 実行で意図通りの seed が使われることを確認すること。

#### list（一覧表示）

```bash
uv run python scripts/alpha_factory/snapshot_manager.py list
```

#### delete（削除）

```bash
uv run python scripts/alpha_factory/snapshot_manager.py delete {{name}}
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
