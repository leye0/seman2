#!/usr/bin/env python3
"""CULT-03: contextual interpretation and reaction to one invariant reply."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import re
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import Python_sml_ClientInterface as sml

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
OUT = P / "output"
RAW = "Absolutely—right after my pet dragon signs it."
LITERAL_ID = "literal:finish-after:report:dragon-signature"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str) -> tuple[Path, dict]:
    path = ROOT / "poc" / name / "output" / "results.json"
    assert path.exists(), path
    return path, json.loads(path.read_text())


def soar_decide(kernel: sml.Kernel, scenario: dict, ranked: list[tuple[str, float]], status: str, index: int) -> dict:
    agent = kernel.CreateAgent(f"cult03-{index}")
    assert agent and not agent.HadError()
    il = agent.GetInputLink()
    il_name = il.GetIdentifierName()
    exchange = il.CreateIdWME("exchange")
    exchange.CreateStringWME("scenario-id", scenario["id"])
    exchange.CreateStringWME("decision-status", status)
    exchange.CreateStringWME("literal-content-id", LITERAL_ID)
    beam = exchange.CreateIdWME("beam")
    for rank, (hypothesis_id, score) in enumerate(ranked, 1):
        candidate = beam.CreateIdWME("candidate")
        candidate.CreateIntWME("rank", rank)
        candidate.CreateStringWME("hypothesis-id", hypothesis_id)
        candidate.CreateFloatWME("support", score)
    agent.Commit()
    productions = r'''
sp {cult03*literal
   (state <s> ^io.input-link.exchange <e> ^io.output-link <o>)
   (<e> ^decision-status selected ^beam <b>)
   (<b> ^candidate <c>) (<c> ^rank 1 ^hypothesis-id H0)
-->
   (<o> ^reaction <r>)
   (<r> ^plan-act acknowledge-literal ^selected-hypothesis H0 ^reason top-supported-literal)}
sp {cult03*affiliative
   (state <s> ^io.input-link.exchange <e> ^io.output-link <o>)
   (<e> ^decision-status selected ^beam <b>)
   (<b> ^candidate <c>) (<c> ^rank 1 ^hypothesis-id H1)
-->
   (<o> ^reaction <r>)
   (<r> ^plan-act reciprocate-prudently ^selected-hypothesis H1 ^reason supported-affiliative-play)}
sp {cult03*criticism
   (state <s> ^io.input-link.exchange <e> ^io.output-link <o>)
   (<e> ^decision-status selected ^beam <b>)
   (<b> ^candidate <c>) (<c> ^rank 1 ^hypothesis-id H2)
-->
   (<o> ^reaction <r>)
   (<r> ^plan-act address-task ^selected-hypothesis H2 ^reason supported-indirect-criticism)}
sp {cult03*undecided
   (state <s> ^io.input-link.exchange <e> ^io.output-link <o>)
   (<e> ^decision-status undecided)
-->
   (<o> ^reaction <r>)
   (<r> ^plan-act clarify-intent ^selected-hypothesis none ^reason insufficient-margin)}
'''
    source = agent.ExecuteCommandLine(productions)
    run = agent.ExecuteCommandLine("run 1")
    top = agent.ExecuteCommandLine("print S1 --depth 6")
    output_name = re.search(r"\^output-link ([A-Z]\d+)", top).group(1)
    output = agent.ExecuteCommandLine(f"print {output_name} --depth 4")
    input_wm = agent.ExecuteCommandLine(f"print {il_name} --depth 8")
    act = re.search(r"\^plan-act ([^\s()]+)", output)
    selected = re.search(r"\^selected-hypothesis ([^\s()]+)", output)
    reason = re.search(r"\^reason ([^\s()]+)", output)
    assert act and selected and reason and "1 rule fired" in run, (run, output)
    selected_value = selected.group(1).strip("|")
    result = {
        "plan_act": act.group(1),
        "selected_hypothesis_id": None if selected_value == "none" else selected_value,
        "reason": reason.group(1),
        "source_result": source,
        "run": run,
        "input_wm": input_wm,
        "output_wm": output,
    }
    kernel.DestroyAgent(agent)
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_paths = {}
    loaded = {}
    for name in ("x-03", "cult-01", "cult-02", "cult-05", "dlg-06", "dlg-07", "dlg-08", "comm-01", "comm-02"):
        path, data = load(name)
        source_paths[name], loaded[name] = path, data

    switchboard_pattern = loaded["cult-01"]["patterns"][0]
    reddit_pattern = loaded["cult-05"]["families"][0]
    retrieved_patterns = [
        {
            "retrieval_id": "ret:C03:switchboard-sequence",
            "source_poc": "CULT-01",
            "pattern_id": switchboard_pattern["pattern_id"],
            "source_corpus": "Switchboard Dialog Act Corpus",
            "support": switchboard_pattern["support_count"],
            "exceptions": switchboard_pattern["exception_count"],
            "evidence_excerpt": switchboard_pattern["support_examples"][0],
            "use": "dialogue-sequence expectation only",
        },
        {
            "retrieval_id": "ret:C03:reddit-form",
            "source_poc": "CULT-05",
            "pattern_id": reddit_pattern["pattern_id"],
            "source_corpus": loaded["cult-05"]["corpus"]["name"],
            "support": reddit_pattern["support"],
            "exceptions": reddit_pattern["exception_count"],
            "evidence_excerpt": reddit_pattern["audit_examples"][0],
            "use": "form/reaction analogy only",
        },
    ]

    observation = {
        "observation_id": "obs:C03:user-reply",
        "speaker": "user",
        "raw_text": RAW,
        "immutable": True,
    }
    literal = {
        "content_id": LITERAL_ID,
        "surface_observation_id": observation["observation_id"],
        "predicate": "finish-after",
        "arguments": ["report", "event:pet-dragon-signs-report"],
        "asserted_humour": False,
        "adapter": "controlled semantic fixture; no external parser claim",
        "immutable": True,
    }
    hypotheses = [
        {"id": "H0", "commitment": "speaker-supports(literal)", "human_eval_label": "literal assertion"},
        {"id": "H1", "commitment": "speaker-invites-affiliative-play(about deadline)", "human_eval_label": "joke/teasing"},
        {"id": "H2", "commitment": "speaker-criticizes-or-evades(report request)", "human_eval_label": "criticism"},
    ]
    scenarios = [
        {
            "id": "CLOSE-PLAY",
            "system_turn": "Did you finish the report?",
            "relation": "close-colleagues-with-play-history",
            "shared_knowledge": ["dragons are fictional here", "similar impossible replies previously led to mutual laughter"],
            "signals": {"world_incongruity": 1.0, "shared_fiction": 0.0, "close_relation": 1.0, "laughter": 1.0, "deadline_pressure": 0.1, "power_asymmetry": 0.0, "explicit_sincerity": 0.0},
            "external_eval_only": "joke/teasing",
        },
        {
            "id": "SHARED-FICTION",
            "system_turn": "Has the guild report been completed?",
            "relation": "role-play collaborators",
            "shared_knowledge": ["the current shared fictional world contains a pet dragon with signing authority"],
            "signals": {"world_incongruity": 0.0, "shared_fiction": 1.0, "close_relation": 0.4, "laughter": 0.0, "deadline_pressure": 0.0, "power_asymmetry": 0.0, "explicit_sincerity": 0.7},
            "external_eval_only": "literal assertion",
        },
        {
            "id": "MANAGER-DEADLINE",
            "system_turn": "The report is late. Is it finished now?",
            "relation": "manager-to-report-with-strained-history",
            "shared_knowledge": ["two deadlines were missed", "impossible answers previously signalled resistance"],
            "signals": {"world_incongruity": 1.0, "shared_fiction": 0.0, "close_relation": 0.0, "laughter": 0.0, "deadline_pressure": 1.0, "power_asymmetry": 1.0, "explicit_sincerity": 0.0},
            "external_eval_only": "criticism/evasion",
        },
        {
            "id": "LOW-CONTEXT",
            "system_turn": "Did you finish the report?",
            "relation": "first interaction",
            "shared_knowledge": [],
            "signals": {"world_incongruity": 1.0, "shared_fiction": 0.0, "close_relation": 0.1, "laughter": 0.0, "deadline_pressure": 0.2, "power_asymmetry": 0.0, "explicit_sincerity": 0.0},
            "external_eval_only": "ambiguous",
        },
    ]

    kernel = sml.Kernel.CreateKernelInNewThread()
    assert not kernel.HadError()
    soar_version = kernel.GetSoarKernelVersion()
    evidence_rows, traces = [], []
    expected = {"CLOSE-PLAY": "H1", "SHARED-FICTION": "H0", "MANAGER-DEADLINE": "H2", "LOW-CONTEXT": None}
    response_text = {
        "acknowledge-literal": "Understood; I'll treat the dragon's signature as the remaining step.",
        "reciprocate-prudently": "I'll keep an eye out for the dragon—should I take that as not finished yet?",
        "address-task": "Let's set the joke aside: when will the report be ready?",
        "clarify-intent": "Do you mean it isn't finished yet, or are we speaking in the shared story?",
    }
    for index, scenario in enumerate(scenarios, 1):
        s = scenario["signals"]
        scores = {
            "H0": 0.20 + 0.90 * s["shared_fiction"] + 0.70 * s["explicit_sincerity"] - 0.40 * s["world_incongruity"],
            "H1": 0.15 + 0.45 * s["world_incongruity"] + 0.45 * s["close_relation"] + 0.40 * s["laughter"] - 0.60 * s["shared_fiction"] - 0.10 * s["power_asymmetry"],
            "H2": 0.10 + 0.50 * s["deadline_pressure"] + 0.35 * s["power_asymmetry"] + 0.15 * s["world_incongruity"] - 0.25 * s["laughter"],
        }
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        margin = ranked[0][1] - ranked[1][1]
        status = "selected" if margin >= 0.30 else "undecided"
        selected_id = ranked[0][0] if status == "selected" else None
        for hypothesis_id, score in scores.items():
            favorable, unfavorable = [], []
            if hypothesis_id == "H0":
                if s["shared_fiction"]: favorable.append("shared-world-makes-event-possible")
                if s["explicit_sincerity"]: favorable.append("explicit-sincerity")
                if s["world_incongruity"]: unfavorable.append("physical-world-incongruity")
            elif hypothesis_id == "H1":
                if s["world_incongruity"]: favorable.append("violated-world-expectation")
                if s["close_relation"]: favorable.append("affiliative-history")
                if s["laughter"]: favorable.append("shared-laughter")
                if s["shared_fiction"]: unfavorable.append("literal-in-shared-fiction")
            else:
                if s["deadline_pressure"]: favorable.append("open-task-obligation")
                if s["power_asymmetry"]: favorable.append("strained-power-context")
                if s["laughter"]: unfavorable.append("shared-laughter")
            evidence_rows.append({
                "scenario_id": scenario["id"], "hypothesis_id": hypothesis_id, "support": score,
                "favorable_json": json.dumps(favorable), "unfavorable_json": json.dumps(unfavorable),
                "literal_content_id": LITERAL_ID,
                "retrieval_ids_json": json.dumps([p["retrieval_id"] for p in retrieved_patterns]),
            })
        soar = soar_decide(kernel, scenario, ranked, status, index)
        assert soar["selected_hypothesis_id"] == selected_id, (scenario["id"], selected_id, soar, ranked, margin)
        plan = {
            "plan_id": f"plan:C03:{scenario['id']}",
            "act": soar["plan_act"],
            "communicative_goal": {
                "acknowledge-literal": "ground-literal-within-shared-world",
                "reciprocate-prudently": "affiliate-without-committing-to-humour-certainty",
                "address-task": "repair-task-coordination",
                "clarify-intent": "resolve-pragmatic-ambiguity",
            }[soar["plan_act"]],
            "content": response_text[soar["plan_act"]],
            "selected_hypothesis_id": selected_id,
            "omitted_alternatives": [h for h, _ in ranked if h != selected_id] if selected_id else [h for h, _ in ranked],
            "provenance": ["COMM-01 plan schema", "COMM-02 context-sensitive selection", soar["reason"]],
        }
        traces.append({
            "scenario_id": scenario["id"],
            "system_turn": scenario["system_turn"],
            "interaction_state_before": {"relation": scenario["relation"], "shared_knowledge": scenario["shared_knowledge"], "open_obligation": "resolve report status"},
            "user_observation": observation,
            "literal_content": literal,
            "broken_expectation": {"kind": "world-or-task-expectation", "degree": s["world_incongruity"], "description": "a pet dragon signing a real report is unexpected unless licensed by the shared world"},
            "retrieved_patterns": retrieved_patterns,
            "concurrent_interpretations": [{"hypothesis_id": h, "support": score} for h, score in ranked],
            "decision": {"status": status, "margin": margin, "threshold": 0.30, "selected_hypothesis_id": selected_id},
            "soar_decision": soar,
            "response_plan": plan,
        })
    kernel.Shutdown()

    evidence_path = OUT / "hypothesis-evidence.parquet"
    pq.write_table(pa.Table.from_pylist(evidence_rows), evidence_path, compression="zstd")
    by = {trace["scenario_id"]: trace for trace in traces}
    validations = {
        "same_raw_reply_all_contexts": all(t["user_observation"]["raw_text"] == RAW for t in traces),
        "same_immutable_literal_all_contexts": len({t["literal_content"]["content_id"] for t in traces}) == 1 and literal["immutable"],
        "all_hypotheses_coexist": all(len(t["concurrent_interpretations"]) == 3 for t in traces),
        "context_changes_interpretation": all(by[k]["decision"]["selected_hypothesis_id"] == v for k, v in expected.items()),
        "ambiguous_case_remains_undecided": by["LOW-CONTEXT"]["decision"]["status"] == "undecided" and by["LOW-CONTEXT"]["response_plan"]["act"] == "clarify-intent",
        "playful_response_is_prudent": by["CLOSE-PLAY"]["response_plan"]["act"] == "reciprocate-prudently" and "should I" in by["CLOSE-PLAY"]["response_plan"]["content"],
        "real_soar_rule_fired_per_context": all("1 rule fired" in t["soar_decision"]["run"] for t in traces),
        "working_memory_has_full_beam": all(t["soar_decision"]["input_wm"].count("^hypothesis-id") == 3 for t in traces),
        "real_patterns_have_support_and_exceptions": all(p["support"] > 0 and p["exceptions"] > 0 for p in retrieved_patterns),
        "human_labels_do_not_drive_scores": all("external_eval_only" not in row for row in evidence_rows),
        "favorable_and_unfavorable_evidence_retained": any(json.loads(r["favorable_json"]) for r in evidence_rows) and any(json.loads(r["unfavorable_json"]) for r in evidence_rows),
        "complete_required_trace": all(all(k in t for k in ("system_turn", "user_observation", "literal_content", "broken_expectation", "retrieved_patterns", "concurrent_interpretations", "decision", "response_plan")) for t in traces),
        "evidence_roundtrip": pq.read_table(evidence_path).num_rows == 12,
        "x03_and_comm_contracts_linked": all(name in source_paths for name in ("x-03", "comm-01", "comm-02")),
    }
    assert all(validations.values()), validations
    result = {
        "observation": observation,
        "literal_content": literal,
        "hypotheses": hypotheses,
        "scenarios": scenarios,
        "retrieved_patterns": retrieved_patterns,
        "traces": traces,
        "source_sha256": {str(path.relative_to(ROOT)): sha(path) for path in source_paths.values()},
        "evidence_table": {"path": "output/hypothesis-evidence.parquet", "rows": len(evidence_rows), "sha256": sha(evidence_path)},
        "boundary": "external_eval_only and human_eval_label are audit metadata, never evidence or speaker intention",
        "validations": validations,
    }
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (OUT / "trace.jsonl").write_text("".join(json.dumps(t, ensure_ascii=False) + "\n" for t in traces))
    (OUT / "summary.json").write_text(json.dumps({
        "scenarios": len(traces), "same_user_reply": RAW, "decided": 3, "undecided": 1,
        "actual_soar_decisions": 4, "real_retrieved_pattern_sources": 2,
        "verdict": "GO_CONTEXTUAL_HUMOUR_HYPOTHESIS_AND_PRUDENT_REACTION",
    }, ensure_ascii=False, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "soar": soar_version, "sml_module": sml.__file__, "pyarrow": importlib.metadata.version("pyarrow"),
        "decision_margin": 0.30, "pythonpath": os.environ.get("PYTHONPATH"),
    }, indent=2) + "\n")
    print("CULT-03: same reply -> literal/play/criticism/undecided; real Soar reaction each time; GO")


if __name__ == "__main__":
    main()
