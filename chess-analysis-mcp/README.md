# chess-analysis-mcp

A **Model Context Protocol (MCP) server** that lets LLM agents analyse a user's Lichess games and puzzles using local Stockfish, Lichess APIs, and PostgreSQL + Redis caching.

## Features

- **Game analysis** - fetch games, detect blunders, calculate ACPL
- **Puzzle statistics** - aggregate puzzle activity, identify weak themes
- **Stockfish integration** - local engine analysis with multi-PV support
- **Lichess Cloud Eval** - fetch positional evaluations from the Lichess cloud database (cached in Redis)
- **Compare local vs cloud** - agree/disagree analysis with novelty scoring
- **Game annotation** - annotate every position (or only critical moments) with local + cloud evals
- **Opening repertoire** - win-rate analysis by ECO code
- **Training plans** - personalised suggestions based on recent performance
- **MCP resources** - expose game/puzzle/report data as URI resources
- **MCP prompts** - structured prompt templates for common workflows

## Tech stack

| Layer | Technology |
|-------|-----------|
| MCP server | `mcp` (Python SDK) |
| Chess logic | `python-chess` |
| Lichess API | `httpx` (async), `tenacity` |
| Database | PostgreSQL 15 via `asyncpg` |
| Cache | Redis 7 via `redis-py` async |
| Logging | `structlog` |
| Config | `pydantic-settings` |

## Project structure

```
chess-analysis-mcp/
  src/
    mcp_server/
      server.py          # MCP server entry point (tools, resources, prompts)
      tools/
        game_tools.py    # fetch_lichess_games, fetch_puzzle_activity
        analysis_tools.py# analyze_position, fetch_cloud_eval, compare_*, annotate_*
        pattern_tools.py # detect_tactical_patterns
        stats_tools.py   # aggregate_puzzle_statistics, performance_report, openings
        training_tools.py# generate_training_plan, suggest_puzzle_set
      resources/
        data_resources.py# game://, puzzle://, analysis:// URI handlers
      prompts/
        analysis_prompts.py # analyze-recent-games, puzzle-performance-review, etc.
    chess_engine/
      stockfish_wrapper.py  # Async Stockfish wrapper
      position_analyzer.py  # Blunder detection, ACPL, endgame classification
      pattern_detector.py   # Fork, pin, skewer, discovered attack detection
    data/
      lichess_client.py  # Lichess API client (games, puzzles, cloud eval)
      storage.py         # PostgreSQL + Redis storage layer
      models.py          # Domain dataclasses
    utils/
      config.py          # Settings (pydantic-settings)
      logging.py         # structlog configuration
      metrics.py         # Timer / timed() decorator
  tests/
    test_tools.py        # Tool handler tests (mocked API)
    test_analysis.py     # Analysis component tests
    fixtures/
      sample_games.pgn   # Sample PGN for tests
  docker/
    Dockerfile
    docker-compose.yml
  infra/
    scripts/deploy.sh    # AWS ECS Fargate deployment script
  pyproject.toml
  .env.example
```

## Quick start

### Local development

```bash
# Copy and edit environment variables
cp .env.example .env

# Install with uv
uv pip install -e ".[dev]"

# Run the server
python -m mcp_server.server
```

### Docker Compose

```bash
cd docker
docker compose up --build
```

The MCP server will be available on port `9000`.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LICHESS_TOKEN` | *(empty)* | Lichess OAuth token |
| `STOCKFISH_PATH` | `/usr/games/stockfish` | Path to Stockfish binary |
| `DATABASE_URL` | `postgresql://chess:chess@localhost:5432/chess_analysis` | PostgreSQL URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URL |
| `MCP_PORT` | `9000` | Server port |
| `LOG_LEVEL` | `INFO` | Logging level |
| `CLOUD_EVAL_CACHE_TTL` | `86400` | Cloud eval cache TTL (seconds) |

## MCP tools

| Tool | Description |
|------|-------------|
| `fetch_lichess_games` | Fetch recent games for a user |
| `fetch_puzzle_activity` | Fetch puzzle activity |
| `analyze_position` | Local Stockfish analysis |
| `find_blunders` | Detect blunders/mistakes in a PGN |
| `calculate_acpl` | Average centipawn loss |
| `detect_tactical_patterns` | Fork, pin, skewer, etc. |
| `analyze_opening_repertoire` | Win rates by ECO code |
| `classify_endgame_type` | Classify endgame type |
| `aggregate_puzzle_statistics` | Puzzle stats and themes |
| `generate_performance_report` | High-level performance summary |
| `compare_to_engine` | Compare played move to engine best |
| `generate_training_plan` | Personalised training plan |
| `suggest_puzzle_set` | Suggest puzzle themes to study |
| `fetch_cloud_eval` | Lichess Cloud Eval (cached) |
| `compare_position_vs_cloud` | Local vs cloud comparison |
| `annotate_game_with_cloud_eval` | Annotate game with evaluations |

## MCP resources

| URI | Description |
|-----|-------------|
| `game://games/{username}` | Recent games |
| `puzzle://activity/{username}` | Puzzle activity |
| `analysis://report/{username}/{period}` | Analysis report |

## MCP prompts

- `analyze-recent-games` - full game analysis workflow
- `puzzle-performance-review` - puzzle performance review
- `opening-repertoire-audit` - opening repertoire audit

## Running tests

```bash
python -m pytest tests/ -v
```

## Deployment (AWS ECS Fargate)

```bash
export AWS_REGION=us-east-1
export ECR_REPO=chess-analysis-mcp
export ECS_CLUSTER=chess-analysis
export ECS_SERVICE=chess-analysis-mcp
bash infra/scripts/deploy.sh
```
