# AGENTS.md — cjcmaterials

Guidance for AI coding agents (and contributors) working in this repository.

This file covers much of the same ground as `README.md`, but for a different
reader: `README.md` is for people who *use* cjcmaterials (install, quick start,
descriptions and valid ranges, the file syntax, the checker, the examples);
this file is for agents who *work on* it (layout, design rules, the library
rules, conventions, tests, releases). `THEORY.md` holds the physics of the
models, the conventions and what the checker can and cannot verify.
`LIBRARY.md` is generated from the YAML files and never edited by hand. When
something changes that more than one of them describes, such as the public
API, the file syntax or a convention, update all of them.

cjcmaterials is strictly about materials: model functions, the material
library with its sources, and the library checker. It contains **no layer
stacks, no `Layer`/`Multilayer`, no discretisation, no transfer matrices or
field ratios, and no fitting**: those belong to cjctmm, cjcfit and a later
stack package. Never import cjctmm or cjcfit (a test checks it).

## Commands

```bash
pip install -e ".[test]"                                  # editable install with pytest
pytest                                                    # run all tests
python -m cjcmaterials.check_library                      # check the bundled library and LIBRARY.md
python -m cjcmaterials.check_library --write-overview     # regenerate LIBRARY.md after editing a YAML file
python -m cjcmaterials.check_library --online             # also resolve DOIs and URLs (needs network)
pip install -e ".[examples]"                              # cjcplot, pinned, for the examples
python examples/example_semiconductors_thz.py             # each example saves its PNG(s) next to itself
```

## Public API

Scripts import only from the package root, never from submodules:

```python
from cjcmaterials import get_material, available_materials, load_material_file, LIBRARY_DIR
from cjcmaterials import Material, Description, Source, SOURCE_TYPES
from cjcmaterials import permittivity, refractive_index, conductivity, select_description
from cjcmaterials import MODELS, constant_permittivity, drude_permittivity, drude_conductivity
from cjcmaterials import lorentz_permittivity, drude_lorentz_permittivity
from cjcmaterials import graphene_sheet_permittivity, graphene_sheet_conductivity
from cjcmaterials import tabulated_permittivity, tabulated_refractive_index, read_nk_table, NKTable
from cjcmaterials import MOBILITY_MODELS, caughey_thomas_mobility, plasma_omega, scattering_time_from_mobility
from cjcmaterials import check_library, LibraryCheck, library_overview
from cjcmaterials import SPEED_OF_LIGHT, VACUUM_PERMITTIVITY, ELEMENTARY_CHARGE, ELECTRON_MASS
from cjcmaterials import REDUCED_PLANCK_CONSTANT, BOLTZMANN_CONSTANT
```

The command line is `python -m cjcmaterials.check_library` (`check_library.py`
holds only `main`; the root package must never import that module, or
`python -m` warns).

## Package layout

```
src/cjcmaterials/
  __init__.py        public API and __version__ (its only source)
  _constants.py      c, mu0, eps0, e, m_e, hbar, k_B written out (no scipy); same values as cjctmm
  models.py          the model functions and MODELS (name -> permittivity function)
  mobility.py        caughey_thomas_mobility and MOBILITY_MODELS
  tables.py          read_nk_table (refractiveindex.info CSV, cached), tabulated_refractive_index/permittivity
  library.py         Source, Description, Material; load_material_file, get_material, available_materials
  optics.py          permittivity, refractive_index, conductivity, select_description; the use-time inputs
  checker.py         check_library, LibraryCheck, library_overview, identifier and online checks
  check_library.py   command line (main) only
  library/           one <name>.yaml per material, plus its table files (package data)
tests/
  conftest.py        a small complete test material (GOOD_MATERIAL) and write_material()
  test_models.py     analytic values of every model
  test_mobility_tables.py  Caughey-Thomas limits, table reading and interpolation
  test_library.py    bundled files, selection, warnings, carrier inputs, own folders
  test_checker.py    every checker rule on a deliberately broken copy of the test material; CLI; template
  test_dependencies.py  numpy and pyyaml only; no cjctmm or cjcfit
  data/own_library/  the 'test' material of optpumpthz, as an own-folder example
examples/            one script per topic, PNGs next to it
LIBRARY.md           generated overview, never edited by hand
material_template.yaml  annotated template for a new material file (not loaded as a material)
```

## Design rules

