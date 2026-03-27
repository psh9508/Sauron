from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    # project_id: int = Field(..., description="Project ID to find source code from source control(github, gitlab, etc.)")
    error_message: str = Field(..., description="Error message to analyze")
    stack_trace: str = Field(..., description="Stack trace of the error")
