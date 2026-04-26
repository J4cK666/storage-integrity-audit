from dataclasses import dataclass, field
from typing import Optional, List, Any


# input data example
# files = [
#     {
#         "file_name": "F1",
#         "content": b"...file bytes...",
#         "keywords": ["cloud", "audit"]
#     },
#     {
#         "file_name": "F2",
#         "content": b"...",
#         "keywords": ["search", "encryption"]
#     }
# ]



@dataclass
class MyFile:
    file_id: str                                  # 文件ID，例如哈希值
    original_filename: Optional[str] = None  # 原始文件名
    data: List[Any] = field(default_factory=list)  # 加密文件块
    authenticator: List[Any] = field(default_factory=list)  # 审计标签(验证器)

    @property
    def file_name(self) -> str:
        """
        返回文件显示名：
        优先使用原始文件名，如果没有，则使用文件ID
        """
        return self.original_filename or self.file_id

    def add_block(self, block: Any):
        """添加一个加密文件块"""
        self.data.append(block)

    def add_authenticator(self, tag: Any):
        """添加一个审计标签"""
        self.authenticator.append(tag)

    def block_count(self) -> int:
        """返回文件块数量"""
        return len(self.data)



GroupElement = Any  # 如果你用 PBC / Charm-Crypto，这里可以放群元素类型


@dataclass
class KeywordTag:
    """
    用户端关键词标签结构：
    一个 KeywordTag 对应一个关键词 wk。
    """

    keyword: str                                  # 明文关键词，用户端保存
    block_count: int                             # 每个文件的分块数 s
    file_ids: List[str] = field(default_factory=list)  # 包含该关键词的文件ID集合 Swk
    ral: List[GroupElement] = field(default_factory=list)  # RAL: [Vwk,1, ..., Vwk,s]

    def __post_init__(self):
        """
        对象创建后自动执行，用于初始化和检查数据。
        """
        if not self.keyword:
            raise ValueError("keyword 不能为空")

        if self.block_count <= 0:
            raise ValueError("block_count 必须大于 0")

        # 去重，保持原有顺序
        self.file_ids = list(dict.fromkeys(self.file_ids))

        # 如果没有传入 RAL，则先用 None 占位
        if not self.ral:
            self.ral = [None for _ in range(self.block_count)]

        # 如果传入了 RAL，长度必须等于 block_count
        if len(self.ral) != self.block_count:
            raise ValueError("RAL 数量必须等于 block_count")

    def add_file(self, file_id: str):
        """
        添加一个包含该关键词的文件ID。
        """
        if not file_id:
            raise ValueError("file_id 不能为空")

        if file_id not in self.file_ids:
            self.file_ids.append(file_id)

    def remove_file(self, file_id: str):
        """
        删除一个文件ID。
        """
        if file_id in self.file_ids:
            self.file_ids.remove(file_id)

    def contains_file(self, file_id: str) -> bool:
        """
        判断某个文件是否包含该关键词。
        """
        return file_id in self.file_ids

    def set_ral(self, j: int, value: GroupElement):
        """
        设置第 j 个 RAL 标签。
        注意：这里 j 从 0 开始。
        如果论文里是 Vwk,1，那么代码里对应 ral[0]。
        """
        if j < 0 or j >= self.block_count:
            raise IndexError("RAL 下标越界")

        self.ral[j] = value

    def get_ral(self, j: int) -> GroupElement:
        """
        获取第 j 个 RAL 标签。
        """
        if j < 0 or j >= self.block_count:
            raise IndexError("RAL 下标越界")

        return self.ral[j]

    def build_index_vector(self, all_file_ids: List[str]) -> List[int]:
        """
        根据所有文件ID构造索引向量 vwk。

        如果文件包含该关键词，则对应位置为 1；
        否则为 0。
        """
        file_set = set(self.file_ids)

        index_vector = []
        for file_id in all_file_ids:
            if file_id in file_set:
                index_vector.append(1)
            else:
                index_vector.append(0)

        return index_vector

    @property
    def file_count(self) -> int:
        """
        返回包含该关键词的文件数量 |Swk|。
        """
        return len(self.file_ids)
    

