"""Session history with bounded model context."""
import hashlib
import json

GREETING = {'role': 'assistant', 'content': 'How can I help you?'}


def reset_for_database(state, identity, clear=False):
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if clear or state.get('database_identity') != digest:
        state['messages'] = [dict(GREETING)]
        state['database_identity'] = digest


def context_messages(messages):
    return [{'role': item['role'], 'content': item['content'][:2000]}
            for item in messages[-8:]]
