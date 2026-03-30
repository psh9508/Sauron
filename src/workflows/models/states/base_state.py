from typing import Annotated, NotRequired, Sequence, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class BaseAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    installation_token_internal_key: NotRequired[str]
    repo_file_paths: NotRequired[list[str]]
    candidate_file_paths: NotRequired[list[str]]
