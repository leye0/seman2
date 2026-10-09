"""Local-only KQML transport and lossless projections for TRIPS/Cogent."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import os
import socket
import threading
import time
from typing import Any, Mapping, Sequence

from .model import (
    InterpretationHypothesis,
    InterpretationSegment,
    Projection,
    ProjectionEdge,
    ProjectionNode,
    SourceSpan,
)


class KqmlProtocolError(ValueError):
    pass


def _atom(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _same(value: Any, expected: str) -> bool:
    return isinstance(value, str) and value.casefold() == expected.casefold()


def _get(items: Any, key: str, default: Any = None) -> Any:
    if not isinstance(items, list):
        return default
    for index, item in enumerate(items[:-1]):
        if _same(item, key):
            return items[index + 1]
    return default


def _integer(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class _Reader:
    """Small complete KQML S-expression reader; native text is kept separately."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.offset = 0

    def read(self) -> Any:
        self._space()
        value = self._expression()
        self._space()
        if self.offset != len(self.text):
            raise KqmlProtocolError("trailing data after KQML expression")
        return value

    def _space(self) -> None:
        while self.offset < len(self.text) and self.text[self.offset].isspace():
            self.offset += 1

    def _expression(self) -> Any:
        if self.offset >= len(self.text):
            raise KqmlProtocolError("unexpected end of KQML expression")
        char = self.text[self.offset]
        if char == "(":
            return self._list()
        if char == '"':
            return self._string()
        if char == "#":
            return self._hashed_string()
        if char in "'`":
            self.offset += 1
            return [char, self._expression()]
        return self._token()

    def _list(self) -> list[Any]:
        self.offset += 1
        result: list[Any] = []
        while True:
            self._space()
            if self.offset >= len(self.text):
                raise KqmlProtocolError("unterminated KQML list")
            if self.text[self.offset] == ")":
                self.offset += 1
                return result
            result.append(self._expression())

    def _string(self) -> str:
        self.offset += 1
        result: list[str] = []
        while self.offset < len(self.text):
            char = self.text[self.offset]
            self.offset += 1
            if char == '"':
                return "".join(result)
            if char == "\\" and self.offset < len(self.text):
                char = self.text[self.offset]
                self.offset += 1
            result.append(char)
        raise KqmlProtocolError("unterminated KQML string")

    def _hashed_string(self) -> str:
        self.offset += 1
        start = self.offset
        while self.offset < len(self.text) and self.text[self.offset].isdigit():
            self.offset += 1
        if start == self.offset or self.offset >= len(self.text) or self.text[self.offset] != '"':
            raise KqmlProtocolError("invalid KQML hashed string")
        length = int(self.text[start:self.offset])
        self.offset += 1
        result = self.text[self.offset:self.offset + length]
        if len(result) != length:
            raise KqmlProtocolError("truncated KQML hashed string")
        self.offset += length
        return result

    def _token(self) -> str:
        start = self.offset
        in_pipes = False
        while self.offset < len(self.text):
            char = self.text[self.offset]
            if char == "|":
                in_pipes = not in_pipes
                self.offset += 1
                continue
            if not in_pipes and (char.isspace() or char in "()"):
                break
            self.offset += 1
        if start == self.offset:
            raise KqmlProtocolError(f"invalid KQML token at {self.offset}")
        return self.text[start:self.offset]


def parse_kqml(payload: bytes) -> list[Any]:
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise KqmlProtocolError("TRIPS returned non-UTF-8 KQML") from exc
    parsed = _Reader(decoded).read()
    if not isinstance(parsed, list):
        raise KqmlProtocolError("TRIPS response is not a KQML performative")
    return parsed


