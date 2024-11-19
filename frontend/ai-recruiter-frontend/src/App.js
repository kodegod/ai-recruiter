import React, { useState } from 'react';
import Dashboard from './Dashboard';
import VideoInterview from './VideoInterview';
import MockInterview from './MockInterview'; // Import MockInterview component
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
          <button 
            className={`tab ${activeTab === 'mockinterview' ? 'active' : ''}`}
            onClick={() => setActiveTab('mockinterview')}
          >
            Mock Interview
          </button>
        </div>
      </div>

      <div className="tab-content">
        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'interview' && <VideoInterview />}
        {activeTab === 'mockinterview' && <MockInterview />}
      </div>
    </div>
  );
}

export default App;