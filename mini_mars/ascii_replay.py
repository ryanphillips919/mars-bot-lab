"""Terminal inspection of saved Mini Mars replays."""

from __future__ import annotations

import json
from pathlib import Path


def render(replay: dict, turn: int, view: str = "0") -> str:
    frames = replay["frames"]
    if not 0 <= turn < len(frames):
        raise ValueError(f"turn must be between 0 and {len(frames) - 1}")
    if view not in {"0", "1", "omniscient"}:
        raise ValueError("view must be 0, 1, or omniscient")
    frame = frames[turn]
    width, height = replay["config"]["width"], replay["config"]["height"]
    rocks = {(cell["x"], cell["y"]) for cell in replay["map"]["rocks"]}
    current_deposits = {(cell["x"], cell["y"]): cell for cell in frame["deposits"]}
    known: dict[tuple[int, int], dict] = {}
    if view != "omniscient":
        known = {(cell["x"], cell["y"]): cell for cell in frame["colonies"][int(view)]["known"]}
    board = []
    for y in range(height):
        row = []
        for x in range(width):
            point = (x, y)
            if view != "omniscient" and point not in known:
                symbol = "?"
            elif point in rocks:
                symbol = "#"
            else:
                deposit = current_deposits.get(point) if view == "omniscient" else known[point]
                if deposit and deposit["resource"] and deposit["quantity"] > 0:
                    symbol = ("G" if deposit["resource"] == "gold" else "I") if (
                        view == "omniscient" or deposit.get("visible")) else (
                            "g" if deposit["resource"] == "gold" else "i")
                else:
                    symbol = "." if view == "omniscient" or known[point]["visible"] else ","
            row.append(symbol)
        board.append(row)

    for colony in frame["colonies"]:
        for base in colony["bases"]:
            point = (base["x"], base["y"])
            if view == "omniscient" or colony["id"] == int(view) or known.get(point, {}).get("visible"):
                board[point[1]][point[0]] = "AB"[colony["id"]]
    occupants: dict[tuple[int, int], list[int]] = {}
    for rover in frame["rovers"]:
        point = (rover["x"], rover["y"])
        if view == "omniscient" or rover["player"] == int(view) or known.get(point, {}).get("visible"):
            occupants.setdefault(point, []).append(rover["player"])
    for (x, y), owners in occupants.items():
        board[y][x] = "*" if len(owners) > 1 else "ab"[owners[0]]

    colonies = frame["colonies"]
    lines = [f"Mini Mars | seed {replay['seed']} | turn {turn}/{len(frames) - 1} | view {view}",
             f"Gold P0 {colonies[0]['bank']['gold']} : P1 {colonies[1]['bank']['gold']}  "
             f"Iron P0 {colonies[0]['bank']['iron']} : P1 {colonies[1]['bank']['iron']}",
             "   " + "".join(str(x % 10) for x in range(width))]
    lines.extend(f"{y:02d} " + "".join(row) for y, row in enumerate(board))
    lines.append("? unseen  , remembered empty  . visible empty  # rock  G/I visible deposit  g/i remembered deposit")
    lines.append("A/B base  a/b rover  * stacked rovers; known deposit quantities may be stale outside vision")
    if frame["events"]:
        lines.append("Events: " + ", ".join(event["type"] for event in frame["events"][:8]))
    if frame["diagnostics"]:
        lines.append(f"Diagnostics: {len(frame['diagnostics'])} invalid actions or bot faults")
    return "\n".join(lines)


def view_file(path: Path, turns: str | None, step: bool, view: str) -> None:
    replay = json.loads(path.read_text(encoding="utf-8"))
    if replay.get("format") != "mini-mars-replay-v1":
        raise ValueError("not a Mini Mars replay")
    last = len(replay["frames"]) - 1
    if step:
        turn = 0
        while True:
            print(render(replay, turn, view))
            response = input("Enter next, p previous, turn number, or q quit > ").strip().lower()
            if response == "q":
                return
            if response == "p":
                turn = max(0, turn - 1)
            elif not response:
                turn = min(last, turn + 1)
            elif response.isdecimal():
                turn = min(last, int(response))
            else:
                print("Enter a turn number, p, or q.")
    else:
        selected = [int(item.strip()) for item in turns.split(",")] if turns else sorted({0, last // 4, last // 2, last * 3 // 4, last})
        for turn in selected:
            print(render(replay, turn, view), end="\n\n")
