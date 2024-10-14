from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Candidate(Base):
    __tablename__ = 'candidates'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    interviews = relationship("Interview", back_populates="candidate")

class Interview(Base):
    __tablename__ = 'interviews'
    id = Column(Integer, primary_key=True)
    candidate_id = Column(Integer, ForeignKey('candidates.id'))
    candidate = relationship("Candidate", back_populates="interviews")
    questions = relationship("Question", back_populates="interview")
    consolidated_score = Column(Float)

class Question(Base):
    __tablename__ = 'questions'
    id = Column(Integer, primary_key=True)
    interview_id = Column(Integer, ForeignKey('interviews.id'))
    interview = relationship("Interview", back_populates="questions")
    question_text = Column(Text)
    response = Column(Text)
    score = Column(Float)