from groq import Groq
import os
from typing import List, Dict, Any
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get API key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found. Please check your .env file.")

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

async def modify_questions(questions: List[Dict[str, Any]], feedback: str) -> List[Dict[str, Any]]:
    """
    Modify existing questions based on feedback
    """
    try:
        logger.info("Modifying questions based on feedback...")
        
        # Format existing questions for the prompt
        questions_text = "\n".join([
            f"Question {i+1}:\n{q['question_text']}\nType: {q.get('question_type', 'N/A')}\nAssesses: {q.get('assesses', 'N/A')}"
            for i, q in enumerate(questions)
        ])

        prompt = f"""Modify these interview questions based on the following feedback while maintaining their professional structure:

Current Questions:
{questions_text}

Feedback:
{feedback}

Provide modified questions in the same format:
1. Question: [Modified question]
   Type: [Question type]
   Assesses: [Skill/competency]
   Key Points: [Key points to look for in answer]
"""

        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": "You are an expert at refining interview questions based on feedback."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )

        # Parse the modified questions
        modified_questions = parse_generated_questions(response.choices[0].message.content)
        
        # Validate and clean up modified questions
        validated_questions = []
        for i, q in enumerate(modified_questions):
            if i >= len(questions):  # Don't add more questions than we started with
                break
                
            validated_question = {
                "question_text": q.get("question_text", "").strip(),
                "question_type": q.get("question_type", questions[i].get("question_type", "general")).lower(),
                "assesses": q.get("assesses", questions[i].get("assesses", "general skills")),
                "key_points": q.get("key_points", questions[i].get("key_points", ""))
            }
            
            # Only include valid questions
            if validated_question["question_text"]:
                validated_questions.append(validated_question)
            else:
                # If modification failed, keep the original question
                validated_questions.append(questions[i])

        logger.info(f"Successfully modified {len(validated_questions)} questions")
        return validated_questions

    except Exception as e:
        logger.error(f"Error modifying questions: {str(e)}")
        # Return original questions if modification fails
        logger.info("Returning original questions due to modification error")
        return questions

