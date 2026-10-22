.PHONY: setup test demo demo-mini-mars view view-mini-mars setup-lux demo-lux

setup:
	bash scripts/setup_halite.sh

test:
	python3 -m unittest discover -s tests -v
	python3 -m unittest discover -s mini_mars/tests -v

demo:
	python3 -m experiments.match

demo-mini-mars:
	python3 -m mini_mars match --bot-a greedy --bot-b coordinated --seed 42

view:
	python3 -m experiments.replay_server

view-mini-mars:
	python3 -m mini_mars.viewer

setup-lux:
	bash scripts/setup.sh

demo-lux:
	.venv/bin/python -m experiments.lux_match

