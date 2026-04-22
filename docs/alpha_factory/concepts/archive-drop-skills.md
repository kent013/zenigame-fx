# Concept: archive-drop-skills

## 目的

zenigame から流用した skill 群のうち、zenigame-fx 環境で動かない 7 個を `.claude/skills/_archived/` に退避する。将来 FX 側に対応インフラが整った時に復活できるよう、理由を README に記録。

## 対象 skill（7 個）

- zenigame-enqueue-task（Dramatiq 依存）
- zenigame-manage-alert（Discord + systemd 依存）
- zenigame-manage-timer（systemd 依存）
- zenigame-restart-worker（systemd 依存）
- zenigame-troubleshoot-worker（systemd 依存）
- zenigame-primitive-ic-eval（J-Quants 依存）
- zenigame-primitive-ic-sync（J-Quants 依存）

## 方針

1. `.claude/skills/_archived/` 作成
2. `git mv` で 7 skill を退避
3. `_archived/README.md` に退避理由・復活条件を記録
4. AGENTS.md の skill 説明を更新

## 優先度・モード

- Priority: High（プロジェクト整理の基盤）
- Mode: incremental
- テーマ: skill-port
