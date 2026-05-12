from __future__ import annotations

import base64
from typing import Any, Dict, Optional

try:
    from ..config.database import get_user_db_connection, init_user_tables
except ImportError:
    from config.database import get_user_db_connection, init_user_tables


PUBLIC_PARAMETER_CURVE = "SS512"


def encode_bytes(value: bytes) -> str:
    return base64.b64encode(bytes(value)).decode("ascii")


def decode_bytes(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


def _bytes_from_db(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    return bytes(value)


def _user_query(where_clause: str) -> str:
    return f"""
        SELECT
            users.account_id,
            users.username,
            users.cloud_folder,
            user_crypto_keys.public_key,
            user_crypto_keys.private_key,
            user_crypto_keys.g,
            user_crypto_keys.u,
            user_crypto_keys.k0,
            user_crypto_keys.k1,
            user_crypto_keys.k2
        FROM users
        LEFT JOIN user_crypto_keys
            ON user_crypto_keys.account_id = users.account_id
        WHERE {where_clause}
    """


def _algorithm_components():
    from charm.toolbox.pairinggroup import PairingGroup, pair

    try:
        from ..myalgorithm.public_parameter import H1, H2, H3, Dec, Enc, PP, PRF, PRP
    except ImportError:
        from myalgorithm.public_parameter import H1, H2, H3, Dec, Enc, PP, PRF, PRP

    return {
        "PairingGroup": PairingGroup,
        "pair": pair,
        "H1": H1,
        "H2": H2,
        "H3": H3,
        "Enc": Enc,
        "Dec": Dec,
        "PP": PP,
        "PRF": PRF,
        "PRP": PRP,
    }


def _row_to_serialized_pp(row) -> Dict[str, str]:
    return {
        "pk": row["public_key"],
        "sk": row["private_key"],
        "public_key": row["public_key"],
        "private_key": row["private_key"],
        "g": row["g"],
        "u": row["u"],
        "k0": encode_bytes(_bytes_from_db(row["k0"])),
        "k1": encode_bytes(_bytes_from_db(row["k1"])),
        "k2": encode_bytes(_bytes_from_db(row["k2"])),
    }


def _row_to_runtime_pp(row) -> Dict[str, Any]:
    components = _algorithm_components()
    PairingGroup = components["PairingGroup"]
    group = PairingGroup(PUBLIC_PARAMETER_CURVE)
    return {
        "group": group,
        "pair": components["pair"],
        "g": group.deserialize(decode_bytes(row["g"])),
        "u": group.deserialize(decode_bytes(row["u"])),
        "H1": components["H1"],
        "H2": components["H2"],
        "H3": components["H3"],
        "Enc": components["Enc"],
        "Dec": components["Dec"],
        "PRP": components["PRP"],
        "PRF": components["PRF"],
        "k0": _bytes_from_db(row["k0"]),
        "k1": _bytes_from_db(row["k1"]),
        "k2": _bytes_from_db(row["k2"]),
        "sk": group.deserialize(decode_bytes(row["private_key"])),
        "pk": group.deserialize(decode_bytes(row["public_key"])),
    }


def _row_to_user_info(row, include_pp: bool = True) -> Optional[Dict[str, Any]]:
    if not row:
        return None

    user_info: Dict[str, Any] = {
        "account_id": row["account_id"],
        "username": row["username"],
        "cloud_folder": row["cloud_folder"],
    }

    if include_pp:
        missing_key = any(row[key] is None for key in ("public_key", "private_key", "g", "u", "k0", "k1", "k2"))
        user_info["pp"] = None if missing_key else _row_to_serialized_pp(row)

    return user_info


def get_user_info_by_username(username: str, include_pp: bool = True) -> Optional[Dict[str, Any]]:
    init_user_tables()
    with get_user_db_connection() as connection:
        row = connection.execute(
            _user_query("users.username = ?"),
            (username,),
        ).fetchone()

    return _row_to_user_info(row, include_pp=include_pp)


def get_user_info_by_account_id(account_id: str, include_pp: bool = True) -> Optional[Dict[str, Any]]:
    init_user_tables()
    with get_user_db_connection() as connection:
        row = connection.execute(
            _user_query("users.account_id = ?"),
            (account_id,),
        ).fetchone()

    return _row_to_user_info(row, include_pp=include_pp)


def get_user_runtime_pp(account_id: str) -> Optional[Dict[str, Any]]:
    init_user_tables()
    with get_user_db_connection() as connection:
        row = connection.execute(
            _user_query("users.account_id = ?"),
            (account_id,),
        ).fetchone()

    if not row:
        return None

    missing_key = any(row[key] is None for key in ("public_key", "private_key", "g", "u", "k0", "k1", "k2"))
    if missing_key:
        return None

    return _row_to_runtime_pp(row)


def load_user_runtime_pp(account_id: str) -> Optional[Dict[str, Any]]:
    runtime_pp = get_user_runtime_pp(account_id)
    if runtime_pp is None:
        return None

    PP = _algorithm_components()["PP"]
    PP.clear()
    PP.update(runtime_pp)
    return PP


def save_user_info(pp: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "public_key": pp.get("pk"),
        "private_key": pp.get("sk"),
        "g": pp.get("g"),
        "u": pp.get("u"),
        "k0": pp.get("k0"),
        "k1": pp.get("k1"),
        "k2": pp.get("k2"),
    }
