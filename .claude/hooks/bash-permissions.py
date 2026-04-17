#!/usr/bin/env python3
"""PreToolUse hook that enforces Bash permissions from settings.json."""
import json
import sys
from pathlib import Path

def load_settings():
    """~/.claude/settings.json と .claude/settings.local.json から設定を読み込む"""
    allow_patterns = []
    deny_patterns = []

    # ユーザー設定とローカル設定を両方チェック
    settings_files = [
        Path.home() / ".claude" / "settings.json",
        Path("/Users/ishitoya/repository/zenigame/.claude/settings.local.json"),
    ]

    for settings_file in settings_files:
        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    permissions = settings.get("permissions", {})

                    for rule in permissions.get("allow", []):
                        if rule == "Bash":
                            # "Bash" だけの場合は全許可
                            return ["*"], []
                        if rule.startswith("Bash(") and rule.endswith(")"):
                            pattern = rule[5:-1]  # "Bash(uv:*)" -> "uv:*"
                            allow_patterns.append(pattern)

                    for rule in permissions.get("deny", []):
                        if rule.startswith("Bash(") and rule.endswith(")"):
                            pattern = rule[5:-1]
                            deny_patterns.append(pattern)
            except Exception:
                pass

    return allow_patterns, deny_patterns

def pattern_matches(pattern, command):
    """パターンマッチング - ワイルドカード対応"""
    command = command.strip()

    # 全許可パターン
    if pattern == "*":
        return True

    # "uv:*" 形式（プレフィックスマッチング）
    if pattern.endswith(":*"):
        prefix = pattern[:-2]
        # コマンドがプレフィックスで始まり、その後にスペースまたは行末がある
        return command.startswith(prefix + " ") or command == prefix

    # "uv *" 形式（グロブマッチング）
    if pattern.endswith(" *"):
        prefix = pattern[:-2]
        return command.startswith(prefix + " ") or command == prefix

    # 完全一致
    return command == pattern

def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if input_data.get("tool_name") != "Bash":
        sys.exit(0)

    command = input_data.get("tool_input", {}).get("command", "")
    allow_patterns, deny_patterns = load_settings()

    # Deny ルールを優先チェック
    for pattern in deny_patterns:
        if pattern_matches(pattern, command):
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Denied by pattern: {pattern}"
                }
            }))
            sys.exit(0)

    # Allow ルールをチェック
    for pattern in allow_patterns:
        if pattern_matches(pattern, command):
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": f"Allowed by pattern: {pattern}"
                }
            }))
            sys.exit(0)

    # どのパターンにもマッチしない場合は、デフォルト動作（ユーザーに確認）
    sys.exit(0)

if __name__ == "__main__":
    main()
