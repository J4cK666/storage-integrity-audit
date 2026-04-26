"""
解密测试模块 - 用于测试文件内容解密功能
"""

from typing import List
from dataclasses import dataclass

# 导入 public_parameter 中的加密解密函数
from .public_parameter import Enc, Dec


# ================= 数据模型 =================

@dataclass
class EncryptedBlock:
    """加密后的文件块"""
    file_id: str
    file_name: str
    block_index: int
    ciphertext: bytes
    cij_int: int
    is_padding: bool = False


@dataclass
class EncryptedFile:
    """加密文件对象"""
    file_id: str
    file_name: str
    blocks: List[EncryptedBlock]
    original_block_count: int


# ================= 解密函数 =================

def decrypt_file_content(k0: bytes, encrypted_file) -> bytes:
    """
    解密文件内容。
    
    Args:
        k0: AES 密钥
        encrypted_file: EncryptedFile 对象，加密的文件数据
        
    Returns:
        解密后的明文内容 (bytes)
    """
    decrypted_blocks = []
    
    for block in encrypted_file.blocks:
        # 跳过填充块
        if block.is_padding:
            continue
        
        # 解密每个块
        plaintext_block = Dec(k0, block.ciphertext)
        decrypted_blocks.append(plaintext_block)
    
    # 合并所有块
    return b''.join(decrypted_blocks)


def decrypt_block_content(k0: bytes, ciphertext: bytes) -> bytes:
    """
    解密单个块的内容。
    
    Args:
        k0: AES 密钥
        ciphertext: 加密的块数据
        
    Returns:
        解密后的明文块 (bytes)
    """
    return Dec(k0, ciphertext)


# ================= 测试代码 =================

def test_decrypt_file():
    """测试解密整个文件"""
    # 1. 准备测试数据
    k0 = b'0123456789abcdef'  # 16字节密钥
    
    original_content = b'Hello, this is a test file content!'
    
    # 2. 加密内容
    ciphertext = Enc(k0, original_content)
    print(f"原始内容: {original_content}")
    print(f"加密后: {ciphertext.hex()}")
    
    # 3. 解密内容
    decrypted = Dec(k0, ciphertext)
    print(f"解密后: {decrypted}")
    
    # 4. 验证
    assert decrypted == original_content, "解密失败！"
    print("✓ 测试通过: 解密单个内容")


def test_decrypt_blocks():
    """测试解密多个块"""
    # 1. 准备测试数据
    k0 = b'0123456789abcdef'
    
    blocks_data = [
        b'Block 1 content here.',
        b'Block 2 content here.',
        b'Block 3 content here.',
    ]
    
    # 2. 加密每个块
    encrypted_blocks = []
    for i, data in enumerate(blocks_data):
        ciphertext = Enc(k0, data)
        encrypted_blocks.append(ciphertext)
        print(f"块 {i+1} 加密后: {ciphertext.hex()}")
    
    # 3. 解密每个块
    decrypted_blocks = []
    for ct in encrypted_blocks:
        pt = Dec(k0, ct)
        decrypted_blocks.append(pt)
        print(f"块解密后: {pt}")
    
    # 4. 验证
    for original, decrypted in zip(blocks_data, decrypted_blocks):
        assert original == decrypted, "块解密失败！"
    print("✓ 测试通过: 解密多个块")


def test_decrypt_encrypted_file():
    """测试解密 EncryptedFile 对象"""
    # 1. 准备测试数据
    k0 = b'0123456789abcdef'
    
    original_blocks = [
        b'This is the first block of data.',
        b'This is the second block of data.',
        b'This is the third block of data.',
    ]
    
    # 2. 创建加密文件
    encrypted_blocks = []
    for i, data in enumerate(original_blocks):
        ciphertext = Enc(k0, data)
        block = EncryptedBlock(
            file_id="test_file_1",
            file_name="test.txt",
            block_index=i + 1,
            ciphertext=ciphertext,
            cij_int=i,
            is_padding=False
        )
        encrypted_blocks.append(block)
    
    # 添加一个填充块
    padding_ciphertext = Enc(k0, b'\x00' * 16)
    padding_block = EncryptedBlock(
        file_id="test_file_1",
        file_name="test.txt",
        block_index=4,
        ciphertext=padding_ciphertext,
        cij_int=3,
        is_padding=True
    )
    encrypted_blocks.append(padding_block)
    
    encrypted_file = EncryptedFile(
        file_id="test_file_1",
        file_name="test.txt",
        blocks=encrypted_blocks,
        original_block_count=3
    )
    
    # 3. 解密整个文件
    decrypted_content = decrypt_file_content(k0, encrypted_file)
    print(f"解密后文件内容: {decrypted_content}")
    
    # 4. 验证
    expected = b''.join(original_blocks)
    assert decrypted_content == expected, "文件解密失败！"
    print("✓ 测试通过: 解密 EncryptedFile 对象")