def _complete_expression(buffer: bytearray) -> bytes | None:
    """Return one exact complete top-level KQML expression, if available."""
    start = 0
    while start < len(buffer) and chr(buffer[start]).isspace():
        start += 1
    if start == len(buffer) or buffer[start] != ord("("):
        return None
    depth = 0
    quoted = False
    escaped = False
    in_pipes = False
    for index in range(start, len(buffer)):
        byte = buffer[index]
        if quoted:
            if escaped:
                escaped = False
            elif byte == ord("\\"):
                escaped = True
            elif byte == ord('"'):
                quoted = False
            continue
        if byte == ord('"'):
            quoted = True
        elif byte == ord("|"):
            in_pipes = not in_pipes
        elif not in_pipes and byte == ord("("):
            depth += 1
        elif not in_pipes and byte == ord(")"):
            depth -= 1
            if depth == 0:
                return bytes(buffer[start:index + 1])
    return None


def _escape_string(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _result_content(message: list[Any]) -> list[Any] | None:
    if not message or not _same(message[0], "TELL"):
        return None
    content = _get(message, ":CONTENT")
    if not isinstance(content, list) or not content:
        return None
    if any(
        _same(content[0], kind)
        for kind in ("NEW-SPEECH-ACT", "NEW-SPEECH-ACT-HYPS", "FAILED-TO-PARSE")
    ):
        return content
    return None


def _matches_uttnum(content: list[Any], uttnum: int) -> bool:
    if _same(content[0], "FAILED-TO-PARSE"):
        return _integer(_get(content, ":UTTNUM")) == uttnum
    return _contains_uttnum(content, uttnum)


def _contains_uttnum(node: Any, uttnum: int) -> bool:
    """Search the reply tree: COMPOUND-COMMUNICATION-ACT nests UTTNUM in :ACTS."""
    if not isinstance(node, list) or not node:
        return False
    if _integer(_get(node, ":UTTNUM")) == uttnum:
        return True
    for item in node:
        if _contains_uttnum(item, uttnum):
            return True
    return False


@dataclass(frozen=True, slots=True)
class LocalKqmlResult:
    body: bytes
    content_type: str
    status: int
    endpoint: str
    headers: Mapping[str, str]


class LocalTripsTransport:
    """Talk to a TRIPS Facilitator on loopback; remote hosts are rejected."""

    # NUMBER-INTERPS-DESIRED changes parser-global state.  Keep configuration
    # and parsing atomic for callers sharing one local TRIPS process.
    _parser_configuration_lock = threading.Lock()

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6200,
        *,
        timeout_seconds: float = 60.0,
        max_response_bytes: int = 16 * 1024 * 1024,
    ) -> None:
        try:
            addresses = {info[4][0] for info in socket.getaddrinfo(host, port)}
        except OSError as exc:
            raise ValueError(f"invalid TRIPS host {host!r}") from exc
        if not addresses or any(not ipaddress.ip_address(item).is_loopback for item in addresses):
            raise ValueError("TRIPS transport is local-only; host must resolve to loopback")
        if not 1 <= port <= 65535 or timeout_seconds <= 0 or max_response_bytes < 1024:
            raise ValueError("invalid local TRIPS transport bounds")
        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.endpoint = f"kqml://{host}:{port}"
        self._request_counter = 0

    def parse(self, input_text: str, parameters: Mapping[str, str]) -> LocalKqmlResult:
        with self._parser_configuration_lock:
            return self._parse_locked(input_text, parameters)

    def _parse_locked(
        self, input_text: str, parameters: Mapping[str, str]
    ) -> LocalKqmlResult:
        self._request_counter += 1
        uttnum = os.getpid() * 1_000_000 + self._request_counter
        name = f"SEMAN2-{os.getpid()}-{self._request_counter}"
        desired = int(parameters.get("number-parses-desired", "2"))
        if not 1 <= desired <= 10:
            raise ValueError("TRIPS accepts between 1 and 10 parses")
        messages = (
            f"(register :name {name})",
            "(subscribe :content (tell &key :content (new-speech-act . *)))",
            "(subscribe :content (tell &key :content (new-speech-act-hyps . *)))",
            "(subscribe :content (tell &key :content (failed-to-parse . *)))",
            # The Parser has a dedicated, validated message for this setting;
            # arbitrary EVAL is unnecessary and can terminate the Lisp image
            # on a reader error before its normal error handler is installed.
            f"(tell :receiver PARSER :content (number-interps-desired {desired}))",
            # Cogent is configured to accept parser input from TextTagger.  We
            # deliberately impersonate that local module so it does not tag
            # the same utterance a second time after seeing our final TELL.
            "(tell :sender TEXTTAGGER :content (started-speaking :channel DESKTOP :direction INPUT :mode TEXT))",
            f'(tell :sender TEXTTAGGER :content (word "{_escape_string(input_text)}" :frame (0 {len(input_text)}) :channel DESKTOP :direction INPUT))',
            "(tell :sender TEXTTAGGER :content (stopped-speaking :channel DESKTOP :direction INPUT :mode TEXT))",
            f'(tell :sender TEXTTAGGER :content (utterance :channel DESKTOP :direction INPUT :mode TEXT :text "{_escape_string(input_text)}" :uttnum {uttnum}))',
        )
        deadline = time.monotonic() + self.timeout_seconds
        buffer = bytearray()
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout_seconds) as connection:
                connection.settimeout(max(0.1, deadline - time.monotonic()))
                connection.sendall(("\n".join(messages) + "\n").encode("utf-8"))
                while time.monotonic() < deadline:
                    while (expression := _complete_expression(buffer)) is not None:
                        content = _result_content(parse_kqml(expression))
                        consumed = buffer.find(expression) + len(expression)
                        del buffer[:consumed]
                        if content is not None and _matches_uttnum(content, uttnum):
                            return LocalKqmlResult(
                                body=expression,
                                content_type="application/kqml; charset=utf-8",
                                status=0,
                                endpoint=self.endpoint,
                                headers={
                                    "transport": "KQML/TCP",
                                    "host": self.host,
                                    "port": str(self.port),
                                    "uttnum": str(uttnum),
                                },
                            )
                    connection.settimeout(max(0.1, deadline - time.monotonic()))
                    chunk = connection.recv(65536)
                    if not chunk:
                        raise ConnectionError("TRIPS closed the KQML connection")
                    buffer.extend(chunk)
                    if len(buffer) > self.max_response_bytes:
                        raise ConnectionError("TRIPS response exceeds configured bound")
        except (OSError, TimeoutError, ConnectionError) as exc:
            raise ConnectionError(f"local TRIPS unavailable at {self.endpoint}: {exc}") from exc
        raise ConnectionError(f"local TRIPS timed out at {self.endpoint}")


