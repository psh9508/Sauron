from typing import Any
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from src.clients.models.llm_config import LLMConfig

def create_llm_client(llm_config: LLMConfig) -> BaseChatModel:
    configurable_fields = [
        "provider",
        "model",
    ]

    client_kwargs: dict[str, Any] = {
        "configurable_fields": configurable_fields,
        "model": llm_config.model,
    }

    client_kwargs.update(_get_model_provider_kwargs(llm_config.provider))
    
    client = init_chat_model(**client_kwargs)
    return client


def _get_model_provider_kwargs(provider_name: str) -> dict[str, Any]:
    provider_map = {
        "gemini": "google_genai",
        "openai": "openai",
        "anthropic": "google_anthropic_vertex"
    }
    
    mapped_name = provider_map.get(provider_name)
    return {"model_provider": mapped_name} if mapped_name else {}
