"""Persistent JSON Lines bot process: python -m mini_mars.bots.entry NAME --seed N."""

from __future__ import annotations

import argparse
import json
import sys

from .strategies import CoordinatedGreedy, GreedyMiner, RandomBot, StrategySettings, ValueGreedy
from .competition_starter import StarterBot


BOT_NAMES = ("random", "starter", "greedy", "greedy-no-cargo-guard", "value", "independent", "coordinated",
             "coordinated-harvest-first",
             "coordinated-harvest-scored",
             "coordinated-harvest-stable", "coordinated-harvest-cargo",
             "coordinated-harvest-reliable",
             "coordinated-stable",
             "coordinated-frontier-scored", "coordinated-adaptive",
             "coordinated-nearest", "coordinated-no-endgame",
             "coordinated-payback-build",
             "coordinated-no-explore", "coordinated-gold-only")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", choices=BOT_NAMES)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    bots = {
        "random": lambda: RandomBot(args.seed),
        "starter": StarterBot,
        "greedy": GreedyMiner,
        "greedy-no-cargo-guard": lambda: GreedyMiner(cargo_safety=False),
        "value": ValueGreedy,
        "independent": lambda: CoordinatedGreedy(StrategySettings(coordinate=False)),
        "coordinated": CoordinatedGreedy,
        "coordinated-harvest-first": lambda: CoordinatedGreedy(StrategySettings(gold_priority=True)),
        "coordinated-harvest-scored": lambda: CoordinatedGreedy(
            StrategySettings(gold_priority=True, frontier_value_mode="individual")),
        "coordinated-harvest-stable": lambda: CoordinatedGreedy(
            StrategySettings(gold_priority=True, stable_targets=True)),
        "coordinated-harvest-cargo": lambda: CoordinatedGreedy(
            StrategySettings(gold_priority=True, marginal_cargo_return=True)),
        "coordinated-harvest-reliable": lambda: CoordinatedGreedy(
            StrategySettings(gold_priority=True, stable_targets=True,
                             marginal_cargo_return=True)),
        "coordinated-stable": lambda: CoordinatedGreedy(StrategySettings(stable_targets=True)),
        "coordinated-frontier-scored": lambda: CoordinatedGreedy(
            StrategySettings(frontier_value_mode="individual")),
        "coordinated-adaptive": lambda: CoordinatedGreedy(
            StrategySettings(frontier_value_mode="individual", adaptive_exploration=True)),
        "coordinated-nearest": lambda: CoordinatedGreedy(StrategySettings(frontier_policy="nearest")),
        "coordinated-no-endgame": lambda: CoordinatedGreedy(StrategySettings(endgame_enabled=False)),
        "coordinated-payback-build": lambda: CoordinatedGreedy(StrategySettings(build_policy="payback")),
        "coordinated-no-explore": lambda: CoordinatedGreedy(StrategySettings(exploration_weight=0)),
        "coordinated-gold-only": lambda: CoordinatedGreedy(StrategySettings(iron_enabled=False,
                                                                            build_enabled=False)),
    }
    bot = bots[args.name]()
    for line in sys.stdin:
        observation = None
        try:
            observation = json.loads(line)
            response = {"turn": observation["turn"], "actions": bot.decide(observation)}
            targets = getattr(bot, "diagnostic_targets", None)
            if targets:
                response["targets"] = {key: list(point) for key, point in targets.items()}
        except Exception as error:
            print(f"bot input error: {error}", file=sys.stderr, flush=True)
            # Keep a valid turn when a supported observation triggered a bot
            # error. The engine then treats omitted rover actions as WAIT.
            turn = observation.get("turn", -1) if isinstance(observation, dict) else -1
            response = {"turn": turn, "actions": [], "bot_error": type(error).__name__}
        print(json.dumps(response, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
