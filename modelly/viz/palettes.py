"""Colour-blind-safe palettes, as hex strings, for every backend.

``OKABE_ITO`` is the eight-colour palette of Okabe and Ito, designed to stay distinct with
the common forms of colour-blindness. ``TOL_BRIGHT``, ``TOL_VIBRANT`` and ``TOL_MUTED`` are
Paul Tol's qualitative schemes (https://personal.sron.nl/~pault/), checked the same way.
``PALETTES`` maps their names, as ``modelly.viz.styles.paper(palette=...)`` takes them.
"""

OKABE_ITO = (
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#009E73",  # bluish green
    "#F0E442",  # yellow
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#CC79A7",  # reddish purple
    "#000000",  # black
)
TOL_BRIGHT = (
    "#4477AA",
    "#EE6677",
    "#228833",
    "#CCBB44",
    "#66CCEE",
    "#AA3377",
    "#BBBBBB",
)
TOL_VIBRANT = (
    "#0077BB",
    "#33BBEE",
    "#009988",
    "#EE7733",
    "#CC3311",
    "#EE3377",
    "#BBBBBB",
)
TOL_MUTED = (
    "#332288",
    "#88CCEE",
    "#44AA99",
    "#117733",
    "#999933",
    "#DDCC77",
    "#CC6677",
    "#882255",
    "#AA4499",
)

PALETTES = {
    "okabe_ito": OKABE_ITO,
    "tol_bright": TOL_BRIGHT,
    "tol_vibrant": TOL_VIBRANT,
    "tol_muted": TOL_MUTED,
}

__all__ = ["OKABE_ITO", "PALETTES", "TOL_BRIGHT", "TOL_MUTED", "TOL_VIBRANT"]
