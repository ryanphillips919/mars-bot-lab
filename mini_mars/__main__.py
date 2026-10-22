"""Mini Mars command line interface."""

from __future__ import annotations

import argparse
from pathlib import Path

from mini_mars.ascii_replay import view_file
from mini_mars.runner.match import run_match
from mini_mars.runner.tournament import run_tournament


def main() -> None:
    parser = argparse.ArgumentParser(description="Mini Mars bot programming simulator")
    commands = parser.add_subparsers(dest="command", required=True)
    match = commands.add_parser("match", help="run one two-player match")
    tournament = commands.add_parser("tournament", help="run paired seeded matches")
    replay = commands.add_parser("replay", help="inspect a saved replay in the terminal")
    for command in (match, tournament):
        command.add_argument("--bot-a", default="greedy", help="random, greedy, coordinated, or a command")
        command.add_argument("--bot-b", default="coordinated", help="random, greedy, coordinated, or a command")
        command.add_argument("--seed", type=int, default=42)
        command.add_argument("--timeout", type=float, default=1.0, help="seconds per bot response")
    match.add_argument("--no-replay", action="store_true")
    tournament.add_argument("--matches", type=int, default=10, help="number of seeds; each runs twice with swapped slots")
    tournament.add_argument("--save-replays", action="store_true")
    replay.add_argument("path", type=Path)
    replay.add_argument("--turns", help="comma-separated turns, e.g. 0,10,50,100")
    replay.add_argument("--step", action="store_true", help="step interactively through turns")
    replay.add_argument("--view", choices=("0", "1", "omniscient"), default="0")
    args = parser.parse_args()
    if args.command == "match":
        result = run_match((args.bot_a, args.bot_b), args.seed, save_replay=not args.no_replay,
                           timeout_seconds=args.timeout)
        winner = "tie" if result["winner"] is None else f"player {result['winner']}"
        print(f"Seed {args.seed}: {result['scores'][0]}–{result['scores'][1]} gold; {winner}; "
              f"{result['turns']} turns")
        print(f"Summary: {result['output_dir']}/summary.json")
        if result["replay"]:
            print(f"Replay: {result['replay']}")
        if any(result["invalid_actions"] + result["timeouts"] + result["crashes"]):
            print(f"Diagnostics: invalid {result['invalid_actions']}, timeouts {result['timeouts']}, "
                  f"bot faults {result['crashes']}")
    elif args.command == "tournament":
        report = run_tournament(args.bot_a, args.bot_b, args.matches, args.seed,
                                save_replays=args.save_replays, timeout_seconds=args.timeout)
        print(f"{report['games_played']} games from {args.matches} paired seeds; "
              f"A {report['wins']['a']} wins, B {report['wins']['b']} wins, "
              f"{report['wins']['ties']} ties, {report['failed_matches']} failed")
        print(f"A win rate (ties half): {report['win_rate_a']:.1%}" if report["win_rate_a"] is not None else "No completed games")
        print(f"Average gold: A {report['average_gold']['a']:.2f}, B {report['average_gold']['b']:.2f}" if report["games_played"] else "")
        print(f"Average score difference (A−B): {report['average_score_difference_a_minus_b']:.2f}" if report["games_played"] else "")
        print(f"Report: {report['output_dir']}/tournament.json")
    else:
        view_file(args.path, args.turns, args.step, args.view)


if __name__ == "__main__":
    main()