def probe_local_trips(
    host: str = "127.0.0.1", port: int = 6200, *, timeout_seconds: float = 2.0
) -> bool:
    """Confirm that the local Parser is registered without parsing user text."""
    transport = LocalTripsTransport(host, port, timeout_seconds=timeout_seconds)
    tag = f"SEMAN2-HEALTH-{os.getpid()}-{time.time_ns()}"
    name = f"{tag}-CLIENT"
    messages = (
        f"(register :name {name})",
        f"(request :receiver PARSER :reply-with {tag} :content (seman2-health))",
    )
    deadline = time.monotonic() + timeout_seconds
    buffer = bytearray()
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds) as connection:
            connection.sendall(("\n".join(messages) + "\n").encode("utf-8"))
            while time.monotonic() < deadline:
                while (expression := _complete_expression(buffer)) is not None:
                    message = parse_kqml(expression)
                    consumed = buffer.find(expression) + len(expression)
                    del buffer[:consumed]
                    if (
                        _same(_get(message, ":IN-REPLY-TO"), tag)
                        and _same(_get(message, ":SENDER"), "PARSER")
                        and any(_same(message[0], verb) for verb in ("SORRY", "ERROR"))
                    ):
                        return True
                connection.settimeout(max(0.1, deadline - time.monotonic()))
                chunk = connection.recv(8192)
                if not chunk:
                    return False
                buffer.extend(chunk)
    except (OSError, TimeoutError, ConnectionError, KqmlProtocolError):
        return False
    return False


