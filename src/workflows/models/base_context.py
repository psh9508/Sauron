from anthropic import BaseModel
from langchain_core.runnables import RunnableConfig

class BaseContext(BaseModel):
    system_prompt: str
    runnable_config: RunnableConfig