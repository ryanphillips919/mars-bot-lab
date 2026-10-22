"""Small, named Mini Mars experiment presets; these are not Lucid rules."""

from __future__ import annotations

from dataclasses import replace

from mini_mars.engine.game import Config


SCENARIOS: dict[str, Config] = {
    "default": Config(),
    "full-info": replace(Config(), full_information=True),
    "scarce": replace(Config(), gold_pairs=5, iron_pairs=3),
    "obstacle-heavy": replace(Config(), rock_pairs=20),
    "short-horizon": replace(Config(), turns=40),
}


def resolve_config(config: Config | None, scenario: str | None) -> tuple[str, Config]:
    """Preserve explicit Config callers while ensuring named presets are exact."""
    if scenario == "custom" and config is not None:
        return "custom", config
    if scenario is not None:
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown scenario: {scenario}")
        preset = SCENARIOS[scenario]
        if config is not None and config != preset:
            raise ValueError("explicit config differs from named scenario preset")
        return scenario, preset
    if config is None:
        return "default", SCENARIOS["default"]
    for name, preset in SCENARIOS.items():
        if config == preset:
            return name, config
    return "custom", config
