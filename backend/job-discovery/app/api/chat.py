"""
Chat API — endpoint for Alice conversational agent.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import AuthUser, assert_owner, require_user
from app.database import async_session
from app.models.candidate import Candidate
from app.agents.alice_agent import chat_with_alice

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


class ChatTurn(BaseModel):
    sender: str = Field(description="'user' ou 'alice'")
    text: str = Field(default="", max_length=4000)


class ChatRequest(BaseModel):
    candidate_id: str = Field(..., description="UUID of the candidate")
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
async def chat_endpoint(req: ChatRequest, user: AuthUser = Depends(require_user)):
    """
    Send a message to Alice and receive a structured response.
    Alice may call tools (search_jobs, get_cv_audit, etc.) and return
    both text and UI blocks for the frontend to render inline.
    """
    # Validate candidate exists
    try:
        candidate_id = UUID(req.candidate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid candidate_id format")

    async with async_session() as session:
        # Le candidat est dans le corps, pas dans le chemin : la garde
        # globale ne le voit pas, on vérifie ici.
        await assert_owner(session, user, candidate_id)
        candidate = await session.get(Candidate, candidate_id)

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Call Alice agent
    result = await chat_with_alice(
        candidate_id=candidate_id,
        user_message=req.message,
        user_name=candidate.full_name or "l'utilisateur",
        history=[t.model_dump() for t in req.history],
    )

    return ChatResponse(
        reply=result["reply"],
        ui_blocks=result.get("ui_blocks", []),
    )
