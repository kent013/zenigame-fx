# Concept: port-rename-only-skills

## 目的

zenigame-* skill のうち、**内容の修正がほぼ不要で名前空間とパス参照だけ直せば使える** もの 4 個を `zenigame-fx-*` として移植する。

## 対象 skill（4 個）

- zenigame-manage-sessions → zenigame-fx-manage-sessions
- zenigame-clear-cache → zenigame-fx-clear-cache
- zenigame-snapshot → zenigame-fx-snapshot
- zenigame-batch-ga → zenigame-fx-batch-ga（GA スクリプトパスを FX 側に）

## 方針

- zenigame 側のソースを Read → パス・参照を FX 側に置換 → zenigame-fx-* として Write
- 使命・禁止事項は `zenigame-fx-codex-review` から参照する記述に差し替え（skill に重複記載しない）
- 既存の zenigame-fx-codex-vscode / zenigame-fx-codex-review と整合

## 優先度・モード

- Priority: Medium
- Mode: incremental
- テーマ: skill-port
