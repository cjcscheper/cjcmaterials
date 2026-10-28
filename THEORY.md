# Theory of the material models

This note explains what `cjcmaterials` computes: the conventions,
each model with where it comes from and what its parameters mean, why the
carrier density is an input at use time, how descriptions and valid ranges
work, and what the library checker can and cannot verify.

Good general references: Dressel & Grüner, *Electrodynamics of Solids*
(Cambridge, 2002), ch. 2–6, for the Drude and Lorentz models and the relations
between ε, n and σ; Yu & Cardona, *Fundamentals of Semiconductors* (Springer),
ch. 6, for phonons and free carriers in semiconductors; Ashcroft & Mermin,
*Solid State Physics* (1976), ch. 1, for the free-electron metal.

## 1. Conventions: ε, n + iκ and σ

Fields vary in time as $`e^{-i\omega t}`$ (the physics convention, Jackson and Born & Wolf). A wave travelling along $`+z`$ is
$`e^{i(\tilde n\omega z/c - \omega t)}`$ with the complex refractive index

```math
\tilde n = n' + i\kappa = \sqrt{\varepsilon}, \qquad \varepsilon = \varepsilon' + i\varepsilon'' ,
```

so it decays as $`e^{-\kappa\omega z/c}`$: **κ > 0 and ε″ > 0 mean absorption**;
the intensity absorption coefficient is $`\alpha = 2\kappa\omega/c`$. The
principal square root gives κ ≥ 0 whenever ε″ ≥ 0. In the other convention ($`e^{+i\omega t}`$, $`n' - i\kappa`$,
common in electrical engineering) every complex quantity is the complex conjugate.

A current density $`\mathbf{J} = \sigma\mathbf{E}`$ and a polarisation
$`\mathbf{P}`$ enter Maxwell's equations only through $`-i\omega\mathbf{P} + \mathbf{J}`$,
so a conductivity is equivalent to a permittivity:

```math
\varepsilon(\omega) = \varepsilon_{\text{bound}}(\omega) + \frac{i\sigma(\omega)}{\varepsilon_0\omega}.
```

Which charges one calls "bound" and which "conducting" is a choice. The
models below put the free carriers in σ and everything else in ε_bound.
`conductivity(material, ...)` returns the *total* optical conductivity, which
counts every charge as a current,

```math
\sigma_{\text{total}} = -i\omega\varepsilon_0(\varepsilon - 1),
```

because it is defined for every description, tables included. Its real part
is the absorption and equals the real part of the free-carrier conductivity
when ε_bound is real; its imaginary part also contains the background
$`-\omega\varepsilon_0(\varepsilon_\infty - 1)`$. The free-carrier part alone
is `drude_conductivity`.

All frequencies are angular, `omega` in rad/s, except the valid ranges, which
are in THz (`valid_range_thz`, ordinary frequency f = ω/2π) because that is
how ranges are read and written.

## 2. Free carriers: the Drude model

A carrier of charge e and effective mass m* in a field E, losing its momentum
by collisions at a rate 1/τ, obeys $`m^*\dot v = eE - m^* v/\tau`$. For
$`E\propto e^{-i\omega t}`$ this gives $`v = (e\tau/m^*)E/(1 - i\omega\tau)`$, and
N such carriers per volume carry $`J = Nev = \sigma E`$ with

```math
\sigma(\omega) = \frac{\sigma_{\text{DC}}}{1 - i\omega\tau}, \qquad
\sigma_{\text{DC}} = \frac{Ne^2\tau}{m^*} = Ne\mu, \qquad \mu = \frac{e\tau}{m^*}.
```

- The **mobility** μ is what transport measurements give, so a material file
  usually gives μ (or a mobility model, section 3), and the scattering time
  follows as $`\tau = \mu m^*/e`$ (`scattering_time_from_mobility`). For
  N = 10²⁴ m⁻³ and μ = 0.1 m²/(V s), σ_DC = 1.602·10⁴ S/m.
