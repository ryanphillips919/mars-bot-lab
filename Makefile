.PHONY: setup test demo view setup-lux demo-lux

setup:
	bash scripts/setup_halite.sh

test:
	python3 -m unittest discover -s tests -v

demo:
	python3 -m experiments.match

view:
	python3 -m experiments.replay_server

setup-lux:
	bash scripts/setup.sh

demo-lux:
	.venv/bin/python -m experiments.lux_match

