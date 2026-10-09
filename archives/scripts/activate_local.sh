#!/usr/bin/env bash

# À sourcer depuis n'importe quel répertoire :
#   source scripts/activate_local.sh

SEMAN2_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export SEMAN2_ROOT

export VIRTUAL_ENV="$SEMAN2_ROOT/.venv"
export JAVA_HOME="$SEMAN2_ROOT/.local/opt/jre"
export PATH="$SEMAN2_ROOT/.venv/bin:$JAVA_HOME/bin:$SEMAN2_ROOT/.local/bin:$SEMAN2_ROOT/.local/opt/sbcl/usr/bin:$SEMAN2_ROOT/.local/opt/sqlite/usr/bin:$SEMAN2_ROOT/.local/opt/xslt/usr/bin:$SEMAN2_ROOT/.local/opt/flite/bin:$SEMAN2_ROOT/.local/opt/duckling/bin:$SEMAN2_ROOT/.local/opt/treetagger/bin:$SEMAN2_ROOT/.local/opt/treetagger/cmd:$SEMAN2_ROOT/.local/opt/pcre/bin:$PATH"

export NLTK_DATA="$SEMAN2_ROOT/.local/share/nltk_data"
export HF_HOME="$SEMAN2_ROOT/.local/share/huggingface"
export CONVOKIT_HOME="$SEMAN2_ROOT/.local/share/convokit"
export CONVOKIT_CONFIG="$CONVOKIT_HOME/config.yml"
export CONVOKIT_DATA_DIR="$CONVOKIT_HOME/corpora"
export CONVOKIT_MODEL_DIR="$CONVOKIT_HOME/models"
export CONVOKIT_PYTHON="$SEMAN2_ROOT/.venv-conversation/bin/python"
export CORENLP_HOME="$SEMAN2_ROOT/.local/opt/stanford-corenlp"
export ACE_BIN="$SEMAN2_ROOT/.local/bin/ace"
export ERG_DAT="$SEMAN2_ROOT/.local/share/erg/erg-2018-x86-64-0.9.34.dat"
export SEMLINK_HOME="$SEMAN2_ROOT/.local/share/semlink"
export SUMO_HOME="$SEMAN2_ROOT/.local/share/sumo"
export HEIDELTIME_HOME="$SEMAN2_ROOT/.local/opt/heideltime"
export TREETAGGER_HOME="$SEMAN2_ROOT/.local/opt/treetagger"
export SOAR_HOME="$SEMAN2_ROOT/.local/opt/soar"
export SOAR_BIN="$SOAR_HOME/bin/linux_x86-64"
export STACK_ROOT="$SEMAN2_ROOT/.local/stack"
export POPPER_HOME="$SEMAN2_ROOT/.local/src/popper"
export SIMPLENLG_JAR="$SEMAN2_ROOT/.local/opt/simplenlg/SimpleNLG-4.5.0.jar"
export DUCKLING_HOME="$SEMAN2_ROOT/.local/src/duckling"
export SEMIOTIC_PYTHON="$SEMAN2_ROOT/.venv-semiotic/bin/python"
export FLITE_HOME="$SEMAN2_ROOT/.local/opt/flite"
export DIALOGUE_PYTHON="$SEMAN2_ROOT/.venv-dialogue/bin/python"
export DYLAN_HOME="$SEMAN2_ROOT/.local/src/dylan"
export TRIPS_BASE="$SEMAN2_ROOT/.local/src/cogent-v3"
export TRIPS_SYSNAME="cogent"
export SBCL_HOME="$SEMAN2_ROOT/.local/opt/sbcl/usr/lib/sbcl"
export PERL5LIB="$SEMAN2_ROOT/.local/opt/perl/usr/lib/x86_64-linux-gnu/perl5/5.38${PERL5LIB:+:$PERL5LIB}"

export PYTHONPATH="$SOAR_BIN${PYTHONPATH:+:$PYTHONPATH}"
export CLASSPATH="$SIMPLENLG_JAR:$CORENLP_HOME/*${CLASSPATH:+:$CLASSPATH}"
export PKG_CONFIG_PATH="$SEMAN2_ROOT/.local/opt/link-grammar/lib/pkgconfig:$SEMAN2_ROOT/.local/opt/pcre/lib/pkgconfig:$SEMAN2_ROOT/.local/opt/swipl/share/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export CPATH="$SEMAN2_ROOT/.local/opt/gmp/include:$SEMAN2_ROOT/.local/opt/pcre/include${CPATH:+:$CPATH}"
export LIBRARY_PATH="$SEMAN2_ROOT/.local/opt/gmp/lib:$SEMAN2_ROOT/.local/opt/pcre/lib:$SEMAN2_ROOT/.local/opt/link-grammar/lib${LIBRARY_PATH:+:$LIBRARY_PATH}"
export LD_LIBRARY_PATH="$SOAR_BIN:$SEMAN2_ROOT/.local/opt/gmp/lib:$SEMAN2_ROOT/.local/opt/pcre/lib:$SEMAN2_ROOT/.local/opt/link-grammar/lib:$SEMAN2_ROOT/.local/opt/swipl/lib/swipl/lib/x86_64-linux:$SEMAN2_ROOT/.local/opt/swipl/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
