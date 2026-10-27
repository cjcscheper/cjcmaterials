"""The material library: one YAML file per material, read into frozen dataclasses.

A material file (``<name>.yaml``) holds the material's ``sources`` and one or
more ``descriptions``. A description names a model of ``cjcmaterials.models``,
its parameters, the frequency range where it is valid and its sources; a
source says where the values come from and whether a person has checked them.
The YAML files are the only source of truth: ``LIBRARY.md`` is generated from
them, and ``python -m cjcmaterials.check_library`` checks them. The syntax is
shown at the top of every bundled file and in the README.

The bundled files live in ``LIBRARY_DIR``; :func:`get_material` and
:func:`available_materials` also search the user's own folders, which come
first, so a user file overrides a bundled material of the same name.

Loading is deliberately lenient about completeness (a missing source or valid
range still loads), so that the checker can report every problem at once; it
only refuses files it cannot interpret (unknown model, a source key that is
not defined, wrong structure).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from cjcmaterials.models import MODELS

# The folder with the bundled material files (and their table files).
LIBRARY_DIR = Path(__file__).resolve().parent / "library"

# The three kinds of identifier a source may have; every one can be looked up by a reader.
SOURCE_TYPES = ("doi", "isbn", "url")


# Author names in the docstring are not typos.
# noinspection SpellCheckingInspection
@dataclass(frozen=True)
class Source:
    """Where values come from.

    Attributes
    ----------
    key : str
        Short name the descriptions refer to, e.g. ``"alyabyeva2017"``.
    type : str
        ``"doi"``, ``"isbn"`` or ``"url"``.
    identifier : str
        The DOI (``10.xxxx/...``), ISBN or URL.
    citation : str
        Human-readable reference: authors, title, journal or book, year.
    location : str
        Where in the source the values are (table, equation, page).
    valid_range_thz : tuple of (min, max)
        Frequency intervals [THz] the source's values apply to.
    checked : str
        ``"no"``, or who checked the values against the source and when
        (``"J. Doe, 2026-11-02"``).
    """

    key: str
    type: str
    identifier: str
    citation: str
    location: str
    valid_range_thz: tuple[tuple[float, float], ...]
    checked: str


@dataclass(frozen=True)
class Description:
    """One way of describing a material: a model, its parameters, a valid range and sources.

    Attributes
    ----------
    label : str
        Name of the description within its material, e.g. ``"thz"``.
    model : str
        Name of the model in ``cjcmaterials.MODELS``.
    parameters : dict
        Keyword arguments of the model function, without their sources; may
        contain ``electrons`` and ``holes`` blocks with the carrier-type
        dependent parameters (chosen with ``carrier_type`` at use time).
        Treat as read-only.
    valid_range_thz : tuple of (min, max)
        Frequency intervals [THz] in which the description is valid.
    sources : tuple of Source
        Sources of the description as a whole (and of every parameter without its own).
    parameter_sources : dict
        Parameter path (``"eps_inf"``, ``"electrons.mobility"``) -> its own sources.
    note : str
        Free text from the file, e.g. caveats.
    """

    label: str
    model: str
    parameters: dict[str, Any]
    valid_range_thz: tuple[tuple[float, float], ...]
    sources: tuple[Source, ...]
    parameter_sources: dict[str, tuple[Source, ...]] = field(default_factory=dict)
    note: str = ""


@dataclass(frozen=True)
class Material:
    """A material from the library: its descriptions and all the sources of its file.

    Attributes
    ----------
    name : str
        The material name, equal to the file name without ``.yaml``.
    descriptions : tuple of Description
        One or more descriptions, e.g. a THz model and an optical table.
    sources : tuple of Source
        Every source defined in the file.
    note : str
        Free text from the file.
    file : str
        The YAML file it was read from.
    """

    name: str
    descriptions: tuple[Description, ...]
    sources: tuple[Source, ...]
    note: str
    file: str


def _as_ranges(value: Any, where: str) -> tuple[tuple[float, float], ...]:
    """``[[min, max], ...]`` (or a single ``[min, max]``) as a tuple of float pairs; empty if missing."""
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError(f"{where}: valid_range_thz must be a list of [min, max] pairs, got {value!r}.")

    # A single [min, max] pair is accepted as a list of one interval.
    pairs = [value] if len(value) == 2 and not isinstance(value[0], Sequence) else value
    ranges = []
    for pair in pairs:
        if not isinstance(pair, Sequence) or isinstance(pair, str) or len(pair) != 2:
            raise ValueError(f"{where}: every valid range must be a [min, max] pair, got {pair!r}.")
        ranges.append((_as_number(pair[0], where), _as_number(pair[1], where)))
    return tuple(ranges)


def _as_number(value: Any, where: str) -> float:
    """A YAML number as float; PyYAML reads ``4e-2`` (no dot) as text, so numeric text is accepted too."""
    if isinstance(value, bool):
        raise ValueError(f"{where}: expected a number, got {value!r}.")
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{where}: expected a number, got {value!r}.") from None


def _as_keys(value: Any) -> tuple[str, ...]:
    """A ``source:`` entry (one key or a list of keys) as a tuple of keys."""
    if value is None:
        return ()
    return (str(value),) if isinstance(value, str) else tuple(str(key) for key in value)


def _parse_source(key: str, entry: Any, where: str) -> Source:
    """One entry of the file's ``sources:`` mapping."""
    if not isinstance(entry, Mapping):
        raise ValueError(f"{where}: source {key!r} must be a mapping with type, id, citation, ...")

    # YAML reads 'checked: no' as False and an empty entry as None; both mean not checked.
    checked = entry.get("checked")
    checked_text = "no" if checked is None or checked is False else str(checked).strip()
    return Source(
        key=str(key),
        type=str(entry.get("type", "")).strip().lower(),
        identifier=str(entry.get("id", "") or "").strip(),
        citation=" ".join(str(entry.get("citation", "") or "").split()),
        location=str(entry.get("location", "") or "").strip(),
        valid_range_thz=_as_ranges(entry.get("valid_range_thz"), f"{where}, source {key!r}"),
        checked=checked_text,
    )


