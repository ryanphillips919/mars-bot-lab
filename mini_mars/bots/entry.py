"""Persistent JSON Lines bot process: python -m mini_mars.bots.entry NAME --seed N."""

from __future__ import annotations

import argparse
import json
import sys

from .strategies import CoordinatedGreedy, GreedyMiner, RandomBot, StrategySettings, ValueGreedy


BOT_NAMES = ("random", "greedy", "value", "independent", "coordinated",
             "coordinated-no-explore", "coordinated-gold-only")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", choices=BOT_NAMES)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    bots = {
        "random": lambda: RandomBot(args.seed),
        "greedy": GreedyMiner,
        "value": ValueGreedy,
        "independent": lambda: CoordinatedGreedy(StrategySettings(coordinate=False)),
        "coordinated": CoordinatedGreedy,
        "coordinated-no-explore": lambda: CoordinatedGreedy(StrategySettings(exploration_weight=0)),
        "coordinated-gold-only": lambda: CoordinatedGreedy(StrategySettings(iron_enabled=False,
                                                                            build_enabled=False)),
    }
    bot = bots[args.name]()
    for line in sys.stdin:
        try:
            observation = json.loads(line)
            response = {"turn": observation["turn"], "actions": bot.decide(observation)}
        except (KeyError, ValueError, TypeError) as error:
            print(f"bot input error: {error}", file=sys.stderr, flush=True)
            response = {"turn": -1, "actions": []}
        print(json.dumps(response, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
