"""Caughey–Thomas mobility of silicon versus carrier density, electrons and holes.

The parameters come from the silicon file of the library (Caughey & Thomas 1967). The mobility
falls from its phonon-limited value at low density to the impurity-limited one at high density,
with the midpoint at n_ref; electrons are about three times as mobile as holes.
"""

from pathlib import Path

import numpy as np
from cjcplot import plot_1d, style_colors

from cjcmaterials import caughey_thomas_mobility, get_material

output_stem = Path(__file__).with_suffix("")
carrier_density_cm3 = np.geomspace(1e12, 1e22, 400)

# The mobility model of each carrier type, as the library file gives it (SI units).
thz = next(item for item in get_material("Si").descriptions if item.label == "thz")
mobility_cm2_per_vs = []
for block in ("electrons", "holes"):
    parameters = {key: value for key, value in thz.parameters[block]["mobility"].items() if key != "model"}
    mobility_cm2_per_vs.append(caughey_thomas_mobility(carrier_density_cm3 * 1e6, **parameters) * 1e4)
    print(f"{block}: mu_max = {parameters['mu_max'] * 1e4:.0f} cm^2/Vs, mu_min = {parameters['mu_min'] * 1e4:.1f} "
          f"cm^2/Vs, n_ref = {parameters['n_ref'] * 1e-6:.1e} cm^-3")

# Log-log, as the step spans many decades of density; electrons red, holes blue.
plot_1d(
    [carrier_density_cm3] * 2, mobility_cm2_per_vs,
    colors=[style_colors()[2], style_colors()[0]],
    legend_labels=["electrons", "holes"],
    xlabel=r"Carrier density [cm$^{-3}$]", ylabel=r"Mobility [cm$^2$/(V s)]",
    xlim=(1e12, 1e22), ylim=(1e1, 1e4),
    logx=True, logy=True,
    legend_loc="lower left",
    fig_aspect_ratio=(0.5, 0.5),
    save_path=f"{output_stem}.png",
    fig_show=False,
)
