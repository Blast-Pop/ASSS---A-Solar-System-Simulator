"""
Test: a comet crossing the Solar System, starting from point A.
A comes from right-click -> "Copy position" on the simulation.

Unlike the first version, we no longer aim straight at B (that line
passed almost right through the Sun -> perihelion of 0.02 AU -> the
comet nearly plunged into it, causing the "bounce" effect: the
simulation advances in fixed time jumps, so a passage that close and
fast near the Sun skips from one frame to the next instead of drawing
a smooth curve).

Here we directly choose the desired minimum passage distance
(perihelion) and eccentricity, and compute the required launch speed
using real orbital mechanics equations (vis-viva formula + angular
momentum). The result is a real, visible flyby curve.

Usage: paste this script into the Editor tab then Ctrl+Enter,
or load it via the "Load script..." button / the shell (run("...")).
Requires the viewer (01_live_viewer.py) to already be open
(the sim / app variables must be active).
"""
import numpy as np

A = np.array([5.806931, 5.427677])

GM = 4 * np.pi ** 2  # G*Msun, units AU / yr / Msun

# --- adjustable comet parameters ---
r_p = 2.0   # AU - desired minimum distance to the Sun (perihelion)
e = 1.3     # eccentricity: >1 = hyperbolic (leaves for good, never returns)

r0 = np.linalg.norm(A)
eps = GM * (e - 1) / (2 * r_p)      # specific energy (vis-viva)
L = np.sqrt(GM * r_p * (1 + e))     # specific angular momentum

v0 = np.sqrt(2 * (eps + GM / r0))   # total speed at starting point A
v_t = L / r0                        # tangential component (makes it "orbit" the Sun)
v_r = -np.sqrt(max(v0 ** 2 - v_t ** 2, 0))  # radial component, negative = inbound

r_hat = A / r0
t_hat = np.array([-r_hat[1], r_hat[0]])  # perpendicular, counterclockwise

vx, vy = v_r * r_hat + v_t * t_hat

app.add_body(
    name="Comet", letter="C", color="#7FFFD4", size=5,
    m=0.0, x=float(A[0]), y=float(A[1]), vx=float(vx), vy=float(vy),
)

print(f"Comet: start r0={r0:.3f} AU, target perihelion={r_p} AU, e={e}")
print(f"speed={v0:.3f} AU/yr -> vx={vx:.3f}, vy={vy:.3f}")
print("Tip: lower the Speed slider near the Sun passage to see the curve clearly.")
