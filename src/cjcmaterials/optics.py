"""Optical response of a library material: permittivity, refractive index, conductivity.

The three public functions take a :class:`~cjcmaterials.Material`, the
angular frequencies and the use-time inputs (carrier density and type), choose
a description, and call the model function that the description names in
``cjcmaterials.MODELS``: dispatch by name, never by type.

Why the carrier density is an input here and not in the file: it is a
property of the sample and the moment (doping, photo-excitation, a depth
profile), not of the material. The file holds what stays the same: the
effective mass, the mobility (model), the background. A file may still give a
``carrier_density`` for materials where it is a material constant (a metal);
a value given here then replaces it.
"""

from __future__ import annotations

import inspect
import warnings

import numpy as np
import numpy.typing as npt

from cjcmaterials._constants import VACUUM_PERMITTIVITY
from cjcmaterials.library import Description, Material
from cjcmaterials.mobility import MOBILITY_MODELS
from cjcmaterials.models import MODELS

# Use-time carrier type -> the parameter block of a description that holds its parameters.
CARRIER_BLOCKS = {"n": "electrons", "p": "holes"}


def _format_ranges(ranges: tuple[tuple[float, float], ...]) -> str:
    """``0.06-21, 300-1500 THz`` style text for messages; ``no valid range`` when there is none."""
    if not ranges:
        return "no valid range"
    return ", ".join(f"{low:g}-{high:g}" for low, high in ranges) + " THz"


def _inside(freq_thz: np.ndarray, ranges: tuple[tuple[float, float], ...]) -> np.ndarray:
    """Which frequencies lie inside one of the intervals (edges included)."""
    inside = np.zeros(freq_thz.shape, dtype=bool)
    for low, high in ranges:
        inside |= (freq_thz >= low) & (freq_thz <= high)
    return inside


def select_description(
    material: Material, omega: float | npt.ArrayLike, *, description: str | None = None
) -> Description:
    """Choose the description of ``material`` to use at ``omega``.

    By default this is the one description whose valid range covers all
    requested frequencies. If several do, or none does, the choice is a
    physics decision the package will not make for you: a ``ValueError`` lists
    the descriptions with their ranges, and ``description="<label>"`` picks one
    explicitly (frequencies outside its range then give a warning when it is
    evaluated).

    Raises
    ------
    ValueError
        For an unknown label, or when not exactly one description covers ``omega``.
    """
    labels = [item.label for item in material.descriptions]
    listing = "; ".join(f"{item.label!r} ({item.model}, {_format_ranges(item.valid_range_thz)})"
                        for item in material.descriptions)

    # An explicit choice wins, whatever the frequencies.
    if description is not None:
        for item in material.descriptions:
            if item.label == description:
                return item
        raise ValueError(f"{material.name} has no description {description!r}; it has {labels}.")

    # Otherwise exactly one description must cover every requested frequency.
    freq_thz = np.atleast_1d(np.asarray(omega, dtype=np.float64)) / (2.0 * np.pi) / 1e12
    covering = [item for item in material.descriptions if np.all(_inside(freq_thz, item.valid_range_thz))]
    span = f"{freq_thz.min():g}-{freq_thz.max():g} THz"
    if len(covering) == 1:
        return covering[0]
    if covering:
        raise ValueError(
            f"Several descriptions of {material.name} cover {span}: "
            + "; ".join(f"{item.label!r} ({_format_ranges(item.valid_range_thz)})" for item in covering)
            + ". Choose one with description='<label>'."
        )
    raise ValueError(
        f"No description of {material.name} covers all of {span}. It has: {listing}. "
        "Choose one with description='<label>' (frequencies outside its range give a warning), "
        "or split the frequencies."
    )


def _warn_outside_range(material: Material, chosen: Description, omega: npt.ArrayLike, stacklevel: int) -> None:
    """Warn when frequencies lie outside the chosen description's valid range, naming its sources."""
    freq_thz = np.atleast_1d(np.asarray(omega, dtype=np.float64)) / (2.0 * np.pi) / 1e12
    outside = ~_inside(freq_thz, chosen.valid_range_thz)
    if not np.any(outside):
        return

    # Name everything a reader needs to judge the extrapolation: where, how far, and whose values.
    citations = "; ".join(source.citation for source in chosen.sources) or "no source given"
    warnings.warn(
        f"{material.name}, description {chosen.label!r}: {np.count_nonzero(outside)} of {freq_thz.size} "
        f"frequencies ({freq_thz[outside].min():g}-{freq_thz[outside].max():g} THz) lie outside its valid "
        f"range ({_format_ranges(chosen.valid_range_thz)}). Source: {citations}.",
        UserWarning,
        stacklevel=stacklevel,
    )