def _source_span(start: int, end: int, input_spans: Sequence[SourceSpan]) -> SourceSpan:
    for span in input_spans:
        if start >= span.start and end <= span.end:
            return SourceSpan(
                start=start,
                end=end,
                evidence_id=span.evidence_id,
                evidence_start=start - span.start,
                evidence_end=end - span.start,
            )
    return SourceSpan(start=start, end=end)


def _cover(spans: Sequence[SourceSpan], input_spans: Sequence[SourceSpan]) -> SourceSpan | None:
    if not spans:
        return None
    return _source_span(min(item.start for item in spans), max(item.end for item in spans), input_spans)


def _keyword_attributes(items: Any) -> dict[str, Any]:
    if not isinstance(items, list):
        return {}
    result: dict[str, Any] = {}
    index = 1
    while index + 1 < len(items):
        key = items[index]
        if isinstance(key, str) and key.startswith(":"):
            result[key] = items[index + 1]
            index += 2
        else:
            index += 1
    return result


def _semantic_projection(
    utterance: list[Any], prefix: str, input_spans: Sequence[SourceSpan]
) -> Projection:
    terms = _get(utterance, ":TERMS", [])
    terms = terms if isinstance(terms, list) else []
    variables = {_atom(_get(term, ":VAR")) for term in terms if isinstance(term, list)}
    variables.discard("")
    nodes: list[ProjectionNode] = []
    edges: list[ProjectionEdge] = []
    ids = {variable: f"{prefix}:sem:{variable}" for variable in variables}
    for index, term in enumerate(terms):
        if not isinstance(term, list):
            continue
        native_id = _atom(_get(term, ":VAR")) or f"anonymous-{index}"
        lf = _get(term, ":LF", [])
        start, end = _integer(_get(term, ":START")), _integer(_get(term, ":END"))
        attributes = {
            "native_id": native_id,
            "native_term": term,
            "native_fields": _keyword_attributes(term),
            "native_lf": lf,
        }
        if isinstance(lf, list):
            attributes["indicator"] = lf[0] if lf else None
            attributes["type"] = lf[2] if len(lf) > 2 else None
            lf_fields = _keyword_attributes(lf)
            attributes["lf_fields"] = lf_fields
            for relation, value in lf_fields.items():
                candidates = value if isinstance(value, list) else [value]
                for position, candidate in enumerate(candidates):
                    if isinstance(candidate, str) and candidate in variables:
                        edges.append(
                            ProjectionEdge(
                                source_id=ids.get(native_id, f"{prefix}:sem:{native_id}"),
                                target_id=ids[candidate],
                                relation=relation.removeprefix(":"),
                                attributes={"position": position, "native_relation": relation},
                            )
                        )
        nodes.append(
            ProjectionNode(
                node_id=ids.get(native_id, f"{prefix}:sem:{native_id}"),
                category="lf-term",
                attributes=attributes,
                span=_source_span(start, end, input_spans) if start is not None and end is not None else None,
                native_path=f":TERMS/{index}",
            )
        )
    root = _atom(_get(utterance, ":ROOT"))
    roots = (ids[root],) if root in ids else ()
    return Projection(
        projection_id=f"{prefix}:semantic",
        family="semantic",
        nodes=tuple(nodes),
        edges=tuple(edges),
        roots=roots,
        metadata={"native_terms_present": bool(terms)},
    )


_PUNCTUATION = {
    "PUNC-PERIOD": ".",
    "PUNC-COMMA": ",",
    "PUNC-QUESTION-MARK": "?",
    "PUNC-EXCLAMATION-MARK": "!",
    "PUNC-COLON": ":",
    "PUNC-SEMICOLON": ";",
}


def _surface_token(native: str) -> str:
    value = native.rsplit("::", 1)[-1]
    return _PUNCTUATION.get(value.upper(), value.replace("^", "'"))


def _align_words(words: list[Any], text: str) -> list[tuple[str, int | None, int | None]]:
    result: list[tuple[str, int | None, int | None]] = []
    cursor = 0
    folded = text.casefold()
    for raw in words:
        native = _atom(raw)
        surface = _surface_token(native)
        start = folded.find(surface.casefold(), cursor)
        if start < 0:
            result.append((native, None, None))
            continue
        end = start + len(surface)
        result.append((native, start, end))
        cursor = end
    return result


