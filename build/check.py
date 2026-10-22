"""Validates ../data.js against the raw sources (forum posts, Zombie Slayer sheet, wiki), row by row.
Run after build.py: python3 build/check.py. Uses build/cache; prints each check with its failures."""
import csv
import io
import json
import re
import subprocess
from collections import Counter

import build as b

s = (b.HERE.parent / "data.js").read_text(encoding="utf8")
ROWS = json.loads(s[s.index("["):s.rindex("]") + 1])
OCT15 = b.first_post_text(b.fetch(b.OCT15, "oct15.html"))
OCT22 = b.first_post_text(b.fetch("https://hypixel.net/threads/october-22-magic-find-rework-testing-2.6164761/", "oct22.html"))
results = []


def check(name, fails, total):
    results.append((name, len(fails), total))
    print(f"\n[{'OK ' if not fails else 'BAD'}] {name}: {total - len(fails)}/{total} pass")
    for f in fails[:200]:
        print("   ", f)


def close(a, b_):
    return a is not None and b_ is not None and abs(a - b_) <= 1e-9 + 1e-6 * abs(b_)


def pct(s):
    """First chance in a wiki/forum chance string -> fraction (handles 1/50k, 0.5%, {{Green|2%}})."""
    s = re.sub(r"\{\{\w+\|([^{}|]*)\}\}", r"\1", s)
    return b.parse_chance(s)


def bare(item):
    item = re.sub(r"^(COMMON|UNCOMMON|RARE|EPIC|LEGENDARY|MYTHIC) ", "", item)
    return re.sub(r" \(was .*\)$", "", item).lower().replace("’", "'")


# 1. Every row is well-formed and its status matches its numbers.
fails = []
for r in ROWS:
    o, n = (r["oldChance"], r["oldAmount"]), (r["newChance"], r["newAmount"])
    for c, a in (o, n):
        if c is not None and not (0 < c <= 1 and a and a > 0):
            fails.append(("bad value", r))
    want = {"changed": o[0] is not None and n[0] is not None and o != n,
            "same": o == n and o[0] is not None, "unlisted": o == n and o[0] is not None,
            "added": o[0] is None and n[0] is not None, "removed": n[0] is None and o[0] is not None,
            "unknown": o[0] is None and n[0] is not None}[r["status"]]
    if not want:
        fails.append(("status", r["status"], r["mob"], r["item"], o, n))
check("1 values in (0,1], status consistent with old/new", fails, len(ROWS))

# 2. No duplicate rows and no wiki markup left in names.
keys = Counter((r["region"], r["mob"], r["variant"], r["item"], r["newChance"]) for r in ROWS)  # same item twice = two rolls
fails = [k for k, c in keys.items() if c > 1]
fails += [r["item"] for r in ROWS if re.search(r"[{}\[\]$&|]|''", r["item"] + r["mob"])]
check("2 no duplicates, no leftover wiki markup", fails, len(ROWS))

# 3. Oct 15: every drop line in the "New Drop Tables" section is on the site with the same chance and amount.
start, end = OCT15.index("➥ New Drop Tables"), OCT15.index("➥ Related Changes")
forum, section = [], None
for line in OCT15[start:end]:
    if line.startswith("Spoiler: "):
        section = line[9:]
    for m in re.finditer(r"(?:([\d,]+)x )?([^|()\s][^|()]*?) \(([\d.]+)%\)", line):
        if section not in b.SKIP_SECTIONS:
            forum.append((m[2].strip(), float(m[3]) / 100, int((m[1] or "1").replace(",", ""))))
site_new = Counter((r["item"], round(r["newChance"], 9), r["newAmount"]) for r in ROWS
                   if r["status"] in ("changed", "same", "added", "unknown") and r["newChance"])
OCT22_ITEMS = {"Looting VII", "Fire Aspect III", "Shredded Line", "Deep Sea Orb", "Box of Junk", "Plasma",
               "Daedalus Stick", "Manti-Core", "Shimmering Wool", "Glacite Amalgamation", "Rotten Flesh",
               "Poisonous Potato", "Potato", "Carrot", "Umber Key", "Tungsten Key", "Skeleton Key"}
fails = [f for f in forum if not site_new[(f[0], round(f[1], 9), f[2])] and f[0] not in OCT22_ITEMS]
check("3 every Oct 15 table drop is on the site", fails, len(forum))

# 4. The other way: every Alpha chance on the site comes from a source line.
oct22_text = "\n".join(OCT22).lower()
forum_set = {(i, round(c, 9), a) for i, c, a in forum}
fails = []
total = 0
for r in ROWS:
    if r["status"] in ("unlisted", "removed") or r["mob"] == "Revenant Horror" or r["region"] == "Slayer" \
            or r["mob"] == "Ender Dragon":
        continue
    total += 1
    if (r["item"], round(r["newChance"], 9), r["newAmount"]) not in forum_set and r["item"].lower() not in oct22_text:
        fails.append((r["mob"], r["variant"], r["item"], r["newChance"], r["newAmount"]))
