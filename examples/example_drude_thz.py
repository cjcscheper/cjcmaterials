"""Drude model in the THz range: n and kappa of electrons in GaAs for five carrier densities.

The model function is used directly, with the electron effective mass and Caughey–Thomas mobility
of the GaAs file, on a background eps_inf = 12.9 (the static permittivity of GaAs: the phonon at
8 THz is left out to show the free carriers alone). More carriers raise the plasma frequency:
below it kappa dominates (metallic), just above it n dips before recovering to sqrt(eps_inf).
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from cjcplot import colors_from_colormap, plot_1d

from cjcmaterials import caughey_thomas_mobility, drude_permittivity, get_material, plasma_omega

output_stem = Path(__file__).with_suffix("")
material_name = "GaAs"
eps_static = 12.9

# Shorter legend handles and gaps than the style's, so a two-column legend fits inside the axes.
COMPACT_LEGEND = {"legend.handlelength": 1.2, "legend.handletextpad": 0.4, "legend.columnspacing": 0.8}

# Electron parameters of the material file: effective mass and mobility model (SI units).
thz = next(item for item in get_material(material_name).descriptions if item.label == "thz")
electrons = thz.parameters["electrons"]
mobility_model = {key: value for key, value in electrons["mobility"].items() if key != "model"}

# Frequencies and carrier densities; K densities give a (K, M) array in one call.
freq_thz = np.geomspace(0.1, 10.0, 500)
omega = 2 * np.pi * freq_thz * 1e12
carrier_density_cm3 = np.array([1e15, 1e16, 1e17, 1e18, 1e19])
carrier_density = carrier_density_cm3 * 1e6
mobility = caughey_thomas_mobility(carrier_density, **mobility_model)
eps = drude_permittivity(omega, eps_inf=eps_static, effective_mass_ratio=electrons["effective_mass_ratio"],
                         carrier_density=carrier_density, mobility=mobility)
index = np.sqrt(eps)

# Where each density's screened plasma frequency lies, and its mobility.
for density_cm3, density, mu in zip(carrier_density_cm3, carrier_density, mobility):
    omega_p = plasma_omega(density, effective_mass_ratio=electrons["effective_mass_ratio"], eps_inf=eps_static)
    print(f"N = {density_cm3:.0e} cm^-3: mu = {mu * 1e4:.0f} cm^2/Vs, "
          f"screened plasma frequency {omega_p / (2 * np.pi) / 1e12:.2f} THz")

# One figure for n and one for kappa, log-log to show every density; colours run with the density.
# Compact legend in two columns read row by row (10^15 10^16 / 10^17 10^18 / 10^19 cm^-3): matplotlib
# fills a legend column by column, so the traces are passed in the order 15, 17, 19, 16, 18.
colors = colors_from_colormap("viridis", len(carrier_density))
exponents = np.log10(carrier_density_cm3).round().astype(int)
labels = [rf"$10^{{{exponent}}}$" for exponent in exponents[:-1]] + [rf"$10^{{{exponents[-1]}}}$ cm$^{{-3}}$"]
legend_order = [0, 2, 4, 1, 3]
for quantity, values, ylabel, ylim in (("n", index.real, "Real refractive index n", (1e-2, 1e3)),
                                       ("kappa", index.imag, r"Imaginary refractive index $\kappa$", (1e-7, 1e3))):
    with plt.rc_context(COMPACT_LEGEND):
        plot_1d(
            [freq_thz] * len(carrier_density), [values[i] for i in legend_order],
            colors=[colors[i] for i in legend_order],
            legend_labels=[labels[i] for i in legend_order],
            legend_ncols=2,
            xlabel="Frequency [THz]", ylabel=ylabel,
            xlim=(0.1, 10.0), ylim=ylim,
            logx=True, logy=True,
            legend_loc="lower left",
            fig_aspect_ratio=(0.5, 0.5),
            save_path=f"{output_stem}_{material_name}_{quantity}.png",
            fig_show=False,
        )
