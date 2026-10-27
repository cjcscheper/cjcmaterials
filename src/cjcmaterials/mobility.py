"""Carrier mobility as a function of carrier density.

A free-carrier (Drude) description needs a scattering time, and the measured
quantity that sets it is the mobility, which falls with carrier (or doping)
density because the carriers scatter off more ionised impurities. A material
file can therefore give the mobility either as one number or as a mobility
model, named in :data:`MOBILITY_MODELS` and evaluated at the carrier density
given at use time (see ``cjcmaterials.optics``).

Adding a mobility model = one function here + one line in ``MOBILITY_MODELS``.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def caughey_thomas_mobility(
    carrier_density: float | npt.ArrayLike,
    *,
    mu_min: float,
    mu_max: float,
    n_ref: float,
    alpha: float,
) -> np.ndarray:
    """Caughey–Thomas mobility: an empirical step from ``mu_max`` to ``mu_min``.

    ``mu(N) = mu_min + (mu_max - mu_min) / (1 + (N / n_ref)**alpha)``

    Why this form: at low density the mobility is limited by phonon scattering
    alone (``mu_max``); at high density ionised-impurity scattering dominates
    and the mobility saturates at ``mu_min``. The step is centred on ``n_ref``,
    where ``mu = (mu_min + mu_max) / 2``, and ``alpha`` sets how sharp it is.
    The form was fitted to silicon by Caughey & Thomas (Proc. IEEE 55, 2192,
    1967) and to III–V compounds by Sotoodeh et al. (J. Appl. Phys. 87, 2890,
    2000). It is written here in the density ``N`` of the carriers; the
    original papers use the doping density, which is the same for fully
    ionised dopants (see THEORY.md).

    Parameters
    ----------
    carrier_density : float or array
        Carrier density N [m^-3] (or [m^-2] for a sheet), >= 0.
    mu_min, mu_max : float
        Mobility at high and at low density [m^2/(V s)], 0 <= mu_min <= mu_max.
    n_ref : float
        Density of the midpoint of the step [same unit as ``carrier_density``], > 0.
    alpha : float
        Steepness exponent, > 0.

    Returns
    -------
    np.ndarray
        Mobility [m^2/(V s)], same shape as ``carrier_density``.

    Raises
    ------
    ValueError
        For a negative density or parameters outside the ranges above.
    """
    # Validate first, so a typo in a material file gives a clear message instead of NaNs.
    if not 0.0 <= mu_min <= mu_max:
        raise ValueError(f"Caughey-Thomas needs 0 <= mu_min <= mu_max, got mu_min={mu_min}, mu_max={mu_max}.")
    if n_ref <= 0.0 or alpha <= 0.0:
        raise ValueError(f"Caughey-Thomas needs n_ref > 0 and alpha > 0, got n_ref={n_ref}, alpha={alpha}.")
    density = np.asarray(carrier_density, dtype=np.float64)
    if np.any(density < 0.0):
        raise ValueError("carrier_density must be >= 0.")

    # The empirical step itself.
    return mu_min + (mu_max - mu_min) / (1.0 + (density / n_ref) ** alpha)


# Mobility models by name, as a material file names them (``mobility: {model: caughey_thomas, ...}``).
MOBILITY_MODELS = {
    "caughey_thomas": caughey_thomas_mobility,
}
