"""The bundled library, own folders, description selection and use-time inputs."""

import warnings
from pathlib import Path

import numpy as np
import pytest

from cjcmaterials import (
    ELECTRON_MASS,
    ELEMENTARY_CHARGE,
    LIBRARY_DIR,
    REDUCED_PLANCK_CONSTANT,
    SPEED_OF_LIGHT,
    VACUUM_PERMITTIVITY,
    available_materials,
    conductivity,
    get_material,
    load_material_file,
    permittivity,
    refractive_index,
    select_description,
)

from conftest import GOOD_MATERIAL, write_material

OWN_LIBRARY = Path(__file__).resolve().parent / "data" / "own_library"

# Every material of optpumpthz (n- and p-type variants merged), the two new tabulated ones and the
# Rakic (1998) Lorentz-Drude metals.
BUNDLED_MATERIALS = ["air", "Al", "Be", "Cr", "GaAs", "GaN", "Graphene", "In053Ga047As", "InP", "Ni", "Pd", "Pt",
                     "Si", "SiN", "SiO2", "Ti", "W"]

# Rakic et al. (1998) in eV: Table 1 (omega_p) and Table 2 (f_0, Gamma_0, then f_k, Gamma_k, omega_k).
RAKIC_1998_LD = {
    "Al": (14.98, 0.523, 0.047, [(0.227, 0.333, 0.162), (0.050, 0.312, 1.544), (0.166, 1.351, 1.808),
                                 (0.030, 3.382, 3.473)]),
    "Be": (18.51, 0.084, 0.035, [(0.031, 1.664, 0.100), (0.140, 3.395, 1.032), (0.530, 4.454, 3.183),
                                 (0.130, 1.802, 4.604)]),
    "Cr": (10.75, 0.168, 0.047, [(0.151, 3.175, 0.121), (0.150, 1.305, 0.543), (1.149, 2.676, 1.970),
                                 (0.825, 1.335, 8.775)]),
    "Ni": (15.92, 0.096, 0.048, [(0.100, 4.511, 0.174), (0.135, 1.334, 0.582), (0.106, 2.178, 1.597),
                                 (0.729, 6.292, 6.089)]),
    "Pd": (9.72, 0.330, 0.008, [(0.649, 2.950, 0.336), (0.121, 0.555, 0.501), (0.638, 4.621, 1.659),
                                (0.453, 3.236, 5.715)]),
    "Pt": (9.59, 0.333, 0.080, [(0.191, 0.517, 0.780), (0.659, 1.838, 1.314), (0.547, 3.668, 3.141),
                                (3.576, 8.517, 9.249)]),
    "Ti": (7.29, 0.148, 0.082, [(0.899, 2.276, 0.777), (0.393, 2.518, 1.545), (0.187, 1.663, 2.509),
                                (0.001, 1.762, 19.43)]),
    "W": (13.22, 0.206, 0.064, [(0.054, 0.530, 1.004), (0.166, 1.281, 1.917), (0.706, 3.332, 3.580),
                                (2.590, 5.836, 7.498)]),
}


def thz(*freq_thz):
    """Angular frequencies [rad/s] of frequencies given in THz."""
    return 2 * np.pi * np.array(freq_thz) * 1e12


def test_every_bundled_material_loads_with_sources_and_ranges():
    """All files load; every description has a source and a valid range; the list is complete."""
    assert available_materials() == sorted(BUNDLED_MATERIALS, key=str.lower)
    for name in available_materials():
        material = get_material(name)
        assert material.name == name
        for description in material.descriptions:
            assert description.sources, (name, description.label)
            assert description.valid_range_thz, (name, description.label)


def test_bundled_tables_ship_next_to_their_material_files():
    """Every table a description refers to exists in the package's library folder."""
    for name in available_materials():
        for description in get_material(name).descriptions:
            if "file" in description.parameters:
                assert Path(description.parameters["file"]).parent == LIBRARY_DIR
                assert Path(description.parameters["file"]).is_file()


def test_parameter_sources_are_kept_by_path():
    """{value, source} entries load as plain values, with the source recorded under the parameter path."""
    description = get_material("InP").descriptions[0]
    assert description.parameters["eps_inf"] == 9.61
    assert description.parameter_sources["eps_inf"][0].key == "levinshtein1996"
    assert description.parameter_sources["electrons.mobility"][0].key == "sotoodeh2000"
    assert description.parameters["electrons"]["mobility"]["model"] == "caughey_thomas"


def test_description_is_chosen_by_frequency():
    """Frequencies below the table pick the THz description, optical ones the table."""
    material = get_material("Si")
    assert select_description(material, thz(0.2, 0.9)).label == "thz"
    assert select_description(material, thz(375.0)).label == "optical"