def _tree_children(tree: Any) -> list[Any]:
    children = _get(tree, ":SUB", [])
    return children if isinstance(children, list) else []


def _tree_lexeme(tree: Any) -> str:
    """Return the native W::LEX value carried by a tree node, if present."""
    features = _get(tree, ":FEATS", [])
    if not isinstance(features, list):
        return ""
    for feature in features:
        if (
            isinstance(feature, list)
            and len(feature) > 1
            and _same(feature[0], "W::LEX")
        ):
            return _atom(feature[1])
    return ""


def _structural_projection(
    utterance: list[Any], prefix: str, input_text: str, input_spans: Sequence[SourceSpan]
) -> Projection:
    native_words = _get(utterance, ":WORDS", [])
    native_words = native_words if isinstance(native_words, list) else []
    aligned = _align_words(native_words, input_text)
    nodes: list[ProjectionNode] = []
    edges: list[ProjectionEdge] = []
    word_ids: list[str] = []
    word_spans: list[SourceSpan | None] = []
    word_natives: list[str] = []
    for index, (native, start, end) in enumerate(aligned):
        node_id = f"{prefix}:word:{index}"
        word_ids.append(node_id)
        word_natives.append(native)
        span = _source_span(start, end, input_spans) if start is not None and end is not None else None
        word_spans.append(span)
        nodes.append(
            ProjectionNode(
                node_id=node_id,
                category="parser-word",
                attributes={"native_word": native, "surface": _surface_token(native), "position": index},
                span=span,
                native_path=f":WORDS/{index}",
            )
        )

    tree = _get(utterance, ":TREE", [])
    roots = tree if isinstance(tree, list) and tree and isinstance(tree[0], list) else [tree]
    root_ids: list[str] = []
    leaf_cursor = [0]
    source_cursor = [0]
    synthetic_words = [0]

    def add_tree_word(native: str, path: tuple[int, ...]) -> int:
        """Anchor a lexical tree leaf omitted from the native :WORDS list."""
        surface = _surface_token(native)
        start = input_text.casefold().find(surface.casefold(), source_cursor[0])
        end = start + len(surface) if start >= 0 else None
        span = (
            _source_span(start, end, input_spans)
            if start >= 0 and end is not None
            else None
        )
        index = len(word_ids)
        word_ids.append(f"{prefix}:word:{index}")
        word_natives.append(native)
        word_spans.append(span)
        nodes.append(
            ProjectionNode(
                node_id=word_ids[-1],
                category="parser-word",
                attributes={
                    "native_word": native,
                    "surface": surface,
                    "position": index,
                    "inferred_from_tree": True,
                },
                span=span,
                native_path=":TREE/" + "/".join(map(str, path)) + "/:FEATS/W::LEX",
            )
        )
        synthetic_words[0] += 1
        return index

    def walk(item: Any, path: tuple[int, ...]) -> tuple[str, SourceSpan | None]:
        node_id = f"{prefix}:tree:" + ".".join(map(str, path))
        children = _tree_children(item)
        child_rows = [walk(child, (*path, index)) for index, child in enumerate(children)]
        if not children:
            native_lexeme = _tree_lexeme(item)
            word_index: int | None = None
            if native_lexeme:
                for candidate in range(leaf_cursor[0], len(word_ids)):
                    if _same(word_natives[candidate], native_lexeme):
                        word_index = candidate
                        break
                if word_index is None and _surface_token(native_lexeme) in _PUNCTUATION.values():
                    word_index = add_tree_word(native_lexeme, path)
            elif leaf_cursor[0] < len(word_ids):
                # Older TRIPS trees sometimes omit W::LEX on their leaves.
                word_index = leaf_cursor[0]
            if word_index is not None:
                leaf_cursor[0] = max(leaf_cursor[0], word_index + 1)
                span = word_spans[word_index]
                if span is not None:
                    source_cursor[0] = max(source_cursor[0], span.end)
                edges.append(ProjectionEdge(node_id, word_ids[word_index], "realizes-token", {"position": word_index}))
            else:
                span = None
        else:
            span = _cover([row[1] for row in child_rows if row[1] is not None], input_spans)
            for position, (child_id, _) in enumerate(child_rows):
                edges.append(ProjectionEdge(node_id, child_id, "contains", {"position": position}))
        nodes.append(
            ProjectionNode(
                node_id=node_id,
                category="tree-node",
                attributes={
                    "native_category": item[0] if isinstance(item, list) and item else None,
                    "native_tree": item,
                    "native_fields": _keyword_attributes(item),
                },
                span=span,
                native_path=":TREE/" + "/".join(map(str, path)),
            )
        )
        return node_id, span

    for index, root in enumerate(roots):
        if isinstance(root, list) and root:
            root_ids.append(walk(root, (index,))[0])
    return Projection(
        projection_id=f"{prefix}:structural",
        family="structural",
        nodes=tuple(nodes),
        edges=tuple(edges),
        roots=tuple(root_ids),
        metadata={
            "native_words": native_words,
            "native_tree_present": bool(tree),
            "tree_lexemes_added": synthetic_words[0],
        },
    )


