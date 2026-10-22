"""Small dense linear-algebra helpers for three-dimensional impacts."""

from __future__ import annotations

import math


Vector = tuple[float, float, float]
Matrix = tuple[Vector, Vector, Vector]


def add(a: Vector, b: Vector) -> Vector:
    """Add two three-vectors."""
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def subtract(a: Vector, b: Vector) -> Vector:
    """Subtract two three-vectors."""
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(vector: Vector, factor: float) -> Vector:
    """Multiply a three-vector by a scalar."""
    return (vector[0] * factor, vector[1] * factor, vector[2] * factor)


def dot(a: Vector, b: Vector) -> float:
    """Return the Euclidean dot product."""
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vector, b: Vector) -> Vector:
    """Return the right-handed cross product."""
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def norm(vector: Vector) -> float:
    """Return the Euclidean norm."""
    return math.sqrt(dot(vector, vector))


def normalize(vector: Vector) -> Vector:
    """Return a unit vector in the same direction."""
    length = norm(vector)
    if length == 0.0:
        raise ValueError("cannot normalize a zero vector")
    return scale(vector, 1.0 / length)


def matvec(matrix: Matrix, vector: Vector) -> Vector:
    """Multiply a matrix by a vector."""
    return tuple(dot(row, vector) for row in matrix)  # type: ignore[return-value]


def matmul(left: Matrix, right: Matrix) -> Matrix:
    """Multiply two three-by-three matrices."""
    right_columns = tuple(zip(*right, strict=True))
    return tuple(
        tuple(dot(row, column) for column in right_columns)
        for row in left
    )  # type: ignore[return-value]


def determinant(matrix: Matrix) -> float:
    """Return a three-by-three determinant."""
    a, b, c = matrix[0]
    d, e, f = matrix[1]
    g, h, i = matrix[2]
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def inverse(matrix: Matrix) -> Matrix:
    """Invert a nonsingular three-by-three matrix."""
    a, b, c = matrix[0]
    d, e, f = matrix[1]
    g, h, i = matrix[2]
    det = determinant(matrix)
    if abs(det) <= 1e-15:
        raise ValueError("singular inertia matrix")
    return (
        ((e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det),
        ((f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det),
        ((d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det),
    )


def is_positive_definite(matrix: Matrix) -> bool:
    """Check the leading principal minors of a symmetric matrix."""
    a, b, c = matrix[0]
    d, e, f = matrix[1]
    g, h, i = matrix[2]
    if abs(b - d) > 1e-12 or abs(c - g) > 1e-12 or abs(f - h) > 1e-12:
        return False
    if a <= 0.0:
        return False
    if a * e - b * d <= 0.0:
        return False
    return determinant(matrix) > 0.0


def cross_matrix(vector: Vector) -> Matrix:
    """Return C such that C*x = vector cross x."""
    x, y, z = vector
    return (
        (0.0, -z, y),
        (z, 0.0, -x),
        (-y, x, 0.0),
    )


def tangent_basis(normal: Vector) -> tuple[Vector, Vector]:
    """Build any right-handed orthonormal basis for the contact plane."""
    reference: Vector = (1.0, 0.0, 0.0) if abs(normal[0]) < 0.9 else (0.0, 1.0, 0.0)
    first = normalize(cross(normal, reference))
    second = normalize(cross(normal, first))
    return first, second


def solve2(matrix: tuple[tuple[float, float], tuple[float, float]], rhs: tuple[float, float]) -> tuple[float, float]:
    """Solve a two-by-two system with full pivoting tolerance."""
    a, b = matrix[0]
    c, d = matrix[1]
    det = a * d - b * c
    if abs(det) <= 1e-15:
        raise ValueError("singular tangent mass matrix")
    return ((d * rhs[0] - b * rhs[1]) / det, (-c * rhs[0] + a * rhs[1]) / det)
