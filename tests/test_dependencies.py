"""The package stays about materials: numpy and pyyaml only, no plotting, optics or fitting packages."""

import subprocess
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "src"


def test_package_imports_only_numpy_and_yaml():
    """Importing cjcmaterials loads no scipy, matplotlib, cjcplot, cjctmm or cjcfit (checked in a fresh interpreter)."""
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import cjcmaterials; "
            "print(','.join(m for m in ('scipy', 'matplotlib', 'cjcplot', 'cjctmm', 'cjcfit') if m in sys.modules))")
    loaded = subprocess.run([sys.executable, "-c", code, str(SOURCE)], capture_output=True, text=True, check=True)
    assert loaded.stdout.strip() == ""


def test_no_source_file_mentions_the_sibling_optics_or_fitting_packages():
    """No module of the package imports cjctmm or cjcfit, even lazily."""
    for path in (SOURCE / "cjcmaterials").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "import cjctmm" not in text and "import cjcfit" not in text, path
        assert "from cjctmm" not in text and "from cjcfit" not in text, path
