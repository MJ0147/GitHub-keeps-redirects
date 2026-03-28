import logging
import os
import sys
from typing import Optional, Dict

import httpx
from fastapi import FastAPI, Depends, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from openai import OpenAI
from sqlalchemy.orm import Session
from sqlalchemy import text
from deps import get_db
from app.core.config import settings

# Setup structured logging for Cloud Run
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("iyobo-service")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

IYOBO_SYSTEM_PROMPT = "You are Iyobo, the AI assistant for Ekioba e-commerce. You help users with shopping, orders, and payments via Idia Coin (on TON/Solana). Be helpful, professional, and concise."

app = FastAPI(title="Iyobo AI Assistant", description="AI Service for Ekioba E-commerce")

# Allow CORS for frontend interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend domain
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The user's input message")
    user_id: Optional[str] = Field(None, description="Optional user ID for context")
    context: Optional[Dict] = Field(None, description="Additional context (e.g., cart items)")


class ChatResponse(BaseModel):
    reply: str
    intent: Optional[str] = None

async def get_ai_response(message: str, raise_on_error: bool = False) -> str:
    """Centralized method to get real-time AI responses."""
    try:
        response = ai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": IYOBO_SYSTEM_PROMPT},
                {"role": "user", "content": message}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"AI Service Error: {e}")
        if raise_on_error:
            raise e
        return "I'm having trouble connecting to my brain right now. Please try again later."

@app.get("/", tags=["Health"])
def root():
    """Root endpoint for basic connectivity check."""
    return {"service": "Iyobo AI Assistant", "status": "running"}


@app.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """Health check for database connectivity and service status."""
    try:
        # Execute a simple query to verify the MySQL connection
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed"
        )


@app.post("/telegram/webhook", tags=["Telegram"])
async def telegram_webhook(request: Request):
    """
    Webhook to receive messages from Telegram.
    Wakes up Cloud Run on demand.
    """
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not configured")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Telegram configuration missing")

    data = await request.json()
    
    # Basic echo/reply logic
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        user_text = data["message"].get("text", "")
        logger.info(f"Telegram message from {chat_id}: {user_text}")

        # Get real-time AI response
        ai_reply = await get_ai_response(user_text)

        # Send reply back to Telegram
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": ai_reply}
            )

    return {"status": "ok"}

@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(payload: ChatRequest):
    """Process a chat message with real-time AI."""
    logger.info(f"Received message from user {payload.user_id}: {payload.message}")

    try:
        reply = await get_ai_response(payload.message, raise_on_error=True)
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI Service unreachable")

    return {
        "reply": reply,
        "intent": "dynamic_ai",
    }


if __name__ == "__main__":
    # Cloud Run injects the PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Iyobo AI Service on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
