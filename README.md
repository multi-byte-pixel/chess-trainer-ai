# chess-trainer-ai

A comprehensive chess training platform powered by AI. Combines a **Model Context Protocol (MCP) server** with local Stockfish analysis, Lichess APIs, **ChessDB** crowd-sourced evaluations, **Syzygy endgame tablebases**, and a **React web UI**.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Web UI                             │
│  Position Explorer · Three-Source Comparison · Opening Explorer  │
│  Puzzle Trainer · Endgame Explorer                              │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP / JSON
┌──────────────────────────────▼──────────────────────────────────┐
│                     MCP Server (Python)                          │
│  Tools · Resources · Prompts · Dispatch                         │
├─────────┬───────────┬──────────────┬───────────┬───────────────┤
│Stockfish│ Lichess   │ ChessDB      │ Tablebase │ PostgreSQL    │
│ (local) │ API       │ (chessdb.cn) │ (Lichess) │ + Redis       │
└─────────┴───────────┴──────────────┴───────────┴───────────────┘
```

## Features

### Existing (Lichess + Stockfish)
- **Game analysis** – fetch games, detect blunders, calculate ACPL
- **Puzzle statistics** – aggregate puzzle activity, identify weak themes
- **Stockfish integration** – local engine analysis with multi-PV support
- **Lichess Cloud Eval** – fetch positional evaluations (cached in Redis)
- **Compare local vs cloud** – agree/disagree analysis with novelty scoring
- **Game annotation** – annotate positions with local + cloud evals
- **Opening repertoire** – win-rate analysis by ECO code
- **Training plans** – personalised suggestions based on recent performance

### New Features (this branch)

| Feature | Branch | Status |
|---------|--------|--------|
| **ChessDB Client** | `feature/chessdb-client` | ✅ Scaffolded |
| **Position Explorer** | `feature/position-explorer` | ✅ Scaffolded |
| **Three-Source Comparison** | `feature/three-source-comparison` | ✅ Scaffolded |
| **Opening Prep** | `feature/opening-prep` | ✅ Scaffolded |
| **Game Annotation (ChessDB)** | `feature/game-annotation-chessdb` | ✅ Scaffolded |
| **Puzzle Generation** | `feature/puzzle-generation` | ✅ Scaffolded |
| **Endgame Tablebase Bridge** | `feature/endgame-tablebase-bridge` | ✅ Scaffolded |
| **Web UI (React)** | `feature/web-ui-chessdb` | ✅ Scaffolded |

## New MCP Tools

| Tool | Description |
|------|-------------|
| `explore_position` | Query ChessDB for all scored candidate moves |
| `explore_best_move` | Get the single best move from ChessDB |
| `explore_principal_variation` | Get the PV from ChessDB |
| `queue_position_analysis` | Request server-side analysis on ChessDB |
| `compare_three_sources` | Compare Stockfish, Lichess Cloud, and ChessDB evals |
| `compare_move_rankings` | Compare how each source ranks the top N moves |
| `opening_explorer` | Browse opening moves via ChessDB |
| `opening_line_analysis` | Analyse a specific opening line with ChessDB |
| `opening_repertoire_vs_chessdb` | Compare user's repertoire against ChessDB |
| `annotate_game_three_sources` | Annotate a game with all three eval sources |
| `generate_puzzles_from_game` | Generate training puzzles from a PGN game |
| `generate_puzzles_from_user_games` | Generate puzzles from a user's recent games |
| `probe_tablebase` | Probe Syzygy endgame tablebase (≤ 7 pieces) |
| `probe_tablebase_mainline` | Get optimal play sequence from tablebase |
| `endgame_analysis` | Combined Stockfish + tablebase endgame analysis |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| MCP server | Python (`mcp` SDK) |
| Chess logic | `python-chess` |
| Lichess API | `httpx` (async), `tenacity` |
| ChessDB API | `httpx` (async), `tenacity` |
| Tablebase API | `httpx` (async), `tenacity` |
| Database | PostgreSQL 15 via `asyncpg` |
| Cache | Redis 7 via `redis-py` async |
| Frontend | React 18, TypeScript, react-router-dom |
| Logging | `structlog` |
| Config | `pydantic-settings` |

## Quick Start

### Backend (MCP Server)

```bash
cd chess-analysis-mcp
cp .env.example .env
# Edit .env with your Lichess token and other settings

# Install with pip
pip install -e ".[dev]"

