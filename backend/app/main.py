# Standard library imports
import json
import logging
import os
import shutil
import uuid
from datetime import datetime
from typing import List, Set, Dict, Any

# Third-party imports
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, Depends, HTTPException, Query, File, Form, status, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from pydub import AudioSegment
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional

# Local application imports
from app.database import engine, get_db, Base, SessionLocal  # Remove SessionLocal as it's in database.py
from app.models.auth import User, UserRole, UserSession
from app.models.core import (
    JobDescription,
    CandidateResume,
    InterviewSession,
    InterviewQuestion,
    CandidateResponse
)
from app.utils.auth import verify_token, get_current_user
from app.middleware.auth import require_auth, require_recruiter, require_candidate
from app.routes.auth import router as auth_router
from app.utils.file_processing import process_jd_file, process_resume_file, extract_text_from_file
from app.utils.question_generation import generate_interview_questions, modify_questions, analyze_response

def init_database():
    """Initialize database tables"""
    try:
        logger.info("Dropping all existing tables...")
        Base.metadata.drop_all(bind=engine)
        logger.info("Creating new tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Logs to console
        logging.FileHandler('app.log')  # Logs to file
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Environment variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# Validate required environment variables
required_env_vars = {
    "GROQ_API_KEY": GROQ_API_KEY,
    "ELEVENLABS_API_KEY": ELEVENLABS_API_KEY,
    "JWT_SECRET_KEY": JWT_SECRET_KEY,
    "GOOGLE_CLIENT_ID": GOOGLE_CLIENT_ID,
    "GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET
}

for var_name, var_value in required_env_vars.items():
    if not var_value:
        raise ValueError(f"{var_name} not found in environment variables")

# Get frontend URL from environment
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Initialize FastAPI app
app = FastAPI(title="AI Recruiter API")

# CORS configuration
origins = [
    FRONTEND_URL,
    "https://accounts.google.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "Authorization"],
    expose_headers=["*"],
    max_age=3600
)

# Error handling middleware
@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    try:
        # Log request details
        logger.info(f"Incoming request: {request.method} {request.url}")
        logger.debug(f"Request headers: {request.headers}")
        
        # Process request
        response = await call_next(request)
        
        # Log response status
        logger.info(f"Response status: {response.status_code}")
        return response
        
    except SQLAlchemyError as e:
        # Handle database errors
        logger.error(f"Database error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "A database error occurred",
                "type": "database_error"
            }
        )
        
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unhandled error: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An unexpected error occurred. Please try again later.",
                "type": "internal_server_error"
            }
        )

# Request logging middleware
@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    start_time = datetime.utcnow()
    
    # Generate request ID for tracking
    request_id = str(uuid.uuid4())
    logger.info(f"Request {request_id} started: {request.method} {request.url}")
    
    try:
        # Process request and capture timing
        response = await call_next(request)
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        # Log response details
        logger.info(
            f"Request {request_id} completed: {response.status_code} "
            f"Duration: {duration:.3f}s"
        )
        
        # Add request ID and timing headers to response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        return response
        
    except Exception as e:
        # Log error details
        logger.error(
            f"Request {request_id} failed: {str(e)}",
            exc_info=True
        )
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        # Return error response with request ID
        error_response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An unexpected error occurred",
                "type": "internal_server_error",
                "request_id": request_id
            }
        )
        error_response.headers["X-Request-ID"] = request_id
        error_response.headers["X-Response-Time"] = f"{duration:.3f}s"
        return error_response

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint to verify API is running"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

# Initialize database
Base.metadata.create_all(bind=engine)

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

# Constants
ALLOWED_DOCUMENT_TYPES: Set[str] = {'.pdf', '.docx', '.doc', '.txt', '.rtf'}
MAX_FILE_SIZE: int = 5 * 1024 * 1024  # 5 MB in bytes

# Include routers
app.include_router(auth_router)

print("Current CORS origins:", origins)
print("API routes:", [route.path for route in app.routes])

