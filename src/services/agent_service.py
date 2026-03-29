from typing import Any
from langchain_core.runnables import RunnableConfig


def get_runtime_context():
    pass


def get_runnable_config() -> RunnableConfig:
    config_dict: dict[str, Any] = {
        "configurable": {
            "thread_id": "1234",  # test
            "message_id": "5678", # test
        },
        "recursion_limit": 50,
    }

    return RunnableConfig(**config_dict)