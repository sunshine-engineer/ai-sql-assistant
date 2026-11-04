"""Application settings shared by the UI and runtime; no framework side effects."""
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MODEL = 'qwen/qwen3.8-27b'
DEFAULT_DATABASE = Path(__file__).resolve().parent.parent / 'data' / 'retail-v1.db'


@dataclass
class AppConfig:
    kind: str
    settings: dict = field(repr=False)
    schema: str | None = None
    api_key: str = field(default='', repr=False)
    model_name: str = DEFAULT_MODEL
    approved_columns: dict | None = None
    principal: str | None = field(default=None, repr=False)
    hosted: bool = False

    @property
    def ready(self) -> bool:
        return bool(self.api_key and all(self.settings.values()))

    @property
    def database_identity(self) -> list:
        """Used only for the session fingerprint; never sent to the model."""
        identity = [self.kind, self.settings, self.schema]
        if self.principal or self.approved_columns:
            identity += [self.principal, self.approved_columns]
        return identity