if __name__ == "__main__":
    # print("=" * 50)
    # print("开始解密功能测试")
    # print("=" * 50)
    
    # test_decrypt_file()
    # print()
    
    # test_decrypt_blocks()
    # print()
    
    # test_decrypt_encrypted_file()
    # print()
    
    # print("=" * 50)
    # print("所有测试通过！")
    # print("=" * 50)
    C = [EncryptedFile(file_id='2f9ae9b2ad9783d50f3482f86a3147bfef6b6b3add2093c32c5bbd1ef17a7912', file_name='f1.txt', blocks=[EncryptedBlock(file_id='2f9ae9b2ad9783d50f3482f86a3147bfef6b6b3add2093c32c5bbd1ef17a7912', file_name='f1.txt', block_index=1, ciphertext=b'\x81\x80\x1eK\xfc\xce\xa9VJ\xba\x03L;`\x8e\xa3\xa7A\xb4v\xb2\xdfbs\x84\x0bX\\,\x95\x0f\xeaxx\x0b#1h\xa37 \xc5}\x03\xb0\x9b\x00\xf3', cij_int=50483822888121696336687453145516559484234411848594649495759146383361086410303, is_padding=False), EncryptedBlock(file_id='2f9ae9b2ad9783d50f3482f86a3147bfef6b6b3add2093c32c5bbd1ef17a7912', file_name='f1.txt', block_index=2, ciphertext=b'\xd4\x0c\xfan\x8bu\x95\x90:\xb0UKF3\x1b=\t\xcb\xc1U\x04}\xe5\x95d2\nT\xd8?QN?@t\x17r\xa3\xae\xe1P\xdab\xde\xe07\xd00\xdd \xc9:\xc7\xf5xp\x0bi\xe40\xf8\x02\xf8\x81\xba\xe8ais\xe6h\xd8\xfe*u\xb4\xc46\x8bv\xa1\xa6C\xef\xae\x89\x9aD\xc1\xe5\x18\xd3T\x0eA\xe7\xfc\xd1h\x8a\x08\x8d\xf0\x03 Ni@\x04Sk~\x19\x96\x11\xfc\xdd\xbe\r\xb0\x94\xdd\xe6\x8cH;\xe1\x0f\xe2\x1bUa\xd4\xd6~\xf1i\x9f\xbeR\xb7\xfe\x89\x1a(\x985+\x81n\xf8%<y<sEQ\x9fF\xb1\xee\xb7\xde\xe9\x9bN\xce\x18=\xc4\xe2u\xc9\xf0\xe7\n\xedP\x04\x0cp\x8fD\x0e\xb8\xbf.\'$\x93\x03\x7f\xed|.&\xa5\xdf\xc1{\x7f;\xad\xe7j\xa5j\x8d\xd4-m\x17\x10T\xef\xa0ba\xbc!\x97I\xae\x0b\xf6\x04U\x92\xf5\n3\x95b)\xa3\xd8P\x906\xf2O\xd7\x925\x97\x9c%%\xcd\xbb>.K\xc63\x96^\xfe\x12\xa0\x93\x90cW_\x0b\xfd\xa5Z\x03wi}bb\xd9\x7f\xd6[\x1a\xc9&-\xe2\x1cv}\x99r\x0f\xdb\xe5f\xa66\xd9R\xbe\xbcs\x83m\xb4w\xc1\xf4\xbe:\xcf\x80\xac\x15\xc8M\x99\xf4\xa3!H\xdc\x9a\x14\xff(\xe2\xd0\xe7K\x8e\xe3i\xeb\xca%\'\xbe\x9e\xab{\x96\xf5)0\xe8\xa0u\xf5\x1e\x10a\xe7YK0\n^\x0e\xefk\x84\x9be\xb9\x08\x8c\x8fq\xfb\xb7\x03\x8c 8>\xd5\xb9\x85\xa6\x9d5\x89"\xa8\x9d\xfabt\x02\xfb#A:\xe5\xb8jz\x92\x84\xa5B\xf1fP\xc9Kj\x97\xf2\xad\x0b\x9c\xa7\xe7\x8c\xbc\x16\xd4\x06\x03\xf0\xe9q\x9bS}\xfc\xcd\xde\xdd\x9cr\xf8\x14\xcc\xb6\x7fvY\xc7\x0b\x9f\xb7Q\x98\xeb-<\xb9\xd8\xeb\x04\xbb\xe1n\xa8]Oh\r!\xf8\xc4\x9b\xe3\x04\xc0\x02\x88\xa0\xd0\n\x8c~\x92\xc2\xa9\x19\x11\xd4\xba\x87\xf3\x9ax\xc9,\x1b\xb5w\xe7?\x83\xe0`\x84y\xc3\x01\xcb\xaa`@5+@\xbd\xd6\xb51\xe9M\xd3\x7f\xe1\x0bH\xe9\xeb\xe2y\xad\xa0\xe8\xcf\xb6.\x81\xb6\x80\xd6|$\\\x1d\x18e\x04\xc1Pk\x15\xe2\x82\xc7\x17\xddyr\xb3\xd2Q\n\x00>D~ yi}&\xd0Y\xb9\x0c\xca\xb0J\xc3\xf7)\xc7\x16B$\xae\xf1\xf9(\xd5\xc6\xd7\x7fQ\x12Q\x82\x8co\xb4\x0f\xe8\xf2\xffD.\xaeKc\xb2\xdb\xb2Qkh\x95C\xd9zZhk)\xfd\x88\xd2\xdd\x19\x92\xde\xb0\xeb0\xaa\xab\xf7\xea\xf9F\x96\x14>)\xaf\xdcm\x90\x03\xda\x0f\x92\xcfJ;`\xe1\xad\xfd\xc7\xfb\x9c\xac:\x15JM\x16\xc0?:\x19\xdc\xb0\xce\xfc\x13\x88\xcfR\x10\x91\x0b\xfai\xef\x8e\'Hc\xe4`\x89\xe7H\x1c\x03\xbe\xcf\xf0\x1f\x15\x16\x9c\xe1\xb4\xcbA\xdc\x97i\x87\xa6Pa\x90i\x02\xb5\xcb1!8y?\xd4b\xc0\xc8P\x86\xdf\x9c=\x1a?\xfc6\x01\x941\xf41\xec).\xbc\x12\xe5\x8c\xc8\xfd\xf2C\x0b\x82\xfe\x80:\x9e\xb0\x8e\x05J\xaf\xd3{K\x80\x1c\xbf\xf3\x00\x1cu\xbb\xb8\xdd\xe0\xb2\x959D%\xd2\xc6tS^\xf6x\xae\x16(E\xae\x94\xa3\x0e\xeb\x94\x98\xe3\x8f&-\xd6gr\xeauj\x9b\xfc\x07\x95$\n\xe8b\xe6\x19:tE\xca*\xc6\xa8\x9et\xa8\x00Q]S\x7f2\xb1\x9d(]\x9d\xf9\xb4\x90\xb0S\x87\x9eu=\xce\x08L\x1f\xda]\x980r[\x82{B\xf0\x1fG\xb1\\z0\xc9\xd7\xf1\xc5\xe4\xf0x\x0b\xa4J\x0bt\x9e &\x08\x15\x8bZ\x94w*\xef\xa4\xe2\x01\xf7\xb5\x15\x9f?L\x83F\x93\xb0\x0c\xe4w\x9e]\xa5k\xe1\xf5>\xd9d\x81\xad\x18\x9c\xd7\xc5\xdf\x9a\xe8\x0b5\x0b\xaa\xcf,\xd6\x17\x1dG\xdeU\xb6C\xe4\xb5+\xeb\x949\xf8\xbcw\xa7J\xbe.R&\xdd\x06\x80c\xfa\xc9Y \xd7\x93\x17\xf6c\xba]MS\xe6\xac\x99\x9dMu\x8c#\xd4t_\xa3\xa7\xa6u\tV\xc0O\x0c\xc3\xc0N8\x01_$\xd1e\xfdVm\xaa=\xcc\x9e\xc4\x01\xa4P\x0f\\\xea\xf6\xd9\xf5LF\x88\xa4\x1a\xd4\x84*\x03\th\x7f|\xafPJO.\x99`\xc5i\xc0\x9d\xf8\xecOOS\xf2\xe8\x16\x15\xd0\xc5\xbd\xa9|\x18\x1cd\x8b\x07\xdb\x13', cij_int=72235694629254661974306397983727071750907076209453000587565234743351537669595, is_padding=True)], original_block_count=1)]
    k0 = b'\x02\xe3bS\xa7z\xf1(\x95@|\x91\xabG\xfa\xec'

    dec = decrypt_block_content(k0,C[0].blocks[0].ciphertext)
    print(dec)