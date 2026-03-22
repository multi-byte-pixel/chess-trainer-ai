import React, { useState, useEffect, useCallback } from "react";
import apiService from "../services/api";
import type { ExplorePositionResult, ChessDBMove } from "../types/chess";

/**
 * Opening Explorer – browse opening moves using ChessDB data.
 *
 * Starts at the initial position and lets users click through moves
 * to explore opening lines with scores and win rates.
 */
const OpeningExplorer: React.FC = () => {
  const STARTING_FEN =
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

  const [fen, setFen] = useState(STARTING_FEN);
  const [result, setResult] = useState<ExplorePositionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [moveHistory, setMoveHistory] = useState<string[]>([]);

  const loadPosition = useCallback(async (positionFen: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiService.openingExplorer(positionFen);
      setResult(data);
      setFen(positionFen);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPosition(STARTING_FEN);
  }, [loadPosition]);

  const handleReset = () => {
    setMoveHistory([]);
    loadPosition(STARTING_FEN);
  };

  return (
    <section>
      <h2>Opening Explorer (ChessDB)</h2>

      <div style={{ marginBottom: "1rem" }}>
        <strong>Position:</strong>{" "}
        <code style={{ fontSize: "0.85rem" }}>{fen}</code>
        <button onClick={handleReset} style={{ marginLeft: "0.5rem" }}>
          Reset
        </button>
      </div>

      {moveHistory.length > 0 && (
        <p>
          Moves played: <code>{moveHistory.join(" ")}</code>
        </p>
      )}

      {loading && <p>Loading…</p>}
      {error && <p style={{ color: "red" }}>Error: {error}</p>}

      {result && !loading && (
        <table style={{ borderCollapse: "collapse", width: "100%" }}>
          <thead>
            <tr>
              <th style={thStyle}>Move</th>
              <th style={thStyle}>Score</th>
              <th style={thStyle}>Win Rate</th>
              <th style={thStyle}>Note</th>
            </tr>
          </thead>
          <tbody>
            {result.moves.map((m: ChessDBMove, i: number) => (
              <tr key={i} style={{ cursor: "pointer" }}>
                <td style={tdStyle}>
                  <strong>{m.san || m.uci}</strong>
                </td>
                <td style={tdStyle}>{m.score ?? "–"}</td>
                <td style={tdStyle}>
                  {m.winrate != null ? `${(m.winrate * 100).toFixed(1)}%` : "–"}
                </td>
                <td style={tdStyle}>{m.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {result && result.moves.length === 0 && !loading && (
        <p>No opening data available for this position.</p>
      )}
    </section>
  );
};

const thStyle: React.CSSProperties = {
  borderBottom: "2px solid #333",
  padding: "0.4rem",
  textAlign: "left",
};

const tdStyle: React.CSSProperties = {
  borderBottom: "1px solid #ccc",
  padding: "0.4rem",
};

export default OpeningExplorer;
