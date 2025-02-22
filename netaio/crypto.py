from hashlib import sha256


IV_SIZE = 16


def xor(b1: bytes, b2: bytes) -> bytes:
    """XOR two equal-length byte strings together."""
    b3 = bytearray()
    for i in range(len(b1)):
        b3.append(b1[i] ^ b2[i])
    return bytes(b3)


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
