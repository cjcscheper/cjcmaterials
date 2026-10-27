"""Small material libraries written into a temporary folder, for the library and checker tests."""

from pathlib import Path

import pytest

# A complete, correct material with two descriptions that meet at 10 THz (no overlap):
# a Drude model for 0.1-10 THz and a constant index for 20-30 THz. Tests derive broken
# versions of it by replacing one piece of text.
GOOD_MATERIAL = """\
name: Testium
note: A made-up material for the tests.
sources:
  book:
    type: isbn
    id: 0-12-544420-6
    citation: E. D. Palik (ed.), Handbook of Optical Constants of Solids, Academic Press (1985)
    location: p. 1
    valid_range_thz: [[0.1, 30]]
    checked: no
  paper:
    type: doi
    id: 10.1063/1.372274
    citation: >-
      M. Sotoodeh, A. H. Khalid, A. A. Rezazadeh, Empirical low-field mobility model for III-V
      compounds applicable in device simulation codes, J. Appl. Phys. 87, 2890-2900 (2000)
    location: Table I
    valid_range_thz: [[0.1, 10]]
    checked: "C. Scheper, 2026-10-27"
descriptions:
  - label: thz
    model: drude
    valid_range_thz: [[0.1, 10]]
    sources: [book]
    parameters:
      eps_inf: 10.0
      electrons:
        effective_mass_ratio: 0.1
        mobility: {model: caughey_thomas, mu_min: 0.01, mu_max: 0.5, n_ref: 1.0e23, alpha: 0.5, source: paper}
      holes:
        effective_mass_ratio: 0.5
        mobility: 0.02
  - label: ir
    model: constant
    valid_range_thz: [[20, 30]]
    sources: [book]
    parameters:
      n: 3.0
"""


def write_material(folder: Path, text: str, name: str = "Testium") -> Path:
    """Write ``text`` as ``<name>.yaml`` in ``folder`` and return the path."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.yaml"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def good_library(tmp_path) -> Path:
    """A folder with only the complete test material."""
    folder = tmp_path / "library"
    write_material(folder, GOOD_MATERIAL)
    return folder
