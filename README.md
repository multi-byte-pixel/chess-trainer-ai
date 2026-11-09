# chess-trainer-ai

A chess training toolkit built around a Model Context Protocol (MCP) server. An LLM agent can use it to analyse a Lichess player's games and puzzles with local Stockfish, Lichess cloud evaluations, ChessDB crowd-sourced scores, and Syzygy endgame tablebases.

## Status

| Component | State |
|---|---|
| MCP server (`chess-analysis-mcp/`) | Runs over stdio. 44 unit tests pass offline against mocked APIs (`pytest`). |
| ChessDB, tablebase, three-source comparison, puzzle and opening tools | Implemented and unit-tested against mocked HTTP responses. Not yet checked against live services in CI. |
| Web UI (`web-ui/`) | Early React prototype. It calls an HTTP API on port 9000, but the server currently speaks stdio only, so an HTTP bridge is still needed. |
| Docker Compose and ECS deploy script | Provided for local experiments; not exercised in CI. |

## Architecture

```
React web UI (prototype)  --HTTP (planned bridge)-->  MCP server (Python, stdio)
                                                        |
        +-------------+-------------+------------+------+---------------+
        | Stockfish   | Lichess API | ChessDB    | Lichess tablebase    |
        | (local)     | + cloud eval| chessdb.cn | tablebase.lichess.ovh|
        +-------------+-------------+------------+----------------------+
                         PostgreSQL (storage) + Redis (cache)
```

## Features

- Game analysis: fetch games, detect blunders, calculate average centipawn loss
- Puzzle statistics: aggregate puzzle activity and identify weak themes
- Local Stockfish analysis with multi-PV, compared against Lichess cloud evaluations
- Three-source comparison: Stockfish vs. Lichess cloud vs. ChessDB, including move-ranking agreement
- Game annotation with all three evaluation sources
- Opening explorer and repertoire comparison against ChessDB
- Puzzle generation from a PGN or a user's recent games
- Endgame tablebase probing (up to 7 pieces) combined with Stockfish analysis
- Personalised training plans based on recent performance

## MCP tools

| Tool | Description |
|------|-------------|
| `explore_position` | Query ChessDB for all scored candidate moves |
| `explore_best_move` | Get the single best move from ChessDB |
| `explore_principal_variation` | Get the principal variation from ChessDB |
| `queue_position_analysis` | Request server-side analysis on ChessDB |
| `compare_three_sources` | Compare Stockfish, Lichess cloud, and ChessDB evaluations |
| `compare_move_rankings` | Compare how each source ranks the top N moves |
| `opening_explorer` | Browse opening moves via ChessDB |
| `opening_line_analysis` | Analyse a specific opening line with ChessDB |
| `opening_repertoire_vs_chessdb` | Compare a user's repertoire against ChessDB |
| `annotate_game_three_sources` | Annotate a game with all three evaluation sources |
| `generate_puzzles_from_game` | Generate training puzzles from a PGN game |
| `generate_puzzles_from_user_games` | Generate puzzles from a user's recent games |
| `probe_tablebase` | Probe the Syzygy endgame tablebase |
| `probe_tablebase_mainline` | Get the optimal play sequence from the tablebase |
| `endgame_analysis` | Combined Stockfish and tablebase endgame analysis |

The original Lichess and Stockfish tools are documented in [chess-analysis-mcp/README.md](chess-analysis-mcp/README.md).

## Tech stack

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

## Quick start

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

### Frontend (React web UI prototype)

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

## ChessDB network allowlisting

ChessDB is hosted at `chessdb.cn`. If your environment blocks outbound traffic, allowlist:

- **Domain:** `chessdb.cn`
- **Port:** `443` (HTTPS)

### AWS configuration

1. **Security Group** - add outbound rule for HTTPS (TCP 443)
2. **NACL** - ensure subnet allows outbound 443 and ephemeral return (1024-65535)
3. **NAT Gateway** - if ECS tasks run in a private subnet, route through NAT Gateway
4. **Route Tables** - ensure internet gateway route exists for public subnets

### GitHub Actions CI

```yaml
- name: Verify ChessDB connectivity
  run: curl -sf https://chessdb.cn/cdb_api_health || echo "ChessDB unreachable - skipping integration tests"
```

## Environment variables

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
| `REACT_APP_API_URL` | `http://localhost:9000` | Web UI API endpoint |

## Project structure

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
│   │   │       ├── explorer_tools.py
│   │   │       ├── comparison_tools.py
│   │   │       ├── opening_tools.py
│   │   │       ├── annotation_tools.py
│   │   │       ├── puzzle_tools.py
│   │   │       └── endgame_tools.py
│   │   ├── chess_engine/
│   │   │   ├── stockfish_wrapper.py
│   │   │   ├── position_analyzer.py
│   │   │   └── pattern_detector.py
│   │   ├── data/
│   │   │   ├── lichess_client.py
│   │   │   ├── chessdb_client.py
│   │   │   ├── tablebase_client.py
│   │   │   ├── storage.py
│   │   │   └── models.py
│   │   └── utils/
│   │       ├── config.py
│   │       ├── logging.py
│   │       └── metrics.py
│   ├── tests/
│   │   ├── test_tools.py
│   │   ├── test_analysis.py
│   │   ├── test_chessdb_client.py
│   │   ├── test_tablebase_client.py
│   │   └── test_new_features.py
│   ├── docker/
│   │   ├── Dockerfile
│   │   └── docker-compose.yml
│   ├── pyproject.toml
│   └── .env.example
├── web-ui/
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
└── README.md
```

## Running tests

```bash
cd chess-analysis-mcp
python -m pytest tests/ -v
```

## How this was built

Developed with AI coding assistance. The commit and pull-request history retain that attribution.

## Next steps

- HTTP bridge so the web UI can call the MCP tools
- Live-service smoke tests behind an opt-in flag
- Deployment on AWS (ECS Fargate, RDS, ElastiCache, S3 and CloudFront); see `chess-analysis-mcp/infra/scripts/deploy.sh`
