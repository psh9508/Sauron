import re

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.runtime import Runtime

from src.clients.llm import create_llm_client
from src.clients.models.llm_config import LLMConfig
from src.workflows.models.base_context import BaseContext
from src.workflows.models.states.base_state import BaseAgentState
from src.workflows.tools.github_tools import (
    get_installation_context_cache_key,
    get_repository_file_paths,
    get_repository_content,
)

class SauronAgent():
    def __init__(
        self,
        name: str,
        llm_config: LLMConfig,
    ) -> None:
        self.name = name
        self.tools = [
            get_repository_content,
        ]
        self.tool_node = ToolNode(self.tools)
        self.llm_client = create_llm_client(llm_config)
        self.llm_client_with_tools = self.llm_client.bind_tools(self.tools)


    def build_agent(self) -> CompiledStateGraph:
        workflow = StateGraph(state_schema=BaseAgentState, context_schema=BaseContext)
        workflow.add_node("prepare", self.prepare)
        workflow.add_node("invoke_llm", self.invoke_llm)
        workflow.add_node("tools", self.tool_node)

        workflow.add_edge(START, "prepare")
        workflow.add_edge("prepare", "invoke_llm")
        workflow.add_conditional_edges(
            "invoke_llm",
            tools_condition,
            {
                "tools": "tools",
                "__end__": END,
            },
        )
        workflow.add_edge("tools", "invoke_llm")

        return workflow.compile()


    def _extract_candidate_file_paths(
        self,
        stack_trace: str,
        repo_file_paths: list[str],
    ) -> list[str]:
        if not stack_trace or not repo_file_paths:
            return []

        direct_matches = [
            repo_path for repo_path in repo_file_paths
            if repo_path in stack_trace
        ]

        trace_paths = re.findall(r'["\']([^"\']+\.[A-Za-z0-9]+)["\']', stack_trace)
        suffix_matches = [
            repo_path
            for repo_path in repo_file_paths
            if any(trace_path.endswith(repo_path) for trace_path in trace_paths)
        ]

        file_names = set(
            re.findall(r'([\w.-]+\.(?:py|js|ts|tsx|jsx|java|kt|go|rb|php|cs|cpp|c|h|hpp|swift|rs|scala|m))', stack_trace)
        )
        basename_matches = [
            repo_path for repo_path in repo_file_paths
            if repo_path.rsplit("/", 1)[-1] in file_names
        ]

        ordered_candidates: list[str] = []
        for candidate in direct_matches + suffix_matches + basename_matches:
            if candidate not in ordered_candidates:
                ordered_candidates.append(candidate)

        return ordered_candidates[:20]


    def _build_runtime_hint_message(self, candidate_file_paths: list[str]) -> SystemMessage | None:
        if not candidate_file_paths:
            return None

        candidate_lines = "\n".join(f"- {path}" for path in candidate_file_paths)
        return SystemMessage(
            content=(
                "Repository file path candidates inferred from the stack trace:\n"
                f"{candidate_lines}\n"
                "When calling get_repository_content, prefer choosing from these paths."
            )
        )


    def _build_llm_messages(
        self,
        system_prompt: str,
        state: BaseAgentState,
    ) -> list[BaseMessage]:
        messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]

        runtime_hint_message = self._build_runtime_hint_message(
            state.get("candidate_file_paths", [])
        )
        if runtime_hint_message is not None:
            messages.append(runtime_hint_message)

        messages.extend(state["messages"])
        return messages


    async def prepare(
        self,
        _: BaseAgentState,
        runtime: Runtime[BaseContext],
    ) -> dict:
        analyze_request = runtime.context.analyze_request

        cache_key = await get_installation_context_cache_key(analyze_request.repository_id)
        repo_file_paths = get_repository_file_paths(cache_key)
        candidate_file_paths = self._extract_candidate_file_paths(
            stack_trace=analyze_request.stack_trace,
            repo_file_paths=repo_file_paths,
        )
        return {
            "installation_token_internal_key": cache_key,
            "repo_file_paths": repo_file_paths,
            "candidate_file_paths": candidate_file_paths,
        }


    async def invoke_llm(
        self,
        state: BaseAgentState,
        config: RunnableConfig,
        runtime: Runtime[BaseContext],
    ):
        context = getattr(runtime, "context", None)
        system_prompt = context.system_prompt if context else "You are a helpful assistant."
        messages = self._build_llm_messages(system_prompt=system_prompt, state=state)

        response = await self.llm_client_with_tools.ainvoke(messages, config=config)
        return {"messages": [response]}
