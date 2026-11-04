"""Result-referenced answer facts; unverified model prose is never displayed."""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import json
import math
import re

MAX_FACTS = 32


@dataclass
class AnswerAssessment:
    status: str
    reason: str | None
    answer: str
    facts: list = field(default_factory=list)
    displayed_verified: bool = True

    @property
    def model_verified(self):
        return self.status == 'verified'

    def summary(self):
        """Safe operational metadata: exclude text, facts, values and result data."""
        return {'status': self.status, 'reason': self.reason,
                'model_verified': self.model_verified,
                'displayed_verified': self.displayed_verified, 'fact_count': len(self.facts)}


def _cell(value):
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)  # Matches the tool's default=str serialization.


def _equal(value, actual):
    if isinstance(actual, bool) or isinstance(value, bool):
        return type(value) is type(actual) and value == actual
    if isinstance(actual, (int, float, Decimal)):
        if not isinstance(value, (int, float, str)) or isinstance(value, bool):
            return False
        # Numeric strings are accepted only when the DBAPI serializes Decimal as text.
        if isinstance(value, str) and not isinstance(actual, Decimal):
            return False
        try:
            a, b = Decimal(str(actual)), Decimal(str(value))
            if not a.is_finite() or not b.is_finite():
                return False
            if isinstance(actual, (int, Decimal)):
                return a == b
            return abs(a-b) <= max(Decimal('1e-12'), abs(a)*Decimal('1e-12'))
        except InvalidOperation:
            return False
    expected = _cell(actual)
    return type(value) is type(expected) and value == expected


def result_facts(result, limit=8):
    facts = []
    for row_index, row in enumerate(result['rows']):
        for column_index, value in enumerate(row):
            facts.append({'result_id': result['result_id'], 'row': row_index,
                          'column': column_index, 'value': _cell(value)})
            if len(facts) >= limit:
                return facts
    return facts



def _markdown_text(value):
    text = str(value).replace('\n', '\\n').replace('\r', '\\r')
    return re.sub(r'([\\`*_{}\[\]()<>#+.!|~-])', r'\\\1', text)


def render_facts(facts, result, fallback=False):
    if not result['rows']:
        text = 'The executed query returned no rows.'
    else:
        text = ('The model summary could not be verified. Showing result-backed values:'
                if fallback else 'Verified query values:')
        lines = []
        for fact in facts:
            value = json.dumps(fact['value'], ensure_ascii=True, allow_nan=False)
            if len(value) > 300:
                value = value[:300] + '… (display shortened; see the result table)'
            column = str(result['columns'][fact['column']])
            lines.append(f"- {_markdown_text(column)}: {_markdown_text(value)} [{fact['result_id']}:r{fact['row']}:c{fact['column']}]")
        text += '\n\n' + '\n'.join(lines) + '\n\nSee the result table for all returned rows and columns.'
    if result.get('truncated'):
        text += '\nThis is a partial result; it does not establish complete totals.'
    return text


def deterministic_answer(result):
    facts = result_facts(result)
    return AnswerAssessment('deterministic', None, render_facts(facts, result), facts)


def _unique_keys(pairs):
    document = {}
    for key, value in pairs:
        if key in document:
            raise ValueError('duplicate_key')
        document[key] = value
    return document


def _reject_constant(value):
    raise ValueError('nonfinite_number')


def assess_answer(content, result):
    """Validate a strict facts JSON object against the final executed result.

    This certifies cell/value references, not business semantics or completeness.
    Free-form prose is unsupported: even apparently correct prose is not certified.
    A rejected candidate falls back to deterministic, cited result values.
    """
    if not result or result.get('error') or not result.get('result_id'):
        return AnswerAssessment('unavailable', 'unusable_result',
                                'No usable query result is available.', displayed_verified=False)
    reason = None
    facts = []
    try:
        if not isinstance(content, str) or len(content) > 16000:
            raise ValueError('structured_answer_required')
        document = json.loads(content, object_pairs_hook=_unique_keys, parse_constant=_reject_constant)
        if not isinstance(document, dict) or set(document) != {'facts'}:
            raise ValueError('structured_answer_required')
        claims = document['facts']
        if not isinstance(claims, list) or len(claims) > MAX_FACTS:
            raise ValueError('invalid_facts')
        if not claims and result['rows']:
            raise ValueError('missing_facts')
        seen = set()
        for claim in claims:
            if not isinstance(claim, dict) or set(claim) != {'result_id', 'row', 'column', 'value'}:
                raise ValueError('invalid_reference')
            if claim['result_id'] != result['result_id']:
                raise ValueError('wrong_result_reference')
            row, column = claim['row'], claim['column']
            if (type(row) is not int or type(column) is not int or
                    not 0 <= row < len(result['rows']) or not 0 <= column < len(result['columns'])):
                raise ValueError('invalid_cell_reference')
            if (row, column) in seen:
                raise ValueError('duplicate_reference')
            seen.add((row, column))
            actual = result['rows'][row][column]
            if not _equal(claim['value'], actual):
                raise ValueError('value_mismatch')
            facts.append({'result_id': result['result_id'], 'row': row,
                          'column': column, 'value': _cell(actual)})
        return AnswerAssessment('verified', None, render_facts(facts, result), facts)
    except json.JSONDecodeError:
        reason = 'structured_answer_required'
    except (ValueError, RecursionError) as exc:
        reason = str(exc) if isinstance(exc, ValueError) else 'invalid_answer'
    # Never echo the rejected candidate or validation exception text into a trace.
    allowed = {'structured_answer_required', 'invalid_facts', 'missing_facts',
               'invalid_reference', 'wrong_result_reference', 'invalid_cell_reference',
               'duplicate_reference', 'value_mismatch', 'duplicate_key', 'nonfinite_number'}
    reason = reason if reason in allowed else 'invalid_answer'
    facts = result_facts(result)
    return AnswerAssessment('rejected', reason, render_facts(facts, result, fallback=True), facts)
