from charm.toolbox.pairinggroup import G1
from Crypto.Cipher import AES
from Crypto.Hash import HMAC, SHA256
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
from pydantic import BaseModel

# 全局参数容器
PP = {}



# ================= Hash =================
def H1(group, data: bytes):
    return group.hash(data, G1)

def H2(group, data: bytes):
    return group.hash(b'H2'+data, G1)

def H3(group, data: bytes):
    return group.hash(b'H3'+data, G1)

# ================= Enc =================
def Enc(k0: bytes, plaintext: bytes):
    iv = get_random_bytes(16)
    cipher = AES.new(k0, AES.MODE_CBC, iv)
    ct = cipher.encrypt(pad(plaintext, AES.block_size))
    return iv + ct

def Dec(k0: bytes, ciphertext: bytes):
    if len(ciphertext) < AES.block_size:
        raise ValueError("密文长度不合法")

    iv = ciphertext[:16]
    ct = ciphertext[16:]

    if len(ct) % AES.block_size != 0:
        raise ValueError("密文块长度不是16字节的倍数")

    cipher = AES.new(k0, AES.MODE_CBC, iv)
    pt = cipher.decrypt(ct)
    return unpad(pt, AES.block_size)

# ================= PRP =================
def PRP(k1: bytes, data: bytes):
    cipher = AES.new(k1, AES.MODE_ECB)
    pad_len = 16 - len(data) % 16
    data += bytes([pad_len]) * pad_len
    return cipher.encrypt(data)

# ================= PRF =================
def PRF(k2: bytes, data: bytes):
    h = HMAC.new(k2, digestmod=SHA256)
    h.update(data)
    return h.digest()

