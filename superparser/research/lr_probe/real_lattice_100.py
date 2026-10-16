"""Seman2 lexical lattice -> parglare structural GLR benchmark."""
import json
import multiprocessing as mp
import re
import resource
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

from parglare import Grammar, GLRParser
from parglare.closure import LR_0
from parglare.parser import Token
from parglare.tables import create_load_table
from seman_parser.engine import ParserResources
from seman_parser.segmentation import build_lattice

LIMIT_S = 2.5
LIMIT_MB = 768
INPUT = Path("reading_100_results.json")
OUTPUT = Path("research/lr_probe/real_lattice_100.json")

# Charger le cache SLR existant, sans recompilation.
g = Grammar.from_file(
    "research/lr_probe/grammar.pg",
    _no_check_recognizers=True
)
table = create_load_table(
    g,
    itemset_type=LR_0,
    prefer_shifts=False,
    cache_path="research/lr_probe/grammar_slr.pgc",
    force_load=True
)

terminals = dict(g.terminals)
resources = ParserResources.from_dir("data")

cases = json.loads(INPUT.read_text())["results"]

latest_path = Path("reading_100_results_live.json")
latest = (
    json.loads(latest_path.read_text())["results"]
    if latest_path.exists() else cases
)
previous = {r["id"]: bool(r["complete"]) for r in latest}


def terminal_name(category):
    return "TK_" + re.sub(r"[^A-Za-z0-9_]", "_", category)


def prepare(text):
    text = text.strip()

    # La ponctuation finale . et ! est externe à la
    # construction CLAUSE dans ce test.
    if text.endswith((".", "!")):
        text = text[:-1].rstrip()

    tic = time.perf_counter()
    lattice = build_lattice(text, resources.lexicon)
    lexical_ms = (time.perf_counter() - tic) * 1000

    # Fusionner uniquement les sens ayant la même
    # catégorie ET le même span.
    # Les traits seront évalués dans la prochaine POC.
    edges = sorted({
        (
            c.span_start,
            c.span_end,
            terminal_name(c.category)
        )
        for c in lattice.candidates
        if c.span_end <= len(text)
        and c.span_end > c.span_start
        and terminal_name(c.category) in terminals
    })

    starts = {c.span_start for c in lattice.candidates}
    unknown = [
        tok.text for tok in lattice.tokens
        if tok.start not in starts
    ]

    return text, edges, lexical_ms, len(lattice.tokens), unknown


def worker(text, edges, send):
    try:
        limit = LIMIT_MB * 1024 * 1024
        _, hard = resource.getrlimit(resource.RLIMIT_AS)

        if hard != resource.RLIM_INFINITY:
            limit = min(limit, hard)

        resource.setrlimit(
            resource.RLIMIT_AS, (limit, limit)
        )

        by_start = defaultdict(list)
        for start, end, name in edges:
            by_start[start].append((end, terminals[name]))

        def recognize(head, _fallback):
            at = head.position
            allowed = head.state.actions

            return [
                Token(
                    symbol,
                    text[at:end],
                    at,
                    length=end - at
                )
                for end, symbol in by_start.get(at, ())
                if symbol in allowed
            ]

        parser = GLRParser(
            g,
            table=table,
            lexical_disambiguation=False,
            custom_token_recognition=recognize
        )

        tic = time.perf_counter()

        try:
            parser.parse(text)
            answer = {"status": "OK"}

        except Exception as exc:
            kind = type(exc).__name__
            answer = {
                "status": (
                    "REJECT" if kind == "SyntaxError"
                    else "ERROR"
                ),
                "reason": f"{kind}: {exc}"[:240]
            }

        answer["parse_ms"] = round(
            (time.perf_counter() - tic) * 1000, 3
        )
        answer["rss_mb"] = round(
            resource.getrusage(
                resource.RUSAGE_SELF
            ).ru_maxrss / 1024,
            1
        )

    except BaseException as exc:
        answer = {
            "status": "ERROR",
            "reason": (
                f"{type(exc).__name__}: {exc}"
            )[:240]
        }

    try:
        send.send(answer)
    except (BrokenPipeError, OSError):
        pass
    finally:
        send.close()


# Linux : fork partage les tables déjà chargées.
ctx = mp.get_context("fork")
records = []

print(
    f"Cache prêt : {len(table.states)} états | "
    f"{len(cases)} phrases",
    flush=True
)

for i, case in enumerate(cases, 1):
    text, edges, lexical_ms, token_count, unknown = (
        prepare(case["text"])
    )

    receiver, sender = ctx.Pipe(duplex=False)

    proc = ctx.Process(
        target=worker,
        args=(text, edges, sender)
    )
    proc.start()
    sender.close()
    proc.join(LIMIT_S)

    if proc.is_alive():
        proc.terminate()
        proc.join(1)
        answer = {
            "status": "TIMEOUT",
            "reason": f">{LIMIT_S}s"
        }

    elif receiver.poll(0.15):
        try:
            answer = receiver.recv()
        except EOFError:
            answer = {
                "status": "CRASH",
                "reason": f"exit={proc.exitcode}"
            }
    else:
        answer = {
            "status": "CRASH",
            "reason": f"exit={proc.exitcode}"
        }

    receiver.close()

    records.append({
        "id": case["id"],
        "source": case["source"],
        "text": case["text"],
        "baseline_complete": previous.get(
            case["id"], case["complete"]
        ),
        "token_count": token_count,
        "lattice_edges": len(edges),
        "unknown_token_starts": unknown,
        "lexical_ms": round(lexical_ms, 3),
        **answer
    })

    if i % 10 == 0:
        counts = Counter(
            r["status"] for r in records
        )
        print(
            f"{i}/100 | "
            f"OK={counts['OK']} | "
            f"REJECT={counts['REJECT']} | "
            f"TIMEOUT={counts['TIMEOUT']} | "
            f"ERROR={counts['CRASH']+counts['ERROR']}",
            flush=True
        )

    OUTPUT.write_text(
        json.dumps(
            {
                "mode": "SLR GLR, lexical lattice, no feature unification",
                "results": records
            },
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


print("\n========== BILAN ==========")

for source in ("référence", "roman", "ensemble"):
    sub = [
        r for r in records
        if source == "ensemble"
        or r["source"] == source
    ]
    counts = Counter(r["status"] for r in sub)

    times = sorted(
        r["parse_ms"] for r in sub
        if r["status"] == "OK"
    )

    p50 = (
        round(statistics.median(times), 2)
        if times else None
    )
    p95 = (
        round(
            times[min(
                len(times) - 1,
                int(.95 * (len(times) - 1))
            )],
            2
        )
        if times else None
    )

    old_ok = sum(
        r["baseline_complete"] for r in sub
    )

    print(
        f"\n{source}: "
        f"ancien={old_ok}/{len(sub)} | "
        f"GLR={counts['OK']}/{len(sub)}"
    )
    print(
        f"  Rejets={counts['REJECT']} "
        f"Timeouts={counts['TIMEOUT']} "
        f"Erreurs={counts['ERROR']+counts['CRASH']}"
    )
    print(
        f"  Lecture GLR (succès) : "
        f"p50={p50} ms | p95={p95} ms"
    )


print("\n========== PREMIERS ÉCHECS ==========")

for r in [
    r for r in records
    if r["status"] != "OK"
][:10]:
    print(
        f"\n[{r['status']}] {r['text']}\n"
        f"  {r.get('reason', '')[:160]}"
    )

print("\nRésultats :", OUTPUT)
