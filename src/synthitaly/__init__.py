"""synthitaly — a small, beginner-readable agent-based simulation of Italian
consumer transactions, viewed from the bank's perspective.

Quick start (in a Python REPL or notebook)::

    from synthitaly import ItalyModel
    model = ItalyModel(n_consumers=200, n_days=30, seed=42)
    model.run()

    import pandas as pd
    df = pd.DataFrame(model.transactions)
    print(df.head())

For an interactive view, run from the repo root::

    uv run solara run src/synthitaly/viz.py
"""

from .model import Consumer, IncomeSource, ItalyModel, Merchant

__all__ = ["ItalyModel", "Consumer", "Merchant", "IncomeSource"]
