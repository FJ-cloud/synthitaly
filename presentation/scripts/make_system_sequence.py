#!/usr/bin/env python3
"""Two black-and-white sequence diagrams for the 'Model Logic' slide:
  A) s13_sequence_bw_simple  — the one-day ItalyModel.step() (as-is, monochrome, cleaner)
  B) s13_sequence_bw_full    — the whole system: construction -> daily loop -> outputs

Run:  uv run python presentation/make_system_sequence.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

OUT = Path(__file__).resolve().parent.parent / "slide_assets"
OUT.mkdir(parents=True, exist_ok=True)

BLACK, GREY, LINE, NOTE, TAB = "#111111", "#8a8a8a", "#bdbdbd", "#f1f1f1", "#e6e6e6"
plt.rcParams.update({"font.family": "sans-serif",
                     "font.sans-serif": ["DejaVu Sans", "Segoe UI", "Arial"],
                     "figure.facecolor": "white", "savefig.facecolor": "white"})


class Seq:
    def __init__(self, w, h, title, sub):
        self.fig, self.ax = plt.subplots(figsize=(w, h))
        self.ax.set_xlim(0, 100); self.ax.set_ylim(0, 100); self.ax.axis("off")
        self.ax.text(0, 99, title, ha="left", va="top", fontsize=18, weight="bold", color=BLACK)
        if sub:
            self.ax.text(0, 93.2, sub, ha="left", va="top", fontsize=10.5, color=GREY, style="italic")
        self.lanes = {}

    def lifelines(self, items, top, bottom, hw=9.2):
        for name, x in items:
            self.lanes[name] = x
            self.ax.add_patch(FancyBboxPatch((x - hw, top), 2 * hw, 5.0,
                              boxstyle="round,pad=0.2,rounding_size=1.4",
                              facecolor="white", edgecolor=BLACK, linewidth=1.6, mutation_aspect=0.5))
            self.ax.text(x, top + 2.5, name, ha="center", va="center", fontsize=10.2,
                         weight="bold", color=BLACK)
            self.ax.plot([x, x], [bottom, top], color=LINE, lw=1.2, ls=(0, (2, 3)), zorder=0)

    def activation(self, name, y0, y1):
        x = self.lanes[name]
        self.ax.add_patch(Rectangle((x - 1.1, y1), 2.2, y0 - y1, facecolor="white",
                          edgecolor=BLACK, linewidth=1.1, zorder=3))

    def msg(self, a, b, y, text, ret=False, self_lbl=None):
        x0, x1 = self.lanes[a], self.lanes[b]
        if a == b:  # self-message
            self.ax.add_patch(FancyArrowPatch((x0 + 1.1, y), (x0 + 1.1, y - 3.2),
                              connectionstyle="arc3,rad=0", arrowstyle="-", color=BLACK, lw=1.6))
            self.ax.add_patch(FancyArrowPatch((x0 + 7, y), (x0 + 7, y - 3.2),
                              arrowstyle="-", color=BLACK, lw=1.6))
            self.ax.plot([x0 + 1.1, x0 + 7], [y, y], color=BLACK, lw=1.6)
            self.ax.add_patch(FancyArrowPatch((x0 + 7, y - 3.2), (x0 + 1.6, y - 3.2),
                              arrowstyle="-|>", mutation_scale=13, color=BLACK, lw=1.6))
            self.ax.text(x0 + 9, y - 1.6, text, ha="left", va="center", fontsize=9.2, color=BLACK)
            return
        style = "-|>" if not ret else "-|>"
        ls = "-" if not ret else (0, (5, 3))
        self.ax.add_patch(FancyArrowPatch((x0, y), (x1, y), arrowstyle=style, mutation_scale=14,
                          color=BLACK, lw=1.7, linestyle=ls, shrinkA=1, shrinkB=1, zorder=4))
        self.ax.text((x0 + x1) / 2, y + 1.7, text, ha="center", va="bottom", fontsize=9.2,
                     color=BLACK)

    def note(self, x0, x1, y, h, text, fs=9.0, weight="normal"):
        self.ax.add_patch(FancyBboxPatch((x0, y), x1 - x0, h, boxstyle="round,pad=0.2,rounding_size=1.0",
                          facecolor=NOTE, edgecolor=GREY, linewidth=1.2, mutation_aspect=0.5, zorder=2))
        self.ax.text((x0 + x1) / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
                     color=BLACK, linespacing=1.4, weight=weight, zorder=3)

    def frame(self, x0, y0, x1, y1, label):
        self.ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, edgecolor="#444444",
                          linewidth=1.4, zorder=1))
        self.ax.add_patch(Rectangle((x0, y1 - 4.2), 26, 4.2, facecolor=TAB, edgecolor="#444444",
                          linewidth=1.2, zorder=2))
        self.ax.text(x0 + 1.5, y1 - 2.1, label, ha="left", va="center", fontsize=9.2,
                     weight="bold", color=BLACK, zorder=3)

    def save(self, name):
        self.fig.tight_layout()
        for ext in ("png", "svg"):
            self.fig.savefig(OUT / f"{name}.{ext}", dpi=200, bbox_inches="tight")
        plt.close(self.fig)
        print(f"  wrote {name}.png / .svg")


# ---------------------------------------------------------------- A) simple
def build_simple():
    s = Seq(12.5, 7.4, "One simulated day — ItalyModel.step()",
            "synchronous across days, randomised within a day (income paid before consumers act)")
    top, bot = 83, 8
    s.lifelines([("ItalyModel.step()", 13), ("IncomeSource", 39), ("Consumer", 65),
                 ("DataCollector", 90)], top, bot, hw=10)
    s.msg("ItalyModel.step()", "IncomeSource", 77, "do(\"step\")")
    s.activation("IncomeSource", 77, 69)
    s.msg("IncomeSource", "Consumer", 70, "credit income on the 27th  (+Dec tredicesima)")
    s.msg("ItalyModel.step()", "Consumer", 60, "shuffle_do(\"step\")")
    s.note(49, 83, 42, 13,
           "per Consumer, in order:\n_month_close (1st) → _settle_overdue_bills →\n"
           "_pay_due_bills → _service_debt (25th) → _maybe_buy_from_merchant")
    s.msg("Consumer", "ItalyModel.step()", 36, "append to model.transactions", ret=True)
    s.msg("ItalyModel.step()", "DataCollector", 27, "collect(self)  → KPIs + grouped balances")
    s.msg("ItalyModel.step()", "ItalyModel.step()", 18, "today += 1 day")
    s.save("s13_sequence_bw_simple")


# ---------------------------------------------------------------- B) full system
def build_full():
    s = Seq(14.5, 9.2, "",
            "construction once · a daily loop where every transaction is generated")
    top, bot = 85, 10
    s.lifelines([("ItalyModel", 9), ("IncomeSource", 30), ("Consumer", 51),
                 ("Merchant", 72), ("DataCollector", 91)], top, bot, hw=8.3)
    # construction (above the loop)
    s.note(1.5, 98.5, 77, 6.5,
           "__init__ (seeded):  build Merchants (category × area) · IncomeSources (per area) · Consumers;   "
           "assign income bands, debt (participation → subtype → opening principal), savings/pension flags",
           fs=8.6)
    # loop frame — tab spans 70.8..75; first message sits well below it, inside the frame
    s.frame(3.5, 13, 98.5, 75, "loop  [ for day in range(N_days) ]")
    s.msg("ItalyModel", "IncomeSource", 66, "do(\"step\")")
    s.activation("IncomeSource", 66, 59.5)
    s.msg("IncomeSource", "Consumer", 60.5, "salary on the 27th  (+Dec tredicesima)")
    s.msg("ItalyModel", "Consumer", 53, "shuffle_do(\"step\")")
    s.activation("Consumer", 53, 26)
    # per-consumer note placed to the RIGHT of the Consumer lifeline so the activation bar never crosses it
    s.note(57, 98.5, 36.5, 13,
           "per Consumer, in order:\n"
           "_month_close (1st) → sweep surplus to savings / pension\n"
           "_settle_overdue (+11% late fee) · _pay_due_bills\n"
           "_service_debt (25th: climber repay→exit / chronic\n"
           "interest-only / subsister borrow)\n"
           "_maybe_buy_from_merchant (P ∝ daily intensity) →\n"
           "affordability gate → pay / defer / borrow",
           fs=8.2)
    s.msg("Consumer", "Merchant", 32, "purchase / bill / fee  (+€30 if it crosses €0)")
    s.msg("Consumer", "ItalyModel", 27.5, "append to transactions  (paired debit/credit)", ret=True)
    s.msg("ItalyModel", "DataCollector", 23, "collect(self)  → KPIs + grouped balances")
    s.msg("ItalyModel", "ItalyModel", 19, "today += 1 day")
    s.save("s13_sequence_bw_full")


def main():
    print("Building B&W sequence diagrams:")
    build_simple()
    build_full()
    print(f"Done → {OUT}")


if __name__ == "__main__":
    main()
