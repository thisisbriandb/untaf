"""
Accès à Gemini — point unique pour tout le backend.

SDK `google-genai` : l'ancien `google-generativeai` n'est plus maintenu
depuis fin 2025. Les appels passent par le client asynchrone, pour ne pas
bloquer la boucle d'événements de FastAPI pendant qu'un modèle réfléchit.
"""

from functools import lru_cache

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import settings


@lru_cache(maxsize=1)
def client() -> genai.Client:
    return genai.Client(api_key=settings.gemini_api_key)


async def generate(
    prompt: str,
    *,
    json: bool = False,
    schema: type[BaseModel] | None = None,
) -> str:
    """
    Un appel unique, sans conversation. Renvoie le texte de la réponse.

    `json` force une sortie JSON ; `schema` impose en plus sa structure.
    """
    config = types.GenerateContentConfig(
        response_mime_type="application/json" if (json or schema) else None,
        response_schema=schema,
    )
    response = await client().aio.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=config,
    )
    return response.text or ""