- **Models are plain functions, dispatched by name.** Every model is one
  function `<model>_permittivity(omega, *, <parameters>)` returning the
  relative permittivity, listed in `MODELS`. `optics.py` looks the model up
  by the description's `model` name; there is no `isinstance` dispatch
  anywhere, and no model classes. Adding a model = one function + one line in
  `MODELS` (+ tests with analytic values, a THEORY.md section, a README table
  row). Mobility models likewise: one function + one line in `MOBILITY_MODELS`.
- **The keyword names of a model function are the parameter names in the
  files**, so a description maps one-to-one onto a function call. Rename one
  only together with every YAML file that uses it.
- **Carrier density and type are use-time inputs.** They are not stored in
  the files (except as a material constant, e.g. a metal's electron density,
  which a use-time value replaces). Carrier-type dependent parameters live in
  `electrons` / `holes` blocks, merged by `optics._model_inputs`, which also
  evaluates mobility models at the given density. Keep this logic in that one
  function.
- **One shared path.** `permittivity`, `refractive_index` and `conductivity`
  all go through `optics._evaluate` (select, warn, inputs, model). The
  selection rule: exactly one description must cover the frequencies, else a
  `ValueError` listing all descriptions and ranges; an explicit `description=`
  wins, with a `UserWarning` outside its range naming material, description,
  range and source. Never choose silently between overlapping descriptions.
- **No extrapolation.** Tables give NaN outside their data; the warning says
  where the description is not valid.
- **Conventions are fixed** and equal to cjctmm's: `exp(-i omega t)`,
  `n = n' + i kappa` with `kappa >= 0` absorbing, `Im eps >= 0`,
  `sigma = -i omega eps0 (eps - 1)` for the total conductivity.
- **Classes only as frozen dataclasses for data** (`Material`, `Description`,
  `Source`, `NKTable`, `LibraryCheck`): no methods (validation in
  `__post_init__` would be allowed, but the library dataclasses deliberately
  accept incomplete data so the checker can report it), no inheritance.
- **No user-editable settings in the package**: every setting is a keyword
  argument with a documented default. The checker's private sanity densities
  are rule internals, not settings.
- **Loading is lenient, the checker strict.** `load_material_file` refuses
  only what it cannot interpret (unknown model, undefined source key, wrong
  structure); missing sources or ranges load, so the checker can list all
  problems at once.

## Library rules

- **The YAML files are the only source of truth.** After any change to a
  material file run `python -m cjcmaterials.check_library --write-overview`
  and commit `LIBRARY.md` with it (a test fails when it is stale).
- **Every value has a source.** A description lists its sources; a parameter
  with a different source gets `{value: ..., source: <key>}`. A source has
  `type` (doi, isbn or url only), `id`, `citation`, `location`,
  `valid_range_thz` and `checked`.
- **Never invent a citation or a value silently.** A candidate source or
  value you could not verify goes in with `checked: no` and a `location` or
  `note` saying so, and is reported to the maintainer. Only the maintainer
  (or the person who checked) sets `checked: "<who>, <YYYY-MM-DD>"`; an agent
  never marks a source as checked.
- Start a new material from `material_template.yaml` (repository root) and
  keep its field order (name, note, sources, descriptions; within a source:
  type, id, citation, location, valid_range_thz, checked). Every library file
  starts with the one-line header naming the template (a test checks it).
  When the file syntax changes, update the template; a test checks that it
  still loads and passes the checker.
- Values in SI units, as the model functions take them; give the value in
  the paper's own unit as a trailing comment where it differs (e.g. cm⁻¹ for
  oscillators), so a reader can compare at a glance.
- Tables are refractiveindex.info CSV exports (`wl,n` and `wl,k` blocks,
  wavelength in µm) next to the YAML file, named `<material>_<Source><year>.csv`,
  with a `#` line naming the source. They are package data
  (`pyproject.toml`). A description's range must lie inside the part of the
  table that has both n and κ (the checker tests it).
- Run `--online` after adding or changing a DOI.

## Coding conventions

- Functions first: physics is written as plain functions (inputs in, outputs
  out); a module groups functions, never a class.
- Every logical block inside a function gets a one-line `#` comment saying why
  it exists. Docstrings explain why and how (where a formula comes from, which
  sign and why), with Parameters / Returns / Raises.
