"""Compatibility helpers for provisional source-span recognizers only."""
def _parts(components, *functions):
    return tuple(c for c in components if c.get("function") in functions)


def _specs():
    specs = []

    def add(category, a, b, kind="lexical", **features):
        specs.append((category, a, b, kind, features))

    def marks(category, a, b):
        add(category, a, b, "source-punctuation")

    def match_parts(match, offset, parts):
        for group, cat, kind, features in parts:
            a, b = match.span(group)
            add(cat, offset + a, offset + b, kind, **features)

    return specs, add, marks, match_parts


