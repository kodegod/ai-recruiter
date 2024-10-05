import React, { useState, useRef, useEffect, useCallback } from "react";
import axios from "axios";
import Webcam from "react-webcam";
import './App.css';

function App() {
  const [recording, setRecording] = useState(false);
  const [videoResponse, setVideoResponse] = useState(null);
  const [isNewVideo, setIsNewVideo] = useState(false);
  const [loading, setLoading] = useState(false);  // New state for loading
  const webcamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const [capturedChunks, setCapturedChunks] = useState([]);

  // Function to handle the start of video recording
  const startRecording = () => {
    setCapturedChunks([]); // Clear previous chunks
    setRecording(true);
    mediaRecorderRef.current = new MediaRecorder(webcamRef.current.stream, {
      mimeType: "video/webm",
      audioBitsPerSecond: 128000, // Set higher bitrate for better audio quality
      videoBitsPerSecond: 2500000, // Optionally set higher video quality
    });
    mediaRecorderRef.current.addEventListener("dataavailable", handleDataAvailable);
    mediaRecorderRef.current.start();
  };

  // Function to handle when the user stops recording
  const stopRecording = () => {
    mediaRecorderRef.current.stop();
    setRecording(false);
    setLoading(true); // Start loading animation when user stops recording
  };

  // Function to gather the video data chunks when recording is stopped
  const handleDataAvailable = ({ data }) => {
    if (data.size > 0) {
      setCapturedChunks((prev) => prev.concat(data));
    }
  };

  // Function to automatically upload the video after stopping recording
  const uploadVideo = useCallback(async () => {
    const videoBlob = new Blob(capturedChunks, { type: "video/webm" });
    const formData = new FormData();
    formData.append("file", videoBlob, "user-video.webm");

    try {
      const response = await axios.post(
        "http://localhost:8000/talk-video", // Update this to your backend URL
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
          responseType: "arraybuffer",
        }
      );

      const audioBlob = new Blob([response.data], { type: "audio/mpeg" });
      const audioURL = URL.createObjectURL(audioBlob);
      setVideoResponse(audioURL);
      setIsNewVideo(true);
    } catch (error) {
      console.error("Error uploading the video file:", error);
    } finally {
      setLoading(false);  // Stop loading animation when response is received
    }
  }, [capturedChunks]);

  // Effect to trigger video upload after recording stops
  useEffect(() => {
    if (!recording && capturedChunks.length > 0) {
      uploadVideo();
    }
  }, [recording, capturedChunks, uploadVideo]);

  // Function to play the AI response audio
  const handleVideoPlay = () => {
    setIsNewVideo(false);
  };

  return (
    <div className="AppContainer">
      <h1 className="Header">AI Powered Recruiter - Video Interview</h1>
      <Webcam 
        audio={true}
        ref={webcamRef}
        audioConstraints={{
          echoCancellation: true,  // Enable echo cancellation to reduce feedback
          noiseSuppression: true,  // Suppress background noise
          autoGainControl: false,  // Disable auto gain control to prevent over-amplifying low sounds
          sampleRate: 16000        // Set sample rate to control audio quality
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

      {/* Display the animation while waiting for AI response */}
      {loading && (
        <div className="ListeningAnimation">
          <h2>Listening...</h2>
          <div className="spinner"></div> {/* Add a spinner animation */}
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

export default App;