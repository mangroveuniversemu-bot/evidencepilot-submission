"""Submitted CHSH analysis (synthetic example)."""

import csv
import sys


def main(path):
    totals = {}
    for row in csv.DictReader(open(path)):
        key = (row["setting_a"], row["setting_b"])
        cell = totals.setdefault(key, [0, 0, 0, 0])
        for i, name in enumerate(("n_pp", "n_pm", "n_mp", "n_mm")):
            cell[i] += int(row[name])
    e = {}
    for key, (pp, pm, mp, mm) in totals.items():
        n = pp + pm + mp + mm
        e[key] = (pp + mm - pm - mp) / n
    s = e[("a", "b")] - e[("a", "bp")] + e[("ap", "b")] + e[("ap", "bp")]
    print(f"S = {s:.4f}")


if __name__ == "__main__":
    main(sys.argv[1])
