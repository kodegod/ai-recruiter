import React, { useState, useRef } from 'react';
import { ReactMic } from 'react-mic';
import Webcam from 'react-webcam';
import axios from 'axios';
import './VideoInterview.css';

function VideoInterview() {
  const [isRecording, setIsRecording] = useState(false);
  const [interviewId, setInterviewId] = useState('');
  const [isValidated, setIsValidated] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [currentQuestion, setCurrentQuestion] = useState(0); // 0 for intro
  const [isInterviewComplete, setIsInterviewComplete] = useState(false);
  const [error, setError] = useState(null);
  const [totalQuestions, setTotalQuestions] = useState(5);
  const webcamRef = useRef(null);

  // Validate interview ID
  const validateInterviewId = async () => {
    if (!interviewId.trim()) {
      setError('Please enter an Interview ID');
      return;
    }

    setIsValidating(true);
    setError(null);

    try {
      const response = await axios.get(
        `http://localhost:8000/interview/validate/${interviewId.trim()}`
      );

      if (response.data.valid) {
        setIsValidated(true);
        setError(null);
      } else {
        setError(response.data.message || 'Invalid Interview ID');
        setIsValidated(false);
      }
    } catch (error) {
      console.error('Validation error:', error.response || error);
      
      let errorMessage = 'Error validating Interview ID';
      if (error.response?.data?.message) {
        errorMessage = error.response.data.message;
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error.response?.status === 404) {
        errorMessage = 'Interview ID not found';
      }
      setError(errorMessage);
      setIsValidated(false);
    } finally {
      setIsValidating(false);
    }
  };

  // Start recording
  const startRecording = () => {
    setIsRecording(true);
    setError(null);
  };

  // Stop recording
  const stopRecording = () => {
    setIsRecording(false);
  };

  // Handle recording data
  const onData = (recordedData) => {
    console.log('Recording data:', recordedData);
  };

  // Handle recording stop
  const onStop = async (recordedBlob) => {
    try {
      const formData = new FormData();
      formData.append('file', recordedBlob.blob);
      formData.append('interview_id', interviewId);

      const response = await axios.post(
        'http://localhost:8000/talk-video',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          responseType: 'arraybuffer'  // Added to match previous version
        }
      );

      // Get interview status from headers
      const interviewStatus = response.headers['x-interview-status'];
      const answeredQuestions = parseInt(response.headers['x-answered-questions'] || '0');
      const totalQs = parseInt(response.headers['x-total-questions'] || '5');

      setTotalQuestions(totalQs);
      setCurrentQuestion(answeredQuestions);

      // Create and play audio response - updated to match previous version
      const audioBlob = new Blob([response.data], { type: 'audio/mpeg' });
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      
      audio.onended = () => {
        if (interviewStatus === 'completed') {
          setIsInterviewComplete(true);
        }
      };

      audio.play();

    } catch (error) {
      console.error('Recording error:', error.response || error);
      setError('Error processing response: ' + 
        (error.response?.data?.detail || error.message));
    }
  };

  // Get question number display
  const getQuestionText = () => {
    if (currentQuestion === 0) {
      return "Please introduce yourself";
    } else if (!isInterviewComplete) {
      return `Question ${currentQuestion} of ${totalQuestions}`;
    } else {
      return "Interview Complete";
    }
  };

  return (
    <div className="video-interview">
      <h2>Video Interview</h2>

      {/* Interview ID Validation Section */}
      {!isValidated && (
        <div className="validation-section">
          <div className="input-group">
            <label>Interview ID:</label>
            <input
              type="text"
              value={interviewId}
              onChange={(e) => {
                setInterviewId(e.target.value);
                setError(null);
              }}
              placeholder="Enter Interview ID"
              disabled={isValidating}
              className={error ? 'error' : ''}
            />
          </div>
          {error && (
            <div className="error-message">
              {error}
              {error === 'Interview ID not found' && (
                <p className="error-help">Please check if the ID was copied correctly</p>
              )}
            </div>
          )}
          <button
            onClick={validateInterviewId}
            disabled={isValidating || !interviewId.trim()}
            className="validate-button"
          >
            {isValidating ? 'Validating...' : 'Start Interview'}
          </button>
        </div>
      )}

      {/* Video Interview Section - Only show after validation */}
      {isValidated && (
        <>
          <div className="interview-status">
            <h3>{getQuestionText()}</h3>
            {error && <div className="error-message">{error}</div>}
          </div>

          <div className="video-section">
            <Webcam
              ref={webcamRef}
              audio={false}
              width={640}
              height={480}
              screenshotFormat="image/jpeg"
            />
          </div>

          {!isInterviewComplete && (
            <div className="audio-section">
              {/* Hide ReactMic visualization but keep functionality */}
              <div style={{ width: 0, height: 0, overflow: 'hidden' }}>
                <ReactMic
                  record={isRecording}
                  onStop={onStop}
                  onData={onData}
                  mimeType="audio/wav"    // Changed to match previous version
                  visualize={false}       // Disable visualization as in previous version
                />
              </div>
              <div className="controls">
                <button 
                  onClick={startRecording} 
                  disabled={isRecording || isInterviewComplete}
                  className="record-button"
                >
                  Start Recording
                </button>
                <button 
                  onClick={stopRecording} 
                  disabled={!isRecording || isInterviewComplete}
                  className="stop-button"
                >
                  Stop Recording
                </button>
              </div>
            </div>
          )}

          {isInterviewComplete && (
            <div className="completion-message">
              <h3>Thank you for completing the interview!</h3>
              <p>Your responses have been recorded. The recruiter will review them shortly.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default VideoInterview;