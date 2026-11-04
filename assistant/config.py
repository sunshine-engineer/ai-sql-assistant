"""Application settings shared by the UI and runtime; no framework side effects.

File: assistant/config.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Defaults remain code-level inputs: callers can override request and query limits
# explicitly; deployment secrets are never initialized at module import time.
DEFAULT_MODEL = "qwen/qwen3.8-27b"
DEFAULT_REQUEST_SECONDS = 60
DEFAULT_REQUEST_TOKENS = 60_000
DEFAULT_OUTPUT_TOKENS = 1_500
DEFAULT_PROVIDER_TIMEOUT_SECONDS = 20
DEFAULT_CONNECT_TIMEOUT_SECONDS = 5
DEFAULT_QUERY_ROWS = 200
DEFAULT_QUERY_TIMEOUT_MS = 5_000
DEFAULT_BENCHMARK_SECONDS = 120
DEFAULT_REQUESTS_PER_MINUTE = 30
DEFAULT_TOKENS_PER_MINUTE = 8_000
EVALUATION_DIRECTORY = PROJECT_ROOT / "evaluation"
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "retail-v1.db"


@dataclass
class AppConfig:
    """Store request connection settings while excluding credentials from representation.

    Attributes:
        kind: Database kind.
        settings: Runtime connection settings, excluded from repr.
        schema: Optional remote schema.
        api_key: Provider credential, excluded from repr.
        model_name: Provider model identifier.
        approved_columns: Optional hosted view projection.
        principal: Verified hosted email, excluded from repr.
        hosted: Whether authenticated hosted restrictions apply.
    """

    kind: str
    settings: dict = field(repr=False)
    schema: str | None = None
    api_key: str = field(default="", repr=False)
    model_name: str = DEFAULT_MODEL
    approved_columns: dict | None = None
    principal: str | None = field(default=None, repr=False)
    hosted: bool = False

    @property
    def ready(self) -> bool:
        """Report whether a provider key and every supplied connection setting are populated.

        Returns:
            bool: Whether the supplied request settings are populated.
        """
        return bool(self.api_key and all(self.settings.values()))

    @property
    def database_identity(self) -> list:
        """Return connection and access-scope identity inputs for session reset hashing.

        Returns:
            list: Identity inputs for session fingerprinting; never send to the model.
        """
        identity = [self.kind, self.settings, self.schema]
        if self.principal or self.approved_columns:
            identity += [self.principal, self.approved_columns]
        return identity
