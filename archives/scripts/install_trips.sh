#!/usr/bin/env bash
set -euo pipefail

SEMAN2_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRIPS_BASE="$SEMAN2_ROOT/.local/src/cogent-v3"
cache="$SEMAN2_ROOT/.local/cache"
wordnet_root="$SEMAN2_ROOT/.local/share/wordnet"
sbcl_root="$SEMAN2_ROOT/.local/opt/sbcl"
perl_root="$SEMAN2_ROOT/.local/opt/perl"
sqlite_root="$SEMAN2_ROOT/.local/opt/sqlite"
xslt_root="$SEMAN2_ROOT/.local/opt/xslt"
commit="7f80f44977f533138737c1858fd1a1e0f942acfe"
runtime_patch="$SEMAN2_ROOT/patches/cogent/seman2-runtime.patch"
host_javac="$(command -v javac)"

for command in apt-get curl dpkg-deb git make gcc g++ java perl pkg-config; do
  command -v "$command" >/dev/null || {
    printf 'Dépendance de build manquante : %s\n' "$command" >&2
    exit 1
  }
done
mkdir -p "$cache/debs" "$wordnet_root" "$SEMAN2_ROOT/.local/opt"

download_deb() {
  local package="$1" destination="$2" pattern="$3"
  if [[ -d "$destination" ]]; then
    return
  fi
  (cd "$cache/debs" && apt-get download "$package")
  mkdir -p "$destination"
  local archive
  archive="$(find "$cache/debs" -maxdepth 1 -type f -name "$pattern" -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)"
  dpkg-deb -x "$archive" "$destination"
}

download_deb sbcl "$sbcl_root" 'sbcl_*.deb'
download_deb libdbi-perl "$perl_root" 'libdbi-perl_*.deb'
(cd "$cache/debs" && apt-get download libdbd-sqlite3-perl)
dbd_archive="$(find "$cache/debs" -maxdepth 1 -type f -name 'libdbd-sqlite3-perl_*.deb' -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)"
dpkg-deb -x "$dbd_archive" "$perl_root"
download_deb sqlite3 "$sqlite_root" 'sqlite3_*.deb'
download_deb xsltproc "$xslt_root" 'xsltproc_*.deb'

wordnet_archive="$cache/WordNet-3.0.tar.bz2"
glosstag_archive="$cache/WordNet-3.0-glosstag.tar.bz2"
if [[ ! -f "$wordnet_archive" ]]; then
  curl -fL https://wordnetcode.princeton.edu/3.0/WordNet-3.0.tar.bz2 -o "$wordnet_archive"
fi
if [[ ! -f "$glosstag_archive" ]]; then
  curl -fL https://wordnetcode.princeton.edu/glosstag-files/WordNet-3.0-glosstag.tar.bz2 -o "$glosstag_archive"
fi
if [[ ! -d "$wordnet_root/WordNet-3.0/glosstag" ]]; then
  tar -xjf "$wordnet_archive" -C "$wordnet_root"
  tar -xjf "$glosstag_archive" -C "$wordnet_root"
fi

if [[ ! -d "$TRIPS_BASE/.git" ]]; then
  git clone https://github.com/wdebeaum/cogent.git "$TRIPS_BASE"
fi
git -C "$TRIPS_BASE" checkout --detach "$commit"
if git -C "$TRIPS_BASE" apply --reverse --check "$runtime_patch" 2>/dev/null; then
  printf 'Patch runtime Seman2 déjà appliqué à TRIPS/Cogent.\n'
else
  git -C "$TRIPS_BASE" apply --check "$runtime_patch"
  git -C "$TRIPS_BASE" apply "$runtime_patch"
fi

export TRIPS_BASE TRIPS_SYSNAME=cogent
export SBCL_HOME="$sbcl_root/usr/lib/sbcl"
export PERL5LIB="$perl_root/usr/lib/x86_64-linux-gnu/perl5/5.38${PERL5LIB:+:$PERL5LIB}"
export PATH="$sbcl_root/usr/bin:$sqlite_root/usr/bin:$xslt_root/usr/bin:$PATH"

(
  cd "$TRIPS_BASE/src"
  ./configure \
    --with-lisp="$sbcl_root/usr/bin/sbcl" \
    --with-runtime-lisp="$sbcl_root/usr/bin/sbcl" \
    --with-fasl=fasl \
    --with-wordnet="$wordnet_root/WordNet-3.0/dict/" \
    --without-corenlp \
    --without-ruby
  # The host compiler may be newer than the repository-local Java runtime.
  # A command-line Make variable propagates through recursive builds without
  # replacing package-specific JFLAGS such as CollaborativeStateManager's
  # classpath.
  make -j"$(getconf _NPROCESSORS_ONLN 2>/dev/null || printf 2)" \
    JAVAC="$host_javac --release 17" \
    NONTRIPS_JAVAC="$host_javac --release 17"
  make install
)

make -C "$TRIPS_BASE/src/TextTagger" terms
install -m 755 "$TRIPS_BASE/src/TextTagger/terms" "$TRIPS_BASE/bin/terms"
make -C "$TRIPS_BASE/src/TextTagger/terms2"
install -m 755 "$TRIPS_BASE/src/TextTagger/terms2/terms2" "$TRIPS_BASE/bin/terms2"

if [[ ! -s "$TRIPS_BASE/etc/WordNetSQL/wn.db" ]]; then
  make -C "$TRIPS_BASE/src/WordNetSQL" distclean
  make -C "$TRIPS_BASE/src/WordNetSQL" wn.db-no-really
  make -C "$TRIPS_BASE/src/WordNetSQL" install-wn
fi
make -C "$TRIPS_BASE/src/TextTagger" wn-multiwords.tsv
install -m 644 "$TRIPS_BASE/src/TextTagger/wn-multiwords.tsv" \
  "$TRIPS_BASE/etc/TextTagger/wn-multiwords.tsv"

printf '%s\n' "$commit" >"$TRIPS_BASE/.seman2-installed-commit"
printf 'TRIPS/Cogent local installé dans %s\n' "$TRIPS_BASE"
