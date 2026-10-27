"""The library checker: every rule fails on a deliberately broken small library."""

import shutil
from pathlib import Path

import pytest

import cjcmaterials.checker as checker
from cjcmaterials import LIBRARY_DIR, check_library, get_material, library_overview
from cjcmaterials.check_library import main
from cjcmaterials.checker import compare_citation, is_valid_doi, is_valid_isbn, is_valid_url

from conftest import GOOD_MATERIAL, write_material

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def broken(tmp_path, old, new, *, count=1):
    """A library folder with the good test material, ``old`` replaced by ``new``."""
    assert GOOD_MATERIAL.count(old) >= 1, f"test text {old!r} not found"
    folder = tmp_path / "broken"
    write_material(folder, GOOD_MATERIAL.replace(old, new, count))
    return folder


def problems_of(folder, group):
    """The messages of one rule group (empty tuple when it passed)."""
    return check_library(folder).problems.get(group, ())


def test_bundled_library_passes_every_offline_rule_and_overview_is_current():
    """The shipped YAML files pass, and LIBRARY.md is what --write-overview would write."""
    result = check_library(overview_path=REPOSITORY_ROOT / "LIBRARY.md")
    assert result.problems == {}
    assert result.passed
    assert len(result.materials) == 10


def test_material_template_loads_and_passes_every_offline_rule(tmp_path):
    """material_template.yaml, copied with its table into a folder as a user would, is a valid material."""
    folder = tmp_path / "own"
    folder.mkdir()
    shutil.copy(REPOSITORY_ROOT / "material_template.yaml", folder)
    shutil.copy(LIBRARY_DIR / "Si_Franta2017.csv", folder)
    material = get_material("material_template", folders=folder)
    assert [description.model for description in material.descriptions] == [
        "constant", "drude", "drude_lorentz", "tabulated"]
    result = check_library(folder)
    assert result.problems == {}
    assert result.passed


def test_every_library_file_points_to_the_template():
    """Each bundled file starts with the one-line header that names the template."""
    for path in sorted(LIBRARY_DIR.glob("*.yaml")):
        first_line = path.read_text(encoding="utf-8").splitlines()[0]
        assert "material_template.yaml" in first_line, path.name


def test_good_test_library_passes_and_lists_its_unchecked_source(good_library):
    """A complete library passes; the source with 'checked: no' is listed, the checked one is not."""
    result = check_library(good_library)
    assert result.passed and result.problems == {}
    assert len(result.unchecked_sources) == 1
    assert result.unchecked_sources[0].startswith("Testium: book (isbn 0-12-544420-6)")


def test_unchecked_sources_fail_only_on_request(good_library):
    """require_checked=True turns the to-do list into a failure."""
    assert not check_library(good_library, require_checked=True).passed


def test_missing_description_source_is_reported(tmp_path):
    """A description without sources fails completeness (and its source then counts as unused)."""
    folder = broken(tmp_path, "    sources: [book]\n    parameters:\n      n: 3.0", "    parameters:\n      n: 3.0")
    assert "Testium, description 'ir': no sources (add 'sources: [<key>]')." in problems_of(folder, "completeness")


def test_missing_source_fields_and_bad_type_are_reported(tmp_path):
    """A source needs a known type, an id, a citation, a location and a valid range."""
    folder = broken(tmp_path, "    type: isbn\n    id: 0-12-544420-6\n", "    type: arxiv\n")
    messages = problems_of(folder, "completeness")
    assert "Testium, source 'book': type 'arxiv' is not one of doi, isbn, url." in messages
    assert "Testium, source 'book': no id." in messages
    folder = broken(tmp_path, "    location: p. 1\n    valid_range_thz: [[0.1, 30]]\n", "")
    messages = problems_of(folder, "completeness")
    assert "Testium, source 'book': no location." in messages
    assert "Testium, source 'book': no valid_range_thz." in messages


