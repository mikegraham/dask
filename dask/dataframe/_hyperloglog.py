# -*- coding: utf-8 -*
u"""Implementation of HyperLogLog

This implements the HyperLogLog algorithm for cardinality estimation, found
in

    Philippe Flajolet, Éric Fusy, Olivier Gandouet and Frédéric Meunier.
        "HyperLogLog: the analysis of a near-optimal cardinality estimation
        algorithm". 2007 Conference on Analysis of Algorithms. Nice, France
        (2007)

"""
from __future__ import division

import numpy as np
import pandas as pd

from .hashing import hash_pandas_object

def compute_first_bit(a):
    "Compute the position of the first nonzero bit for each int in an array."
    # TODO: consider making this less memory-hungry
    bits = np.bitwise_and.outer(a, 1<<np.arange(32))
    bits = bits.cumsum(axis=1).astype(np.bool)
    return 33 - bits.sum(axis=1)

def compute_hll_array(obj, b):
    # b is the number of bits

    if not 8 <= b <= 16:
        raise ValueError('b should be between 8 and 16')
    num_bits_discarded = 32 - b
    m = 1 << b

    # Get an array of the hashes
    hashes = hash_pandas_object(obj).astype(np.uint32)

    # Of the first b bits, which is the first nonzero?
    j = hashes >> num_bits_discarded
    first_bit = compute_first_bit(j)

    # Pandas can do the max aggregation
    df = pd.DataFrame({'j': j, 'first_bit': first_bit})
    series = df.groupby('j').max()['first_bit']

    # Return a dense array so we can concat them and get a result
    # that is easy to deal with
    return series.reindex(np.arange(m), fill_value=0).values.astype(np.uint8)

def estimate_count(Ms, b):
    if b < 8:
        # Smaller is incompatible with the alpha below
        raise ValueError('p must be at least 7')
    m = 1 << b

    # We concatenated all of the states, now we need to get the max
    # value for each j in both
    Ms = Ms.reshape((m, len(Ms)//m))
    M = Ms.max(axis=1)

    alpha = 0.7213 / (1 + 1.079 / m)

    # Estimate cardinality
    E = alpha * m / (2.0**-M).sum() * m
    # Apply adjustments for small / big cardinalities, if applicable
    if E < 2.5*m:
        V = (M == 0).sum()
        if V:
            return m * np.log(m / V)
    if E > 2**32 / 30.0:
        return -2**32 * np.log1p(-E / 2**32)
    return E
