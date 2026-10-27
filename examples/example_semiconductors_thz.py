"""Undoped InP, GaAs and Si from the library in the THz range: n solid, kappa dashed.

Each material's THz description is used inside its own valid range only, so nothing here
extrapolates: InP (0.06-21 THz) and GaAs (0.1-20 THz) show their TO-phonon resonances near 9.1 and
8.1 THz, where n swings and kappa peaks; silicon's THz description ends at 4.5 THz.
"""

from pathlib import Path

import numpy as np
from cjcplot import plot_1d, style_colors

from cjcmaterials import get_material, refractive_index

output_stem = Path(__file__).with_suffix("")
freq_thz = np.linspace(0.1, 10.0, 2000)

# Each material over the part of 0.1-10 THz its 'thz' description covers.
x_traces, n_traces, kappa_traces, names = [], [], [], ["InP", "GaAs", "Si"]
for name in names:
    material = get_material(name)
    description = next(item for item in material.descriptions if item.label == "thz")
    low, high = description.valid_range_thz[0]
    inside = freq_thz[(freq_thz >= low) & (freq_thz <= high)]
    index = refractive_index(material, 2 * np.pi * inside * 1e12, description="thz")
    x_traces.append(inside)
    n_traces.append(index.real)
    kappa_traces.append(index.imag)
    print(f"{name}: n = {index.real[0]:.3f} at {inside[0]:.1f} THz, valid {low:g}-{high:g} THz")

# n and kappa in one figure on a log axis, one colour (and legend entry) per material.
colors = style_colors()[:3]
plot_1d(
    x_traces + x_traces, n_traces + kappa_traces,
    colors=colors + colors,
    line_styles=["-"] * 3 + ["--"] * 3,
    legend_labels=names + [None] * 3,
    xlabel="Frequency [THz]", ylabel=r"n (solid), $\kappa$ (dashed)",
    xlim=(0.0, 10.0), ylim=(1e-6, 100.0),
    logy=True,
    legend_loc="lower right",
    fig_aspect_ratio=(0.5, 0.5),
    save_path=f"{output_stem}.png",
    fig_show=False,
)
