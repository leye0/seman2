"""Explicit download of pinned role tables. No runtime network calls."""
import argparse
from pathlib import Path
from urllib.request import urlopen
from seman_parser.role_resources import manifest,verify

def main():
    p=argparse.ArgumentParser();p.add_argument("directory",type=Path);args=p.parse_args()
    args.directory.mkdir(parents=True,exist_ok=True)
    for rec in manifest():
        dst=args.directory/rec["name"]
        if dst.exists():
            verify(dst.read_bytes(),rec);continue
        with urlopen(rec["url"],timeout=60) as f:raw=f.read(rec["bytes"]+1)
        verify(raw,rec)
        tmp=dst.with_suffix(dst.suffix+".tmp")
        tmp.write_bytes(raw);tmp.replace(dst)
    print("ROLE_RESOURCES_BYTES",sum(r["bytes"] for r in manifest()))
if __name__=="__main__":main()