def _model_inputs(
    material: Material,
    chosen: Description,
    carrier_density: float | npt.ArrayLike | None,
    carrier_type: str | None,
) -> dict:
    """The keyword arguments for the chosen model function, with the use-time inputs filled in."""
    where = f"{material.name}, description {chosen.label!r} ({chosen.model})"
    parameters = dict(chosen.parameters)
    accepted = inspect.signature(MODELS[chosen.model]).parameters

    # Carrier type: merge the matching electrons/holes block into the parameters.
    blocks = {name: parameters.pop(name) for name in CARRIER_BLOCKS.values() if name in parameters}
    if carrier_type is not None and carrier_type not in CARRIER_BLOCKS:
        raise ValueError(f"carrier_type must be 'n' (electrons) or 'p' (holes), got {carrier_type!r}.")
    if blocks:
        if carrier_type is None:
            # Without carriers the type does not matter (N = 0 removes the free-carrier term); with them it does.
            if carrier_density is not None and np.any(np.asarray(carrier_density) != 0.0):
                raise ValueError(f"{where}: give carrier_type='n' or 'p' with a carrier density.")
            parameters.update(next(iter(blocks.values())))
        elif CARRIER_BLOCKS[carrier_type] not in blocks:
            raise ValueError(f"{where}: has no {CARRIER_BLOCKS[carrier_type]!r} parameters for carrier_type="
                             f"{carrier_type!r}; it has {sorted(blocks)}.")
        else:
            parameters.update(blocks[CARRIER_BLOCKS[carrier_type]])
    elif carrier_type is not None:
        raise ValueError(f"{where}: carrier_type applies only to descriptions with electrons/holes parameters.")

    # Carrier density: only models with free carriers take one; a use-time value replaces the file's.
    if carrier_density is not None:
        if "carrier_density" not in accepted:
            raise ValueError(f"{where} has no free carriers; carrier_density cannot be set.")
        parameters["carrier_density"] = carrier_density
    elif "carrier_density" in accepted and "carrier_density" not in parameters:
        if accepted["carrier_density"].default is inspect.Parameter.empty:
            raise ValueError(f"{where} needs a carrier_density (see the model's docstring for its unit).")

    # Mobility models are evaluated at the carrier density, so the model receives a number (or one per density).
    for name, value in list(parameters.items()):
        if isinstance(value, dict) and "model" in value:
            model_parameters = dict(value)
            mobility_model = model_parameters.pop("model")
            if mobility_model not in MOBILITY_MODELS:
                raise ValueError(f"{where}: unknown mobility model {mobility_model!r}; known: {sorted(MOBILITY_MODELS)}.")
            density = parameters.get("carrier_density", accepted["carrier_density"].default
                                     if "carrier_density" in accepted else 0.0)
            parameters[name] = MOBILITY_MODELS[mobility_model](density, **model_parameters)
    return parameters


def _evaluate(material, omega, carrier_density, carrier_type, description, stacklevel) -> np.ndarray:
    """Choose a description, warn outside its range and evaluate its model: the shared path of all three."""
    chosen = select_description(material, omega, description=description)
    _warn_outside_range(material, chosen, omega, stacklevel=stacklevel + 1)
    parameters = _model_inputs(material, chosen, carrier_density, carrier_type)
    return MODELS[chosen.model](omega, **parameters)


def permittivity(
    material: Material,
    omega: float | npt.ArrayLike,
    *,
    carrier_density: float | npt.ArrayLike | None = None,
    carrier_type: str | None = None,
    description: str | None = None,
) -> np.ndarray:
    """Complex relative permittivity of ``material`` at angular frequencies ``omega``.

    Convention ``exp(-i omega t)``: ``Im eps >= 0`` for absorption.

    Parameters
    ----------
    material : Material
        From :func:`~cjcmaterials.get_material`.
    omega : float or array
        Angular frequency [rad/s], > 0.
    carrier_density : float or 1D array, optional
        Free-carrier density [m^-3] (a sheet density [m^-2] for graphene).
        Not given: no free carriers (or the file's value, for a metal). K
        densities give shape ``(K,) + omega.shape``. Only for descriptions
        with free carriers.
    carrier_type : {"n", "p"}, optional
        Electrons or holes, choosing the description's ``electrons`` or
        ``holes`` parameters (effective mass, mobility). Needed with a carrier
        density when the description has such blocks.
    description : str, optional
        Label of the description to use; by default the one whose valid range
        covers ``omega`` (see :func:`select_description`).

    Warns
    -----
    UserWarning
        When frequencies lie outside the chosen description's valid range.
    """
    # stacklevel 3: the warning points at the caller of this function.
    return _evaluate(material, omega, carrier_density, carrier_type, description, stacklevel=3)


def refractive_index(
    material: Material,
    omega: float | npt.ArrayLike,
    *,
    carrier_density: float | npt.ArrayLike | None = None,
    carrier_type: str | None = None,
    description: str | None = None,
) -> np.ndarray:
    """Complex refractive index ``n' + i kappa = sqrt(eps)`` of ``material``.

    The principal square root gives ``kappa >= 0`` whenever ``Im eps >= 0``,
    the decaying wave in the ``exp(-i omega t)`` convention, as cjctmm
    expects. Parameters as in :func:`permittivity`.
    """
    # The principal root, taken on the permittivity of the chosen description; NaN (no table data) stays NaN quietly.
    eps = _evaluate(material, omega, carrier_density, carrier_type, description, stacklevel=3)
    with np.errstate(invalid="ignore"):
        return np.sqrt(eps)


def conductivity(
    material: Material,
    omega: float | npt.ArrayLike,
    *,
    carrier_density: float | npt.ArrayLike | None = None,
    carrier_type: str | None = None,
    description: str | None = None,
) -> np.ndarray:
    """Total optical conductivity ``sigma = -i omega eps0 (eps - 1)`` [S/m] of ``material``.

    This counts every charge (free carriers, phonons, bound electrons) as a
    current, so it is defined for every description, tables included; its
    real part is the absorption. For the free-carrier part alone use the model
    functions (:func:`~cjcmaterials.drude_conductivity`), and for a graphene
    sheet :func:`~cjcmaterials.graphene_sheet_conductivity` (in S, not S/m;
    the value here is that of its effective slab). Parameters as in
    :func:`permittivity`.
    """
    # Inverse of eps = 1 + i sigma / (eps0 omega).
    eps = _evaluate(material, omega, carrier_density, carrier_type, description, stacklevel=3)
    return -1j * np.asarray(omega, dtype=np.float64) * VACUUM_PERMITTIVITY * (eps - 1.0)
