from typing import Any
from langchain.chat_models import init_chat_model
from clients.models.llm_config import LLMConfig


def create_llm_client(llm_config: LLMConfig):
    configurable_fields = [
        "provider",
        "model",
    ]

    client_kwargs: dict[str, Any] = {
        "configurable_fields": configurable_fields,
        "model": llm_config.model,
    }
    
    client = init_chat_model(**client_kwargs)
    return client