def validate_file(file: UploadFile, allowed_types: Set[str], max_size: int) -> None:
    """
    Validate file type and size with enhanced error handling and logging
    
    Args:
        file: UploadFile object to validate
        allowed_types: Set of allowed file extensions
        max_size: Maximum file size in bytes
        
    Raises:
        HTTPException: If validation fails
    """
    try:
        logger.info(f"Validating file: {file.filename}")
        
        # Check if file is empty
        if not file.filename:
            logger.error("Empty file name")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )
            
        # Check file extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_types:
            logger.error(f"Invalid file type: {file_ext}. Allowed types: {allowed_types}")
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Invalid file type. Allowed types are: {', '.join(allowed_types)}"
            )
        
        # Check content type
        if not file.content_type:
            logger.error("No content type provided")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not determine file type"
            )
            
        if not file.content_type.startswith(('application/', 'text/')):
            logger.error(f"Invalid content type: {file.content_type}")
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Invalid content type. Must be a document file."
            )
        
        # Check file size
        try:
            file.file.seek(0, 2)  # Seek to end
            file_size = file.file.tell()
            file.file.seek(0)  # Reset to beginning
            
            logger.info(f"File size: {file_size/1024/1024:.2f}MB")
            
            if file_size > max_size:
                logger.error(f"File too large: {file_size/1024/1024:.2f}MB > {max_size/1024/1024:.2f}MB")
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large. Maximum size allowed is {max_size/1024/1024:.1f}MB"
                )
                
            if file_size == 0:
                logger.error("Empty file")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File is empty"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error checking file size: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error reading file: {str(e)}"
            )
            
        logger.info("File validation successful")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in validate_file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while validating the file"
        )

