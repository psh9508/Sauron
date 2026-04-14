from pydantic import BaseModel, Field

from src.apis.models.AnalyzeRequest import AnalyzeRequest


class BaseContext(BaseModel):
    system_prompt: str = Field(..., description="System prompt to guide the agent's behavior")
    analyze_request: AnalyzeRequest = Field(..., description="Analyze request for the current run")
