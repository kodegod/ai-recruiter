# [AI Recruiter](https://ai-recruiter-tau.vercel.app/)

Live Link - https://ai-recruiter-tau.vercel.app/

[AI Recruiter](https://ai-recruiter-tau.vercel.app/) is an intelligent platform that streamlines and enhances the hiring process by leveraging AI technologies to conduct mock interviews, create customized interviews for recruiters, and facilitate real-time video interviews with automated scoring and feedback.

## Overview

AI Recruiter has two main components:

- **Frontend:** Built using React and Three.js, the frontend provides an interactive and visually engaging user interface.
- **Backend:** Powered by FastAPI, the backend handles data processing, interview session management, AI-driven question generation, audio transcription, and feedback analysis.

## Features

### Frontend Features

- **Mock Interview:**

    - Allows candidates to quickly prepare for interviews by entering a job role.
    - Automatically generates interview questions for the specified role.

- **Recruiter Dashboard:**

    - Uploading a Job Description (JD) file.
    - Uploading a candidate's resume.
    - Adding custom interview questions.
    - Automatically generates questions based on the JD and resume.

- **Video Interview:**

    - Enables real-time interviews where candidates respond to AI-generated questions.
    - Automatically transcribes and analyzes audio responses.
    - Provides scores and feedback for:
        - Technical Proficiency
        - Communication Skills
        - Cultural Fit

### Backend Features

- **Job Description Management:**

Upload and process JDs to extract role-specific details like title, company, and requirements.

- **Resume Management:**

Upload and process resumes to extract candidate information, skills, and experience.

- **Interview Session Management:**

    - Combine JD and resume to create interview sessions.
    - Generate AI-powered questions tailored to the JD and resume.
    - Edit, update, and confirm questions before starting the interview.

- **Mock Interview Generation:**

Dynamically generate a JD and interview questions for candidates without requiring any uploads.

- **Audio Transcription:**

Converts candidate audio responses into text using OpenAI Whisper API.

- **AI Feedback and Scoring:**

    - Analyzes transcriptions to provide scores and feedback on:
    - Relevance to the question.
    - Clarity of response.
    - Technical accuracy.
    - Generates improvement suggestions and highlights strengths.

- **Text-to-Speech:**

Responds to candidates with audio feedback using ElevenLabs API.


## Technology Stack

### Frontend

- **React:** Component-based architecture for building the user interface.
- **Three.js:** 3D animations and visual effects for the landing animation and background.
- **CSS:** Styling for components and layouts.

### Backend
- **FastAPI:** Framework for building the RESTful API.
- **SQLAlchemy:** ORM for database operations.
- **OpenAI Whisper API:** Audio-to-text transcription.
- **OpenAI GPT-like models:** AI-powered question generation and feedback.
- **ElevenLabs API:** Text-to-speech functionality for audio responses.

### Database
- **SQLite:** Used as the default database (can be swapped for PostgreSQL, MySQL, etc.).

## Usage

### Mock Interview

- Navigate to the Mock Interview tab in the app.
- Enter a job role and click Create Mock Interview.
- The backend generates a dynamic JD and interview questions for the role.

### Recruiter Dashboard
- Navigate to the Recruiter Dashboard tab.
- Upload:
        - Job Description file.
        - Candidate Resume file.
        - Customize or confirm AI-generated interview questions.
- A unique Interview ID is generated.

### Video Interview

- Navigate to the Video Interview tab.
- Enter the Interview ID generated from the Recruiter Dashboard or Mock Interview.
- Answer questions in real-time, and the backend:
- Transcribes audio.
- Scores and analyzes responses.
- Provides feedback.

## Setup and Installation

### Prerequisites

1. Node.js and npm (for the frontend).
2. Python 3.8+ (for the backend).
3. Environment Variables:
- DATABASE_URL: Database connection string (default: SQLite).
- OPENAI_API_KEY: OpenAI API key for transcription and question generation.
- GROQ_API_KEY: API key for LLM-based question generation.
- ELEVENLABS_API_KEY: ElevenLabs API key for text-to-speech functionality.

### Frontend Setup

1. Clone the repository:

```
git clone https://github.com/kodegod/ai-recruiter.git
```

2. Install dependencies:

```
npm install
```

3. Set up environment variable

```
REACT_APP_API_URL = http://localhost:8000
```

4. Start the development server:

```
npm start
```

The app will be available at http://localhost:3000.

### Backend Setup

1. Install dependencies:

```
pip install -r requirements.txt
```

2. Set up environment variables:

Create a .env file in the backend directory:

```
OPENAI_API_KEY=<your_openai_api_key>
GROQ_API_KEY=<your_groq_api_key>
ELEVENLABS_API_KEY=<your_elevenlabs_api_key>
```

3. Start the server:

```
uvicorn main:app --reload
```






