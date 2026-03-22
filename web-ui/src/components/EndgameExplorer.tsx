import React, { useState } from "react";
import apiService from "../services/api";
import type { TablebaseResult } from "../types/chess";

/**
 * Endgame Explorer – probe the Syzygy endgame tablebase for a position.
 *
 * Supports positions with up to 7 pieces.
 */
const EndgameExplorer: React.FC = () => {
  const [fen, setFen] = useState("8/8/4k3/8/4K3/4P3/8/8 w - - 0 1");
  const [result, setResult] = useState<TablebaseResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleProbe = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiService.probeTablebase(fen);
      setResult(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const categoryColor = (cat?: string): string => {
    if (!cat) return "#333";
    if (cat === "win" || cat === "cursed-win") return "green";
    if (cat === "loss" || cat === "blessed-loss") return "red";
    return "#666";
  };

  return (
    <section>
      <h2>Endgame Explorer (Tablebase)</h2>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <input
          type="text"
          value={fen}
          onChange={(e) => setFen(e.target.value)}
          style={{ flex: 1, fontFamily: "monospace" }}
          placeholder="Enter endgame FEN (≤7 pieces)"
        />
        <button onClick={handleProbe} disabled={loading}>
          {loading ? "Probing…" : "Probe Tablebase"}
        </button>
      </div>

      {error && <p style={{ color: "red" }}>Error: {error}</p>}

      {result && (
        <div>
          {!result.available ? (
            <p>Position not available in the tablebase (too many pieces or unknown).</p>
          ) : (
            <>
              <p>
                Result:{" "}
                <strong style={{ color: categoryColor(result.category) }}>
                  {result.category?.toUpperCase()}
                </strong>
              </p>
              {result.dtz != null && <p>DTZ (distance to zeroing): {result.dtz}</p>}
              {result.dtm != null && <p>DTM (distance to mate): {result.dtm}</p>}

              {result.moves && result.moves.length > 0 && (
                <table style={{ borderCollapse: "collapse", width: "100%", marginTop: "0.5rem" }}>
                  <thead>
                    <tr>
                      <th style={thStyle}>Move</th>
                      <th style={thStyle}>Result</th>
                      <th style={thStyle}>DTZ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.moves.map((m, i) => (
                      <tr key={i}>
                        <td style={tdStyle}>{m.san || m.uci}</td>
                        <td style={{ ...tdStyle, color: categoryColor(m.category) }}>
                          {m.category}
                        </td>
                        <td style={tdStyle}>{m.dtz ?? "–"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
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

export default EndgameExplorer;
