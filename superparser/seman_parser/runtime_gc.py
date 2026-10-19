"""CPython runtime policy for the long-lived WordNet-backed Layer 1 parser.

After the first lexical lattice has populated all four WordNet POS data tables,
move *currently live* objects to CPython's permanent GC generation once per
process. Automatic cycle collection remains enabled for future parse forests.

Important: gc.freeze() is process-global, not a selective WordNet freeze.
Opt out with SEMAN2_DISABLE_GC_FREEZE=1 before starting the process when
embedding Seman2 in a long-running application with other object lifetimes.
"""

from __future__ import annotations

import gc
import os
from threading import Lock

from .wordnet import POS_ADJ, POS_ADV, POS_NOUN, POS_VERB

_lock = Lock()
_frozen = False
_WORDNET_POSITIONS = frozenset((POS_NOUN, POS_VERB, POS_ADJ, POS_ADV))


def freeze_loaded_wordnet_once(lexicon: object) -> bool:
    """Freeze only after WordNet is loaded; never freeze an active parse forest.

    Returns True if this invocation performed the one-time process-global
    freeze. Does not force WordNet loading, change grammar, disable automatic
    GC, alter parser caching, or hold onto individual sentence results.
    """
    global _frozen
    if _frozen or not gc.isenabled() or not hasattr(gc, "freeze"):
        return False
    if os.environ.get("SEMAN2_DISABLE_GC_FREEZE", "").lower() in ("1", "true", "yes"):
        return False
    backend = getattr(lexicon, "_wordnet", None)
    if backend is None or not getattr(backend, "_loaded_index", False):
        return False
    if not _WORDNET_POSITIONS.issubset(getattr(backend, "_loaded_data", ())):
        return False

    with _lock:
        if _frozen or not gc.isenabled():
            return False
        # The lattice is already constructed, but the first packed forest has
        # not yet been allocated. Run one full collection to avoid preserving
        # cyclic garbage in the permanent generation.
        gc.collect(2)
        gc.freeze()
        _frozen = True
        return True
