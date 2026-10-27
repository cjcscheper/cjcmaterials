"""Command line check of a material library: are the files complete, sourced and physical?

Usage::

    python -m cjcmaterials.check_library [folder ...] [--overview PATH] [--write-overview]
                                         [--online] [--require-checked]

This file is only the terminal front end. The rules themselves live in
:func:`cjcmaterials.check_library` (module ``checker``), which you can also call
from Python or a test. Run it after adding or editing a material file, before a
release, and in CI.

What is checked
    Without folder arguments the bundled library (``src/cjcmaterials/library``)
    is checked; with folders, every ``*.yaml`` in them (e.g. your own library).
    The rules come in groups, reported in this order:

    - loading: every file reads as a material.
    - completeness: the name matches the file name, description labels are
      unique, every description has sources and a ``valid_range_thz``, every
      source has a known type (doi/isbn/url), a citation, a location, a range
      and a ``checked`` field (``no`` or ``<who>, <YYYY-MM-DD>``), and no
      source is defined without being used.
    - identifiers: DOIs, ISBNs (check digit included) and URLs are well formed.
    - valid ranges: every range has 0 < min < max; a description stays inside
      the ranges of all its sources and, for an n,k table, inside the
      frequencies where the table has both n and kappa.
    - physical sanity: known parameters have physical signs, and each
      description, evaluated over its own valid range (at test carrier
      densities and for each carrier type it defines), gives a finite n,
      kappa >= 0, and a positive plasma frequency, mobility and scattering time.
    - overview: ``LIBRARY.md`` matches what the library would generate now.
    - online (only with ``--online``): every DOI resolves at doi.org and its
      registered first author, year and title match the citation; every URL
      responds. Needs internet; without it this group is skipped.

What is printed
    The materials checked, then each group's problems, then the to-do list of
    sources whose ``checked`` is still ``no``: values nobody has yet compared
    with the original paper or book. A last line gives PASSED or FAILED.

Options
    ``--overview PATH``   the LIBRARY.md to compare (default: the repository's
                          one, and only for the bundled library).
    ``--write-overview``  regenerate that LIBRARY.md first, then check.
    ``--online``          add the online group.
    ``--require-checked`` also fail while any source is still ``checked: no``.

Exit code
    0 when no rule finds a problem, 1 otherwise, so scripts and CI can use it.
    Unchecked sources alone do not fail the check unless ``--require-checked``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cjcmaterials.checker import GROUPS, check_library, default_overview_path, library_overview


def main(argv: list[str] | None = None) -> int:
    """Run the check from the command line; returns the exit code (0 passed, 1 failed)."""
    parser = argparse.ArgumentParser(prog="python -m cjcmaterials.check_library",
                                     description="Check a cjcmaterials material library and its sources.")
    parser.add_argument("folders", nargs="*", help="folders with material files (default: the bundled library)")
    parser.add_argument("--overview", type=Path, default=None,
                        help="LIBRARY.md to compare or write (default: the repository's, for the bundled library)")
    parser.add_argument("--write-overview", action="store_true", help="regenerate the overview before checking")
    parser.add_argument("--online", action="store_true", help="also resolve DOIs (and compare their metadata) and URLs")
    parser.add_argument("--require-checked", action="store_true", help="fail while any source has 'checked: no'")
    arguments = parser.parse_args(argv)
    folders = arguments.folders or None

    # Author names with accents must not crash a console with a narrow code page.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    # The overview to write or compare: the given one, or the repository's for the bundled library.
    overview_path = arguments.overview or (default_overview_path() if folders is None else None)
    if arguments.write_overview:
        if overview_path is None:
            parser.error("--write-overview needs --overview PATH here (no repository LIBRARY.md found).")
        overview_path.write_text(library_overview(folders) + "\n", encoding="utf-8", newline="\n")
        print(f"Wrote {overview_path}.")

    # Run every rule, then report group by group.
    result = check_library(folders, overview_path=overview_path, online=arguments.online,
                           require_checked=arguments.require_checked)
    print(f"Checked {len(result.materials)} materials: {', '.join(result.materials)}.")
    for group in GROUPS:
        messages = result.problems.get(group, ())
        if messages:
            print(f"\n[{group}] {len(messages)} problem{'s' if len(messages) > 1 else ''}")
            for message in messages:
                print(f"  - {message}")
    if not arguments.online:
        print("\n[online] not run (add --online to resolve DOIs and URLs).")

    # The to-do list for a person: sources nobody has compared with the original yet.
    if result.unchecked_sources:
        print(f"\nSources still to be checked by a person ({len(result.unchecked_sources)}):")
        for line in result.unchecked_sources:
            print(f"  - {line}")

    # One closing line with the verdict, and the exit code for scripts and CI.
    problem_count = sum(len(messages) for messages in result.problems.values())
    verdict = "PASSED" if result.passed else "FAILED"
    print(f"\n{verdict}: {problem_count} problem(s), {len(result.unchecked_sources)} source(s) not yet checked.")
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
