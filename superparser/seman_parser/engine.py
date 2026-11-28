"""Native ERG only. Never turn a source-span hypothesis into a grammatical proof."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from time import perf_counter
from .structural_preanalysis import analyze_paragraph
from .dialogue_graph import compose_dialogue

class Parser:
    """Own one ACE subprocess; use as a context manager.

    parse accepts one exact source utterance. parse_paragraph preserves the
    source graph and additionally exposes independently parsed speech spans.
    Native rank is never silently changed. Partial parses are not whole parses.
    """
    def __init__(self, grammar: str | Path, *, executable: str | Path = "ace",
                 max_results: int = 10, timeout: int = 10, stderr=None):
        if max_results < 1 or timeout < 1:
            raise ValueError("positive result and time limits required")
        self.grammar = str(grammar)
        self.executable = str(executable)
        self.max_results = max_results
        self.timeout = timeout
        self.stderr = stderr
        self._native = None

    @property
    def options(self):
        return ["-n", str(self.max_results), f"--timeout={self.timeout}",
                "--max-words=200", "--max-chart-megabytes=1200",
                "--max-unpack-megabytes=1500"]

    def __enter__(self):
        from delphin import ace
        self._native = ace.ACEParser(self.grammar, executable=self.executable,
                                    cmdargs=self.options, stderr=self.stderr)
        self._native.__enter__()
        return self

    def __exit__(self, *exc):
        native, self._native = self._native, None
        if native is not None:
            return native.__exit__(*exc)

    def parse(self, text: str):
        from delphin.codecs import simplemrs
        if self._native is None:
            raise RuntimeError("Use Parser as a context manager")
        start = perf_counter()
        row = {"source_text": text, "source_sha256": sha256(text.encode()).hexdigest(),
               "results": [], "native_response": {}, "n_results": 0,
               "result_cap_reached": False, "status": "no_analysis_returned"}
        if not text.strip() or "\n" in text or "\r" in text:
            row["status"] = "unsupported_empty_or_multiline_input"
        else:
            try:
                response = self._native.interact(text)
                row["native_response"] = {k: v for k, v in response.items()
                                          if k not in ("results", "run")}
                for rank, result in enumerate(response.results(), 1):
                    native = dict(result)
                    flags = []
                    if not native.get("mrs") or not native.get("derivation"):
                        flags.append("missing_native_output")
                    else:
                        try:
                            mrs = simplemrs.decode(native["mrs"])
                            flags.extend(sorted({ep.predicate.strip('"') for ep in mrs.rels
                                                 if ep.predicate.strip('"') in {"fw_seq","unknown","quoted"}}))
                        except Exception as exc:
                            flags.append("mrs_decode_error")
                            native["mrs_decode_error"] = repr(exc)
                    row["results"].append({**native, "native_rank": rank, "quality_flags": flags})
                row["n_results"] = len(row["results"])
                row["result_cap_reached"] = row["n_results"] >= self.max_results
                if row["results"]:
                    row["status"] = ("incomplete_native_output" if any(
                        set(x["quality_flags"]) & {"missing_native_output","mrs_decode_error"}
                        for x in row["results"]) else "has_native_analysis")
            except Exception as exc:
                row["status"] = "interface_error"
                row["error"] = repr(exc)
        row["elapsed_seconds"] = perf_counter()-start
        return row

    def parse_unit(self, text, constituents, *, parse_components=True):
        # Exact span identity is checked before any native call.
        for part in constituents:
            if not 0 <= part["start"] < part["end"] <= len(text):
                raise ValueError("Component lies outside source unit")
        whole = self.parse(text)
        components = []
        if parse_components:
            for part in constituents:
                if part["function"] not in {"spoken_clause_candidate", "reporting_clause",
                                             "narratorial_parenthetical"}:
                    continue
                a,b = part["start"],part["end"]
                components.append({"component_id":part["id"],"unit_span":[a,b],
                                   "analysis":self.parse(text[a:b])})
        report = {"source_text":text,"source_constituents":list(constituents),
                  "whole":whole,"component_analyses":components,
                  "component_policy":"independent exact substrings, not a combined parse"}
        if parse_components:
            report["dialogue_graph"] = compose_dialogue(text, constituents, whole, components, parse=self.parse)
        return report

    def parse_paragraph(self, paragraph: str, *, parse_components=True):
        units = []
        for unit in analyze_paragraph(paragraph):
            graph = [c.to_dict() for c in unit.constituents]
            row = {"paragraph_span":[unit.source_start,unit.source_end],
                   "source_text":unit.text,"quotation_status":unit.quotation_status,
                   "structural_status":unit.structural_status,
                   "discourse_function":unit.discourse_function,
                   "source_constituents":graph}
            if unit.eligible_for_parse:
                row.update(self.parse_unit(unit.text,graph,parse_components=parse_components))
            else:
                row.update({"whole":None,"component_analyses":[],"status":"requires_source_review"})
            units.append(row)
        return {"source_text":paragraph,"units":units}
