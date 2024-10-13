

from fastapi import FastAPI, UploadFile, Depends, HTTPException, Query, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
import os
import logging
from groq import Groq
import json
import requests
from fastapi.middleware.cors import CORSMiddleware
from audio_extract import extract_audio
import uuid
from typing import List
import shutil

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()

role = "Frontend Engineer"

# Update CORS settings for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3004"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Candidate(Base):
    __tablename__ = 'candidates'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    interviews = relationship("Interview", back_populates="candidate")

class Interview(Base):
    __tablename__ = 'interviews'
    id = Column(Integer, primary_key=True)
    candidate_id = Column(Integer, ForeignKey('candidates.id'))
    session_id = Column(String, unique=True)
    candidate = relationship("Candidate", back_populates="interviews")
    questions = relationship("Question", back_populates="interview")
    consolidated_score = Column(Float, default=0.0)

class Question(Base):
    __tablename__ = 'questions'
    id = Column(Integer, primary_key=True)
    interview_id = Column(Integer, ForeignKey('interviews.id'))
    interview = relationship("Interview", back_populates="questions")
    question_text = Column(Text, nullable=False)
    response = Column(Text)
    score = Column(Float, default=0.0)

Base.metadata.create_all(bind=engine)

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Verify API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

if not GROQ_API_KEY or not ELEVENLABS_API_KEY:
    logger.error("Missing API keys. Please check your .env file.")
    raise ValueError("Missing API keys")

client = Groq(api_key=GROQ_API_KEY)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/test-groq")
async def test_groq():
    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": "Hello, how are you?"}]
        )
        return {"response": response.choices[0].message.content}
    except Exception as e:
        logger.error(f"Error testing Groq API: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": f"Groq API test failed: {str(e)}"})

@app.get("/candidates/search/")
def search_candidates(name: str, skip: int = Query(0, ge=0), limit: int = Query(10, le=100), db: Session = Depends(get_db)):
    logger.info(f"Searching for candidates with name: {name}")
    try:
        candidates = db.query(Candidate).filter(Candidate.name.ilike(f"%{name}%")).offset(skip).limit(limit).all()
        logger.info(f"Found {len(candidates)} candidates")
        return [{"id": c.id, "name": c.name} for c in candidates]
    except Exception as e:
        logger.error(f"Error searching candidates: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.get("/candidates/{candidate_id}/interviews")
def get_candidate_interviews(candidate_id: int, db: Session = Depends(get_db)):
    logger.info(f"Fetching interviews for candidate ID: {candidate_id}")
    interviews = db.query(Interview).filter(Interview.candidate_id == candidate_id).all()
    if not interviews:
        logger.warning(f"No interviews found for candidate ID: {candidate_id}")
        raise HTTPException(status_code=404, detail="No interviews found for this candidate")
    
    interview_data = []
    for interview in interviews:
        interview_dict = jsonable_encoder(interview)
        interview_dict['questions'] = [jsonable_encoder(q) for q in interview.questions]
        interview_data.append(interview_dict)
    
    return interview_data

@app.get("/interviews/{interview_id}/details")
def get_interview_details(interview_id: int, db: Session = Depends(get_db)):
    logger.info(f"Fetching details for interview ID: {interview_id}")
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        logger.warning(f"Interview not found for ID: {interview_id}")
        raise HTTPException(status_code=404, detail="Interview not found")
    return {
        "id": interview.id,
        "candidate_name": interview.candidate.name,
        "consolidated_score": interview.consolidated_score,
        "questions": [
            {
                "question": q.question_text,
                "response": q.response,
                "score": q.score
            } for q in interview.questions
        ]
    }

@app.post("/talk")
async def post_audio(file: UploadFile = File(...), candidate_name: str = Form(...), db: Session = Depends(get_db)):
    logger.info(f"Received audio file for candidate: {candidate_name}")
    try:
        user_message = await transcribe_audio(file)
        logger.info(f"Transcribed message: {user_message[:50]}...")

        chat_response, ai_question = get_chat_response(str(uuid.uuid4()), user_message, role)
        logger.info(f"AI response: {chat_response[:50]}...")
        logger.info(f"AI question: {ai_question}")

        candidate = db.query(Candidate).filter(Candidate.name == candidate_name).first()
        if not candidate:
            candidate = Candidate(name=candidate_name)
            db.add(candidate)
            db.flush()
            logger.info(f"Created new candidate: {candidate_name}")

        interview = Interview(candidate_id=candidate.id)
        db.add(interview)
        db.flush()
        logger.info(f"Created new interview for candidate: {candidate_name}")

        question = Question(
            interview_id=interview.id,
            question_text=ai_question,
            response=user_message,
            score=calculate_score(user_message)
        )
        db.add(question)
        db.commit()
        logger.info("Saved interview data to database")

        audio_output = text_to_speech(chat_response)
        logger.info("Generated audio response")

        def iterfile():
            yield audio_output
        return StreamingResponse(iterfile(), media_type='audio/mpeg')

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error in post_audio: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": f"Database error: {str(e)}"})
    except Exception as e:
        logger.error(f"Error in post_audio: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": f"An error occurred: {str(e)}"})

