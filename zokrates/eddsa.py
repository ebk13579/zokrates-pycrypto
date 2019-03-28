"""
This module implements an EdDSA signature:

The signer has two secret values:

    * k = Secret key
    * r = Per-(message,key) nonce

The signer provides a signature consisting of two values:

    * R = Point, image of `r*B`
    * s = Image of `r + (k*t)`

The signer provides the verifier with their public key:

    * A = k*B

Both the verifier and the signer calculate the common reference string:

    * t = H(R, A, M)

The nonce `r` is  a random secret, and protects the value `s` from revealing the
signers secret key. H() denotes a cryptographic hash function, SHA256 in this implementation.

based on: https://github.com/HarryR/ethsnarks
For further information see: https://eprint.iacr.org/2015/677.pdf
"""

import hashlib
from collections import namedtuple
from math import ceil, log2
from os import urandom

from .babyjubjub import JUBJUB_E, JUBJUB_L, JUBJUB_Q, Point
from .field import FQ
from .utils import to_bytes


class PrivateKey(namedtuple("_PrivateKey", ("fe"))):
    """
    Wraps field element
    """

    @classmethod
    def from_rand(cls):
        mod = JUBJUB_L
        nbytes = ceil(ceil(log2(mod)) / 8) + 1
        rand_n = int.from_bytes(urandom(nbytes), "little")
        return cls(rand_n)

    def sign(self, msg, B=None):
        "Returns the signature (R,S) for a given private key and message."
        B = B or Point.generator()

        A = PublicKey.from_private(self)  # A = kB

        M = msg
        r = hash_to_scalar(self.fe, M)  # r = H(k,M) mod L
        R = B.mult(r)  # R = rB

        # Bind the message to the nonce, public key and message
        hRAM = hash_to_scalar(R, A, M)
        key_field = self.fe.n
        S = (r + (key_field * hRAM)) % JUBJUB_E  # r + (H(R,A,M) * k)

        return (R, S)


class PublicKey(namedtuple("_PublicKey", ("p"))):
    """
    Wraps edwards point
    """

    @classmethod
    def from_private(cls, sk, B=None):
        "Returns public key for a private key. B denotes the group generator"
        B = B or Point.generator()
        if not isinstance(sk, PrivateKey):
            sk = PrivateKey(sk)
        A = B.mult(sk.fe)
        return cls(A)

    def verify(self, sig, msg, B=None):
        B = B or Point.generator()

        R, S = sig
        M = msg
        A = self.p

        lhs = B.mult(S)

        hRAM = hash_to_scalar(R, A, M)
        rhs = R + (A.mult(hRAM))

        return lhs == rhs


def hash_to_scalar(*args):
    """
    Hash the key and message to create `r`, the blinding factor for this signature.
    If the same `r` value is used more than once, the key for the signature is revealed.

    Note that we take the entire 256bit hash digest as input for the scalar multiplication.
    As the group is only of size JUBJUB_E (<256bit) we allow wrapping around the group modulo.
    """
    p = b"".join(to_bytes(_) for _ in args)
    digest = hashlib.sha256(p).digest()
    return int(digest.hex(), 16)  # mod JUBJUB_E here for optimized implementation
