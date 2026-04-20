#!/usr/bin/env python3
"""
Unpack a signed .shortcut into an Apple Archive (.aar), extract contents,
and convert any plist files to XML for easier diff/LLM use.

Requires macOS CLIs: aea, aa, openssl, plutil.
"""
import argparse
import base64
import plistlib
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


def die(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def run(cmd, *, capture=False, text=True):
    if capture:
        return subprocess.check_output(cmd, text=text)
    subprocess.check_call(cmd)
    return ""


def read_auth_plist_bytes(data: bytes) -> bytes:
    idx = data.find(b"bplist00")
    if idx < 4:
        die("auth plist not found (missing bplist00 magic)")
    length = struct.unpack("<I", data[idx - 4 : idx])[0]
    end = idx + length
    if end > len(data):
        die("auth plist length out of range")
    return data[idx:end]


def extract_sign_pub_base64(auth_plist: bytes, workdir: Path) -> str:
    pl = plistlib.loads(auth_plist)
    chain = pl.get("SigningCertificateChain")
    if not chain:
        die("SigningCertificateChain missing in auth plist")
    leaf = chain[0]
    leaf_der = workdir / "leaf.der"
    leaf_pem = workdir / "leaf.pub.pem"
    leaf_der.write_bytes(leaf)

    with leaf_pem.open("wb") as out:
        subprocess.check_call(
            ["openssl", "x509", "-inform", "der", "-in", str(leaf_der), "-pubkey", "-noout"],
            stdout=out,
        )

    text = run(["openssl", "ec", "-pubin", "-in", str(leaf_pem), "-text", "-noout"], capture=True)
    lines = []
    collect = False
    for line in text.splitlines():
        if line.strip().startswith("pub:"):
            collect = True
            continue
        if line.strip().startswith("ASN1"):
            break
        if collect:
            lines.append(line.strip())
    hexstr = re.sub(r"[^0-9a-fA-F]", "", "".join(l.replace(":", "") for l in lines))
    if not hexstr:
        die("failed to parse EC public key from openssl output")
    raw = bytes.fromhex(hexstr)
    return base64.b64encode(raw).decode()


def is_plist_candidate(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in (".plist", ".bplist", ".wflow"):
        return True
    try:
        head = path.open("rb").read(16)
    except OSError:
        return False
    return head.startswith(b"bplist00") or head.lstrip().startswith(b"<?xml")


def with_extra_suffix(path: Path, extra: str) -> Path:
    if path.suffix:
        return path.with_suffix(path.suffix + extra)
    return path.with_name(path.name + extra)


def convert_plists(root: Path, *, force: bool):
    xml_count = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if not is_plist_candidate(path):
            continue
        out_xml = with_extra_suffix(path, ".xml")
        if out_xml.exists() and not force:
            continue
        try:
            run(["plutil", "-convert", "xml1", "-o", str(out_xml), str(path)])
            xml_count += 1
        except subprocess.CalledProcessError:
            pass
    return xml_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Unpack signed .shortcut files.")
    parser.add_argument("input", help="Path to .shortcut file")
    parser.add_argument("-o", "--out", help="Output directory")
    parser.add_argument("--no-convert", action="store_true", help="Skip plist -> XML conversion")
    parser.add_argument("--force", action="store_true", help="Overwrite existing outputs")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        die(f"input not found: {input_path}")

    outdir = Path(args.out).expanduser().resolve() if args.out else input_path.with_suffix(".unpacked")
    if outdir.exists() and not args.force:
        die(f"output directory exists: {outdir} (use --force to reuse)")
    outdir.mkdir(parents=True, exist_ok=True)

    data = input_path.read_bytes()
    if not data.startswith(b"AEA1"):
        die("input does not look like an AEA archive (missing AEA1 magic). "
            "If it starts with 'bplist00' it's an unsigned shortcut — convert directly with "
            "`plutil -convert xml1 -o out.xml <file>`.")

    auth_plist = read_auth_plist_bytes(data)
    (outdir / "auth.plist").write_bytes(auth_plist)

    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        sign_pub_b64 = extract_sign_pub_base64(auth_plist, workdir)

        aar_path = outdir / (input_path.stem + ".aar")
        if aar_path.exists() and not args.force:
            die(f"output exists: {aar_path} (use --force to overwrite)")

        run(
            [
                "aea",
                "decrypt",
                "-i",
                str(input_path),
                "-o",
                str(aar_path),
                "-sign-pub-value",
                f"base64:{sign_pub_b64}",
            ]
        )

    extracted = outdir / "extracted"
    if extracted.exists() and args.force:
        for p in extracted.rglob("*"):
            if p.is_file():
                p.unlink()
        for p in sorted(extracted.rglob("*"), reverse=True):
            if p.is_dir():
                try:
                    p.rmdir()
                except OSError:
                    pass
    extracted.mkdir(parents=True, exist_ok=True)
    run(["aa", "extract", "-i", str(aar_path), "-d", str(extracted)])

    if not args.no_convert:
        xml_count = convert_plists(extracted, force=args.force)
        print(f"converted {xml_count} plist(s) to XML")

    print(f"done: {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
