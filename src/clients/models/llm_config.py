from typing import Literal
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
    temperature: float = Field(
        0.3,
        ge=0.0,
        le=1.0,
        description="Model temperature",
    )
