"""Plot observed Gutenberg canonical-vector replay measurements, no simulation."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def render(path, out):
    report=json.loads(Path(path).read_text())
    points=report["curve"]
    if not points:
        raise ValueError("No observed data")
    out=Path(out)
    out.parent.mkdir(parents=True,exist_ok=True)
    x=[p["sentences"] for p in points]

    fig,ax=plt.subplots(figsize=(10,6))
    ax.axhline(0,color="gray",linewidth=1)
    for key,label in (
        ("memo_savings_pct","Exact same-text replay (positive control)"),
        ("C_savings_pct","C + vector grammar, parsing alone"),
        ("C_amortized_savings_pct","C + vector grammar, learning included"),
    ):
        ax.plot(x,[p[key] for p in points],marker="o",markersize=3,label=label)
    ax.set_title("Seman2 — savings on repeated Gutenberg parsing")
    ax.set_xlabel("Sentences replayed")
    ax.set_ylabel("Measured reduction in total wall time (%)")
    ax.legend()
    ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(str(out)+"_savings.png",dpi=180)
    plt.close(fig)

    fig,ax=plt.subplots(figsize=(10,6))
    for key,label in (
        ("canonical_cumulative_s","Vector grammar without cache"),
        ("memo_cumulative_s","Exact stored ParseResult"),
        ("C_cumulative_s","C-patterns + vector grammar"),
    ):
        ax.plot(x,[p[key] for p in points],marker="o",markersize=3,label=label)
    ax.set_title("Seman2 — cumulative time on identical novel passages")
    ax.set_xlabel("Sentences replayed")
    ax.set_ylabel("Observed cumulative wall time (s)")
    ax.legend()
    ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(str(out)+"_cumulative.png",dpi=180)
    plt.close(fig)

    d=report["second_pass"]["timing"]
    keys=("p50_ms","p75_ms","p90_ms")
    modes=("canonical","exact_cache","C_vector")
    fig,ax=plt.subplots(figsize=(9,5.6))
    for j,name in enumerate(modes):
        ax.bar([i + (j-1)*.23 for i in range(3)],
               [d[name][key] for key in keys],
               width=.23,label=name)
    ax.set_xticks(range(3),("Median (p50)","p75","p90"))
    ax.set_ylabel("Milliseconds per sentence (lexing included)")
    ax.set_title("Seman2 — observed tail latencies")
    ax.legend()
    ax.grid(axis="y",alpha=.2)
    fig.tight_layout()
    fig.savefig(str(out)+"_latencies.png",dpi=180)
    plt.close(fig)

    counts=report["second_pass"]["counts"]
    total=report["corpus"]["sentences"]
    fig,ax=plt.subplots(figsize=(9,5))
    values=[
        counts.get("exact_object_recovered",0)/total*100,
        counts.get("C_complete_parity",0)/total*100,
        counts.get("C_tree_equal",0)/total*100,
        counts.get("C_forest_parity",0)/total*100,
    ]
    labels=("Exact cache recall","C completion parity","C best-tree parity",
            "C forest-count parity")
    bars=ax.barh(labels,values)
    for bar,val in zip(bars,values):
        ax.text(min(val+1,101),bar.get_y()+bar.get_height()/2,
                f"{val:.1f}%",va="center")
    ax.set_xlim(0,112)
    ax.set_xlabel("Fraction of sentences (%)")
    ax.set_title("Seman2 — reconstruction fidelity, not gold accuracy")
    fig.tight_layout()
    fig.savefig(str(out)+"_parity.png",dpi=180)
    plt.close(fig)

    with open(str(out)+"_curve.csv","w",newline="",encoding="utf8") as f:
        writer=csv.DictWriter(f,fieldnames=list(points[0]))
        writer.writeheader()
        writer.writerows(points)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--report",required=True)
    p.add_argument("--prefix",required=True)
    args=p.parse_args()
    render(args.report,args.prefix)


if __name__=="__main__":
    main()
