from hashlib import sha256
from os import urandom
from struct import pack, unpack


IV_SIZE = 16


def xor(b1: bytes, b2: bytes) -> bytes:
    """XOR two equal-length byte strings together."""
    b3 = bytearray()
    for i in range(len(b1)):
        b3.append(b1[i] ^ b2[i])
    return bytes(b3)

def keystream(key: bytes, iv: bytes, length: int, start: int = 0) -> bytes:
    """Get a keystream of bytes. If start is specified, it will skip
      that many bytes; if it is a multiple of 32, it will skip those
      hashes.
    """
    data = b''
    counter = 0
    if start // 32 > 0:
        counter = start // 32
        start -= 32 * counter
    while len(data) < length + start:
        data += sha256(iv+key+counter.to_bytes(4, 'big')).digest()
        counter += 1
    data = data[start:]
    return data[:length]

def symcrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    """Get a keystream of bytes equal in length to the data bytes,
      then XOR the data with the keystream.
    """
    pad = keystream(key, iv, len(data))
    return xor(data, pad)

def encrypt(key: bytes, data: bytes, iv: bytes | None = None) -> tuple[bytes, bytes]:
    """Encrypt the plaintext, returning the IV and ciphertext together."""
    iv = iv or urandom(IV_SIZE)
    return (iv, symcrypt(key, iv, data))

def decrypt(key: bytes, iv: bytes, ct: bytes) -> bytes:
    """Decrypt the iv+ciphertext. Return the plaintext."""
    return symcrypt(key, iv, ct)


def hmac(key: bytes, message: bytes) -> bytes:
    """Create an hmac according to rfc 2104 specifications."""
    # set up variables
    B, L = 136 , len(message)
    L = L if L < 32 else 32
    ipad_byte = 0x36.to_bytes(1, 'big')
    opad_byte = 0x5c.to_bytes(1, 'big')
    null_byte = 0x00.to_bytes(1, 'big')
    ipad = b''.join([ipad_byte for i in range(B)])
    opad = b''.join([opad_byte for i in range(B)])

    # if key length is greater than digest length, hash it first
    key = key if len(key) <= L else sha256(key).digest()

    # if key length is less than block length, pad it with null bytes
    key = key + b''.join(null_byte for _ in range(B - len(key)))

    # compute and return the hmac
    partial = sha256(xor(key, ipad) + message).digest()
    return sha256(xor(key, opad) + partial).digest()

def check_hmac(key: bytes, message: bytes, mac: bytes) -> bool:
    """Check an hmac. Timing-attack safe implementation."""
    # first compute the proper hmac
    computed = hmac(key, message)

    # if it is the wrong length, reject
    if len(mac) != len(computed):
        return False

    # compute difference without revealing anything through timing attack
    diff = 0
    for i in range(len(mac)):
        diff += mac[i] ^ computed[i]

    return diff == 0

def seal(key: bytes, plaintext: bytes, iv: bytes | None = None) -> str:
    """Generate an iv, encrypt a message, and create an hmac all in one."""
    iv, ct = encrypt(key, plaintext, iv)
    return pack(
        f'{IV_SIZE}s32s{len(ct)}s',
        iv,
        hmac(key, ct),
        ct
    )

def unseal(key: bytes, ciphergram: bytes) -> bytes:
    """Checks hmac, then decrypts the message."""
    iv, ac, ct = unpack(f'{IV_SIZE}s32s{len(ciphergram)-32-IV_SIZE}s', ciphergram)

    if not check_hmac(key, ct, ac):
        raise Exception('HMAC authentication failed')

    return decrypt(key, iv, ct)
