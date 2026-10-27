"""Valid ranges made visible: n and kappa of silicon, from two descriptions joined at 4.5 THz.

Silicon has two descriptions: Dai et al. (2004), a Drude–Lorentz model valid 0.1-4.5 THz, and
Franta et al. (2017), a table valid 0.97-9670 THz. Between 0.97 and 4.5 THz both apply, and the
package does not choose between them: this script does, with description=, taking Dai's model up
to the end of its range and Franta's table above. Each part is drawn on its own coloured background,
with the border at 4.5 THz as a grey dashed line and the authors written on either side. Evaluating
the table below its range gives a warning, which the script prints.
"""

import warnings
from pathlib import Path

import numpy as np
from cjcplot import plot_1d, style_colors

from cjcmaterials import get_material, refractive_index

output_stem = Path(__file__).with_suffix("")
material_name = "Si"
material = get_material(material_name)
freq_min_thz, freq_max_thz = 0.1, 1e4

# Where the script switches from Dai's model to Franta's table (the end of Dai's valid range), and where
# Franta's range ends, so the curve stops there instead of extrapolating.
descriptions = {item.label: item for item in material.descriptions}
border_thz = descriptions["thz"].valid_range_thz[0][1]
freq_thz = np.geomspace(freq_min_thz, descriptions["optical"].valid_range_thz[0][1], 2000)
below = freq_thz <= border_thz

# Each part from its own description, joined into one curve.
index = np.empty(freq_thz.shape, dtype=complex)
index[below] = refractive_index(material, 2 * np.pi * freq_thz[below] * 1e12, description="thz")
index[~below] = refractive_index(material, 2 * np.pi * freq_thz[~below] * 1e12, description="optical")

# Using Franta's table below its range (0.1-0.97 THz) on purpose, to show the warning.
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    refractive_index(material, 2 * np.pi * freq_thz * 1e12, description="optical")
for warning in caught:
    print(f"{warning.category.__name__}: {warning.message}")

# One figure per quantity: the curve and the border by plot_1d, then each part's background and authors.
colors = style_colors()
parts = [(freq_min_thz, border_thz, "Dai et al.", "right"), (border_thz, freq_max_thz, "Franta et al.", "left")]
for quantity, values, ylabel, logy, ylim in (
    ("n", index.real, "Real refractive index n", False, (0.0, 8.0)),
    ("kappa", index.imag, r"Imaginary refractive index $\kappa$", True, (1e-12, 1e3)),
):
    fig, ax = plot_1d(
        freq_thz, values,
        colors=[colors[0]],
        xlabel="Frequency [THz]", ylabel=ylabel,
        xlim=(freq_min_thz, freq_max_thz), ylim=ylim,
        logx=True, logy=logy,
        vlines_pos=[border_thz],
        legend_show=False,
        fig_aspect_ratio=(0.5, 0.5),
        fig_show=False,
    )
    for shade, (low, high, authors, alignment) in zip(colors[1:], parts):
        ax.axvspan(low, high, color=shade, alpha=0.2, linewidth=0, zorder=0)
        # Text just beside the border, both at the same height (x in data, y in axes coordinates).
        offset = 0.8 if alignment == "right" else 1.25
        ax.text(border_thz * offset, 0.92, authors, ha=alignment, va="top", transform=ax.get_xaxis_transform())
    fig.savefig(f"{output_stem}_{material_name}_{quantity}.png")
