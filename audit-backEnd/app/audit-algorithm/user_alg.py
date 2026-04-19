from py_ecc.bls12_381 import G1, G2, add, multiply, neg, Z1, Z2, eq
from py_ecc.bls12_381.bls12_381_pairing import pairing
import sys
import public_parameter



# def init():

#     # 生成公钥和私钥
#     sk = 1234567890  # 私钥
#     pk = multiply(G2, sk)  # 公钥

#     return sk, pk


# 如果一个映射满足以下三个性质，则称为双线性映射e:G1*G1->G2：
# 1.可计算性：计算此映射是高效的。
# 2.非退化性：对于生成元g∈G1，有e(g,g)≠1。
# 3.双线性：给定a,b∈Z_q^*和u,v∈G_1,e(u^a,v^b)=e(u,v)^{ab}。

def test_pairing():
    # 1. 私钥：大整数（椭圆曲线离散对数私钥）
    sk = 123
    # u,g=G1
    print("私钥:", sk)

    # 2. 公钥生成：G2群生成元 * 私钥 (pk = G2^sk)
    pk = multiply(G2, sk)
    print("公钥 (G2群点):", pk)
    print("公钥哈希:", hash(pk))  # 哈希摘要（安全、快速、能看到结果）
    sys.stdout.flush()  # 强制输出
    # 3. 核心：双线性配对验证（密码学核心用途：签名/加密验证）
    # 配对公式：e(G1, pk) = e(G1, G2^sk) = e(G1, G2)^sk
    left = pairing(pk, G1)          # 左值：e(G1, 公钥)
    print("左值哈希:", hash(left))
    right = pairing(G2, G1) ** sk   # 右值：e(G1, G2)^私钥
    print(eq(left, right))  # 验证配对性质：True
    # # 打印哈希摘要（安全、快速、能看到结果）
    # print("右值哈希:", hash(right))
    # print("\n双线性配对验证结果:", left == right)


# def test_pairing():
#     # 1. 生成私钥（随机整数）
#     sk1 = 123456
#     sk2 = 654321

#     print("私钥1:", sk1)
#     print("私钥2:", sk2)
#     # 2. 标量乘：私钥→公钥（G1/G2点）
#     pk1_G1 = multiply(G1, sk1)  # G1上的公钥 
#     pk2_G2 = multiply(G2, sk2)  # G2上的公钥
#     # pk1_G1 = (G1 * sk1, G1[1] * sk1)  # G1上的公钥

#     print("公钥1 (G1):", pk1_G1)
#     print("公钥2 (G2):", pk2_G2)

#     # 3. 双线性配对（核心）
#     result1 = pairing(pk2_G2, pk1_G1)
#     # 配对性质：e(a^p, b^q) = e(a, b)^(pq)
#     result2 = pairing(multiply(G2, sk1*sk2), G1)
#     print("配对结果1:", result1)
#     print("配对结果2:", result2)
#     print(result1 == result2)  # True，配对性质验证


if __name__ == "__main__":
    print("\n测试双线性配对:")
    test_pairing()