def test_bad_checked_field_unused_source_and_name_mismatch_are_reported(tmp_path):
    """'checked: yes' says nothing about who and when; a source nobody uses and a wrong name are flagged."""
    folder = broken(tmp_path, 'checked: "C. Scheper, 2026-10-27"', "checked: yes")
    assert any("checked must be 'no' or '<who>, <YYYY-MM-DD>'" in m for m in problems_of(folder, "completeness"))
    folder = broken(tmp_path, "descriptions:", "  spare:\n    type: url\n    id: https://example.org\n"
                    "    citation: x\n    location: y\n    valid_range_thz: [[1, 2]]\n    checked: no\ndescriptions:")
    assert "Testium, source 'spare': defined but not used by any description or parameter." in problems_of(
        folder, "completeness")
    folder = broken(tmp_path, "name: Testium", "name: Other")
    assert "Testium.yaml: name 'Other' differs from the file name 'Testium'." in problems_of(folder, "completeness")


@pytest.mark.parametrize("old, new, expected", [
    ("id: 10.1063/1.372274", "id: 10.10/abc", "'10.10/abc' is not a DOI of the form 10.<registrant>/<suffix>."),
    ("id: 0-12-544420-6", "id: 0-12-544420-7", "'0-12-544420-7' is not an ISBN-10 or ISBN-13 with a correct check digit."),
])
def test_bad_identifiers_are_reported(tmp_path, old, new, expected):
    """A DOI without a 4-9 digit registrant and an ISBN with a wrong check digit fail the identifier rule."""
    folder = broken(tmp_path, old, new)
    assert any(message.endswith(expected) for message in problems_of(folder, "identifiers"))


def test_bad_url_is_reported(tmp_path):
    """A URL must be http(s) with a host."""
    folder = broken(tmp_path, "    type: isbn\n    id: 0-12-544420-6", "    type: url\n    id: ftp://example.org/x")
    assert any("is not an http(s) URL" in message for message in problems_of(folder, "identifiers"))


def test_identifier_syntax_functions():
    """Known-good and known-bad identifiers, including the ISBN-10 X check digit and ISBN-13."""
    assert is_valid_doi("10.1038/s41598-017-07164-1") and not is_valid_doi("doi:10.1038/x")
    assert is_valid_isbn("0-12-544420-6") and is_valid_isbn("978-0-12-544420-0")
    assert is_valid_isbn("0-8044-2957-X") and not is_valid_isbn("978-0-12-544420-4")
    assert is_valid_url("https://www.bipm.org/en/") and not is_valid_url("www.bipm.org")


@pytest.mark.parametrize("old, new, expected", [
    ("valid_range_thz: [[20, 30]]", "valid_range_thz: [[30, 20]]", "range [30, 20] THz must have 0 < min < max."),
    ("valid_range_thz: [[20, 30]]", "valid_range_thz: [[0, 30]]", "range [0, 30] THz must have 0 < min < max."),
])
def test_malformed_ranges_are_reported(tmp_path, old, new, expected):
    """Ranges need 0 < min < max."""
    folder = broken(tmp_path, old, new)
    assert any(message.endswith(expected) for message in problems_of(folder, "valid ranges"))


def test_description_beyond_its_source_range_is_reported(tmp_path):
    """The 'thz' description uses 'paper' (0.1-10 THz) for its mobility; extending it to 15 THz is flagged."""
    folder = broken(tmp_path, "valid_range_thz: [[0.1, 10]]\n    sources: [book]",
                    "valid_range_thz: [[0.1, 15]]\n    sources: [book]")
    assert ("Testium, description 'thz': its range (0.1-15 THz) extends beyond that of source 'paper' "
            "(0.1-10 THz).") in problems_of(folder, "valid ranges")


def test_tabulated_description_beyond_its_table_is_reported(tmp_path):
    """A table with data at 1-2 um (150-300 THz) cannot be valid at 100-300 THz; the sanity rule sees NaN too."""
    folder = tmp_path / "table_library"
    (folder).mkdir()
    (folder / "nk.csv").write_text("wl,n\n1.0,3.0\n2.0,3.1\nwl,k\n1.0,0.0\n2.0,0.0\n", encoding="utf-8")
    write_material(folder, GOOD_MATERIAL.replace(
        "    model: constant\n    valid_range_thz: [[20, 30]]", "    model: tabulated\n    valid_range_thz: [[100, 290]]"
    ).replace("      n: 3.0", "      file: nk.csv").replace("[[0.1, 30]]", "[[0.1, 300]]"))
    result = check_library(folder)
    assert any("extends beyond the table, which has n and kappa only at 149.9-299.8 THz"
               in message for message in result.problems["valid ranges"])
    assert any("not finite" in message for message in result.problems["physical sanity"])


