"""Risk management limits, checked on small hand-made weight tables."""

import numpy as np
import pandas as pd
import pytest

from qrp.risk.limits import Limits

DATES = pd.to_datetime(["2024-01-02", "2024-01-03"])


def weights(rows):
    return pd.DataFrame(rows, index=DATES, columns=["A", "B", "C"], dtype=float)


PRICES = weights([[1, 1, 1], [1, 1, 1]])  # limits do not look at prices


def test_default_limits_leave_a_valid_portfolio_alone():
    w = weights([[0.5, 0.3, 0.2], [1.0, 0.0, 0.0]])
    assert Limits().apply(w, PRICES).equals(w)


def test_long_only_removes_shorts():
    w = weights([[0.6, -0.2, 0.4], [0, 0, 0]])
    out = Limits().apply(w, PRICES)
    assert out.iloc[0].tolist() == [0.6, 0.0, 0.4]


def test_shorts_allowed_when_long_only_is_off():
    w = weights([[0.6, -0.2, 0.4], [0, 0, 0]])
    out = Limits(long_only=False, max_gross_exposure=2.0).apply(w, PRICES)
    assert out.iloc[0].tolist() == [0.6, -0.2, 0.4]


def test_max_weight_caps_each_asset_and_leaves_the_rest_in_cash():
    # 0.7 is capped to 0.4; the 0.3 cut goes to cash, not to B or C.
    w = weights([[0.7, 0.2, 0.1], [0, 0, 0]])
    out = Limits(max_weight=0.4).apply(w, PRICES)
    assert out.iloc[0].tolist() == pytest.approx([0.4, 0.2, 0.1])


def test_gross_exposure_scales_everything_down_proportionally():
    # Sum is 1.6 > 1.0, so every weight is multiplied by 1.0 / 1.6.
    w = weights([[0.8, 0.4, 0.4], [0, 0, 0]])
    out = Limits().apply(w, PRICES)
    assert out.iloc[0].tolist() == pytest.approx([0.5, 0.25, 0.25])
    assert out.iloc[0].sum() == pytest.approx(1.0)


def test_rules_apply_in_order_short_then_cap_then_scale():
    # Short removed -> [0.9, 0, 0.6]; cap 0.75 -> [0.75, 0, 0.6]; gross 1.35 -> scale by 1/1.35.
    w = weights([[0.9, -0.5, 0.6], [0, 0, 0]])
    out = Limits(max_weight=0.75).apply(w, PRICES)
    assert out.iloc[0].tolist() == pytest.approx([0.75 / 1.35, 0.0, 0.6 / 1.35])


def test_missing_weights_become_cash():
    w = weights([[np.nan, 0.5, 0.5], [0, 0, 0]])
    assert Limits().apply(w, PRICES).iloc[0].tolist() == [0.0, 0.5, 0.5]


def test_limits_must_be_positive():
    with pytest.raises(ValueError):
        Limits(max_weight=0)
