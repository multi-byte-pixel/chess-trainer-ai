import React, { useState } from "react";
import apiService from "../services/api";
import type { GeneratedPuzzle } from "../types/chess";

/**
 * Puzzle Trainer – generate and solve puzzles from games.
 *
 * Users paste a PGN and the backend generates puzzles from the
 * game's mistakes. Each puzzle shows the position FEN, themes,
 * difficulty, and the solution line.
 *
 * TODO: integrate interactive chessboard for puzzle solving.
 */
const PuzzleTrainer: React.FC = () => {
  const [pgn, setPgn] = useState("");
  const [puzzles, setPuzzles] = useState<GeneratedPuzzle[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revealedSolutions, setRevealedSolutions] = useState<Set<number>>(
    new Set()
  );

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiService.generatePuzzles(pgn);
      setPuzzles(data.puzzles);
      setRevealedSolutions(new Set());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const toggleSolution = (index: number) => {
    setRevealedSolutions((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  return (
    <section>
      <h2>Puzzle Trainer</h2>

      <div style={{ marginBottom: "1rem" }}>
        <textarea
          value={pgn}
          onChange={(e) => setPgn(e.target.value)}
          placeholder="Paste a PGN game here…"
          rows={6}
          style={{ width: "100%", fontFamily: "monospace" }}
        />
        <button onClick={handleGenerate} disabled={loading || !pgn.trim()}>
          {loading ? "Generating…" : "Generate Puzzles"}
        </button>
      </div>

      {error && <p style={{ color: "red" }}>Error: {error}</p>}

      {puzzles.length > 0 && (
        <div>
          <h3>Generated Puzzles ({puzzles.length})</h3>
          {puzzles.map((p, i) => (
            <div
              key={i}
              style={{
                border: "1px solid #ccc",
                borderRadius: "4px",
                padding: "0.75rem",
                marginBottom: "0.5rem",
              }}
            >
              <p>
                <strong>Puzzle {i + 1}</strong> – {p.color_to_move} to move |
                Difficulty: <em>{p.difficulty}</em> | CP loss: {p.cp_loss}
              </p>
              <p>
                Themes: <code>{p.themes.join(", ")}</code>
              </p>
              <p>
                FEN: <code style={{ fontSize: "0.8rem" }}>{p.fen}</code>
              </p>
              <button onClick={() => toggleSolution(i)}>
                {revealedSolutions.has(i) ? "Hide Solution" : "Show Solution"}
              </button>
              {revealedSolutions.has(i) && (
                <p style={{ color: "green" }}>
                  Solution: <code>{p.solution_uci.join(" ")}</code>
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {puzzles.length === 0 && !loading && pgn && (
        <p>No puzzles generated. Try a game with more mistakes.</p>
      )}
    </section>
  );
};

export default PuzzleTrainer;