def test_unphysical_parameters_are_reported(tmp_path):
    """A negative effective mass and a negative-strength (gain) constant index fail the sanity rule."""
    folder = broken(tmp_path, "effective_mass_ratio: 0.5", "effective_mass_ratio: -0.5")
    assert "Testium, description 'thz': holes.effective_mass_ratio = -0.5 must be > 0." in problems_of(
        folder, "physical sanity")
    folder = broken(tmp_path, "      n: 3.0", "      n: 3.0\n      kappa: -0.1")
    assert any("kappa = -0.1 must be >= 0" in message for message in problems_of(folder, "physical sanity"))


def test_unreadable_file_is_a_loading_problem(tmp_path):
    """A file the loader cannot interpret is reported under loading, and the others are still checked."""
    folder = broken(tmp_path, "model: constant", "model: magic")
    write_material(folder, "name: Other\n", name="Other")
    messages = problems_of(folder, "loading")
    assert any(message.startswith("Testium.yaml:") and "unknown model 'magic'" in message for message in messages)
    assert any(message.startswith("Other.yaml:") for message in messages)


def test_stale_or_missing_overview_is_reported(good_library, tmp_path):
    """LIBRARY.md must equal the generated overview; it starts with the 'Generated by' line."""
    overview = tmp_path / "LIBRARY.md"
    assert "does not exist" in check_library(good_library, overview_path=overview).problems["overview"][0]
    overview.write_text(library_overview(good_library), encoding="utf-8")
    assert check_library(good_library, overview_path=overview).passed
    assert overview.read_text(encoding="utf-8").splitlines()[0] == (
        "Generated by `python -m cjcmaterials.check_library --write-overview`; do not edit.")
    overview.write_text(library_overview(good_library).replace("Testium", "Oldium"), encoding="utf-8")
    assert "is out of date" in check_library(good_library, overview_path=overview).problems["overview"][0]


def test_citation_comparison_with_doi_metadata():
    """Matching metadata passes; another author, year or title is reported; accents and o-slash are tolerated."""
    paper = next(source for source in get_material("Graphene").sources if source.key == "boggild2017")
    # The registry spells the first author 'Bøggild', the citation 'Boggild'.
    good = {"title": "Mapping the electrical properties of large-area graphene", "first_author": "Bøggild",
            "year": 2017}
    assert compare_citation(paper, good) == []
    wrong = {"title": "Something else entirely about phonons", "first_author": "Smith", "year": 1999}
    messages = compare_citation(paper, wrong)
    assert len(messages) == 3 and "first author 'Smith'" in messages[0]


def test_online_check_uses_doi_metadata_and_urls(tmp_path, monkeypatch):
    """With network calls replaced: a DOI pointing at another paper and a dead URL are reported."""
    folder = broken(tmp_path, "    type: isbn\n    id: 0-12-544420-6", "    type: url\n    id: https://example.org/gone")
    monkeypatch.setattr(checker, "fetch_doi_metadata",
                        lambda doi, timeout: {"title": "A different paper", "first_author": "Jones", "year": 2001})
    monkeypatch.setattr(checker, "url_responds", lambda url, timeout: False)
    messages = check_library(folder, online=True).problems["online"]
    assert any("first author 'Jones' is not in the citation" in message for message in messages)
    assert "Testium, source 'book': https://example.org/gone does not respond." in messages


def test_command_line_exit_codes_and_overview_writing(good_library, tmp_path, capsys):
    """Exit 0 on a passing library, 1 on a broken one; --write-overview writes the file it then checks."""
    overview = tmp_path / "LIBRARY.md"
    assert main([str(good_library), "--overview", str(overview), "--write-overview"]) == 0
    assert overview.is_file()
    output = capsys.readouterr().out
    assert "Sources still to be checked by a person (1):" in output and "PASSED" in output
    folder = broken(tmp_path, "id: 10.1063/1.372274", "id: 10.10/abc")
    assert main([str(folder)]) == 1
    output = capsys.readouterr().out
    assert "[identifiers] 1 problem" in output and "FAILED" in output
