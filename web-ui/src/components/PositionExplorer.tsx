import React, { useState } from "react";
import apiService from "../services/api";
import type { ExplorePositionResult, ChessDBMove } from "../types/chess";

/**
 * Position Explorer – query ChessDB for candidate moves at any position.
 *
 * TODO: integrate a chessboard component for visual position entry.
 */
const PositionExplorer: React.FC = () => {
  const [fen, setFen] = useState(
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
  );
  const [result, setResult] = useState<ExplorePositionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExplore = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiService.explorePosition(fen);
      setResult(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section>
      <h2>Position Explorer (ChessDB)</h2>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <input
          type="text"
          value={fen}
          onChange={(e) => setFen(e.target.value)}
          style={{ flex: 1, fontFamily: "monospace" }}
          placeholder="Enter FEN"
        />
        <button onClick={handleExplore} disabled={loading}>
          {loading ? "Loading…" : "Explore"}
        </button>
      </div>

      {error && <p style={{ color: "red" }}>Error: {error}</p>}

      {result && (
        <div>
          <p>
            Status: <strong>{result.status}</strong> | Moves found:{" "}
            <strong>{result.moves.length}</strong>
          </p>
          <table style={{ borderCollapse: "collapse", width: "100%" }}>
            <thead>
              <tr>
                <th style={thStyle}>Rank</th>
                <th style={thStyle}>Move (SAN)</th>
                <th style={thStyle}>UCI</th>
                <th style={thStyle}>Score</th>
                <th style={thStyle}>Win Rate</th>
                <th style={thStyle}>Note</th>
              </tr>
            </thead>
            <tbody>
              {result.moves.map((m: ChessDBMove, i: number) => (
                <tr key={i}>
                  <td style={tdStyle}>{m.rank ?? i + 1}</td>
                  <td style={tdStyle}>{m.san || m.uci}</td>
                  <td style={tdStyle}>{m.uci}</td>
                  <td style={tdStyle}>{m.score ?? "–"}</td>
                  <td style={tdStyle}>
                    {m.winrate != null ? `${(m.winrate * 100).toFixed(1)}%` : "–"}
                  </td>
                  <td style={tdStyle}>{m.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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

export default PositionExplorer;
