# 导入双线性映射核心模块
from charm.toolbox.pairinggroup import PairingGroup, ZR, G1, G2, GT, pair

def bilinear_pairing_test():
    """
    双线性映射核心测试
    验证双线性性质：e(g^a, h^b) = e(g, h)^(a*b)
    其中：
    - G1, G2：两个循环群
    - GT：目标群（配对结果所在群）
    - e(·,·)：双线性配对函数
    """
    print("========== 双线性映射测试开始 ==========\n")

    # 1. 初始化双线性映射群（使用标准椭圆曲线参数：Type A 最常用）
    group = PairingGroup('SS512')  # SS512 = 512位安全双线性群
    print("✅ 双线性映射群初始化完成")

    # 2. 生成群生成元
    g = group.random(G1)   # G1群生成元
    h = group.random(G2)   # G2群生成元
    print("✅ 生成 G1、G2 群生成元")

    # 3. 生成随机指数（标量）
    a = group.random(ZR)   # ZR = 整数环（指数域）
    b = group.random(ZR)
    print(f"✅ 生成随机指数 a = {a}")
    print(f"✅ 生成随机指数 b = {b}\n")

    # 4. 计算群元素幂运算
    g_a = g ** a           # g^a
    h_b = h ** b           # h^b
    print("✅ 完成群元素幂运算")

    # 5. 执行双线性配对（核心操作）
    left_side = pair(g_a, h_b)        # 左边：e(g^a, h^b)
    right_side = pair(g, h) ** (a * b)# 右边：e(g, h)^(a*b)
    print("✅ 完成双线性配对计算\n")

    # 6. 验证双线性性质（必须相等）
    print("========== 验证结果 ==========")
    print(f"左边 e(g^a, h^b) 结果: {left_side}")
    print(f"右边 e(g, h)^(a*b) 结果: {right_side}")
    print(f"双线性性质验证: {'✅ 成功' if left_side == right_side else '❌ 失败'}")

    # 7. 额外：基础配对测试
    print("\n========== 基础配对测试 ==========")
    e1 = pair(g, h)
    e2 = pair(g ** 2, h)
    e3 = pair(g, h ** 2)
    print(f"e(g, h) == e(g, h)^2 ? {e1 == e2}")
    print(f"e(g^2, h) == e(g, h^2) ? {e2 == e3}")
    print(f"e(g^2, h) == e(g,h)^2   ? {e2 == e1**2}")

    print("\n========== 双线性映射测试结束 ==========")

# 运行测试
if __name__ == '__main__':
    bilinear_pairing_test()