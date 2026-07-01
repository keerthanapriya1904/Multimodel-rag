import os, sys, tempfile
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from groq import Groq
from config import GROQ_API_KEY
from database import User
from api.auth import get_current_user

# Ensure local imports work
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

router = APIRouter(prefix="/voice", tags=["Voice"])

# ── 1. SETUP GROQ CLIENT ──
# Using Groq Whisper API (0MB local RAM usage)
client = Groq(api_key=GROQ_API_KEY)

@router.post("/transcribe")
async def transcribe_voice(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Cloud-Based English Transcription via Groq Whisper-V3.
    Optimized for 4GB RAM by offloading ASR to the cloud.
    """
    # Create a temporary file for the audio data
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
        content = await audio.read()
        temp_audio.write(content)
        temp_path = temp_audio.name

    try:
        print(f"  [Voice] Processing English audio for user: {current_user.username}")
        
        with open(temp_path, "rb") as file:
            # ── 2. CALL WHISPER (FIXED TO ENGLISH) ──
            transcription = client.audio.transcriptions.create(
                file=(temp_path, file.read()),
                model="whisper-large-v3", 
                response_format="json",
                language="en", # <--- CRITICAL: Forces English Only
                temperature=0.0 # <--- Ensures highest accuracy (zero randomness)
            )
        
        clean_text = transcription.text.strip()
        print(f"  [Voice] Success: '{clean_text[:50]}...'")
        
        return {"text": clean_text}

    except Exception as e:
        print(f"  [Voice Error] {e}")
        raise HTTPException(status_code=500, detail="Voice processing failed.")
    
    finally:
        # ── 3. ZERO-PERSISTENCE CLEANUP ──
        if os.path.exists(temp_path):
            os.remove(temp_path)