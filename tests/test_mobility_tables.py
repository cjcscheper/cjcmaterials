"""Caughey–Thomas mobility and tabulated n, kappa."""

import numpy as np
import pytest

from cjcmaterials import SPEED_OF_LIGHT, caughey_thomas_mobility, read_nk_table, tabulated_permittivity, tabulated_refractive_index

# Silicon electrons (Caughey & Thomas 1967) in SI units.
SILICON_ELECTRONS = dict(mu_min=0.0065, mu_max=0.1330, n_ref=8.5e22, alpha=0.72)

# A small table: n at 1, 2, 4 um and kappa at 1, 2 um only, in the refractiveindex.info format.
TABLE_TEXT = "# test table\nwl,n\n4.0,3.0\n1.0,3.6\n2.0,3.2\nwl,k\n1.0,0.2\n2.0,0.1\n"


def test_caughey_thomas_tends_to_mu_max_at_low_density():
    """N << n_ref: mu -> mu_max (phonon-limited)."""
    assert caughey_thomas_mobility(1e15, **SILICON_ELECTRONS) == pytest.approx(0.1330, rel=1e-4)


def test_caughey_thomas_tends_to_mu_min_at_high_density():
    """N >> n_ref: mu -> mu_min (impurity-limited)."""
    assert caughey_thomas_mobility(1e30, **SILICON_ELECTRONS) == pytest.approx(0.0065, rel=1e-3)


def test_caughey_thomas_is_the_midpoint_at_n_ref():
    """mu(n_ref) = (mu_min + mu_max) / 2 for any alpha."""
    for alpha in (0.4, 1.0, 2.2):
        parameters = {**SILICON_ELECTRONS, "alpha": alpha}
        assert caughey_thomas_mobility(8.5e22, **parameters) == pytest.approx((0.0065 + 0.1330) / 2)


def test_caughey_thomas_falls_monotonically_and_keeps_shape():
    """The mobility decreases with density, element by element."""
    mobility = caughey_thomas_mobility(np.geomspace(1e18, 1e27, 50), **SILICON_ELECTRONS)
    assert mobility.shape == (50,)
    assert np.all(np.diff(mobility) < 0)


def test_caughey_thomas_rejects_unphysical_parameters():
    """mu_min > mu_max, n_ref <= 0 and a negative density are errors."""
    with pytest.raises(ValueError, match="mu_min <= mu_max"):
        caughey_thomas_mobility(1e22, mu_min=0.2, mu_max=0.1, n_ref=1e23, alpha=0.7)
    with pytest.raises(ValueError, match="n_ref > 0"):
        caughey_thomas_mobility(1e22, mu_min=0.0, mu_max=0.1, n_ref=0.0, alpha=0.7)
    with pytest.raises(ValueError, match=">= 0"):
        caughey_thomas_mobility(-1.0, **SILICON_ELECTRONS)


def test_table_is_read_in_increasing_frequency(tmp_path):
    """Rows in any wavelength order come back sorted by frequency f = c / lambda."""
    path = tmp_path / "table.csv"
    path.write_text(TABLE_TEXT, encoding="utf-8")
    table = read_nk_table(path)
    np.testing.assert_allclose(table.n_freq, SPEED_OF_LIGHT / (np.array([4.0, 2.0, 1.0]) * 1e-6))
    np.testing.assert_allclose(table.n, [3.0, 3.2, 3.6])
    np.testing.assert_allclose(table.kappa, [0.1, 0.2])


def test_interpolation_returns_the_table_values_at_the_table_points(tmp_path):
    """At 1 um and 2 um the index is exactly the tabulated n + i kappa, and eps its square."""
    path = tmp_path / "table.csv"
    path.write_text(TABLE_TEXT, encoding="utf-8")
    omega = 2 * np.pi * SPEED_OF_LIGHT / (np.array([1.0, 2.0]) * 1e-6)
    np.testing.assert_allclose(tabulated_refractive_index(omega, file=path), [3.6 + 0.2j, 3.2 + 0.1j])
    np.testing.assert_allclose(tabulated_permittivity(omega, file=path), [(3.6 + 0.2j) ** 2, (3.2 + 0.1j) ** 2])


def test_interpolation_is_linear_in_frequency_and_nan_outside(tmp_path):
    """Halfway in frequency between two points gives the mean; where kappa has no data the result is NaN."""
    path = tmp_path / "table.csv"
    path.write_text(TABLE_TEXT, encoding="utf-8")
    f1, f2 = SPEED_OF_LIGHT / 1e-6, SPEED_OF_LIGHT / 2e-6
    halfway = tabulated_refractive_index(2 * np.pi * (f1 + f2) / 2, file=path)
    assert halfway == pytest.approx(3.4 + 0.15j)
    # 3 um has n (between 2 and 4 um) but no kappa; 0.5 um has neither.
    beyond = tabulated_refractive_index(2 * np.pi * SPEED_OF_LIGHT / np.array([3e-6, 0.5e-6]), file=path)
    assert np.isfinite(beyond[0].real) and np.isnan(beyond[0].imag)
    assert np.isnan(beyond[1].real) and np.isnan(beyond[1].imag)


def test_table_without_kappa_block_is_an_error(tmp_path):
    """A table needs both blocks; the message names the missing one."""
    path = tmp_path / "only_n.csv"
    path.write_text("wl,n\n1.0,3.0\n2.0,2.9\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no 'wl,k' block"):
        read_nk_table(path)


def test_table_with_a_bad_row_names_the_line(tmp_path):
    """A row that is not 'wavelength_um,value' is reported with its line number."""
    path = tmp_path / "bad.csv"
    path.write_text("wl,n\n1.0,3.0\n2.0;2.9\nwl,k\n1.0,0.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 3"):
        read_nk_table(path)
