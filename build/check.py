"""Validates ../data.js against the raw sources (forum posts, slayer sheets, wiki), row by row.
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
NOV10 = b.first_post_text(b.fetch(b.NOV10, "nov10.html"))
NOV12 = b.first_post_text(b.fetch(b.NOV12, "nov12.html"))
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

# 3. Nov 10: every drop line in the "Drop Table Changes" tables is on the site with the same chance and amount
#    (unless a later Nov 12 / prose change, checked in 5, moved it).
start, end = NOV10.index("➥ Drop Table Changes"), NOV10.index("➥ Item Adjustments")
forum, section = [], None
for line in NOV10[start:end]:
    if line.startswith("Spoiler: "):
        section = line[9:]
    for m in re.finditer(r"(?:([\d,]+)x )?([^|()\s][^|()]*?) \(([\d.]+)%\)", line):
        if section not in b.SKIP_SECTIONS:
            item = b.FORUM_TYPOS.get(m[2].strip(), m[2].strip())
            forum.append((item, float(m[3]) / 100, int((m[1] or "1").replace(",", ""))))
site_new = Counter((r["item"], round(r["newChance"], 9), r["newAmount"]) for r in ROWS
                   if r["status"] in ("changed", "same", "added", "unknown") and r["newChance"])
CHANGED_ITEMS = {c[2] for c in b.CHANGES}
fails = [f for f in forum if not site_new[(f[0], round(f[1], 9), f[2])] and f[0] not in CHANGED_ITEMS]
check("3 every Nov 10 table drop is on the site", fails, len(forum))

# 4. The other way: every Alpha chance on a forum mob comes from a Nov 10 table line or a later change.
forum_set = {(i, round(c, 9), a) for i, c, a in forum}
fails, total = [], 0
for r in ROWS:
    if r["status"] in ("unlisted", "removed") or r["region"] == "Slayer" or r["mob"] == "Ender Dragon":
        continue
    total += 1
    if (r["item"], round(r["newChance"], 9), r["newAmount"]) not in forum_set and r["item"] not in CHANGED_ITEMS:
        fails.append((r["mob"], r["variant"], r["item"], r["newChance"], r["newAmount"]))
check("4 every Alpha chance on the site is in the Nov 10 tables", fails, total)


# 5. Nov 12 (and Nov 10 prose) changes, parsed straight from the post text rather than from build.CHANGES.
def new(mob, item, variants=None):
    return [r for r in ROWS if r["mob"] == mob and r["item"] == item and (variants is None or r["variant"] in variants)]


MOB_WORDS = {"Tarantula Slayer": "Tarantula Broodfather", "Wolf Slayer": "Sven Packmaster", "Enderman Slayer": "Voidgloom Seraph",
             "Blaze Slayer": "Inferno Demonlord", "Drowned Pirate": "Drowned Captain", "Griffin Minotaur variant": "Minotaur"}
ITEM_WORDS = {"Spooky Hook": "Phantom Hook"}
expect = []  # (mob, variants, item, chance or None, amount or None, source line)
for line in NOV12:
    m = re.match(r"(?:Increased drop-rate of|Reduced) (.+?) \(([^)]+?)\)?,? (?:drop-rate )?from ([\d.]+)% → ([\d.]+)%", line)
    if not m:
        continue
    item, where, to = ITEM_WORDS.get(m[1], m[1]), m[2].replace(" drop-rate", ""), float(m[4]) / 100
    tiers = re.search(r"Tier ([\d/]+)", where)
    variants = tuple(f"Tier {t}" for t in tiers[1].split("/")) if tiers else None
    rar = re.match(r"(EPIC|LEGENDARY|MYTHIC) (.*)", where)
    if rar:
        variants, where = (rar[1],), rar[2]
    mob = next((v for k, v in MOB_WORDS.items() if k in where), re.sub(r" Tier.*", "", where))
    expect.append((mob, variants, item, to, None, line))
for m in re.finditer(r"Increased Derelict Ashe \(Inferno Demonlord (I+V?|IV)\) from [\d-]+ → ([\d-]+)", "\n".join(NOV12)):
    expect.append(("Inferno Demonlord", (f"Tier {['I', 'II', 'III', 'IV'].index(m[1]) + 1}",), "Derelict Ashe", None, b.avg_amount(m[2]), m[0]))
for rar, frm, to in re.findall(r"(EPIC|LEGENDARY): Increased from ([\d.]+)% → ([\d.]+)% per eye", "\n".join(NOV12)):
    expect.append(("Ender Dragon", None, f"{rar} Ender Dragon Pet", float(to) * 4 / 100, None, f"{rar} {to}% per eye x 4 eyes"))
if m := re.search(r"Added (.+) to Sven Packmaster ([\d/]+) Drop Table\s+Requires .*?, ([\d.]+)% drop-rate", "\n".join(NOV12)):
    expect.append(("Sven Packmaster", tuple(f"Tier {t}" for t in m[2].split("/")), m[1], float(m[3]) / 100, None, m[0]))
for line in NOV10:
    if m := re.match(r"Increased the (weaker|stronger) Arachne’s (\w+ Tarantula) Pet drop chance from [\d.]+% → ([\d.]+)%", line):
        expect.append(("Arachne", ("Lower Tier" if m[1] == "weaker" else "Higher Tier",), m[2] + " Pet", float(m[3]) / 100, None, line))
    elif m := re.match(r"Increased (.+) from (.+) from [\d.]+% (?:→|->) ([\d.]+)%", line):
        expect.append((m[2], None, m[1], float(m[3]) / 100, None, line))
    elif m := re.match(r"Reduced [\d-]+x Enchanted Honeycomb \(100%\) from (\w[\w ]*?) ?→ (\d+)x", line):
        expect.append((m[1], None, "Enchanted Honeycomb", None, float(m[2]), line))
fails = []
for mob, variants, item, chance, amount, line in expect:
    got = new(mob, item, variants)
    if not got or (variants and len(got) != len(variants)) or not all(
            (chance is None or close(r["newChance"], chance)) and (amount is None or close(r["newAmount"], amount)) for r in got):
        fails.append((line, [(r["variant"], r["newChance"], r["newAmount"]) for r in got]))
if len(expect) != len(b.CHANGES):
    fails.append(f"post has {len(expect)} changes, build.CHANGES has {len(b.CHANGES)}")
check("5 every Nov 12 / Nov 10 prose change is applied", fails, len(expect))

# 6. Slayers: every row of Hypixel's six sheets, every tier (dyes in 7; Nov 12 edits in 5).
fails, total = [], 0
nov12_hit = {(e[0], e[2]) for e in expect}
for boss, key in b.SHEETS.items():
    for f in sorted(b.CACHE.glob(f"{key[-6:]}_*.csv")):
        page = (b.CACHE / f"sheet_{key[-6:]}.html").read_text(encoding="utf8")
        tier = "Tier " + re.search(rf'name: "[^"]*?Tier (\d)[^"]*", pageUrl: "[^"]*gid={f.stem.split("_")[1]}"', page)[1]
        for drop, amount, chance, _ in list(csv.reader(io.StringIO(f.read_text(encoding="utf8"))))[1:]:
            if "Dye" in drop or (boss, drop) in nov12_hit:
                continue
            total += 1
            got = new(boss, drop, (tier,))
            if len(got) != 1 or not close(got[0]["newChance"], b.sheet_chance(chance)) or not close(got[0]["newAmount"], b.avg_amount(amount)):
                fails.append((boss, tier, drop, amount, chance, [(r["newChance"], r["newAmount"]) for r in got]))
check("6 every slayer matches Hypixel's sheets", fails, total)

# 7. Dyes: every "T#: 1/X → 1/Y" slayer line (and the sheets agree), and the Superior Dragon line.
fails, total, dye, boss = [], 0, None, None
for line in NOV10:
    if line.rstrip(" |").endswith(" Dye"):
        dye, boss = line.rstrip(" |"), None
    elif m := re.match(r"Increased (.+) drop rates?:?", line):
        boss = m[1]
    elif dye and boss and (m := re.match(r"T(\d): 1/([\d,]+) → 1/([\d,]+)", line)) and boss in b.SLAYERS:
        total += 1
        got = new(boss, dye, (f"Tier {m[1]}",))
        old, nw = (1 / int(x.replace(",", "")) for x in m.groups()[1:])
        key = b.SHEETS[boss][-6:]
        tabs = dict(re.findall(r'name: "[^"]*?Tier (\d)[^"]*", pageUrl: "[^"]*gid=(\d+)', (b.CACHE / f"sheet_{key}.html").read_text(encoding="utf8")))
        sheet = [(t, b.sheet_chance(c)) for t, gid in tabs.items()
                 for d, _, c, _ in list(csv.reader(io.StringIO((b.CACHE / f"{key}_{gid}.csv").read_text(encoding="utf8"))))[1:] if d == dye]
        tab = [x for x in sheet if x[0] == m[1]]  # the sheet is newer than the post and wins where they differ
        want = tab[0][1] if tab else nw
        if not got or not (close(got[0]["oldChance"], old) and close(got[0]["newChance"], want)):
            fails.append((boss, dye, line, got and got[0]["newChance"], "sheet:", tab))
        elif not close(want, nw):
            print(f"    note: {boss} {dye} T{m[1]}: post says 1/{1 / nw:,.0f}, sheet says 1/{1 / want:,.0f} (sheet used)")
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
pages = b.wiki_pages(b.SLAYERS)
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

# 11. Looting I-VII flat MF in mf.js matches the Oct 23 post ("Looting V: 6 -> 15").
OCT23 = b.first_post_text(b.fetch(b.OCT15.replace("october-15-magic-find-rework-ghost-visitors.6162638",
                                                  "october-23-magic-find-rework-testing-3-faq.6165335"), "oct23.html"))
posted = [float(m[1]) for l in OCT23 if (m := re.match(r"Looting [IVX]+: [\d.]+ -> ([\d.]+)$", l))]
in_js = json.loads(re.search(r"NEW_LOOTING_MF = (\[.*?\])", (b.HERE.parent / "mf.js").read_text())[1])[1:]
check("11 Looting MF matches the Oct 23 post", [] if posted == in_js and len(posted) == 7 else [(posted, in_js)], 7)

# 12. MF estimator in index.html: the last value of each "Reduced/Increased X ... -> a/b/c" line in Nov 10/12.
page = (b.HERE.parent / "index.html").read_text(encoding="utf8")
posts = "\n".join(NOV10 + NOV12)
fails = []
for post_name, label, attr in [("Booster Cookie", "Booster Cookie", "data-mf"), ("Magic Find Potion I/II/III/IV's Magic Find", "MF Potion IV", "data-mf"),
                               ("Private Island Beacon", "Private Island Beacon", "data-mf"), ("Pulse Ring", "Pulse Ring", "max"),
                               ("Anguish Artifact", "Anguish line", "max"), ("Celestial Mason Jar", "Celestial Mason Jar", "data-mf")]:
    m = re.search(re.escape(post_name) + r" from [+\d./]+ -> \+?([\d./]*\d)", posts)
    want = float(m[1].split("/")[0 if label == "Private Island Beacon" else -1]) if m else None  # Beacon: per level
    got = re.search(re.escape(label) + rf'[^<]*<input[^>]*{attr}="([\d.]+)"', page)
    if want is None or not got or float(got[1]) != want:
        fails.append((post_name, want, got and got[1]))
check("12 MF estimator values match the Nov 10/12 posts", fails, 6)

print("\n" + "\n".join(f"{'OK ' if not n else 'BAD'} {name} ({t - n}/{t})" for name, n, t in results))
