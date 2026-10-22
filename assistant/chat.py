"""Session history with bounded model context.

File: assistant/chat.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import hashlib
import json

GREETING = {"role": "assistant", "content": "How can I help you?"}


def reset_for_database(state, identity, clear=False):
    """Clear conversation and analysis context when the database identity changes.

    Args:
        state: Mutable session-state mapping.
        identity: Connection and access-scope inputs hashed to detect database changes.
        clear: Whether to reset the conversation even when the identity is unchanged.
    """
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if clear or state.get("database_identity") != digest:
        state["messages"] = [dict(GREETING)]
        state["database_identity"] = digest
        state["analysis_context"] = {}


def context_messages(messages):
    """Bound provider history to the last eight messages and 2,000 characters per message.

    Args:
        messages: Conversation messages supplied to the workflow or model.

    Returns:
        list[dict]: Bounded role/content pairs without query reports.
    """
    return [{"role": item["role"], "content": item["content"][:2000]} for item in messages[-8:]]
