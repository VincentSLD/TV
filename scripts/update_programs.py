#!/usr/bin/env python3
"""
Fetch French TV schedules from xmltvfr.fr and generate programs.json
for the 25 TNT channels.
"""

import gzip
import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

XMLTV_URL = "https://xmltvfr.fr/xmltv/xmltv_local.xml.gz"
OUTPUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "programs.json")

# TNT channels: display-name patterns -> our channel config
CHANNELS = [
    {"match": ["TF1"],                   "num": "TF1",  "name": "TF1",              "color": "#1a6fd4"},
    {"match": ["France 2"],              "num": "F2",   "name": "France 2",          "color": "#d41a1a"},
    {"match": ["France 3"],              "num": "F3",   "name": "France 3",          "color": "#d47a1a"},
    {"match": ["Canal+", "Canal +"],     "num": "C+",   "name": "Canal+",            "color": "#222222"},
    {"match": ["France 5"],              "num": "F5",   "name": "France 5",          "color": "#1aad6d"},
    {"match": ["M6"],                    "num": "M6",   "name": "M6",                "color": "#e6a800"},
    {"match": ["Arte"],                  "num": "ART",  "name": "Arte",              "color": "#6b3fa0"},
    {"match": ["C8"], "match_id": ["D8.fr", "C8.fr"],  "num": "C8",   "name": "C8",   "color": "#c0392b"},
    {"match": ["W9"],                    "num": "W9",   "name": "W9",                "color": "#e84393"},
    {"match": ["TMC"],                   "num": "TMC",  "name": "TMC",               "color": "#1a8fd4"},
    {"match": ["TFX"],                   "num": "TFX",  "name": "TFX",               "color": "#2ecc71"},
    {"match": ["NRJ 12", "NRJ12"], "match_id": ["NRJ12.fr"],  "num": "NRJ",  "name": "NRJ 12",  "color": "#ff6600"},
    {"match": ["LCP"],                   "num": "LCP",  "name": "LCP",               "color": "#003580"},
    {"match": ["France 4"],              "num": "F4",   "name": "France 4",          "color": "#c0392b"},
    {"match": ["BFMTV", "BFM TV"],       "num": "BFM",  "name": "BFM TV",            "color": "#e30614"},
    {"match": ["CNews", "CNEWS"],        "num": "CNW",  "name": "CNews",             "color": "#004a9f"},
    {"match": ["CStar", "CSTAR"],        "num": "CST",  "name": "CSTAR",             "color": "#ff3366"},
    {"match": ["Gulli"],                 "num": "GUL",  "name": "Gulli",             "color": "#f7a800"},
    {"match": ["TF1 Séries-Films", "TF1 Séries Films", "TF1 Series Films"], "num": "TSF", "name": "TF1 Séries Films", "color": "#0066cc"},
    {"match": ["La chaine l'équipe", "La chaîne L'Équipe", "L'Équipe", "L'Equipe"], "match_id": ["LEquipe21.fr"], "num": "EQP", "name": "L'Équipe", "color": "#1a1a1a"},
    {"match": ["6ter"],                  "num": "6TR",  "name": "6ter",              "color": "#e6a800"},
    {"match": ["RMC Story", "RMC STORY"],"num": "RMS",  "name": "RMC Story",         "color": "#2c3e50"},
    {"match": ["RMC Découverte", "RMC Decouverte"], "num": "RMD", "name": "RMC Découverte", "color": "#16a085"},
]

GENRE_MAP = {
    "journal": "info", "information": "info", "actualité": "info", "débat": "info",
    "politique": "info", "météo": "info", "news": "info",
    "film": "film", "cinéma": "film", "téléfilm": "film",
    "série": "serie", "feuilleton": "serie", "fiction": "serie", "sitcom": "serie",
    "sport": "sport", "football": "sport", "rugby": "sport", "tennis": "sport",
    "documentaire": "documentaire", "découverte": "documentaire", "nature": "documentaire",
    "histoire": "documentaire", "science": "documentaire", "reportage": "documentaire",
    "musique": "musique", "concert": "musique", "clip": "musique",
    "divertissement": "divertissement", "jeu": "divertissement", "magazine": "divertissement",
    "humour": "divertissement", "talk-show": "divertissement", "variétés": "divertissement",
    "jeunesse": "divertissement", "animation": "divertissement", "dessin animé": "divertissement",
}


def classify_genre(categories):
    """Map XMLTV categories to our genre system."""
    for cat in categories:
        cat_lower = cat.lower()
        for keyword, genre in GENRE_MAP.items():
            if keyword in cat_lower:
                return genre
    return "divertissement"


def parse_xmltv_time(timestr):
    """Parse XMLTV datetime like '20260321060000 +0100'."""
    timestr = timestr.strip()
    # Handle format: YYYYMMDDHHmmSS +HHMM
    dt_part = timestr[:14]
    tz_part = timestr[14:].strip()

    dt = datetime.strptime(dt_part, "%Y%m%d%H%M%S")

    if tz_part:
        sign = 1 if tz_part[0] == '+' else -1
        tz_hours = int(tz_part[1:3])
        tz_mins = int(tz_part[3:5])
        tz = timezone(timedelta(hours=sign * tz_hours, minutes=sign * tz_mins))
        dt = dt.replace(tzinfo=tz)

    return dt


