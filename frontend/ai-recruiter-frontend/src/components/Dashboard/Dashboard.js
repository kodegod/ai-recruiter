import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './Dashboard.css';
import { useAuth } from '../../contexts/AuthContext';
import LogoutButton from '../LogoutButton';

// Error message formatting helper
const formatErrorMessage = (error) => {
  if (typeof error === 'string') return error;
  if (error?.response?.data?.detail) return error.response.data.detail;
  if (error?.message) return error.message;
  return 'An unexpected error occurred';
};

// Create axios instance
const createApi = (token) => {
  const api = axios.create({
    baseURL: process.env.REACT_APP_API_URL,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/json',
    },
    withCredentials: true
  });

  // Add request interceptor
  api.interceptors.request.use((config) => {
    console.log('🟡 API Request:', {
      url: config.url,
      method: config.method,
      hasToken: !!config.headers.Authorization
    });

    if (config.data instanceof FormData) {
      delete config.headers['Content-Type'];
    } else {
      config.headers['Content-Type'] = 'application/json';
    }
    
    const currentToken = localStorage.getItem('token');
    if (currentToken) {
      config.headers.Authorization = `Bearer ${currentToken}`;
    }
    return config;
  }, (error) => {
    console.error('🔴 Request Error:', error);
    return Promise.reject(error);
  });

  // Add response interceptor
  api.interceptors.response.use(
    (response) => {
      console.log('🟢 API Response:', {
        url: response.config.url,
        status: response.status
      });
      return response;
    },
    async (error) => {
      console.error('🔴 Response Error:', error.response || error);
      
      if (error.response?.status === 401) {
        console.log('🟡 Unauthorized, redirecting to login');
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = '/login';
      }
      return Promise.reject(error);
    }
  );

  return api;
};

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
  const { user } = useAuth();
  const [api] = useState(() => createApi(localStorage.getItem('token')));

  // Initialize dashboard
  useEffect(() => {
    const initializeDashboard = async () => {
      console.log('Initializing dashboard...');
      const token = localStorage.getItem('token');
      
      if (!token) {
        console.warn('No token found, redirecting to login');
        window.location.href = '/login';
        return;
      }
  
      try {
        await checkCompletedInterviews();
      } catch (error) {
        console.error('Dashboard initialization error:', error);
        if (error.response?.status === 401) {
          window.location.href = '/login';
        }
      }
    };
  
    initializeDashboard();
  }, []);

  // Function to check for completed interviews
  const checkCompletedInterviews = async () => {
    try {
      console.log('Checking completed interviews...');
      const token = localStorage.getItem('token');
      if (!token) {
        console.warn('No token found');
        return;
      }
  
      const response = await api.get('/interview/check-completed');
      console.log('Check completed response:', response.data);
      
      if (response.data !== undefined) {
        setHasCompletedInterviews(Boolean(response.data.has_completed_interviews));
      }
    } catch (error) {
      console.error('Error checking completed interviews:', error.response || error);
    }
  };

  // Handle file selection for JD
  const handleJdFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) { // 5MB limit
        setError('Job Description file size must be less than 5MB');
        event.target.value = null;
      } else {
        setJdFile(file);
        setError(null);
      }
    }
  };

  // Handle file selection for Resume
  const handleResumeFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) { // 5MB limit
        setError('Resume file size must be less than 5MB');
        event.target.value = null;
        setResumeFile(null);
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
      console.log('Starting file upload...');
      
      // Upload JD
      const jdFormData = new FormData();
      jdFormData.append('file', jdFile);

      console.log('Uploading JD...');
      const jdResponse = await api.post('/upload/jd', jdFormData, {
        onUploadProgress: (progressEvent) => {
          const progress = (progressEvent.loaded / progressEvent.total) * 100;
          setUploadProgress(prev => ({ ...prev, jd: progress }));
        }
      });

      if (!jdResponse.data?.jd_id) {
        throw new Error('Invalid JD upload response');
      }

      // Upload Resume
      const resumeFormData = new FormData();
      resumeFormData.append('file', resumeFile);

      console.log('Uploading resume...');
      const resumeResponse = await api.post('/upload/resume', resumeFormData, {
        onUploadProgress: (progressEvent) => {
          const progress = (progressEvent.loaded / progressEvent.total) * 100;
          setUploadProgress(prev => ({ ...prev, resume: progress }));
        }
      });

      if (!resumeResponse.data?.resume_id) {
        throw new Error('Invalid resume upload response');
      }
  
      // Create interview session - FIXED THIS PART
      const formData = new FormData();
      formData.append('jd_id', jdResponse.data.jd_id);
      formData.append('resume_id', resumeResponse.data.resume_id);

      console.log('Creating interview session...');
      const createInterviewResponse = await api.post('/interview/create', formData);

      console.log('Interview Creation Response:', createInterviewResponse.data);

      const { interview_id, questions: generatedQuestions } = createInterviewResponse.data;

      if (interview_id) {
        setInterviewId(interview_id);
        setQuestions(generatedQuestions || []);
        setSuccess('Files uploaded and questions generated successfully!');
      } else {
        throw new Error('Invalid response from server');
      }

    } catch (error) {
      console.error('Upload Error:', error.response || error);
      setError(formatErrorMessage(error));
    } finally {
      setIsLoading(false);
      setUploadProgress({ jd: 0, resume: 0 });
    }
  };

  // Handle question modification
  const handleQuestionChange = (questionId, newText) => {
    setQuestions(questions.map(q => 
      q.id === questionId 
        ? { ...q, question_text: newText }
        : q
    ));
  };

  // Handle edit/save question
  const toggleEditQuestion = (questionId) => {
    setEditingQuestions(prev => ({
      ...prev,
      [questionId]: !prev[questionId]
    }));
  };

  // Save individual question
  const handleSaveQuestion = async (questionId) => {
    try {
      setIsLoading(true);
      const question = questions.find(q => q.id === questionId);
      
      await api.put(`/interview/questions/${questionId}`, {
        question_text: question.question_text
      });
      
      setEditingQuestions(prev => ({
        ...prev,
        [questionId]: false
      }));
      
      setSuccess('Question saved successfully!');
    } catch (error) {
      setError(formatErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  };

  // Save all questions and confirm
  const handleConfirmQuestions = async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      const savePromises = Object.keys(editingQuestions)
        .filter(id => editingQuestions[id])
        .map(id => handleSaveQuestion(id));
      
      await Promise.all(savePromises);
      await api.post(`/interview/${interviewId}/confirm`);
      
      setQuestionsConfirmed(true);
      setSuccess(`Questions confirmed! Use Interview ID: ${interviewId} for the video interview.`);
      
    } catch (error) {
      setError(formatErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  };

  // Handle interview report search
  const handleSearchReport = async () => {
    if (!searchInterviewId.trim()) {
      setSearchError('Please enter an Interview ID');
      return;
    }

    try {
      setIsLoading(true);
      setIsValidatingId(true);
      setError(null);

      const response = await api.get(`/interview/${searchInterviewId.trim()}/details`);

      if (response.data) {
        setCandidateReport(response.data);
      } else {
        setSearchError('No data found for this interview ID');
      }
    } catch (error) {
      console.error('Error fetching report:', error.response || error);
      setSearchError(formatErrorMessage(error));
      setCandidateReport(null);
    } finally {
      setIsLoading(false);
      setIsValidatingId(false);
    }
  };

  return (
    <div className="dashboard">
      <h1>Recruiter Dashboard</h1>
      <div className="user-info flex items-center gap-4">
        <div>
          <p className="font-medium">{user?.name}</p>
          <p className="text-sm text-gray-600">{user?.email}</p>
        </div>
        <LogoutButton />
      </div>

      {/* Alerts */}
      {error && (
        <div className="alert alert-error">
          <h4>Error</h4>
          <p>{typeof error === 'string' ? error : formatErrorMessage(error)}</p>
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

      {/* Interview Report Section */}
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
                {typeof searchError === 'string' ? searchError : formatErrorMessage(searchError)}
              </div>
            )}
          </div>

          {/* Candidate Report Display */}
          {candidateReport && (
            <div className="report-content">
              <div className="candidate-info">
                <h3>Candidate: {candidateReport.candidate?.name}</h3>
                <p>Status: {candidateReport.status}</p>
                <p>Overall Score: {candidateReport.scoring?.overall_score}</p>
              </div>

              <div className="questions-responses">
                <h4>Questions and Responses:</h4>
                {candidateReport.questions?.map((q, index) => (
                  <div key={index} className="qa-pair">
                    <p className="question">Q: {q.question_text}</p>
                    {q.responses?.map((r, rIndex) => (
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
                  <p>{candidateReport.scoring?.technical_score}</p>
                </div>
                <div className="score-card">
                  <h4>Communication Score</h4>
                  <p>{candidateReport.scoring?.communication_score}</p>
                </div>
                <div className="score-card">
                  <h4>Cultural Fit Score</h4>
                  <p>{candidateReport.scoring?.cultural_fit_score}</p>
                </div>
              </div>

              <div className="interview-summary">
                <h4>Interview Summary</h4>
                {candidateReport.interview_summary && (
                  <>
                    <div className="summary-section">
                      <h5>Strengths</h5>
                      <ul>
                        {candidateReport.interview_summary.strengths?.map((strength, index) => (
                          <li key={index}>{strength}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="summary-section">
                      <h5>Areas for Improvement</h5>
                      <ul>
                        {candidateReport.interview_summary.areas_for_improvement?.map((area, index) => (
                          <li key={index}>{area}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="overall-recommendation">
                      <h5>Overall Recommendation</h5>
                      <p>{candidateReport.interview_summary.overall_recommendation}</p>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

export default Dashboard;