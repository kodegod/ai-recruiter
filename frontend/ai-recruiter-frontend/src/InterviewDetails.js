import React, { useState, useEffect } from 'react';
import axios from 'axios';

function InterviewDetails({ candidateId }) {
  const [interviews, setInterviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchInterviews = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`http://localhost:8000/candidates/${candidateId}/interviews`);
        setInterviews(response.data);
        setLoading(false);
      } catch (err) {
        console.error('Error fetching interviews:', err);
        setError('Failed to fetch interview details');
        setLoading(false);
      }
    };

    if (candidateId) {
      fetchInterviews();
    }
  }, [candidateId]);

  if (loading) return <p>Loading interview details...</p>;
  if (error) return <p>{error}</p>;

  return (
    <div>
      <h2>Interview Details</h2>
      {interviews.length === 0 ? (
        <p>No interviews found for this candidate.</p>
      ) : (
        interviews.map(interview => (
          <div key={interview.id}>
            <h3>Interview {interview.id}</h3>
            <p>Score: {interview.consolidated_score}</p>
            {interview.questions && interview.questions.map((q, index) => (
              <div key={index}>
                <p><strong>Q: {q.question_text}</strong></p>
                <p>A: {q.response}</p>
                <p>Score: {q.score}</p>
              </div>
            ))}
          </div>
        ))
      )}
    </div>
  );
}

export default InterviewDetails;