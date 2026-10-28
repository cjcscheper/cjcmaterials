# Changelog

All notable changes to cjcmaterials. Versions follow MAJOR.MINOR.PATCH: patch
for fixes, minor for new features or materials, major for changes that break
existing scripts.

## [Unreleased]

### Added
- Be, Cr, Ni, Pd, Pt, Ti and W: the Lorentz–Drude model of Rakić et al.
  (1998), Tables 1 and 2, converted from eV to SI; each valid over the
  energy range its fit used (0.06–6 eV depending on the metal, so from
  14.5–48 THz upwards).
- Al: the refractiveindex.info database (Polyanskiy 2024) as a second
  source of both descriptions.
- Al: an optical description from the Rakić (1995) n, k table,
  0.000124–200 µm (1.5–2.4·10⁶ THz); it overlaps the Lorentz–Drude
  description at 1.5–4835 THz, where `description=` chooses.

### Changed
- Al: the free-electron Drude description `thz` (0.1–6 THz, Ashcroft and
  Mermin, Ordal 1985) is replaced by Rakić (1998)'s Lorentz–Drude model,
  `lorentz_drude`, valid 1.21–4835 THz (0.005–20 eV, the range of the
  refractiveindex.info script; the paper's range is 0.1–6 eV); the
  parameters are converted from eV to SI. Scripts using
  `description="thz"` for Al need `description="lorentz_drude"`; below
  1.21 THz it now warns.
- air: lab air with n = 1.0003 from the Ciddor (1996) model instead of
  vacuum. Two descriptions: `optical` (177.4–1303.4 THz, Ciddor) and `thz`
  (0.001–177.4 THz, the same constant continued, bounded by vacuum n = 1).
- GaAs: Palik (1985) is replaced by Franta et al. (2026). The table
  `GaAs_Franta2026.csv` (undoped, 0.751–334.8 THz) is the new `infrared`
  description, and the TO-phonon oscillator and eps_inf of the `thz`
  description take Franta's literature values instead of unsourced
  candidates: f_TO = 8.0337 THz, f_LO = 8.7361 THz, eps_inf = 10.873,
  gamma = 63.18 GHz, strength from the LST relation (eps_s = 12.857). The
  `thz` description is now valid 0.1–7.5 THz (was 0.1–20 THz): n agrees with
  Franta's table to 0.5 % there, but by up to 17 % at the resonance.
- GaAs: the hole effective mass of the `thz` description is 0.18 (was
  0.51, the heavy-hole band mass alone): the conductivity mass from Franta
  et al. (2026)'s light/heavy-hole Drude split of Zn-doped GaAs with the band
  masses of Levinshtein (1996); it reproduces the nominal doping of both of
  Franta's samples. The Drude hole plasma frequency rises by 1.7× at the
  same density.
- GaAs: the `optical` description is now the Papatryfonos et al. (2021)
  table of MBE-grown GaAs at 334.8–1150 THz (was Palik, 332–1498 THz).

### Removed
- GaAs: the Palik (1985) table.

## [0.1.0] - 2026-10-27

First release: the material models and library of optpumpthz, redesigned as a
standalone package with sources for every value.

### Added
- Model functions returning the permittivity, dispatched by name through
  `MODELS`: `constant_permittivity`, `drude_permittivity` (mobility or
  scattering time, optional Drude–Smith `smith_c`), `lorentz_permittivity`,
  `drude_lorentz_permittivity`, `graphene_sheet_permittivity` and
  `tabulated_permittivity`; also `drude_conductivity`,
  `graphene_sheet_conductivity` (sheet, in S), `plasma_omega`,
  `scattering_time_from_mobility`, `tabulated_refractive_index`,
  `read_nk_table` (refractiveindex.info CSV format). Free-carrier models take
  one carrier density or K of them (result `(K, M)`).
- `caughey_thomas_mobility` and `MOBILITY_MODELS`, evaluated at the use-time
  carrier density when a material file gives a mobility model.
- The material library: one YAML file per material with one or more
  descriptions (model, parameters, `valid_range_thz`, sources) and sources
  with type doi / isbn / url, id, citation, location, valid range and
  `checked`. Ported from optpumpthz: air, Al, GaAs, In0.53Ga0.47As, InP, Si,
  Graphene, SiO2 (n- and p-type variants merged into one file each); new: GaN
  and SiN tables from the pump-ΔT/T source files.
- `get_material(name, folders=None)` and `available_materials(folders=None)`
  with the user's own folders searched first (override and extend);
  `load_material_file`; frozen dataclasses `Material`, `Description`, `Source`.
- `permittivity`, `refractive_index` and `conductivity` of a material with
  use-time `carrier_density` and `carrier_type` ("n"/"p"), automatic
  description choice by frequency (error on overlap or no coverage),
  explicit `description=`, and a `UserWarning` outside the valid range;
  `select_description`.
- The checker `check_library` / `python -m cjcmaterials.check_library`:
  completeness, DOI/ISBN/URL syntax (ISBN check digit), valid ranges (also
  against the sources and the table), physical sanity, the list of unchecked
  sources, `LIBRARY.md` up to date (`--write-overview`), and `--online` DOI
  metadata and URL checks; exit code 0 / 1.
- `material_template.yaml`: an annotated material file to copy for a new
  material; each library file starts with a one-line header pointing to it.
- `LIBRARY.md` (generated), README, AGENTS.md, THEORY.md, tests, four
  examples (plotted with cjcplot v0.2.0 through the `examples` extra) and a
  GitHub Actions workflow.

### Changed (compared with optpumpthz)
- No THz/optical regime splitting: a material has several descriptions with
  their own valid ranges, and the choice between them is explicit.
- Carrier density and type are given when a material is used, not stored in
  the material (no `set_carrier_density`, no `InP_n`/`InP_p`).
- InP: the THz description is valid 0.06–21 THz (the range of its oscillator
  fit) instead of 0.1–6 THz; the optical table is Glembocki 1985 instead of a
  constant-index placeholder. GaAs: a TO-phonon oscillator was added to the
  THz description (candidate values, unchecked); the optical table is Palik
  1985 instead of a placeholder. The Caughey–Thomas exponent is called
  `alpha` (was `lambda`).

### Removed (compared with optpumpthz)
- The placeholder optical tables of Al, SiO2, In0.53Ga0.47As and the `test`
  material (constant n = 1.5 everywhere, n = 1.5 for a metal); the `test`
  material itself moved to `tests/data/own_library/`.
