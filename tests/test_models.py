"""Model functions against analytic values that can be checked by hand."""

import numpy as np
import pytest

from cjcmaterials import (
    ELECTRON_MASS,
    ELEMENTARY_CHARGE,
    REDUCED_PLANCK_CONSTANT,
    VACUUM_PERMITTIVITY,
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

# One resonance at 10 THz used by the Lorentz tests: strength 2, width 0.5 THz (angular).
OSCILLATOR = {"strength": 2.0, "resonance_omega": 2 * np.pi * 10e12, "damping": 2 * np.pi * 0.5e12}


def test_constant_permittivity_is_index_squared_everywhere():
    """n = 1.5 + 0.1i gives eps = 2.24 + 0.3i at every frequency, in the shape of omega."""
    eps = constant_permittivity(np.array([1e12, 1e15]), n=1.5, kappa=0.1)
    assert eps.shape == (2,)
    np.testing.assert_allclose(eps, 2.24 + 0.3j)


def test_drude_dc_conductivity_is_n_e_mu():
    """N = 1e24 m^-3 and mu = 0.1 m^2/Vs give sigma_DC = N e mu = 1.602e4 S/m (omega << 1/tau)."""
    sigma = drude_conductivity(1.0, carrier_density=1e24, effective_mass_ratio=0.1, mobility=0.1)
    assert sigma.real == pytest.approx(1.602176634e4, rel=1e-9)
    assert abs(sigma.imag) < 1e-6 * sigma.real


def test_scattering_time_from_mobility_is_mu_m_over_e():
    """mu = 0.1 m^2/Vs and m* = 0.1 m_e give tau = 0.1 * 0.1 m_e / e = 5.686e-14 s."""
    tau = scattering_time_from_mobility(0.1, effective_mass_ratio=0.1)
    assert tau == pytest.approx(0.01 * ELECTRON_MASS / ELEMENTARY_CHARGE)
    assert tau == pytest.approx(5.686e-14, rel=1e-3)


def test_drude_real_part_halves_and_imaginary_part_peaks_at_one_over_tau():
    """At omega = 1/tau, sigma' = sigma_DC / 2 and sigma'' = sigma_DC / 2 is its maximum."""
    tau = 1e-13
    omega = np.geomspace(1e11, 1e15, 4001)
    sigma = drude_conductivity(omega, carrier_density=1e23, effective_mass_ratio=0.2, scattering_time=tau)
    sigma_dc = 1e23 * ELEMENTARY_CHARGE**2 * tau / (0.2 * ELECTRON_MASS)
    at_rate = drude_conductivity(1 / tau, carrier_density=1e23, effective_mass_ratio=0.2, scattering_time=tau)
    np.testing.assert_allclose(at_rate, sigma_dc * (0.5 + 0.5j), rtol=1e-12)
    # The grid is log-spaced with 1000 points per decade, so the peak lies within 0.25 % of 1/tau.
    assert omega[np.argmax(sigma.imag)] * tau == pytest.approx(1.0, rel=2.5e-3)


def test_plasma_frequency_formula_and_zero_crossing():
    """omega_p^2 = N e^2 / (eps0 eps_inf m*), and an undamped Drude eps crosses zero exactly there."""
    density, mass, eps_inf = 1e24, 0.067, 12.0
    omega_p = plasma_omega(density, effective_mass_ratio=mass, eps_inf=eps_inf)
    expected = np.sqrt(density * ELEMENTARY_CHARGE**2 / (VACUUM_PERMITTIVITY * eps_inf * mass * ELECTRON_MASS))
    assert omega_p == pytest.approx(expected)
    # A very long scattering time makes the damping negligible: eps = eps_inf (1 - omega_p^2 / omega^2).
    eps = drude_permittivity(omega_p, eps_inf=eps_inf, effective_mass_ratio=mass, carrier_density=density,
                             scattering_time=1e-6)
    assert abs(eps.real) < 1e-9 * eps_inf


def test_drude_permittivity_tends_to_eps_inf_far_above_plasma_frequency():
    """For omega = 1000 omega_p the carriers no longer follow: eps -> eps_inf within 1e-5."""
    omega_p = plasma_omega(1e23, effective_mass_ratio=0.1, eps_inf=10.0)
    eps = drude_permittivity(1000 * omega_p, eps_inf=10.0, effective_mass_ratio=0.1, carrier_density=1e23,
                             mobility=0.2)
    assert eps == pytest.approx(10.0, rel=1e-5)


def test_drude_without_carriers_is_eps_inf():
    """carrier_density = 0 (the default) leaves only the background."""
    eps = drude_permittivity(np.array([1e12, 1e13]), eps_inf=11.7, effective_mass_ratio=0.26, mobility=0.1)
    np.testing.assert_allclose(eps, 11.7)


def test_drude_smith_with_c_minus_one_suppresses_dc_conductivity():
    """c = -1 gives sigma(omega -> 0) = 0 (full backscattering); c = 0 is plain Drude."""
    common = dict(carrier_density=1e23, effective_mass_ratio=0.1, scattering_time=1e-13)
    assert abs(drude_conductivity(1.0, smith_c=-1.0, **common)) < 1e-9 * abs(drude_conductivity(1.0, **common))
    np.testing.assert_allclose(drude_conductivity(1e13, smith_c=0.0, **common), drude_conductivity(1e13, **common))


def test_drude_vectorises_over_carrier_densities():
    """K densities give shape (K, M), and each row equals the scalar call."""
    omega = np.array([1e12, 1e13, 1e14])
    densities = np.array([0.0, 1e22, 1e24])
    mobilities = np.array([0.5, 0.3, 0.1])
    sigma = drude_conductivity(omega, carrier_density=densities, effective_mass_ratio=0.1, mobility=mobilities)
    assert sigma.shape == (3, 3)
    for row, (density, mobility) in enumerate(zip(densities, mobilities)):
        np.testing.assert_allclose(sigma[row], drude_conductivity(omega, carrier_density=density,
                                                                  effective_mass_ratio=0.1, mobility=mobility))


def test_drude_rejects_ambiguous_or_unphysical_inputs():
    """Both or neither of mobility and scattering_time, a negative mass or density, and omega <= 0 are errors."""
    with pytest.raises(ValueError, match="exactly one of mobility"):
        drude_conductivity(1e12, carrier_density=1e22, effective_mass_ratio=0.1, mobility=0.1, scattering_time=1e-13)
    with pytest.raises(ValueError, match="exactly one of mobility"):
        drude_conductivity(1e12, carrier_density=1e22, effective_mass_ratio=0.1)
    with pytest.raises(ValueError, match="effective_mass_ratio"):
        drude_conductivity(1e12, carrier_density=1e22, effective_mass_ratio=-0.1, mobility=0.1)
    with pytest.raises(ValueError, match="carrier_density must be >= 0"):
        drude_conductivity(1e12, carrier_density=-1.0, effective_mass_ratio=0.1, mobility=0.1)
    with pytest.raises(ValueError, match="omega must be finite and > 0"):
        drude_conductivity(0.0, carrier_density=1e22, effective_mass_ratio=0.1, mobility=0.1)


def test_lorentz_static_permittivity_is_eps_inf_plus_strength():
    """eps(omega -> 0) = eps_inf + Delta eps = 3 + 2 = 5."""
    eps = lorentz_permittivity(1e6, eps_inf=3.0, oscillators=[OSCILLATOR])
    assert eps == pytest.approx(5.0, rel=1e-9)


def test_lorentz_absorption_peaks_at_the_resonance():
    """kappa = Im sqrt(eps) is largest near omega_0 = 2 pi 10 THz (within the grid step)."""
    omega = 2 * np.pi * np.linspace(5e12, 15e12, 2001)
    kappa = np.sqrt(lorentz_permittivity(omega, eps_inf=3.0, oscillators=[OSCILLATOR])).imag
    # kappa peaks slightly above omega_0 (where Re eps falls); within the 0.5 THz linewidth.
    assert abs(omega[np.argmax(kappa)] / (2 * np.pi) - 10e12) < 0.5e12
    eps_imag = lorentz_permittivity(omega, eps_inf=3.0, oscillators=[OSCILLATOR]).imag
    assert omega[np.argmax(eps_imag)] / (2 * np.pi) == pytest.approx(10e12, rel=1e-3)


def test_lorentz_dispersion_has_the_kramers_kronig_sign():
    """Below the resonance Re eps rises above its static value, above it falls below eps_inf; Im eps > 0."""
    eps = lorentz_permittivity(2 * np.pi * np.array([5e12, 9.5e12, 10.5e12, 20e12]), eps_inf=3.0,
                               oscillators=[OSCILLATOR])
    # Normal dispersion below the line (Re eps above its static value), anomalous across it, then below eps_inf.
    assert eps[0].real > 5.0 and eps[1].real > eps[0].real
    assert eps[2].real < 3.0 and eps[3].real < 3.0
    assert np.all(eps.imag > 0.0)


def test_lorentz_rejects_malformed_oscillators():
    """A missing key or a negative damping is a clear error."""
    with pytest.raises(ValueError, match="exactly the keys"):
        lorentz_permittivity(1e12, eps_inf=1.0, oscillators=[{"strength": 1.0, "resonance_omega": 1e13}])
    with pytest.raises(ValueError, match="damping >= 0"):
        lorentz_permittivity(1e12, eps_inf=1.0, oscillators=[{**OSCILLATOR, "damping": -1.0}])


def test_drude_lorentz_is_the_sum_with_one_background():
    """eps_DL = eps_Lorentz + eps_Drude - eps_inf: the background is counted once."""
    omega = 2 * np.pi * np.array([0.5e12, 3e12, 12e12])
    drude = dict(effective_mass_ratio=0.08, carrier_density=1e23, mobility=0.4)
    combined = drude_lorentz_permittivity(omega, eps_inf=9.6, oscillators=[OSCILLATOR], **drude)
    separate = (lorentz_permittivity(omega, eps_inf=9.6, oscillators=[OSCILLATOR])
                + drude_permittivity(omega, eps_inf=9.6, **drude) - 9.6)
    np.testing.assert_allclose(combined, separate, rtol=1e-12)


def test_graphene_dc_sheet_conductivity_is_n_e_mu_when_cold():
    """For k_B T << E_F and omega << Gamma the sheet conductivity is N e mu (Gamma from the mobility)."""
    density, mobility = 1e17, 0.2
    sigma = graphene_sheet_conductivity(2 * np.pi * 1e9, carrier_density=density, mobility=mobility, temperature=1.0)
    # The interband term adds ~e^2/(4 hbar) * small, well below 0.1 % here.
    assert sigma.real == pytest.approx(density * ELEMENTARY_CHARGE * mobility, rel=1e-3)


def test_graphene_absorbs_the_universal_value_far_above_the_pauli_edge():
    """For hbar omega >> 2 E_F, Re sigma -> e^2 / (4 hbar) = 6.08e-5 S (the 2.3 % absorption of graphene)."""
    sigma = graphene_sheet_conductivity(2 * np.pi * 2000e12, carrier_density=1e15, mobility=0.2, temperature=10.0)
    assert sigma.real == pytest.approx(ELEMENTARY_CHARGE**2 / (4 * REDUCED_PLANCK_CONSTANT), rel=1e-2)


def test_graphene_permittivity_spreads_the_sheet_over_its_thickness():
    """eps = eps_inf + i sigma_sheet / (eps0 omega d), and the carrier density must be > 0."""
    omega = 2 * np.pi * 1e12
    inputs = dict(carrier_density=1e16, mobility=0.3)
    sigma = graphene_sheet_conductivity(omega, **inputs)
    eps = graphene_sheet_permittivity(omega, thickness=0.34e-9, **inputs)
    assert eps == pytest.approx(1.0 + 1j * sigma / (VACUUM_PERMITTIVITY * omega * 0.34e-9))
    with pytest.raises(ValueError, match="carrier_density > 0"):
        graphene_sheet_conductivity(omega, carrier_density=0.0, mobility=0.3)
