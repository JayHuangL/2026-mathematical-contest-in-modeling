"""Kirchhoff face averages for nonlinear moisture diffusivity.

The temperature is frozen at the arithmetic face temperature while the
diffusivity is integrated along the moisture segment joining two nodes.
Eight-point Gauss--Legendre quadrature is effectively exact for the smooth
constitutive laws used in Questions 1--4.
"""
from __future__ import annotations

import numpy as np


_X, _W = np.polynomial.legendre.leggauss(8)
S = (_X + 1.0) / 2.0
W = _W / 2.0


def moisture_face(T_left, T_right, C_left, C_right, material):
    """Return D_K and its four endpoint derivatives.

    ``material(T, C)`` must return ``(..., D, ..., D_C, D_T)`` in the same
    format as the constitutive functions in Questions 2 and 4.
    """
    c = C_left[:, None] + (C_right - C_left)[:, None] * S
    tf = ((T_left + T_right) / 2.0)[:, None]
    _, _, d, _, _, d_c, d_t = material(tf, c)
    d_face = np.sum(W * d, axis=1)
    d_cl = np.sum(W * d_c * (1.0 - S), axis=1)
    d_cr = np.sum(W * d_c * S, axis=1)
    d_tface = 0.5 * np.sum(W * d_t, axis=1)
    return d_face, d_cl, d_cr, d_tface, d_tface


def scalar_face(u_left, u_right, coefficient):
    """Return the Kirchhoff average and endpoint derivatives for D(u)."""
    u = u_left[:, None] + (u_right - u_left)[:, None] * S
    d, d_u = coefficient(u)
    d_face = np.sum(W * d, axis=1)
    d_left = np.sum(W * d_u * (1.0 - S), axis=1)
    d_right = np.sum(W * d_u * S, axis=1)
    return d_face, d_left, d_right
