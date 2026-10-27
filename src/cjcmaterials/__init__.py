"""cjcmaterials: optical and electronic material models with a sourced material library.

Models are plain functions of the angular frequency (Drude, Lorentz,
Drude–Lorentz, graphene sheet, constant index, tabulated n and kappa), named
in one table, :data:`MODELS`. The library holds one YAML file per material,
each with one or more descriptions (a model, its parameters, a valid
frequency range, and sources that a person can check), and
``python -m cjcmaterials.check_library`` checks it. The carrier density and
carrier type are given when a material is used, not stored in its file::

    from cjcmaterials import get_material, refractive_index
    n = refractive_index(get_material("InP"), omega, carrier_density=1e22, carrier_type="n")

numpy and pyyaml are the only dependencies.
"""

from cjcmaterials._constants import (
    BOLTZMANN_CONSTANT,
    ELECTRON_MASS,
    ELEMENTARY_CHARGE,
    REDUCED_PLANCK_CONSTANT,
    SPEED_OF_LIGHT,
    VACUUM_PERMITTIVITY,
)
from cjcmaterials.checker import LibraryCheck, check_library, library_overview
from cjcmaterials.library import (
    LIBRARY_DIR,
    SOURCE_TYPES,
    Description,
    Material,
    Source,
    available_materials,
    get_material,
    load_material_file,
)
from cjcmaterials.mobility import MOBILITY_MODELS, caughey_thomas_mobility
from cjcmaterials.models import (
    MODELS,
    constant_permittivity,
    drude_conductivity,
    drude_lorentz_permittivity,
    drude_permittivity,
    graphene_sheet_conductivity,
    graphene_sheet_permittivity,
    lorentz_permittivity,
    plasma_omega,
    scattering_time_from_mobility,
)
from cjcmaterials.optics import conductivity, permittivity, refractive_index, select_description
from cjcmaterials.tables import NKTable, read_nk_table, tabulated_permittivity, tabulated_refractive_index

__version__ = "0.1.0"

__all__ = [
    "BOLTZMANN_CONSTANT",
    "Description",
    "ELECTRON_MASS",
    "ELEMENTARY_CHARGE",
    "LIBRARY_DIR",
    "LibraryCheck",
    "MOBILITY_MODELS",
    "MODELS",
    "Material",
    "NKTable",
    "REDUCED_PLANCK_CONSTANT",
    "SOURCE_TYPES",
    "SPEED_OF_LIGHT",
    "Source",
    "VACUUM_PERMITTIVITY",
    "available_materials",
    "caughey_thomas_mobility",
    "check_library",
    "conductivity",
    "constant_permittivity",
    "drude_conductivity",
    "drude_lorentz_permittivity",
    "drude_permittivity",
    "get_material",
    "graphene_sheet_conductivity",
    "graphene_sheet_permittivity",
    "library_overview",
    "load_material_file",
    "lorentz_permittivity",
    "permittivity",
    "plasma_omega",
    "read_nk_table",
    "refractive_index",
    "scattering_time_from_mobility",
    "select_description",
    "tabulated_permittivity",
    "tabulated_refractive_index",
]