def _split_sources(
    value: Any, path: str, folder: Path, sources: Mapping[str, Source], where: str,
    parameter_sources: dict[str, tuple[Source, ...]],
) -> Any:
    """Strip ``source`` entries from a parameter value (recording them by path) and convert numbers.

    ``{value: 9.61, source: key}`` becomes ``9.61``; a mapping with its own
    ``source`` (a mobility model) keeps its other entries; ``file`` entries
    become absolute paths, relative to the material file.
    """
    # A mapping either wraps a value with its source or is itself structured (mobility, a carrier block).
    if isinstance(value, Mapping):
        entries = dict(value)
        if "source" in entries:
            keys = _as_keys(entries.pop("source"))
            unknown = [key for key in keys if key not in sources]
            if unknown:
                raise ValueError(f"{where}: parameter {path!r} refers to undefined source(s) {unknown}.")
            parameter_sources[path] = tuple(sources[key] for key in keys)
        if set(entries) == {"value"}:
            return _split_sources(entries["value"], path, folder, sources, where, parameter_sources)
        return {key: _split_sources(item, f"{path}.{key}", folder, sources, where, parameter_sources)
                for key, item in entries.items()}

    # Lists (Lorentz oscillators) are converted item by item, sharing the list's path.
    if isinstance(value, list):
        return [_split_sources(item, path, folder, sources, where, parameter_sources) for item in value]

    # Table files are found next to the material file, wherever the script runs.
    name = path.rsplit(".", 1)[-1]
    if name == "file":
        return str((folder / str(value)).resolve())
    if name == "model":
        return str(value)
    return _as_number(value, f"{where}, parameter {path!r}")


