import React, { useState, useRef, useEffect, useCallback } from "react";
import axios from "axios";
import { ReactMic } from "react-mic";
import Webcam from "react-webcam";
import './App.css';

function App() {
  const [recording, setRecording] = useState(false);
  const [videoResponse, setVideoResponse] = useState(null);
  const [isNewVideo, setIsNewVideo] = useState(false);
  const [loading, setLoading] = useState(false);  // New state for loading
  const [blob, setBlob] = useState(null); // Store the recorded audio blob
  const webcamRef = useRef(null);
  
  // Start recording only audio
  const startRecording = () => {
    setRecording(true);
    setBlob(null); // Reset the previous blob
  };

  // Stop recording the audio
  const stopRecording = () => {
    setRecording(false);
    setLoading(true); // Start loading animation when user stops recording
  };

  // On stop, handle the audio data
  const onStop = (recordedBlob) => {
    setBlob(recordedBlob); // Save the recorded audio blob
  };

  // Automatically upload audio after recording stops
  const uploadAudio = useCallback(async () => {
    if (blob) {
      const formData = new FormData();
      formData.append("file", blob.blob, "user-audio.wav");

      try {
        const response = await axios.post(
          "http://localhost:8000/talk", // Update this to your backend URL
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
        console.error("Error uploading the audio file:", error);
      } finally {
        setLoading(false);  // Stop loading animation when response is received
      }
    }
  }, [blob]);

  // Effect to upload audio once the recording stops
  useEffect(() => {
    if (!recording && blob) {
      uploadAudio();
    }
  }, [recording, blob, uploadAudio]);

  // Function to play the AI response audio
  const handleVideoPlay = () => {
    setIsNewVideo(false);
  };

  return (
    <div className="AppContainer">
      <h1 className="Header">AI Powered Recruiter - Video Interview</h1>
      
      {/* Show the webcam to make it look like video recording */}
      <Webcam 
        audio={false} // No audio here
        ref={webcamRef}
      />

      {/* React-Mic to record audio */}
      <div style={{ width: 0, height: 0, overflow: 'hidden' }}>
        <ReactMic
          record={recording}
          onStop={onStop}
          mimeType="audio/wav"
          visualize={false} // Disable the sound wave visualization
        />
      </div>

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