@app.post("/talk-video")
async def post_video(file: UploadFile = File(...), candidate_name: str = Form(...), db: Session = Depends(get_db)):
    logger.info(f"Received video file: {file.filename}, Candidate name: {candidate_name}")
    temp_dir = "temp/"
    webm_path = ""
    audio_path = ""
    session_id = str(uuid.uuid4())
    try:
        if not candidate_name.strip():
            raise HTTPException(status_code=400, detail="Candidate name cannot be empty")

        os.makedirs(temp_dir, exist_ok=True)

        webm_path = f"{temp_dir}{file.filename}"
        with open(webm_path, "wb") as video_file:
            content = await file.read()
            video_file.write(content)
        logger.info(f"Saved video file to {webm_path}")

        audio_path = f"{temp_dir}audio_from_video_{uuid.uuid4()}.wav"
        extract_audio(input_path=webm_path, output_path=audio_path, output_format='wav', overwrite=True)
        logger.info(f"Extracted audio to {audio_path}")

        user_message = await transcribe_audio_from_video(audio_path)
        logger.info(f"Transcribed message: {user_message[:50]}...")

        chat_response, ai_question = get_chat_response(session_id, user_message, role)
        logger.info(f"AI response: {chat_response[:50]}...")
        logger.info(f"AI question: {ai_question}")

        candidate = db.query(Candidate).filter(Candidate.name == candidate_name).first()
        if not candidate:
            candidate = Candidate(name=candidate_name)
            db.add(candidate)
            db.flush()
            logger.info(f"Created new candidate: {candidate_name}")
        else:
            logger.info(f"Found existing candidate: {candidate_name}")

        interview = Interview(candidate_id=candidate.id, session_id=session_id)
        db.add(interview)
        db.flush()
        logger.info(f"Created new interview for candidate: {candidate_name}")

        question = Question(
            interview_id=interview.id,
            question_text=ai_question,
            response=user_message,
            score=calculate_score(user_message)
        )
        db.add(question)
        db.commit()
        logger.info("Saved interview data to database")

        audio_output = text_to_speech(chat_response)
        logger.info(f"Received audio output from text_to_speech, size: {len(audio_output)} bytes")

        def iterfile():
            yield audio_output
        return StreamingResponse(iterfile(), media_type='audio/mpeg')

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error in post_video: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": f"Database error: {str(e)}"})
    except HTTPException as he:
        return JSONResponse(status_code=he.status_code, content={"detail": he.detail})
    except Exception as e:
        logger.error(f"Error in post_video: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": f"An error occurred: {str(e)}"})
    finally:
        if webm_path and os.path.exists(webm_path):
            os.remove(webm_path)
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
        logger.info("Cleaned up temporary files")

@app.get("/test-candidates")
def test_candidates(db: Session = Depends(get_db)):
    candidates = db.query(Candidate).all()
    return {"count": len(candidates), "candidates": [{"id": c.id, "name": c.name} for c in candidates]}

async def transcribe_audio(file):
    file_content = await file.read()
    transcription = client.audio.transcriptions.create(
        file=(file.filename, file_content),
        model="distil-whisper-large-v3-en",
        prompt="Specify context or spelling",
        response_format="json",
        language="en",
        temperature=0.0
    )
    return transcription.text

async def transcribe_audio_from_video(file_path):
    with open(file_path, "rb") as audio_file:
        file_content = audio_file.read()

    transcription = client.audio.transcriptions.create(
        file=("audio_from_video.wav", file_content),
        model="distil-whisper-large-v3-en",
        prompt="Specify context or spelling",
        response_format="json",
        language="en",
        temperature=0.0
    )
    return transcription.text

