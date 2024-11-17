from fastapi import FastAPI, UploadFile, Depends, HTTPException, Query, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
import os
import logging
from groq import Groq
import json
import requests
import uuid
from typing import List, Set
import shutil
from datetime import datetime
from pydub import AudioSegment 

# Import custom modules
from file_processing import process_jd_file, process_resume_file, extract_text_from_file
from question_generation import generate_interview_questions, modify_questions, analyze_response

# Import models
from models import (
    Base, JobDescription, CandidateResume, InterviewSession,
    InterviewQuestion, CandidateResponse, init_db
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="AI Recruiter API")

@app.get("/")
async def root():
    return {"message": "Welcome to the AI Recruiter API"}

# Update CORS settings for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only. In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialize database
init_db(engine)

# API Key Verification
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set in environment variables")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in environment variables")
if not ELEVENLABS_API_KEY:
    raise ValueError("ELEVENLABS_API_KEY not found in environment variables")

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

# Constants for file validation
ALLOWED_DOCUMENT_TYPES: Set[str] = {'.pdf', '.docx', '.doc', '.txt', '.rtf'}
MAX_FILE_SIZE: int = 5 * 1024 * 1024  # 5 MB in bytes

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def validate_file(file: UploadFile, allowed_types: Set[str], max_size: int) -> None:
    """
    Validate file type and size
    """
    # Check file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types are: {', '.join(allowed_types)}"
        )
    
    # Check content type
    if not file.content_type.startswith(('application/', 'text/')):
        raise HTTPException(
            status_code=400,
            detail="Invalid content type. Must be a document file."
        )
    
    # Check file size (requires reading the file into memory)
    file_size = 0
    try:
        file_size = len(file.file.read())
        file.file.seek(0)  # Reset file pointer to beginning
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error reading file: {str(e)}"
        )
    
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size allowed is {max_size/1024/1024:.1f}MB"
        )

