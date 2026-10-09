"""Probe key constructions from unfixed sentences (substrings, not whole sentences)."""
import sys
sys.path.insert(0, '.')
from seman_parser.engine import Parser

p = Parser.from_dir('data', goal_category='CLAUSE')
p2 = Parser.from_dir('data', goal_category='NP')
p3 = Parser.from_dir('data', goal_category='VP')
p4 = Parser.from_dir('data', goal_category='PP')
p5 = Parser.from_dir('data', goal_category='ADJP')
p6 = Parser.from_dir('data', goal_category='WH-CLAUSE')
p7 = Parser.from_dir('data', goal_category='ADVP')
for x in (p, p2, p3, p4, p5, p6, p7):
    x.parse('warm up')

probes = [
    # #7
    ('NP', 'the bathroom'),
    ('VP', 'needed the bathroom'),
    ('CLAUSE', 'somebody always needed the bathroom'),
    ('CLAUSE', 'somebody else was late'),
    ('NP', 'somebody else'),
    ('NP', 'everyone else'),
    ('CLAUSE', 'Mom worked during the day'),
    ('CLAUSE', 'Mom worked during the day, Dad sometimes worked from home'),
    ('CLAUSE', 'Mom worked during the day, Dad worked from home, Eli was learning to read'),
    ('CLAUSE', 'Eli was learning to read longer sentences'),
    ('VP', 'was learning to read longer sentences'),
    ('NP', 'longer sentences'),
    ('CLAUSE', 'somebody always needed the bathroom when somebody else was late'),
    ('WH-CLAUSE', 'when somebody else was late'),
    # #63
    ('CLAUSE', 'Maya could describe the red door'),
    ('CLAUSE', 'she realized that visitors would also need the street'),
    ('VP', 'realized that visitors would also need the street'),
    ('VP', 'would also need the street'),
    ('NP', 'the red door'),
    ('NP', 'the street, the intersection, and perhaps a number'),
    ('NP', 'perhaps a number'),
    ('CLAUSE', 'visitors would also need the street, the intersection, and perhaps a number'),
    # #121
    ('CLAUSE', 'Beneath them she wrote'),
    ('CLAUSE', 'she wrote: What changes'),
    ('CLAUSE', 'What changes when you do the same job'),
    ('CLAUSE', 'you do the same job in a hurry rather than carefully'),
    ('PP', 'in a hurry'),
    ('ADVP', 'rather than carefully'),
    ('ADVP', 'in a hurry rather than carefully'),
    ('WH-CLAUSE', 'What changes when you do the same job in a hurry rather than carefully'),
    # #141
    ('CLAUSE', 'The missing lunch had been funny'),
    ('CLAUSE', 'The missing lunch had been funny for everyone else'),
    ('CLAUSE', 'she had been frightened of not having food'),
    ('VP', 'had been frightened of not having food'),
    ('PP', 'of not having food'),
    ('VP', 'not having food'),
    ('CLAUSE', 'she had been frightened of not having food when she needed it'),
    # #171
    ('CLAUSE', 'One said'),
    ('CLAUSE', 'I know what happened'),
    ('CLAUSE', 'How do you know'),
    ('CLAUSE', 'Maya let both characters ask questions'),
    ('NP', 'both characters'),
    ('VP', 'let both characters ask questions'),
    ('CLAUSE', 'the disagreement became more specific'),
    ('ADJP', 'more specific'),
    ('CLAUSE', 'Maya let both characters ask questions until the disagreement became more specific'),
    # #255
    ('CLAUSE', 'Information has a source'),
    ('CLAUSE', 'a useful reader asks who made it'),
    ('WH-CLAUSE', 'who made it'),
    ('WH-CLAUSE', 'how that person could know'),
    ('NP', 'a useful reader'),
    ('CLAUSE', 'a useful reader asks who made it, when, why, and how that person could know'),
    # #272
    ('CLAUSE', 'She first divided a circle into four pieces'),
    ('VP', 'divided a circle into four pieces'),
    ('CLAUSE', 'realized that four equal quarters could not give six people one piece each'),
    ('VP', 'could not give six people one piece each'),
    ('NP', 'four equal quarters'),
    ('NP', 'one piece each'),
    ('NP', 'six people'),
    ('CLAUSE', 'four equal quarters could not give six people one piece each'),
]

parsers = {'CLAUSE': p, 'NP': p2, 'VP': p3, 'PP': p4, 'ADJP': p5, 'WH-CLAUSE': p6, 'ADVP': p7}
for goal, text in probes:
    r = parsers[goal].parse(text)
    ok = r.result.completed
    print(f'{"OK  " if ok else "FAIL"} [{goal:10s}] {text}')
