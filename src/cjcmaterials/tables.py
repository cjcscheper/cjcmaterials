"""Tabulated optical constants n and kappa read from a file.

The file format is the CSV export of refractiveindex.info: optional ``#`` comment lines, a block headed ``wl,n``
and a block headed ``wl,k``, each a list of ``wavelength_um,value`` rows
(wavelength in micrometres). The two blocks may have different wavelength
grids and ranges, as in many handbooks where kappa is not tabulated in the
transparent region.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import numpy.typing as npt

from cjcmaterials._constants import SPEED_OF_LIGHT


@dataclass(frozen=True)
class NKTable:
    """Tabulated n and kappa of one file, on increasing frequency.

    Attributes
    ----------
    file : str
        The file they were read from.
    n_freq, n : np.ndarray
        Frequencies [Hz] and real refractive index n' at them.
    kappa_freq, kappa : np.ndarray
        Frequencies [Hz] and extinction coefficient kappa at them.
    """

    file: str
    n_freq: np.ndarray
    n: np.ndarray
    kappa_freq: np.ndarray
    kappa: np.ndarray


def _read_blocks(path: Path) -> dict[str, list[tuple[float, float]]]:
    """``{'n': rows, 'k': rows}`` from a refractiveindex.info CSV export."""
    blocks: dict[str, list[tuple[float, float]]] = {}
    quantity = None
    with open(path, encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.strip()

            # Blank and comment lines carry no data; a 'wl,<quantity>' header starts a block.
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("wl,"):
                quantity = line.split(",")[1].strip().lower()
                blocks[quantity] = []
                continue

            # Every other line is one 'wavelength_um,value' row of the current block.
            if quantity is None:
                raise ValueError(f"{path}, line {line_number}: data before a 'wl,n' or 'wl,k' header.")
            try:
                wavelength_um, value = (float(part) for part in line.split(","))
            except ValueError:
                raise ValueError(f"{path}, line {line_number}: expected 'wavelength_um,value', got {line!r}.") from None
            blocks[quantity].append((wavelength_um, value))
    return blocks


@lru_cache(maxsize=None)
def _read_nk_table_cached(resolved_path: str) -> NKTable:
    """Read once per file and session: tables are read on every evaluation otherwise."""
    path = Path(resolved_path)
    blocks = _read_blocks(path)
    missing = [quantity for quantity in ("n", "k") if not blocks.get(quantity)]
    if missing:
        raise ValueError(f"{path}: no 'wl,{missing[0]}' block; a table needs both 'wl,n' and 'wl,k'.")

    # Convert each block to increasing frequency, the axis the models work on.
    columns = {}
    for quantity in ("n", "k"):
        wavelength_um, value = np.array(blocks[quantity], dtype=np.float64).T
        if np.any(wavelength_um <= 0.0):
            raise ValueError(f"{path}: wavelengths in the 'wl,{quantity}' block must be > 0.")
        freq = SPEED_OF_LIGHT / (wavelength_um * 1e-6)
        order = np.argsort(freq)
        if np.any(np.diff(freq[order]) <= 0.0):
            raise ValueError(f"{path}: repeated wavelength in the 'wl,{quantity}' block.")
        frozen_freq, frozen_value = freq[order], value[order]
        frozen_freq.flags.writeable = False
        frozen_value.flags.writeable = False
        columns[quantity] = (frozen_freq, frozen_value)
    return NKTable(str(path), columns["n"][0], columns["n"][1], columns["k"][0], columns["k"][1])


def read_nk_table(file: str | Path) -> NKTable:
    """Read a refractiveindex.info CSV export (``wl,n`` and ``wl,k`` blocks, wavelength in µm).

    The result is cached per file, so a table is parsed once per session; the
    arrays are read-only for that reason.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If a block is missing or a row cannot be read; the message names the line.
    """
    path = Path(file).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Table file {path} not found.")
    return _read_nk_table_cached(str(path))


def tabulated_refractive_index(omega: float | npt.ArrayLike, *, file: str | Path) -> np.ndarray:
    """Complex refractive index n' + i kappa interpolated from a table file.

    n' and kappa are interpolated linearly in frequency, each on its own grid,
    so the table values come back exactly at the table points. Outside a
    block's range the result is NaN: a table says nothing about frequencies it
    does not contain, and extrapolating optical constants (across a band edge,
    say) is a physics choice the user must make, not this function.

    Parameters
    ----------
    omega : float or array
        Angular frequency [rad/s], > 0.
    file : str or Path
        A table in the refractiveindex.info CSV format (see :func:`read_nk_table`).

    Returns
    -------
    np.ndarray
        Complex ``n' + i kappa``, same shape as ``omega``; NaN outside the table.
    """
    # Frequencies, the axis the table was sorted on.
    omega_array = np.asarray(omega, dtype=np.float64)
    if np.any(~np.isfinite(omega_array)) or np.any(omega_array <= 0.0):
        raise ValueError("omega must be finite and > 0 [rad/s].")
    freq = omega_array / (2.0 * np.pi)
    table = read_nk_table(file)

    # Linear interpolation inside each block, NaN outside it (no extrapolation).
    n = np.interp(freq, table.n_freq, table.n, left=np.nan, right=np.nan)
    kappa = np.interp(freq, table.kappa_freq, table.kappa, left=np.nan, right=np.nan)

    # Assembled part by part: n + 1j * nan would turn a known n into NaN as well.
    index = np.array(n, dtype=np.complex128)
    index.imag = kappa
    return index


def tabulated_permittivity(omega: float | npt.ArrayLike, *, file: str | Path) -> np.ndarray:
    """Complex permittivity ``(n' + i kappa)**2`` from a table file; NaN outside the table.

    See :func:`tabulated_refractive_index` for the interpolation.
    """
    # The table holds n and kappa; epsilon = N^2 follows without further assumptions.
    return tabulated_refractive_index(omega, file=file) ** 2
