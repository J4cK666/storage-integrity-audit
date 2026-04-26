# input files

# output: 
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


from pathlib import Path
from typing import List, Dict, Union, Any
import json
import hashlib

from ..audit_algorithm.data_models import PlainFile
# from app.audit_algorithm.data_models import PlainFile


def parse_keyword_input(keyword_input: Union[str, Dict[str, List[str]]]) -> Dict[str, List[str]]:
    """
    支持两种关键词输入格式：

    1. 标准 JSON / dict：
       {
           "f1.txt": ["first", "file"],
           "f2.txt": ["search", "encryption"]
       }

    2. 简化字符串格式：
       [f1.txt:first,file; f2.txt:search,encryption]
    """

    if isinstance(keyword_input, dict):
        return {
            str(file_name): [
                str(kw).strip().lower()
                for kw in keywords
                if str(kw).strip()
            ]
            for file_name, keywords in keyword_input.items()
        }

    if not isinstance(keyword_input, str):
        raise TypeError("keyword_input 必须是 dict 或字符串")

    text = keyword_input.strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return parse_keyword_input(data)
    except json.JSONDecodeError:
        pass

    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]

    result: Dict[str, List[str]] = {}

    if not text:
        return result

    items = text.split(";")

    for item in items:
        item = item.strip()
        if not item:
            continue

        if ":" not in item:
            raise ValueError(f"关键词格式错误：{item}，应为 文件名:关键词1,关键词2")

        file_name, keywords = item.split(":", 1)

        result[file_name.strip()] = [
            kw.strip().lower()
            for kw in keywords.split(",")
            if kw.strip()
        ]

    return result


def split_bytes(data: bytes, block_size: int) -> List[bytes]:
    if block_size <= 0:
        raise ValueError("block_size 必须大于 0")

    if len(data) == 0:
        return [b""]

    return [
        data[i:i + block_size]
        for i in range(0, len(data), block_size)
    ]


def make_file_id(file_name: str, file_bytes: bytes) -> str:
    h = hashlib.sha256()
    h.update(file_name.encode("utf-8"))
    h.update(b"::")
    h.update(file_bytes)
    return h.hexdigest()


def read_files(
    folder_path: str,
    keyword_input: Union[str, Dict[str, List[str]]],
    block_size: int = 4096,
    recursive: bool = False
) -> List[PlainFile]:

    """
    读取文件夹中的文件，并统计文件个数、文件名、文件内容块、关键词。

    :param folder_path: 文件夹路径
    :param keyword_input: 用户输入的关键词映射
    :param block_size: 分块大小，默认 4096 字节
    :param recursive: 是否递归读取子文件夹
    :return: 包含文件数量和文件列表的字典
    """

    folder = Path(folder_path)

    if not folder.exists():
        raise FileNotFoundError(f"文件夹不存在：{folder_path}")

    if not folder.is_dir():
        raise NotADirectoryError(f"不是文件夹：{folder_path}")

    keyword_map = parse_keyword_input(keyword_input)

    pattern = "**/*" if recursive else "*"

    file_paths = sorted([
        path for path in folder.glob(pattern)
        if path.is_file()
    ])

    files: List[PlainFile] = []

    for path in file_paths:
        file_bytes = path.read_bytes()
        blocks = split_bytes(file_bytes, block_size)

        keywords = keyword_map.get(path.name, [])
        keywords = sorted(set(kw.strip().lower() for kw in keywords if kw.strip()))

        file = PlainFile(
            file_id=make_file_id(path.name, file_bytes),
            file_name=path.name,
            file_path=str(path),
            blocks=blocks,
            keywords=keywords,
            size=len(file_bytes),
            block_count=len(blocks)
        )

        files.append(file)

    return files


if __name__ == "__main__":
    folder_path = "/home/jgj/MyRepository/storage-integrity-audit/testfiles"
    folder_path1 = "../testfiles"

    keyword_input = {
        "f1.txt": ["first", "file"],
        "f2.txt": ["second", "file"],
        "f3.txt": ["third", "file"]
    }

    result = read_files(
        folder_path=folder_path,
        keyword_input=keyword_input,
        block_size=1024
    )

    print("文件数量：", len(result))

    # for file in result:
    #     print("文件名：", file.file_name)
    #     print("文件大小：", file.size)
    #     print("分块数量：", file.block_count)
    #     print("关键词：", file.keywords)
    #     print("第一个分块：", file.blocks[0] if file.blocks else b"")
    print(result)