def project_kqml(
    payload: bytes,
    *,
    analysis_id: str,
    input_text: str,
    input_spans: Sequence[SourceSpan],
) -> tuple[InterpretationSegment, ...]:
    message = parse_kqml(payload)
    content = _result_content(message)
    if content is None:
        raise KqmlProtocolError("KQML payload contains no TRIPS parse result")
    if _same(content[0], "FAILED-TO-PARSE"):
        return (InterpretationSegment(segment_index=0, status="failed-to-parse", hypotheses=()),)
    if _same(content[0], "NEW-SPEECH-ACT"):
        utterances = [content[1]] if len(content) > 1 else []
    else:
        utterances = content[1] if len(content) > 1 and isinstance(content[1], list) else []
    hypotheses: list[InterpretationHypothesis] = []
    for rank, utterance in enumerate(utterances):
        if not isinstance(utterance, list):
            continue
        prefix = f"{analysis_id}:s0:h{rank}"
        semantic = _semantic_projection(utterance, prefix, input_spans)
        structural = _structural_projection(utterance, prefix, input_text, input_spans)
        cross_links: list[ProjectionEdge] = []
        for semantic_node in semantic.nodes:
            if semantic_node.span is None:
                continue
            for structural_node in structural.nodes:
                if structural_node.span is None:
                    continue
                if semantic_node.span.start < structural_node.span.end and structural_node.span.start < semantic_node.span.end:
                    cross_links.append(
                        ProjectionEdge(
                            semantic_node.node_id,
                            structural_node.node_id,
                            "span-overlap",
                            {
                                "start": max(semantic_node.span.start, structural_node.span.start),
                                "end": min(semantic_node.span.end, structural_node.span.end),
                            },
                        )
                    )
        reliability = _get(utterance, ":RELIABILITY")
        try:
            score = float(reliability) if reliability is not None else None
        except (TypeError, ValueError):
            score = None
        hypotheses.append(
            InterpretationHypothesis(
                hypothesis_id=f"{prefix}:hypothesis",
                rank=rank,
                score=score,
                semantic=semantic,
                structural=structural,
                cross_links=tuple(cross_links),
                parser_attributes={"native_utterance": utterance, "native_fields": _keyword_attributes(utterance)},
            )
        )
    if not hypotheses:
        raise KqmlProtocolError("TRIPS result contains no utterance hypothesis")
    spans = [
        node.span
        for hypothesis in hypotheses
        for node in (*hypothesis.semantic.nodes, *hypothesis.structural.nodes)
        if node.span is not None
    ]
    return (
        InterpretationSegment(
            segment_index=0,
            status="parsed",
            hypotheses=tuple(hypotheses),
            span=_cover(spans, input_spans),
        ),
    )
