"""Integration tests on actual Seman2 grammar and WordNet; not a fixture substitute."""
from pathlib import Path
import pytest

DATA = Path(__file__).resolve().parents[1] / 'data'
if not (DATA / 'grammar.jsonl').exists():
    pytest.skip('Actual Seman2 grammar and lexicon not available here', allow_module_level=True)

from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader


@pytest.fixture(scope='module')
def machine():
    return SemanCompiledReader.from_dir(DATA)


@pytest.mark.parametrize('text', [
    'The recipe Rosa followed failed.',
    'Are the keys inside the box?',
    'The teacher listed dates, places, and names.',
    'The document Emma examined disappeared.',
    'Were the papers behind the desk?',
    'The editor cataloged poems, songs, and stories.',
    'Are the keys still inside the box?',
    'The teacher listed dates and names.',
    'The teacher listed dates, places, times, and names.',
])
def test_compiled_reading(machine, text):
    r = machine.parse(text)
    assert r.complete, {'reason': r.outcome.reason,
                        'events': [e.as_dict() for e in r.outcome.events]}
    assert r.item.category == 'CLAUSE'
    assert r.outcome.counters.get('unifications', 0) <= 25
    assert r.outcome.counters.get('consumptions', 0) <= 12


def test_nonlanguage_stops_without_search(machine):
    r = machine.parse('the the the the.')
    assert not r.complete
    assert r.item is None
    assert r.outcome.events[-1].action == 'STOP'
