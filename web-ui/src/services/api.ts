/**
 * API service for communicating with the chess-analysis-mcp server.
 *
 * In production this will call the MCP server's HTTP API (or a thin
 * middleware layer).  During development, the base URL defaults to
 * ``http://localhost:9000`` and can be overridden via the
 * ``REACT_APP_API_URL`` environment variable.
 */
import axios, { AxiosInstance } from "axios";
import type {
  ExplorePositionResult,
  ThreeSourceComparison,
  TablebaseResult,
  GeneratedPuzzle,
} from "../types/chess";

const API_BASE = process.env.REACT_APP_API_URL ?? "http://localhost:9000";

class ChessApiService {
  private client: AxiosInstance;

  constructor(baseURL: string = API_BASE) {
    this.client = axios.create({
      baseURL,
      timeout: 30_000,
      headers: { "Content-Type": "application/json" },
    });
  }

  // -----------------------------------------------------------------
  // ChessDB Position Explorer
  // -----------------------------------------------------------------

  async explorePosition(fen: string): Promise<ExplorePositionResult> {
    const { data } = await this.client.post<ExplorePositionResult>(
      "/tools/explore_position",
      { fen }
    );
    return data;
  }

  async exploreBestMove(fen: string): Promise<{ move: string; score: number | null }> {
    const { data } = await this.client.post("/tools/explore_best_move", { fen });
    return data;
  }

  // -----------------------------------------------------------------
  // Three-source comparison
  // -----------------------------------------------------------------

  async compareThreeSources(fen: string): Promise<ThreeSourceComparison> {
    const { data } = await this.client.post<ThreeSourceComparison>(
      "/tools/compare_three_sources",
      { fen }
    );
    return data;
  }

  // -----------------------------------------------------------------
  // Endgame tablebase
  // -----------------------------------------------------------------

  async probeTablebase(fen: string): Promise<TablebaseResult> {
    const { data } = await this.client.post<TablebaseResult>(
      "/tools/probe_tablebase",
      { fen }
    );
    return data;
  }

  // -----------------------------------------------------------------
  // Puzzle generation
  // -----------------------------------------------------------------

  async generatePuzzles(
    pgn: string,
    options?: { depth?: number; min_cp_loss?: number; max_puzzles?: number }
  ): Promise<{ puzzles: GeneratedPuzzle[] }> {
    const { data } = await this.client.post("/tools/generate_puzzles_from_game", {
      pgn,
      ...options,
    });
    return data;
  }

  // -----------------------------------------------------------------
  // Opening explorer
  // -----------------------------------------------------------------

  async openingExplorer(fen?: string): Promise<ExplorePositionResult> {
    const { data } = await this.client.post<ExplorePositionResult>(
      "/tools/opening_explorer",
      { fen }
    );
    return data;
  }
}

const apiService = new ChessApiService();
export default apiService;
