.PHONY: help install run test check train-weapon clean

PYTHON := ./venv/bin/python
STREAMLIT := ./venv/bin/streamlit

help:
	@echo "Available commands:"
	@echo "  make install  - create venv and install project dependencies"
	@echo "  make run      - start the Streamlit app"
	@echo "  make test     - run the test suite"
	@echo "  make check    - run compile + test validation"
	@echo "  make train-weapon DATA=path/to/dataset.yaml - train the dedicated danger detector"
	@echo "  make clean    - remove generated cache files"

install:
	python3 -m venv venv
	./venv/bin/python -m pip install --upgrade pip
	./venv/bin/python -m pip install -r requirements.txt

run:
	$(STREAMLIT) run app.py

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

check:
	$(PYTHON) -m py_compile app.py src/*.py tests/test_security_and_weapon_logic.py
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

train-weapon:
	@test -n "$(DATA)" || (echo "Usage: make train-weapon DATA=path/to/dataset.yaml"; exit 1)
	$(PYTHON) scripts/train_weapon_model.py --data "$(DATA)"

clean:
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -type d -name '.pytest_cache' -prune -exec rm -rf {} +
