.PHONY: setup test demo

setup:
	bash scripts/setup.sh

test:
	python3 -m unittest discover -s tests -v

demo:
	.venv/bin/python -m experiments.match

