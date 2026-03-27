from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, HumanMessage
from langgraph.runtime import Runtime
from src.clients.llm import create_llm_client
from src.clients.models.llm_config import LLMConfig
from src.workflows.models.states.base_state import BaseAgentState
from src.workflows.models.base_context import BaseContext
from langchain_core.runnables import RunnableConfig

class SauronAgent():
    def __init__(
        self,
        name: str,
        llm_config: LLMConfig,
    ) -> None:
        self.name = name
        self.llm_client = create_llm_client(llm_config)


    def build_agent(self) -> CompiledStateGraph:
        workflow = StateGraph(state_schema=BaseAgentState, context_schema=BaseContext)
        workflow.add_node("invoke_llm", self.invoke_llm)

        workflow.add_edge(START, "invoke_llm")
        workflow.add_edge("invoke_llm", END)

        return workflow.compile()


    async def invoke_llm(
        self,
        state: BaseAgentState,
        config: RunnableConfig,
        runtime: Runtime[BaseContext],
    ):
        context = getattr(runtime, "context", None)
        system_prompt = context.system_prompt if context else "You are a helpful assistant."
        messages = [SystemMessage(content=system_prompt)] + state["messages"]

        response = await self.llm_client.ainvoke(messages, config=config)
        return {"messages": [response]}
