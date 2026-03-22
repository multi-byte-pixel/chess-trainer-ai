import React from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import PositionExplorer from "./components/PositionExplorer";
import ThreeSourceComparison from "./components/ThreeSourceComparison";
import OpeningExplorer from "./components/OpeningExplorer";
import PuzzleTrainer from "./components/PuzzleTrainer";
import EndgameExplorer from "./components/EndgameExplorer";

/**
 * Main application shell.
 *
 * Provides navigation between the feature pages:
 *   - Position Explorer (ChessDB)
 *   - Three-Source Comparison
 *   - Opening Explorer
 *   - Puzzle Trainer
 *   - Endgame Explorer (tablebase)
 */
const App: React.FC = () => {
  return (
    <BrowserRouter>
      <div style={{ fontFamily: "sans-serif", padding: "1rem" }}>
        <header>
          <h1>♟ Chess Trainer AI</h1>
          <nav style={{ display: "flex", gap: "1rem", marginBottom: "1rem" }}>
            <Link to="/">Position Explorer</Link>
            <Link to="/compare">Three-Source Comparison</Link>
            <Link to="/openings">Opening Explorer</Link>
            <Link to="/puzzles">Puzzle Trainer</Link>
            <Link to="/endgames">Endgame Explorer</Link>
          </nav>
        </header>

        <main>
          <Routes>
            <Route path="/" element={<PositionExplorer />} />
            <Route path="/compare" element={<ThreeSourceComparison />} />
            <Route path="/openings" element={<OpeningExplorer />} />
            <Route path="/puzzles" element={<PuzzleTrainer />} />
            <Route path="/endgames" element={<EndgameExplorer />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
};

export default App;
