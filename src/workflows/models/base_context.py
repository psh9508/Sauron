from pydantic import BaseModel, Field


class BaseContext(BaseModel):
    system_prompt: str = Field(..., description="System prompt to guide the agent's behavior")
    project_id: int = Field(..., description="Project ID for the current request")
