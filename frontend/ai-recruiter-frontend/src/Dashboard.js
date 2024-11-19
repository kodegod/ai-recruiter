import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './Dashboard.css';

const API_URL = process.env.REACT_APP_API_URL

function Dashboard() {
  // State management
  const [jdFile, setJdFile] = useState(null);
  const [resumeFile, setResumeFile] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [interviewId, setInterviewId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [editingQuestions, setEditingQuestions] = useState({});
  const [uploadProgress, setUploadProgress] = useState({ jd: 0, resume: 0 });
  const [questionsConfirmed, setQuestionsConfirmed] = useState(false);
  const [hasCompletedInterviews, setHasCompletedInterviews] = useState(false);
  const [searchInterviewId, setSearchInterviewId] = useState('');
  const [candidateReport, setCandidateReport] = useState(null);
  const [isValidatingId, setIsValidatingId] = useState(false);
  const [searchError, setSearchError] = useState(null);

  // Check for completed interviews on component mount
  useEffect(() => {
    checkCompletedInterviews();
  }, []);

  // Function to check for completed interviews
  const checkCompletedInterviews = async () => {
    try {
      const response = await axios.get('${API_URL}/interview/check-completed');
      setHasCompletedInterviews(response.data.has_completed_interviews);
    } catch (error) {
      console.error('Error checking completed interviews:', error);
    }
  };

  // Handle file selection
  const handleJdFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) {
        setError('Job Description file size must be less than 5MB');
        event.target.value = null;
      } else {
        setJdFile(file);
        setError(null);
      }
    }
  };

  const handleResumeFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) {
        setError('Resume file size must be less than 5MB');
        event.target.value = null;
      } else {
        setResumeFile(file);
        setError(null);
      }
    }
  };

  // Handle file upload
  const handleFileUpload = async () => {
    if (!jdFile || !resumeFile) {
      setError('Please select both JD and Resume files.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setSuccess(null);
    setQuestions([]);
    setInterviewId('');
    setQuestionsConfirmed(false);

    try {
      // Upload JD
      const jdFormData = new FormData();
      jdFormData.append('file', jdFile);

      const jdResponse = await axios.post(
        '${API_URL}/upload/jd',
        jdFormData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          onUploadProgress: (progressEvent) => {
            const progress = (progressEvent.loaded / progressEvent.total) * 100;
            setUploadProgress(prev => ({ ...prev, jd: progress }));
          }
        }
      );

      // Upload Resume
      const resumeFormData = new FormData();
      resumeFormData.append('file', resumeFile);

      const resumeResponse = await axios.post(
        '${API_URL}/upload/resume',
        resumeFormData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          onUploadProgress: (progressEvent) => {
            const progress = (progressEvent.loaded / progressEvent.total) * 100;
            setUploadProgress(prev => ({ ...prev, resume: progress }));
          }
        }
      );

      // Create interview session
      const formData = new URLSearchParams();
      formData.append('jd_id', jdResponse.data.jd_id);
      formData.append('resume_id', resumeResponse.data.resume_id);

      const createInterviewResponse = await axios.post(
        '${API_URL}/interview/create',
        formData,
        {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          }
        }
      );

      setInterviewId(createInterviewResponse.data.interview_id);
      setQuestions(createInterviewResponse.data.questions || []);
      setSuccess('Files uploaded and questions generated successfully!');
      
    } catch (error) {
      console.error('Upload Error:', error);
      
      let errorMessage = 'Error uploading files or generating questions.';
      
      if (error.response) {
        console.error('Error Response:', error.response.data);
        console.error('Status:', error.response.status);
        console.error('Headers:', error.response.headers);
        errorMessage = error.response.data.detail || error.response.data.message || errorMessage;
      } else if (error.request) {
        console.error('Error Request:', error.request);
        errorMessage = 'No response from server. Please check your connection.';
      } else {
        console.error('Error Message:', error.message);
        errorMessage = error.message;
      }
      
      setError(errorMessage);
    } finally {
      setIsLoading(false);
      setUploadProgress({ jd: 0, resume: 0 });
    }
  };

  // Handle edit/save question
  const toggleEditQuestion = (questionId) => {
    setEditingQuestions(prev => ({
      ...prev,
      [questionId]: !prev[questionId]
    }));
  };

  // Handle question modification
  const handleQuestionChange = (questionId, newText) => {
    setQuestions(questions.map(q => 
      q.id === questionId 
        ? { ...q, question_text: newText }
        : q
    ));
  };

  // Save individual question
  const handleSaveQuestion = async (questionId) => {
    try {
      setIsLoading(true);
      const question = questions.find(q => q.id === questionId);
      
      await axios.put(
        `${API_URL}/interview/questions/${questionId}`,
        {
          question_text: question.question_text
        }
      );
      
      setEditingQuestions(prev => ({
        ...prev,
        [questionId]: false
      }));
      
      setSuccess('Question saved successfully!');
    } catch (error) {
      setError('Error saving question: ' + (error.response?.data?.detail || error.message));
    } finally {
      setIsLoading(false);
    }
  };

  // Save all questions and confirm
  const handleConfirmQuestions = async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      // Save any remaining edited questions
      const savePromises = Object.keys(editingQuestions)
        .filter(id => editingQuestions[id])
        .map(id => handleSaveQuestion(id));
      
      await Promise.all(savePromises);
      
      // Mark questions as confirmed
      await axios.post(`${API_URL}/interview/${interviewId}/confirm`);
      
      setQuestionsConfirmed(true);
      setSuccess(`Questions confirmed! Use Interview ID: ${interviewId} for the video interview.`);
      
    } catch (error) {
      setError('Error confirming questions: ' + (error.response?.data?.detail || error.message));
    } finally {
      setIsLoading(false);
    }
  };

  // Handle interview report search
  const handleSearchReport = async () => {
    if (!searchInterviewId.trim()) {
      setError('Please enter an Interview ID');
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      // Log the ID being searched for debugging
      console.log('Searching for interview:', searchInterviewId);

      const response = await axios.get(
        `${API_URL}/interview/${searchInterviewId.trim()}/details`,
        {
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
          }
        }
      );

      if (response.data) {
        setCandidateReport(response.data);
      } else {
        setError('No data found for this interview ID');
      }
    } catch (error) {
      console.error('Error fetching report:', error.response || error);
      let errorMessage = 'Error fetching report: ';
      
      if (error.response?.status === 404) {
        errorMessage = 'Interview not found';
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error.response?.data?.message) {
        errorMessage = error.response.data.message;
      } else {
        errorMessage += 'Failed to fetch interview report';
      }
      
      setError(errorMessage);
      setCandidateReport(null);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="dashboard">
      <h1>Recruiter Dashboard</h1>
      
      {/* Alerts */}
      {error && (
        <div className="alert alert-error">
          <h4>Error</h4>
          <p>{error}</p>
        </div>
      )}
      
      {success && (
        <div className="alert alert-success">
          <h4>Success</h4>
          <p>{success}</p>
        </div>
      )}
      
      {/* File Upload Section */}
      <section className="upload-section">
        <h2>Upload Documents</h2>
        <div className="file-upload">
          <div className="upload-field">
            <label>Job Description:</label>
            <input 
              type="file" 
              onChange={handleJdFileChange}
              accept=".pdf,.doc,.docx,.txt"
              disabled={isLoading}
            />
            {uploadProgress.jd > 0 && uploadProgress.jd < 100 && (
              <div className="progress-bar">
                <div 
                  className="progress"
                  style={{ width: `${uploadProgress.jd}%` }}
                />
              </div>
            )}
          </div>

          <div className="upload-field">
            <label>Resume:</label>
            <input 
              type="file" 
              onChange={handleResumeFileChange}
              accept=".pdf,.doc,.docx,.txt"
              disabled={isLoading}
            />
            {uploadProgress.resume > 0 && uploadProgress.resume < 100 && (
              <div className="progress-bar">
                <div 
                  className="progress"
                  style={{ width: `${uploadProgress.resume}%` }}
                />
              </div>
            )}
          </div>

          <button
            onClick={handleFileUpload}
            disabled={isLoading || !jdFile || !resumeFile}
            className={`upload-button ${isLoading ? 'loading' : ''}`}
          >
            {isLoading ? 'Uploading...' : 'Upload Files'}
          </button>
        </div>
      </section>

      {/* Questions Section */}
      {questions.length > 0 && !questionsConfirmed && (
        <section className="questions-section">
          <h2>Interview Questions</h2>
          <div className="questions-list">
            {questions.map((question, index) => (
              <div key={question.id} className="question-item">
                <div className="question-header">
                  <label>Question {index + 1}:</label>
                  <button 
                    onClick={() => 
                      editingQuestions[question.id] 
                        ? handleSaveQuestion(question.id)
                        : toggleEditQuestion(question.id)
                    }
                    disabled={isLoading}
                    className={`edit-button ${editingQuestions[question.id] ? 'save-mode' : ''}`}
                  >
                    {editingQuestions[question.id] ? 'Save' : 'Edit'}
                  </button>
                </div>
                <textarea
                  value={question.question_text}
                  onChange={(e) => handleQuestionChange(question.id, e.target.value)}
                  disabled={!editingQuestions[question.id] || isLoading}
                  className={editingQuestions[question.id] ? 'editing' : ''}
                />
              </div>
            ))}
            
            <button 
              onClick={handleConfirmQuestions}
              disabled={isLoading || Object.values(editingQuestions).some(Boolean)}
              className="confirm-button"
            >
              Use these questions
            </button>
          </div>
        </section>
      )}

      {/* Interview Ready Message */}
      {questionsConfirmed && interviewId && (
        <section className="interview-info">
          <h2>Interview Ready!</h2>
          <div className="interview-id-box">
            <p>Interview ID: <strong>{interviewId}</strong></p>
            <p>Use this ID to conduct the video interview with the candidate.</p>
          </div>
        </section>
      )}

      {/* Interview Report Section - Only show if there are completed interviews */}
      {hasCompletedInterviews && (
        <section className="report-section">
          <h2>Interview Report</h2>
          <div className="search-box">
            <div className="search-container">
              <input
                type="text"
                value={searchInterviewId}
                onChange={(e) => {
                  setSearchInterviewId(e.target.value);
                  setSearchError(null);
                }}
                placeholder="Enter Interview ID"
                disabled={isValidatingId}
                className={searchError ? 'error' : ''}
              />
              <button 
                onClick={handleSearchReport}
                disabled={isValidatingId || !searchInterviewId.trim()}
              >
                {isValidatingId ? 'Searching...' : 'Search'}
              </button>
            </div>
            {searchError && (
              <div className="search-error">
                {searchError}
              </div>
            )}
          </div>

          {/* Candidate Report Display */}
          {candidateReport && (
            <div className="report-content">
              <div className="candidate-info">
                <h3>Candidate: {candidateReport.candidate.name}</h3>
                <p>Status: {candidateReport.status}</p>
                <p>Overall Score: {candidateReport.scoring.overall_score}</p>
              </div>

              <div className="questions-responses">
                <h4>Questions and Responses:</h4>
                {candidateReport.questions.map((q, index) => (
                  <div key={index} className="qa-pair">
                    <p className="question">Q: {q.question_text}</p>
                    {q.responses.map((r, rIndex) => (
                      <div key={rIndex} className="response">
                        <p>A: {r.response_text}</p>
                        <p className="score">Score: {r.score}</p>
                        <p className="feedback">Feedback: {r.ai_feedback}</p>
                      </div>
                    ))}
                  </div>
                ))}
              </div>

              <div className="scores-grid">
                <div className="score-card">
                  <h4>Technical Score</h4>
                  <p>{candidateReport.scoring.technical_score}</p>
                </div>
                <div className="score-card">
                  <h4>Communication Score</h4>
                  <p>{candidateReport.scoring.communication_score}</p>
                </div>
                <div className="score-card">
                  <h4>Cultural Fit Score</h4>
                  <p>{candidateReport.scoring.cultural_fit_score}</p>
                </div>
              </div>

              <div className="interview-summary">
                <h4>Interview Summary</h4>
                <div className="summary-section">
                  <h5>Strengths</h5>
                  <ul>
                    {candidateReport.interview_summary.strengths.map((strength, index) => (
                      <li key={index}>{strength}</li>
                    ))}
                  </ul>
                </div>
                <div className="summary-section">
                  <h5>Areas for Improvement</h5>
                  <ul>
                    {candidateReport.interview_summary.areas_for_improvement.map((area, index) => (
                      <li key={index}>{area}</li>
                    ))}
                  </ul>
                </div>
                <div className="overall-recommendation">
                  <h5>Overall Recommendation</h5>
                  <p>{candidateReport.interview_summary.overall_recommendation}</p>
                </div>
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

export default Dashboard;