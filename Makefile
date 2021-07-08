# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
# 
# SPDX-License-Identifier: GPL-3.0-or-later

VENV?=build/.venv

.PHONY: default install venv clean

default: venv
	. $(VENV)/bin/activate; \
	pytest -vv tests/

install:
	pip install .

venv:
	mkdir -p build
	[ -d $(VENV) ] || virtualenv $(VENV)  # Create virtual environment first run only!
	. $(VENV)/bin/activate; \
	pip install -r requirements.txt; \
	python setup.py install

clean:
	rm -fr build
	rm -fr dist
