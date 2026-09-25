#!/usr/bin/env bash
set -euo pipefail

SEMAN2_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL="$SEMAN2_ROOT/.local"
BIN="$LOCAL/bin"
OPT="$LOCAL/opt"
SRC="$LOCAL/src"
BUILD="$LOCAL/build"
DOWNLOADS="$LOCAL/downloads"
JOBS="${SEMAN2_BUILD_JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || printf '4')}"
SKIP_VERIFY=false

if [[ "${1:-}" == "--check" ]]; then
  exec "$SEMAN2_ROOT/scripts/verify_local_dependencies.sh"
elif [[ "${1:-}" == "--skip-verify" ]]; then
  SKIP_VERIFY=true
elif [[ $# -gt 0 ]]; then
  printf 'Usage: ./scripts/seman2 install-tools [--check|--skip-verify]\n' >&2
  exit 2
fi

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  printf 'Cet installateur supporte actuellement Linux x86_64 seulement.\n' >&2
  exit 1
fi

for command_name in curl git tar unzip make gcc g++ cmake pkg-config gzip bzip2 xz; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'Prérequis système absent: %s\n' "$command_name" >&2
    exit 1
  fi
done

mkdir -p "$BIN" "$OPT" "$SRC" "$BUILD" "$DOWNLOADS" \
  "$LOCAL/share" "$LOCAL/cache/uv" "$LOCAL/python"

temp_root="$(mktemp -d "$LOCAL/install-tmp.XXXXXX")"
cleanup() { rm -rf "$temp_root"; }
trap cleanup EXIT

log() { printf '\n==> %s\n' "$*"; }

download() {
  local url="$1"
  local destination="$2"
  if [[ -s "$destination" ]]; then
    return
  fi
  mkdir -p "$(dirname "$destination")"
  curl -L --fail --retry 5 --retry-all-errors -o "$destination.part" "$url"
  mv "$destination.part" "$destination"
}

extract_tar() {
  local archive="$1"
  local destination="$2"
  mkdir -p "$destination"
  tar -xf "$archive" -C "$destination" --strip-components=1
}

clone_at() {
  local repository="$1"
  local revision="$2"
  local destination="$3"
  if [[ ! -d "$destination/.git" ]]; then
    if [[ -e "$destination" ]]; then
      printf 'Répertoire non Git inattendu: %s\n' "$destination" >&2
      exit 1
    fi
    git clone --filter=blob:none --no-checkout "$repository" "$destination"
  fi
  if [[ "$(git -C "$destination" rev-parse HEAD 2>/dev/null || true)" != "$revision" ]]; then
    git -C "$destination" fetch --depth 1 origin "$revision"
    git -C "$destination" checkout --detach "$revision"
  fi
}

log "uv et interpréteurs Python locaux"
if [[ ! -x "$BIN/uv" ]]; then
  uv_archive="$DOWNLOADS/uv-0.12.17-linux-x86_64.tar.gz"
  download \
    "https://github.com/astral-sh/uv/releases/download/0.12.17/uv-x86_64-unknown-linux-gnu.tar.gz" \
    "$uv_archive"
  mkdir -p "$temp_root/uv"
  tar -xzf "$uv_archive" -C "$temp_root/uv"
  install -m 0755 "$temp_root"/uv/*/uv "$BIN/uv"
fi
export UV_CACHE_DIR="$LOCAL/cache/uv"
export UV_PYTHON_INSTALL_DIR="$LOCAL/python"
"$BIN/uv" python install 3.12 3.14
if [[ ! -x "$SEMAN2_ROOT/.venv/bin/python" ]]; then
  "$BIN/uv" venv --python 3.12 "$SEMAN2_ROOT/.venv"
fi
if [[ ! -x "$SEMAN2_ROOT/.venv-popper/bin/python" ]]; then
  "$BIN/uv" venv --python 3.14 "$SEMAN2_ROOT/.venv-popper"
fi
if [[ ! -x "$SEMAN2_ROOT/.venv-rst/bin/python" ]]; then
  "$BIN/uv" venv --python 3.12 "$SEMAN2_ROOT/.venv-rst"
fi
"$BIN/uv" pip install --python "$SEMAN2_ROOT/.venv/bin/python" \
  -r "$SEMAN2_ROOT/requirements-cognitive.txt"

log "corpus NLTK"
NLTK_DATA="$LOCAL/share/nltk_data" "$SEMAN2_ROOT/.venv/bin/python" \
  -m nltk.downloader -d "$LOCAL/share/nltk_data" \
  wordnet verbnet propbank treebank framenet_v17

log "Java Temurin local"
if [[ ! -x "$OPT/jre/bin/java" ]]; then
  jre_archive="$DOWNLOADS/OpenJDK17-jre.tar.gz"
  download \
    "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jre/hotspot/normal/eclipse" \
    "$jre_archive"
  extract_tar "$jre_archive" "$OPT/jre"
fi

log "ACE et ERG"
if [[ ! -x "$OPT/ace/ace" ]]; then
  ace_archive="$DOWNLOADS/ace-0.9.34-x86-64.tar.gz"
  download \
    "https://sweaglesw.org/linguistics/ace/download/ace-0.9.34-x86-64.tar.gz" \
    "$ace_archive"
  extract_tar "$ace_archive" "$OPT/ace"
fi
mkdir -p "$LOCAL/share/erg"
if [[ ! -s "$LOCAL/share/erg/erg-2018-x86-64-0.9.34.dat" ]]; then
  erg_archive="$DOWNLOADS/erg-2018-x86-64-0.9.34.dat.bz2"
  download \
    "https://sweaglesw.org/linguistics/ace/download/erg-2018-x86-64-0.9.34.dat.bz2" \
    "$erg_archive"
  bzip2 -dc "$erg_archive" > \
    "$LOCAL/share/erg/erg-2018-x86-64-0.9.34.dat.part"
  mv "$LOCAL/share/erg/erg-2018-x86-64-0.9.34.dat.part" \
    "$LOCAL/share/erg/erg-2018-x86-64-0.9.34.dat"
fi
ln -sfn ../opt/ace/ace "$BIN/ace"

log "Flex et Link Grammar"
if [[ ! -x "$OPT/flex/bin/flex" ]]; then
  flex_archive="$DOWNLOADS/flex-2.6.4.tar.gz"
  download \
    "https://github.com/westes/flex/releases/download/v2.6.4/flex-2.6.4.tar.gz" \
    "$flex_archive"
  [[ -d "$SRC/flex-2.6.4" ]] || extract_tar "$flex_archive" "$SRC/flex-2.6.4"
  mkdir -p "$BUILD/flex-2.6.4"
  (
    cd "$BUILD/flex-2.6.4"
    "$SRC/flex-2.6.4/configure" --prefix="$OPT/flex"
    make -j"$JOBS"
    make install
  )
fi
if [[ ! -x "$OPT/link-grammar/bin/link-parser" ]]; then
  link_archive="$DOWNLOADS/link-grammar-5.13.0.tar.gz"
  download \
    "https://github.com/opencog/link-grammar/archive/refs/tags/link-grammar-5.13.0.tar.gz" \
    "$link_archive"
  [[ -d "$SRC/link-grammar-5.13.0" ]] || \
    extract_tar "$link_archive" "$SRC/link-grammar-5.13.0"
  mkdir -p "$BUILD/link-grammar"
  (
    cd "$BUILD/link-grammar"
    env PATH="$OPT/flex/bin:$SEMAN2_ROOT/.venv/bin:$PATH" \
      PYTHON="$SEMAN2_ROOT/.venv/bin/python" \
      "$SRC/link-grammar-5.13.0/configure" \
      --prefix="$OPT/link-grammar" --disable-java-bindings \
      --disable-aspell --disable-hunspell --with-python-sys-prefix
    make -j"$JOBS"
    make install
  )
fi
ln -sfn ../opt/link-grammar/bin/link-parser "$BIN/link-parser"
ln -sfn ../opt/link-grammar/bin/link-generator "$BIN/link-generator"

log "TreeTagger et HeidelTime"
if [[ ! -x "$OPT/treetagger/bin/tree-tagger" ]]; then
  tt_binary="$DOWNLOADS/tree-tagger-linux-3.2.5.tar.gz"
  tt_scripts="$DOWNLOADS/tagger-scripts.tar.gz"
  tt_english="$DOWNLOADS/english.par.gz"
  tt_french="$DOWNLOADS/french.par.gz"
  tt_base="https://www.cis.uni-muenchen.de/~schmid/tools/TreeTagger/data"
  download "$tt_base/tree-tagger-linux-3.2.5.tar.gz" "$tt_binary"
  download "$tt_base/tagger-scripts.tar.gz" "$tt_scripts"
  download "$tt_base/english.par.gz" "$tt_english"
  download "$tt_base/french.par.gz" "$tt_french"
  mkdir -p "$OPT/treetagger"
  tar -xzf "$tt_binary" -C "$OPT/treetagger"
  tar -xzf "$tt_scripts" -C "$OPT/treetagger"
  gzip -dc "$tt_english" > "$OPT/treetagger/lib/english.par"
  gzip -dc "$tt_french" > "$OPT/treetagger/lib/french.par"
fi
if [[ ! -s "$OPT/heideltime/de.unihd.dbs.heideltime.standalone.jar" ]]; then
  heidel_archive="$DOWNLOADS/heideltime-standalone-2.2.1.tar.gz"
  download \
    "https://github.com/HeidelTime/heideltime/releases/download/VERSION2.2.1/heideltime-standalone-2.2.1.tar.gz" \
    "$heidel_archive"
  extract_tar "$heidel_archive" "$OPT/heideltime"
fi
sed -i \
  "s|^treeTaggerHome[[:space:]]*=.*|treeTaggerHome = $OPT/treetagger|" \
  "$OPT/heideltime/config.props"

log "SimpleNLG"
mkdir -p "$OPT/simplenlg"
download \
  "https://repo1.maven.org/maven2/uk/ac/abdn/SimpleNLG/4.5.0/SimpleNLG-4.5.0.jar" \
  "$OPT/simplenlg/SimpleNLG-4.5.0.jar"

log "SemLink et SUMO"
clone_at "https://github.com/cu-clear/semlink.git" \
  "2636bf5a4ae9c93b669a1184a8aaae9ca21552d3" "$LOCAL/share/semlink"
clone_at "https://github.com/ontologyportal/sumo.git" \
  "77f8fdd2a6e8970c68e452cecb051aaa441c0387" "$LOCAL/share/sumo"

log "Soar"
if [[ ! -x "$OPT/soar/bin/linux_x86-64/soar" ]]; then
  soar_archive="$DOWNLOADS/SoarSuite_9.6.5-Multiplatform.zip"
  download \
    "https://github.com/SoarGroup/Soar/releases/download/releases/9.6.5/SoarSuite_9.6.5-Multiplatform.zip" \
    "$soar_archive"
  mkdir -p "$temp_root/soar"
  unzip -q "$soar_archive" -d "$temp_root/soar"
  soar_root="$(dirname "$(find "$temp_root/soar" -name SoarCLI.sh -print -quit)")"
  mkdir -p "$OPT/soar"
  cp -a "$soar_root/." "$OPT/soar/"
fi
ln -sfn ../opt/soar/bin/linux_x86-64/soar "$BIN/soar"

log "GMP, PCRE, Stack et Duckling"
if [[ ! -s "$OPT/gmp/lib/libgmp.so" ]]; then
  gmp_archive="$DOWNLOADS/gmp-6.3.0.tar.xz"
  download "https://ftpmirror.gnu.org/gmp/gmp-6.3.0.tar.xz" "$gmp_archive"
  [[ -d "$SRC/gmp-6.3.0" ]] || extract_tar "$gmp_archive" "$SRC/gmp-6.3.0"
  mkdir -p "$BUILD/gmp-6.3.0"
  (
    cd "$BUILD/gmp-6.3.0"
    "$SRC/gmp-6.3.0/configure" --prefix="$OPT/gmp" --enable-cxx
    make -j"$JOBS"
    make install
  )
fi
if [[ ! -x "$OPT/pcre/bin/pcre-config" ]]; then
  pcre_archive="$DOWNLOADS/pcre-8.45.tar.gz"
  download \
    "https://sourceforge.net/projects/pcre/files/pcre/8.45/pcre-8.45.tar.gz/download" \
    "$pcre_archive"
  [[ -d "$SRC/pcre-8.45" ]] || extract_tar "$pcre_archive" "$SRC/pcre-8.45"
  mkdir -p "$BUILD/pcre-8.45"
  (
    cd "$BUILD/pcre-8.45"
    "$SRC/pcre-8.45/configure" --prefix="$OPT/pcre" \
      --enable-utf --enable-unicode-properties
    make -j"$JOBS"
    make install
  )
fi
if [[ ! -x "$OPT/stack/stack" ]]; then
  stack_archive="$DOWNLOADS/stack-3.11.1-linux-x86_64.tar.gz"
  download \
    "https://github.com/commercialhaskell/stack/releases/download/v3.11.1/stack-3.11.1-linux-x86_64.tar.gz" \
    "$stack_archive"
  extract_tar "$stack_archive" "$OPT/stack"
fi
ln -sfn ../opt/stack/stack "$BIN/stack"
clone_at "https://github.com/facebook/duckling.git" \
  "59a13ff87b1aa8be6b93d387244f8636b26185c5" "$SRC/duckling"
if [[ ! -x "$OPT/duckling/bin/duckling-example-exe" ]]; then
  mkdir -p "$OPT/duckling/bin" "$LOCAL/stack"
  (
    cd "$SRC/duckling"
    env STACK_ROOT="$LOCAL/stack" \
      LIBRARY_PATH="$OPT/gmp/lib:$OPT/pcre/lib" \
      CPATH="$OPT/gmp/include:$OPT/pcre/include" \
      LD_LIBRARY_PATH="$OPT/gmp/lib:$OPT/pcre/lib" \
      PKG_CONFIG_PATH="$OPT/pcre/lib/pkgconfig" \
      "$BIN/stack" build --copy-bins --local-bin-path "$OPT/duckling/bin"
  )
fi
ln -sfn ../opt/duckling/bin/duckling-example-exe "$BIN/duckling"

log "SWI-Prolog et Popper"
if [[ ! -x "$OPT/swipl/bin/swipl" ]]; then
  swipl_archive="$DOWNLOADS/swipl-9.2.9.tar.gz"
  download \
    "https://www.swi-prolog.org/download/stable/src/swipl-9.2.9.tar.gz" \
    "$swipl_archive"
  [[ -d "$SRC/swipl-9.2.9" ]] || extract_tar "$swipl_archive" "$SRC/swipl-9.2.9"
  mkdir -p "$BUILD/swipl-9.2.9"
  (
    cd "$BUILD/swipl-9.2.9"
    cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$OPT/swipl" \
      -DCMAKE_PREFIX_PATH="$OPT/gmp" -DINSTALL_DOCUMENTATION=OFF \
      -DBUILD_TESTING=OFF -DSWIPL_PACKAGE_LIST="clib;plunit" \
      "$SRC/swipl-9.2.9"
    cmake --build . -j"$JOBS"
    cmake --install .
  )
fi
ln -sfn ../opt/swipl/bin/swipl "$BIN/swipl"
clone_at "https://github.com/logic-and-learning-lab/Popper.git" \
  "5c608d3ec87e4975866042fe326e9a317277e021" "$SRC/popper"
env PATH="$BIN:$PATH" PKG_CONFIG_PATH="$OPT/swipl/share/pkgconfig" \
  LD_LIBRARY_PATH="$OPT/swipl/lib/swipl/lib/x86_64-linux:$OPT/swipl/lib" \
  "$BIN/uv" pip install --python "$SEMAN2_ROOT/.venv-popper/bin/python" \
  -e "$SRC/popper"

log "IsaNLP RST et modèle gumrrg"
clone_at "https://github.com/tchewik/isanlp_rst.git" \
  "cc8789f44c1341c3e7752b472634d75e81b62518" "$SRC/isanlp_rst"
"$BIN/uv" pip install --python "$SEMAN2_ROOT/.venv-rst/bin/python" \
  "isanlp @ git+https://github.com/iinemo/isanlp.git@2a102e59f9718acc7fe259dd8d83c66d5da39794" \
  -e "$SRC/isanlp_rst" "torch==2.14.0" "transformers==5.17.0"
mkdir -p "$LOCAL/share/huggingface"
if [[ ! -f "$LOCAL/share/huggingface/.seman2-rst-gumrrg-ready" ]]; then
  HF_HOME="$LOCAL/share/huggingface" NLTK_DATA="$LOCAL/share/nltk_data" \
    "$SEMAN2_ROOT/.venv-rst/bin/python" - <<'PY'
from isanlp_rst.parser import Parser

parser = Parser(
    hf_model_name="tchewik/isanlp_rst_v3",
    hf_model_version="gumrrg",
    cuda_device=-1,
)
result = parser("Il pleut. Nous restons donc à la maison.")
assert result["rst"]
PY
  touch "$LOCAL/share/huggingface/.seman2-rst-gumrrg-ready"
fi

log "Installation terminée"
if [[ "$SKIP_VERIFY" == false ]]; then
  "$SEMAN2_ROOT/scripts/verify_local_dependencies.sh"
fi