@app.post("/upload/jd")
async def upload_jd(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        validate_file(file, ALLOWED_DOCUMENT_TYPES, MAX_FILE_SIZE)
        processed_data = await process_jd_file(file)
        jd_id = str(uuid.uuid4())
        
        jd = JobDescription(
            id=jd_id,
            content=processed_data["content"],
            file_name=file.filename,
            file_type=os.path.splitext(file.filename)[1].lower(),
            title=processed_data["title"],
            company=processed_data["company"]
        )
        
        db.add(jd)
        db.commit()
        
        return {
            "jd_id": jd_id,
            "title": processed_data["title"],
            "company": processed_data["company"],
            "file_name": file.filename,
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
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """
    Upload and process a resume with authentication
    """
    try:
        # Handle user email for logging
        user_email = getattr(current_user, 'email', 'unknown@email.com') if isinstance(current_user, User) else current_user.get('email', 'unknown@email.com')
        logger.info(f"Received resume upload request from user: {user_email}")
        logger.info(f"File name: {file.filename}")
        logger.info(f"Content type: {file.content_type}")
        
        # Validate file before processing
        validate_file(file, ALLOWED_DOCUMENT_TYPES, MAX_FILE_SIZE)
        
        try:
            # Process file content
            processed_data = await process_resume_file(file)
            logger.info("Resume file processed successfully")
            
            resume_id = str(uuid.uuid4())
            
            # Create resume record with fallback values
            resume = CandidateResume(
                id=resume_id,
                content=processed_data.get("content", ""),
                file_name=file.filename,
                file_type=os.path.splitext(file.filename)[1].lower(),
                candidate_name=processed_data.get("candidate_name", "Unknown Candidate"),
                email=processed_data.get("email", user_email),  # Fallback to user's email
                skills=processed_data.get("skills", []),
                experience=processed_data.get("experience", []),
                uploaded_by=str(getattr(current_user, 'id', None)) if isinstance(current_user, User) else str(current_user.get('id'))
            )
            
            db.add(resume)
            db.commit()
            logger.info(f"Resume record created with ID: {resume_id}")
            
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "resume_id": resume_id,
                    "candidate_name": resume.candidate_name,
                    "email": resume.email,
                    "file_name": resume.file_name,
                    "message": "Resume uploaded successfully"
                }
            )
            
        except HTTPException as he:
            logger.error(f"HTTP Exception processing resume: {str(he)}")
            raise he
        except Exception as e:
            logger.error(f"Error processing resume: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing resume: {str(e)}"
            )
            
    except HTTPException as he:
        logger.error(f"HTTP Exception in upload_resume: {str(he)}")
        db.rollback()
        raise he
    except Exception as e:
        logger.error(f"Error in upload_resume: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    finally:
        await file.close()

# Interview Management Endpoints
@app.post("/interview/create")
async def create_interview(
    jd_id: str = Form(...),
    resume_id: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)  # Add this to get the current user
):
    try:
        job_description = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
        candidate_resume = db.query(CandidateResume).filter(CandidateResume.id == resume_id).first()
        
        if not job_description or not candidate_resume:
            raise HTTPException(status_code=404, detail="Job Description or Resume not found")
        
        session_id = str(uuid.uuid4())
        interview_session = InterviewSession(
            id=session_id,
            jd_id=jd_id,
            resume_id=resume_id,
            recruiter_id=str(current_user.id),  # Add the recruiter_id
            status="draft",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(interview_session)
        db.flush()
        
        generated_questions = await generate_interview_questions(
            job_description.content,
            candidate_resume.content
        )
        
        questions = []
        for idx, question_data in enumerate(generated_questions, 1):
            question = InterviewQuestion(
                id=str(uuid.uuid4()),
                interview_session_id=session_id,
                question_text=question_data["question_text"],
                question_type=question_data.get("question_type", "general"),
                category=question_data.get("assesses", "general"),
                sequence_number=idx,
                is_generated=True
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
        
        return {
            "interview_id": session_id,
            "questions": questions,
            "status": "draft"
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating interview: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/interview/{interview_id}/details")
async def get_interview_details(
    interview_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)  # Both roles can view details
):
    """
    Get interview details with role-based access control
    """
    try:
        # Get interview session
        interview_session = db.query(InterviewSession).filter(
            InterviewSession.id == interview_id
        ).first()
        
        if not interview_session:
            raise HTTPException(status_code=404, detail="Interview session not found")
        
        # Check permissions
        if current_user.role == UserRole.CANDIDATE:
            # Candidates can only view their own interviews
            candidate_resume = db.query(CandidateResume).filter(
                CandidateResume.id == interview_session.resume_id
            ).first()
            if candidate_resume.email != current_user.email:
                raise HTTPException(
                    status_code=403,
                    detail="Not authorized to view this interview"
                )
        
        # Get all related data
        questions_with_responses = []
        total_questions = len(interview_session.questions)
        answered_questions = 0
        
        for question in interview_session.questions:
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
                "responses": responses
            })
        
        # Calculate progress
        progress = {
            "total_questions": total_questions,
            "answered_questions": answered_questions,
            "completion_percentage": (answered_questions / total_questions * 100) if total_questions > 0 else 0
        }
        
        return {
            "interview_id": interview_session.id,
            "status": interview_session.status,
            "progress": progress,
            "job_description": {
                "id": interview_session.job_description.id,
                "title": interview_session.job_description.title,
                "company": interview_session.job_description.company
            },
            "candidate": {
                "id": interview_session.candidate_resume.id,
                "name": interview_session.candidate_resume.candidate_name,
                "email": interview_session.candidate_resume.email
            },
            "questions": questions_with_responses,
            "created_by": interview_session.recruiter_id,
            "created_at": interview_session.created_at.isoformat(),
            "overall_score": interview_session.overall_score
        }
        
    except HTTPException:
        raise
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter)  # Only recruiters can confirm questions
):
    """
    Confirm interview questions with authentication
    """
    try:
        interview = db.query(InterviewSession).filter(
            InterviewSession.id == interview_id
        ).first()
        
        if not interview:
            raise HTTPException(status_code=404, detail="Interview session not found")
        
        # Verify ownership
        if interview.recruiter_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to modify this interview"
            )
        
        # Update status
        interview.status = "ready"
        interview.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "interview_id": interview_id,
            "status": "ready",
            "message": "Interview questions confirmed and ready for use"
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
    temp_audio_path = None
    temp_mp3_path = None
    
    try:
        # Get interview session
        interview_session = db.query(InterviewSession).filter(
            InterviewSession.id == interview_id
        ).first()
        
        if not interview_session:
            raise HTTPException(status_code=404, detail="Interview session not found")

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
            db.commit()

        # Validate file size
        content = await file.read()
        file_size = len(content)
        
        if file_size > 5 * 1024 * 1024:  # 5MB limit
            raise HTTPException(
                status_code=400,
                detail="File too large. Please limit recordings to 5MB or less."
            )

        # Process audio file
        try:
            # Generate temporary file paths
            temp_audio_path = f"temp_{uuid.uuid4()}.webm"
            temp_mp3_path = f"temp_{uuid.uuid4()}.mp3"
            
            # Save the original WebM file
            with open(temp_audio_path, "wb") as buffer:
                buffer.write(content)
            
            # Convert audio to MP3 format
            audio = AudioSegment.from_file(temp_audio_path, format="webm")
            audio.export(temp_mp3_path, format="mp3")
            
            # Transcribe audio using MP3 file
            with open(temp_mp3_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    file=(temp_mp3_path, audio_file, 'audio/mp3'),
                    model="distil-whisper-large-v3-en",
                    response_format="text"
                )
                user_message = transcription
                logger.info(f"Transcribed message: {user_message[:100]}...")

        except Exception as e:
            logger.error(f"Error processing audio: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing audio: {str(e)}")
            
        finally:
            # Clean up temporary files
            if temp_audio_path and os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
                logger.info("Temporary WebM file removed")
            if temp_mp3_path and os.path.exists(temp_mp3_path):
                os.remove(temp_mp3_path)
                logger.info("Temporary MP3 file removed")

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
                response_audio_url="",
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
                
                technical_scores = [r.technical_accuracy or 0 for r in responses]
                clarity_scores = [r.clarity_score or 0 for r in responses]
                
                interview_session.technical_score = sum(technical_scores) / len(responses)
                interview_session.communication_score = sum(clarity_scores) / len(responses)
                interview_session.overall_score = (
                    interview_session.technical_score + interview_session.communication_score
                ) / 2
                
                ai_response = "Thank you for completing the interview. Your responses have been recorded and will be reviewed. Have a great day!"
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

            db.commit()
            logger.info(f"Processing completed, generating audio response: {ai_response[:100]}...")

            # Generate audio response
            try:
                audio_output = text_to_speech(ai_response)
            except Exception as e:
                logger.error(f"Error generating audio response: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail="Error generating audio response"
                )
            
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

        else:
            # Handle case when no current question is found
            raise HTTPException(
                status_code=400,
                detail="Invalid question sequence"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

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
        logger.info(f"Validating interview ID: {interview_id}")
        
        # Get interview session with questions
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
        
        # Get questions count and verify all 5 questions exist
        questions = db.query(InterviewQuestion).filter(
            InterviewQuestion.interview_session_id == interview_id
        ).order_by(InterviewQuestion.sequence_number).all()
        
        logger.info(f"Found {len(questions)} questions")
        
        if not questions:
            logger.warning(f"No questions found for interview {interview_id}")
            return JSONResponse(
                status_code=400,
                content={
                    "valid": False,
                    "message": "Interview is not properly set up (missing questions)"
                }
            )
            
        if len(questions) != 5:
            logger.warning(f"Interview {interview_id} has {len(questions)} questions, expected 5")
            return JSONResponse(
                status_code=400,
                content={
                    "valid": False,
                    "message": f"Interview must have exactly 5 questions (found {len(questions)})"
                }
            )
        
        # Verify all questions have proper content
        for q in questions:
            if not q.question_text or not q.question_type:
                logger.warning(f"Invalid question found in interview {interview_id}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "valid": False,
                        "message": "One or more questions are not properly formatted"
                    }
                )
        
        # All validations passed
        return JSONResponse(
            status_code=200,
            content={
                "valid": True,
                "message": "Interview ID is valid and ready to start",
                "total_questions": len(questions),
                "interview_status": interview.status
            }
        )
        
    except SQLAlchemyError as e:
        logger.error(f"Database error validating interview ID: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Database error occurred while validating interview"
        )
    except Exception as e:
        logger.error(f"Error validating interview ID: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate interview ID: {str(e)}"
        )

