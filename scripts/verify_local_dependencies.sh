#!/usr/bin/env bash
set -euo pipefail

SEMAN2_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SEMAN2_ROOT/scripts/activate_local.sh"
cd "$SEMAN2_ROOT"

pass() { printf 'OK  %s\n' "$1"; }

python - <<'PY'
import duckdb, delphin, linkgrammar, nltk
import bs4, ijson, lxml, mwparserfromhell, networkx, numpy, odis
import orjson, polars, pyarrow, scipy, tree_sitter, z3, zstandard
from nltk.corpus import framenet, propbank, verbnet, wordnet

assert wordnet.synsets("dog")
assert verbnet.classids("run")
assert propbank.roleset("eat.01").attrib["id"] == "eat.01"
assert len(framenet.frames()) > 0
print("OK  environnement Python principal et corpus NLTK")
PY

printf 'A dog barks.\n' | ace -g "$ERG_DAT" -1Tf >/dev/null
pass "ACE + ERG"

link-parser --version >/dev/null 2>&1
pass "Link Grammar"

test -d "$SEMLINK_HOME/instances"
test -n "$(find "$SUMO_HOME" -type f -name '*.kif' -print -quit)"
pass "SemLink + SUMO"

(cd "$TREETAGGER_HOME" && printf 'Ceci est un test.\n' | cmd/tree-tagger-french >/dev/null)
pass "TreeTagger français"

java -jar "$HEIDELTIME_HOME/de.unihd.dbs.heideltime.standalone.jar" \
  plans/architecture_systeme_cognitif_symbolique_v2.md -l french -t narratives \
  -c "$HEIDELTIME_HOME/config.props" >/dev/null
pass "HeidelTime"

unzip -t "$SIMPLENLG_JAR" >/dev/null
pass "SimpleNLG"

PYTHONPATH="$SOAR_BIN" LD_LIBRARY_PATH="$SOAR_BIN${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" python - <<'PY'
import Python_sml_ClientInterface as sml
kernel = sml.Kernel.CreateKernelInNewThread()
assert not kernel.HadError()
kernel.Shutdown()
print("OK  Soar SML Python")
PY

swipl -q -g 'writeln(ok),halt' | grep -qx ok
pass "SWI-Prolog"

PATH="$SEMAN2_ROOT/.local/bin:$PATH" \
  "$SEMAN2_ROOT/.venv-popper/bin/python" -c 'import janus_swi, popper'
pass "Popper"

"$SEMAN2_ROOT/.venv-rst/bin/python" -c 'import isanlp, isanlp_rst, torch, transformers'
pass "IsaNLP RST"

duckling_log="$(mktemp)"
duckling-example-exe >"$duckling_log" 2>&1 &
duckling_pid=$!
cleanup_duckling() {
  kill "$duckling_pid" 2>/dev/null || true
  wait "$duckling_pid" 2>/dev/null || true
}
trap cleanup_duckling EXIT
duckling_response=''
for _attempt in $(seq 1 30); do
  if duckling_response="$(curl -fsS -XPOST http://127.0.0.1:8000/parse \
      --data 'locale=fr_FR&text=demain à huit heures' 2>/dev/null)"; then
    break
  fi
  sleep 1
done
printf '%s' "$duckling_response" | grep -q '"dim":"time"'
cleanup_duckling
trap - EXIT
pass "Duckling (service HTTP français)"

printf 'Toutes les dépendances locales vérifiables sont opérationnelles.\n'
