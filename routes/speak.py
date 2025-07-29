import os
from fastapi import FastAPI, Body, APIRouter
from fastapi.responses import Response
from groq import Groq

speak_router = APIRouter(prefix="/speak")

client = Groq(api_key=os.environ.get("GROQ_STT_API_KEY"))

MODEL = "playai-tts"
VOICE = "Fritz-PlayAI"
FORMAT = "wav"

@speak_router.post("/speak_up")
async def speak(text: str = Body(..., embed=True)):
    try:
        # Call Groq TTS
        response = client.audio.speech.create(
            model=MODEL,
            voice=VOICE,
            input=text,
            response_format=FORMAT,
        )

        # Get audio bytes (streamed)
        audio_bytes = response.read()  # raw bytes

        # Return as audio response
        return Response(
            content=audio_bytes,
            media_type="audio/wav"
        )

    except Exception as e:
        return {"error": str(e)}
