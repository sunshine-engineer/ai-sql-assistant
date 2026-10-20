"""Deployment boundary: the packaged reviewer app accepts synthetic data only."""
import os
from pathlib import Path
from .config import DEFAULT_DATABASE


def enforce_deployment(config):
    mode = os.environ.get('ASSISTANT_DEPLOYMENT', 'local')
    if mode not in {'local', 'reviewer', 'hosted'}:
        raise ValueError('Unknown deployment policy.')
    if mode == 'reviewer':
        allowed = {DEFAULT_DATABASE.resolve(), (DEFAULT_DATABASE.parent.parent / 'student.db').resolve()}
        if config.kind != 'sqlite' or Path(config.settings.get('path', '')).resolve() not in allowed:
            raise PermissionError('Reviewer deployments permit bundled synthetic datasets only.')

    if mode == 'hosted' and (config.kind not in ('postgres','mysql') or not config.hosted or not config.principal or not config.approved_columns or not config.settings.get('tls_ca')):
        raise PermissionError('Hosted mode requires authenticated, scoped, TLS connections.')
