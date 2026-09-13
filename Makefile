.PHONY: install test lint fmt demo queue collatz examples all

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest

lint:
	ruff check .
	ruff format --check .

fmt:
	ruff format .
	ruff check . --fix

demo:
	python -m app.main --deadline-note "Device review starts in 43 minutes (17:00)." \
		verify examples/maya_case/inputs

queue:
	python -m app.main queue examples/review_queue/queue.json

collatz:
	python -m app.main benchmark collatz --limit 1000000

examples:
	python scripts/build_examples.py

all: lint test