def _parse_description(entry: Any, index: int, folder: Path, sources: Mapping[str, Source], where: str) -> Description:
    """One entry of the file's ``descriptions:`` list."""
    if not isinstance(entry, Mapping) or "label" not in entry or "model" not in entry:
        raise ValueError(f"{where}: description {index} must be a mapping with at least 'label' and 'model'.")
    label, model = str(entry["label"]), str(entry["model"])
    where = f"{where}, description {label!r}"
    if model not in MODELS:
        raise ValueError(f"{where}: unknown model {model!r}; known models: {sorted(MODELS)}.")

    # Description-level sources must exist in the file's sources mapping.
    keys = _as_keys(entry.get("sources"))
    unknown = [key for key in keys if key not in sources]
    if unknown:
        raise ValueError(f"{where}: refers to undefined source(s) {unknown}.")

    # Parameters without their sources, with the sources recorded per parameter path.
    raw_parameters = entry.get("parameters") or {}
    if not isinstance(raw_parameters, Mapping):
        raise ValueError(f"{where}: parameters must be a mapping.")
    parameter_sources: dict[str, tuple[Source, ...]] = {}
    parameters = {name: _split_sources(value, name, folder, sources, where, parameter_sources)
                  for name, value in raw_parameters.items()}
    return Description(
        label=label,
        model=model,
        parameters=parameters,
        valid_range_thz=_as_ranges(entry.get("valid_range_thz"), where),
        sources=tuple(sources[key] for key in keys),
        parameter_sources=parameter_sources,
        note=" ".join(str(entry.get("note", "") or "").split()),
    )


def load_material_file(file: str | Path) -> Material:
    """Read one material file (see the module docstring and README for the syntax).

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file cannot be interpreted; the message names the file and the entry.
    """
    path = Path(file).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Material file {path} not found.")
    with open(path, encoding="utf-8") as stream:
        content = yaml.safe_load(stream)
    where = str(path)
    if not isinstance(content, Mapping):
        raise ValueError(f"{where}: a material file must be a mapping with name, sources and descriptions.")

    # Sources first: descriptions and parameters refer to them by key.
    raw_sources = content.get("sources") or {}
    if not isinstance(raw_sources, Mapping):
        raise ValueError(f"{where}: 'sources' must be a mapping of key -> source.")
    sources = tuple(_parse_source(str(key), entry, where) for key, entry in raw_sources.items())
    sources_by_key = {source.key: source for source in sources}

    # Then every description, in file order.
    raw_descriptions = content.get("descriptions") or []
    if not isinstance(raw_descriptions, list) or not raw_descriptions:
        raise ValueError(f"{where}: 'descriptions' must be a non-empty list.")
    descriptions = tuple(_parse_description(entry, index, path.parent, sources_by_key, where)
                         for index, entry in enumerate(raw_descriptions))
    return Material(
        name=str(content.get("name", path.stem)),
        descriptions=descriptions,
        sources=sources,
        note=" ".join(str(content.get("note", "") or "").split()),
        file=str(path),
    )


def _search_folders(folders: str | Path | Iterable[str | Path] | None) -> list[Path]:
    """The user's folders (in the given order) followed by the bundled library."""
    if folders is None:
        user_folders = []
    elif isinstance(folders, (str, Path)):
        user_folders = [Path(folders)]
    else:
        user_folders = [Path(folder) for folder in folders]

    # A misspelled folder should fail loudly, not silently fall back to the bundled material.
    for folder in user_folders:
        if not folder.expanduser().is_dir():
            raise FileNotFoundError(f"Material folder {folder} not found.")
    return [folder.expanduser().resolve() for folder in user_folders] + [LIBRARY_DIR]


def available_materials(folders: str | Path | Iterable[str | Path] | None = None) -> list[str]:
    """Names of all materials in the bundled library and in ``folders``, sorted."""
    # Every <name>.yaml in any searched folder is a material; duplicates count once.
    names = {path.stem for folder in _search_folders(folders) for path in folder.glob("*.yaml")}
    return sorted(names, key=lambda name: name.lower())


def get_material(name: str, folders: str | Path | Iterable[str | Path] | None = None) -> Material:
    """Load a material by name from ``folders`` (first) or the bundled library.

    Parameters
    ----------
    name : str
        Material name, the file name without ``.yaml`` (e.g. ``"InP"``).
    folders : path or list of paths, optional
        Your own folders with material files, searched in order before the
        bundled library: a file there overrides a bundled material of the same
        name, and new names extend the library.

    Raises
    ------
    KeyError
        If no folder has ``<name>.yaml``; the message lists the available names.
    """
    # The first folder that has the file wins.
    for folder in _search_folders(folders):
        path = folder / f"{name}.yaml"
        if path.is_file():
            return load_material_file(path)
    raise KeyError(f"Material {name!r} not found. Available: {', '.join(available_materials(folders))}.")
