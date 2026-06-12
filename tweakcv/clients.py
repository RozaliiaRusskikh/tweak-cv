"""Shared singleton clients for Slack and Langfuse.

All nodes import from here so there is exactly one client instance per process.
"""

from langfuse import Langfuse
from slack_sdk import WebClient

from tweakcv.settings import settings

_slack_client: WebClient | None = None
_langfuse_client: Langfuse | None = None


def get_slack() -> WebClient:
    global _slack_client
    if _slack_client is None:
        _slack_client = WebClient(token=settings.slack_bot_token.get_secret_value())
    return _slack_client


def get_langfuse() -> Langfuse:
    global _langfuse_client
    if _langfuse_client is None:
        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key.get_secret_value(),
            secret_key=settings.langfuse_secret_key.get_secret_value(),
            host=settings.langfuse_host,
        )
    return _langfuse_client
