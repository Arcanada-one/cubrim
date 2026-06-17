"""
R6: Header round-trip tests.

Focus: the b_k edge-length field must survive serialize->parse for the full
v1 default B=256. b_k is packed as uint16 (B=256 does not fit in uint8 — a
naive uint8 pack silently stored 256 as 255, a latent representational bug).
"""

from cubrim_proto.header import serialize_header, parse_header


def test_b_k_256_survives_round_trip():
    # B=256 is the v1 default edge bound; every axis at the bound must
    # round-trip exactly, not be truncated to 255.
    blob = serialize_header(
        mode=0, N=2, B=256, L=65536, count=10,
        b_k=[256, 256], W=8, inverse_dict=[], axis_gap_counts=[5, 5],
    )
    hdr, _ = parse_header(blob)
    assert hdr["B"] == 256
    assert hdr["b_k"] == [256, 256], "b_k=256 must not be truncated to 255"


def test_b_k_mixed_edge_lengths_round_trip():
    blob = serialize_header(
        mode=0, N=3, B=256, L=100, count=4,
        b_k=[256, 1, 200], W=6, inverse_dict=[], axis_gap_counts=[2, 1, 2],
    )
    hdr, _ = parse_header(blob)
    assert hdr["b_k"] == [256, 1, 200]
