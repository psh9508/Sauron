from fastapi import APIRouter
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from src.apis.models.AnalyzeRequest import AnalyzeRequest
from src.clients.models.llm_config import LLMConfig
from src.workflows.models.base_context import BaseContext
from src.workflows.templates.sauron_agent_system_prompt import SAURON_SYSTEM_PROMPT
from src.workflows.v1.sauron_agent_v1 import SauronAgent

router = APIRouter(prefix="/analyze", tags=["analyze"])

analyze_workflow = SauronAgent(
    name="analyze_agent",   
    llm_config=LLMConfig(
        provider="gemini",
        model="gemini-3-flash-preview",
    ),
).build_agent()

@router.post("")
async def analyze(request: AnalyzeRequest):
    data = await analyze_workflow.ainvoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "Analyze the following application error.\n\n"
                        f"error_message:\n{request.error_message}\n\n"
                        f"stack_trace:\n{request.stack_trace}"
                    )
                )
            ]
        },
        config=RunnableConfig(),
        context=BaseContext(
            system_prompt=SAURON_SYSTEM_PROMPT,
        ),
    )
    print(data)
    return data
