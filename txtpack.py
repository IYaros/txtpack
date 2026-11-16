#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""txtpack - собирает out/<папка>.zip, в котором все файлы папки (рекурсивно) имеют
расширение .txt; структура подпапок сохраняется, карта исходных имён — extensions.txt —
лежит внутри архива. Исходная папка не меняется.

unpack смотрит только в out: распаковывает каждый архив в out/<имя архива>/ и возвращает
исходные имена и структуру. config.ini нужен только для pack.

Папка берётся из config.ini (path=...) или из аргумента: txtpack.py pack "D:\\папка".
Режимы: pack, unpack.
"""

import shutil
import sys
import zipfile
from pathlib import Path

MANIFEST = "extensions.txt"


def fail(message):
    print(message)
    sys.exit(1)


def configure_output():
    for stream in (sys.stdout, sys.stderr):
        if not stream.isatty():
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                pass


def read_config(tool_dir):
    config = tool_dir / "config.ini"
    if not config.exists():
        fail("Не найден config.ini: %s" % config)
    value = ""
    for line in config.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line or line[0] in ";#":
            continue
        key, _, val = line.partition("=")
        if key.strip().lower() == "path":
            value = val.strip().strip('"').strip("'")
    if not value:
        fail("Укажите папку в config.ini, например: path=D:\\Photos")
    path = Path(value)
    return path if path.is_absolute() else tool_dir / path


def is_under(path, base):
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def walk_files(root, excluded):
    return sorted((p for p in root.rglob("*") if p.is_file() and not excluded(p)), key=str)


def leaf_name(root):
    return root.name or "archive"


def pack(root, out_dir, excluded):
    files = walk_files(root, excluded)
    if not files:
        fail("Нет файлов для обработки: %s" % root)

    leaf = leaf_name(root)
    mapping = []
    entries = []          # (файл на диске, имя в архиве относительно папки)
    used = set()
    for path in files:
        rel_old = path.relative_to(root)
        if path.suffix.lower() == ".txt":
            entries.append((path, rel_old))
            continue
        base = path.stem or path.name
        rel_dir = rel_old.parent
        new_name = base + ".txt"
        counter = 1
        while (rel_dir / new_name) in used or (path.parent / new_name).exists():
            new_name = "%s_%d.txt" % (base, counter)
            counter += 1
        rel_new = rel_dir / new_name
        used.add(rel_new)
        entries.append((path, rel_new))
        mapping.append("%s\t%s" % (rel_new, rel_old))

    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / ("%s.zip" % leaf)
    if not mapping and archive.exists():
        fail("В папке нет файлов с другими расширениями, а архив уже есть: %s\nУдалите его, если хотите перезаписать." % archive)
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, rel in entries:
            zf.write(path, "%s/%s" % (leaf, rel.as_posix()))
        if mapping:
            zf.writestr(MANIFEST, "\n".join(mapping) + "\n")  # карта имён - в корне архива

    print("Файлов в архиве: %d" % len(entries))
    if mapping:
        print("Переименовано в .txt: %d" % len(mapping))
    print("Архив: %s" % archive)


def unpack_archive(archive, out_dir):
    stem = archive.stem
    stage = out_dir / ".unpack"
    if stage.exists():
        shutil.rmtree(stage)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(stage)

    src_root = stage / stem
    if not src_root.is_dir():
        dirs = [p for p in stage.iterdir() if p.is_dir()]
        files = [p for p in stage.iterdir() if p.is_file() and p.name != MANIFEST]
        src_root = dirs[0] if len(dirs) == 1 and not files else stage

    map_file = stage / MANIFEST
    if not map_file.is_file():
        map_file = src_root / MANIFEST
    mapping = {}
    if map_file.is_file():
        for line in map_file.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            current, _, original = line.partition("\t")
            if original:
                mapping[current] = original

    target = out_dir / stem
    if target.exists():
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    target.mkdir(parents=True, exist_ok=True)

    restored = 0
    for path in sorted(src_root.rglob("*")):
        if not path.is_file() or path == map_file:
            continue
        rel = str(path.relative_to(src_root))
        dest = target / mapping.get(rel, rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(path), str(dest))
        restored += 1

    if stage.exists():
        shutil.rmtree(stage)
    return restored


def unpack(out_dir):
    archives = sorted(out_dir.glob("*.zip")) if out_dir.is_dir() else []
    if not archives:
        fail("В out нет архивов: %s" % out_dir)
    for archive in archives:
        count = unpack_archive(archive, out_dir)
        print("Распаковано: %s -> %s (%d файлов)" % (archive.name, out_dir / archive.stem, count))


def main():
    configure_output()
    mode = (sys.argv[1] if len(sys.argv) > 1 else "pack").lower()
    if mode not in ("pack", "unpack"):
        fail("Неизвестный режим: %s (нужно pack или unpack)" % mode)

    tool_dir = Path(__file__).resolve().parent
    out_dir = tool_dir / "out"

    if mode == "pack":
        raw_path = sys.argv[2] if len(sys.argv) > 2 else ""
        root = Path(raw_path) if raw_path else read_config(tool_dir)
        root = root.resolve()
        if root.is_file():
            fail("В config.ini нужна папка, а не файл: %s" % root)
        if not root.is_dir():
            fail("Папка не найдена: %s" % root)
        pack(root, out_dir, lambda path: is_under(path, out_dir))
    else:
        unpack(out_dir)


if __name__ == "__main__":
    main()
