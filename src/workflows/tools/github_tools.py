"""Source control tools for LLM agents.

This module provides provider-agnostic tools for interacting with source control
repositories (GitHub, GitLab, etc.) through the SourceControlService abstraction.
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, NotRequired, TypedDict

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import Field

from src.core import database
from src.services.source_control_service import SourceControlService
from src.services.source_controlers.base import SourceControlClient


class SourceControlContext(TypedDict):
    """Cached source control context for a repository."""
    client: SourceControlClient
    access_token: str
    repo_url: str
    repo_file_paths: NotRequired[list[str]]


# Cache for source control contexts, keyed by repository target
SOURCE_CONTROL_CACHE: dict[str, SourceControlContext] = {}


def _get_cache_key(repository_id: int, repository_url: str | None = None) -> str:
    """Generate cache key for a repository target."""
    if repository_url:
        return f"source_control_{repository_id}_{repository_url}"
    return f"source_control_{repository_id}"


def _get_cached_context(
    repository_id: int,
    repository_url: str | None = None,
) -> tuple[str, SourceControlContext | None]:
    """Get cached context for a repository if it exists."""
    cache_key = _get_cache_key(repository_id, repository_url)
    return cache_key, SOURCE_CONTROL_CACHE.get(cache_key)


async def get_source_control_cache_key(
    repository_id: int,
    provider: str,
    repository_url: str | None = None,
) -> str:
    """Get or create a cached source control context for the repository.

    This function is provider-agnostic and works with any supported source control
    provider (GitHub, GitLab, etc.).

    Args:
        repository_id: The ID of the repository configuration in the database
        provider: Source control provider for the analyze request
        repository_url: Optional repository URL override for provider-specific flows

    Returns:
        Cache key for the source control context
    """
    cache_key, cached_context = _get_cached_context(repository_id, repository_url)
    if cached_context:
        return cache_key

    async with database.session_scope() as session:
        source_control_service = SourceControlService(session)
        client, access_token, repo_url = await source_control_service.get_client_for_repository(
            repository_id,
            provider,
            repository_url,
        )

    if not access_token or not repo_url:
        raise RuntimeError(
            "Source control service did not provide access_token or repo_url"
        )

    SOURCE_CONTROL_CACHE[cache_key] = {
        "client": client,
        "access_token": access_token,
        "repo_url": repo_url,
    }

    return cache_key


def get_repository_file_paths(cache_key: str) -> list[str]:
    """Get all file paths in the repository.

    This function is provider-agnostic and uses the cached source control client
    to fetch the repository tree.

    Args:
        cache_key: Cache key from get_installation_context_cache_key()

    Returns:
        List of file paths in the repository
    """
    context = SOURCE_CONTROL_CACHE.get(cache_key)
    if not context:
        raise RuntimeError(f"Source control context not found for key: {cache_key}")

    # Return cached paths if available
    cached_paths = context.get("repo_file_paths")
    if isinstance(cached_paths, list):
        return [path for path in cached_paths if isinstance(path, str)]

    # Fetch tree using the abstracted client
    client = context["client"]
    access_token = context["access_token"]
    repo_url = context["repo_url"]

    repo_file_paths = client.get_repository_tree(access_token, repo_url)

    # Cache the paths
    context["repo_file_paths"] = repo_file_paths
    return repo_file_paths


def _fetch_file_content(
    client: SourceControlClient,
    access_token: str,
    repo_url: str,
    file_path: str,
) -> dict[str, str]:
    """Fetch content of a single file using the source control client."""
    file_content = client.get_file_content(access_token, repo_url, file_path)
    return {
        "path": file_content.path,
        "type": file_content.file_type,
        "content": file_content.content,
    }


@tool
def get_repository_content(
    paths: Annotated[
        list[str],
        Field(
            description=(
                "Repository-relative file paths to fetch. Infer these paths from the "
                "stack trace, error message, and the surrounding code that may be "
                "related to the failure. Examples: ['src/main.py'], "
                "['app/services/pricing.py', 'app/models/order.py'], "
                "['backend/api/orders.py', 'backend/services/order_service.py']. "
                "Do not use absolute runtime paths such as '/app/src/main.py'."
            )
        ),
    ],
    installation_cache_key: Annotated[
        str,
        InjectedState("installation_token_internal_key"),
    ],
    repo_file_paths: Annotated[
        list[str],
        InjectedState("repo_file_paths"),
    ],
) -> dict[str, object]:
    """Fetch the content of one or more repository files for the current project.

    Use the paths that most likely match the failing source files mentioned in the
    stack trace. Each path must be relative to the repository root.

    This function is provider-agnostic and works with any supported source control
    provider (GitHub, GitLab, etc.).
    """
    context = SOURCE_CONTROL_CACHE.get(installation_cache_key)
    if not context:
        raise RuntimeError(
            f"Source control context not found for key: {installation_cache_key}"
        )

    client = context["client"]
    access_token = context["access_token"]
    repo_url = context["repo_url"]
    repo_info = client.parse_repo_url(repo_url)

    if not paths:
        raise RuntimeError("At least one repository path is required.")

    available_paths = set(repo_file_paths)
    resolved_paths: list[str] = []

    for path in paths:
        normalized_path = path.strip().lstrip("/")
        if not normalized_path:
            continue

        if normalized_path in available_paths:
            resolved_paths.append(normalized_path)
            continue

        # Try suffix matching for partial paths
        suffix_matches = [
            repo_path for repo_path in repo_file_paths
            if repo_path.endswith(normalized_path)
        ]
        if len(suffix_matches) == 1:
            resolved_paths.append(suffix_matches[0])
            continue

        raise RuntimeError(f"Repository path not found: {normalized_path}")

    if not resolved_paths:
        raise RuntimeError("No valid repository paths were provided.")

    # Fetch files in parallel
    max_workers = min(len(resolved_paths), 8)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                _fetch_file_content,
                client,
                access_token,
                repo_url,
                path,
            )
            for path in resolved_paths
        ]
        files = [future.result() for future in futures]

    return {
        "repo": f"{repo_info.owner}/{repo_info.repo_name}",
        "files": files,
        "token_key": installation_cache_key,
    }


INSTALLATION_TOKEN_CACHE = SOURCE_CONTROL_CACHE
