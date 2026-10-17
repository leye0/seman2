"""Plots from observed (not extrapolated) two-pass Gutenberg benchmark JSON."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def render(report_file: Path, output_prefix: Path):
    payload=json.loads(report_file.read_text())
    points=payload["curve"]
    if not points:
        raise ValueError("No measured checkpoints")
    output_prefix.parent.mkdir(parents=True,exist_ok=True)
    x=[p["sentences"] for p in points]
    a=[p["pass2_time_saved_pct"] for p in points]
    b=[p["two_pass_time_saved_pct"] for p in points]
    c=[p["hit_rate_pct"] for p in points]
    d=[p["recall_of_stored_pct"] for p in points]
    fig,axis=plt.subplots(figsize=(10.5,6))
    axis.axhline(0,color="gray",linewidth=1)
    axis.plot(x,a,label="Économie nette au 2e passage",linewidth=2.4)
    axis.plot(x,b,label="Économie nette des 2 passages (apprentissage inclus)",linewidth=2.1)
    axis.set_xlabel("Phrases rejouées (même corpus)")
    axis.set_ylabel("Économie de temps mesurée (%)")
    axis.legend(loc="best")
    axis.grid(alpha=.2)
    fig.suptitle("Seman2 : l'apprentissage amortit-il son coût ?",fontsize=15)
    fig.text(.5,.015,"Valeurs négatives = surcoût. Temps de segmentation inclus dans les deux options.",
             fontsize=9,ha="center")
    fig.tight_layout(rect=(0,.035,1,.96))
    fig.savefig(str(output_prefix)+"_economie_pct.png",dpi=170)
    plt.close(fig)

    fig,axis=plt.subplots(figsize=(10.5,6))
    axis.plot(x,c,linewidth=2.4,label="Reconnaissance sur toutes les phrases")
    axis.plot(x,d,linewidth=2.2,label="Rappel parmi les arbres mémorisés")
    axis.set_xlabel("Phrases rejouées")
    axis.set_ylabel("Reconnaissance / rappel (%)")
    axis.set_ylim(0,105)
    axis.grid(alpha=.2)
    axis.legend()
    fig.suptitle("Seman2 : rejouer exactement le corpus appris",fontsize=15)
    fig.text(.5,.015,"Une phrase non analysée au premier passage ne peut pas avoir d'arbre mémorisé.",
             fontsize=9,ha="center")
    fig.tight_layout(rect=(0,.035,1,.96))
    fig.savefig(str(output_prefix)+"_reconnaissance.png",dpi=170)
    plt.close(fig)

    stage=payload["second_pass"]
    keys=("p50_ms","p75_ms","p90_ms")
    fig,axis=plt.subplots(figsize=(8.4,5.4))
    positions=range(len(keys))
    base=[stage["baseline_latency"][key] for key in keys]
    hybrid=[stage["hybrid_latency"][key] for key in keys]
    axis.bar([x-.18 for x in positions],base,width=.36,label="Parseur de référence")
    axis.bar([x+.18 for x in positions],hybrid,width=.36,label="Mémoire + repli")
    axis.set_xticks(list(positions),["Médiane (p50)","p75","p90"])
    axis.set_ylabel("Temps par phrase (ms), segmentation comprise")
    axis.set_title("Distribution du temps au second passage")
    axis.legend()
    axis.grid(axis="y",alpha=.2)
    fig.tight_layout()
    fig.savefig(str(output_prefix)+"_percentiles.png",dpi=170)
    plt.close(fig)

    with open(str(output_prefix)+"_checkpoints.csv","w",newline="",encoding="utf8") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(points[0]))
        writer.writeheader()
        writer.writerows(points)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--report",type=Path,required=True)
    p.add_argument("--out-prefix",type=Path,required=True)
    a=p.parse_args()
    render(a.report,a.out_prefix)


if __name__=="__main__":
    main()
