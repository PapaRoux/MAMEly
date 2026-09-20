#!/usr/bin/env python3
"""Link MAME-softlist-named video snaps (10yard.mp4) to your real ROM filenames.

Video packs taken from MAME's software lists are named by softlist short name,
but MAMEly looks for <rom name>.mp4 (e.g. "10-Yard Fight (J) [o1].mp4"). This
maps each short name to its full title via MAME's hash/<list>.xml, fuzzy-matches
that title against your ROM filenames, and creates <rom name>.mp4 in the
platform's video/ folder. The original videos are never moved or modified.

Default is a dry run. Nothing on disk changes without --apply.

    python3 link_softlist_videos.py                # dry run, writes report
    python3 link_softlist_videos.py --apply        # create the links

Sequel numbers must agree ("Act Raiser 2" never takes "Act Raiser"'s video).
Anything below --threshold is left alone and listed in the report; fix those
with an overrides file (tab-separated: ROM name or stem, video short name).
"""
import argparse
import os
import re
import shutil
import sys
import unicodedata
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher

ROMAN = {
    "ii": 2, "iii": 3, "iv": 4, "vi": 6, "vii": 7, "viii": 8, "ix": 9,
    "xi": 11, "xii": 12, "xiii": 13, "xiv": 14, "xv": 15,
}
ARTICLES = {"the", "a", "an"}
# GoodTools region letters -> word found in softlist descriptions, e.g. "(USA, Europe)"
REGION_CODES = {
    "U": "usa", "J": "japan", "E": "europe", "W": "world", "A": "australia",
    "K": "korea", "C": "china", "F": "france", "G": "germany", "S": "spain",
    "I": "italy", "B": "brazil",
}
REGION_GROUP = re.compile(r"^[UJEWAKCFGSIB]{1,4}$")
# No region on the ROM: prefer these, in order.
DEFAULT_REGION_PREF = ("usa", "world", "europe")
VARIANT_WORDS = re.compile(r"proto|beta|demo|sample|unl|pirate|bootleg", re.I)


def normalize(name, is_file=False):
    """Return (key, numbers, regions) for a ROM filename or softlist title."""
    text = os.path.splitext(name)[0] if is_file else name
    # Fold accents and symbols: "Déjà Vu" -> "Deja Vu", "Alien³" -> "Alien3", "720°" -> "720".
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    regions = set()
    for group in re.findall(r"\(([^)]*)\)", text):
        g = group.strip()
        if REGION_GROUP.match(g):
            regions.update(REGION_CODES[c] for c in g)
        else:
            low = g.lower()
            regions.update(w for w in REGION_CODES.values() if w in low)
    text = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", text)
    text = text.lower().replace("&", " and ").replace("'", "")
    # Letters and digits split apart so "Goonies2" carries its sequel number.
    tokens = re.findall(r"[a-z]+|[0-9]+", text)
    tokens = [t for t in tokens if t not in ARTICLES]
    tokens = [str(ROMAN[t]) if t in ROMAN else t for t in tokens]
    numbers = tuple(t for t in tokens if t.isdigit())
    return "".join(tokens), numbers, regions


def load_titles(hash_dir, lists):
    titles = {}
    for lst in lists:
        path = os.path.join(hash_dir, lst + ".xml")
        if not os.path.exists(path):
            sys.exit(f"softlist not found: {path}")
        for sw in ET.parse(path).getroot().iter("software"):
            titles.setdefault(sw.get("name"), sw.findtext("description") or "")
    return titles


def region_bonus(rom_regions, video_desc):
    desc = video_desc.lower()
    if rom_regions:
        return 0.02 if any(r in desc for r in rom_regions) else 0.0
    for rank, word in enumerate(DEFAULT_REGION_PREF):
        if word in desc:
            return 0.01 - rank * 0.003
    return 0.0


def read_overrides(path):
    overrides = {}
    if not path:
        return overrides
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            rom, _, vid = line.partition("\t")
            overrides[os.path.splitext(rom.strip())[0]] = vid.strip().removesuffix(".mp4")
    return overrides


def build_video_index(video_dir, titles, video_ext):
    index, untitled = [], []
    for fname in sorted(os.listdir(video_dir)):
        stem, ext = os.path.splitext(fname)
        if ext.lower() != video_ext:
            continue
        desc = titles.get(stem)
        if desc is None:
            untitled.append(stem)
            continue
        key, numbers, _ = normalize(desc)
        index.append({"short": stem, "file": fname, "desc": desc,
                      "key": key, "numbers": numbers})
    return index, untitled


def match_rom(rom_file, index, threshold, review_floor):
    """Return (status, video, score, suggestion) for one ROM filename."""
    key, numbers, regions = normalize(rom_file, is_file=True)
    if not key:
        return "NONE", None, 0.0, None
    sm = SequenceMatcher(None, autojunk=False)
    sm.set_seq2(key)
    best_ok = best_any = None  # (adjusted, raw, video)
    for v in index:
        sm.set_seq1(v["key"])
        if sm.real_quick_ratio() < review_floor or sm.quick_ratio() < review_floor:
            continue
        raw = sm.ratio()
        if raw < review_floor:
            continue
        adj = raw + region_bonus(regions, v["desc"])
        if VARIANT_WORDS.search(v["desc"]):
            adj -= 0.02
        cand = (adj, raw, v)
        if best_any is None or adj > best_any[0]:
            best_any = cand
        if v["numbers"] == numbers and (best_ok is None or adj > best_ok[0]):
            best_ok = cand
    if best_ok and best_ok[1] >= threshold:
        return "MATCH", best_ok[2], best_ok[1], None
    if best_any:
        return "REVIEW", None, best_any[1], best_any[2]
    return "NONE", None, 0.0, None


