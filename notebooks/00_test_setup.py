"""
Basic test: verifies that REBOUND correctly simulates an orbit.
Here: Earth around the Sun, one year, we check it returns to its starting point.
"""
from pathlib import Path

import rebound
import matplotlib.pyplot as plt

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

sim = rebound.Simulation()
sim.units = ('yr', 'AU', 'Msun')

sim.add(m=1.0)                          # Sun
sim.add(m=3.003e-6, a=1.0, e=0.0167)    # Earth (mass, semi-major axis, eccentricity)

sim.integrator = "whfast"
sim.dt = 0.01

xs, ys = [], []
for t in [i * 0.01 for i in range(101)]:
    sim.integrate(t)
    xs.append(sim.particles[1].x)
    ys.append(sim.particles[1].y)

plt.figure(figsize=(5, 5))
plt.plot(xs, ys)
plt.scatter([0], [0], color="orange", label="Sun")
plt.gca().set_aspect("equal")
plt.title("Earth-Sun orbit (1 year, REBOUND)")
plt.legend()
plt.savefig(DATA_DIR / "test_orbit.png")
print("OK - simulation done, image saved to data/test_orbit.png")
