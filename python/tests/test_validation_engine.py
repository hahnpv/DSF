"""
Unit tests for the GUI cycle-detection algorithm (no Qt required).

Regression coverage for the review fix [A26]: the old DFS returned early on a
cycle without unwinding its path set, which poisoned later DFS roots (falsely
flagging unrelated blocks) and marked feeder nodes as cycle members.
"""
from dsf.gui.core.validation_engine import ValidationEngine


def cyc(adj):
    return ValidationEngine._detect_cycles(adj)


def test_no_cycle():
    assert cyc({"A": ["B"], "B": ["C"], "C": []}) == set()


def test_simple_cycle():
    assert cyc({"A": ["B"], "B": ["C"], "C": ["A"]}) == {"A", "B", "C"}


def test_feeder_into_cycle_not_flagged():
    # D feeds into a B->C->B cycle. The old code flagged D and never recovered.
    adj = {"A": ["B"], "B": ["C"], "C": ["B"], "D": ["A"]}
    assert cyc(adj) == {"B", "C"}


def test_self_loop():
    assert cyc({"A": ["A"], "B": []}) == {"A"}


def test_two_independent_cycles():
    adj = {"A": ["B"], "B": ["A"], "X": ["Y"], "Y": ["X"], "Z": []}
    assert cyc(adj) == {"A", "B", "X", "Y"}


def test_dag_diamond_no_false_positive():
    # Diamond A->B, A->C, B->D, C->D is acyclic; the old path-poisoning bug
    # could flag nodes here after visiting a shared descendant.
    adj = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
    assert cyc(adj) == set()
