# ==============================================================================
# AeroParse Automation Makefile
# ==============================================================================

.PHONY: train up down test lint package help

SUBSET ?= 0
VERSION ?= v1
SEED ?= 42
MODEL_VERSION ?= v1

help:
	@echo "AeroParse Build & Operations Menu:"
	@echo "  make train [SUBSET=50] [VERSION=v1]   - Run student model distillation"
	@echo "  make up [MODEL_VERSION=v1]            - Deploy cluster, storage, and service"
	@echo "  make down                             - Tear down local k3d cluster"
	@echo "  make test                             - Run unit test suite"
	@echo "  make lint                             - Run Ruff and compile checks"
	@echo "  make package                          - Package final 230101065.zip submission"

train:
	SUBSET=$(SUBSET) python training/train.py --subset $(SUBSET) --version $(VERSION) --seed $(SEED)

up:
	@MODEL_VERSION=$(MODEL_VERSION) bash scripts/deploy.sh

down:
	@bash scripts/destroy.sh

test:
	python -m unittest discover -s tests -v

lint:
	python -m compileall -q service tools training worker tests
	ruff check --select E9,F63,F7,F82 service tools training worker tests

package:
	python scripts/package_submission.py
