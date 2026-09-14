"""非线性含水率扩散系数的 Kirchhoff 面平均。

温度取面两侧节点温度的算术平均值，扩散系数沿连接两节点的含水率线段积分。
对于第一至第四问使用的光滑本构关系，八点 Gauss–Legendre 求积已足够精确。
"""
from __future__ import annotations

import numpy as np


_X, _W = np.polynomial.legendre.leggauss(8)
S = (_X + 1.0) / 2.0
W = _W / 2.0


def moisture_face(T_left, T_right, C_left, C_right, material):
    """返回 D_K 及其四个端点导数。

    `material(T, C)` 必须返回与第二问、第四问本构函数相同格式的
    `(..., D, ..., D_C, D_T)`。
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
    """返回 D(u) 的 Kirchhoff 平均值及其端点导数。"""
    u = u_left[:, None] + (u_right - u_left)[:, None] * S
    d, d_u = coefficient(u)
    d_face = np.sum(W * d, axis=1)
    d_left = np.sum(W * d_u * (1.0 - S), axis=1)
    d_right = np.sum(W * d_u * S, axis=1)
    return d_face, d_left, d_right
