from datetime import datetime, timedelta, timezone

from src.services.source_control_models import IssuedAccessToken
from src.services.source_controlers.base import SourceControlClient


class GitLabSourceControl(SourceControlClient):
    """GitLab source control client using Personal Access Token (PAT)."""

    def __init__(self, access_token: str) -> None:
        self.access_token = access_token

    def issue_access_token(self, repo_url: str) -> IssuedAccessToken:
        """
        For GitLab PAT, we simply return the stored access token.
        PATs don't have a built-in expiration tracking mechanism via API,
        so we return None for expires_at.
        """
        return IssuedAccessToken(
            access_token=self.access_token,
            expires_at=None,
        )