def load_messages(session_id, role):
    session_file = f'sessions/{session_id}.json'
    if os.path.exists(session_file) and os.stat(session_file).st_size > 0:
        with open(session_file) as db_file:
            return json.load(db_file)
    else:
        return [{
            "role": "system",
            "content": f"""
You are ai-recruiter, an experienced interviewer conducting a preliminary interview for the role of {role}. Your goal is to
assess the candidate's suitability for {role} role based on specific criteria, including their communication skills,
relevant experience, and alignment with the company's values. You will ask a series of tailored questions to
evaluate these aspects, encouraging the candidate to provide detailed responses. You will also observe non-verbal
cues such as tone, enthusiasm, and clarity of speech. Begin the interview by introducing yourself and then asking the interviewee to introduce themselves
briefly, then proceed with questions related to the candidate's experience, skills, and motivation for applying.
Use follow-up questions to delve deeper into their answers if needed. Ensure that the interaction is professional,
engaging, and respectful, making the candidate feel comfortable while maintaining a focus on extracting relevant
information. Conclude the interview by thanking the candidate for their time and asking them to wait for
the result of this interview and next steps in the hiring process.
            """
        }]

def save_messages(session_id, messages):
    os.makedirs('sessions', exist_ok=True)
    session_file = f'sessions/{session_id}.json'
    with open(session_file, 'w') as f:
        json.dump(messages, f)

def get_chat_response(session_id, user_message, role):
    try:
        messages = load_messages(session_id, role)
        messages.append({"role": "user", "content": user_message})

        logger.info(f"Sending request to Groq API for session {session_id}")
        llm_response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=messages
        )
        
        ai_response = llm_response.choices[0].message.content
        logger.info(f"Received response from Groq API: {ai_response[:100]}...")  # Log first 100 chars

        ai_question = extract_question(ai_response)
        logger.info(f"Extracted question: {ai_question}")

        messages.append({"role": "assistant", "content": ai_response})
        save_messages(session_id, messages)

        return ai_response, ai_question
    except Exception as e:
        logger.error(f"Error in get_chat_response: {str(e)}")
        raise

import logging

logger = logging.getLogger(__name__)

def text_to_speech(text):
    url = "https://api.elevenlabs.io/v1/text-to-speech/pNInz6obpgDQGcFmaJgB"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    data = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.5,
            "style": 0.5,
            "use_speaker_boost": True
        }
    }
    try:
        logger.info(f"Sending request to ElevenLabs API with text: {text[:100]}...")  # Log first 100 chars
        response = requests.post(url, json=data, headers=headers)
        logger.info(f"ElevenLabs API response status: {response.status_code}")
        
        if response.status_code == 200:
            audio_content = response.content
            logger.info(f"Received audio response, size: {len(audio_content)} bytes")
            return audio_content
        else:
            error_message = f"ElevenLabs API error: {response.status_code}, Response: {response.text}"
            logger.error(error_message)
            raise Exception(error_message)
    except requests.RequestException as e:
        error_message = f"Network error in text-to-speech request: {str(e)}"
        logger.error(error_message)
        raise HTTPException(status_code=500, detail=error_message)
    except Exception as e:
        error_message = f"Unexpected error in text-to-speech: {str(e)}"
        logger.error(error_message)
        raise HTTPException(status_code=500, detail=error_message)

def calculate_score(response):
    # Implement your scoring logic here
    # This is a placeholder implementation
    return len(response) / 100  # Simple score based on response length

def extract_question(ai_response):
    # Split the response into sentences
    sentences = ai_response.split('.')
    questions = []

    for sentence in sentences:
        # Strip whitespace and check if the sentence contains a question mark
        sentence = sentence.strip()
        if '?' in sentence:
            # Ensure the sentence ends with a question mark
            if not sentence.endswith('?'):
                sentence += '?'
            questions.append(sentence)

    # If questions were found, return the last one (usually the most relevant)
    if questions:
        return questions[-1]
    
    # If no questions were found, return a default message
    return "No explicit question found in the AI response. The AI may be waiting for more information or clarification."

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting the FastAPI server")
    uvicorn.run(app, host="0.0.0.0", port=8000)