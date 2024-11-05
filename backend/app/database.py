from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import os
import logging
from dotenv import load_dotenv

# Set up logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# Ensure SQLite directory exists
if DATABASE_URL.startswith("sqlite"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    logger.info(f"Ensured SQLite database directory exists at: {db_path}")

# Create engine with proper settings
engine = create_engine(
    DATABASE_URL,
    # Add connect_args only for SQLite
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    # Add pooling configuration
    poolclass=QueuePool,
    pool_size=5,
    pool_pre_ping=True,
    pool_recycle=300
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base
Base = declarative_base()

def get_db():
    """
    Database dependency that handles session management and connection testing
    """
    db = SessionLocal()
    try:
        # Test connection
        db.execute(text("SELECT 1"))
        logger.debug("Database connection successful")
        yield db
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        try:
            db.rollback()
        except Exception as rollback_error:
            logger.error(f"Rollback error: {str(rollback_error)}")
        raise
    finally:
        db.close()
        logger.debug("Database connection closed")

def init_db():
    """
    Initialize database and create all tables
    """
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}")
        raise Exception(f"Failed to initialize database: {str(e)}")

# Log database configuration on module load
logger.info(f"Database configured with URL: {DATABASE_URL}")