import base64
from concurrent.futures import ThreadPoolExecutor
import json
from typing import Annotated, NotRequired, TypedDict
from urllib.parse import quote, urlparse
from urllib import error, request

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import Field

from src.apis.models.source_control import ProjectInfo
from src.core import database
from src.services.source_control_service import SourceControlService


class InstallationContext(TypedDict):
    access_token: str
    repo_url: str
    repo_file_paths: NotRequired[list[str]]


INSTALLATION_TOKEN_CACHE: dict[str, InstallationContext] = {}


def _get_installation_cache_key(project_id: int) -> str:
    return f"installation_token_{project_id}"


def _get_cached_installation(project_id: int) -> tuple[str, InstallationContext | None]:
    cache_key = _get_installation_cache_key(project_id)
    return cache_key, INSTALLATION_TOKEN_CACHE.get(cache_key)


def _parse_github_repo(repo_url: str) -> tuple[str, str]:
    parsed_url = urlparse(repo_url)
    path_parts = [part for part in parsed_url.path.strip("/").split("/") if part]
    if len(path_parts) < 2:
        raise RuntimeError(f"Invalid GitHub repo_url: {repo_url}")

    owner = path_parts[0]
    repo = path_parts[1].removesuffix(".git")
    return owner, repo


async def get_installation_context_cache_key(project_id: int) -> str:
    cache_key, cached_installation = _get_cached_installation(project_id)
    if cached_installation:
        return cache_key

    async with database.session_scope() as session:
        source_control_service = SourceControlService(session)
        installation_data = await source_control_service.issue_access_token(
            ProjectInfo(project_id=project_id)
        )

    access_token = installation_data.access_token
    repo_url = str(installation_data.repo_url)
    if (
        not isinstance(access_token, str)
        or not access_token
        or not isinstance(repo_url, str)
        or not repo_url
    ):
        raise RuntimeError(
            "Source control service did not provide access_token or repo_url"
        )

    INSTALLATION_TOKEN_CACHE[cache_key] = {
        "access_token": access_token,
        "repo_url": repo_url,
    }

    return cache_key


def get_repository_file_paths(installation_cache_key: str) -> list[str]:
    installation_context = INSTALLATION_TOKEN_CACHE.get(installation_cache_key)
    if not installation_context:
        raise RuntimeError(
            f"Installation context not found for key: {installation_cache_key}"
        )

    cached_paths = installation_context.get("repo_file_paths")
    if isinstance(cached_paths, list):
        return [path for path in cached_paths if isinstance(path, str)]

    owner, repo = _parse_github_repo(installation_context["repo_url"])
    access_token = installation_context["access_token"]

    repo_request = request.Request(
        url=f"https://api.github.com/repos/{owner}/{repo}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {access_token}",
            "X-GitHub-Api-Version": "2026-03-10",
        },
        method="GET",
    )

    try:
        with request.urlopen(repo_request) as response:
            repo_response = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Failed to get repository metadata: {exc.code} {error_body}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(
            f"Failed to connect to GitHub API: {exc.reason}"
        ) from exc

    default_branch = repo_response.get("default_branch")
    if not isinstance(default_branch, str) or not default_branch:
        raise RuntimeError("Repository metadata did not include default_branch")

    tree_request = request.Request(
        url=f"https://api.github.com/repos/{owner}/{repo}/git/trees/{quote(default_branch, safe='')}?recursive=1",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {access_token}",
            "X-GitHub-Api-Version": "2026-03-10",
        },
        method="GET",
    )

    try:
        with request.urlopen(tree_request) as response:
            tree_response = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Failed to get repository tree: {exc.code} {error_body}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(
            f"Failed to connect to GitHub API: {exc.reason}"
        ) from exc

    tree_items = tree_response.get("tree", [])
    if not isinstance(tree_items, list):
        raise RuntimeError("Repository tree response did not include a valid tree")

    repo_file_paths = [
        item["path"]
        for item in tree_items
        if isinstance(item, dict)
        and item.get("type") == "blob"
        and isinstance(item.get("path"), str)
    ]
    installation_context["repo_file_paths"] = repo_file_paths
    return repo_file_paths


def _fetch_repository_content(
    owner: str,
    repo: str,
    access_token: str,
    path: str,
) -> dict[str, str]:
    normalized_path = path.strip().lstrip("/")
    if not normalized_path:
        raise RuntimeError("A repository path is required.")

    encoded_path = quote(normalized_path, safe="/")
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded_path}"
    http_request = request.Request(
        url=url,
        headers={
            "Accept": "application/vnd.github.object+json",
            "Authorization": f"Bearer {access_token}",
            "X-GitHub-Api-Version": "2026-03-10",
        },
        method="GET",
    )

    try:
        with request.urlopen(http_request) as response:
            response_body = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Failed to get repository content for '{normalized_path}': "
            f"{exc.code} {error_body}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(
            f"Failed to connect to GitHub API: {exc.reason}"
        ) from exc

    content = response_body.get("content", "")
    encoding = response_body.get("encoding")
    if encoding == "base64" and content:
        decoded_content = base64.b64decode(content).decode("utf-8", errors="replace")
    else:
        decoded_content = content

    return {
        "path": response_body.get("path", normalized_path),
        "type": response_body.get("type", ""),
        "content": decoded_content,
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
    """
    installation_context = INSTALLATION_TOKEN_CACHE.get(installation_cache_key)
    if not installation_context:
        raise RuntimeError(
            f"Installation context not found for key: {installation_cache_key}"
        )

    owner, repo = _parse_github_repo(installation_context["repo_url"])
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

        suffix_matches = [
            repo_path for repo_path in repo_file_paths
            if repo_path.endswith(normalized_path)
        ]
        if len(suffix_matches) == 1:
            resolved_paths.append(suffix_matches[0])
            continue

        raise RuntimeError(
            f"Repository path not found: {normalized_path}"
        )

    if not resolved_paths:
        raise RuntimeError("No valid repository paths were provided.")

    max_workers = min(len(resolved_paths), 8)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                _fetch_repository_content,
                owner,
                repo,
                installation_context["access_token"],
                path,
            )
            for path in resolved_paths
        ]
        files = [future.result() for future in futures]

    return {
        "repo": f"{owner}/{repo}",
        "files": files,
        "token_key": installation_cache_key,
    }
