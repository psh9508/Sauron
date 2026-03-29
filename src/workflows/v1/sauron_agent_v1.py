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
    get_installation_context,
    get_repository_content,
)
from langchain_core.runnables import RunnableConfig

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


    async def prepare(
        self,
        _: BaseAgentState,
        runtime: Runtime[BaseContext],
    ) -> dict:
        cache_key = get_installation_context(runtime.context.project_id)
        return {"installation_token_internal_key": cache_key}


    async def invoke_llm(
        self,
        state: BaseAgentState,
        config: RunnableConfig,
        runtime: Runtime[BaseContext],
    ):
        context = getattr(runtime, "context", None)
        system_prompt = context.system_prompt if context else "You are a helpful assistant."
        messages = [SystemMessage(content=system_prompt)] + state["messages"]

        response = await self.llm_client_with_tools.ainvoke(messages, config=config)
        return {"messages": [response]}
