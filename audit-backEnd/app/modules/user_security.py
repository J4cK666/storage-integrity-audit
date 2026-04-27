import base64
import hashlib
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException

try:
    from ..config.config import CLOUD_ROOT, USER_ID_COUNT_MAX, USER_ID_COUNT_MIN
    from ..config.database import get_user_db_connection, init_user_tables
except ImportError:
    from config.config import CLOUD_ROOT, USER_ID_COUNT_MAX, USER_ID_COUNT_MIN
    from config.database import get_user_db_connection, init_user_tables


PASSWORD_SCHEME = "sha256"


def encode_bytes(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def hash_password(password: str, salt: str) -> str:
    digest = hashlib.sha256()
    digest.update(salt.encode("utf-8"))
    digest.update(b"::")
    digest.update(password.encode("utf-8"))
    return digest.hexdigest()


def make_password_hash(password: str) -> str:
    salt = uuid4().hex
    return f"{PASSWORD_SCHEME}${salt}${hash_password(password, salt)}"


def verify_password(password: str, password_hash: str) -> bool:
    parts = password_hash.split("$", 2)
    if len(parts) != 3 or parts[0] != PASSWORD_SCHEME:
        return password == password_hash

    _, salt, expected_hash = parts
    return hash_password(password, salt) == expected_hash


def make_cloud_folder_name(account_id: str) -> str:
    return hashlib.sha256(account_id.encode("utf-8")).hexdigest()


def generate_account_id(connection) -> str:
    date_key = datetime.now().strftime("%Y%m%d")
    row = connection.execute(
        "SELECT last_count FROM user_id_counters WHERE date_key = ?",
        (date_key,),
    ).fetchone()

    count_range = USER_ID_COUNT_MAX - USER_ID_COUNT_MIN + 1
    start_count = USER_ID_COUNT_MIN if row is None else (row["last_count"] % USER_ID_COUNT_MAX) + 1
    count = start_count

    for _ in range(count_range):
        account_id = f"{date_key}{count:02d}"
        exists = connection.execute(
            "SELECT 1 FROM users WHERE account_id = ?",
            (account_id,),
        ).fetchone()

        if not exists:
            connection.execute(
                """
                INSERT INTO user_id_counters (date_key, last_count)
                VALUES (?, ?)
                ON CONFLICT(date_key) DO UPDATE SET last_count = excluded.last_count
                """,
                (date_key, count),
            )
            return account_id

        count = (count % USER_ID_COUNT_MAX) + 1

    raise HTTPException(status_code=409, detail="当天可用用户 ID 已用尽")


def serialize_group_element(group, element) -> str:
    return encode_bytes(group.serialize(element))


def create_user_keys() -> dict:
    try:
        from ..myalgorithm.init import init
    except ImportError as exc:
        try:
            from myalgorithm.init import init
        except ImportError as fallback_exc:
            raise HTTPException(status_code=500, detail=f"算法初始化模块不可用：{fallback_exc}") from exc

    pp = init()
    group = pp["group"]
    return {
        "public_key": serialize_group_element(group, pp["pk"]),
        "private_key": serialize_group_element(group, pp["sk"]),
        "g": serialize_group_element(group, pp["g"]),
        "u": serialize_group_element(group, pp["u"]),
        "k0": pp["k0"],
        "k1": pp["k1"],
        "k2": pp["k2"],
    }


def get_user_by_username(username: str):
    init_user_tables()
    with get_user_db_connection() as connection:
        return connection.execute(
            """
            SELECT account_id, username, password_hash, cloud_folder
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()


def get_user_by_account_id(account_id: str):
    init_user_tables()
    with get_user_db_connection() as connection:
        return connection.execute(
            """
            SELECT account_id, username, password_hash, cloud_folder
            FROM users
            WHERE account_id = ?
            """,
            (account_id,),
        ).fetchone()


def ensure_user_cloud_folder(account_id: str) -> str:
    cloud_folder = make_cloud_folder_name(account_id)
    (CLOUD_ROOT / cloud_folder).mkdir(parents=True, exist_ok=True)
    return cloud_folder
