from anthropic import BaseModel
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator

LLM_PROVIDERS = Literal[
    "openai",
    "anthropic",
    "gemini",
]

class LLMConfig(BaseModel):
    provider: LLM_PROVIDERS = Field(
        "openai", description="LLM provider (openai, anthropic, gemini)"
    )
    model: str = Field(..., description="Model name")