async def transcribe_audio(file):
    """
    Transcribe audio using audio transcription service
    """
    try:
        file_content = await file.read()
        
        # Create temporary file with correct extension
        temp_file_path = f"temp_{uuid.uuid4()}.wav"  # Change to .wav
        try:
            # First save the file
            with open(temp_file_path, "wb") as temp_file:
                temp_file.write(file_content)
            
            # Open and transcribe the file
            with open(temp_file_path, "rb") as audio_file:
                # Create file tuple with filename and content
                file_tuple = (os.path.basename(temp_file_path), audio_file, 'audio/wav')
                
                transcription = client.audio.transcriptions.create(
                    file=file_tuple,
                    model="distil-whisper-large-v3-en",
                    response_format="text",
                    language="en"
                )
                
            logger.info("Audio transcription successful")
            return transcription

        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                logger.info("Temporary audio file removed")
                
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error transcribing audio: {str(e)}"
        )

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

def text_to_speech(text: str) -> bytes:
    """
    Convert text to speech using ElevenLabs API
    """
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
        logger.info(f"Sending request to ElevenLabs API with text: {text[:100]}...")
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 200:
            audio_content = response.content
            logger.info(f"Received audio response, size: {len(audio_content)} bytes")
            return audio_content
        else:
            error_message = f"ElevenLabs API error: {response.status_code}, Response: {response.text}"
            logger.error(error_message)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_message
            )
            
    except requests.RequestException as e:
        error_message = f"Network error in text-to-speech request: {str(e)}"
        logger.error(error_message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_message
        )
    except Exception as e:
        error_message = f"Unexpected error in text-to-speech: {str(e)}"
        logger.error(error_message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_message
        )

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

@app.on_event("startup")
async def startup_event():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error in startup: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting the FastAPI server")
    uvicorn.run(app, host="0.0.0.0", port=8000)