- At $`\omega = 1/\tau`$ the real part has fallen to σ_DC/2 and the imaginary
  part, the inertial (inductive) response, is at its maximum, also σ_DC/2. For
  THz spectroscopy this is the point of the model: the spectrum measures τ
  and N/m* separately.
- With $`\varepsilon = \varepsilon_\infty + i\sigma/(\varepsilon_0\omega)`$ and
  ωτ ≫ 1, $`\varepsilon \approx \varepsilon_\infty(1 - \omega_p^2/\omega^2)`$ with the
  screened plasma frequency

  ```math
  \omega_p = \sqrt{\frac{Ne^2}{\varepsilon_0\varepsilon_\infty m^*}}
  ```

  (`plasma_omega`; with ε_∞ = 1 the bare one). Below ω_p, ε′ < 0 and the
  material reflects like a metal; far above it, ε → ε_∞.
- `effective_mass_ratio` is the *conductivity* effective mass m*/mₑ (for
  anisotropic or degenerate bands this is an average, which is why sources
  differ, e.g. 0.26 for electrons in silicon).
- **Drude–Smith** (`smith_c` = c ∈ [−1, 0]) multiplies σ by
  $`1 + c/(1 - i\omega\tau)`$, a phenomenological memory of the first
  collision: c = −1 means full backscattering, σ_DC = 0, as for carriers
  confined in grains or nanostructures (Smith, Phys. Rev. B 64, 155106, 2001).

## 3. Mobility versus density: Caughey–Thomas

The mobility falls with the density of ionised impurities, which scatter the
carriers. Caughey & Thomas (Proc. IEEE 55, 2192, 1967) fitted silicon with

```math
\mu(N) = \mu_{\min} + \frac{\mu_{\max} - \mu_{\min}}{1 + (N/N_{\text{ref}})^{\alpha}},
```

with μ → μ_max (phonon-limited) for N ≪ N_ref, μ → μ_min for N ≫ N_ref and
μ(N_ref) = (μ_min + μ_max)/2; α sets the steepness. Sotoodeh et al. (J. Appl.
Phys. 87, 2890, 2000) give the same form for III–V compounds. The fits are in
the *doping* density; using them with the *carrier* density is exact for fully
ionised dopants and an approximation for photo-excited carriers, which scatter
off each other but not off ionised impurities. A material file states the
model by name (`mobility: {model: caughey_thomas, ...}`); it is evaluated at
the carrier density of each call, so one file serves every density.

## 4. Bound charges: Lorentz oscillators

A bound charge (an ion in a polar lattice, a bound electron) is a damped
harmonic oscillator. Its polarisation adds

```math
\varepsilon(\omega) = \varepsilon_\infty + \sum_k \frac{\Delta\varepsilon_k\,\omega_k^2}{\omega_k^2 - \omega^2 - i\gamma_k\omega}
```

with `strength` Δε_k, `resonance_omega` ω_k and `damping` γ_k (both in rad/s).

- **Static limit**: ε(0) = ε_∞ + Σ Δε_k, so the strength of a polar phonon is
  ε_static − ε_∞ (for InP ≈ 12.5 − 9.6).
- **Absorption** ε″ peaks at ω_k with full width γ_k; κ peaks slightly above
  ω_k, where ε′ drops.
- **Dispersion** has the Kramers–Kronig sign: ε′ rises towards the resonance
  from below (normal dispersion), falls through it (anomalous dispersion), and
  stays below ε_∞ just above it, where ε′ can even be negative (the
  reststrahlen band between the TO and LO phonon).
- Papers usually give ν̃_k and γ_k in cm⁻¹; the files store
  ω = 2πc ν̃ (c in cm/s) and show the cm⁻¹ value as a comment.

## 5. Drude–Lorentz