# Run the server
python -m mcp_server.server
```

### Frontend (React Web UI)

```bash
cd web-ui
npm install
npm start
# Opens http://localhost:3000
```

### Docker Compose (full stack)

```bash
cd chess-analysis-mcp/docker
docker compose up --build
```

## ChessDB Network Allowlisting

ChessDB is hosted at `chessdb.cn`. If your environment blocks outbound traffic, allowlist:

- **Domain:** `chessdb.cn`
- **Port:** `443` (HTTPS)

### AWS-specific Configuration

1. **Security Group** – add outbound rule for HTTPS (TCP 443)
2. **NACL** – ensure subnet allows outbound 443 and ephemeral return (1024-65535)
3. **NAT Gateway** – if ECS tasks run in a private subnet, route through NAT Gateway
4. **Route Tables** – ensure internet gateway route exists for public subnets

### GitHub Actions CI

```yaml
- name: Verify ChessDB connectivity
  run: curl -sf https://chessdb.cn/cdb_api_health || echo "ChessDB unreachable – skipping integration tests"
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LICHESS_TOKEN` | *(empty)* | Lichess OAuth token |
| `STOCKFISH_PATH` | `/usr/games/stockfish` | Path to Stockfish binary |
| `DATABASE_URL` | `postgresql://chess:chess@localhost:5432/chess_analysis` | PostgreSQL URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URL |
| `MCP_PORT` | `9000` | MCP server port |
| `LOG_LEVEL` | `INFO` | Logging level |
| `CHESSDB_API_URL` | `https://chessdb.cn` | ChessDB API base URL |
| `CHESSDB_REQUEST_TIMEOUT` | `30` | ChessDB request timeout (seconds) |
| `CHESSDB_CACHE_TTL` | `86400` | ChessDB cache TTL (seconds) |
| `TABLEBASE_API_URL` | `https://tablebase.lichess.ovh` | Tablebase API base URL |
| `TABLEBASE_REQUEST_TIMEOUT` | `15` | Tablebase request timeout (seconds) |
| `TABLEBASE_CACHE_TTL` | `604800` | Tablebase cache TTL (seconds, 1 week) |
| `REACT_APP_API_URL` | `http://localhost:9000` | Web UI → MCP API endpoint |

## Project Structure

```
chess-trainer-ai/
├── chess-analysis-mcp/           # Python MCP server
│   ├── src/
│   │   ├── mcp_server/
│   │   │   ├── server.py         # MCP server entry point (all tool dispatch)
│   │   │   └── tools/
│   │   │       ├── game_tools.py
│   │   │       ├── analysis_tools.py
│   │   │       ├── pattern_tools.py
│   │   │       ├── stats_tools.py
│   │   │       ├── training_tools.py
│   │   │       ├── explorer_tools.py      # NEW – ChessDB position explorer
│   │   │       ├── comparison_tools.py    # NEW – three-source comparison
│   │   │       ├── opening_tools.py       # NEW – opening preparation
│   │   │       ├── annotation_tools.py    # NEW – three-source annotation
│   │   │       ├── puzzle_tools.py        # NEW – puzzle generation
│   │   │       └── endgame_tools.py       # NEW – tablebase bridge
│   │   ├── chess_engine/
│   │   │   ├── stockfish_wrapper.py
│   │   │   ├── position_analyzer.py
│   │   │   └── pattern_detector.py
│   │   ├── data/
│   │   │   ├── lichess_client.py
│   │   │   ├── chessdb_client.py          # NEW – ChessDB API client
│   │   │   ├── tablebase_client.py        # NEW – Tablebase API client
│   │   │   ├── storage.py
│   │   │   └── models.py                  # Updated with new models
│   │   └── utils/
│   │       ├── config.py                  # Updated with new settings
│   │       ├── logging.py
│   │       └── metrics.py
│   ├── tests/
│   │   ├── test_tools.py
│   │   ├── test_analysis.py
│   │   ├── test_chessdb_client.py         # NEW
│   │   ├── test_tablebase_client.py       # NEW
│   │   └── test_new_features.py           # NEW
│   ├── docker/
│   │   ├── Dockerfile
│   │   └── docker-compose.yml             # Updated with new env vars
│   ├── pyproject.toml
│   └── .env.example                       # Updated with new variables
├── web-ui/                                # NEW – React frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── PositionExplorer.tsx
│   │   │   ├── ThreeSourceComparison.tsx
│   │   │   ├── OpeningExplorer.tsx
│   │   │   ├── PuzzleTrainer.tsx
│   │   │   └── EndgameExplorer.tsx
│   │   ├── services/api.ts
│   │   ├── types/chess.ts
│   │   ├── App.tsx
│   │   └── index.tsx
│   ├── package.json
│   └── tsconfig.json
└── README.md                              # This file
```

## Running Tests

```bash
cd chess-analysis-mcp
python -m pytest tests/ -v
```

## Future Work (AWS Migration)

The Docker Compose setup is designed for local development. For production:

- **ECS Fargate** – deploy MCP server as a containerised service
- **ElastiCache** – replace local Redis with AWS ElastiCache (Redis)
- **RDS PostgreSQL** – replace local PostgreSQL with RDS
- **CloudFront + S3** – host React web UI as a static site
- **API Gateway** – front the MCP server with API Gateway for auth/rate limiting

See `chess-analysis-mcp/infra/scripts/deploy.sh` for the existing ECS deployment script.