.PHONY: init fmt tests all

all: fmt tests

init:
	poetry install

fmt:
	poetry run isort ham_tools tests
	poetry run black ham_tools tests

tests:
	poetry run mypy ham_tools tests
	poetry run pytest -m 'not integration'

integration:
	poetry run pytest
