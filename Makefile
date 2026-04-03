.PHONY: run test test-unit test-quality test-chaos test-e2e test-load lint docker-up docker-down migrate clean

run:
	python main.py

test:
	python -m pytest tests/unit/ tests/quality/ tests/chaos/test_chaos.py -v

test-unit:
	python -m pytest tests/unit/ -v

test-quality:
	python -m pytest tests/quality/ -v

test-chaos:
	python -m pytest tests/chaos/ -v

test-e2e:
	python -m pytest tests/e2e/ -v

test-e2e-sh:
	bash tests/e2e/run_e2e.sh

test-load:
	bash tests/load/run_load_tests.sh

test-chaos-sh:
	bash tests/chaos/run_chaos.sh

test-all:
	python -m pytest tests/unit/ tests/quality/ tests/chaos/test_chaos.py -v

lint:
	python -m flake8 src/ --max-line-length=120 --ignore=E501,W503

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-build:
	docker compose build

docker-logs:
	docker compose logs -f app

migrate:
	python -c "from src.models.task import init_db; init_db()"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true
