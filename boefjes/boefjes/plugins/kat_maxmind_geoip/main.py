import hashlib
import io
import json
import os
import re
import shutil
import tarfile
from datetime import datetime, timezone
from ipaddress import ip_address
from os import getenv
from pathlib import Path

import maxminddb
import requests

BASE_PATH = Path(getenv("OPENKAT_CACHE_PATH", Path(__file__).parent))

if BASE_PATH.name != Path(__file__).parent.name:
    BASE_PATH = BASE_PATH / Path(__file__).parent.name
    BASE_PATH.mkdir(exist_ok=True)

GEOIP_PATH_PATTERN = r"GeoLite2-City_\d+/GeoLite2-City.mmdb"
GEOIP_META_PATH = BASE_PATH / "geoip-meta.json"
GEOIP_SOURCE_URL = "https://download.maxmind.com/geoip/databases/GeoLite2-City/download?suffix=tar.gz"
GEOIP_CACHE_TIMEOUT = 86400  # in seconds
HASHFUNC = "sha256"
REQUEST_TIMEOUT = 30


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]
    ip = input_["address"]
    hash_algorithm = getenv("HASHFUNC", HASHFUNC)

    # if the address is private, we do not need a Location
    if not ip_address(ip).is_global:
        return [(set(), json.dumps("IP address is private, no location possible"))]

    if not geoip_file_exists() or cache_out_of_date():
        geoip_meta = refresh_geoip(hash_algorithm)
    else:
        with GEOIP_META_PATH.open() as json_meta_file:
            geoip_meta = json.load(json_meta_file)

    geoip_path = find_geoip_path()

    with maxminddb.open_database(geoip_path) as reader:
        results = reader.get(ip)

    return [({"maxmind-geoip/geo_data"}, json.dumps(results)), ({"maxmind-geoip/cache-meta"}, json.dumps(geoip_meta))]


def create_hash(data: bytes, algo: str) -> str:
    hashfunc = getattr(hashlib, algo)
    return hashfunc(data).hexdigest()


def cache_out_of_date() -> bool:
    """Returns True if the file is older than the allowed cache_timout"""
    now = datetime.now(timezone.utc)
    max_age = int(getenv("GEOIP_CACHE_TIMEOUT", GEOIP_CACHE_TIMEOUT))
    with GEOIP_META_PATH.open() as meta_file:
        meta = json.load(meta_file)
    cached_file_timestamp = datetime.fromisoformat(meta["timestamp"])
    return (now - cached_file_timestamp).total_seconds() > max_age


def refresh_geoip(algo: str) -> dict:
    maxmind_user_id = str(getenv("MAXMIND_USER_ID", ""))
    maxmind_licence_key = getenv("MAXMIND_LICENCE_KEY", "")
    source_url = getenv("GEOIP_SOURCE_URL", GEOIP_SOURCE_URL)
    request_timeout = getenv("REQUEST_TIMEOUT", REQUEST_TIMEOUT)
    response = requests.get(
        source_url, allow_redirects=True, timeout=float(request_timeout), auth=(maxmind_user_id, maxmind_licence_key)
    )
    response.raise_for_status()

    remove_old_geolite_data()

    file_like_object = io.BytesIO(response.content)

    with tarfile.open("r:gz", fileobj=file_like_object) as tf:
        geoip_file = None
        for member in tf.getmembers():
            if re.match(GEOIP_PATH_PATTERN, member.name):
                geoip_file = member
                break
        if geoip_file:
            tf.extract(geoip_file, BASE_PATH)
        else:
            raise FileNotFoundError("GeoLite2-City.mmdb not found in the tar archive")

    metadata = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source_url,
        "hash": create_hash(response.content, algo),
        "hash_algorithm": algo,
    }
    with open(GEOIP_META_PATH, "w") as meta_file:
        json.dump(metadata, meta_file)
    return metadata


def find_geoip_path() -> str:
    """Find the GeoLite2-City.mmdb file in the BASE_PATH"""
    for path in BASE_PATH.glob("GeoLite2-City_*/GeoLite2-City.mmdb"):
        return str(path)
    raise FileNotFoundError("GeoLite2-City.mmdb file not found in BASE_PATH")


def geoip_file_exists() -> bool:
    """Check if the GeoLite2-City.mmdb file exists in the BASE_PATH"""
    try:
        find_geoip_path()
        return True
    except FileNotFoundError:
        return False


def remove_old_geolite_data():
    """Removes old GeoLite2 directory"""
    for root, dirs, files in os.walk(BASE_PATH, topdown=False):
        for directory in dirs:
            dir_path = os.path.join(root, directory)
            shutil.rmtree(dir_path)
