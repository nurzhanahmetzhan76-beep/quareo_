# RetailPool AI v2.0

> Omnichannel analytics & co-buying platform for Kaspi.kz marketplace.

## Architecture

```
┌─────────────────────┐    ┌──────────────────────┐
│   FastAPI Backend    │    │  Playwright Scraper   │
│   (API container)    │    │  (Worker container)   │
│                      │    │                       │
│  • Pool CRUD API     │    │  • Kaspi parser       │
│  • Niche results     │    │  • Anti-fraud layer   │
│  • Invoice payloads  │    │  • Niche analyzer     │
│  • API Key auth      │    │  • Redis caching      │
└──────────┬───────────┘    └──────────┬────────────┘
           │                           │
     ┌─────┴───────────────────────────┴─────┐
     │          PostgreSQL + Redis            │
     └───────────────────────────────────────┘
                       │
           ┌───────────┴───────────┐
           │   Telegram Bot        │
           │   (separate worker)   │
           │   • Fetches JSON      │
           │   • Generates PDF     │
           │   • Kaspi Pay links   │
           └───────────────────────┘
```

## Quick Start

```bash
# 1. Copy environment config
cp .env.example .env

# 2. Start with Docker
docker-compose up --build

# 3. Access API docs
open http://localhost:8000/docs
```

## Local Development (without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Start PostgreSQL & Redis (must be running)
# Then run the API server
uvicorn retailpool.main:app --reload --port 8000
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/pools/create` | Open a co-buying pool |
| `POST` | `/pools/{id}/join` | Join a pool |
| `GET` | `/pools/{id}/status` | Get pool status + quorum |
| `POST` | `/scanner/scan` | Scan all target categories |
| `POST` | `/scanner/scan/{slug}` | Scan single category |
| `GET` | `/scanner/niches` | Get niche analysis results |
| `GET` | `/scanner/categories` | List target categories |

## Running Tests

```bash
pip install aiosqlite  # for test DB
pytest tests/ -v
```

## Target Categories (MVP)

- Увлажнители воздуха (`air-humidifiers`)
- Очистители воздуха (`air-purifiers`)
- Автоаксессуары (`auto-accessories`)
- Автоэлектроника (`auto-electronics`)
- Ароматизаторы для дома (`home-fragrances`)
