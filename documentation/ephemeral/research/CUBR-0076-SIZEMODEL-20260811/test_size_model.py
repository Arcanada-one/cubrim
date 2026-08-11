#!/usr/bin/env python3
"""Soundness gates for the CUBR-0076 charged size model.

These are the gates named in CUBR-0076-SIZEMODEL-PREREG-20260811.md. They run
before any size is reported; a failure here voids the result rather than
degrading it.

Run: python3 -m pytest test_size_model.py -q   (or: python3 test_size_model.py)
"""

from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import size_model as sm  # noqa: E402


# -- code tables -----------------------------------------------------------

def test_length_codes_cover_range():
    for length in range(sm.MIN_MATCH, sm.MAX_MATCH + 1):
        code = sm.length_code(length)
        base = sm.LENGTH_BASE[code]
        span = 1 << sm.LENGTH_EXTRA[code]
        assert base <= length < base + span or length == sm.MAX_MATCH, length


def test_distance_codes_cover_range():
    for distance in list(range(1, 2000)) + [4096, 32768, 65535, 320975]:
        code = sm.dist_code(distance)
        base = sm.DIST_BASE[code]
        span = 1 << sm.DIST_EXTRA[code]
        assert base <= distance < base + span, (distance, code)


def test_distance_alphabet_reaches_whole_file_window():
    biggest = sm.DIST_BASE[-1] + (1 << sm.DIST_EXTRA[-1]) - 1
    assert biggest >= 320976, biggest


# -- entropy stage ---------------------------------------------------------

def test_huffman_kraft_and_limit():
    rng = random.Random(20260811)
    for _ in range(50):
        n = rng.randint(2, 300)
        freqs = [rng.randint(0, 5000) for _ in range(n)]
        if sum(1 for f in freqs if f > 0) < 2:
            freqs[0] = freqs[1] = 7
        lengths = sm.huffman_lengths(freqs, sm.MAX_CODE_LEN)
        assert max(lengths) <= sm.MAX_CODE_LEN
        assert abs(sm.kraft_sum(lengths) - 1.0) < 1e-9, sm.kraft_sum(lengths)
        for i, f in enumerate(freqs):
            assert (lengths[i] > 0) == (f > 0)


def test_huffman_respects_tight_limit_on_skewed_input():
    # Fibonacci-like frequencies force a deep unconstrained code; the
    # length-limited construction must still produce a valid code.
    freqs = [1, 1]
    while len(freqs) < 40:
        freqs.append(freqs[-1] + freqs[-2])
    lengths = sm.huffman_lengths(freqs, sm.MAX_CODE_LEN)
    assert max(lengths) <= sm.MAX_CODE_LEN
    assert abs(sm.kraft_sum(lengths) - 1.0) < 1e-9


def test_single_symbol_alphabet_costs_one_bit():
    freqs = [0] * 10
    freqs[3] = 99
    lengths = sm.huffman_lengths(freqs, sm.MAX_CODE_LEN)
    assert lengths[3] == 1
    assert sm.kraft_sum(lengths) <= 1.0


def test_code_length_alphabet_limit():
    rng = random.Random(7)
    freqs = [rng.randint(0, 900) for _ in range(sm.CL_ALPHABET)]
    lengths = sm.huffman_lengths(freqs, sm.MAX_CL_CODE_LEN)
    assert max(lengths) <= sm.MAX_CL_CODE_LEN


# -- RLE of the table descriptors -----------------------------------------

def test_rle_round_trips_code_lengths():
    rng = random.Random(3)
    for _ in range(200):
        seq = []
        while len(seq) < rng.randint(1, 400):
            value = rng.choice([0, 0, 0, rng.randint(1, 15)])
            seq.extend([value] * rng.randint(1, 200))
        seq = seq[:400]
        out = []
        for symbol, extra_bits, extra_value in sm.rle_code_lengths(seq):
            if symbol < 16:
                out.append(symbol)
            elif symbol == 16:
                out.extend([out[-1]] * (extra_value + 3))
            elif symbol == 17:
                out.extend([0] * (extra_value + 3))
            else:
                out.extend([0] * (extra_value + 11))
            assert extra_bits in (0, 2, 3, 7)
        assert out == seq


# -- LZ parse: the reconstruction gate ------------------------------------

def _samples():
    rng = random.Random(11)
    yield b""
    yield b"a"
    yield b"ab"
    yield b"aaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    yield b"abcabcabcabcabcabcabc"
    yield b"the quick brown fox " * 40
    yield bytes(rng.randrange(256) for _ in range(4096))
    yield (b'{"key":"value","n":123}' * 100)
    yield bytes(rng.choice(b"abc \n") for _ in range(8000))


def test_parse_reconstructs_every_sample():
    for data in _samples():
        for chain in (1, 8, 128):
            for lazy in (False, True):
                tokens = sm.lz_parse(data, window=len(data) or 1,
                                     max_chain=chain, lazy=lazy)
                assert sm.reconstruct(tokens) == data, (len(data), chain, lazy)


def test_parse_respects_window():
    data = b"X" * 500 + b"payload-marker-payload" + b"Y" * 500 \
        + b"payload-marker-payload"
    tokens = sm.lz_parse(data, window=64, max_chain=64)
    assert sm.reconstruct(tokens) == data
    assert all(tok.distance <= 64 for tok in tokens)


