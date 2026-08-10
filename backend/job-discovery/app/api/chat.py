"""
Chat API — endpoint for Alice conversational agent.
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_candidate
from app.models.candidate import Candidate
from app.agents.alice_agent import chat_with_alice

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


class ChatTurn(BaseModel):
    sender: str = Field(description="'user' ou 'alice'")
    text: str = Field(default="", max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, description="User message to Alice")
    history: list[ChatTurn] = Field(
        default_factory=list,
        description="Tours précédents, du plus ancien au plus récent. Porte le "
                    "fil de la conversation — jamais les chiffres, qui sont "
                    "toujours relus depuis la base.",
    )


class UiBlock(BaseModel):
    type: str
    data: dict | list | None = None
    action: str | None = None


class ChatResponse(BaseModel):
    reply: str
    ui_blocks: list[dict] = Field(default_factory=list)


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, current: Candidate = Depends(get_current_candidate)):
    """
    Send a message to Alice and receive a structured response.
    Alice may call tools (search_jobs, get_cv_audit, etc.) and return
    both text and UI blocks for the frontend to render inline.
    """
    result = await chat_with_alice(
        candidate_id=current.id,
        user_message=req.message,
        user_name=current.full_name or "l'utilisateur",
        history=[t.model_dump() for t in req.history],
    )

    return ChatResponse(
        reply=result["reply"],
        ui_blocks=result.get("ui_blocks", []),
    )
