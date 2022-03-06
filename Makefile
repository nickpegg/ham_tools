all: fmt tests

init:
	poetry install

fmt:
	poetry run black ham_tools

tests:
	poetry run mypy ham_tools
	poetry run pytest