In a doped polar semiconductor the lattice and the free carriers respond
independently, so their susceptibilities add on one background:

```math
\varepsilon = \varepsilon_\infty + \sum_k(\text{Lorentz})_k + \frac{i\sigma_{\text{Drude}}}{\varepsilon_0\omega}.
```

The background is counted once (optpumpthz subtracted it explicitly; here the
Drude term is simply added without one). The coupled phonon–plasmon modes of
doped material follow from this sum by themselves, as the zeros of ε.

## 6. Graphene sheet

Graphene is a single atomic layer; its response is a *sheet* conductivity
σ_s in siemens. Its carriers are massless Dirac fermions with
$`E = \hbar v_F|k|`$, so a sheet density N fills the cone up to
$`\mu_c = \hbar v_F\sqrt{\pi N}`$ (electrons and holes alike). The local
random-phase result at temperature T (Falkovsky; as used by Arts et al.,
J. Appl. Phys. 124, 073105, 2018) has two parts:

```math
\sigma_{\text{intra}} = \frac{i e^2\, 2k_BT}{\pi\hbar^2(\omega + i\Gamma)}\ln\!\left[2\cosh\frac{\mu_c}{2k_BT}\right],
\qquad
\sigma_{\text{inter}} = \frac{e^2}{4\hbar}\left[\frac12 + \frac1\pi\arctan\frac{\hbar\omega - 2\mu_c}{2k_BT}
 - \frac{i}{2\pi}\ln\frac{(\hbar\omega + 2\mu_c)^2}{(\hbar\omega - 2\mu_c)^2 + (2k_BT)^2}\right].
```

- For μ_c ≫ k_BT the intraband term is Drude-like with the graphene Drude
  weight $`e^2\mu_c/(\pi\hbar^2)`$.
- The interband term is the universal absorption e²/(4ħ) = 6.08·10⁻⁵ S
  (πα = 2.3 % of the light) above the Pauli-blocking edge ħω = 2μ_c.
- The scattering rate follows from the mobility,
  $`\Gamma = ev_F/(\hbar\mu\sqrt{\pi N})`$ (Bøggild et al., 2D Mater. 4, 042003,
  2017, eq. 6), which makes the DC limit exactly σ_s = Neμ. It diverges at the
  Dirac point, so N must be > 0.

`graphene_sheet_permittivity` spreads σ_s over an effective slab of
`thickness` d (0.34 nm, the interlayer distance of graphite, as in Weber et
al. 2010): $`\varepsilon = \varepsilon_\infty + i\sigma_s/(\varepsilon_0\omega d)`$.
In a multilayer calculation this reproduces the sheet's reflection and
transmission as long as d is far below the wavelength; the result then does
not depend on d. `conductivity(material, ...)` of graphene is that of the
effective slab, in S/m.

## 7. Tables of n and κ

