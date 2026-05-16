from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

try:
    from ..myalgorithm.data_models import (
        AuthenticatorSet,
        EncryptedBlock,
        EncryptedFile,
        SecureIndex,
        SecureIndexRow,
        SetupResult,
    )
except ImportError:
    from myalgorithm.data_models import (
        AuthenticatorSet,
        EncryptedBlock,
        EncryptedFile,
        SecureIndex,
        SecureIndexRow,
        SetupResult,
    )


ENC_SCHEMA = "storage-integrity-audit.encrypted-file.v1"
AUTH_SCHEMA = "storage-integrity-audit.authenticator-set.v1"
INDEX_SCHEMA = "storage-integrity-audit.secure-index.v1"


@dataclass(frozen=True)
class CloudSaveResult:
    encrypted_files: Dict[str, Path]
    authenticator_file: Path
    index_file: Path


@dataclass(frozen=True)
class CloudPackage:
    setup_result: SetupResult
    secure_index: SecureIndex
    auth_set: AuthenticatorSet


def _b64_encode(value: bytes) -> str:
    return base64.b64encode(bytes(value)).decode("ascii")


def _b64_decode(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


def _require_group(group: Any = None) -> Any:
    if group is not None:
        return group

    try:
        from ..myalgorithm.public_parameter import PP
    except ImportError:
        from myalgorithm.public_parameter import PP

    resolved_group = PP.get("group")
    if resolved_group is None:
        raise ValueError("PairingGroup is required. Initialize PP or pass group explicitly.")
    return resolved_group


def _safe_name_component(value: str, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} cannot be empty")
    if any(separator in text for separator in ("/", "\\", ":", "\x00")):
        raise ValueError(f"{field_name} contains unsafe path characters: {value!r}")
    return text


def _write_json(path: Path, payload: Dict[str, Any], overwrite: bool) -> Path:
    if path.exists() and not overwrite:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _serialize_group_element(group: Any, value: Any) -> str:
    return _b64_encode(group.serialize(value))


def _deserialize_group_element(group: Any, value: str) -> Any:
    return group.deserialize(_b64_decode(value))


def _encrypted_file_to_payload(enc_file: EncryptedFile) -> Dict[str, Any]:
    return {
        "schema": ENC_SCHEMA,
        "file_id": enc_file.file_id,
        "original_block_count": enc_file.original_block_count,
        "block_count": len(enc_file.blocks),
        "blocks": [
            {
                "block_index": block.block_index,
                "ciphertext": _b64_encode(block.ciphertext),
                "cij_int": str(block.cij_int),
                "is_padding": block.is_padding,
            }
            for block in sorted(enc_file.blocks, key=lambda item: item.block_index)
        ],
    }


def _payload_to_encrypted_file(payload: Dict[str, Any]) -> EncryptedFile:
    if payload.get("schema") != ENC_SCHEMA:
        raise ValueError("invalid encrypted file schema")

    file_id = str(payload["file_id"])
    blocks = [
        EncryptedBlock(
            file_id=file_id,
            file_name="",
            block_index=int(block["block_index"]),
            ciphertext=_b64_decode(block["ciphertext"]),
            cij_int=int(block["cij_int"]),
            is_padding=bool(block.get("is_padding", False)),
        )
        for block in payload.get("blocks", [])
    ]

    return EncryptedFile(
        file_id=file_id,
        file_name="",
        blocks=sorted(blocks, key=lambda item: item.block_index),
        original_block_count=int(payload["original_block_count"]),
    )


def save_encrypted_file(
    enc_file: EncryptedFile,
    cloud_dir: str | Path,
    *,
    overwrite: bool = True,
) -> Path:
    """
    Save one encrypted data-block file as ``<file_id>.enc``.

    The payload intentionally excludes original file names and paths.
    """

    file_id = _safe_name_component(enc_file.file_id, "file_id")
    path = Path(cloud_dir) / f"{file_id}.enc"
    return _write_json(path, _encrypted_file_to_payload(enc_file), overwrite)


def save_encrypted_files(
    setup_result: SetupResult,
    cloud_dir: str | Path,
    *,
    overwrite: bool = True,
) -> Dict[str, Path]:
    return {
        enc_file.file_id: save_encrypted_file(enc_file, cloud_dir, overwrite=overwrite)
        for enc_file in setup_result.C
    }


def save_encrypted_blocks(
    setup_result: SetupResult,
    cloud_dir: str | Path,
    *,
    overwrite: bool = True,
) -> Dict[str, Path]:
    return save_encrypted_files(setup_result, cloud_dir, overwrite=overwrite)


def load_encrypted_file(path: str | Path) -> EncryptedFile:
    return _payload_to_encrypted_file(_read_json(Path(path)))


def load_encrypted_files(
    cloud_dir: str | Path,
    *,
    file_ids: Optional[Sequence[str]] = None,
) -> List[EncryptedFile]:
    base_dir = Path(cloud_dir)

    if file_ids is None:
        paths = sorted(base_dir.glob("*.enc"))
    else:
        paths = [
            base_dir / f"{_safe_name_component(file_id, 'file_id')}.enc"
            for file_id in file_ids
        ]

    return [load_encrypted_file(path) for path in paths]


def load_encrypted_blocks(
    cloud_dir: str | Path,
    *,
    file_ids: Optional[Sequence[str]] = None,
) -> List[EncryptedFile]:
    return load_encrypted_files(cloud_dir, file_ids=file_ids)


def _auth_set_to_payload(
    auth_set: AuthenticatorSet,
    user_id: str,
    group: Any,
) -> Dict[str, Any]:
    return {
        "schema": AUTH_SCHEMA,
        "user_id": user_id,
        "authenticators": [
            {
                "file_id": file_id,
                "blocks": [
                    {
                        "block_index": int(block_index),
                        "sigma": _serialize_group_element(group, sigma),
                    }
                    for block_index, sigma in sorted(blocks.items())
                ],
            }
            for file_id, blocks in sorted(auth_set.authenticators.items())
        ],
    }


def _payload_to_auth_set(payload: Dict[str, Any], group: Any) -> AuthenticatorSet:
    if payload.get("schema") != AUTH_SCHEMA:
        raise ValueError("invalid authenticator schema")

    authenticators: Dict[str, Dict[int, Any]] = {}
    for file_item in payload.get("authenticators", []):
        file_id = str(file_item["file_id"])
        authenticators[file_id] = {
            int(block["block_index"]): _deserialize_group_element(group, block["sigma"])
            for block in file_item.get("blocks", [])
        }

    return AuthenticatorSet(authenticators=authenticators)


def save_authenticator_set(
    auth_set: AuthenticatorSet,
    user_id: str,
    cloud_dir: str | Path,
    *,
    group: Any = None,
    overwrite: bool = True,
) -> Path:
    """
    Save AuthGen output as ``<user_id>.auth``.
    """

    safe_user_id = _safe_name_component(user_id, "user_id")
    resolved_group = _require_group(group)
    path = Path(cloud_dir) / f"{safe_user_id}.auth"
    payload = _auth_set_to_payload(auth_set, safe_user_id, resolved_group)
    return _write_json(path, payload, overwrite)


def load_authenticator_set(
    user_id: str,
    cloud_dir: str | Path,
    *,
    group: Any = None,
) -> AuthenticatorSet:
    safe_user_id = _safe_name_component(user_id, "user_id")
    resolved_group = _require_group(group)
    path = Path(cloud_dir) / f"{safe_user_id}.auth"
    return _payload_to_auth_set(_read_json(path), resolved_group)


def _metadata_from_setup_result(setup_result: SetupResult) -> Dict[str, Any]:
    file_table = {
        str(index): file_id
        for index, file_id in sorted(setup_result.id_table.items())
    }

    return {
        "n": setup_result.n,
        "s": setup_result.s,
        "block_size": setup_result.block_size,
        "file_table": file_table,
    }


def _file_table_from_metadata(metadata: Dict[str, Any]) -> Dict[int, str]:
    """
    Cloud-side file_table maps file order to file_id, never to file names.
    """

    if "file_table" in metadata:
        return {
            int(index): str(file_id)
            for index, file_id in metadata["file_table"].items()
        }

    return {
        int(item["index"]): str(item["file_id"])
        for item in metadata.get("id_table", [])
    }


def _index_to_payload(
    secure_index: SecureIndex,
    setup_result: SetupResult,
    user_id: str,
    group: Any,
) -> Dict[str, Any]:
    rows = []
    for address, row in sorted(secure_index.rows.items(), key=lambda item: item[0]):
        rows.append(
            {
                "address": _b64_encode(address),
                "encrypted_vector": _b64_encode(row.encrypted_vector),
                "ral": [
                    {
                        "block_index": int(block_index),
                        "value": _serialize_group_element(group, value),
                    }
                    for block_index, value in sorted(row.ral.items())
                ],
            }
        )

    return {
        "schema": INDEX_SCHEMA,
        "user_id": user_id,
        "metadata": _metadata_from_setup_result(setup_result),
        "rows": rows,
    }


def _payload_to_index(payload: Dict[str, Any], group: Any) -> SecureIndex:
    if payload.get("schema") != INDEX_SCHEMA:
        raise ValueError("invalid secure index schema")

    rows: Dict[bytes, SecureIndexRow] = {}
    for row_payload in payload.get("rows", []):
        address = _b64_decode(row_payload["address"])
        row = SecureIndexRow(
            address=address,
            encrypted_vector=_b64_decode(row_payload["encrypted_vector"]),
            ral={
                int(item["block_index"]): _deserialize_group_element(group, item["value"])
                for item in row_payload.get("ral", [])
            },
            keyword_debug="",
        )
        rows[address] = row

    return SecureIndex(rows=rows)


def save_secure_index(
    secure_index: SecureIndex,
    setup_result: SetupResult,
    user_id: str,
    cloud_dir: str | Path,
    *,
    group: Any = None,
    overwrite: bool = True,
) -> Path:
    """
    Save IndexGen output as ``<user_id>.index``.

    Sensitive fields such as plaintext keywords, ``keyword_debug``, file names,
    and raw setup vectors W/V are not included.
    """

    safe_user_id = _safe_name_component(user_id, "user_id")
    resolved_group = _require_group(group)
    path = Path(cloud_dir) / f"{safe_user_id}.index"
    payload = _index_to_payload(secure_index, setup_result, safe_user_id, resolved_group)
    return _write_json(path, payload, overwrite)


def load_secure_index(
    user_id: str,
    cloud_dir: str | Path,
    *,
    group: Any = None,
) -> SecureIndex:
    safe_user_id = _safe_name_component(user_id, "user_id")
    resolved_group = _require_group(group)
    path = Path(cloud_dir) / f"{safe_user_id}.index"
    return _payload_to_index(_read_json(path), resolved_group)


def load_index_metadata(user_id: str, cloud_dir: str | Path) -> Dict[str, Any]:
    safe_user_id = _safe_name_component(user_id, "user_id")
    payload = _read_json(Path(cloud_dir) / f"{safe_user_id}.index")
    if payload.get("schema") != INDEX_SCHEMA:
        raise ValueError("invalid secure index schema")
    return payload["metadata"]


def _setup_result_from_cloud_payload(
    metadata: Dict[str, Any],
    encrypted_files: Iterable[EncryptedFile],
) -> SetupResult:
    file_table = _file_table_from_metadata(metadata)
    encrypted_by_id = {
        enc_file.file_id: enc_file
        for enc_file in encrypted_files
    }
    ordered_C = [
        encrypted_by_id[file_id]
        for _, file_id in sorted(file_table.items())
        if file_id in encrypted_by_id
    ]

    missing_file_ids = [
        file_id
        for _, file_id in sorted(file_table.items())
        if file_id not in encrypted_by_id
    ]
    if missing_file_ids:
        raise FileNotFoundError(f"missing encrypted files: {missing_file_ids}")

    return SetupResult(
        C=ordered_C,
        W=[],
        V={},
        n=int(metadata["n"]),
        s=int(metadata["s"]),
        block_size=int(metadata["block_size"]),
        file_table=file_table,
        id_table=file_table.copy(),
    )


def save_to_cloud(
    setup_result: SetupResult,
    secure_index: SecureIndex,
    auth_set: AuthenticatorSet,
    user_id: str,
    cloud_dir: str | Path,
    *,
    group: Any = None,
    overwrite: bool = True,
) -> CloudSaveResult:
    """
    Save Setup/IndexGen/AuthGen cloud-side outputs.

    Naming:
    - encrypted data blocks: ``<file_id>.enc``
    - authenticators: ``<user_id>.auth``
    - secure index: ``<user_id>.index``

    The secure index metadata includes ``file_table`` as
    ``{"1": "file_id_1", "2": "file_id_2"}``, without original file names.
    """

    resolved_group = _require_group(group)
    encrypted_paths = save_encrypted_files(
        setup_result,
        cloud_dir,
        overwrite=overwrite,
    )
    auth_path = save_authenticator_set(
        auth_set,
        user_id,
        cloud_dir,
        group=resolved_group,
        overwrite=overwrite,
    )
    index_path = save_secure_index(
        secure_index,
        setup_result,
        user_id,
        cloud_dir,
        group=resolved_group,
        overwrite=overwrite,
    )

    return CloudSaveResult(
        encrypted_files=encrypted_paths,
        authenticator_file=auth_path,
        index_file=index_path,
    )


def load_from_cloud(
    user_id: str,
    cloud_dir: str | Path,
    *,
    group: Any = None,
) -> CloudPackage:
    """
    Load cloud-side data and rebuild objects needed by ProofGen.
    """

    resolved_group = _require_group(group)
    metadata = load_index_metadata(user_id, cloud_dir)
    file_ids = [
        file_id
        for _, file_id in sorted(_file_table_from_metadata(metadata).items())
    ]
    encrypted_files = load_encrypted_files(cloud_dir, file_ids=file_ids)

    return CloudPackage(
        setup_result=_setup_result_from_cloud_payload(metadata, encrypted_files),
        secure_index=load_secure_index(user_id, cloud_dir, group=resolved_group),
        auth_set=load_authenticator_set(user_id, cloud_dir, group=resolved_group),
    )