check("4 every Alpha chance on the site is in the Oct 15/22 posts", fails, total)

# 5. Oct 22 changes, re-transcribed independently from the post.
def new(mob, item, variant=None):
    m = [r for r in ROWS if r["mob"] == mob and r["item"] == item and (variant is None or r["variant"] == variant)]
    return [(r["newChance"], r["newAmount"]) for r in m]

expect = [
    ("Sphinx", "Looting VII", None, 0.01), ("Milennia-Aged Blaze", "Fire Aspect III", None, 0.001),
    ("Grim Reaper", "Shredded Line", None, 0.01), ("Alligator", "Box of Junk", None, 0.2),
    ("Small Mithril Grubber", "Plasma", None, 0.025), ("Bloated Mithril Grubber", "Plasma", None, 0.025),
    ("Atoll Croaker", "Tropical Fish", None, 1), ("Lotus Guardian", "Tropical Fish", None, 1), ("gorF", "Tropical Fish", None, 1),
    ("gorF", "Enchanted Tropical Fish", None, 0.05), ("Drowned Captain", "Enchanted Tropical Fish", None, 0.2),
    ("Puddle Jumper", "Enchanted Tropical Fish", None, 1), ("Frog Prince", "Enchanted Tropical Fish", None, 1),
    ("Drowned Captain", "Unlucky Doubloon", None, 0.025), ("Frog Prince", "Prince's Crown Jewel", None, 0.01),
    ("Puck", "Bottled Mischief", None, 0.1), ("Werewolf", "Deep Sea Orb", None, 0.002),
    ("Phantom Fisher", "Deep Sea Orb", None, 0.01), ("Grim Reaper", "Deep Sea Orb", None, 0.04),
    ("Minotaur", "Daedalus Stick", "EPIC", 0.0015), ("Minotaur", "Daedalus Stick", "LEGENDARY", 0.002),
    ("Minotaur", "Daedalus Stick", "MYTHIC", 0.0025), ("Zombie", "Poisonous Potato", None, 0.05),
    ("Graveyard Zombie", "Carrot", None, 0.025), ("Manticore", "Manti-Core", "MYTHIC", 0.0075),
    ("King Minos", "Shimmering Wool", "MYTHIC", 0.0075), ("Littlefoot", "Glacite Amalgamation", None, 0.05),
    ("Drowned Captain", "Enchanted Gold Ingot", None, 1),
]
fails = [(m, i, v, want, got) for m, i, v, want in expect if not (got := new(m, i, v)) or not all(close(c, want) for c, _ in got)]
fails += [("Littlefoot still drops", r["item"]) for r in ROWS if r["mob"] == "Littlefoot" and r["item"].endswith("Key") and r["newChance"]]
fails += [("Drowned Captain gold amount", a) for c, a in new("Drowned Captain", "Enchanted Gold Ingot") if a != 1]
check("5 every Oct 22 drop change is applied", fails, len(expect) + 2)

# 6. Zombie Slayer: every row of Hypixel's sheet, all 5 tiers.
fails, total = [], 0
for tier, gid in b.REV_TIERS.items():
    for row in csv.DictReader(io.StringIO((b.CACHE / f"revenant_{gid}.csv").read_text(encoding="utf8"))):
        total += 1
        c = b.parse_chance(row["Drop Chance"].replace("in", "/").replace("Million", "m").replace(" ", "")) \
            if " in " in row["Drop Chance"] else float(row["Drop Chance"].rstrip("%")) / 100
        got = [r for r in ROWS if r["mob"] == "Revenant Horror" and r["variant"] == tier and r["item"] == row["Drop"]]
        if not got or not close(got[0]["newChance"], c):
            fails.append((tier, row["Drop"], row["Drop Chance"], got and got[0]["newChance"]))
check("6 Zombie Slayer matches Hypixel's sheet", fails, total)

# 7. Dyes: every "T#: 1/X → 1/Y" slayer line and the Superior Dragon line.
fails, total, dye, boss = [], 0, None, None
for line in OCT15:
    if line.rstrip(" |").endswith(" Dye"):
        dye, boss = line.rstrip(" |"), None
    elif m := re.match(r"Increased (.+) drop rates?:?", line):
        boss = m[1]
    elif dye and boss and (m := re.match(r"T(\d): 1/([\d,]+) → 1/([\d,]+)", line)) and boss in b.SLAYERS:
        total += 1
        got = [r for r in ROWS if r["mob"] == boss and r["item"] == dye and r["variant"] == f"Tier {m[1]}"]
        old, nw = (1 / int(x.replace(",", "")) for x in m.groups()[1:])
        if not got or not (close(got[0]["oldChance"], old) and close(got[0]["newChance"], nw)):
            fails.append((boss, dye, line))