def test_explicit_description_and_unknown_label():
    """description='<label>' wins regardless of frequency; an unknown label lists the real ones."""
    material = get_material("Si")
    assert select_description(material, thz(1.0), description="optical").label == "optical"
    with pytest.raises(ValueError, match=r"no description 'uv'; it has \['thz', 'optical'\]"):
        select_description(material, thz(1.0), description="uv")


def test_no_covering_description_is_an_error_naming_all_ranges():
    """Frequencies that no single description covers raise, listing every description and its range."""
    with pytest.raises(ValueError, match=r"No description of Si covers all of 0.5-10 THz.*'thz' \(drude_lorentz, "
                                         r"0.1-4.5 THz\).*'optical' \(tabulated, 0.97-9670 THz\)"):
        refractive_index(get_material("Si"), thz(0.5, 10.0))


def test_overlapping_descriptions_are_an_error(tmp_path):
    """Two descriptions that both cover the frequencies raise instead of choosing silently."""
    folder = tmp_path / "overlap"
    write_material(folder, GOOD_MATERIAL.replace("valid_range_thz: [[20, 30]]", "valid_range_thz: [[5, 30]]"))
    with pytest.raises(ValueError, match=r"Several descriptions of Testium cover 6-8 THz: 'thz' \(0.1-10 THz\); "
                                         r"'ir' \(5-30 THz\)"):
        permittivity(get_material("Testium", folders=folder), thz(6.0, 8.0))


def test_silicon_thz_model_and_table_overlap_between_097_and_45_thz():
    """At 2 THz both Si descriptions apply, so the choice is explicit; each then works without a warning."""
    material = get_material("Si")
    with pytest.raises(ValueError, match=r"Several descriptions of Si cover 2-2 THz: 'thz' \(0.1-4.5 THz\); "
                                         r"'optical' \(0.97-9670 THz\)"):
        refractive_index(material, thz(2.0))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        model = refractive_index(material, thz(2.0), description="thz")
        table = refractive_index(material, thz(2.0), description="optical")
    # Both give the undoped index of high-resistivity silicon, n = 3.42, to within 0.01.
    assert model.real == pytest.approx(3.42, abs=0.01) and table.real == pytest.approx(3.42, abs=0.01)


def test_frequencies_outside_the_chosen_range_warn_with_material_range_and_source():
    """An explicitly chosen description evaluated outside its range warns, naming all four."""
    with pytest.warns(UserWarning, match=r"Si, description 'thz': 1 of 2 frequencies \(8-8 THz\) lie outside its "
                                         r"valid range \(0.1-4.5 THz\)\. Source: J\. Dai"):
        refractive_index(get_material("Si"), thz(1.0, 8.0), description="thz")


def test_tabulated_material_warns_and_gives_nan_beyond_its_table():
    """GaAs infrared below its range warns; below the table (0.750 THz) n and kappa are NaN, not extrapolated."""
    with pytest.warns(UserWarning, match="GaAs, description 'infrared'"):
        index = refractive_index(get_material("GaAs"), thz(0.5, 2.0), description="infrared")
    assert np.isnan(index[0].real) and np.isnan(index[0].imag) and np.isfinite(index[1])


def test_gaas_phonon_gives_the_franta_static_permittivity_and_thz_index():
    """Franta's f_TO, f_LO, eps_inf and gamma give eps_s = 12.857 (LST), n = 3.590 and kappa = 2.8e-4 at 1 THz."""
    material = get_material("GaAs")
    # At 0.1 THz the phonon adds S (f/f_TO)^2 ~ 3e-4 to eps_s, inside the tolerance.
    assert permittivity(material, thz(0.1), description="thz").real == pytest.approx(12.857, abs=0.001)
    index = refractive_index(material, thz(1.0), description="thz")
    assert index.real == pytest.approx(3.590, abs=0.001)
    # A factor 2 pi wrong in gamma would show here as kappa 2 pi times off.
    assert index.imag == pytest.approx(2.8e-4, rel=0.01)


def test_gaas_phonon_follows_the_franta_table_up_to_75_thz_and_has_its_reststrahlen_band():
    """n within 0.5 % of Franta's full model at 0.76-7.5 THz; eps' < 0 between f_TO and f_LO, > 0 below."""
    material = get_material("GaAs")
    omega = thz(*np.geomspace(0.76, 7.5, 200))
    model = refractive_index(material, omega, description="thz")
    table = refractive_index(material, omega, description="infrared")
    np.testing.assert_allclose(model.real, table.real, rtol=0.005)
    # With the damping the zero crossings lie 0.002 THz inside f_TO = 8.0337 and f_LO = 8.7361 THz.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        band = permittivity(material, thz(*np.linspace(8.0337 + 0.002, 8.7361 - 0.002, 200)), description="thz")
        below = permittivity(material, thz(*np.linspace(0.1, 8.0337, 200)), description="thz")
    assert np.all(band.real < 0) and np.all(below.real > 0)


