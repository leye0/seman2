"""Seman2 POC 3: grammar/feature validation of a packed parglare GLR forest.

Usage (from superparser):
  PYTHONPATH=. python -u research/lr_probe/glr_forest_validate.py

No production edits, no enumeration of all parse trees. This checks whether at
least one analysis of the shared forest respects Seman2's unification/requires
contract. It does NOT prove full linguistic or semantic correctness.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import resource
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from parglare import GLRParser
from parglare.glr import Parent
from parglare.parser import Token
from parglare.trees import NodeNonTerm, NodeTerm

from seman_parser.engine import ParserResources
from seman_parser.features import FeatureStructure, Variable, unify
from seman_parser.grammar import parse_rule
from seman_parser.predictive import CompactNode, PredictiveParser
from seman_parser.segmentation import build_lattice
from seman_parser.symbols import intern

# Reuse EXACTLY the grammar/cache and lexical refinement of the previous POC.
from glr_feature_probe import META, ROOT, candidate_edges, load_table

RESULT_PATH = ROOT / "forest_validation_10.json"
MAX_PARSE_S = 3.0
MAX_VALIDATE_S = 3.5
MAX_PROCESS_S = 8.0
MAX_OPERATIONS = 200_000
MAX_SIGNATURES_PER_NODE = 2_000
MEMORY_MB = 768

# Genuine sentences and deliberately malformed probes. The expected column
# is for *diagnosis*, not used to bias or force acceptance/rejection.
TESTS = [
    ("fronted_pp", "After school, Maya made a snow person with Jonah.", True),
    ("simple_transitive", "The nurse counted pills and bandages.", True),
    ("simple_intransitive", "The train arrived.", True),
    ("relative", "The key that Oliver found disappeared.", True),
    ("sentential_complement", "Julia explained that the engine needed fuel.", True),
    ("infinitive", "She wanted to understand both.", True),
    ("gerund", "Making mistakes teaches humility.", True),
    ("bad_agreement", "The dogs runs.", False),
    ("bad_valency", "The boy sleeps the table.", False),
    ("bad_agreement_2", "The train sleep.", False),
]


def features_key(node):
    # Stable enough for POC; do not collapse distinct grammatical evidence.
    return (
        tuple(sorted((key, repr(value)) for key, value in node.features.items())),
        tuple(sorted(node.evidence)),
    )


def bindings_key(bindings):
    return tuple(sorted((key, repr(value)) for key, value in bindings.items()))


@dataclass(slots=True)
class Reading:
    node: CompactNode
    front_pp_root: bool = False


class BudgetExceeded(Exception):
    pass


class ForestValidator:
    def __init__(self, forest, grammar_metadata, lexical_candidates, text, rules):
        self.root = forest.result  # Parglare's packed root, NOT forest.get_tree()
        self.text = text
        self.rule_map = {
            (row["lhs"], tuple(row["rhs"])): row["ids"]
            for row in grammar_metadata["rule_map"]
        }
        self.rules = rules
        self.term_specs = grammar_metadata["terminals"]
        self.lexical = defaultdict(list)
        for candidate in lexical_candidates:
            self.lexical[(candidate.span_start, candidate.span_end, candidate.category)].append(candidate)
        self.memo = {}
        self.visiting = set()
        self.operations = 0
        self.nodes = 0
        self.valid_reductions = 0
        self.rejected_reductions = 0
        self.invalid_evidence = 0
        self.deadline = time.perf_counter() + MAX_VALIDATE_S

    def tick(self):
        self.operations += 1
        if self.operations > MAX_OPERATIONS:
            raise BudgetExceeded("operation_limit")
        if self.operations % 256 == 0 and time.perf_counter() > self.deadline:
            raise BudgetExceeded("validation_time_limit")

    def compact(self, readings):
        best = {}
        for reading in readings:
            key = (features_key(reading.node), reading.front_pp_root)
            previous = best.get(key)
            if previous is None or reading.node.score > previous.node.score:
                best[key] = reading
            if len(best) > MAX_SIGNATURES_PER_NODE:
                raise BudgetExceeded("signature_limit")
        return list(best.values())

    def solve(self, obj):
        identity = id(obj)
        if identity in self.memo:
            return self.memo[identity]
        if identity in self.visiting:
            # Cyclic packed structures require a fixpoint algorithm; do not
            # silently call this a grammatical rejection.
            raise BudgetExceeded("cyclic_forest_requires_fixpoint")
        self.visiting.add(identity)
        self.nodes += 1
        self.tick()
        try:
            if isinstance(obj, Parent):
                options = []
                for alt in obj.possibilities:
                    options.extend(self.solve(alt))
                result = self.compact(options)
            elif isinstance(obj, NodeTerm):
                result = self.terminal(obj)
            elif isinstance(obj, NodeNonTerm):
                result = self.nonterminal(obj)
            else:
                raise TypeError(f"unexpected forest node: {type(obj).__name__}")
            self.memo[identity] = result
            return result
        finally:
            self.visiting.remove(identity)

    def terminal(self, obj):
        name = obj.symbol.name
        spec = self.term_specs.get(name)
        if spec is None:
            return []
        cat = spec["category"]
        # A terminal can match several distinct lexical senses. Maintain
        # those readings until they are distinguishable by grammar features.
        candidates = self.lexical.get((obj.start_position, obj.end_position, cat), ())
        result = []
        constraints = FeatureStructure.build(spec["features"])
        for candidate in candidates:
            self.tick()
            if any(not candidate.features.has(name) or
                   isinstance(candidate.features.get(name), Variable)
                   for name in spec["requires"]):
                self.invalid_evidence += 1
                continue
            if unify(constraints, candidate.features) is None:
                continue
            evidence = frozenset(
                name for name, val in candidate.features.items()
                if not isinstance(val, Variable)
            )
            node = CompactNode(
                candidate.category, intern(candidate.category),
                candidate.span_start, candidate.span_end,
                candidate.features, evidence,
                candidate.score, candidate=candidate
            )
            result.append(Reading(node))
        return self.compact(result)

    def nonterminal(self, obj):
        prod = obj.production
        key = (prod.symbol.name, tuple(s.name for s in prod.rhs))
        identifiers = self.rule_map.get(key, ())
        if not identifiers:
            # The synthesized DOCUMENT start production is transparent.
            if key == ("DOCUMENT", ("NT_CLAUSE",)):
                return self.solve(obj.children[0])
            raise ValueError(f"production not in metadata: {key}")

        # Evaluate only RHS children actually occurring in this packed
        # derivation. Alternative child readings remain shared/memoized.
        child_options = [self.solve(child) for child in obj.children]
        if any(not opts for opts in child_options):
            return []
        accepted = []
        for rule_id in identifiers:
            if rule_id.startswith("lexical_bridge_"):
                # Terminal -> N/ADJ/WH-* wrapper from the grammar POC.
                if len(child_options) != 1:
                    raise ValueError(f"unexpected bridge: {key}")
                accepted.extend(child_options[0])
                continue

            rule = self.rules[rule_id]
            # Incremental rule-local unification to avoid the cartesian
            # product of complete parse trees. Deduplicate compatible partial
            # bindings as we advance through RHS slots.
            # (bindings, evidence for variable-valued LHS fields, children,
            #  accumulated score)
            partials = [({}, frozenset(), (), 0.0)]
            lhs_vars = [
                (key, value.name)
                for key, value in rule.lhs.features.items()
                if isinstance(value, Variable)
            ]
            for symbol, options in zip(rule.rhs, child_options):
                updated = {}
                for env, evidence, chosen, score in partials:
                    for reading in options:
                        self.tick()
                        child = reading.node
                        if any(intern(k) not in child.evidence for k in symbol.requires):
                            self.rejected_reductions += 1
                            continue
                        merged = unify(symbol.features, child.features, env)
                        if merged is None:
                            self.rejected_reductions += 1
                            continue
                        next_env = merged[1]
                        extra_evidence = {
                            lhs_key
                            for lhs_key, variable in lhs_vars
                            for rhs_key, rhs_value in symbol.features.items()
                            if isinstance(rhs_value, Variable)
                            and rhs_value.name == variable
                            and rhs_key in child.evidence
                        }
                        next_evidence = evidence | extra_evidence
                        next_children = chosen + (child,)
                        next_score = score + child.score
                        signature = (bindings_key(next_env), tuple(sorted(next_evidence)))
                        old = updated.get(signature)
                        if old is None or next_score > old[3]:
                            updated[signature] = (
                                next_env, next_evidence, next_children, next_score
                            )
                        if len(updated) > MAX_SIGNATURES_PER_NODE:
                            raise BudgetExceeded("partial_signature_limit")
                partials = list(updated.values())
                if not partials:
                    break

            for env, evidence, chosen, score in partials:
                self.tick()
                # Reuse SEMAN2'S authoritative reducer to retain its exact
                # variable bindings and requires/evidence behavior.
                node = PredictiveParser._reduce(rule, chosen)
                if node is None:
                    self.rejected_reductions += 1
                    continue
                if (
                    node.start != obj.start_position or
                    node.end != obj.end_position
                ):
                    raise AssertionError("reduction span mismatch")
                self.valid_reductions += 1
                front_pp = (
                    rule.rule_id == "clause_front_pp" and
                    node.start == 0 and
                    node.end == len(self.text) and
                    len(chosen) == 3 and
                    self.text[chosen[0].start:chosen[0].end].lower() == "after school"
                )
                accepted.append(Reading(node, front_pp_root=front_pp))
        return self.compact(accepted)

    def run(self):
        started = time.perf_counter()
        readings = self.solve(self.root)
        fronted = [r for r in readings if r.front_pp_root]
        ranked = sorted(readings, key=lambda r: r.node.score, reverse=True)
        answer = {
            "status": "VALID" if readings else "INVALID",
            "signatures": len(readings),
            "validation_ms": round((time.perf_counter() - started) * 1000, 2),
            "forest_nodes_visited": self.nodes,
            "feature_tests": self.operations,
            "reductions_accepted": self.valid_reductions,
            "reductions_rejected": self.rejected_reductions,
            "missing_lexical_evidence": self.invalid_evidence,
            "fronted_pp_valid": bool(fronted),
            "best_score": round(ranked[0].node.score, 2) if ranked else None,
        }
        if ranked:
            answer["best_witness"] = format_witness(ranked[0].node)
        if fronted:
            answer["fronted_pp_witness"] = format_witness(fronted[0].node)
        return answer


def format_witness(node, depth=0, max_depth=18):
    if depth > max_depth:
        return "  " * depth + "..."
    prefix = "  " * depth
    if node.candidate is not None:
        return f"{prefix}{node.category}: {node.candidate.surface!r}"
    rule = node.rule.rule_id if node.rule else "LEXICAL"
    lines = [f"{prefix}{node.category} [{rule}] {node.start}:{node.end}"]
    for child in node.children:
        lines.append(format_witness(child, depth + 1, max_depth))
    return "\n".join(lines)


def worker(text, specs, meta, original_rules, send):
    try:
        mb = MEMORY_MB * 1024 * 1024
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        if hard != resource.RLIM_INFINITY:
            mb = min(mb, hard)
        resource.setrlimit(resource.RLIMIT_AS, (mb, mb))

        tic = time.perf_counter()
        lattice = build_lattice(text, RESOURCES.lexicon)
        lexical_ms = (time.perf_counter() - tic) * 1000
        # Use the exact same candidates/filtering as previous POC.
        edges, details = candidate_edges(text, RESOURCES.lexicon, specs)
        grouped = defaultdict(list)
        for start, end, name in edges:
            grouped[start].append((end, TERMINALS[name]))

        def recognize(head, fallback):
            position = head.position
            actions = head.state.actions
            return [
                Token(sym, text[position:end], position, length=end-position)
                for end, sym in grouped.get(position, ()) if sym in actions
            ]

        parser = GLRParser(
            G, table=TABLE,
            lexical_disambiguation=False,
            custom_token_recognition=recognize
        )
        start = time.perf_counter()
        try:
            forest = parser.parse(text)
            parsed = True
            parse_error = None
        except Exception as exc:
            parsed = False
            parse_error = f"{type(exc).__name__}: {str(exc)[:180]}"
        parse_ms = round((time.perf_counter()-start)*1000, 2)

        if not parsed:
            result = {"status": "STRUCTURAL_REJECT", "reason": parse_error}
        elif parse_ms > MAX_PARSE_S * 1000:
            result = {"status": "INCOMPLETE", "reason": "parse_time_budget"}
        else:
            validator = ForestValidator(
                forest, meta, lattice.candidates, text, original_rules
            )
            try:
                result = validator.run()
            except BudgetExceeded as exc:
                result = {
                    "status": "INCOMPLETE", "reason": str(exc),
                    "forest_nodes_visited": validator.nodes,
                    "feature_tests": validator.operations
                }

        result.update({
            "parse_ms": parse_ms,
            "lexical_ms": round(lexical_ms, 2),
            "tokens": len(lattice.tokens),
            "lattice_edges": details["raw_lattice_edges"],
            "refined_edges": len(edges),
            "rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024, 1),
        })
    except BaseException as exc:
        result = {
            "status": "ERROR",
            "reason": f"{type(exc).__name__}: {exc}"
        }
    try:
        send.send(result)
    except (BrokenPipeError, OSError):
        pass
    finally:
        send.close()


def main():
    global G, TABLE, RESOURCES, TERMINALS
    meta = json.loads(META.read_text())
    rules = {
        x["id"]: parse_rule(x)
        for x in (
            json.loads(line)
            for line in Path("data/grammar.jsonl").read_text().splitlines()
            if line.strip()
        )
    }
    G, TABLE = load_table()
    TERMINALS = G.terminals
    RESOURCES = ParserResources.from_dir("data")
    ctx = mp.get_context("fork")
    rows = []
    print("\n=== VALIDATION GRAMMATICALE DE LA FORÊT GLR ===", flush=True)
    for label, original_text, expected in TESTS:
        text = original_text.strip().rstrip(".!").rstrip()
        recv, send = ctx.Pipe(duplex=False)
        proc = ctx.Process(
            target=worker,
            args=(text, meta["terminals"], meta, rules, send)
        )
        proc.start()
        send.close()
        proc.join(MAX_PROCESS_S)
        if proc.is_alive():
            proc.terminate()
            proc.join(1)
            outcome = {"status": "INCOMPLETE", "reason": "process_timeout"}
        elif recv.poll(0.3):
            try:
                outcome = recv.recv()
            except EOFError:
                outcome = {"status": "ERROR", "reason": f"worker_exit={proc.exitcode}"}
        else:
            outcome = {"status": "ERROR", "reason": f"worker_exit={proc.exitcode}"}
        recv.close()
        row = {
            "id": label,
            "text": original_text,
            "expected_grammatical": expected,
            **outcome
        }
        rows.append(row)
        ms = row.get("parse_ms")
        vms = row.get("validation_ms")
        print(
            f"{label:24} {row['status']:18} "
            f"GLR={f'{ms:.1f}' if ms is not None else '?':>7}ms "
            f"VALIDATOR={f'{vms:.1f}' if vms is not None else '?':>7}ms "
            f"signatures={row.get('signatures', '?')}",
            flush=True
        )
        if row.get("reason"):
            print("  ", row["reason"][:180], flush=True)
        if label == "fronted_pp":
            print("  fronted_pp_valid:", row.get("fronted_pp_valid"), flush=True)
            if row.get("fronted_pp_witness"):
                print("  TÉMOIN PP:\n" + row["fronted_pp_witness"][:1900], flush=True)
            elif row.get("best_witness"):
                print("  AUTRE TÉMOIN:\n" + row["best_witness"][:1400], flush=True)
        RESULT_PATH.write_text(
            json.dumps({"results": rows}, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    counts = Counter(r["status"] for r in rows)
    print("\n=== BILAN ===")
    for key in ("VALID", "INVALID", "STRUCTURAL_REJECT", "INCOMPLETE", "ERROR"):
        print(f"  {key}: {counts[key]}")
    for r in rows:
        if r["status"] in ("VALID", "INVALID"):
            predicted = r["status"] == "VALID"
            if predicted != r["expected_grammatical"]:
                print("  DÉSACCORD ATTENDU:", r["id"], r["status"])
    print("Sortie :", RESULT_PATH)


if __name__ == "__main__":
    main()
