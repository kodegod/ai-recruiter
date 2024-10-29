from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class JobDescription(Base):
    __tablename__ = 'job_descriptions'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    file_name = Column(String(255), nullable=True)
    original_file_path = Column(String(512), nullable=True)
    file_type = Column(String(50), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Metadata
    requirements = Column(JSON, nullable=True)
    skills_required = Column(JSON, nullable=True)
    experience_required = Column(String(100), nullable=True)
    
    # Relationships
    interviews = relationship("InterviewSession", back_populates="job_description")

class CandidateResume(Base):
    __tablename__ = 'candidate_resumes'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    content = Column(Text, nullable=False)
    file_name = Column(String(255), nullable=True)
    original_file_path = Column(String(512), nullable=True)
    file_type = Column(String(50), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Parsed information
    skills = Column(JSON, nullable=True)
    experience = Column(JSON, nullable=True)
    education = Column(JSON, nullable=True)
    
    # Relationships
    interviews = relationship("InterviewSession", back_populates="candidate_resume")

class InterviewSession(Base):
    __tablename__ = 'interview_sessions'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    jd_id = Column(String(36), ForeignKey('job_descriptions.id'), nullable=False)
    resume_id = Column(String(36), ForeignKey('candidate_resumes.id'), nullable=False)
    
    # Interview metadata
    status = Column(String(50), default='created')  # created, in_progress, completed, cancelled
    scheduled_datetime = Column(DateTime, nullable=True)
    actual_start_time = Column(DateTime, nullable=True)
    actual_end_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Scoring and evaluation
    overall_score = Column(Float, default=0.0)
    technical_score = Column(Float, default=0.0)
    communication_score = Column(Float, default=0.0)
    cultural_fit_score = Column(Float, default=0.0)
    interviewer_notes = Column(Text, nullable=True)
    
    # Session data
    recording_url = Column(String(512), nullable=True)
    transcript = Column(Text, nullable=True)
    
    # Relationships
    job_description = relationship("JobDescription", back_populates="interviews")
    candidate_resume = relationship("CandidateResume", back_populates="interviews")
    questions = relationship("InterviewQuestion", back_populates="interview_session")
    responses = relationship("CandidateResponse", back_populates="interview_session")

class InterviewQuestion(Base):
    __tablename__ = 'interview_questions'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_session_id = Column(String(36), ForeignKey('interview_sessions.id'), nullable=False)
    
    # Question details
    question_text = Column(Text, nullable=False)
    question_type = Column(String(50), nullable=False)  # technical, behavioral, experience
    category = Column(String(100), nullable=True)  # specific skill or competency
    sequence_number = Column(Integer, nullable=False)
    
    # Question metadata
    is_generated = Column(Boolean, default=True)
    is_modified = Column(Boolean, default=False)
    original_question = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Scoring criteria
    expected_answer_keywords = Column(JSON, nullable=True)
    max_score = Column(Float, default=10.0)
    scoring_rubric = Column(JSON, nullable=True)
    
    # Relationships
    interview_session = relationship("InterviewSession", back_populates="questions")
    responses = relationship("CandidateResponse", back_populates="question")

class CandidateResponse(Base):
    __tablename__ = 'candidate_responses'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_session_id = Column(String(36), ForeignKey('interview_sessions.id'), nullable=False)
    question_id = Column(String(36), ForeignKey('interview_questions.id'), nullable=False)
    
    # Response details
    response_text = Column(Text, nullable=False)
    response_audio_url = Column(String(512), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Analysis and scoring
    score = Column(Float, nullable=True)
    keywords_matched = Column(JSON, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    clarity_score = Column(Float, nullable=True)
    technical_accuracy = Column(Float, nullable=True)
    
    # AI Analysis
    ai_feedback = Column(Text, nullable=True)
    improvement_suggestions = Column(Text, nullable=True)
    
    # Relationships
    interview_session = relationship("InterviewSession", back_populates="responses")
    question = relationship("InterviewQuestion", back_populates="responses")

def init_db(engine):
    """Initialize the database by creating all tables"""
    Base.metadata.create_all(bind=engine)