from charm.toolbox.pairinggroup import G1
from Crypto.Cipher import AES
from Crypto.Hash import HMAC, SHA256
from Crypto.Random import get_random_bytes
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

    pad_len = 16 - len(plaintext) % 16
    plaintext += bytes([pad_len]) * pad_len

    return iv + cipher.encrypt(plaintext)

def Dec(k0: bytes, ciphertext: bytes):
    iv = ciphertext[:16]
    ct = ciphertext[16:]
    cipher = AES.new(k0, AES.MODE_CBC, iv)
    pt = cipher.decrypt(ct)
    return pt[:-pt[-1]]

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

