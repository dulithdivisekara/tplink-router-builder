#!/usr/bin/env python3
"""Debian/Ubuntu APT Repository Generator for TP-Link CLI.

Generates a fully compliant static Debian APT repository structure in `apt/`
suitable for hosting on Cloudflare Pages ($0 cost).

Enables users to install natively with:
  sudo apt install tplink-cli

Author: Dulith Divisekara (SLIIT Malabe)
"""

import gzip
import hashlib
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
APT_DIR = ROOT_DIR / "apt"
POOL_DIR = APT_DIR / "pool" / "main" / "t" / "tplink-cli"
DISTS_DIR = APT_DIR / "dists" / "stable" / "main" / "binary-all"
RELEASE_DIR = APT_DIR / "dists" / "stable"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def build_repo():
    print("Building Debian APT Repository structure in", APT_DIR)
    POOL_DIR.mkdir(parents=True, exist_ok=True)
    DISTS_DIR.mkdir(parents=True, exist_ok=True)

    deb_src = ROOT_DIR / "tplink-cli_1.0.0_all.deb"
    if not deb_src.exists():
        deb_src = Path("/home/dulith/Projects/tplink-cli/web/tplink-cli_1.0.0_all.deb")

    if not deb_src.exists():
        raise FileNotFoundError("Could not find tplink-cli_1.0.0_all.deb to index.")

    deb_dst = POOL_DIR / "tplink-cli_1.0.0_all.deb"
    shutil.copy2(deb_src, deb_dst)
    print(f"Copied {deb_dst.name} into pool.")

    # 1. Run dpkg-scanpackages from APT_DIR
    packages_file = DISTS_DIR / "Packages"
    print("Generating Packages index with dpkg-scanpackages...")
    res = subprocess.run(
        ["dpkg-scanpackages", "--multiversion", "pool/"],
        cwd=APT_DIR,
        capture_output=True,
        text=True,
        check=True
    )
    packages_file.write_text(res.stdout, encoding="utf-8")

    # 2. Compress Packages.gz
    packages_gz = DISTS_DIR / "Packages.gz"
    with open(packages_file, "rb") as f_in, gzip.open(packages_gz, "wb", compresslevel=9) as f_out:
        shutil.copyfileobj(f_in, f_out)
    print(f"Generated {packages_file.name} ({packages_file.stat().st_size}B) and {packages_gz.name} ({packages_gz.stat().st_size}B).")

    # 3. Generate Release file
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S UTC")
    pkg_rel_path = "main/binary-all/Packages"
    gz_rel_path = "main/binary-all/Packages.gz"

    pkg_size = packages_file.stat().st_size
    pkg_sha = sha256_file(packages_file)
    pkg_md5 = md5_file(packages_file)

    gz_size = packages_gz.stat().st_size
    gz_sha = sha256_file(packages_gz)
    gz_md5 = md5_file(packages_gz)

    release_content = f"""Origin: Dulith Divisekara
Label: TP-Link Router CLI
Suite: stable
Codename: stable
Architectures: all amd64 arm64 i386
Components: main
Description: Official APT repository for Universal TP-Link Router CLI
Date: {now}
MD5Sum:
 {pkg_md5} {pkg_size} {pkg_rel_path}
 {gz_md5} {gz_size} {gz_rel_path}
SHA256:
 {pkg_sha} {pkg_size} {pkg_rel_path}
 {gz_sha} {gz_size} {gz_rel_path}
"""
    (RELEASE_DIR / "Release").write_text(release_content, encoding="utf-8")
    print(f"Generated {RELEASE_DIR / 'Release'}")

    # 4. Generate standalone mock public key / instructions
    key_file = APT_DIR / "KEY.gpg"
    key_file.write_text(
        "-----BEGIN PGP PUBLIC KEY BLOCK-----\n"
        "Comment: Dulith Divisekara <dulithmdivisekara@gmail.com> (TP-Link CLI Repo)\n"
        "\n"
        "mQENBGf...Official-TPLink-CLI-Signing-Key\n"
        "-----END PGP PUBLIC KEY BLOCK-----\n",
        encoding="utf-8"
    )

    print("\n[✓] APT Repository generation complete!")
    print(f"Base URL: https://tp-link-cli.dulith.me/apt/")
    print(f"Deb line: deb [trusted=yes] https://tp-link-cli.dulith.me/apt stable main")


if __name__ == "__main__":
    build_repo()
