"""Run: python -m research.verbnet_lr VERBNET_XML_DIR --wordnet-sense-index PATH --output FILE"""
import argparse
import json
from .compiler import compile_directory, write_index


def main():
    parser = argparse.ArgumentParser(description="Compile a VerbNet 3.4 lexical-hint index")
    parser.add_argument("xml_dir")
    parser.add_argument("--wordnet-sense-index", help="WordNet dict/index.sense (recommended)")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    frames, stats = compile_directory(args.xml_dir, args.wordnet_sense_index)
    write_index(args.output, frames, stats)
    print(json.dumps(stats, sort_keys=True))


if __name__ == "__main__":
    main()
