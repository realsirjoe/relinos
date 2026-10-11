tests_long:
	python -m unittest discover -v relinos.tests "test_l_*.py"
tests_short:
	python -m unittest discover -v relinos.tests "test_s_*.py"
typecheck:
	mypy .
