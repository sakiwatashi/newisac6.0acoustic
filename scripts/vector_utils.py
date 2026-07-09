"""vector_utils.py — 共用 3D 向量數學工具

此模組集中了散佈於 17+ 個 official_asset_*.py 腳本中的
完全相同的向量函式，作為統一的真實來源。

使用方式：
    from vector_utils import vec_tuple, vec_sub, vec_norm, vec_dot, vec_unit
    from vector_utils import vec_add, vec_scale, distance

注意：現有腳本在口試前不強制替換，此模組作為後續重構的基礎。
"""

from __future__ import annotations

import math


def vec_tuple(values: object) -> tuple[float, float, float]:
    """將任意可索引物件轉為 3 元素 float tuple。"""
    return (float(values[0]), float(values[1]), float(values[2]))  # type: ignore[index]


def vec_add(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    """向量加法。"""
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vec_sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    """向量減法 (a - b)。"""
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vec_scale(v: tuple[float, float, float], s: float) -> tuple[float, float, float]:
    """向量純量乘法。"""
    return (v[0] * s, v[1] * s, v[2] * s)


def vec_norm(v: tuple[float, float, float]) -> float:
    """向量模長（L2 norm）。"""
    return math.sqrt(float(v[0]) * float(v[0]) + float(v[1]) * float(v[1]) + float(v[2]) * float(v[2]))


def vec_dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    """向量點積。"""
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])


def vec_unit(v: tuple[float, float, float]) -> tuple[float, float, float]:
    """正規化為單位向量；長度為 0 時返回原向量（避免 ZeroDivisionError）。"""
    n = max(vec_norm(v), 1e-12)
    return (v[0] / n, v[1] / n, v[2] / n)


def distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    """兩點歐氏距離。"""
    return vec_norm(vec_sub(a, b))
