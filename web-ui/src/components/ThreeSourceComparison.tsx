import React, { useState } from "react";
import apiService from "../services/api";
import type { ThreeSourceComparison as ComparisonResult } from "../types/chess";

/**
 * Three-Source Comparison – compare Stockfish, Lichess Cloud, and ChessDB
 * evaluations side by side.
 */
const ThreeSourceComparison: React.FC = () => {
  const [fen, setFen] = useState(
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
  );
  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCompare = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiService.compareThreeSources(fen);
      setResult(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const formatCp = (cp: number | null): string => {
    if (cp == null) return "–";
    return cp > 0 ? `+${cp}` : `${cp}`;
  };

  return (
    <section>
      <h2>Three-Source Comparison</h2>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <input
          type="text"
          value={fen}
          onChange={(e) => setFen(e.target.value)}
          style={{ flex: 1, fontFamily: "monospace" }}
          placeholder="Enter FEN"
        />
        <button onClick={handleCompare} disabled={loading}>
          {loading ? "Comparing…" : "Compare"}
        </button>
      </div>

      {error && <p style={{ color: "red" }}>Error: {error}</p>}

      {result && (
        <div>
          <p>
            Consensus: <strong>{result.consensus}</strong>
          </p>
          <table style={{ borderCollapse: "collapse", width: "100%" }}>
            <thead>
              <tr>
                <th style={thStyle}>Source</th>
                <th style={thStyle}>Best Move</th>
                <th style={thStyle}>Score (cp)</th>
                <th style={thStyle}>Available</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={tdStyle}>Stockfish (local)</td>
                <td style={tdStyle}>{result.stockfish.best_move || "–"}</td>
                <td style={tdStyle}>{formatCp(result.stockfish.cp)}</td>
                <td style={tdStyle}>✅</td>
              </tr>
              <tr>
                <td style={tdStyle}>Lichess Cloud</td>
                <td style={tdStyle}>{result.lichess_cloud.best_move || "–"}</td>
                <td style={tdStyle}>{formatCp(result.lichess_cloud.cp)}</td>
                <td style={tdStyle}>
                  {result.lichess_cloud.available ? "✅" : "❌"}
                </td>
              </tr>
              <tr>
                <td style={tdStyle}>ChessDB</td>
                <td style={tdStyle}>{result.chessdb.best_move || "–"}</td>
                <td style={tdStyle}>
                  {result.chessdb.score != null ? formatCp(result.chessdb.score) : "–"}
                </td>
                <td style={tdStyle}>
                  {result.chessdb.available ? "✅" : "❌"}
                </td>
              </tr>
            </tbody>
          </table>
          <p style={{ marginTop: "0.5rem" }}>
            Unique best moves:{" "}
            <code>{result.unique_best_moves.join(", ") || "none"}</code>
          </p>
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

export default ThreeSourceComparison;
