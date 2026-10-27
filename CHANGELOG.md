# Changelog

All notable changes to cjcmaterials. Versions follow MAJOR.MINOR.PATCH: patch
for fixes, minor for new features or materials, major for changes that break
existing scripts.

## [Unreleased]

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
