#!/usr/bin/env python3
"""Build published images and READMEs for every waypoint.

usage: build.py --manifest PATH --originals DIR

The manifest and originals live outside this repo. Manifest columns:
original,wp,shot,publish

Images use macOS `sips`. Every output has its metadata stripped.
"""
import argparse
import csv
import json
import subprocess
import tempfile
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIDTH = 1600
QUALITY = 68
THUMB_WIDTH = 640
THUMB_QUALITY = 60

# Which shot leads a waypoint, best first.
HERO_ORDER = ("ground", "flight", "hangar", "thrusters", "upgrade")
SHOT_LABELS = {
    "ground": "On the ground",
    "flight": "In flight",
    "hangar": "In the hangar",
    "thrusters": "Thrusters",
    "upgrade": "S-class",
}
GLYPH_NAMES = dict(zip("0123456789ABCDEF", (
    "Sunset", "Bird", "Face", "Diplo", "Eclipse", "Balloon", "Boat", "Bug",
    "Dragonfly", "Galaxy", "Voxel", "Fish", "Tent", "Rocket", "Tree", "Atlas",
)))
GLYPH_NAMES["?"] = "Unknown"
UNKNOWN_PLANET_NOTE = "First glyph (the planet) is unknown: no ground shot at this stop."
GTM_ID = "GTM-WTL7LBSL"
SOCIAL_LINKS = (
    ("Instagram", "https://www.instagram.com/rimtocore/"),
    ("Mastodon", "https://mastodon.social/@rimtocore"),
)
KOFI_URL = "https://ko-fi.com/pelicanism"
TIP_REASON = "Every tip helps me keep hunting Sentinel ships toward the core. A$1 is plenty."
TIP_EASE = "Optional, takes a few seconds, no sign-up needed."
SITE_TITLE = "Rim to Core"
SITE_DESCRIPTION = (
    "A journey from the galactic rim to the core of Euclid in No Man's Sky, "
    "logged one waypoint at a time."
)
FAVICON = (
    "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
    "<circle cx='16' cy='16' r='15' fill='%230b0d14'/>"
    "<circle cx='16' cy='16' r='5' fill='%23f2b84b'/></svg>"
)

# JPEG segments to keep: APP0 (JFIF) and APP2 (ICC colour profile).
KEEP_MARKERS = {0xE0, 0xE2}


def sips(*args):
    subprocess.run(["sips", *map(str, args)], check=True, capture_output=True)


