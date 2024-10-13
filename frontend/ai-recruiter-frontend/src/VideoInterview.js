import React, { useState, useRef, useEffect, useCallback } from "react";
import axios from "axios";
import Webcam from "react-webcam";
import './App.css';

function VideoInterview() {
  const [recording, setRecording] = useState(false);
  const [videoResponse, setVideoResponse] = useState(null);
  const [isNewVideo, setIsNewVideo] = useState(false);
  const [loading, setLoading] = useState(false);
  const [candidateName, setCandidateName] = useState('');
  const [error, setError] = useState(null);  // New error state
  const webcamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const [capturedChunks, setCapturedChunks] = useState([]);

  const startRecording = () => {
    if (!candidateName.trim()) {
      alert("Please enter your name before starting the interview.");
      return;
    }
    setCapturedChunks([]);
    setRecording(true);
    mediaRecorderRef.current = new MediaRecorder(webcamRef.current.stream, {
      mimeType: "video/webm",
      audioBitsPerSecond: 128000,
      videoBitsPerSecond: 2500000,
    });
    mediaRecorderRef.current.addEventListener("dataavailable", handleDataAvailable);
    mediaRecorderRef.current.start();
  };

  const stopRecording = () => {
    mediaRecorderRef.current.stop();
    setRecording(false);
    setLoading(true);
  };

  const handleDataAvailable = ({ data }) => {
    if (data.size > 0) {
      setCapturedChunks((prev) => prev.concat(data));
    }
  };

  const uploadVideo = useCallback(async () => {
    const videoBlob = new Blob(capturedChunks, { type: "video/webm" });
    const formData = new FormData();
    formData.append("file", videoBlob, "user-video.webm");
    formData.append("candidate_name", candidateName.trim() || "Anonymous");
  
    try {
      console.log("Sending video to backend...");
      const response = await axios.post(
        "http://localhost:8000/talk-video",
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
          responseType: "arraybuffer",
        }
      );
      
      console.log("Received response from backend");
      console.log("Response headers:", response.headers);
      console.log("Response data length:", response.data.byteLength);
  
      if (response.headers['content-type'].includes('audio')) {
        const audioBlob = new Blob([response.data], { type: "audio/mpeg" });
        console.log("Created audio blob, size:", audioBlob.size);
        const audioURL = URL.createObjectURL(audioBlob);
        console.log("Created audio URL:", audioURL);
        setVideoResponse(audioURL);
        setIsNewVideo(true);
      } else {
        console.error("Received non-audio response:", new TextDecoder().decode(response.data));
      }
    } catch (error) {
      console.error("Error uploading the video file:", error);
      if (error.response) {
        console.error("Response data:", new TextDecoder().decode(error.response.data));
        console.error("Response status:", error.response.status);
        console.error("Response headers:", error.response.headers);
      } else if (error.request) {
        console.error("No response received:", error.request);
      } else {
        console.error("Error setting up request:", error.message);
      }
    } finally {
      setLoading(false);
    }
  }, [capturedChunks, candidateName]);

  useEffect(() => {
    if (!recording && capturedChunks.length > 0) {
      uploadVideo();
    }
  }, [recording, capturedChunks, uploadVideo]);

  const handleVideoPlay = () => {
    setIsNewVideo(false);
  };

  return (
    <div className="AppContainer">
      <h1 className="Header">AI Powered Recruiter - Video Interview</h1>
      <div className="CandidateNameInput">
        <input
          type="text"
          value={candidateName}
          onChange={(e) => setCandidateName(e.target.value)}
          placeholder="Enter your name"
          disabled={recording}
        />
      </div>
      <Webcam 
        audio={true}
        ref={webcamRef}
        audioConstraints={{
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: false,
          sampleRate: 16000
        }}
      />
      <div>
        <button onClick={startRecording} disabled={recording} className="Button">
          Start Recording
        </button>
        <button onClick={stopRecording} disabled={!recording} className="Button">
          Stop Recording
        </button>
      </div>

      {loading && (
        <div className="ListeningAnimation">
          <h2>Listening...</h2>
          <div className="spinner"></div>
        </div>
      )}

      {error && (
        <div className="ErrorMessage">
          {error}
        </div>
      )}

      <div className="AudioResponseContainer">
        {videoResponse && (
          <div className={`AudioPlayerWrapper ${isNewVideo ? 'isNew' : ''}`}>
            <h2>AI Recruiter Response</h2>
            <audio controls src={videoResponse} onPlay={handleVideoPlay} className="AudioPlayer"></audio>
          </div>
        )}
      </div>
    </div>
  );
}

export default VideoInterview;