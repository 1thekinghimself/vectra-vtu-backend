# Vectra VTU Backend

Flask-based backend providing VTU endpoints (airtime/data/webhooks) used by the Vectra service.

## Features

- REST endpoints for airtime and data purchases
- Webhook receiver for downstream providers
- Simple SQLite/Postgres-backed persistence (see `database.py`)

## Requirements

- Python 3.10+ (use a virtual environment)
- See `requirements.txt` for pinned dependencies

## Quickstart (local)

1. Create and activate a virtual environment:

	python -m venv .venv
	source .venv/bin/activate

2. Install dependencies:

	pip install -r requirements.txt

3. Copy environment example and set values:

	cp env.example .env
	# Edit .env and fill in required keys (database URL, API keys, etc.)

4. Run the app:

	# Option A: using Flask CLI
	export FLASK_APP=app.py
	flask run --host=0.0.0.0 --port=5000

	# Option B: run directly
	python app.py

5. Run tests:

	pytest -q

## Deployment

This project includes a `render. yaml` deployment descriptor for Render.com. Ensure environment variables are set in the target platform.

## Project layout

- `app.py` — application entrypoint
- `config.py` — configuration
- `database.py` — DB helpers
- `models.py` — data models
- `services/` — service modules and route handlers
- `requirements.txt` — Python dependencies

## Contributing

Open an issue or submit a PR. Keep changes small and include tests for new behavior.

## License

See repository settings or ask the maintainers for license information.

