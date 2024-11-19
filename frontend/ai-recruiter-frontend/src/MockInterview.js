import React, { useState } from 'react';
import axios from 'axios';
import './MockInterview.css';

const API_URL = process.env.REACT_APP_API_URL;

function MockInterview() {
  const [jobRole, setJobRole] = useState('');
  const [interviewId, setInterviewId] = useState('');
  const [questions, setQuestions] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const handleCreateMockInterview = async () => {
    if (!jobRole.trim()) {
      setError('Please enter a job role');
      return;
    }

    setIsLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const formData = new URLSearchParams();
      formData.append('job_role', jobRole);

      const response = await axios.post(`${API_URL}/mock-interview`, formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      setInterviewId(response.data.interview_id);
      setQuestions(response.data.questions);
      setSuccess('Mock interview created successfully! Use the ID to start the interview.');
    } catch (error) {
      console.error('Error creating mock interview:', error.response || error);
      setError('Failed to create mock interview: ' + (error.response?.data?.detail || error.message));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="mock-interview">
      <h2>Mock Interview</h2>
      {/* Alerts */}
      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}
  
      {/* Input for Job Role */}
      <div className="input-group">
        <label>Job Role:</label>
        <input
          type="text"
          value={jobRole}
          onChange={(e) => setJobRole(e.target.value)}
          placeholder="Enter Job Role"
          disabled={isLoading}
        />
      </div>
  
      <button
        onClick={handleCreateMockInterview}
        disabled={isLoading || !jobRole.trim()}
        className="create-button"
      >
        {isLoading ? 'Creating...' : 'Create Mock Interview'}
      </button>
  
      {/* Interview Details */}
      {interviewId && (
        <div className="interview-details">
          <h3>Mock Interview Created</h3>
          <p>Interview ID: <strong>{interviewId}</strong></p>
          <p>Use this ID in the Video Interview tab to start the interview.</p>
        </div>
      )}
    </div>
  );
}

export default MockInterview;