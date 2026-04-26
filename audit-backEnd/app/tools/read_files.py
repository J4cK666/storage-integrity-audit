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
from typing import Dict, List, Any, Union
import json


def split_bytes(data: bytes, block_size: int = 4096) -> List[bytes]:
    """
    将文件字节内容按固定大小切分为块
    """
    return [
        data[i:i + block_size]
        for i in range(0, len(data), block_size)
    ]


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
        return keyword_input

    keyword_input = keyword_input.strip()

    # 尝试按 JSON 解析
    try:
        data = json.loads(keyword_input)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # 解析简化格式：[f1.txt:first,file; f2.txt:search,encryption]
    if keyword_input.startswith("[") and keyword_input.endswith("]"):
        keyword_input = keyword_input[1:-1]

    result: Dict[str, List[str]] = {}

    if not keyword_input:
        return result

    items = keyword_input.split(";")

    for item in items:
        item = item.strip()
        if not item:
            continue

        if ":" not in item:
            raise ValueError(f"关键词格式错误：{item}，应为 文件名:关键词1,关键词2")

        file_name, keywords = item.split(":", 1)

        file_name = file_name.strip()
        keyword_list = [
            kw.strip()
            for kw in keywords.split(",")
            if kw.strip()
        ]

        result[file_name] = keyword_list

    return result


def read_files_from_folder(
    folder_path: str,
    keyword_input: Union[str, Dict[str, List[str]]],
    block_size: int = 4096,
    recursive: bool = False
) -> Dict[str, Any]:
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
    file_paths = [
        path for path in folder.glob(pattern)
        if path.is_file()
    ]

    files = []

    for path in file_paths:
        file_bytes = path.read_bytes()
        blocks = split_bytes(file_bytes, block_size)

        file_info = {
            "file_name": path.name,
            "file_path": str(path),
            "size": len(file_bytes),
            "block_size": block_size,
            "block_count": len(blocks),
            "blocks": blocks,
            "keywords": keyword_map.get(path.name, [])
        }

        files.append(file_info)

    return {
        "file_count": len(files),
        "files": files
    }


if __name__ == "__main__":
    folder_path = "/home/jgj/MyRepository/storage-integrity-audit/testfiles"
    folder_path1 = "../testfiles"

    keyword_input = {
        "f1.txt": ["first", "file"],
        "f2.txt": ["second", "file"],
        "f3.txt": ["third", "file"]
    }

    result = read_files_from_folder(
        folder_path=folder_path,
        keyword_input=keyword_input,
        block_size=1024
    )

    print("文件数量：", result["file_count"])

    # for file in result["files"]:
    #     print("文件名：", file["file_name"])
    #     print("文件大小：", file["size"])
    #     print("分块数量：", file["block_count"])
    #     print("关键词：", file["keywords"])
    #     print("第一个分块：", file["blocks"][0] if file["blocks"] else b"")
    print(result)