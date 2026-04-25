
from charm.toolbox.pairinggroup import PairingGroup, G1, ZR, pair
from Crypto.Random import get_random_bytes

from public_parameter import PP, H1, H2, H3, Enc, Dec, PRP, PRF


def init():
    # ===================== a) 系统参数 pp =====================
    # 1. 双线性群初始化 (q 阶乘法循环群 G1, G2=GT，双线性映射 e: G1×G1→GT)
    group = PairingGroup('SS512')   # 标准安全参数，q 为素数阶512位安全
    # 生成生成元 g, u ∈ G1
    g = group.random(G1)
    u = group.random(G1)
    # 生成系统对称密钥
    k0 = get_random_bytes(16)  # Enc
    k1 = get_random_bytes(16)  # PRP
    k2 = get_random_bytes(16)  # PRF
    # 用户密钥生成
    x = group.random(ZR)   # 私钥
    y = g ** x             # 公钥 y=g^x
    # 写入全局公共参数
    PP['group'] = group
    PP['pair'] = pair

    PP['g'] = g
    PP['u'] = u
    
    PP['H1'] = H1
    PP['H2'] = H2
    PP['H3'] = H3
    
    PP['Enc'] = Enc
    PP['Dec'] = Dec
    PP['PRP'] = PRP
    PP['PRF'] = PRF

    PP['k0'] = k0
    PP['k1'] = k1
    PP['k2'] = k2

    PP['sk'] = x
    PP['pk'] = y

    return PP


def split_file(data: bytes, block_size=1024):
    """把文件分割为固定大小块"""
    return [data[i:i+block_size] for i in range(0, len(data), block_size)]

    
def setup(file_dict: dict):
    """
    file_dict 格式:
    {
        "file1.txt": "this is a cloud storage system",
        "file2.txt": "searchable encryption audit"
    }

    输出:
    EncryptedFiles, Index V
    """

    group = PP['group']
    Enc = PP['Enc']
    k0 = PP['k0']

    print("===== Setup Phase Start =====")

    EncryptedFiles = {}
    FileKeywords = {}
    W = set()

    # -------------------------------------------------
    # a) 文件分块 + 加密
    # b) 提取关键词
    # -------------------------------------------------
    for file_id, text in file_dict.items():

        data_bytes = text.encode()

        # 分块
        blocks = split_file(data_bytes, 1024)

        # 加密块
        enc_blocks = [Enc(k0, block) for block in blocks]
        EncryptedFiles[file_id] = enc_blocks

        # 提取关键词
        keywords = extract_keywords(text)
        FileKeywords[file_id] = keywords
        W |= keywords   # 构建全集

    print("Total keywords:", len(W))

    # -------------------------------------------------
    # c) 构建索引向量
    # -------------------------------------------------
    files = list(file_dict.keys())
    n = len(files)

    V = {}  # keyword -> bit vector

    for w in W:
        vector = [0] * n

        for i, f in enumerate(files):
            if w in FileKeywords[f]:
                vector[i] = 1

        V[w] = vector

    print("Index build complete.")
    print("===== Setup Finished =====")

    return EncryptedFiles, V



if __name__ == "__main__":
    init()
    # ===================== 测试输出 =====================
    print("===== 系统公开参数 pp =====")
    print(f"PP['group']: \n{PP['group']}\n")
    print(f"PP['pair']: \n{PP['pair']}\n")
    print(f"G1 生成元 u:\n{PP['u']}\n")
    print(f"G1 生成元 g:\n{PP['g']}\n")
    print(f"私钥 x (Z_q^*): {PP['sk']}\n")
    print(f"公钥 y = g^x:\n{PP['pk']}\n")

    # 测试哈希函数
    test_str = "test_message"
    print(f"H1('{test_str}') -> G1:\n{H1(PP['group'], test_str)}\n")

    # 测试双线性配对 e(g, u)
    e_result = pair(PP['g'], PP['u'])
    print(f"双线性映射 e(g, u) ∈ G2(GT):\n{e_result}")



# 如果一个映射满足以下三个性质，则称为双线性映射e:G1*G1->G2：
# 1.可计算性：计算此映射是高效的。
# 2.非退化性：对于生成元g∈G1，有e(g,g)≠1。
# 3.双线性：给定a,b∈Z_q^*和u,v∈G_1,e(u^a,v^b)=e(u,v)^{ab}。

# def test_pairing():

#     group = PairingGroup('SS512')  # SS512 = 512位安全双线性群
#     # 1. 私钥：大整数（椭圆曲线离散对数私钥）
#     sk = group.random(ZR)  # ZR = 整数环（指数域）
#     u,g= group.random(G1), group.random(G2)  # G1、G2群生成元（随机点）
#     print("私钥:", sk)

#     # 2. 公钥生成：G2群生成元 * 私钥 (pk = g^sk)
#     pk = pow(g,sk)
#     print("公钥 (G2群点):", pk)
#     print("公钥哈希:", hash(pk))  # 哈希摘要（安全、快速、能看到结果）
#     # 3. 核心：双线性配对验证（密码学核心用途：签名/加密验证）
#     # 配对公式：e(G1, pk) = e(G1, G2^sk) = e(G1, G2)^sk
#     left = pair(pk, u)          # 左值：e(u, 公钥)
#     print("左值哈希:", hash(left))
#     right = pair(g, u) ** sk   # 右值：e(u, g)^私钥
#     print("验证配对性质:", left == right)  # 验证配对性质：True
#     # # 打印哈希摘要（安全、快速、能看到结果）
#     # print("右值哈希:", hash(right))
#     # print("\n双线性配对验证结果:", left == right)

