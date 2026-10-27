"""Physical constants in SI units.

Written out here instead of importing scipy, so numpy and pyyaml stay the only
dependencies.
"""

# Speed of light in vacuum [m/s], exact by the SI definition of the metre.
SPEED_OF_LIGHT = 299_792_458.0

# Vacuum magnetic permeability mu0 [N/A^2], CODATA 2022. Since the 2019 SI
# redefinition it is measured, not exactly 4*pi*1e-7 (they differ by ~1e-10).
VACUUM_PERMEABILITY = 1.25663706127e-6

# Vacuum electric permittivity eps0 = 1/(mu0*c^2) [F/m].
VACUUM_PERMITTIVITY = 1.0 / (VACUUM_PERMEABILITY * SPEED_OF_LIGHT**2)

# Elementary charge e [C], exact since the 2019 SI redefinition.
ELEMENTARY_CHARGE = 1.602176634e-19

# Electron rest mass m_e [kg], CODATA 2022.
ELECTRON_MASS = 9.1093837139e-31

# Reduced Planck constant hbar = h/(2*pi) [J s]; h is exact since 2019.
REDUCED_PLANCK_CONSTANT = 6.62607015e-34 / (2.0 * 3.141592653589793)

# Boltzmann constant k_B [J/K], exact since 2019.
BOLTZMANN_CONSTANT = 1.380649e-23