@app.post("/upload/jd")
async def upload_jd(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload and process a job description document with enhanced data extraction
    """
    try:
        # Validate file before processing
        validate_file(file, ALLOWED_DOCUMENT_TYPES, MAX_FILE_SIZE)
        
        # Process file content with enhanced extraction
        processed_data = await process_jd_file(file)
        jd_id = str(uuid.uuid4())
        
        # Create job description record with extracted information
        jd = JobDescription(
            id=jd_id,
            content=processed_data["content"],
            file_name=file.filename,
            file_type=os.path.splitext(file.filename)[1].lower(),
            title=processed_data["title"],
            company=processed_data["company"],
            requirements=processed_data.get("metadata", {})
        )
        
        db.add(jd)
        db.commit()
        
        return {
            "jd_id": jd_id,
            "title": processed_data["title"],
            "company": processed_data["company"],
            "file_name": file.filename,
            "file_size": len(processed_data["content"]),
            "message": "Job description uploaded successfully"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Error uploading JD: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing job description: {str(e)}"
        )
    finally:
        await file.close()

@app.post("/upload/resume")
async def upload_resume(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload and process a resume with enhanced candidate information extraction
    """
    try:
        # Validate file before processing
        validate_file(file, ALLOWED_DOCUMENT_TYPES, MAX_FILE_SIZE)
        
        # Process file content with enhanced extraction
        processed_data = await process_resume_file(file)
        resume_id = str(uuid.uuid4())
        
        # Create resume record with extracted information
        resume = CandidateResume(
            id=resume_id,
            content=processed_data["content"],
            file_name=file.filename,
            file_type=os.path.splitext(file.filename)[1].lower(),
            candidate_name=processed_data["candidate_name"],
            email=processed_data["email"],
            skills=processed_data.get("skills", []),
            experience=processed_data.get("experience", [])
        )
        
        db.add(resume)
        db.commit()
        
        return {
            "resume_id": resume_id,
            "candidate_name": processed_data["candidate_name"],
            "email": processed_data["email"],
            "file_name": file.filename,
            "file_size": len(processed_data["content"]),
            "message": "Resume uploaded successfully"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Error uploading resume: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing resume: {str(e)}"
        )
    finally:
        await file.close()

# Interview Management Endpoints
@app.post("/interview/create")
async def create_interview_session(
    jd_id: str = Form(...),
    resume_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Create interview session with 5 questions
    """
    try:
        logger.info(f"Creating interview session with JD ID: {jd_id} and Resume ID: {resume_id}")
        
        # Verify JD and Resume exist
        job_description = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
        candidate_resume = db.query(CandidateResume).filter(CandidateResume.id == resume_id).first()
        
        if not job_description:
            logger.error(f"Job Description not found with ID: {jd_id}")
            raise HTTPException(status_code=404, detail="Job Description not found")
            
        if not candidate_resume:
            logger.error(f"Resume not found with ID: {resume_id}")
            raise HTTPException(status_code=404, detail="Resume not found")
        
        # Create interview session
        session_id = str(uuid.uuid4())
        interview_session = InterviewSession(
            id=session_id,
            jd_id=jd_id,
            resume_id=resume_id,
            status="draft",  # Initial status is draft until questions are confirmed
            scheduled_datetime=datetime.utcnow()
        )
        db.add(interview_session)
        db.flush()
        
        # Generate exactly 5 questions
        generated_questions = await generate_interview_questions(
            job_description.content,
            candidate_resume.content
        )
        
        # Add questions
        questions = []
        for idx, question_data in enumerate(generated_questions, 1):
            question = InterviewQuestion(
                id=str(uuid.uuid4()),
                interview_session_id=session_id,
                question_text=question_data["question_text"],
                question_type=question_data.get("question_type", "general"),
                category=question_data.get("assesses", "general"),
                sequence_number=idx,
                is_generated=True,
                expected_answer_keywords=question_data.get("key_points", ""),
                scoring_rubric={"key_points": question_data.get("key_points", [])}
            )
            db.add(question)
            
            questions.append({
                "id": question.id,
                "question_text": question.question_text,
                "question_type": question.question_type,
                "category": question.category,
                "sequence_number": idx
            })
        
        db.commit()
        logger.info(f"Successfully created interview session with ID: {session_id}")
        
        return {
            "interview_id": session_id,
            "status": "draft",
            "candidate_name": candidate_resume.candidate_name,
            "job_title": job_description.title,
            "questions": questions,
            "message": "Interview session created with generated questions"
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating interview: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/interview/{interview_id}/details")
async def get_interview_details(interview_id: str, db: Session = Depends(get_db)):
    """
    Get comprehensive interview details including questions, responses, and analysis
    """
    try:
        # Get interview session with related data
        interview_session = db.query(InterviewSession).filter(
            InterviewSession.id == interview_id
        ).first()
        
        if not interview_session:
            raise HTTPException(status_code=404, detail="Interview session not found")
        
        # Prepare questions with responses and analysis
        questions_with_responses = []
        total_questions = len(interview_session.questions)
        answered_questions = 0
        
        for question in interview_session.questions:
            # Get responses for this question
            responses = [
                {
                    "response_text": response.response_text,
                    "score": response.score,
                    "timestamp": response.timestamp.isoformat() if response.timestamp else None,
                    "ai_feedback": response.ai_feedback,
                    "technical_accuracy": response.technical_accuracy,
                    "clarity_score": response.clarity_score,
                    "improvement_suggestions": response.improvement_suggestions,
                    "keywords_matched": response.keywords_matched
                }
                for response in question.responses
            ]
            
            if responses:
                answered_questions += 1
            
            questions_with_responses.append({
                "id": question.id,
                "question_text": question.question_text,
                "question_type": question.question_type,
                "category": question.category,
                "sequence_number": question.sequence_number,
                "is_modified": question.is_modified,
                "original_question": question.original_question if question.is_modified else None,
                "expected_answer_keywords": question.expected_answer_keywords,
                "scoring_rubric": question.scoring_rubric,
                "responses": responses
            })
        
        # Calculate interview progress
        progress = {
            "total_questions": total_questions,
            "answered_questions": answered_questions,
            "completion_percentage": (answered_questions / total_questions * 100) if total_questions > 0 else 0
        }
        
        # Calculate average scores
        scores = {
            "overall_score": interview_session.overall_score,
            "technical_score": interview_session.technical_score,
            "communication_score": interview_session.communication_score,
            "cultural_fit_score": interview_session.cultural_fit_score,
            "score_breakdown": {
                "technical_proficiency": interview_session.technical_score,
                "communication_skills": interview_session.communication_score,
                "problem_solving": sum(q.responses[0].score for q in interview_session.questions if q.responses and q.question_type == "technical") / total_questions if total_questions > 0 else 0,
                "experience_relevance": sum(q.responses[0].score for q in interview_session.questions if q.responses and q.question_type == "experience") / total_questions if total_questions > 0 else 0
            }
        }
        
        # Get timing information
        timing = {
            "created_at": interview_session.created_at.isoformat() if interview_session.created_at else None,
            "scheduled_datetime": interview_session.scheduled_datetime.isoformat() if interview_session.scheduled_datetime else None,
            "actual_start_time": interview_session.actual_start_time.isoformat() if interview_session.actual_start_time else None,
            "actual_end_time": interview_session.actual_end_time.isoformat() if interview_session.actual_end_time else None,
            "duration_minutes": (interview_session.actual_end_time - interview_session.actual_start_time).total_seconds() / 60 if interview_session.actual_end_time and interview_session.actual_start_time else None
        }
        
        return {
            "interview_id": interview_session.id,
            "status": interview_session.status,
            "progress": progress,
            "timing": timing,
            "job_description": {
                "id": interview_session.job_description.id,
                "title": interview_session.job_description.title,
                "company": interview_session.job_description.company,
                "content": interview_session.job_description.content,
                "requirements": interview_session.job_description.requirements
            },
            "candidate": {
                "id": interview_session.candidate_resume.id,
                "name": interview_session.candidate_resume.candidate_name,
                "email": interview_session.candidate_resume.email,
                "skills": interview_session.candidate_resume.skills,
                "experience": interview_session.candidate_resume.experience
            },
            "scoring": scores,
            "questions": questions_with_responses,
            "interview_summary": {
                "strengths": [
                    response.ai_feedback 
                    for question in interview_session.questions 
                    for response in question.responses 
                    if response.score >= 8
                ],
                "areas_for_improvement": [
                    response.improvement_suggestions
                    for question in interview_session.questions
                    for response in question.responses
                    if response.score < 6
                ],
                "overall_recommendation": "Recommended for next round" if interview_session.overall_score >= 7 else "Consider other candidates" if interview_session.overall_score < 5 else "Requires further evaluation"
            }
        }
        
    except SQLAlchemyError as e:
        logger.error(f"Database error getting interview details: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Database error occurred while fetching interview details"
        )
    except Exception as e:
        logger.error(f"Error getting interview details: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving interview details: {str(e)}"
        )


@app.put("/interview/questions/{question_id}")
async def update_interview_question(
    question_id: str,
    question_update: dict,
    db: Session = Depends(get_db)
):
    """
    Update a specific interview question
    """
    try:
        question = db.query(InterviewQuestion).filter(
            InterviewQuestion.id == question_id
        ).first()
        
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")
        
        # Update question fields
        if "question_text" in question_update:
            question.question_text = question_update["question_text"]
            question.is_modified = True
            question.modified_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "id": question.id,
            "question_text": question.question_text,
            "question_type": question.question_type,
            "category": question.category,
            "sequence_number": question.sequence_number
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating question: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/interview/{interview_id}/confirm")
async def confirm_interview_questions(
    interview_id: str,
    db: Session = Depends(get_db)
):
    """
    Confirm the interview questions and mark the session as ready
    """
    try:
        logger.info(f"Confirming questions for interview: {interview_id}")
        
        interview = db.query(InterviewSession).filter(
            InterviewSession.id == interview_id.strip()
        ).first()
        
        if not interview:
            raise HTTPException(status_code=404, detail="Interview session not found")
        
        # Verify we have exactly 5 questions
        questions = db.query(InterviewQuestion).filter(
            InterviewQuestion.interview_session_id == interview_id
        ).all()
        
        if len(questions) != 5:
            raise HTTPException(
                status_code=400,
                detail=f"Interview must have exactly 5 questions. Current count: {len(questions)}"
            )
        
        # Update interview status to ready
        interview.status = "ready"
        interview.updated_at = datetime.utcnow()
        
        # Log the change
        logger.info(f"Setting interview {interview_id} status to ready")
        
        db.commit()
        
        return {
            "interview_id": interview_id,
            "status": "ready",
            "message": "Interview questions confirmed and ready for use",
            "total_questions": len(questions)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error confirming interview: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/interview/search")
async def search_interviews(
    candidate_name: str = None,
    company: str = None,
    status: str = None,
    date_from: datetime = None,
    date_to: datetime = None,
    db: Session = Depends(get_db)
):
    query = db.query(InterviewSession)
    
    if candidate_name:
        query = query.join(CandidateResume).filter(
            CandidateResume.candidate_name.ilike(f"%{candidate_name}%")
        )
    
    if company:
        query = query.join(JobDescription).filter(
            JobDescription.company.ilike(f"%{company}%")
        )
    
    if status:
        query = query.filter(InterviewSession.status == status)
    
    if date_from:
        query = query.filter(InterviewSession.created_at >= date_from)
    
    if date_to:
        query = query.filter(InterviewSession.created_at <= date_to)
    
    interviews = query.all()
    
    return [
        {
            "interview_id": interview.id,
            "candidate_name": interview.candidate_resume.candidate_name,
            "company": interview.job_description.company,
            "job_title": interview.job_description.title,
            "status": interview.status,
            "created_at": interview.created_at,
            "overall_score": interview.overall_score
        }
        for interview in interviews
    ]

# Modified talk-video endpoint to use interview session
@app.post("/talk-video")
async def process_video(
    file: UploadFile = File(...),
    interview_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Process audio from video interview and handle interview flow
    """
    try:
        # Get interview session
        interview_session = db.query(InterviewSession).filter(
            InterviewSession.id == interview_id
        ).first()
        
        if not interview_session:
            raise HTTPException(status_code=404, detail="Interview session not found")

        # Validate file size
        file_size = 0
        content = await file.read()
        file_size = len(content)
        await file.seek(0)  # Reset file pointer
        
        if file_size > 1024 * 1024 * 5:  # 5MB limit
            raise HTTPException(
                status_code=400,
                detail="File too large. Please limit recordings to 5MB or less."
            )
        
        # Get current question count
        answered_questions = db.query(CandidateResponse).filter(
            CandidateResponse.interview_session_id == interview_session.id
        ).count()
        
        # Get all questions for this interview
        all_questions = db.query(InterviewQuestion).filter(
            InterviewQuestion.interview_session_id == interview_session.id
        ).order_by(InterviewQuestion.sequence_number).all()
        
        if not all_questions:
            raise HTTPException(status_code=400, detail="No questions found for this interview")
        
        # Check if interview is already complete
        if interview_session.status == "completed":
            raise HTTPException(status_code=400, detail="Interview is already completed")
        
        # Update interview status if just starting
        if interview_session.status != "in_progress":
            interview_session.status = "in_progress"
            interview_session.actual_start_time = datetime.utcnow()
        
        # Save uploaded audio file temporarily
        temp_audio_path = f"temp_{uuid.uuid4()}.webm"
        try:
            # Save the original WebM file
            with open(temp_audio_path, "wb") as buffer:
                await file.seek(0)  # Ensure we're at the start of the file
                buffer.write(content)
            
            # Convert audio to MP3 format
            from pydub import AudioSegment
            audio = AudioSegment.from_file(temp_audio_path, format="webm")
            temp_mp3_path = f"temp_{uuid.uuid4()}.mp3"
            audio.export(temp_mp3_path, format="mp3")
            
            # Transcribe audio using MP3 file
            # Transcribe audio using OpenAI Whisper API
            user_message = await transcribe_audio(file)
            logger.info(f"Transcribed message: {user_message[:100]}...")
                
        except Exception as e:
            logger.error(f"Error processing audio: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
            
        finally:
            # Clean up temporary files
            try:
                if os.path.exists(temp_audio_path):
                    os.remove(temp_audio_path)
                    logger.info("Temporary WebM file removed")
                if os.path.exists(temp_mp3_path):
                    os.remove(temp_mp3_path)
                    logger.info("Temporary MP3 file removed")
            except Exception as e:
                logger.error(f"Error cleaning up temporary files: {str(e)}")
        
        # Get current question
        current_question = next(
            (q for q in all_questions if q.sequence_number == answered_questions + 1),
            None
        )
        
        if current_question:
            # Create candidate response
            response = CandidateResponse(
                interview_session_id=interview_session.id,
                question_id=current_question.id,
                response_text=user_message,
                response_audio_url="",  # You could store the audio file if needed
                timestamp=datetime.utcnow()
            )
            db.add(response)
            
            # Analyze response
            analysis = await analyze_response(current_question.question_text, user_message)
            
            # Update response with analysis
            response.score = analysis.get("relevance_score", 0)
            response.technical_accuracy = analysis.get("technical_score", 0)
            response.clarity_score = analysis.get("clarity_score", 0)
            response.ai_feedback = analysis.get("feedback", "")
            response.improvement_suggestions = analysis.get("improvement_areas", "")
            
            # Check if this was the last question
            if answered_questions + 1 >= len(all_questions):
                interview_session.status = "completed"
                interview_session.actual_end_time = datetime.utcnow()
                
                # Calculate final scores
                responses = db.query(CandidateResponse).filter(
                    CandidateResponse.interview_session_id == interview_session.id
                ).all()
                
                interview_session.technical_score = sum(r.technical_accuracy or 0 for r in responses) / len(responses)
                interview_session.communication_score = sum(r.clarity_score or 0 for r in responses) / len(responses)
                interview_session.overall_score = (interview_session.technical_score + interview_session.communication_score) / 2
                
                ai_response = "Thank you for completing the interview. Your responses have been recorded. We will review them and get back to you soon. Have a great day!"
            else:
                # Get next question
                next_question = next(
                    (q for q in all_questions if q.sequence_number == answered_questions + 2),
                    None
                )
                if next_question:
                    ai_response = f"Thank you for your response. Here's your next question: {next_question.question_text}"
                else:
                    ai_response = "Thank you for your response."
        else:
            # If no current question (introduction phase)
            ai_response = (
                "Thank you for introducing yourself. Let's begin the interview. "
                f"Here's your first question: {all_questions[0].question_text}"
            )
        
        db.commit()
        logger.info(f"Processing completed, generating audio response: {ai_response[:100]}...")
        
        # Generate audio response
        audio_output = text_to_speech(ai_response)
        
        # Return audio response with headers
        headers = {
            "X-Interview-Status": interview_session.status,
            "X-Total-Questions": str(len(all_questions)),
            "X-Answered-Questions": str(answered_questions + 1),
            "Access-Control-Expose-Headers": "X-Interview-Status, X-Total-Questions, X-Answered-Questions"
        }
        
        return StreamingResponse(
            iter([audio_output]),
            media_type="audio/mpeg",
            headers=headers
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/interview/check-completed")
async def check_completed_interviews(db: Session = Depends(get_db)):
    """
    Check if there are any completed interviews in the system
    """
    try:
        completed_count = db.query(InterviewSession).filter(
            InterviewSession.status == "completed"
        ).count()
        
        return {
            "has_completed_interviews": completed_count > 0
        }
    except Exception as e:
        logger.error(f"Error checking completed interviews: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Failed to check completed interviews"
        )

@app.get("/interview/validate/{interview_id}")
async def validate_interview_id(interview_id: str, db: Session = Depends(get_db)):
    """
    Validate if an interview ID exists and is ready for interview
    """
    try:
        # Log the received ID for debugging
        logger.info(f"Validating interview ID: {interview_id}")
        
        # Get interview session
        interview = db.query(InterviewSession).filter(
            InterviewSession.id == interview_id.strip()
        ).first()
        
        logger.info(f"Found interview: {interview is not None}")
        
        if not interview:
            logger.warning(f"Interview not found with ID: {interview_id}")
            return JSONResponse(
                status_code=404,
                content={
                    "valid": False,
                    "message": "Interview ID not found"
                }
            )
        
        logger.info(f"Interview status: {interview.status}")
        
        # Check if interview is in ready state
        if interview.status != "ready":
            logger.warning(f"Interview {interview_id} is in {interview.status} state, not ready")
            return JSONResponse(
                status_code=400,
                content={
                    "valid": False,
                    "message": f"Interview is not ready (current status: {interview.status})"
                }
            )
        
        # Get questions count
        questions = db.query(InterviewQuestion).filter(
            InterviewQuestion.interview_session_id == interview_id
        ).all()
        
        logger.info(f"Found {len(questions)} questions")
        
        if not questions or len(questions) != 5:
            logger.warning(f"Interview {interview_id} has {len(questions)} questions, expected 5")
            return JSONResponse(
                status_code=400,
                content={
                    "valid": False,
                    "message": "Interview is not properly set up (missing questions)"
                }
            )
        
        return {
            "valid": True,
            "message": "Interview ID is valid and ready to start",
            "total_questions": len(questions)
        }
        
    except Exception as e:
        logger.error(f"Error validating interview ID: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate interview ID: {str(e)}"
        )

async def transcribe_audio(file):
    """
    Transcribe audio using OpenAI's Whisper API with plain text response handling.
    """
    temp_file_path = None
    try:
        file_content = await file.read()
        temp_file_path = f"temp_{uuid.uuid4()}.mp3"

        # Save the audio file temporarily
        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(file_content)

        # Prepare the request for OpenAI Whisper API
        url = "https://api.openai.com/v1/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        files = {
            "file": (temp_file_path, open(temp_file_path, "rb"), "audio/mpeg")
        }
        data = {
            "model": "whisper-1",
            "response_format": "text",  # Request plain text response
            "language": "en"
        }

        # Make the request to OpenAI API
        logger.info("Sending request to OpenAI Whisper API...")
        response = requests.post(url, headers=headers, files=files, data=data, verify=False)

        logger.info(f"OpenAI API response status: {response.status_code}")
        logger.debug(f"OpenAI API response content: {response.text}")

        # Check if the response is successful
        if response.status_code == 200:
            transcription = response.text.strip()  # Handle plain text response
            if not transcription:
                raise ValueError("Transcription is empty.")
            logger.info("Audio transcription successful")
            return transcription
        else:
            # Handle specific HTTP errors
            if response.status_code == 401:
                raise HTTPException(status_code=401, detail="Unauthorized: Check your OpenAI API key")
            elif response.status_code == 429:
                raise HTTPException(status_code=429, detail="Rate limit exceeded: Please try again later")
            elif response.status_code == 500:
                raise HTTPException(status_code=500, detail="Server error: OpenAI API is currently unavailable")
            else:
                raise HTTPException(status_code=response.status_code, detail=f"Transcription request failed: {response.text}")

    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error transcribing audio")
    finally:
        # Clean up the temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.info("Temporary audio file removed")

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

def get_chat_response(session_id: str, user_message: str, job_context: str):
    """
    Get chat response from Groq API with enhanced error handling
    
    Args:
        session_id (str): Unique session identifier
        user_message (str): User's message to process
        job_context (str): Job description context
    
    Returns:
        tuple: (ai_response, ai_question)
    
    Raises:
        HTTPException: For various error conditions with appropriate status codes
    """
    try:
        # Load previous messages
        try:
            messages = load_messages(session_id, job_context)
            messages.append({"role": "user", "content": user_message})
        except Exception as e:
            logger.error(f"Error loading messages for session {session_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to load conversation history"
            )

        # Send request to Groq API
        try:
            logger.info(f"Sending request to Groq API for session {session_id}")
            llm_response = client.chat.completions.create(
                model="llama3-70b-8192",
                messages=messages,
                temperature=0.7,  # Add temperature for consistent responses
                max_tokens=2000   # Limit response length
            )
        except Exception as e:
            logger.error(f"Groq API error for session {session_id}: {str(e)}")
            raise HTTPException(
                status_code=502,
                detail="Failed to get response from AI service"
            )

        # Process API response
        try:
            ai_response = llm_response.choices[0].message.content
            logger.info(f"Received response from Groq API for session {session_id}: {ai_response[:100]}...")
        except (AttributeError, IndexError) as e:
            logger.error(f"Error processing Groq API response: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Invalid response format from AI service"
            )

        # Extract question
        try:
            ai_question = extract_question(ai_response)
            logger.info(f"Extracted question for session {session_id}: {ai_question}")
        except Exception as e:
            logger.error(f"Error extracting question: {str(e)}")
            ai_question = "Could not generate a follow-up question. Please continue the conversation."

        # Save conversation history
        try:
            messages.append({"role": "assistant", "content": ai_response})
            save_messages(session_id, messages)
        except Exception as e:
            logger.error(f"Error saving messages for session {session_id}: {str(e)}")
            # Don't raise an exception here as we still want to return the response
            # Just log the error

        return ai_response, ai_question

    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        # Catch any unexpected errors
        logger.error(f"Unexpected error in get_chat_response: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing your request"
        )

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