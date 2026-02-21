import json
import os
import uuid

from typing import Any, Dict

CONFIG_DIR = "config"
MAPPING_PATH = os.path.join(CONFIG_DIR, "file_mapping.json")


def ensure_structure(mapping: Dict[str, Any]) -> Dict[str, Any]:
    mapping.setdefault("path_to_id", {})
    mapping.setdefault("id_to_path", {})
    mapping.setdefault("metadata", {})
    return mapping


def load_mapping() -> Dict[str, Any]:
    if os.path.exists(MAPPING_PATH):
        with open(MAPPING_PATH, "r") as f:
            return ensure_structure(json.load(f))
    return ensure_structure({})


def save_mapping(mapping: Dict[str, Any]) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    ensure_structure(mapping)
    with open(MAPPING_PATH, "w") as f:
        json.dump(mapping, f, indent=2)


def ensure_file_id(mapping: Dict[str, Any], rel_path: str) -> str:
    path_to_id = mapping.setdefault("path_to_id", {})
    id_to_path = mapping.setdefault("id_to_path", {})
    file_id = path_to_id.get(rel_path)
    if not file_id:
        file_id = str(uuid.uuid4())
        path_to_id[rel_path] = file_id
        id_to_path[file_id] = rel_path
    return file_id


def update_file_metadata(file_id: str, metadata: Dict[str, Any]) -> None:
    mapping = load_mapping()
    ensure_structure(mapping)
    entry = mapping["metadata"].setdefault(file_id, {})
    entry.update(metadata)
    save_mapping(mapping)
