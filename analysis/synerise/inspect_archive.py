"""Inventory and safely extract only official source Parquet files to a fresh directory."""

import argparse
import hashlib
import json
import tarfile
from pathlib import Path, PurePosixPath

EXPECTED = {
    f"{name}.parquet"
    for name in (
        "product_buy",
        "add_to_cart",
        "remove_from_cart",
        "page_visit",
        "search_query",
        "product_properties",
    )
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    members = []
    selected = []
    with tarfile.open(args.archive, "r:gz") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
                raise ValueError(f"Unsafe archive member: {member.name}")
            members.append({"name": member.name, "bytes": member.size, "regular": member.isfile()})
            if member.isfile() and path.name in EXPECTED:
                selected.append(member)
        if {PurePosixPath(m.name).name for m in selected} != EXPECTED or len(selected) != 6:
            raise ValueError("Expected exactly six original source files")
        if sum(m.size for m in selected) > 100 * 1024**3:
            raise ValueError("Extraction exceeds 100 GiB safety budget")
        if args.destination.exists():
            raise FileExistsError("Extraction destination must be fresh")
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "archive_bytes": args.archive.stat().st_size,
            "members": members,
            "selected_bytes": sum(m.size for m in selected),
            "status": "inspected",
        }
        args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")
        args.destination.mkdir(parents=True)
        for member in selected:
            source = archive.extractfile(member)
            assert source is not None
            digest = hashlib.sha256()
            target = args.destination / PurePosixPath(member.name).name
            with source, target.open("xb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
            next(m for m in members if m["name"] == member.name)["sha256"] = digest.hexdigest()
        digest = hashlib.sha256()
        with args.archive.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        manifest.update(status="extracted", archive_sha256=digest.hexdigest())
        args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")
        print(json.dumps({k: v for k, v in manifest.items() if k != "members"}))


if __name__ == "__main__":
    main()
