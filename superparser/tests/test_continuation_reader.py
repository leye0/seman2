"""Integration smoke tests. Run inside the real Seman2 repository."""
from __future__ import annotations
from pathlib import Path
from seman_parser.continuation_reader import ContinuationReader, ContinuationCounts
DATA=Path(__file__).resolve().parents[1]/'data'


def test_counts_roundtrip(tmp_path):
    model=ContinuationCounts()
    model.observe('NP',('DET',),'N','N',2.0)
    model.observe('NP',('DET',),'N','ADJ',0.2)
    p=tmp_path/'c.json'
    model.save(p)
    recovered=ContinuationCounts.load(p)
    assert recovered.probability('NP',('DET',),'N','N') > recovered.probability('NP',('DET',),'N','ADJ')


def test_a_short_sentence_is_incremental_and_has_no_fallback():
    parser=ContinuationReader.from_dir(DATA,max_steps=10000)
    result=parser.parse('The child laughed.')
    assert result.completed, result.stats
    assert result.item is not None and result.item.category=='CLAUSE'
    assert result.stats['fallback'] is False
    assert result.stats['frames_opened'] < 150, result.stats


def test_a_transitive_sentence_completes():
    parser=ContinuationReader.from_dir(DATA,max_steps=20000)
    result=parser.parse('The gardener watered the roses.')
    assert result.completed, result.stats
    assert result.stats['fallback'] is False


def test_invalid_input_cannot_be_accepted():
    parser=ContinuationReader.from_dir(DATA,max_steps=3000)
    result=parser.parse('the the the the.')
    assert not result.completed
    assert result.stats['fallback'] is False


def test_pp_ambiguity_not_claimed_exhaustive():
    parser=ContinuationReader.from_dir(DATA,max_steps=30000)
    result=parser.parse('I saw the man with a telescope.')
    assert result.completed, result.stats
    assert result.stats['alternatives_exhaustively_enumerated'] is False
