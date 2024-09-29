import React, { useState, useEffect } from "react";
import { ReactMic } from "react-mic";
import axios from "axios";
import './App.css';

function App() {
  const [record, setRecord] = useState(false);
  const [audioResponse, setAudioResponse] = useState(null);
  const [isNewAudio, setIsNewAudio] = useState(false);

  const startRecording = () => {
    setRecord(true);
  };

  const stopRecording = () => {
    setRecord(false);
  };

  const onStop = async (recordedBlob) => {
    console.log("Recorded Blob is: ", recordedBlob);

    const formData = new FormData();
    formData.append("file", recordedBlob.blob, "user-audio.wav");

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
      setAudioResponse(audioURL);
      setIsNewAudio(true);
    } catch (error) {
      console.error("Error uploading the audio file:", error);
    }
  };

  useEffect(() => {
    if (audioResponse) {
      setIsNewAudio(true);
    }
  }, [audioResponse]);

  const handleAudioPlay = () => {
    setIsNewAudio(false);
  };

  return (
    <div className="AppContainer">
      <h1 className="Header">AI Powered Recruiter</h1>
      <ReactMic
        record={record}
        className="sound-wave"
        onStop={onStop}
        strokeColor="#343a40"
        backgroundColor="#f8f9fa"
      />
      <div>
        <button onClick={startRecording} type="button" disabled={record} className="Button">
          Start Recording
        </button>
        <button onClick={stopRecording} type="button" disabled={!record} className="Button">
          Stop Recording
        </button>
      </div>
      <div className="AudioResponseContainer">
        {audioResponse && (
          <div className={`AudioPlayerWrapper ${isNewAudio ? 'isNew' : ''}`}>
            <h2>AI Recruiter Response</h2>
            <audio controls src={audioResponse} onPlay={handleAudioPlay} className="AudioPlayer"></audio>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;