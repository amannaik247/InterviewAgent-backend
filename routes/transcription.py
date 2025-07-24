from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
import os
import requests
import tempfile
import azure.cognitiveservices.speech as speechsdk
from db.mongo_client import update_user_session
from dependencies import get_user_session_data
from pydub import AudioSegment

transcription_router = APIRouter(prefix="/transcribe")

@transcription_router.post("/")
async def transcribe_audio(request: Request, file: UploadFile = File(...), user_session: dict = Depends(get_user_session_data)):
    try:
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_file:
            temp_path = temp_file.name
            temp_file.write(await file.read())
            
        # Convert to wav (PCM)
        audio = AudioSegment.from_file(temp_path, format="webm")
        wav_path = temp_path.replace(".webm", ".wav")
        audio.export(wav_path, format="wav")
                    
        # Set up the speech config and audio config
        speech_config = speechsdk.SpeechConfig(subscription=os.getenv("AZURE_SPEECH_KEY"), region="centralindia")
        audio_config = speechsdk.audio.AudioConfig(filename=wav_path)
        speech_config.speech_recognition_language = "en-IN"
        
        # Create the recognizer
        speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
        result = speech_recognizer.recognize_once()

        # Clean up recognizer and audio config before deleting the file
        del speech_recognizer
        del audio_config

        os.remove(temp_path)
        
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            text = result.text
        elif result.reason == speechsdk.ResultReason.NoMatch:
            raise HTTPException(status_code=400, detail="No speech could be recognized.")
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            raise HTTPException(status_code=400, detail=f"Speech Recognition canceled: {cancellation.reason}")
        
        # Store the result in MongoDB messages
        user_id = request.state.user_id
        prev_messages = user_session.get("messages", [])
        prev_messages.append({"role": "user", "content": text})
        update_user_session(user_id, {"messages": prev_messages})

        return JSONResponse(
            status_code=200,
            content={
                "message": "Transcription successful",
                "text": text
            }
        )

    except Exception as e:
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing audio: {str(e)}"
        )