- SI units need no suffix (`omega` in rad/s, `freq` in Hz, densities in m⁻³,
  mobility in m²/(V s)); non-SI values carry one (`_thz`, `_cm3`,
  `_cm2_per_vs`, `_um`). `effective_mass_ratio` is m*/mₑ (a ratio, so no unit).
- Physicist-first names (`carrier_density`, `effective_mass_ratio`,
  `resonance_omega`, `plasma_omega`, `valid_range_thz`), no programmer idioms.
- Wrong inputs raise `ValueError` with a message that says what is wrong and,
  where possible, which material, description or parameter.
- Shared code goes in one module and is imported, never copied.
- Remove unused code instead of leaving it commented out.
- Python 3.10 compatible (no syntax newer than 3.10).

## Dependencies

- All dependencies live in `pyproject.toml`, the only list: `[project]
  dependencies` (numpy, pyyaml), the `test` extra (pytest) and the `examples`
  extra (cjcplot pinned to a release tag). There is no `requirements.txt`.
- The package (`src/cjcmaterials/`) and `tests/` never import matplotlib or
  cjcplot (nor scipy, cjctmm, cjcfit); only `examples/` may, via the pinned
  extra. When upgrading the pin, change the tag in pyproject.toml (and in the
  README) and regenerate all example PNGs. Examples use cjcplot's public API
  for everything, including the legend and saving (`save_path=...,
  fig_show=False`); the only additions are drawing on the axes plot_1d
  returns (shaded ranges, passed back with `ax=`) and `plt.rc_context` for
  shorter legend handles so a two-column legend fits. Every figure has its
  own file named after the material it shows (`..._GaAs_n.png`) and the size
  `fig_aspect_ratio=(0.5, 0.5)`.

## Tests

- Tests check values that can be verified by hand: `sigma_DC = N e mu`
  (1.602e4 S/m for 1e24 m⁻³ and 0.1 m²/Vs), the plasma-frequency zero
  crossing, `sigma' = sigma''= sigma_DC/2` at `omega = 1/tau`,
  `eps(0) = eps_inf + strength`, the Caughey–Thomas midpoint, the universal
  graphene absorption `e^2/(4 hbar)`, table values at table points.
- Every checker rule has a test that breaks one piece of the good test
  material (`conftest.GOOD_MATERIAL`) and expects that rule's message. The
  bundled library must pass all offline rules
  (`test_bundled_library_passes_every_offline_rule_and_overview_is_current`).
- Online checks are tested with the network calls replaced (`monkeypatch`);
  no test needs the network.
- Wrong inputs raise `ValueError`s with clear messages, and those messages are
  tested.
- New or changed functionality comes with new or updated tests in the same
  change, and `pytest` passes before committing. When the public API or the
  file syntax changes, update the README, this file, THEORY.md, CHANGELOG.md
  and the affected examples (and their PNGs) too.
- Every test has a one-line docstring saying what it checks; non-obvious lines
  (the reason behind a value or tolerance) get a short comment.
- GitHub Actions (`.github/workflows/tests.yml`) runs `pytest` on Python 3.10
  and 3.14 for every push and pull request.

## Changelog and releases

- Every change that users notice (new or changed functionality, fixes, library
  values or sources, docs people rely on) gets a line in `CHANGELOG.md` under
  `## [Unreleased]`, in the same change, sorted under `### Added`,
  `### Changed`, `### Fixed` or `### Removed`.
- Before finishing a change, check that `CHANGELOG.md` describes it.
- Versions follow MAJOR.MINOR.PATCH: patch for fixes, minor for new features
  or materials, major for changes that break existing scripts (below 1.0 the
  API may still change). A change of a convention, of the file syntax or of a
  library value that changes results counts as breaking.
- A release:
  1. rename `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` and start a new empty
     `## [Unreleased]` above it;
  2. set the new version in `src/cjcmaterials/__init__.py` (`__version__`), its
     only source: `pyproject.toml` reads it from there; also update the pinned
     version in the README's install command;
  3. commit, tag `vX.Y.Z`, push the commit and the tag, and publish the GitHub
     release with the changelog section as its notes.

## Git workflow

- Do not commit, push, tag, merge or force-push without the maintainer's approval.
- Keep each change focused: no unrelated reformatting or renaming mixed in.
- Keep generated files in the same change as the code or data that produces
  them: `LIBRARY.md` with the YAML files, an example's PNGs with the example.
- In the commit message (or pull request), summarise what changes for users and
  how it was checked (tests run, check_library run, examples regenerated).