def main():
    print(f"Fetching XMLTV data from {XMLTV_URL}...")

    # Try local file first, then smaller file, then full file
    urls_to_try = [
        XMLTV_URL,
        "https://xmltvfr.fr/xmltv/xmltv.xml.gz",
    ]

    xml_data = None
    for url in urls_to_try:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TV-Guide/1.0"})
            with urllib.request.urlopen(req, timeout=120) as response:
                compressed = response.read()
                xml_data = gzip.decompress(compressed)
                print(f"Downloaded from {url} ({len(compressed)} bytes compressed, {len(xml_data)} bytes raw)")
                break
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")

    if xml_data is None:
        print("ERROR: Could not fetch XMLTV data from any source")
        sys.exit(1)

    print("Parsing XML...")
    root = ET.fromstring(xml_data)

    # Build channel ID -> display names mapping
    channel_names = {}
    for ch_elem in root.findall("channel"):
        ch_id = ch_elem.get("id")
        names = [dn.text for dn in ch_elem.findall("display-name") if dn.text]
        channel_names[ch_id] = names

    # Match XMLTV channel IDs to our channels
    channel_id_map = {}  # xmltv_id -> index in CHANNELS
    matched_indices = set()
    for ch_id, names in channel_names.items():
        for i, ch_conf in enumerate(CHANNELS):
            if i in matched_indices:
                continue
            found = False
            # Match by channel ID
            for mid in ch_conf.get("match_id", []):
                if mid.lower() == ch_id.lower():
                    channel_id_map[ch_id] = i
                    matched_indices.add(i)
                    found = True
                    break
            if found:
                break
            # Match by display name
            for match_name in ch_conf["match"]:
                for name in names:
                    if match_name.lower() == name.lower().strip():
                        channel_id_map[ch_id] = i
                        matched_indices.add(i)
                        found = True
                        break
                if found:
                    break
            if found:
                break

    print(f"Matched {len(channel_id_map)} channels out of {len(CHANNELS)}")
    for ch_id, idx in sorted(channel_id_map.items(), key=lambda x: x[1]):
        print(f"  {CHANNELS[idx]['name']} -> {ch_id} ({channel_names.get(ch_id, ['?'])})")

    # Get today and next 5 days in local timezone (Paris)
    paris_tz = timezone(timedelta(hours=1))  # CET (simplified)
    now = datetime.now(paris_tz)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Collect programs per day per channel
    # days: -1 (yesterday), 0 (today), 1 (tomorrow), ... 5
    days_data = {}
    for day_offset in range(-1, 6):
        day_key = (today + timedelta(days=day_offset)).strftime("%Y-%m-%d")
        days_data[day_key] = {i: [] for i in range(len(CHANNELS))}

    print("Extracting programs...")
    program_count = 0
    for prog in root.findall("programme"):
        ch_id = prog.get("channel")
        if ch_id not in channel_id_map:
            continue

        ch_idx = channel_id_map[ch_id]
        start_str = prog.get("start")
        stop_str = prog.get("stop")

        if not start_str or not stop_str:
            continue

        try:
            start_dt = parse_xmltv_time(start_str)
            stop_dt = parse_xmltv_time(stop_str)
        except Exception:
            continue

        # Convert to Paris time
        start_local = start_dt.astimezone(paris_tz)
        stop_local = stop_dt.astimezone(paris_tz)

        # Determine which day this program belongs to (6AM cutoff)
        prog_day = start_local.replace(hour=0, minute=0, second=0, microsecond=0)
        if start_local.hour < 6:
            prog_day -= timedelta(days=1)

        day_key = prog_day.strftime("%Y-%m-%d")
        if day_key not in days_data:
            continue

        # Extract program info
        title_elem = prog.find("title")
        title = title_elem.text if title_elem is not None and title_elem.text else "Programme"

        desc_elem = prog.find("desc")
        desc = desc_elem.text if desc_elem is not None and desc_elem.text else ""
        # Truncate long descriptions
        if len(desc) > 200:
            desc = desc[:197] + "..."

        categories = [c.text for c in prog.findall("category") if c.text]
        genre = classify_genre(categories)

        # Start time as HHMM integer
        start_hhmm = start_local.hour * 100 + start_local.minute
        # Handle post-midnight (make it 24xx, 25xx)
        if start_local.hour < 6 and prog_day.strftime("%Y-%m-%d") == day_key:
            start_hhmm = (start_local.hour + 24) * 100 + start_local.minute

        # Duration in minutes
        duration = int((stop_dt - start_dt).total_seconds() / 60)
        if duration <= 0:
            continue
        # Cap very long programs
        if duration > 360:
            duration = 360

        days_data[day_key][ch_idx].append({
            "start": start_hhmm,
            "title": title,
            "genre": genre,
            "desc": desc,
            "dur": duration,
        })
        program_count += 1

    print(f"Extracted {program_count} programs")

    # Sort programs by start time within each channel/day
    for day_key in days_data:
        for ch_idx in days_data[day_key]:
            days_data[day_key][ch_idx].sort(key=lambda p: p["start"])

    # Build output JSON
    output = {
        "updated": now.isoformat(),
        "channels": [],
        "days": {},
    }

    for ch in CHANNELS:
        output["channels"].append({
            "num": ch["num"],
            "name": ch["name"],
            "color": ch["color"],
        })

    for day_key, ch_progs in days_data.items():
        day_programs = []
        for ch_idx in range(len(CHANNELS)):
            progs = ch_progs.get(ch_idx, [])
            # Convert to compact array format: [start, title, genre, desc, dur]
            compact = [[p["start"], p["title"], p["genre"], p["desc"], p["dur"]] for p in progs]
            day_programs.append(compact)
        output["days"][day_key] = day_programs

    # Write JSON
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    file_size = os.path.getsize(OUTPUT)
    print(f"Written {OUTPUT} ({file_size} bytes)")
    print("Done!")


if __name__ == "__main__":
    main()
