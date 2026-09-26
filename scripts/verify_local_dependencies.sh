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
from nltk.corpus import framenet, propbank, stopwords, verbnet, wordnet
from nltk.tokenize import TextTilingTokenizer

assert wordnet.synsets("dog")
assert verbnet.classids("run")
assert propbank.roleset("eat.01").attrib["id"] == "eat.01"
assert len(framenet.frames()) > 0
assert stopwords.words("english")
assert TextTilingTokenizer()
print("OK  environnement Python principal et corpus NLTK")
PY

CONVOKIT_CONFIG="$CONVOKIT_CONFIG" \
CONVOKIT_DATA_DIR="$CONVOKIT_DATA_DIR" \
CONVOKIT_MODEL_DIR="$CONVOKIT_MODEL_DIR" \
"$CONVOKIT_PYTHON" - <<'PY'
import convokit
import spacy
import coreferee
from convokit import Conversation, Corpus, Speaker, Utterance
from convokit.expected_context_framework import ExpectedContextModel
from convokit.prompt_types import PromptTypes

speaker_a = Speaker(id="a")
speaker_b = Speaker(id="b")
corpus = Corpus(
    utterances=[
        Utterance(id="u1", speaker=speaker_a, text="Where does Alice live?"),
        Utterance(id="u2", speaker=speaker_b, text="In Montreal.", reply_to="u1"),
    ]
)
assert corpus.get_utterance("u2").reply_to == "u1"
assert ExpectedContextModel is not None and PromptTypes is not None
assert spacy.load("en_core_web_sm")("Alice lives in Montreal.")

for model, text in (
    ("en_core_web_sm", "Alice met Bob. She greeted him."),
    ("fr_core_news_sm", "Alice a rencontré Bob. Elle lui a parlé."),
):
    nlp = spacy.load(model)
    nlp.add_pipe("coreferee")
    assert len(nlp(text)._.coref_chains) > 0

switchboard = Corpus(filename=f"{__import__('os').environ['CONVOKIT_DATA_DIR']}/switchboard-corpus")
assert len(list(switchboard.iter_utterances())) == 122646
print("OK  ConvoKit + Coreferee/spaCy anglais-français + corpus Switchboard")
PY
"$SEMAN2_ROOT/.local/bin/uv" pip check --python "$CONVOKIT_PYTHON"
pass "cohérence des dépendances ConvoKit"

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
  plans/architecture_systeme_cognitif_symbolique.md -l french -t narratives \
  -c "$HEIDELTIME_HOME/config.props" >/dev/null
pass "HeidelTime"

unzip -t "$SIMPLENLG_JAR" >/dev/null
pass "SimpleNLG"

corenlp_english="$(
  printf 'Alice met Bob. She greeted him.\n' | java -Xmx3g \
    -cp "$CORENLP_HOME/*" edu.stanford.nlp.pipeline.StanfordCoreNLP \
    -annotators tokenize,ssplit,pos,lemma,ner,parse,coref \
    -coref.algorithm neural -outputFormat json 2>/dev/null
)"
printf '%s' "$corenlp_english" | grep -q '"corefs"'
pass "Stanford CoreNLP coréférence anglaise"

corenlp_french="$(
  printf 'Alice habite à Montréal. Elle y travaille.\n' | java -Xmx3g \
    -cp "$CORENLP_HOME/*" edu.stanford.nlp.pipeline.StanfordCoreNLP \
    -props StanfordCoreNLP-french.properties \
    -annotators tokenize,ssplit,pos,lemma,ner,depparse \
    -outputFormat json 2>/dev/null
)"
printf '%s' "$corenlp_french" | grep -q 'Montréal'
pass "Stanford CoreNLP analyse française"

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

test -x "$SEMAN2_ROOT/.local/bin/NuWLS-c"
PATH="$SEMAN2_ROOT/.local/bin:$PATH" \
  "$SEMAN2_ROOT/.venv-popper/bin/python" - <<'PY'
from popper import maxsat

cost, model = maxsat.anytime_maxsat_solve(
    hard_clauses=[[1]],
    soft_clauses=[[-1]],
    weights=[1],
    timeout=1,
)
assert cost == 1
assert model is not None and model[0] == 1
PY
pass "NuWLS-c"

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
