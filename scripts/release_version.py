import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "version": ROOT / "VERSION",
    "env_example": ROOT / ".env.example",
    "compose": ROOT / "docker-compose.yml",
    "readme_ru": ROOT / "README.md",
    "readme_en": ROOT / "README.en.md",
    "changelog": ROOT / "CHANGELOG.md",
}


def write_text(path, text):
    path.write_text(text, encoding="utf-8")


def replace_exact(path, pattern, replacement, expected_count=1):
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
    if count != expected_count:
        raise SystemExit(f"{path}: expected {expected_count} replacements for {pattern!r}, got {count}")
    write_text(path, updated)


def replace_min(path, pattern, replacement, min_count=1):
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
    if count < min_count:
        raise SystemExit(f"{path}: expected at least {min_count} replacements for {pattern!r}, got {count}")
    write_text(path, updated)


def prepend_changelog(version, date_text):
    path = FILES["changelog"]
    text = path.read_text(encoding="utf-8")
    header = f"## {version} - {date_text}"
    if header in text:
        return
    insertion = f"# Changelog\n\n{header}\n\n- \n\n"
    if not text.startswith("# Changelog\n"):
        raise SystemExit(f"{path}: unexpected header")
    write_text(path, insertion + text[len("# Changelog\n\n"):])


def update_version(version, date_text=None, add_changelog=False):
    write_text(FILES["version"], f"{version}\n")
    replace_exact(FILES["env_example"], r"^BGP_ANTIFILTER_VERSION=.*$", f"BGP_ANTIFILTER_VERSION={version}")
    replace_min(
        FILES["compose"],
        r'bgp-antifilter-bird:\$\{BGP_ANTIFILTER_VERSION:-[^}]+\}',
        f'bgp-antifilter-bird:${{BGP_ANTIFILTER_VERSION:-{version}}}',
        min_count=2,
    )
    replace_min(FILES["readme_ru"], r"BGP_ANTIFILTER_VERSION=\d+\.\d+\.\d+", f"BGP_ANTIFILTER_VERSION={version}")
    replace_min(FILES["readme_ru"], r"по умолчанию `\d+\.\d+\.\d+`", f"по умолчанию `{version}`")
    replace_min(FILES["readme_en"], r"BGP_ANTIFILTER_VERSION=\d+\.\d+\.\d+", f"BGP_ANTIFILTER_VERSION={version}")
    replace_min(FILES["readme_en"], r"defaults to `\d+\.\d+\.\d+`", f"defaults to `{version}`")
    if add_changelog:
        if not date_text:
            raise SystemExit("--date is required with --add-changelog")
        prepend_changelog(version, date_text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("version", help="Release version, for example 0.2.4")
    parser.add_argument("--date", help="Changelog date in YYYY-MM-DD format")
    parser.add_argument("--add-changelog", action="store_true", help="Prepend a new empty changelog section if missing")
    args = parser.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        raise SystemExit("version must use MAJOR.MINOR.PATCH format")
    update_version(args.version, date_text=args.date, add_changelog=args.add_changelog)


if __name__ == "__main__":
    main()
