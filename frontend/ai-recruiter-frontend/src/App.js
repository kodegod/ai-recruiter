import React from "react";
import { BrowserRouter as Router, Route, Routes, Link } from "react-router-dom";
import VideoInterview from "./VideoInterview";
import Dashboard from "./Dashboard";
import './App.css';

function App() {
  return (
    <Router>
      <div className="App">
        <nav>
          <ul>
            <li><Link to="/">Video Interview</Link></li>
            <li><Link to="/dashboard">Recruiter Dashboard</Link></li>
          </ul>
        </nav>

        <Routes>
          <Route path="/" element={<VideoInterview />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;