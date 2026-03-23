from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages

class BaseAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]