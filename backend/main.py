from fastapi import FastAPI, UploadFile
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from openai import OpenAI
import os
from groq import Groq
import json
import requests
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI()

role = "Frontend Engineer"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to allow only specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(
    api_key = os.getenv("GROQ_API_KEY")
)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Talk request
@app.post("/talk")
async def post_audio(file: UploadFile):

    # Get user message from audio
    user_message = await transcribe_audio(file)

    # Get LLM Response for the user message
    chat_response = get_chat_response(user_message)

    # Convert the LLM Response to AI Audio using Elevenlabs
    audio_output = text_to_speech(chat_response)

    # Stream audio using fastapi (that we received from elevenlabs api)
    def iterfile():
        yield audio_output
    return StreamingResponse(iterfile(), media_type='audio/mpeg')


async def transcribe_audio(file):
    file_content = await file.read()
    # Create a transcription of the audio file
    transcription = client.audio.transcriptions.create(
        file=(file.filename, file_content), # Required audio file
        model="distil-whisper-large-v3-en", # Required model to use for transcription
        prompt="Specify context or spelling",  # Optional
        response_format="json",  # Optional
        language="en",  # Optional
        temperature=0.0  # Optional
    )
    return transcription.text



def get_chat_response(user_message):

    # Load current message history
    messages = load_messages(role)

    # Add user message to current message history
    messages.append({"role": "user", "content": f"{user_message}"})

    # Send entire message history with current message to LLM and receive response
    llm_response = client.chat.completions.create(
        model= "llama3-70b-8192",
        messages= messages
    )
    print(llm_response)

    parsed_llm_response = llm_response.choices[0].message.content

    # Save this conversation to message history database
    save_messages(user_message, parsed_llm_response)

    return parsed_llm_response


# Load current chat message history 
def load_messages(role):
    messages = []
    file = 'database.json'
    # If file is empty we need to add the context
    empty = os.stat(file).st_size == 0
    # If file is not empty, add to messages
    if not empty:
        with open(file) as db_file:
            data = json.load(db_file)
            for item in data:
                messages.append(item)
    else:
        messages.append(
            {
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
            }
        )
    return messages

def save_messages(user_message, llm_response):
    file = 'database.json'
    messages = load_messages("Frontent Engineer")
    print(user_message)
    print(llm_response)
    messages.append({"role": "user", "content": f"{user_message}"})
    messages.append({"role": "assistant", "content": f"{llm_response}"})
    with open(file, 'w') as f:
        json.dump(messages, f)


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
            "style": '0.5',
            "use_speaker_boost": True
        }
    }
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            return response.content
        else:
            print('Something went wrong')
    except Exception as e:
        print(e)
