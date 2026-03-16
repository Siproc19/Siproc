# -*- coding: utf-8 -*-

def safe_div(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def round_gt(amount, precision=2):
    return round(amount or 0.0, precision)