def make_link(src, dst, mode):
    if mode == "symlink":
        # Relative, so the link survives a different mount point (mini: /mnt/nfs/8TB).
        os.symlink(os.path.relpath(src, os.path.dirname(dst)), dst)
    elif mode == "hardlink":
        os.link(src, dst)
    else:
        shutil.copy2(src, dst)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--softlist", default="nes",
                    help="MAME softlist name(s), comma separated (default: nes)")
    ap.add_argument("--hash-dir", default="/usr/share/games/mame/hash")
    ap.add_argument("--videos", default="/mnt/8TB/platforms/mame/roms_etc/video/nes",
                    help="folder of softlist-named videos")
    ap.add_argument("--roms", default="/mnt/8TB/platforms/nes/roms")
    ap.add_argument("--out", default="/mnt/8TB/platforms/nes/video",
                    help="platform video folder (romVideoDirectory)")
    ap.add_argument("--rom-ext", default=".nes")
    ap.add_argument("--video-ext", default=".mp4")
    ap.add_argument("--threshold", type=float, default=0.90,
                    help="minimum title similarity to link (default 0.90)")
    ap.add_argument("--review-floor", type=float, default=0.70,
                    help="closest misses at or above this are listed for review")
    ap.add_argument("--accept-review", action="store_true",
                    help="also link the closest suggestion for REVIEW rows (marked ACCEPTED)")
    ap.add_argument("--overrides", help="TSV: ROM name/stem <TAB> video short name")
    ap.add_argument("--mode", choices=("symlink", "hardlink", "copy"), default="symlink")
    ap.add_argument("--apply", action="store_true", help="create the links (default: dry run)")
    ap.add_argument("--force", action="store_true",
                    help="replace existing symlinks that point somewhere else")
    ap.add_argument("--report", default="video_match_report.tsv")
    args = ap.parse_args()

    rom_ext = args.rom_ext.lower()
    video_ext = args.video_ext.lower()
    titles = load_titles(args.hash_dir, [s for s in args.softlist.split(",") if s])
    index, untitled = build_video_index(args.videos, titles, video_ext)
    by_short = {v["short"]: v for v in index}
    overrides = read_overrides(args.overrides)
    roms = sorted(f for f in os.listdir(args.roms) if f.lower().endswith(rom_ext))

    rows, counts = [], {"MATCH": 0, "OVERRIDE": 0, "ACCEPTED": 0, "REVIEW": 0, "NONE": 0}
    used = {}
    for rom in roms:
        stem = os.path.splitext(rom)[0]
        if stem in overrides:
            vid = by_short.get(overrides[stem])
            if vid:
                status, video, score, sugg = "OVERRIDE", vid, 1.0, None
            else:
                status, video, score, sugg = "NONE", None, 0.0, None
                print(f"override for '{stem}' names unknown video '{overrides[stem]}'",
                      file=sys.stderr)
        else:
            status, video, score, sugg = match_rom(
                rom, index, args.threshold, args.review_floor)
            if status == "REVIEW" and args.accept_review and sugg:
                status, video, sugg = "ACCEPTED", sugg, None
        counts[status] += 1
        rows.append((rom, status, score, video, sugg))
        if video:
            used[video["short"]] = used.get(video["short"], 0) + 1

    # Apply
    results = {"linked": 0, "already": 0, "skipped_exists": 0, "replaced": 0}
    if args.apply:
        os.makedirs(args.out, exist_ok=True)
    for rom, status, score, video, sugg in rows:
        if not video:
            continue
        stem = os.path.splitext(rom)[0]
        src = os.path.join(args.videos, video["file"])
        dst = os.path.join(args.out, stem + video_ext)
        if os.path.lexists(dst):
            if os.path.islink(dst):
                same = os.path.realpath(dst) == os.path.realpath(src)
                if same:
                    results["already"] += 1
                    continue
                if not args.force:
                    results["skipped_exists"] += 1
                    continue
                if args.apply:
                    os.unlink(dst)
                results["replaced"] += 1
            else:
                results["skipped_exists"] += 1  # never touch a real file
                continue
        if args.apply:
            make_link(src, dst, args.mode)
        results["linked"] += 1

    with open(args.report, "w", encoding="utf-8") as f:
        f.write("status\tscore\trom\tvideo_short\tvideo_title\tsuggestion_short\tsuggestion_title\n")
        order = {"REVIEW": 0, "NONE": 1, "ACCEPTED": 2, "OVERRIDE": 3, "MATCH": 4}
        for rom, status, score, video, sugg in sorted(rows, key=lambda r: (order[r[1]], r[0])):
            f.write("\t".join([
                status, f"{score:.3f}", rom,
                video["short"] if video else "", video["desc"] if video else "",
                sugg["short"] if sugg else "", sugg["desc"] if sugg else "",
            ]) + "\n")

    matched = counts["MATCH"] + counts["OVERRIDE"] + counts["ACCEPTED"]
    print(f"ROMs: {len(roms)}   videos with titles: {len(index)}"
          f"   videos not in softlist: {len(untitled)}")
    print(f"matched {matched} (overrides {counts['OVERRIDE']}, accepted from review "
          f"{counts['ACCEPTED']}) | review {counts['REVIEW']} | no match {counts['NONE']}")
    unused = len(index) - len(used)
    print(f"videos used: {len(used)}   unused: {unused}")
    verb = "" if args.apply else "would be "
    print(f"links {verb}created: {results['linked']}   already correct: {results['already']}"
          f"   skipped (destination exists): {results['skipped_exists']}"
          + (f"   replaced: {results['replaced']}" if results['replaced'] else ""))
    print(f"report: {args.report}")
    if not args.apply:
        print("dry run: nothing written. Re-run with --apply to create links.")


if __name__ == "__main__":
    main()
