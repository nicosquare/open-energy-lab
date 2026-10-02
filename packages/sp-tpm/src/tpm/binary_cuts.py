"""Solver-independent no-good cuts for compiled queries on binary decisions.

The evaluator must return the log probability represented by the optimization
formulation, including its approximation and normalization. Using a different
native or true probability would not preserve that formulation's feasible set.
This module does not inspect or restrict the evaluator's SPN structure.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Sequence


@dataclass(frozen=True)
class BinaryDecisionCut:
    """The inequality coefficients*x >= rhs excludes exactly ``bits``."""

    bits: tuple[int, ...]
    log_probability: float

    @property
    def coefficients(self) -> tuple[int, ...]:
        return tuple(1 - 2 * bit for bit in self.bits)

    @property
    def rhs(self) -> int:
        return 1 - sum(self.bits)


class CompiledProbabilitySeparator:
    """Separate a violated binary-vertex cut without enumerating decisions.

    A cut excludes one vertex. Its infeasibility follows from a deterministic
    compiled-probability query outside the accepted interval by more than the
    stated log-space tolerance. The tolerance is a numerical buffer, not a
    statistical guarantee or a bound on SPN learning error.
    """

    def __init__(
        self,
        dimension: int,
        evaluate_log_probability: Callable[[tuple[int, ...]], float],
        *,
        log_lower: float,
        log_upper: float = 0.0,
        feasibility_tolerance: float = 1e-6,
        separation_tolerance: float = 1e-6,
    ) -> None:
        if type(dimension) is not int or dimension <= 0:
            raise ValueError("A positive binary decision dimension is required")
        if not (math.isfinite(log_lower) and math.isfinite(log_upper) and log_lower <= log_upper):
            raise ValueError("Finite ordered log-probability bounds are required")
        if not (math.isfinite(feasibility_tolerance) and feasibility_tolerance >= 0
                and math.isfinite(separation_tolerance) and 0 <= separation_tolerance < 1):
            raise ValueError("Invalid feasibility or separation tolerance")
        self.dimension = dimension
        self.evaluate = evaluate_log_probability
        self.log_lower = log_lower
        self.log_upper = log_upper
        self.feasibility_tolerance = feasibility_tolerance
        self.separation_tolerance = separation_tolerance
        self.queries: dict[tuple[int, ...], float] = {}

    def separate(self, point: Sequence[float]) -> BinaryDecisionCut | None:
        if len(point) != self.dimension:
            raise ValueError("Decision dimension does not match the binary domain")
        if any(not math.isfinite(value) or value < -1e-6 or value > 1 + 1e-6 for value in point):
            raise ValueError("A finite node point in the binary unit box is required")
        bits = tuple(int(value >= 0.5) for value in point)
        distance = sum(abs(value - bit) for value, bit in zip(point, bits))
        if distance >= 1 - self.separation_tolerance:
            return None
        if bits not in self.queries:
            value = float(self.evaluate(bits))
            # -inf denotes probability zero. NaN/+inf indicate an invalid query.
            if math.isnan(value) or value == math.inf:
                raise ValueError("The compiled probability query is not valid")
            self.queries[bits] = value
        value = self.queries[bits]
        if (value < self.log_lower - self.feasibility_tolerance
                or value > self.log_upper + self.feasibility_tolerance):
            return BinaryDecisionCut(bits, value)
        return None


# Conditional face certificates promoted from tpm_for_sp/knapsack_tpm/conditional_cuts.py.

@dataclass(frozen=True)
class CertifiedBinaryFace:
    bits: tuple[int, ...]
    fixed_indices: tuple[int, ...]
    log_upper_bound: float


class ConditionalFaceCertifier:
    """Bound numerator above and denominator below on a partial binary box.

    Subtract the same reference affine term from both log-sums before interval
    evaluation. Translation equivariance makes it cancel from their difference.
    The actual monotone PWL curves, including guard segments, supply the bounds.
    No table of full decision probabilities is used.
    """
    ratio = None  # This certificate uses direct interval bounds, not a C*exp envelope.

    def __init__(self, records, *, log_lower, tolerance=1e-6):
        import numpy as np
        if not math.isfinite(log_lower) or not math.isfinite(tolerance) or tolerance < 0:
            raise ValueError("Finite threshold and nonnegative tolerance required")
        if set(records["queries"]) != {"numerator", "denominator"}:
            raise ValueError("Both probability queries are required")
        self.log_lower = log_lower
        self.queries = {}
        for name, graph in records['queries'].items():
            terms = [r for r in graph if r['kind'] == 'affine']
            exp = next(r for r in graph if r['kind'] == 'exp')
            log = graph[-1]
            b = np.array([r['intercept'] for r in terms])
            a = np.array([r['coeff'] for r in terms])
            ex, ey = np.array(exp['evaluation_xs']), np.array(exp['evaluation_ys'])
            lx, ly = np.array(log['evaluation_xs']), np.array(log['evaluation_ys'])
            if (b.ndim != 1 or not len(b) or a.ndim != 2 or a.shape[0] != len(b) or not a.shape[1]
                    or ex.ndim != 1 or ex.shape != ey.shape or len(ex) < 2
                    or lx.ndim != 1 or lx.shape != ly.shape or len(lx) < 2
                    or not all(np.isfinite(v).all() for v in (b,a,ex,ey,lx,ly))
                    or np.any(ey < 0) or np.any(np.diff(ex) <= 0) or np.any(np.diff(ey) < 0) or ey[-1] != 1
                    or ex[-1] != 0 or np.any(np.diff(lx) <= 0) or np.any(np.diff(ly) < 0)
                    or lx[0] > 1 or lx[-1] < len(b)):
                raise ValueError('Monotone curves covering the required sum domain are required')
            self.queries[name] = (b, a, ex, ey, lx, ly)
        self.dimension = self.queries['denominator'][1].shape[1]
        if self.queries['numerator'][1].shape[1] != self.dimension:
            raise ValueError('Both queries must share the same binary decisions')
        self.tolerance = tolerance
        self.cache = {}

    def log_upper(self, bits, fixed):
        import numpy as np
        bits, fixed = np.asarray(bits), np.asarray(fixed)
        if bits.shape != (self.dimension,) or fixed.shape != bits.shape or fixed.dtype != np.bool_ or not np.isin(bits,(0,1)).all():
            raise ValueError('A complete binary point and matching Boolean fixed-coordinate mask are required')
        db, da, *_ = self.queries['denominator']
        reference = int(np.argmax(db+da @ bits))
        bounds = {}
        for name, (b, a, ex, ey, lx, ly) in self.queries.items():
            b, a = b-db[reference], a-da[reference]
            center = b+a[:, fixed] @ bits[fixed]
            lower = center+np.minimum(a[:, ~fixed], 0).sum(1)-1e-9
            upper = center+np.maximum(a[:, ~fixed], 0).sum(1)+1e-9
            ml, mu = float(lower.max()), float(upper.max())
            ql = max(1., float(np.interp(lower-mu, ex, ey).sum())-1e-8)
            qu = min(float(len(b)), float(np.interp(np.minimum(0., upper-ml), ex, ey).sum())+1e-8)
            bounds[name] = (ml+float(np.interp(ql, lx, ly))-1e-8,
                            mu+float(np.interp(qu, lx, ly))+1e-8)
        return bounds['numerator'][1]-bounds['denominator'][0]+1e-8

    def certify(self, bits):
        import numpy as np
        key = tuple(bits)
        if len(key) != self.dimension or any(v not in (0, 1) for v in key):
            raise ValueError('Complete binary decision required')
        if key in self.cache:
            return self.cache[key]
        point = np.array(key)
        fixed = np.ones(self.dimension, dtype=bool)
        threshold = self.log_lower-self.tolerance
        result = None
        if self.log_upper(point, fixed) < threshold:
            while fixed.any():
                candidates = []
                for i in np.flatnonzero(fixed):
                    released = fixed.copy()
                    released[i] = False
                    candidates.append((self.log_upper(point, released), i))
                value, i = min(candidates)
                if value >= threshold:
                    break
                fixed[i] = False
            result = CertifiedBinaryFace(key, tuple(int(i) for i in np.flatnonzero(fixed)),
                                         self.log_upper(point, fixed))
        self.cache[key] = result
        return result



__all__ = ['BinaryDecisionCut', 'CompiledProbabilitySeparator', 'CertifiedBinaryFace', 'ConditionalFaceCertifier']
