import base64
from concurrent.futures import ThreadPoolExecutor
import json
from typing import Annotated
from urllib.parse import quote, urlparse
from urllib import error, request

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import Field

from src.config import get_settings

INSTALLATION_TOKEN_CACHE: dict[str, dict[str, str]] = {}


def _get_installation_cache_key(project_id: int) -> str:
    return f"installation_token_{project_id}"


def _get_cached_installation(project_id: int) -> tuple[str, dict[str, str] | None]:
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


def get_installation_context(project_id: int) -> str:
    cache_key, cached_installation = _get_cached_installation(project_id)
    if cached_installation:
        return cache_key

    settings = get_settings()
    url = f"{settings.auth_server.base_url.rstrip('/')}/source_control/access_token"
    payload = json.dumps({"project_id": project_id}).encode("utf-8")

    http_request = request.Request(
        url=url,
        data=payload,
        headers={
            "accept": "application/json",
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(http_request) as response:
            response_body = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Failed to get installation token: {exc.code} {error_body}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(
            f"Failed to connect to auth server: {exc.reason}"
        ) from exc

    installation_data = response_body.get("data", {})
    access_token = installation_data.get("access_token")
    repo_url = installation_data.get("repo_url")
    if not access_token or not repo_url:
        raise RuntimeError(
            "Auth server response did not include data.access_token or data.repo_url"
        )

    INSTALLATION_TOKEN_CACHE[cache_key] = {
        "access_token": access_token,
        "repo_url": repo_url,
    }

    return cache_key


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

    max_workers = min(len(paths), 8)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                _fetch_repository_content,
                owner,
                repo,
                installation_context["access_token"],
                path,
            )
            for path in paths
        ]
        files = [future.result() for future in futures]

    return {
        "repo": f"{owner}/{repo}",
        "files": files,
        "token_key": installation_cache_key,
    }