def test_gaas_visible_range_continues_the_franta_table():
    """Above the gap Papatryfonos' table absorbs (kappa > 0) and meets Franta's at 334.8 THz within 2 %."""
    material = get_material("GaAs")
    assert select_description(material, thz(500.0)).label == "optical"
    assert refractive_index(material, thz(500.0)).imag > 0.1
    below = refractive_index(material, thz(334.8), description="infrared")
    above = refractive_index(material, thz(334.8), description="optical")
    assert above.real == pytest.approx(below.real, rel=0.02)


def test_undoped_inp_needs_no_carrier_inputs():
    """Without carrier inputs InP is undoped: n = sqrt(eps_static) ~ 3.54 at 1 THz, below the phonon."""
    index = refractive_index(get_material("InP"), thz(1.0))
    assert index.real == pytest.approx(3.54, abs=0.01)
    assert 0 < index.imag < 0.01


def test_carrier_type_chooses_electron_or_hole_parameters():
    """Electrons (light, mobile) change the THz index of InP far more than holes at the same density."""
    material = get_material("InP")
    undoped = refractive_index(material, thz(1.0))
    electrons = refractive_index(material, thz(1.0), carrier_density=1e23, carrier_type="n")
    holes = refractive_index(material, thz(1.0), carrier_density=1e23, carrier_type="p")
    assert abs(electrons - undoped) > 5 * abs(holes - undoped)


def test_carrier_density_without_type_or_on_a_carrier_free_model_is_an_error():
    """A density needs a type when the description has electron and hole parameters; SiO2 has no carriers."""
    with pytest.raises(ValueError, match="give carrier_type='n' or 'p'"):
        refractive_index(get_material("InP"), thz(1.0), carrier_density=1e22)
    with pytest.raises(ValueError, match="has no free carriers"):
        refractive_index(get_material("SiO2"), thz(1.0), carrier_density=1e22)
    with pytest.raises(ValueError, match="carrier_type must be 'n'"):
        refractive_index(get_material("InP"), thz(1.0), carrier_density=1e22, carrier_type="electron")


def test_mobility_model_is_evaluated_at_the_use_time_density(good_library):
    """sigma_DC = N e mu(N) with mu from the file's Caughey-Thomas model, at the density given at use time."""
    material = get_material("Testium", folders=good_library)
    density = 1e23
    omega = thz(0.1)[0]
    sigma = conductivity(material, omega, carrier_density=density, carrier_type="n")
    # mu(n_ref) is the midpoint (0.01 + 0.5) / 2; the background eps_inf adds to Im sigma only.
    mobility = 0.255
    tau = mobility * 0.1 * ELECTRON_MASS / ELEMENTARY_CHARGE
    assert sigma.real == pytest.approx(density * ELEMENTARY_CHARGE * mobility / (1 + (omega * tau) ** 2), rel=1e-9)


def test_carrier_density_array_gives_one_row_per_density():
    """K densities give shape (K, M), and each row equals the call with that one density."""
    material, omega = get_material("Si"), thz(0.2, 0.5, 0.9)
    densities = np.array([1e21, 1e22, 1e23])
    eps = permittivity(material, omega, carrier_density=densities, carrier_type="p")
    assert eps.shape == (3, 3)
    np.testing.assert_allclose(eps[1], permittivity(material, omega, carrier_density=1e22, carrier_type="p"))


def test_metal_carrier_density_from_the_file_and_overridden_at_use_time():
    """Al takes N = 8.51e28 m^-3 from its file; without carriers only the Lorentz oscillators remain."""
    material = get_material("Al")
    omega = thz(1.3)
    with_carriers = conductivity(material, omega)
    without_carriers = conductivity(material, omega, carrier_density=0.0)
    # Bound and free charges add, so the difference is the Drude conductivity sigma_DC / (1 - i omega tau).
    tau = 1.400451e-14
    sigma_dc = 8.51159e28 * ELEMENTARY_CHARGE**2 * tau / ELECTRON_MASS
    assert with_carriers - without_carriers == pytest.approx(sigma_dc / (1 - 1j * omega[0] * tau), rel=1e-9)


