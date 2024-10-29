import React, { useState } from 'react';
import Dashboard from './Dashboard';
import VideoInterview from './VideoInterview';
import './App.css';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');

  return (
    <div className="app">
      <div className="tab-container">
        <div className="tabs">
          <button 
            className={`tab ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            Recruiter Dashboard
          </button>
          <button 
            className={`tab ${activeTab === 'interview' ? 'active' : ''}`}
            onClick={() => setActiveTab('interview')}
          >
            Video Interview
          </button>
        </div>
      </div>

      <div className="tab-content">
        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'interview' && <VideoInterview />}
      </div>
    </div>
  );
}

export default App;