/**
 * Type definitions shared across the Chess Trainer AI web UI.
 */

/** Evaluation from a single source. */
export interface Evaluation {
  cp?: number | null;
  mate?: number | null;
  depth?: number;
  pv?: string;
}

/** A single scored move from ChessDB. */
export interface ChessDBMove {
  uci: string;
  san: string;
  score: number | null;
  rank: number | null;
  note: string;
  winrate: number | null;
}

/** Response from the explore_position MCP tool. */
export interface ExplorePositionResult {
  fen: string;
  status: string;
  moves: ChessDBMove[];
}

/** Response from the compare_three_sources MCP tool. */
export interface ThreeSourceComparison {
  fen: string;
  stockfish: {
    best_move: string;
    cp: number | null;
    eval: Record<string, unknown>;
  };
  lichess_cloud: {
    best_move: string;
    cp: number | null;
    available: boolean;
    eval: Record<string, unknown> | null;
  };
  chessdb: {
    best_move: string;
    score: number | null;
    available: boolean;
    eval: Record<string, unknown> | null;
  };
  consensus: string;
  sources_agree_on_move: boolean | null;
  unique_best_moves: string[];
}

/** Tablebase probe result. */
export interface TablebaseResult {
  fen: string;
  available: boolean;
  category?: string;
  dtz?: number | null;
  dtm?: number | null;
  moves?: Array<{
    uci: string;
    san: string;
    category: string;
    dtz: number | null;
  }>;
}

/** A generated puzzle. */
export interface GeneratedPuzzle {
  fen: string;
  color_to_move: string;
  played_move: string;
  best_move: string;
  solution_uci: string[];
  cp_loss: number;
  themes: string[];
  difficulty: string;
  source_game_id?: string;
}

/** Opening move data. */
export interface OpeningMove {
  uci: string;
  san: string;
  score: number | null;
  rank: number | null;
  winrate: number | null;
}