def strip_metadata(data):
    """Return JPEG bytes without EXIF, XMP, comments or other APP segments."""
    if data[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG")
    out = bytearray(data[:2])
    i = 2
    while True:
        if data[i] != 0xFF:
            raise ValueError(f"bad marker at byte {i}")
        marker = data[i + 1]
        if marker == 0xDA:  # start of scan: the rest is image data
            out += data[i:]
            return bytes(out)
        length = int.from_bytes(data[i + 2:i + 4], "big")
        is_app_or_comment = 0xE0 <= marker <= 0xEF or marker == 0xFE
        if not is_app_or_comment or marker in KEEP_MARKERS:
            out += data[i:i + 2 + length]
        i += 2 + length


def process(source, dest):
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "output.jpg"
        sips("-s", "format", "jpeg", "-s", "formatOptions", QUALITY,
             "--resampleWidth", WIDTH, source, "--out", output)
        dest.write_bytes(strip_metadata(output.read_bytes()))


def make_thumbnail(source, dest):
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "thumb.jpg"
        sips("-s", "format", "jpeg", "-s", "formatOptions", THUMB_QUALITY,
             "--resampleWidth", THUMB_WIDTH, source, "--out", output)
        dest.write_bytes(strip_metadata(output.read_bytes()))


def hero_shot(w):
    return next(shot for shot in HERO_ORDER if shot in w["images"])


def slug_of(w):
    return f"wp{w['wp']:02d}"


def social_links():
    # rel="me" lets Mastodon verify the site as the account's own.
    return " · ".join(f'<a href="{url}" rel="me">{name}</a>' for name, url in SOCIAL_LINKS)


def tip_button(placement):
    # A plain link, not Ko-fi's widget script, so the page stays fast.
    # data-placement lets analytics tell the buttons apart.
    return (
        f'<a class="tip-button" href="{KOFI_URL}" target="_blank" rel="noopener noreferrer" '
        f'data-placement="{placement}">Fuel the journey <span aria-hidden="true">☕</span>'
        '<span class="visually-hidden"> – tip on Ko-fi (opens in a new tab)</span></a>'
    )


def site_page(title, description, root, body):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
<link rel="icon" href="{FAVICON}">
<link rel="stylesheet" href="{root}assets/site.css">
</head>
<body>
{body}
<footer class="footer">
  <p class="social">Follow the journey: {social_links()} · <a href="{KOFI_URL}" target="_blank" rel="noopener noreferrer" data-placement="footer">Tip on Ko-fi<span class="visually-hidden"> (opens in a new tab)</span></a></p>
  <p>Screenshots from No Man's Sky by Hello Games. A fan project, not affiliated with the studio.</p>
  <p><button class="link-button" id="consent-settings" type="button" hidden>Analytics settings</button></p>
</footer>
<div class="consent" id="consent" role="region" aria-label="Analytics choice" hidden>
  <p>This site uses Google Analytics cookies to count visits. Is that OK?</p>
  <div class="consent-actions">
    <button id="consent-accept" type="button">Accept</button>
    <button id="consent-decline" type="button">Decline</button>
  </div>
</div>
<script src="{root}assets/consent.js" data-gtm-id="{GTM_ID}" defer></script>
</body>
</html>
"""


def waypoint_card(w):
    slug = slug_of(w)
    change = f"{w['found']['class']} &rarr; S" if w["found"]["class"] else "S-class"
    jump = f"+{number(w['jump_ly'])} LY" if w["jump_ly"] else "Start"
    return f"""<li>
  <a class="card" href="{slug}/">
    <img src="{slug}/{slug}_thumb.jpg" width="640" height="360" loading="lazy" alt="">
    <div class="card-body">
      <p class="card-number">Waypoint {w['wp']}</p>
      <h3>{escape(w['system'])}</h3>
      <p class="card-ship">{escape(w['s_class']['name'])} <span class="class-change">{change}</span></p>
      <p class="card-data"><span>{number(w['ly_from_core'])} LY</span> <span>{jump}</span></p>
    </div>
  </a>
</li>"""


def index_html(waypoints):
    first, latest = waypoints[0], waypoints[-1]
    slug = slug_of(latest)
    travelled = first["ly_from_core"] - latest["ly_from_core"]
    percent = travelled / first["ly_from_core"] * 100
    cards = "\n".join(waypoint_card(w) for w in reversed(waypoints))
    hero = hero_shot(latest)
    hero_alt = escape(f"{SHOT_LABELS[hero]}: {latest['s_class']['name']} at {latest['system']}")
    body = f"""<header class="hero">
  <img class="hero-image" src="{slug}/{slug}_{hero}.jpg" width="1600" height="900" alt="{hero_alt}">
  <div class="hero-text">
    <h1>{SITE_TITLE}</h1>
    <p class="lede">{escape(SITE_DESCRIPTION)}</p>
    <div class="tip">
      {tip_button("hero")}
      <p class="tip-note">{escape(TIP_REASON)} <span class="tip-ease">{TIP_EASE}</span></p>
    </div>
    <a class="latest" href="{slug}/">Latest: {escape(latest['system'])} &rarr;</a>
  </div>
</header>
<main class="page">
  <section class="progress" aria-label="Journey progress">
    <dl class="stats">
      <div><dt>Waypoints</dt><dd>{len(waypoints)}</dd></div>
      <div><dt>Travelled</dt><dd>{number(travelled)} LY</dd></div>
      <div><dt>To the core</dt><dd>{number(latest['ly_from_core'])} LY</dd></div>
    </dl>
    <div class="track" role="img" aria-label="{percent:.1f} percent of the way to the core">
      <span class="track-fill" style="width: {percent:.2f}%"></span>
    </div>
    <p class="track-labels"><span>Rim</span> <span>{percent:.1f}%</span> <span>Core</span></p>
  </section>
  <section aria-labelledby="waypoints-heading">
    <h2 id="waypoints-heading">Waypoints</h2>
    <p class="legend"><span class="class-change">B &rarr; S</span> means the ship was B-class as found, then upgraded to S-class.</p>
    <ol class="cards">
{cards}
    </ol>
  </section>
  <section class="tip-panel" aria-labelledby="tip-heading">
    <h2 id="tip-heading">Enjoying the ride?</h2>
    <p class="tip-note">{escape(TIP_REASON)} <span class="tip-ease">{TIP_EASE}</span></p>
    {tip_button("after-waypoints")}
  </section>
</main>"""
    return site_page(SITE_TITLE, SITE_DESCRIPTION, "", body)


def waypoint_nav(previous, following):
    links = []
    if previous:
        links.append(f'<a href="../{slug_of(previous)}/">&larr; {escape(previous["system"])}</a>')
    else:
        links.append("<span></span>")
    if following:
        links.append(f'<a href="../{slug_of(following)}/">{escape(following["system"])} &rarr;</a>')
    return f'<nav class="pager" aria-label="Waypoints">{"".join(links)}</nav>'


def glyph_row(glyphs):
    if not glyphs:
        return ""
    names = " · ".join(GLYPH_NAMES[g] for g in glyphs)
    note = f'<dd class="glyph-note">{UNKNOWN_PLANET_NOTE}</dd>' if glyphs[0] == "?" else ""
    return (
        '<div><dt>Portal glyphs</dt>'
        f'<dd class="glyph-code">{glyphs}</dd>'
        f'<dd class="glyph-names">{names}</dd>{note}</div>\n'
    )


def waypoint_html(w, previous, following):
    slug = slug_of(w)
    s = w["s_class"]
    found = found_label(w["found"]) if w["found"]["class"] else None
    jump = f"{number(w['jump_ly'])} LY" if w["jump_ly"] else None
    facts = [
        ("Distance from core", f"{number(w['ly_from_core'])} LY"),
        ("Jump from previous", jump),
        ("Planet coordinates", w["planet_coords"]),
        ("Ship as found", found),
        ("S-class ship", s["name"]),
        ("Damage", s["damage"]),
        ("Shield", s["shield"]),
        ("Hyperdrive", s["hyperdrive"]),
        ("Manoeuvrability", s["manoeuvrability"]),
    ]
    fact_rows = "\n".join(
        f"<div><dt>{label}</dt><dd>{escape(str(value))}</dd></div>"
        for label, value in facts if value is not None
    )
    fact_rows = glyph_row(w["glyphs"]) + fact_rows
    hero = hero_shot(w)
    shots = [hero] + [shot for shot in w["images"] if shot != hero]
    figures = []
    for shot in shots:
        loading = "" if shot == hero else ' loading="lazy"'
        alt = escape(f"{SHOT_LABELS[shot]}: {s['name']} at {w['system']}")
        figures.append(
            f'<figure><img src="{slug}_{shot}.jpg" width="1600" height="900"{loading} alt="{alt}">'
            f"<figcaption>{SHOT_LABELS[shot]}</figcaption></figure>"
        )
    figures = "\n".join(figures)
    caption = f'<p class="caption">{escape(w["caption"])}</p>' if w["caption"] else ""
    body = f"""<main class="page waypoint">
  <a class="home" href="../">&larr; {SITE_TITLE}</a>
  <p class="eyebrow">Waypoint {w['wp']}</p>
  <h1>{escape(w['system'])}</h1>
  {caption}
  <div class="waypoint-layout">
    <div class="gallery">
{figures}
    </div>
    <dl class="facts">
{fact_rows}
    </dl>
  </div>
  {waypoint_nav(previous, following)}
</main>"""
    title = f"{w['system']} | {SITE_TITLE}"
    description = f"Waypoint {w['wp']} of the Rim to Core journey: the {s['name']} at {w['system']}."
    return site_page(title, description, "../", body)


def number(value):
    return "–" if value is None else f"{value:,}"


def s_class_stats(s):
    fields = (("Damage", "damage"), ("Shield", "shield"),
              ("Hyperdrive", "hyperdrive"), ("Manoeuvrability", "manoeuvrability"))
    return " · ".join(f"{label} {s[key]}" for label, key in fields)


def found_label(found):
    if found["class"] is None:
        return "–"
    return f"{found['class']}-class, {found['slots']} slots"


def waypoint_readme(w):
    slug = f"wp{w['wp']:02d}"
    lines = [
        f"# Waypoint {w['wp']}: {w['system']}", "",
        "| | |", "|---|---|",
        f"| Galaxy | {w['galaxy']} |",
        f"| Distance from core | {number(w['ly_from_core'])} LY |",
        f"| Jump from previous | {number(w['jump_ly'])} LY |",
        f"| Planet coordinates | {w['planet_coords'] or '–'} |",
        f"| Glyphs | {w['glyphs'] or '–'} |",
        f"| Ship as found | {found_label(w['found'])} |",
        f"| S-class ship | {w['s_class']['name']} |",
        f"| S-class stats | {s_class_stats(w['s_class'])} |",
        "",
    ]
    if w["glyphs"] and w["glyphs"][0] == "?":
        lines += [f"> {UNKNOWN_PLANET_NOTE}", ""]
    if w["notes"]:
        lines += [f"> {w['notes']}", ""]
    lines += [f"![{shot}]({slug}_{shot}.jpg)\n" for shot in w["images"]]
    lines += ["## Caption", "", w["caption"] or "_Not written yet._", ""]
    return "\n".join(lines)


def top_readme(waypoints):
    lines = [
        "# Rim to Core", "",
        "A journey from the galactic rim to the core of Euclid in No Man's Sky,",
        "logged one waypoint at a time.", "",
        "| # | System | LY from core | Jump | Found | S-class ship |",
        "|---|---|---|---|---|---|",
    ]
    for w in waypoints:
        slug = f"wp{w['wp']:02d}"
        lines.append(
            f"| [{w['wp']}]({slug}/) | {w['system']} | {number(w['ly_from_core'])} "
            f"| {number(w['jump_ly'])} | {found_label(w['found'])} "
            f"| {w['s_class']['name']} |"
        )
    lines += ["", "Data lives in [`waypoints.json`](waypoints.json).", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--originals", required=True, type=Path)
    args = parser.parse_args()

    with args.manifest.open(newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["publish"] == "1"]
    for row in rows:
        folder = ROOT / f"wp{int(row['wp']):02d}"
        folder.mkdir(exist_ok=True)
        dest = folder / f"{folder.name}_{row['shot']}.jpg"
        process(args.originals / row["original"], dest)

    waypoints = json.loads((ROOT / "waypoints.json").read_text())
    for i, w in enumerate(waypoints):
        folder = ROOT / slug_of(w)
        make_thumbnail(folder / f"{folder.name}_{hero_shot(w)}.jpg",
                       folder / f"{folder.name}_thumb.jpg")
        (folder / "README.md").write_text(waypoint_readme(w))
        previous = waypoints[i - 1] if i else None
        following = waypoints[i + 1] if i + 1 < len(waypoints) else None
        (folder / "index.html").write_text(waypoint_html(w, previous, following))
    (ROOT / "README.md").write_text(top_readme(waypoints))
    (ROOT / "index.html").write_text(index_html(waypoints))
    (ROOT / ".nojekyll").touch()
    print(f"{len(rows)} images, {len(waypoints)} waypoints")


if __name__ == "__main__":
    main()
