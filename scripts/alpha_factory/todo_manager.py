"""Alpha Factory TODO マネージャ。

TODO.md / TODO-closed.md の操作を一元化する。zenigame-fx-todo-add / zenigame-fx-todo-close /
zenigame-fx-implement など複数スキルから呼び出される。

Markdown のテーブル行をパイプ区切りで読み書きする。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parents[2]
TODO_PATH = REPO_ROOT / "docs" / "alpha_factory" / "TODO.md"
TODO_CLOSED_PATH = REPO_ROOT / "docs" / "alpha_factory" / "TODO-closed.md"

ALLOWED_THEMES = {
    "ga-architecture",
    "primitives",
    "stage-gate",
    "cross-pair",
    "statistics",
    "data-ingest",
    "swim-lane",
    "skill-port",
    "infrastructure",
    "general",
}
ALLOWED_PRIORITIES = {"Critical", "High", "Medium", "Low"}
ALLOWED_MODES = {"incremental", "standalone"}

OPEN_HEADER = (
    "| ID | タイトル | テーマ | 概要 | 優先度 | 実装モード | 設計 | 追加日時 |\n"
    "|----|---------|-------|------|-------|----------|------|---------|"
)
CONDITIONAL_HEADER = (
    "| ID | タイトル | テーマ | 概要 | トリガー条件 | 昇格時優先度 | 実装モード | 設計 | 追加日時 |\n"
    "|----|---------|-------|------|------------|------------|----------|------|---------|"
)
CLOSED_HEADER = (
    "| ID | タイトル | テーマ | 優先度 | 完了日時 | Run ID |\n"
    "|----|---------|-------|-------|---------|--------|"
)
OBSOLETED_HEADER = (
    "| ID | タイトル | テーマ | 優先度 | 廃止日時 | 理由 |\n"
    "|----|---------|-------|-------|---------|------|"
)

ID_PATTERN = re.compile(r"^T(\d+)$")


def ensure_todo_files() -> None:
    if not TODO_PATH.exists():
        TODO_PATH.parent.mkdir(parents=True, exist_ok=True)
        TODO_PATH.write_text(
            "# Alpha Factory TODO\n\n"
            "zenigame-fx Alpha Factory の改善タスク一覧。\n\n"
            "## Open\n\n"
            f"{OPEN_HEADER}\n\n"
            "## Conditional\n\n"
            f"{CONDITIONAL_HEADER}\n",
            encoding="utf-8",
        )
    if not TODO_CLOSED_PATH.exists():
        TODO_CLOSED_PATH.parent.mkdir(parents=True, exist_ok=True)
        TODO_CLOSED_PATH.write_text(
            "# Alpha Factory TODO (Closed/Obsoleted)\n\n"
            "## Closed\n\n"
            f"{CLOSED_HEADER}\n\n"
            "## Obsoleted\n\n"
            f"{OBSOLETED_HEADER}\n",
            encoding="utf-8",
        )


def _parse_section(text: str, section_name: str) -> tuple[list[str], tuple[int, int]]:
    """指定セクションのデータ行（テーブル本体）と、その範囲を返す。"""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == f"## {section_name}":
            start = i
            break
    if start is None:
        return [], (len(lines), len(lines))
    # セクションヘッダーの次のテーブルを探す
    header_start = None
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("|") and "---" not in lines[i]:
            header_start = i
            break
        if lines[i].startswith("## "):
            return [], (i, i)
    if header_start is None:
        return [], (len(lines), len(lines))
    # | id | ... | の次が ---- 行、その次からデータ行
    data_start = header_start + 2
    data_end = data_start
    while data_end < len(lines) and lines[data_end].startswith("|"):
        data_end += 1
    return lines[data_start:data_end], (data_start, data_end)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(path: Path, text: str) -> None:
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def _insert_row(text: str, section_name: str, row: str) -> str:
    """指定セクションのテーブル末尾に行を追加する。"""
    rows, (start, end) = _parse_section(text, section_name)
    lines = text.splitlines()
    # row が重複しない限り末尾に追加
    new_lines = lines[:end] + [row] + lines[end:]
    return "\n".join(new_lines)


def _remove_row_by_id(text: str, section_name: str, todo_id: str) -> tuple[str, str | None]:
    """指定 ID の行を削除し、(更新後テキスト, 削除された行) を返す。"""
    rows, (start, end) = _parse_section(text, section_name)
    lines = text.splitlines()
    removed = None
    new_rows = []
    for row in rows:
        cells = [c.strip() for c in row.split("|")[1:-1]]
        if cells and cells[0] == todo_id:
            removed = row
            continue
        new_rows.append(row)
    if removed is None:
        return text, None
    new_lines = lines[:start] + new_rows + lines[end:]
    return "\n".join(new_lines), removed


def cmd_next_id(args: argparse.Namespace) -> int:
    ensure_todo_files()
    text_open = _read(TODO_PATH)
    text_closed = _read(TODO_CLOSED_PATH)
    ids = []
    for section in ("Open", "Conditional"):
        rows, _ = _parse_section(text_open, section)
        for row in rows:
            cells = [c.strip() for c in row.split("|")[1:-1]]
            if cells:
                m = ID_PATTERN.match(cells[0])
                if m:
                    ids.append(int(m.group(1)))
    for section in ("Closed", "Obsoleted"):
        rows, _ = _parse_section(text_closed, section)
        for row in rows:
            cells = [c.strip() for c in row.split("|")[1:-1]]
            if cells:
                m = ID_PATTERN.match(cells[0])
                if m:
                    ids.append(int(m.group(1)))
    next_n = (max(ids) + 1) if ids else 1
    print(f"T{next_n:03d}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    if args.theme not in ALLOWED_THEMES:
        print(f"[error] theme must be one of {sorted(ALLOWED_THEMES)}", file=sys.stderr)
        return 2
    if args.priority not in ALLOWED_PRIORITIES:
        print(f"[error] priority must be one of {sorted(ALLOWED_PRIORITIES)}", file=sys.stderr)
        return 2
    if args.mode not in ALLOWED_MODES:
        print(f"[error] mode must be one of {sorted(ALLOWED_MODES)}", file=sys.stderr)
        return 2
    ensure_todo_files()
    text = _read(TODO_PATH)
    row = (
        f"| {args.id} | {args.title} | {args.theme} | {args.summary} | "
        f"{args.priority} | {args.mode} | {args.design_link} | {args.added_at} |"
    )
    text = _insert_row(text, "Open", row)
    _write(TODO_PATH, text)
    print(f"added {args.id} to Open")
    return 0


def cmd_add_conditional(args: argparse.Namespace) -> int:
    if args.theme not in ALLOWED_THEMES:
        print(f"[error] theme must be one of {sorted(ALLOWED_THEMES)}", file=sys.stderr)
        return 2
    if args.priority not in ALLOWED_PRIORITIES:
        print(f"[error] priority must be one of {sorted(ALLOWED_PRIORITIES)}", file=sys.stderr)
        return 2
    if args.mode not in ALLOWED_MODES:
        print(f"[error] mode must be one of {sorted(ALLOWED_MODES)}", file=sys.stderr)
        return 2
    ensure_todo_files()
    text = _read(TODO_PATH)
    row = (
        f"| {args.id} | {args.title} | {args.theme} | {args.summary} | "
        f"{args.trigger_condition} | {args.priority} | {args.mode} | "
        f"{args.design_link} | {args.added_at} |"
    )
    text = _insert_row(text, "Conditional", row)
    _write(TODO_PATH, text)
    print(f"added {args.id} to Conditional")
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    ensure_todo_files()
    text = _read(TODO_PATH)
    for section in ("Open", "Conditional"):
        rows, _ = _parse_section(text, section)
        for row in rows:
            cells = [c.strip() for c in row.split("|")[1:-1]]
            if cells and cells[0] == args.todo_id:
                print("|".join(cells))
                return 0
    print(f"[error] {args.todo_id} not found in Open/Conditional", file=sys.stderr)
    return 1


def _extract_cells(row: str) -> list[str]:
    return [c.strip() for c in row.split("|")[1:-1]]


def cmd_close(args: argparse.Namespace) -> int:
    ensure_todo_files()
    text = _read(TODO_PATH)
    text, removed = _remove_row_by_id(text, "Open", args.todo_id)
    if removed is None:
        print(f"[error] {args.todo_id} not found in Open", file=sys.stderr)
        return 1
    cells = _extract_cells(removed)
    # Open: [id, title, theme, summary, priority, mode, design, added_at]
    todo_id, title, theme, summary, priority = cells[0], cells[1], cells[2], cells[3], cells[4]
    _write(TODO_PATH, text)
    # Closed: [id, title, theme, priority, closed_at, run_id]
    text_closed = _read(TODO_CLOSED_PATH)
    row_closed = (
        f"| {todo_id} | {title} | {theme} | {priority} | {args.closed_at} | {args.run_id or '-'} |"
    )
    text_closed = _insert_row(text_closed, "Closed", row_closed)
    _write(TODO_CLOSED_PATH, text_closed)
    print(f"closed {todo_id} | {title} | {theme} | {priority}")
    return 0


def cmd_obsolete(args: argparse.Namespace) -> int:
    ensure_todo_files()
    text = _read(TODO_PATH)
    # Open と Conditional 両方を検索
    for section in ("Open", "Conditional"):
        text, removed = _remove_row_by_id(text, section, args.todo_id)
        if removed is not None:
            break
    else:
        print(f"[error] {args.todo_id} not found in Open/Conditional", file=sys.stderr)
        return 1
    cells = _extract_cells(removed)
    todo_id, title, theme = cells[0], cells[1], cells[2]
    # priority の位置はセクションによって異なる
    # Open: [id, title, theme, summary, priority, ...]
    # Conditional: [id, title, theme, summary, trigger_condition, priority, ...]
    priority = cells[4] if section == "Open" else cells[5]
    _write(TODO_PATH, text)
    text_closed = _read(TODO_CLOSED_PATH)
    row_obs = (
        f"| {todo_id} | {title} | {theme} | {priority} | {args.obsoleted_at} | {args.reason} |"
    )
    text_closed = _insert_row(text_closed, "Obsoleted", row_obs)
    _write(TODO_CLOSED_PATH, text_closed)
    print(f"obsoleted {todo_id} | {title} | {theme} | {priority}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    ensure_todo_files()
    text = _read(TODO_PATH)
    for section in ("Open", "Conditional"):
        rows, _ = _parse_section(text, section)
        print(f"## {section} ({len(rows)})")
        for row in rows:
            print(row)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Alpha Factory TODO manager")
    sub = parser.add_subparsers(dest="command", required=True)

    p_next = sub.add_parser("next-id", help="Return next available TODO ID")
    p_next.set_defaults(func=cmd_next_id)

    p_add = sub.add_parser("add", help="Add a TODO to Open table")
    p_add.add_argument("--id", required=True)
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--theme", required=True)
    p_add.add_argument("--summary", required=True)
    p_add.add_argument("--priority", required=True)
    p_add.add_argument("--mode", required=True)
    p_add.add_argument("--design-link", required=True)
    p_add.add_argument("--added-at", required=True)
    p_add.set_defaults(func=cmd_add)

    p_addc = sub.add_parser("add-conditional", help="Add a TODO to Conditional table")
    p_addc.add_argument("--id", required=True)
    p_addc.add_argument("--title", required=True)
    p_addc.add_argument("--theme", required=True)
    p_addc.add_argument("--summary", required=True)
    p_addc.add_argument("--trigger-condition", required=True)
    p_addc.add_argument("--priority", required=True)
    p_addc.add_argument("--mode", required=True)
    p_addc.add_argument("--design-link", required=True)
    p_addc.add_argument("--added-at", required=True)
    p_addc.set_defaults(func=cmd_add_conditional)

    p_get = sub.add_parser("get", help="Get a TODO row by ID")
    p_get.add_argument("todo_id")
    p_get.set_defaults(func=cmd_get)

    p_close = sub.add_parser("close", help="Close a TODO (Open → Closed)")
    p_close.add_argument("todo_id")
    p_close.add_argument("--closed-at", required=True)
    p_close.add_argument("--run-id", default="")
    p_close.set_defaults(func=cmd_close)

    p_obs = sub.add_parser("obsolete", help="Obsolete a TODO (Open/Conditional → Obsoleted)")
    p_obs.add_argument("todo_id")
    p_obs.add_argument("--obsoleted-at", required=True)
    p_obs.add_argument("--reason", required=True)
    p_obs.set_defaults(func=cmd_obsolete)

    p_list = sub.add_parser("list", help="List all Open/Conditional TODOs")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
