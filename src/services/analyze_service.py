from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from src.apis.models.AnalyzeRequest import AnalyzeRequest
from src.config import get_settings
from src.services.exceptions.source_control_exception import (
    GitLabInsufficientTokenScopeError,
    GitLabProjectNotFoundError,
    SourceControlAccessTokenInvalidError,
)
from src.workflows.models.base_context import BaseContext
from src.workflows.templates.sauron_agent_system_prompt import SAURON_SYSTEM_PROMPT
from src.workflows.tools.source_control_tools import invalidate_source_control_cache
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


def _format_breadcrumb(crumb: dict) -> str:
    prefix = f"{crumb['timestamp']} " if crumb.get("timestamp") else ""
    level = crumb.get("level") or "info"
    category = crumb.get("category")
    message = crumb.get("message") or ""
    body = f"{category}: {message}" if category else message
    return f"{prefix}[{level}] {body}"


def _format_breadcrumbs(breadcrumbs: list[dict]) -> str:
    return "\n".join(_format_breadcrumb(crumb) for crumb in breadcrumbs)


async def run_analyze(request: AnalyzeRequest) -> str:
    parts = [
        "Analyze the following application error.\n",
        f"error_message:\n{request.error_message}",
    ]
    if request.stack_trace:
        parts.append(f"\nstack_trace:\n{request.stack_trace}")
    if request.breadcrumbs:
        parts.append(f"\nbreadcrumbs:\n{_format_breadcrumbs(request.breadcrumbs)}")

    try:
        data = await analyze_workflow.ainvoke(
            {
                "messages": [
                    HumanMessage(content="\n".join(parts))
                ]
            },
            config=RunnableConfig(),
            context=BaseContext(
                system_prompt=SAURON_SYSTEM_PROMPT,
                analyze_request=request,
            ),
        )
    except (
        SourceControlAccessTokenInvalidError,
        GitLabInsufficientTokenScopeError,
        GitLabProjectNotFoundError,
    ):
        # Cached token or repo tree is stale; reload from DB on the next job
        invalidate_source_control_cache(
            repository_id=request.repository_id,
            repository_url=str(request.repository_url) if request.repository_url is not None else None,
        )
        raise
    return _extract_final_response(data)
