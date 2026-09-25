"""
Loads the catalog of real black holes (measured, sourced masses)
from data/black_holes.json and lets you add one to the running
simulation, with its real mass.

Sources: LIGO/Virgo (GWTC), Event Horizon Telescope, direct observations.
See data/black_holes.json for details + links.

Usage: paste into the Editor tab then Ctrl+Enter (or "Load
script..."), requires 01_live_viewer.py to already be running (sim /
app variables active). Then in the console:

    list_black_holes()
    add_black_hole("Cygnus X-1", x=15, y=0)
"""
import json

with open(BLACK_HOLES_PATH, "r", encoding="utf-8") as f:
    CATALOG = json.load(f)["black_holes"]


def list_black_holes():
    for bh in CATALOG:
        print(f"{bh['name']:35s} {bh['mass_msun']:>15,.3f} Msun   ({bh['type']})")


def add_black_hole(name, x=0.0, y=0.0, vx=0.0, vy=0.0):
    """Add a black hole from the catalog to the simulation, at its
    real measured mass (in Msun, the simulation's mass unit).
    WARNING: supermassive masses (millions/billions of Msun) will
    completely dominate the simulated Solar System's gravity - useful
    to observe the effect, not for realistic coexistence."""
    match = next((bh for bh in CATALOG if bh["name"] == name), None)
    if match is None:
        names = ", ".join(bh["name"] for bh in CATALOG)
        print(f"Not found: {name!r}. Available choices: {names}")
        return

    m = match["mass_msun"]
    # marker size on a log scale to stay readable on screen
    size = 6 + (2 * max(0, __import__("math").log10(max(m, 1))))
    app.add_body(name=match["name"], letter="BH", color="#000000",
                 size=min(size, 40), m=m, x=x, y=y, vx=vx, vy=vy)
    print(f"Added: {match['name']} - {m:,.3f} Msun ({match['type']})")
    print(f"Source: {match.get('source', 'n/a')}")


list_black_holes()
