import React, { useState } from 'react';
import axios from 'axios';
import './MockInterview.css';

const API_URL = process.env.REACT_APP_API_URL

function MockInterview() {
  const [jobRole, setJobRole] = useState('');
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState('');

  const startMockInterview = async () => {
    if (!jobRole.trim()) {
      alert('Please enter a job role.');
      return;
    }

    setLoading(true);
    setResponse('');

    try {
      const res = await axios.post(`${API_URL}/mock-interview`, {
        job_role: jobRole,
      });

      setResponse(res.data.message); // Handle the response from the backend
    } catch (error) {
      console.error('Error starting mock interview:', error);
      setResponse('Failed to start the mock interview. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mock-interview-container">
      <h2>Mock Interview</h2>
      <div className="form-group">
        <label htmlFor="job-role">Enter Job Role:</label>
        <input
          type="text"
          id="job-role"
          value={jobRole}
          onChange={(e) => setJobRole(e.target.value)}
          placeholder="e.g., Software Engineer"
        />
      </div>
      <button onClick={startMockInterview} disabled={loading}>
        {loading ? 'Starting...' : 'Start Mock Interview'}
      </button>
      {response && <div className="response-message">{response}</div>}
    </div>
  );
}

export default MockInterview;