import React, { useState } from 'react';
import CandidateSearch from './CandidateSearch';
import InterviewDetails from './InterviewDetails';

function Dashboard() {
  const [selectedCandidateId, setSelectedCandidateId] = useState(null);

  const handleSelectCandidate = (candidateId) => {
    setSelectedCandidateId(candidateId);
  };

  return (
    <div>
      <h1>Recruiter Dashboard</h1>
      <CandidateSearch onSelectCandidate={handleSelectCandidate} />
      {selectedCandidateId && <InterviewDetails candidateId={selectedCandidateId} />}
    </div>
  );
}

export default Dashboard;