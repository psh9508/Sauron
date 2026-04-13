from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from src.apis.models.AnalyzeRequest import AnalyzeRequestPayload
from src.config import get_settings
from src.workflows.models.base_context import BaseContext
from src.workflows.templates.sauron_agent_system_prompt import SAURON_SYSTEM_PROMPT
from src.workflows.v1.sauron_agent_v1 import SauronAgent


settings = get_settings()

analyze_workflow = SauronAgent(
    name="analyze_agent",
    llm_config=settings.llm,
).build_agent()


def _extract_text_content(message: AIMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
                continue

            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    text_parts.append(text)

        return "\n".join(part for part in text_parts if part)

    return str(content)


def _extract_final_response(data: dict) -> str:
    messages = data.get("messages", [])
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            text = _extract_text_content(message).strip()
            if text:
                return text

    raise RuntimeError("Final AI response was not found in workflow output")


async def run_analyze(request: AnalyzeRequestPayload) -> str:
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
            analyze_request=request,
        ),
    )
    return _extract_final_response(data)