async def generate_interview_questions(jd_content: str, resume_content: str) -> List[Dict[str, Any]]:
    """
    Generate exactly 5 structured interview questions based on JD and resume using Llama model
    """
    try:
        prompt = f"""Given the job description and resume below, generate EXACTLY 5 interview questions.
Create a diverse set of questions covering:
1. Technical skills and expertise
2. Past experience and achievements
3. Problem-solving abilities
4. Behavioral traits and work style
5. Cultural fit and values

Job Description:
{jd_content}

Resume:
{resume_content}

Provide the questions in this EXACT format:

1. Question: [Ask a specific question related to technical skills mentioned in JD]
   Type: technical
   Assesses: [Specific technical skill]
   Key Points: [3-4 key points to look for in answer]

2. Question: [Ask about relevant past experience]
   Type: experience
   Assesses: [Specific experience area]
   Key Points: [3-4 key points to look for in answer]

3. Question: [Ask about a problem-solving scenario]
   Type: problem-solving
   Assesses: [Problem-solving skill]
   Key Points: [3-4 key points to look for in answer]

4. Question: [Ask about behavioral traits]
   Type: behavioral
   Assesses: [Behavioral trait]
   Key Points: [3-4 key points to look for in answer]

5. Question: [Ask about cultural fit]
   Type: cultural-fit
   Assesses: [Cultural aspect]
   Key Points: [3-4 key points to look for in answer]

Important: Ensure questions are highly specific to the job description and candidate's background.
"""

        logger.info("Requesting questions from Llama model...")
        
        # Make multiple attempts to get good questions
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = client.chat.completions.create(
                    model="llama3-70b-8192",
                    messages=[
                        {
                            "role": "system",
                            "content": """You are an expert AI recruiter who generates insightful, 
                            specific interview questions based on job descriptions and resumes. 
                            Focus on creating questions that thoroughly evaluate candidate qualifications."""
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=2000
                )

                # Parse the response into structured format
                generated_text = response.choices[0].message.content
                questions = parse_generated_questions(generated_text)
                
                # Validate the generated questions
                if len(questions) == 5 and all(validate_question(q) for q in questions):
                    logger.info("Successfully generated 5 valid questions from Llama model")
                    return questions
                else:
                    logger.warning(f"Attempt {attempt + 1}: Generated {len(questions)} questions, retrying...")
                    continue

            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_attempts - 1:
                    raise

        # If we couldn't get good questions after all attempts, use default questions
        logger.warning("Could not generate valid questions from Llama model, using defaults")
        return get_default_questions()

    except Exception as e:
        logger.error(f"Error in question generation: {str(e)}")
        return get_default_questions()

def validate_question(question: Dict[str, Any]) -> bool:
    """
    Validate that a question has all required fields and appropriate content
    """
    required_fields = ["question_text", "question_type", "assesses", "key_points"]
    
    # Check all required fields are present and non-empty
    if not all(field in question and question[field] for field in required_fields):
        return False
    
    # Validate question text length
    if len(question["question_text"]) < 10:  # Arbitrary minimum length
        return False
    
    # Validate question type
    valid_types = {"technical", "experience", "problem-solving", "behavioral", "cultural-fit"}
    if question["question_type"].lower() not in valid_types:
        return False
    
    return True

def get_default_questions() -> List[Dict[str, Any]]:
    """
    Get default interview questions as fallback
    """
    logger.info("Using default question set")
    return [
        {
            "question_text": "Could you walk me through your most technically challenging project?",
            "question_type": "technical",
            "assesses": "Technical expertise and problem-solving",
            "key_points": "Technical depth, problem approach, solution implementation, results achieved"
        },
        {
            "question_text": "Describe a situation where you had to learn a new technology quickly. How did you approach it?",
            "question_type": "experience",
            "assesses": "Learning ability and adaptability",
            "key_points": "Learning strategy, time management, practical application, outcome"
        },
        {
            "question_text": "Tell me about a time when you had to resolve a complex technical issue under tight deadlines.",
            "question_type": "problem-solving",
            "assesses": "Critical thinking and pressure handling",
            "key_points": "Problem analysis, solution approach, time management, result"
        },
        {
            "question_text": "How do you handle disagreements with team members about technical decisions?",
            "question_type": "behavioral",
            "assesses": "Conflict resolution and teamwork",
            "key_points": "Communication style, conflict resolution approach, team collaboration, outcome"
        },
        {
            "question_text": "What aspects of our company's tech stack and culture interest you the most?",
            "question_type": "cultural-fit",
            "assesses": "Company culture alignment and technical interest",
            "key_points": "Company research, technical knowledge, cultural values, motivation"
        }
    ]

def parse_generated_questions(text: str) -> List[Dict[str, Any]]:
    """
    Parse the LLM response into structured question objects
    """
    questions = []
    current_question = {}
    
    try:
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Check for new question
            if line.startswith('Question:') or (line[0].isdigit() and line[1] == '.'):
                if current_question and 'question_text' in current_question:
                    questions.append(current_question)
                current_question = {
                    "question_text": line.split(':', 1)[1].strip() if ':' in line 
                    else line.split('.', 1)[1].strip()
                }
            elif line.startswith('Type:'):
                current_question['question_type'] = line.replace('Type:', '').strip().lower()
            elif line.startswith('Assesses:'):
                current_question['assesses'] = line.replace('Assesses:', '').strip()
            elif line.startswith('Key Points:'):
                current_question['key_points'] = line.replace('Key Points:', '').strip()
        
        # Add the last question
        if current_question and 'question_text' in current_question:
            questions.append(current_question)
        
        # Additional validation and cleanup
        validated_questions = []
        for q in questions:
            if validate_question(q):
                validated_questions.append(q)
        
        return validated_questions
        
    except Exception as e:
        logger.error(f"Error parsing questions: {str(e)}")
        return []

async def analyze_response(question: str, response: str) -> Dict[str, Any]:
    """
    Analyze a candidate's response to a question
    """
    try:
        prompt = f"""Analyze this interview response based on the following criteria:
1. Relevance to the question (0-10)
2. Clarity of communication (0-10)
3. Technical accuracy (if applicable) (0-10)
4. Key points covered
5. Areas for improvement

Question: {question}
Response: {response}

Provide analysis in the following format:
Relevance Score: [score]
Clarity Score: [score]
Technical Score: [score]
Key Points Covered: [points]
Improvement Areas: [areas]
Overall Feedback: [feedback]
"""

        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": "You are an expert at evaluating interview responses."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        # Parse the analysis
        analysis_text = response.choices[0].message.content
        analysis = parse_response_analysis(analysis_text)
        return analysis

    except Exception as e:
        logger.error(f"Error analyzing response: {str(e)}")
        # Return default scores if analysis fails
        return {
            'relevance_score': 5,
            'technical_score': 5,
            'clarity_score': 5,
            'feedback': 'Error analyzing response',
            'improvement_areas': 'Analysis unavailable',
            'key_points': ''
        }

def parse_response_analysis(text: str) -> Dict[str, Any]:
    """
    Parse the response analysis into a structured format
    """
    analysis = {
        'relevance_score': 5,
        'clarity_score': 5,
        'technical_score': 5,
        'key_points': '',
        'improvement_areas': '',
        'feedback': ''
    }
    
    try:
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('Relevance Score:'):
                analysis['relevance_score'] = float(line.split(':')[1].strip())
            elif line.startswith('Clarity Score:'):
                analysis['clarity_score'] = float(line.split(':')[1].strip())
            elif line.startswith('Technical Score:'):
                analysis['technical_score'] = float(line.split(':')[1].strip())
            elif line.startswith('Key Points Covered:'):
                analysis['key_points'] = line.split(':')[1].strip()
            elif line.startswith('Improvement Areas:'):
                analysis['improvement_areas'] = line.split(':')[1].strip()
            elif line.startswith('Overall Feedback:'):
                analysis['feedback'] = line.split(':')[1].strip()
    except Exception as e:
        logger.error(f"Error parsing analysis: {str(e)}")
    
    return analysis

def parse_response_analysis(text: str) -> Dict[str, Any]:
    """
    Parse the response analysis into a structured format
    """
    analysis = {
        'relevance_score': 5,
        'clarity_score': 5,
        'technical_score': 5,
        'key_points': '',
        'improvement_areas': '',
        'feedback': ''
    }
    
    try:
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('Relevance Score:'):
                analysis['relevance_score'] = float(line.split(':')[1].strip())
            elif line.startswith('Clarity Score:'):
                analysis['clarity_score'] = float(line.split(':')[1].strip())
            elif line.startswith('Technical Score:'):
                analysis['technical_score'] = float(line.split(':')[1].strip())
            elif line.startswith('Key Points Covered:'):
                analysis['key_points'] = line.split(':')[1].strip()
            elif line.startswith('Improvement Areas:'):
                analysis['improvement_areas'] = line.split(':')[1].strip()
            elif line.startswith('Overall Feedback:'):
                analysis['feedback'] = line.split(':')[1].strip()
    except Exception as e:
        logger.error(f"Error parsing analysis: {str(e)}")
    
    return analysis