@pytest.mark.parametrize("name", sorted(RAKIC_1998_LD))
def test_lorentz_drude_metals_match_rakic_formula_in_electronvolt(name):
    """The SI parameters of each metal reproduce Rakic's Lorentz-Drude formula over its range, written in eV."""
    omega_p, f_0, gamma_0, oscillators_ev = RAKIC_1998_LD[name]
    material = get_material(name)
    (low_thz, high_thz), = select_description(material, thz(100.0), description="lorentz_drude").valid_range_thz
    omega = thz(*np.geomspace(low_thz * 1.001, high_thz * 0.999, 50))
    energy_ev = REDUCED_PLANCK_CONSTANT * omega / ELEMENTARY_CHARGE
    # eps = 1 - f_0 omega_p^2 / (w (w + i Gamma_0)) + sum f_k omega_p^2 / (w_k^2 - w^2 - i w Gamma_k).
    expected = 1 - f_0 * omega_p**2 / (energy_ev * (energy_ev + 1j * gamma_0))
    for strength, damping, resonance in oscillators_ev:
        expected = expected + strength * omega_p**2 / (resonance**2 - energy_ev**2 - 1j * energy_ev * damping)
    eps = permittivity(material, omega, description="lorentz_drude")
    np.testing.assert_allclose(eps, expected, rtol=1e-4)


def test_aluminium_table_values_and_overlap_with_the_lorentz_drude_description():
    """The Rakic table gives its own rows (n = 1.366, k = 7.4052 at 619.93 nm); at 3 THz both descriptions apply."""
    material = get_material("Al")
    omega = 2 * np.pi * SPEED_OF_LIGHT / 0.61993e-6
    assert refractive_index(material, omega, description="optical") == pytest.approx(1.366 + 7.4052j, rel=1e-6)
    with pytest.raises(ValueError, match="Several descriptions of Al cover"):
        refractive_index(material, thz(3.0))
    # The 1998 model and the 1995 table of the same group agree to within 5 % where they overlap.
    model = refractive_index(material, thz(3.0), description="lorentz_drude")
    table = refractive_index(material, thz(3.0), description="optical")
    assert abs(model - table) / abs(table) < 0.05


def test_graphene_needs_a_sheet_density():
    """The graphene description has no density in its file; leaving it out is a clear error."""
    with pytest.raises(ValueError, match="needs a carrier_density"):
        refractive_index(get_material("Graphene"), thz(1.0))
    index = refractive_index(get_material("Graphene"), thz(1.0), carrier_density=1e16)
    assert index.imag > 0


def test_conductivity_is_minus_i_omega_eps0_times_eps_minus_one():
    """The total conductivity follows from eps for every description, tables included."""
    material, omega = get_material("GaAs"), thz(100.0)
    eps = permittivity(material, omega)
    assert conductivity(material, omega) == pytest.approx(-1j * omega * VACUUM_PERMITTIVITY * (eps - 1.0))


def test_own_folder_extends_and_overrides_the_library(tmp_path):
    """A user folder adds new materials and, for the same name, replaces the bundled one."""
    folder = tmp_path / "mine"
    write_material(folder, GOOD_MATERIAL.replace("name: Testium", "name: InP"), name="InP")
    assert get_material("test", folders=OWN_LIBRARY).descriptions[0].parameters["n"] == 1.5
    assert "test" in available_materials(folders=[OWN_LIBRARY, folder])
    assert get_material("InP", folders=folder).descriptions[0].label == "thz"
    assert get_material("InP", folders=folder).file == str((folder / "InP.yaml").resolve())
    assert get_material("InP").file == str(LIBRARY_DIR / "InP.yaml")


def test_unknown_material_and_missing_folder_are_clear_errors(tmp_path):
    """An unknown name lists the available ones; a misspelled folder is not silently ignored."""
    with pytest.raises(KeyError, match="Material 'Unobtainium' not found. Available: air, Al"):
        get_material("Unobtainium")
    with pytest.raises(FileNotFoundError, match="Material folder"):
        get_material("InP", folders=tmp_path / "does_not_exist")


def test_loading_refuses_unknown_models_and_undefined_source_keys(tmp_path):
    """Files that cannot be interpreted fail with the file and entry named."""
    path = write_material(tmp_path, GOOD_MATERIAL.replace("model: constant", "model: magic"))
    with pytest.raises(ValueError, match="unknown model 'magic'"):
        load_material_file(path)
    path = write_material(tmp_path, GOOD_MATERIAL.replace("source: paper}", "source: typo}"))
    with pytest.raises(ValueError, match=r"parameter 'electrons.mobility' refers to undefined source\(s\) \['typo'\]"):
        load_material_file(path)
