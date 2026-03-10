# Chess Trainer AI – Web UI

React frontend for the Chess Trainer AI MCP server.

## Features

| Page | Description |
|------|-------------|
| **Position Explorer** | Query ChessDB for scored candidate moves at any position |
| **Three-Source Comparison** | Compare Stockfish, Lichess Cloud, and ChessDB evaluations side-by-side |
| **Opening Explorer** | Browse opening lines with ChessDB scores and win rates |
| **Puzzle Trainer** | Generate training puzzles from your games (paste PGN) |
| **Endgame Explorer** | Probe Syzygy endgame tablebases for positions with ≤ 7 pieces |

## Tech Stack

- **React 18** with TypeScript
- **react-router-dom** for client-side routing
- **axios** for API calls
- **chess.js** + **chessboardjsx** for chess logic and board display (TODO: integrate)

## Quick Start

```bash
cd web-ui
npm install
npm start
```

The development server runs on `http://localhost:3000` and proxies API
calls to the MCP server at `http://localhost:9000` (configurable via
`REACT_APP_API_URL`).

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REACT_APP_API_URL` | `http://localhost:9000` | MCP server API endpoint |

## Project Structure

```
web-ui/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── PositionExplorer.tsx
│   │   ├── ThreeSourceComparison.tsx
│   │   ├── OpeningExplorer.tsx
│   │   ├── PuzzleTrainer.tsx
│   │   └── EndgameExplorer.tsx
│   ├── services/
│   │   └── api.ts              # API client for MCP server
│   ├── types/
│   │   └── chess.ts            # TypeScript type definitions
│   ├── hooks/                  # Custom React hooks (TODO)
│   ├── App.tsx                 # Main app with routing
│   └── index.tsx               # Entry point
├── package.json
└── tsconfig.json
```

## TODO

- [ ] Integrate `chessboardjsx` for interactive board display
- [ ] Add user authentication (Lichess OAuth)
- [ ] Add game import from Lichess API
- [ ] Add puzzle solving UI with move validation
- [ ] Add performance dashboard / charts
- [ ] Add responsive design / mobile support
- [ ] Add unit tests for components
