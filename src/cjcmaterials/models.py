"""Material models as plain functions of the angular frequency.

Every model is a function ``<model>_permittivity(omega, *, <parameters>)``
that returns the complex relative permittivity, with the time dependence
``exp(-i omega t)`` (so ``Im eps >= 0`` for absorption). The
keyword names are exactly the parameter names in the material files, so a
description in a file maps one-to-one onto a function call. The functions are
public and can be used without any material file.

:data:`MODELS` maps the model names used in material files to these
functions; ``cjcmaterials.optics`` dispatches on that name, never on a type.
Adding a model = one function + one line in ``MODELS`` (and a section in
THEORY.md).

Carrier densities: the free-carrier models accept a scalar
``carrier_density`` or a 1D array of K densities; with K densities the result
has shape ``(K,) + omega.shape``, one row per density (e.g. one per sublayer
of a photo-excited depth profile), computed in one vectorised call.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import numpy.typing as npt

from cjcmaterials._constants import (
    BOLTZMANN_CONSTANT,
    ELECTRON_MASS,
    ELEMENTARY_CHARGE,
    REDUCED_PLANCK_CONSTANT,
    VACUUM_PERMITTIVITY,
)
from cjcmaterials.tables import tabulated_permittivity

# The keys every Lorentz oscillator mapping must have.
_OSCILLATOR_KEYS = {"strength", "resonance_omega", "damping"}


def _as_omega(omega: float | npt.ArrayLike) -> np.ndarray:
    """Angular frequencies as a float array, checked: the models divide by omega."""
    omega_array = np.asarray(omega, dtype=np.float64)
    if np.any(~np.isfinite(omega_array)) or np.any(omega_array <= 0.0):
        raise ValueError("omega must be finite and > 0 [rad/s].")
    return omega_array


def _along_carrier_axis(values: float | npt.ArrayLike, omega: np.ndarray, name: str) -> np.ndarray:
    """A scalar as it is; a 1D array of K values reshaped to broadcast as ``(K,) + omega.shape``."""
    array = np.asarray(values, dtype=np.float64)
    if array.ndim > 1:
        raise ValueError(f"{name} must be a scalar or a 1D array (one value per carrier density).")
    return array.reshape(array.shape + (1,) * omega.ndim) if array.ndim == 1 else array


# --------------------------------------------------------------------------------------------------
# Constant index
# --------------------------------------------------------------------------------------------------

def constant_permittivity(omega: float | npt.ArrayLike, *, n: float, kappa: float = 0.0) -> np.ndarray:
    """Frequency-independent index: ``eps = (n + i kappa)**2`` at every omega.

    For media whose dispersion is negligible in the range of interest (air,
    a reference dielectric). ``kappa`` >= 0 is the extinction coefficient.
    """
    # Same value everywhere, in the shape of omega so it combines with other layers.
    omega_array = _as_omega(omega)
    return np.full(omega_array.shape, (n + 1j * kappa) ** 2, dtype=np.complex128)


# --------------------------------------------------------------------------------------------------
# Free carriers: Drude
# --------------------------------------------------------------------------------------------------

def scattering_time_from_mobility(mobility: float | npt.ArrayLike, *, effective_mass_ratio: float) -> np.ndarray:
    """Momentum scattering time ``tau = mu m* / e`` [s] from a mobility [m^2/(V s)].

    Why: the drift velocity in a DC field is ``v = (e tau / m*) E``, and the
    mobility is defined by ``v = mu E``. ``effective_mass_ratio`` is m*/m_e.
    """
    # The definition of the mobility, solved for tau.
    return np.asarray(mobility, dtype=np.float64) * effective_mass_ratio * ELECTRON_MASS / ELEMENTARY_CHARGE


def plasma_omega(
    carrier_density: float | npt.ArrayLike, *, effective_mass_ratio: float, eps_inf: float = 1.0
) -> np.ndarray:
    """Plasma angular frequency ``omega_p = sqrt(N e^2 / (eps0 eps_inf m*))`` [rad/s].

    With ``eps_inf = 1`` (default) this is the bare plasma frequency of the
    carriers; with the material's ``eps_inf`` it is the screened one, where
    ``Re eps`` of an undamped Drude material crosses zero.
    """
    # Restoring force of the displaced carrier gas against its inertia.
    density = np.asarray(carrier_density, dtype=np.float64)
    return np.sqrt(density * ELEMENTARY_CHARGE**2 / (VACUUM_PERMITTIVITY * eps_inf * effective_mass_ratio * ELECTRON_MASS))


def drude_conductivity(
    omega: float | npt.ArrayLike,
    *,
    carrier_density: float | npt.ArrayLike,
    effective_mass_ratio: float,
    mobility: float | npt.ArrayLike | None = None,
    scattering_time: float | npt.ArrayLike | None = None,
    smith_c: float | None = None,
) -> np.ndarray:
    """Free-carrier conductivity ``sigma(omega) = sigma_DC / (1 - i omega tau)`` [S/m].

    ``sigma_DC = N e^2 tau / m* = N e mu``. The carriers are a damped gas of
    charges: ``tau`` is their momentum relaxation time, from ``mobility`` or
    given directly as ``scattering_time`` (exactly one of the two). At
    ``omega = 1/tau`` the real part has dropped to half of ``sigma_DC`` and the
    imaginary part (the inductive response) peaks.

    ``smith_c`` (in [-1, 0]) adds the Drude–Smith backscattering factor
    ``(1 + c / (1 - i omega tau))``; ``c = 0`` is plain Drude, ``c = -1``
    suppresses the DC conductivity completely (carriers confined in grains).

    Parameters
    ----------
    omega : float or array
        Angular frequency [rad/s], > 0.
    carrier_density : float or 1D array
        Free-carrier density N [m^-3], >= 0; K densities give shape ``(K,) + omega.shape``.
    effective_mass_ratio : float
        Conductivity effective mass m*/m_e, > 0.
    mobility : float or 1D array, optional
        Carrier mobility [m^2/(V s)], > 0 (one per density, or one for all).
    scattering_time : float, optional
        Momentum scattering time tau [s], > 0.
    smith_c : float, optional
        Drude–Smith parameter c in [-1, 0]; None for plain Drude.

    Returns
    -------
    np.ndarray
        Complex conductivity [S/m].
    """
    # Exactly one way to the scattering time, so the description is never ambiguous.
    omega_array = _as_omega(omega)
    if (mobility is None) == (scattering_time is None):
        raise ValueError("Give exactly one of mobility [m^2/(V s)] or scattering_time [s].")
    if effective_mass_ratio <= 0.0:
        raise ValueError(f"effective_mass_ratio must be > 0, got {effective_mass_ratio}.")
    if smith_c is not None and not -1.0 <= smith_c <= 0.0:
        raise ValueError(f"smith_c must lie in [-1, 0], got {smith_c}.")

    # Densities and scattering times along the carrier axis, broadcasting against omega.
    density = _along_carrier_axis(carrier_density, omega_array, "carrier_density")
    if np.any(density < 0.0):
        raise ValueError("carrier_density must be >= 0.")
    if mobility is not None:
        tau = scattering_time_from_mobility(_along_carrier_axis(mobility, omega_array, "mobility"),
                                            effective_mass_ratio=effective_mass_ratio)
    else:
        tau = _along_carrier_axis(scattering_time, omega_array, "scattering_time")
    if np.any(tau <= 0.0):
        raise ValueError("The scattering time (from mobility or scattering_time) must be > 0.")

    # Drude response, with the Drude–Smith backscattering factor when asked for.
    sigma_dc = density * ELEMENTARY_CHARGE**2 * tau / (effective_mass_ratio * ELECTRON_MASS)
    denominator = 1.0 - 1j * omega_array * tau
    sigma = sigma_dc / denominator
    if smith_c is not None:
        sigma = sigma * (1.0 + smith_c / denominator)
    return np.asarray(sigma, dtype=np.complex128)


def drude_permittivity(
    omega: float | npt.ArrayLike,
    *,
    eps_inf: float,
    effective_mass_ratio: float,
    carrier_density: float | npt.ArrayLike = 0.0,
    mobility: float | npt.ArrayLike | None = None,
    scattering_time: float | npt.ArrayLike | None = None,
    smith_c: float | None = None,
) -> np.ndarray:
    """Drude permittivity ``eps = eps_inf + i sigma(omega) / (eps0 omega)``.

    ``eps_inf`` holds everything except the free carriers (bound electrons,
    and phonons far above the range of interest); the carriers add their
    current ``sigma E`` as a polarisation. Without carriers (the default
    ``carrier_density = 0``) this is ``eps_inf``. Parameters as in
    :func:`drude_conductivity`.
    """
    # The free-carrier current written as a polarisation on top of the background.
    omega_array = _as_omega(omega)
    sigma = drude_conductivity(omega_array, carrier_density=carrier_density, effective_mass_ratio=effective_mass_ratio,
                               mobility=mobility, scattering_time=scattering_time, smith_c=smith_c)
    return eps_inf + 1j * sigma / (VACUUM_PERMITTIVITY * omega_array)


# --------------------------------------------------------------------------------------------------
# Bound charges: Lorentz oscillators
# --------------------------------------------------------------------------------------------------

def lorentz_permittivity(
    omega: float | npt.ArrayLike, *, eps_inf: float, oscillators: Sequence[Mapping[str, float]]
) -> np.ndarray:
    """Sum of Lorentz oscillators on a background:
    ``eps = eps_inf + sum_k strength_k w_k^2 / (w_k^2 - omega^2 - i gamma_k omega)``.

    Each oscillator is a damped harmonic charge (a polar phonon, an impurity
    or an interband transition): below its resonance it adds ``strength`` to
    the permittivity, above it subtracts, and it absorbs (``Im eps > 0``) around
    ``w_k`` with a full width ``gamma_k``. At ``omega -> 0`` the sum gives the
    static permittivity ``eps_inf + sum strength_k``.

    Parameters
    ----------
    omega : float or array
        Angular frequency [rad/s], > 0.
    eps_inf : float
        Background permittivity above all oscillators.
    oscillators : sequence of mappings
        Each ``{"strength": dimensionless Delta eps, "resonance_omega": w_k [rad/s] > 0,
        "damping": gamma_k [rad/s] >= 0}``.

    Returns
    -------
    np.ndarray
        Complex relative permittivity, same shape as ``omega``.
    """
    # Start from the background and add one resonance at a time.
    omega_array = _as_omega(omega)
    eps = np.full(omega_array.shape, eps_inf, dtype=np.complex128)
    for index, oscillator in enumerate(oscillators):
        if set(oscillator) != _OSCILLATOR_KEYS:
            raise ValueError(f"Oscillator {index} must have exactly the keys {sorted(_OSCILLATOR_KEYS)}, "
                             f"got {sorted(oscillator)}.")
        w0, gamma = float(oscillator["resonance_omega"]), float(oscillator["damping"])
        if w0 <= 0.0 or gamma < 0.0:
            raise ValueError(f"Oscillator {index} needs resonance_omega > 0 and damping >= 0.")
        eps = eps + float(oscillator["strength"]) * w0**2 / (w0**2 - omega_array**2 - 1j * gamma * omega_array)
    return eps


def drude_lorentz_permittivity(
    omega: float | npt.ArrayLike,
    *,
    eps_inf: float,
    oscillators: Sequence[Mapping[str, float]],
    effective_mass_ratio: float,
    carrier_density: float | npt.ArrayLike = 0.0,
    mobility: float | npt.ArrayLike | None = None,
    scattering_time: float | npt.ArrayLike | None = None,
    smith_c: float | None = None,
) -> np.ndarray:
    """Lorentz oscillators plus free carriers on one background ``eps_inf``.

    ``eps = eps_inf + sum_k (Lorentz)_k + i sigma_Drude / (eps0 omega)``: the
    phonons of a doped polar semiconductor and its carriers respond
    independently, so their susceptibilities add; the background is counted
    once. Parameters as in :func:`lorentz_permittivity` and
    :func:`drude_conductivity`.
    """
    # Bound charges with the background, then the free carriers' susceptibility only (eps_inf = 0).
    omega_array = _as_omega(omega)
    bound = lorentz_permittivity(omega_array, eps_inf=eps_inf, oscillators=oscillators)
    free = drude_permittivity(omega_array, eps_inf=0.0, effective_mass_ratio=effective_mass_ratio,
                              carrier_density=carrier_density, mobility=mobility,
                              scattering_time=scattering_time, smith_c=smith_c)
    return bound + free


# --------------------------------------------------------------------------------------------------
# Graphene sheet
# --------------------------------------------------------------------------------------------------

def graphene_sheet_conductivity(
    omega: float | npt.ArrayLike,
    *,
    carrier_density: float | npt.ArrayLike,
    mobility: float | npt.ArrayLike,
    temperature: float = 300.0,
    fermi_velocity: float = 1.0e6,
) -> np.ndarray:
    """Sheet conductivity of graphene [S] (2D: not S/m), intraband plus interband.

    Dirac carriers with a linear band ``E = hbar v_F |k|`` at a sheet density
    N (electrons or holes alike, the cone is symmetric) fill states up to the
    chemical potential ``mu_c = hbar v_F sqrt(pi N)``. The conductivity is
    the local random-phase result at temperature T (Falkovsky; as in Arts et
    al., J. Appl. Phys. 124, 073105, 2018):

    - intraband (Drude-like), ``i e^2 2 k_B T / (pi hbar^2 (omega + i Gamma))
      ln(2 cosh(mu_c / (2 k_B T)))``, which for ``mu_c >> k_B T`` is the Drude
      form with the graphene Drude weight ``e^2 mu_c / (pi hbar^2)``;
    - interband, ``e^2/(4 hbar) [1/2 + arctan((hbar omega - 2 mu_c)/(2 k_B T))/pi
      - i/(2 pi) ln((hbar omega + 2 mu_c)^2 / ((hbar omega - 2 mu_c)^2 + (2 k_B T)^2))]``,
      the universal ``e^2/(4 hbar)`` absorption above the Pauli-blocking edge
      ``hbar omega = 2 mu_c``.

    The scattering rate follows from the mobility,
    ``Gamma = e v_F / (hbar mu sqrt(pi N))`` (Bøggild et al., 2D Mater. 4,
    042003, 2017, eq. 6), which makes the DC limit ``sigma = N e mu``. That
    relation diverges at the Dirac point, so N must be > 0.

    Parameters
    ----------
    omega : float or array
        Angular frequency [rad/s], > 0.
    carrier_density : float or 1D array
        Sheet carrier density N [m^-2], > 0.
    mobility : float or 1D array
        Carrier mobility [m^2/(V s)], > 0.
    temperature : float, default 300.0
        Temperature [K], > 0.
    fermi_velocity : float, default 1.0e6
        Fermi velocity v_F [m/s], > 0.

    Returns
    -------
    np.ndarray
        Complex sheet conductivity [S].
    """
    # Checks: the Gamma(mu) relation and the thermal terms are singular at zero.
    omega_array = _as_omega(omega)
    density = _along_carrier_axis(carrier_density, omega_array, "carrier_density")
    mobility_array = _along_carrier_axis(mobility, omega_array, "mobility")
    if np.any(density <= 0.0):
        raise ValueError("graphene needs carrier_density > 0 [m^-2]: Gamma(mobility) diverges at the Dirac point.")
    if np.any(mobility_array <= 0.0) or temperature <= 0.0 or fermi_velocity <= 0.0:
        raise ValueError("graphene needs mobility, temperature and fermi_velocity > 0.")

    # Chemical potential of the filled Dirac cone and the scattering rate from the mobility.
    hbar, kt = REDUCED_PLANCK_CONSTANT, BOLTZMANN_CONSTANT * temperature
    chemical_potential = hbar * fermi_velocity * np.sqrt(np.pi * density)
    gamma = ELEMENTARY_CHARGE * fermi_velocity / (hbar * mobility_array * np.sqrt(np.pi * density))

    # Intraband term; logaddexp(x, -x) = ln(2 cosh x) without overflow at high density.
    x = chemical_potential / (2.0 * kt)
    sigma_intra = (1j * ELEMENTARY_CHARGE**2 * 2.0 * kt / (np.pi * hbar**2 * (omega_array + 1j * gamma))
                   * np.logaddexp(x, -x))

    # Interband term with its thermally smeared Pauli-blocking edge at hbar omega = 2 mu_c.
    hbar_omega, two_mu, two_kt = hbar * omega_array, 2.0 * chemical_potential, 2.0 * kt
    sigma_inter = ELEMENTARY_CHARGE**2 / (4.0 * hbar) * (
        0.5
        + np.arctan((hbar_omega - two_mu) / two_kt) / np.pi
        - 1j / (2.0 * np.pi) * np.log((hbar_omega + two_mu) ** 2 / ((hbar_omega - two_mu) ** 2 + two_kt**2))
    )
    return np.asarray(sigma_intra + sigma_inter, dtype=np.complex128)


def graphene_sheet_permittivity(
    omega: float | npt.ArrayLike,
    *,
    carrier_density: float | npt.ArrayLike,
    mobility: float | npt.ArrayLike,
    thickness: float,
    eps_inf: float = 1.0,
    temperature: float = 300.0,
    fermi_velocity: float = 1.0e6,
) -> np.ndarray:
    """Effective permittivity of a graphene sheet modelled as a slab of ``thickness``.

    ``eps = eps_inf + i sigma_sheet / (eps0 omega thickness)``: spreading the
    sheet current over a thin slab gives a bulk conductivity
    ``sigma_sheet / thickness``, which reproduces the sheet's optical response
    in a multilayer calculation as long as the slab is much thinner than the
    wavelength (the result then does not depend on the thickness chosen).
    Other parameters as in :func:`graphene_sheet_conductivity`.
    """
    # The sheet current as a bulk polarisation of the effective slab.
    if thickness <= 0.0:
        raise ValueError(f"thickness must be > 0 [m], got {thickness}.")
    omega_array = _as_omega(omega)
    sigma = graphene_sheet_conductivity(omega_array, carrier_density=carrier_density, mobility=mobility,
                                        temperature=temperature, fermi_velocity=fermi_velocity)
    return eps_inf + 1j * sigma / (VACUUM_PERMITTIVITY * omega_array * thickness)


# Models by the name a material file gives them. Every function returns the relative permittivity.
MODELS = {
    "constant": constant_permittivity,
    "drude": drude_permittivity,
    "lorentz": lorentz_permittivity,
    "drude_lorentz": drude_lorentz_permittivity,
    "tabulated": tabulated_permittivity,
    "graphene_sheet": graphene_sheet_permittivity,
}
