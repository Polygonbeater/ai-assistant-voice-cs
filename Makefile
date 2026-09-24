PYTHON ?= python3
VENV ?= .venv
PYTHON_VENV := $(VENV)/bin/python
PIP_VENV := $(VENV)/bin/pip

.PHONY: install test run clean

install:
	@if [ ! -d "$(VENV)" ]; then \
		$(PYTHON) -m venv $(VENV); \
	fi
	$(PYTHON_VENV) -m pip install --upgrade pip
	$(PIP_VENV) install -r requirements.txt
	@echo "\nHotovo. Nyní vytvořte config.json z config.example.json a spusťte make run."

run:
	@if [ ! -f config.json ]; then \
		echo "Chybí config.json. Zkopírujte config.example.json do config.json a upravte jeho hodnoty."; \
		exit 1; \
	fi
	@if [ -x "$(PYTHON_VENV)" ]; then \
		exec $(PYTHON_VENV) main.py; \
	else \
		exec $(PYTHON) main.py; \
	fi

test:
	$(PYTHON) -m pytest -q tests/test_config_and_helpers.py

clean:
	rm -rf $(VENV) .pytest_cache __pycache__
