import React, { useState } from 'react';
import axios from 'axios';

function CandidateSearch({ onSelectCandidate }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [candidates, setCandidates] = useState([]);
  const [error, setError] = useState(null);

  const handleSearch = async () => {
    try {
      setError(null);
      const response = await axios.get(`http://localhost:8000/candidates/search/?name=${searchTerm}`);
      if (Array.isArray(response.data)) {
        setCandidates(response.data);
        if (response.data.length === 0) {
          setError("No candidates found");
        }
      } else {
        setError("Invalid response from server");
      }
    } catch (error) {
      console.error('Error searching candidates:', error);
      setError("An error occurred while searching");
    }
  };

  return (
    <div>
      <input
        type="text"
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        placeholder="Search candidates"
      />
      <button onClick={handleSearch}>Search</button>
      {error && <p>{error}</p>}
      <ul>
        {candidates.map(candidate => (
          <li key={candidate.id} onClick={() => onSelectCandidate(candidate.id)}>
            {candidate.name}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default CandidateSearch;