Measured optical constants are tabulated against wavelength. `read_nk_table`
reads the refractiveindex.info CSV export (a `wl,n` and a `wl,k` block,
wavelength in µm), converts each block to frequency f = c/λ, and
`tabulated_refractive_index` interpolates n and κ linearly in frequency, each
on its own grid, so the table values come back exactly at the table points.
Outside a block's range the result is NaN: optical constants change abruptly
at band edges, and extrapolating them is a physics choice the package does not
make for you. Many handbooks do not tabulate κ in the transparent region (InP in
Palik's handbook); the description is then valid only where both
exist, and the checker tests exactly that.

## 8. Descriptions, valid ranges and carrier densities

A material can be described differently in different frequency ranges: a
Drude–Lorentz model for the THz range, a measured table for the visible. The
old optpumpthz split each material into a fixed THz and optical regime; here
a material simply has a list of descriptions, each with its own
`valid_range_thz` (one or more intervals) and sources. Choosing one is
explicit:

- by default the one description whose range covers *all* requested
  frequencies is used;
- if two cover them, the package does not choose which model to believe, and
  if none covers them it does not stitch descriptions together (a step in n
  at the seam would show up as an artefact in, e.g., a time-domain
  simulation); both are errors that list the descriptions and ranges;
- `description="<label>"` picks one, and frequencies outside its range give a
  warning naming the material, the description, its range and its source, so
  the extrapolation is visible in the output of every script that does it.

**Why the carrier density is not in the file.** The background, the phonons,
the effective mass and the mobility law are properties of the material. The
carrier density is a property of the sample and the moment: the doping of a
wafer, the photo-excited density at a given pump–probe delay, a depth profile
with a different density in every sublayer. Keeping it out of the file means
one InP file serves undoped, n-type, p-type and photo-excited InP, and one
call with K densities gives the K sublayers of a profile. The carrier type
chooses the `electrons` or `holes` parameters of the description. The
exception is a material constant such as the free-electron density of a metal
(Al), which a file may give; a use-time value replaces it.

## 9. What the checker verifies, and what it cannot

`python -m cjcmaterials.check_library` (or `check_library()`) runs these
rules over every file:

| Rule group      | Verifies                                                                                                          |
|-----------------|-------------------------------------------------------------------------------------------------------------------|
| loading         | every file can be read (known model, defined source keys, valid structure)                                        |
| completeness    | name = file name; unique labels; descriptions have sources and a range; sources have type, id, citation, location, range and a `checked` of the form `no` or `<who>, <YYYY-MM-DD>`; no unused sources |
| identifiers     | DOI `10.<4–9 digits>/<suffix>`; ISBN-10/13 check digit; http(s) URL                                               |
| valid ranges    | 0 < min < max; a description's range inside the ranges of all its sources and inside the n-and-κ part of its table |
| physical sanity | known parameters have physical signs; over its own range, without and with carriers of each type, a description gives a finite n and κ ≥ 0, a positive plasma frequency, mobility and scattering time |
| overview        | `LIBRARY.md` equals what `--write-overview` generates                                                             |
| online          | (`--online`) each DOI resolves at doi.org, and its registered title, first author and year match the citation; each URL responds |

Sources with `checked: no` are listed as a to-do list for a person (they fail
the check only with `--require-checked`).

What it **cannot** verify:

- that a number was copied correctly from its source, or converted correctly
  (cm⁻¹ to rad/s, cm²/(V s) to m²/(V s)), or that the `location` points to
  the right table: that needs a person with the paper, which is what the
  `checked` field records;
- that a source is appropriate (sample, temperature, doping, film or bulk)
  for the use at hand, or that the valid range is the range the authors
  measured rather than a convenient one;
- ISBNs online: the check digit catches typing errors, not a wrong book;
- that a DOI's metadata is complete: the online comparison is tolerant
  (accents, abbreviations, 70 % of the title words) and only catches a DOI
  that points at a different paper;
- physical correctness beyond signs and finiteness: a wrong but positive
  effective mass passes.

## References

- P. Drude, Ann. Phys. 306, 566 (1900); textbook form in Dressel & Grüner (2002), ch. 5.
- N. V. Smith, Classical generalization of the Drude formula for the optical conductivity, Phys. Rev. B 64, 155106 (2001).
- D. M. Caughey, R. E. Thomas, Proc. IEEE 55, 2192 (1967); M. Sotoodeh, A. H. Khalid, A. A. Rezazadeh, J. Appl. Phys. 87, 2890 (2000).
- L. A. Falkovsky, Optical properties of graphene, J. Phys.: Conf. Ser. 129, 012004 (2008); K. Arts et al., J. Appl. Phys. 124, 073105 (2018); P. Bøggild et al., 2D Mater. 4, 042003 (2017).
- J. W. Weber, V. E. Calado, M. C. M. van de Sanden, Appl. Phys. Lett. 97, 091904 (2010).
- The sources of every library value: [LIBRARY.md](LIBRARY.md).
