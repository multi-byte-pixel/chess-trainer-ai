# chess-trainer-ai

An AI-powered chess training assistant built on a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server. It lets LLM agents analyse a user's Lichess games and puzzles using local Stockfish, Lichess APIs, and PostgreSQL + Redis caching.

See [`chess-analysis-mcp/README.md`](chess-analysis-mcp/README.md) for full documentation, quick-start instructions, and the list of available MCP tools, resources, and prompts.

## Planned Features

The features below are inspired by [ChessDB Explorer](https://lichess.org/@/hollowleaf/blog/new-tool-chessdb-explorer/kanf84Uo), a tool that surfaces [ChessDB](https://www.chessdb.cn/) — a massive crowd-sourced opening/middlegame database scored by Stockfish — as a practical training aid.

| Feature | Summary |
|---------|---------|
| **ChessDB API integration** | New `ChessDBClient` with tools to fetch all known moves, best move, and principal variation from ChessDB for any position |
| **Position explorer** | Recursive position-tree exploration driven by ChessDB move lists, exposed as an MCP resource |
| **Three-source comparison** | Unified tool comparing local Stockfish, Lichess Cloud Eval, and ChessDB evaluations with a combined novelty score |
| **Opening preparation** | Build scored opening trees, find repertoire novelties, and analyse opponent repertoires using ChessDB data |
| **Game annotation with ChessDB** | Annotate games with ChessDB recommendations and generate a deviation report ranking every move by centipawn cost |
| **Puzzle generation** | Extract tactical puzzles from positions where ChessDB shows a large gap between the best and second-best move |
| **Endgame tablebase bridge** | Route positions with ≤ 7 pieces to ChessDB's Syzygy tablebase data for definitive win/draw/loss verdicts |
| **Web UI** | Interactive chess board showing real-time scored move arrows from ChessDB alongside a multi-source evaluation bar |

For detailed descriptions of each planned feature see the [chess-analysis-mcp README](chess-analysis-mcp/README.md#planned-features).
