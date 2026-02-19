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

def derive_key(*parts: bytes) -> bytes:
    """Derives a one-time key from parts."""
    pad = b''.join([sha256(p).digest() for p in parts])
    return sha256(pad).digest()

def keystream(key: bytes, iv: bytes, length: int, start: int = 0) -> bytes:
    """Get a keystream of bytes. If start is specified, it will skip
      that many bytes; if it is a multiple of 32, it will skip those
      hashes.
    """
    key = derive_key(key, iv, b'enc')
    data = b''
    counter = 0
    if start // 32 > 0:
        counter = start // 32
        start -= 32 * counter
    while len(data) < length + start:
        data += sha256(key+counter.to_bytes(4, 'big')).digest()
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

def hmac(key: bytes, iv: bytes, message: bytes) -> bytes:
    """Create an hmac according to rfc 2104 specifications."""
    # set up variables
    B = 136
    ipad_byte = 0x36
    opad_byte = 0x5c
    null_byte = 0x00
    ipad = bytes([ipad_byte] * B)
    opad = bytes([opad_byte] * B)

    key = derive_key(key, iv, b'mac')

    # pad key with null bytes
    key = key + bytes([null_byte] * (B - len(key)))

    # compute and return the hmac
    partial = sha256(xor(key, ipad) + message).digest()
    return sha256(xor(key, opad) + partial).digest()

def check_hmac(key: bytes, iv: bytes, message: bytes, mac: bytes) -> bool:
    """Check an hmac."""
    # first compute the proper hmac
    computed = hmac(key, iv, message)

    # if it is the wrong length, reject
    if len(mac) != len(computed):
        return False

    # compute difference without revealing anything through timing attack
    diff = 0
    for i in range(len(mac)):
        diff += mac[i] ^ computed[i]

    return diff == 0

def seal(key: bytes, plaintext: bytes) -> bytes:
    """Generate an iv, encrypt a message, and create an hmac all in one."""
    iv, ct = encrypt(key, plaintext)
    return pack(
        f'{IV_SIZE}s32s{len(ct)}s',
        iv,
        hmac(key, iv, ct),
        ct
    )

def unseal(key: bytes, ciphergram: bytes) -> bytes:
    """Checks hmac, then decrypts the message."""
    iv, ac, ct = unpack(f'{IV_SIZE}s32s{len(ciphergram)-32-IV_SIZE}s', ciphergram)

    if not check_hmac(key, iv, ct, ac):
        raise Exception('HMAC authentication failed')

    return decrypt(key, iv, ct)