def test_optimal_parse_reconstructs_every_sample():
    for data in _samples():
        tokens = sm.lz_parse_optimal(data, window=max(len(data), 1),
                                     max_chain=32, iterations=2)
        assert sm.reconstruct(tokens) == data, len(data)


def test_optimal_parse_respects_window_and_bounds():
    data = b"X" * 300 + b"payload-marker-payload" + b"Y" * 300 \
        + b"payload-marker-payload"
    tokens = sm.lz_parse_optimal(data, window=64, max_chain=64, iterations=2)
    assert sm.reconstruct(tokens) == data
    for tok in tokens:
        if tok.length:
            assert 1 <= tok.distance <= 64
            assert sm.MIN_MATCH <= tok.length <= sm.MAX_MATCH


def test_optimal_parse_is_not_worse_than_lazy():
    data = (b'{"name":"alpha","value":1234,"tags":["x","y"]},' * 300)
    lazy = sm.model_file(data, block_size=None, max_chain=128)
    best = sm.model_file(
        data, block_size=None, max_chain=128, parsed=sm.parse_blocks(
            data, None, 128, optimal=True))
    assert best["modelled_bytes"] <= lazy["modelled_bytes"]


def test_candidate_lengths_are_monotone_and_valid():
    data = (b"abcdefabcdefabcdefzzz" * 50)
    cands = sm.collect_candidates(data, window=len(data), max_chain=64)
    for pos, entries in enumerate(cands):
        last = 0
        for length, dist in entries:
            assert length > last, (pos, entries)
            last = length
            assert 1 <= dist <= pos
            assert data[pos:pos + length] == \
                sm.reconstruct([sm.Token(literal=b) for b in
                                data[pos - dist:pos - dist + length]])


def test_matches_are_within_bounds():
    data = (b"lorem ipsum dolor sit amet " * 60)
    tokens = sm.lz_parse(data, window=len(data), max_chain=64)
    for tok in tokens:
        if tok.length:
            assert sm.MIN_MATCH <= tok.length <= sm.MAX_MATCH
            assert tok.distance >= 1


# -- accounting closure ----------------------------------------------------

def test_charge_items_sum_to_total():
    data = b'{"a":1,"b":[2,3,4],"c":"ccccccccc"}' * 200
    for split in (1, 2, 3):
        result = sm.model_file(data, block_size=None, max_chain=32,
                               context_split=split)
        assert sum(result["charge_bits"].values()) == result["total_bits"]
        assert result["modelled_bytes"] == (result["total_bits"] + 7) // 8


def test_every_decoder_branch_is_charged():
    """No branch may be zero on a payload that exercises all of them."""
    data = b"abcdefghij" * 500 + bytes(range(256))
    result = sm.model_file(data, block_size=None, max_chain=32)
    charges = result["charge_bits"]
    for branch in ("frame_header", "block_headers", "table_descriptors",
                   "literals", "lengths", "length_extra", "distances",
                   "eob", "checksum"):
        assert charges[branch] > 0, branch


def test_branch_inventory_is_complete():
    """The Charge dataclass must expose exactly the preregistered branches."""
    expected = {"frame_header", "block_headers", "table_descriptors",
                "literals", "lengths", "length_extra", "distances",
                "distance_extra", "eob", "checksum", "context_map"}
    assert set(sm.Charge().items()) == expected


def test_store_floor_is_never_undercut():
    rng = random.Random(99)
    data = bytes(rng.randrange(256) for _ in range(20000))  # incompressible
    result = sm.model_file(data, block_size=None, max_chain=16)
    assert result["chosen_bytes"] <= result["store_bytes"]
    assert result["selected"] == "store"
    assert result["chosen_bytes"] >= len(data)


def test_blocking_charges_more_tables_than_whole_file():
    data = (b"the quick brown fox jumps over the lazy dog " * 4000)[:200000]
    whole = sm.model_file(data, block_size=None, max_chain=16)
    blocked = sm.model_file(data, block_size=65536, max_chain=16)
    assert (blocked["charge_bits"]["table_descriptors"]
            > whole["charge_bits"]["table_descriptors"])
    expected_blocks = -(-len(data) // 65536)
    assert blocked["blocks"] == expected_blocks and whole["blocks"] == 1


def test_context_split_charges_a_context_map():
    data = b'{"alpha":123,"beta":456}' * 300
    plain = sm.model_file(data, block_size=None, max_chain=16)
    split = sm.model_file(data, block_size=None, max_chain=16,
                          context_split=2)
    assert plain["charge_bits"]["context_map"] == 0
    assert split["charge_bits"]["context_map"] > 0
    assert (split["charge_bits"]["table_descriptors"]
            > plain["charge_bits"]["table_descriptors"])


def test_varint_charge():
    assert sm.varint_bits(0) == 8
    assert sm.varint_bits(127) == 8
    assert sm.varint_bits(128) == 16
    assert sm.varint_bits(320976) == 24


def test_empty_input_is_modelled():
    result = sm.model_file(b"", block_size=None, max_chain=8)
    assert result["chosen_bytes"] > 0


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{failures} failure(s)")
    sys.exit(1 if failures else 0)