total += 1
if not [r for r in ROWS if r["mob"] == "Ender Dragon" and r["item"] == "Pearlescent Dye" and close(r["newChance"], 1 / 25000)]:
    fails.append("Superior Dragon Pearlescent Dye")
check("7 slayer and dragon dye changes", fails, total)

# 8. Live chances: the wiki page of the mob has that item at that chance (outside Loot Sharing tables).
fails, total, cache = [], 0, {}
for r in ROWS:
    # slayers: check 9; Arachne, End Stone Protector, dragons: hand-read wikitables (dragons scaled to 4 eyes)
    if r["oldChance"] is None or r["region"] == "Slayer" or r["mob"] in ("Arachne", "End Stone Protector", "Ender Dragon"):
        continue
    page = r["mob"] if r["status"] == "unlisted" else b.page_for(r["region"], r["mob"]) or r["mob"]
    if page not in cache:
        text = b.wiki_pages([page]).get(page, "")
        text = re.sub(r"\{\{Mob Drops Table[^{]*?loot_share\s*=\s*true.*?\n\}\}", "", text, flags=re.S)
        cache[page] = [(re.search(r"\|\s*drop\s*=([^\n|]*)", x), re.search(r"\|\s*chance\s*=([^\n]*)", x))
                       for x in re.findall(r"\{\{Mob Drops Row((?:[^{}]|\{\{[^{}]*\}\})*)\}\}", text)]
    total += 1
    item = b.norm(bare(r["item"]))
    # the wiki groups armor as one "X Armor Piece" row that applies to each piece
    names = {item, re.sub(r" (helmet|chestplate|leggings|boots)$", " armor piece", item)}
    hits = [pct(c[1]) for d, c in cache[page]
            if d and c and b.norm(bare(re.sub(r"\$\w+\$\s*", "", d[1].strip()))) in names]
    if not any(close(h, r["oldChance"]) for h in hits):
        fails.append((r["region"], r["mob"], "->", page, r["variant"], r["item"], r["oldChance"], hits))
check("8 every live chance is on the mob's wiki page", fails, total)

# 9. Slayer live chances: the boss page shows that percentage for that item.
fails, total = [], 0
pages = b.wiki_pages(b.SLAYERS - {"Riftstalker Bloodfiend"})
for r in ROWS:
    if r["region"] != "Slayer" or r["mob"] not in pages or r["oldChance"] is None or "Dye" in r["item"] or r["mob"] == "Revenant Horror":
        continue
    total += 1
    shown = f"{r['oldChance'] * 100:.4f}".rstrip("0").rstrip(".")
    nums = {f"{float(x):.4f}".rstrip("0").rstrip(".") for x in re.findall(r"([\d.]+)%", pages[r["mob"]])}
    nums |= {f"{b.parse_chance(x) * 100:.4f}".rstrip("0").rstrip(".") for x in re.findall(r"1/[\d.]+[kKmM]?", pages[r["mob"]])}
    if shown not in nums:
        fails.append((r["mob"], r["variant"], r["item"], shown + "%"))
check("9 every slayer live chance is shown on the boss page", fails, total)

# 10. Math: node runs mf.js over every row; MF 0 gives the base chance, more MF never lowers it.
js = """
const {oldDrop,newDrop,isPet}=require('../mf.js');const fs=require('fs');
eval(fs.readFileSync('../data.js','utf8').replace('const DROPS','globalThis.DROPS'));
let bad=[];const z={mf:0,looting:0,petLuck:0};
for(const r of DROPS){const pet=isPet(r.item);
 for(const [c,a,f] of [[r.oldChance,r.oldAmount,oldDrop],[r.newChance,r.newAmount,newDrop]]){ if(c==null) continue;
  const b0=f(c,a,z,pet), b1=f(c,a,{mf:100,looting:0,petLuck:0},pet), b2=f(c,a,{mf:400,looting:0,petLuck:0},pet);
  if(Math.abs(b0.avg-c*a)>1e-12||!(b1.avg>=b0.avg&&b2.avg>=b1.avg)||[b0,b1,b2].some(x=>!isFinite(x.avg)||x.p>1))
   bad.push(r.mob+' / '+r.item);}}
console.log(JSON.stringify(bad));"""
bad = json.loads(subprocess.run(["node", "-e", js], cwd=b.HERE, capture_output=True, text=True, check=True).stdout)
check("10 formulas: MF 0 = base, more MF never lowers a drop, no NaN", bad, len(ROWS))

print("\n" + "\n".join(f"{'OK ' if not n else 'BAD'} {name} ({t - n}/{t})" for name, n, t in results))
