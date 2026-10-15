"""Integration contracts against *real* Seman2 resources when running in checkout.

These tests intentionally fail on a real lexical/grammar mismatch rather than
pretending fixture coverage means production compatibility.
"""
from pathlib import Path
import pytest

DATA = Path(__file__).resolve().parents[1] / 'data'
if not (DATA / 'grammar.jsonl').exists():
    pytest.skip('Full Seman2 runtime not mounted here', allow_module_level=True)

from seman_parser.reading_kernel_adapter import SemanReadingKernel

@pytest.fixture(scope='module')
def kernel():
    return SemanReadingKernel.from_dir(DATA)

@pytest.mark.parametrize('text', [
    'The recipe Rosa followed failed.',
    'Are the keys inside the box?',
    'The teacher listed dates, places, and names.',
])
def test_real_grammar_native_recognition(kernel, text):
    r = kernel.parse(text)
    assert r.complete, {'text': text, 'failure': r.outcome.reason,
                        'trace': [e.as_dict() for e in r.outcome.events]}
    assert r.item.category == 'CLAUSE'
    assert r.outcome.counters.get('constructions', 0) <= 16
    assert r.outcome.counters.get('unifications', 0) <= 20
    assert r.outcome.counters.get('consumptions', 0) <= 10


def test_unavailable_syntax_no_production_fallback(kernel):
    r = kernel.parse('the the the the.')
    assert not r.complete
    assert r.item is None
