"""
Cubrim prototype — domain layer.

# R8: bytes-as-is domainization (v1-default).

v1-default: input V = raw bytes, no preprocessing, no domain assumptions.
Round-trip is trivially guaranteed: domainize is identity, de-domainize is identity.

Resolution criterion (OQ-5): a domainization giving lower density rho with higher
locality on the corpus beats this baseline (challenger: quantization, tokenization,
type-split). Until measured on corpus, bytes-as-is is the honest zero-assumption start.
"""


def domainize(data: bytes) -> list[int]:
    """
    R8: Convert raw bytes to a list of integer values (0..255).
    Identity function — no domain assumptions.
    """
    return list(data)


def de_domainize(values: list[int]) -> bytes:
    """
    R8 inverse: Convert list of integers (0..255) back to bytes.
    Identity function — trivially lossless.
    """
    return bytes(values)
