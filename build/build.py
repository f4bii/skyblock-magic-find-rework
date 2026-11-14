"""Builds ../data.js: new (alpha) drop tables from the Hypixel forum posts joined
with the current live drop tables scraped from the Hypixel SkyBlock wiki.

Run: python3 build/build.py   (downloads into build/cache on first run; delete it to refresh)
"""
import csv, hashlib, html, io, json, re, sys, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).parent
CACHE = HERE / "cache"
CACHE.mkdir(exist_ok=True)
OCT15 = "https://hypixel.net/threads/october-15-magic-find-rework-ghost-visitors.6162638/"
NOV10 = "https://hypixel.net/threads/november-10-0-27-3-release-candidate.6171140/"  # 0.27.3 RC: all tables so far
NOV12 = "https://hypixel.net/threads/november-12-0-27-3-release-candidate-2.6171435/"
# Slayer loot sheets: the five linked from the Nov 10 post, Vampire from Nov 12. Tabs are Tier 1..N.
SHEETS = {
    "Revenant Horror": "2PACX-1vR89yuHTiqhko583imFPZSokHYdgZ6N7gWsOXqJnduD3xTii5L9z2lCTzYA1zC80OJkEsRhDPpVahJX",
    "Tarantula Broodfather": "2PACX-1vSUa7o7FXzY04QmDzu1Aww-NDE2OCpaQp7-8PL3RE38PMpyEOIpObqq_GKy7zYsJGG44qA7zQVaZczx",
    "Sven Packmaster": "2PACX-1vQ4XqZng7-4rNJkvBpkXasHdAgFVUFIywZU221bqKwHfzS-LrZybePGfrSo7mXWue5otoPVcEYhC4hv",
    "Voidgloom Seraph": "2PACX-1vQQ8uFW6ieUA4lxP-y6nDkHP4hJP48UnvYjHqlgB95r2IiCLPcb1vgeml_Auol9Em3IKXK5spxW8gVP",
    "Inferno Demonlord": "2PACX-1vSm1LLJ4u4XHvC-0Yk6fV3rrJ6zk__7n1qqJIKeez5oMd28tjVrlxgpHkfqujMOQBSiUPINd0jTYkg9",
    "Riftstalker Bloodfiend": "2PACX-1vRsDiYGGkmU33X_ff2HND4bjuiNoh2MNKntkpb0X4FbL5ndC3tBJV-VNg44ExGAmADW6rd0d25EJ2s2",
}
SHEET_PAGE = "https://docs.google.com/spreadsheets/d/e/{}/pubhtml"
SHEET_CSV = "https://docs.google.com/spreadsheets/d/e/{}/pub?output=csv&gid={}"
WIKI_API = "https://hypixelskyblock.minecraft.wiki/api.php?"


def fetch(url, name):
    f = CACHE / name
    if not f.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "mf-rework-compare/1.0"})
        f.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    return f.read_text(encoding="utf8")


def first_post_text(page):
    i = page.find('class="bbWrapper"')
    frag = page[i:page.find("js-selectToQuoteEnd", i)]
    frag = re.sub(r"<br\s*/?>", "\n", frag)
    frag = re.sub(r"</(p|div|li|tr|h\d|table|ul|ol)>", "\n", frag)
    frag = re.sub(r"</t[dh]>", " | ", frag)
    frag = html.unescape(re.sub(r"<[^>]+>", "", frag))
    frag = re.sub(r"[ \t​]+", " ", frag)
    return [l.strip() for l in frag.split("\n") if l.strip()]


DROP_RE = re.compile(r"^(?:([\d,]+)x )?(.+?) \(([\d.]+)%\)\*?$")  # "*" = "Temporary source" footnote
GRIFFIN = ["COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY", "MYTHIC"]
SKIP_SECTIONS = {"Dyes", "Jerrypocalypse", "Slayers", "Torrhus Canyon"}
FORUM_TYPOS = {"FlawedAmber Gemstone": "Flawed Amber Gemstone"}


def parse_new_tables(lines, start="➥ Drop Table Changes", end="➥ Item Adjustments"):
    """-> {(region, mob, variant): [ {item, amount, chance} ]}"""
    start, end = lines.index(start), lines.index(end)
    out, region, key = {}, None, None
    for line in lines[start:end]:
        if line.startswith("Spoiler: "):
            region, key = line[9:], None
            continue
        if region is None or region in SKIP_SECTIONS or line.startswith("Mob |"):
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) >= 2 and cells[1] in GRIFFIN:  # Mythological: Mob | Griffin rarity | drop
            key = (region, cells[0], cells[1])
            out[key] = []
            line = cells[2]
        elif len(cells) >= 2 and cells[0] and not DROP_RE.match(cells[0]):
            key = (region, cells[0], "")
            out[key] = []
            line = cells[1]
        else:
            line = cells[0]
        m = DROP_RE.match(line)
        if key and m:
            out[key].append({"item": FORUM_TYPOS.get(m[2], m[2]), "amount": int((m[1] or "1").replace(",", "")), "chance": float(m[3]) / 100})
    return {k: v for k, v in out.items() if v}


T = lambda *n: tuple(f"Tier {i}" for i in n)  # noqa: E731
# Alpha changes written as prose, applied to the finished rows (forum, slayer sheet or wiki-only).
# (mob, variants or None for all, item, "chance" in % | "amount" as posted | "add" for a new drop, from, to)
CHANGES = [
    # Nov 10, Spider's Den / Torrhus Canyon spoilers (sentences, not tables)
    ("Arachne", ("Lower Tier",), "EPIC Tarantula Pet", "chance", 2, 5),
    ("Arachne", ("Higher Tier",), "LEGENDARY Tarantula Pet", "chance", 2, 2.5),
    ("Giant Isopod", None, "Isopod Husk", "chance", 2, 2.5),
    ("Puck", None, "Bottled Mischief", "chance", 5, 10),
    *[(mob, None, "Enchanted Honeycomb", "amount", old, new) for mob, old, new in [
        ("Honeyhog", "1-2", "1"), ("Honeymite", "2-4", "2"), ("Hewver", "4-8", "3"),
        ("Stag Beetle", "1-2", "1"), ("Woodlouse", "2-4", "2"), ("Murkbat", "4-8", "3"),
        ("Pollendart", "1-2", "1"), ("Parched", "2-4", "2"), ("Hivethief", "4-8", "3")]],
    # Nov 12 RC2 "Drop Table Changes"
    ("Sven Packmaster", T(2, 3, 4), "Spirit Rune I", "add", None, 2.5),
    *[("Inferno Demonlord", T(i), "Derelict Ashe", "amount", old, new)
      for i, old, new in [(1, "2-4", "8-16"), (2, "8-16", "16-32"), (3, "16-32", "32-64"), (4, "32-64", "64-96")]],
    # "0.05% -> 0.1% per eye" / "0.01% -> 0.02% per eye"; the site assumes 4 eyes
    ("Ender Dragon", None, "EPIC Ender Dragon Pet", "chance", 0.2, 0.4),
    ("Ender Dragon", None, "LEGENDARY Ender Dragon Pet", "chance", 0.04, 0.08),
    ("Lord Jawbus", None, "Radioactive Vial", "chance", 1, 1.25),
    ("Thunder", None, "Flash I", "chance", 2, 4),
    ("Phantom Fisher", None, "Phantom Hook", "chance", 1, 2),  # the post calls it "Spooky Hook"
    ("Grim Reaper", None, "Shredded Line", "chance", 1, 2.5),
    ("Yeti", None, "COMMON Baby Yeti Pet", "chance", 2, 3.5),
    ("Yeti", None, "True Ice", "chance", 3, 5),  # post says "from 3%"; Nov 10 table lists 1%
    ("Drowned Captain", None, "Unlucky Doubloon", "chance", 2.5, 3.3),  # post says "Drowned Pirate"
    ("Great White Shark", None, "Great White Shark Tooth", "chance", 5, 7.5),
    ("Voidling Extremist", None, "Enderman Cortex Rewriter", "chance", 0.05, 0.1),
    ("Diamond Goblin", None, "Pure Mithril Gem", "chance", 1, 1.5),
    ("Littlefoot", None, "Littlefoot Fluff", "chance", 0.5, 0.75),
    ("Minotaur", ("EPIC",), "Daedalus Stick", "chance", 0.15, 0.3),
    ("Minotaur", ("LEGENDARY",), "Daedalus Stick", "chance", 0.2, 0.35),
    ("Minotaur", ("MYTHIC",), "Daedalus Stick", "chance", 0.25, 0.4),
    ("Tarantula Broodfather", T(2, 3, 4, 5), "Toxic Arrow Poison", "chance", 10, 5),
    ("Tarantula Broodfather", T(2, 3, 4, 5), "Spider Catalyst", "chance", 2.5, 1),
    ("Tarantula Broodfather", T(5), "Tarantula Silk", "chance", 10, 5),
    ("Sven Packmaster", T(2, 3, 4), "Hamster Wheel", "chance", 10, 5),
    ("Voidgloom Seraph", T(2, 3, 4), "Twilight Arrow Poison", "chance", 10, 5),
    ("Voidgloom Seraph", T(4), "Judgement Core", "chance", 0.1, 0.075),
    ("Inferno Demonlord", T(2, 3, 4), "Enchanted Blaze Powder", "chance", 10, 5),
    ("Inferno Demonlord", T(2, 3, 4), "Bundle of Magma Arrows", "chance", 10, 5),
    ("Inferno Demonlord", T(2, 3, 4), "Inferno Demonlord Shard", "chance", 2.5, 2),
    ("Inferno Demonlord", T(2, 3, 4), "Kelvin Inverter", "chance", 5, 2.5),
    ("Inferno Demonlord", T(3, 4), "Archfiend Dice", "chance", 1.5, 1),
]


def apply_changes(rows):
    for mob, variants, item, field, old, new in CHANGES:
        hit = [r for r in rows if r["mob"] == mob and r["item"] == item and (variants is None or r["variant"] in variants)]
        if field == "add":  # live may already drop it (then that row was marked "removed")
            base = next(r for r in rows if r["mob"] == mob)
            rows += [{**base, "variant": v, "item": item, "newChance": None, "newAmount": None,
                      "oldChance": None, "oldAmount": None} for v in variants if v not in [r["variant"] for r in hit]]
            hit = [r for r in rows if r["mob"] == mob and r["item"] == item and r["variant"] in variants]
            for r in hit:
                r["newChance"], r["newAmount"], r["status"] = new / 100, 1, "added"
        assert hit and (variants is None or len(hit) == len(variants)), f"no row for {mob} / {item} {variants or ''}"
        key, cast = ("newChance", lambda x: x / 100) if field in ("chance", "add") else ("newAmount", avg_amount)
        for r in hit:
            if old is not None and abs(r[key] - cast(old)) > 1e-9:
                print(f"note: {mob} {r['variant']} {item}: post says {field} was {old}, data has {r[key]}", file=sys.stderr)
            r[key] = cast(new)
            if r["oldChance"] is not None:
                r["status"] = "same" if (r["oldChance"], r["oldAmount"]) == (r["newChance"], r["newAmount"]) else "changed"


def slayer_tables():
    """Alpha slayer loot: one Hypixel sheet per boss, one tab per tier -> (tables, {(boss, tier, dye): chance})."""
    out, dyes = {}, {}
    for boss, key in SHEETS.items():
        tabs = re.findall(r'name: "[^"]*?Tier (\d)[^"]*", pageUrl: "[^"]*gid=(\d+)', fetch(SHEET_PAGE.format(key), f"sheet_{key[-6:]}.html"))
        assert tabs, boss
        for tier, gid in tabs:
            rows = []
            for item, amount, chance, _ in list(csv.reader(io.StringIO(fetch(SHEET_CSV.format(key, gid), f"{key[-6:]}_{gid}.csv"))))[1:]:
                if "Dye" in item:
                    dyes[(boss, f"Tier {tier}", item)] = sheet_chance(chance)
                else:
                    rows.append({"item": item, "amount": avg_amount(amount), "chance": sheet_chance(chance)})
            out[("Slayer", boss, f"Tier {tier}")] = rows
    return out, dyes


def sheet_chance(s):
    """'10.000%', '100%%', '1 in 2.5 Million', '1 in 100,000' -> fraction."""
    if m := re.match(r"1 in ([\d.,]+)\s*(Million)?$", s.strip()):
        return 1 / (float(m[1].replace(",", "")) * (1e6 if m[2] else 1))
    return float(s.strip().rstrip("%")) / 100


def slayer_dyes(lines, sheet):
    """Slayer dye rates from the Dyes spoiler, 'T1: 1/X → 1/Y'. Where the (newer) sheet disagrees on the new
    rate, the sheet wins: the Nov 12 Vampire sheet still lists Sangria Dye at its live rates."""
    rows, dye, boss = [], None, None
    for line in lines:
        if line.rstrip(" |").endswith(" Dye"):
            dye, boss = line.rstrip(" |"), None
        elif m := re.match(r"Increased (.+) drop rates:$", line):
            boss = m[1] if dye and m[1] in SLAYERS else None
        elif boss and (m := re.match(r"T(\d): 1/([\d,]+) → 1/([\d,]+)", line)):
            old, new = (1 / int(x.replace(",", "")) for x in m.groups()[1:])
            new = sheet.get((boss, f"Tier {m[1]}", dye), new)
            rows.append({"region": "Slayer", "mob": boss, "variant": f"Tier {m[1]}", "item": dye,
                         "newChance": new, "newAmount": 1, "oldChance": old, "oldAmount": 1,
                         "status": "same" if abs(new - old) < 1e-12 else "changed",
                         **SLAYER_RULE[boss]})
    return rows


SLAYERS = {"Revenant Horror", "Tarantula Broodfather", "Sven Packmaster", "Voidgloom Seraph",
           "Inferno Demonlord", "Riftstalker Bloodfiend"}
# How app.js rolls slayer boss loot. Live: weighted tables (MF only below 5%, no Looting). Alpha: every boss
# uses a normal mob table. "rift": no MF live; on Alpha only the Vampire Slayer level MF applies.
SLAYER_RULE = {b: {"weighted": "old"} for b in SLAYERS} | {"Riftstalker Bloodfiend": {"weighted": "old", "rift": True}}
# Oct 27/Nov 10: slayer levels give MF on that slayer's boss (+1 at levels 1-8, +2 at 9; Rift: 1-4, +2 at 5)
SLAYER_TYPE = {"Revenant Horror": "Zombie Slayer", "Tarantula Broodfather": "Spider Slayer", "Sven Packmaster": "Wolf Slayer",
               "Voidgloom Seraph": "Enderman Slayer", "Inferno Demonlord": "Blaze Slayer", "Riftstalker Bloodfiend": "Vampire Slayer"}


def wt_text(s):
    s = re.sub(r"<!--.*?-->", "", s)
    s = re.sub(r"\{\{(?:Item|Slot)\|([^|}]+)([^}]*)\}\}",
               lambda m: (re.search(r"\|\s*(?:enchant|text)\s*=\s*([^|}]+)", m[2]) or m)[1].strip(), s)
    s = re.sub(r"\{\{Chance\|([^|}]+)[^}]*\}\}", r"\1", s)
    s = re.sub(r"\{\{\w+\|([^{}|]*)\}\}", r"\1", s)
    return re.sub(r"\{\{[^{}]*\}\}|'''?|<[^>]+>", "", s).strip()


def wt_cells(row):
    """Cells of one wikitable row, colspans expanded."""
    out = []
    for line in row.split("\n"):
        if not line.startswith("|") or line[:2] in ("|}", "|-"):
            continue
        for c in re.split(r"\|\|(?![^{]*\}\})", line[1:]):
            m = re.match(r'^\s*((?:(?:colspan|rowspan|style|class)\s*=\s*"?[^"|]*"?\s*)+)\|(.*)$', c)
            span = int(re.search(r'colspan\s*=\s*"?(\d+)', m[1])[1]) if m and "colspan" in m[1] else 1
            out += [wt_text(m[2] if m else c)] * span
    return out


def avg_amount(s):
    lo, _, hi = s.replace(",", "").partition("-")
    try:
        return (float(lo) + float(hi or lo)) / 2
    except ValueError:
        return 1


def slayer_live(text):
    """Live boss loot from the wiki -> {"Tier N": [rows]}. The boss pages use three layouts."""
    sec = text[text.find("== Drops"):]
    out = {}

    def add(tier, item, amount, chance):
        if item and chance:
            out.setdefault(f"Tier {tier}", []).append({"item": item, "amount": avg_amount(amount), "chance": chance})

    if "Calculator:Slayer Drops" in sec:  # Revenant: raw weights per loot pool (formulas from the Slayer wiki page)
        for i, body in enumerate(re.split(r"\|-\|Tier [IVX]+", sec)[1:], 1):
            rows = [dict(re.findall(r"\|(\w+)=([^\n]*)", r)) for r in re.findall(r"\{\{Slayer Drops Row(.*?)\}\}", body, re.S)]
            tot = {p: sum(float(r["weight"]) for r in rows if r["pool"] == p) for p in ("Token", "Main", "Extra")}
            for r in rows:
                w = float(r["weight"])
                add(i, r["drop"].strip(), r.get("quantity", "1"), {
                    "Token": 1, "Main": w / (tot["Token"] + tot["Main"]),
                    "Extra": w / (tot["Token"] + tot["Main"] + tot["Extra"]), "Separate": w}[r["pool"]])
    elif "<tabber>" in sec[:2000]:  # one table per tier
        for i, body in enumerate(re.split(r"\|-\|Tier \d+=", sec)[1:], 1):
            for row in body[:body.find("\n|}")].split("\n|-")[1:]:
                c = wt_cells(row)
                amount = re.search(r"amount=([^|}]+)", row)
                if len(c) >= 7:
                    add(i, c[1], amount[1] if amount else "1", parse_chance(c[-1]))
    else:  # one table, an amount column and a chance column per tier
        sec = sec[:sec.find("\n|}")]
        n = sum(l.count("SlayerTier") for l in sec.split("\n") if l.startswith("!")) // 2
        for row in sec.split("\n|-"):
            c = wt_cells(row)
            if len(c) >= 3 + 2 * n:
                for i in range(n):
                    chance = c[len(c) - n + i]
                    add(i + 1, c[1], c[3 + i], parse_chance(chance) if chance else None)
    return out


# ---------- old (live) tables from the wiki ----------
PAGE_ALIAS = {
    "Milennia-Aged Blaze": "Millennia-Aged Blaze",
    "Undead (All Watcher Undeads)": "Undead",
    "Bat (Secret Bat)": "Secret Bat",
    "Stridersurfer (Both Variants)": "Stridersurfer",
    "Magma Slug / Baby Magma Slug": "Magma Slug",
    "Small Mithril Grubber": "Mithril Grubber", "Medium Mithril Grubber": "Mithril Grubber",
    "Large Mithril Grubber": "Mithril Grubber", "Bloated Mithril Grubber": "Mithril Grubber",
    "Frosty": "Frosty (Mob)",
    "Rat": "",  # wiki "Rat" is the Garden pest, not the Hub mob
    # same-named mobs where the wiki page describes a different location's mob
    "Hub/Skeleton": "", "Private Island/Enderman": "", "Crystal Hollows/Goblin": "",
}


def page_for(region, mob):
    alias = PAGE_ALIAS.get(f"{region}/{mob}", PAGE_ALIAS.get(mob))
    return (re.sub(r"\s*\(.*\)$", "", mob) if alias is None else alias).replace("’", "'")


def wiki_pages(titles):
    out = {}
    titles = sorted(set(titles))
    for i in range(0, len(titles), 40):
        chunk = titles[i:i + 40]
        q = urllib.parse.urlencode({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
                                    "redirects": 1, "format": "json", "titles": "|".join(chunk)})
        d = json.loads(fetch(WIKI_API + q, "wiki_" + hashlib.md5(q.encode()).hexdigest()[:12] + ".json"))["query"]
        redirect = {r["from"]: r["to"] for r in d.get("redirects", []) + d.get("normalized", [])}
        by_title = {p["title"]: p["revisions"][0]["slots"]["main"]["*"] for p in d["pages"].values() if "revisions" in p}
        for t in chunk:
            dest = redirect.get(redirect.get(t, t), redirect.get(t, t))
            if dest in by_title:
                out[t] = by_title[dest]
    return out


def rarity(code):
    """Wiki rarity abbreviations: $l$, $leg$, $Epic$ ... -> LEGENDARY, EPIC (first match in GRIFFIN order)."""
    return next(r for r in GRIFFIN if r.startswith(code.upper()))


def parse_chance(s):
    s = s.strip().replace(",", "")
    m = re.match(r"^1\s*/\s*([\d.]+)\s*([kKmM]?)$", s)
    if m:
        return 1 / (float(m[1]) * {"": 1, "k": 1e3, "m": 1e6}[m[2].lower()])
    m = re.match(r"^([\d.]+)\s*%?", s)  # "100%, 75%" (extra roll) -> first value
    return float(m[1]) / 100 if m else None


def parse_wiki_drops(text):
    """-> [(tab_label, [ {item, amount, chance} ])]; tab_label '' when page has no tabs."""
    m = re.search(r"== ?(Drops?|Loot) ?==", text)  # most pages say "Drops", a few "Drop" or "Loot"
    if not m:
        return []
    sec = text[m.start():]
    nxt = re.search(r"\n==[^=]", sec[5:])
    sec = sec[: nxt.start() + 5] if nxt else sec
    # "Loot Sharing" tables are what a helper gets (e.g. Water Hydra Head 2.8% vs 14%), not the killer's drops
    sec = re.sub(r"\{\{Mob Drops Table[^{]*?loot_share\s*=\s*true.*?\n\}\}", "", sec, flags=re.S)
    parts = re.split(r"\|-\|([^=\n]+)=", sec)
    tabs = [("", parts[0])] + list(zip(parts[1::2], parts[2::2]))
    out = []
    for label, body in tabs:
        rows = []
        for row in re.findall(r"\{\{Mob Drops Row((?:[^{}]|\{\{[^{}]*\}\})*)\}\}", body):
            f = dict((k.strip(), v.strip()) for k, v in re.findall(r"\|\s*(\w+)\s*=([^|]*)", row))
            chance = parse_chance(f.get("chance", ""))
            if not f.get("drop") or chance is None:
                continue
            item = re.sub(r"\$(\w+)\$\s*", lambda m: rarity(m[1]) + " ", f["drop"]).strip()
            item = re.sub(r"^Enchanted Book &(.*)&$", r"\1", item)
            lo, _, hi = f.get("count", "1").replace(",", "").partition("-")
            try:
                amount = (float(lo) + float(hi or lo)) / 2
            except ValueError:
                amount = 1
            rows.append({"item": item, "amount": amount, "chance": chance})
        if rows or "Mob Drops Table" in body:  # an empty table means "drops nothing"
            out.append((label.strip(), rows))
    return out


def all_drop_pages():
    """Every wiki article that has a mob drop table."""
    titles, cont = [], {}
    while True:
        q = urllib.parse.urlencode({"action": "query", "list": "embeddedin", "eititle": "Template:Mob Drops Row",
                                    "einamespace": 0, "eilimit": 500, "format": "json", **cont})
        d = json.loads(fetch(WIKI_API + q, "wiki_" + hashlib.md5(q.encode()).hexdigest()[:12] + ".json"))
        titles += [p["title"] for p in d["query"]["embeddedin"]]
        if "continue" not in d:
            return titles
        cont = d["continue"]


def wiki_text(s):
    s = re.sub(r"\{\{\s*\w+\s*\|([^{}|]*)[^{}]*\}\}", r"\1", s)  # {{Zone|Hub}} -> Hub
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)     # [[A|B]] -> B
    return re.sub(r"<[^>]+>|\{\{[^}]*\}\}|'''?", "", s).strip()


def mob_tags(mob, text):
    """Mob types from the wiki infobox plus the extra groups conditional MF targets."""
    m = re.search(r"\|\s*mob_type\s*=(.*?)(?=\n\s*\|)", text or "", re.S)
    tags = {t.strip().capitalize() for t in re.findall(r"\{\{mt\|([^}|]+)", m[1] if m else "")} - {"None"}
    if "Infobox/Sea creature" in (text or ""):
        tags.add("Sea Creature")
        if re.search(r"location\s*=[^\n]*Jerry", text):
            tags.add("Winter Sea Creature")
    if mob in SLAYERS:
        tags.add("Slayer Boss")
    tags.update(w for w in ("Shark", "Ghost", "Automaton") if w in mob)
    return sorted(tags)


ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}


def dungeon_floors(mob, region, text):
    """Catacombs floors (0 = Entrance) the mob spawns on, from its wiki infobox and per-floor variants;
    [] means every floor. Watcher summons can appear on any floor's blood room."""
    if mob.endswith("(Scarf Boss Fight)"):
        return [2]
    if "Watcher Summon" in mob:
        return []
    m = re.search(r"Floor (\w+)$", region)
    if m:
        return [ROMAN[m[1]]]
    found = set()
    for v in re.findall(r"\|\s*spawn_(?:location|condition)\d*\s*=([^\n]*)", text or ""):
        r = re.search(r"Floor (\w+)\]\]\s*-\s*\[\[[^|\]]*\|(\w+)\]\]|Floor (\w+)\]\]\s*-\s*\[\[[^\]]*Floor (\w+)\]\]", v)
        if r and (r[1] or r[3]) in ROMAN and (r[2] or r[4]) in ROMAN:
            found.update(range(ROMAN[r[1] or r[3]], ROMAN[r[2] or r[4]] + 1))
        found.update(ROMAN[f] for f in re.findall(r"Floor (\w+)", v) if f in ROMAN)
        if "Entrance" in v:
            found.add(0)
    return sorted(found)


def unlisted_tables(covered_texts, texts):
    """Mobs the Alpha posts don't mention: same base rates, but MF now applies to all their drops.
    Rift mobs (drop Motes; no MF there), Garden pests, Stranded/minion copies and
    Baby Magma Slug (in the post as 'Magma Slug / Baby Magma Slug') and
    Watcher summons (already in the post under other names) are left out."""
    out = {}
    for title, text in wiki_pages(all_drop_pages()).items():
        if text in covered_texts or title in covered_texts or title == "Baby Magma Slug" or "motes" in text or "{{mt|Pest}}" in text \
                or re.search(r"\((Stranded|Minion Mob|Watcher|Bonzo|Elle's Quest)\)$", title):
            continue
        if title == "Ender Dragon":  # eye-scaled drops are listed as "0-X%" for 0-8 eyes; assume 4 eyes placed
            text = re.sub(r"chance = 0-([\d.]+)%", lambda m: f"chance = {float(m[1]) / 2:g}%", text)
        texts[title] = text
        cat = re.search(r"\|\s*category\s*=\s*(.+)", text)
        loc = re.search(r"\|\s*spawn_location\s*=\s*(.+)", text)
        region = ("Slayer" if cat and "Slayer" in cat[1] else "Other Sea Creatures" if "Infobox/Sea creature" in text else
                  wiki_text(re.split(r"<br\s*/?>|,|\{\{!\}\}", loc[1])[0]).lstrip("* ") if loc else "") or "Other"
        for label, rows in parse_wiki_drops(text):
            if rows and "Stranded" not in label:
                out[(region, title, label)] = rows
    return out


VARIANT_WORDS = {"EPIC": ["epic", "venerable"], "LEGENDARY": ["legendary", "exalted"], "MYTHIC": ["mythic", "empyrean"]}


def pick_tab(tabs, mob, variant):
    if not tabs:
        return None
    hint = (variant or "") + " " + (re.search(r"\((.*)\)", mob) or [None, ""])[1] + " " + mob.split(" Mithril")[0]
    words = [w.lower() for w in hint.split()] + VARIANT_WORDS.get(variant, [])
    for label, rows in tabs:
        if label and any(w and w in label.lower() for w in words):
            return rows
    return tabs[0][1] if len(tabs) == 1 or not variant else None


# Wiki name -> forum name, after lowercasing. Only true renames/aliases, never different items.
ITEM_ALIAS = {
    "enchanted gold ingot": "enchanted gold", "clay ball": "clay", "enchanted clay ball": "enchanted clay",
    "ink sac": "ink", "raw mutton": "mutton", "enchanted raw mutton": "enchanted mutton", "wool": "white wool",
    "rabbit's foot": "rabbit foot", "redstone dust": "redstone", "enchanted redstone dust": "enchanted redstone",
    "enchanted iron ingot": "enchanted iron", "millennia-old blaze ashes": "milennia-old blaze ashes",
    "condensed lily pads": "condensed lily pad", "lapis lazuli": "lapis", "fire protection 6": "fire protection vi",
    "void conqueror enderman skin": "void conqueror", "exceedingly rare ender artifact upgrade": "exceedingly rare ender artifact upgrader",
}


def norm(name):
    n = name.lower().replace("’", "'").strip()
    n = re.sub(r"^enchanted book &(.*)&$", r"\1", n)
    n = re.sub(r" pet$", "", n)
    n = re.sub(r"^enchanted book \((.*)\)$|^(.* rune) i$", lambda m: m[1] or m[2], n)
    n = ITEM_ALIAS.get(n, n)
    return re.sub(r"[^a-z0-9 ]", "", n).replace("  ", " ").strip()


ARMOR = ("helmet", "chestplate", "leggings", "boots")


def old_lookup(old_by, item):
    """Exact match, else expand the wiki's grouped 'X Armor Piece' row to each piece."""
    k = norm(item)
    if k in old_by:
        return k
    words = k.rsplit(" ", 1)
    if len(words) == 2 and words[1] in ARMOR and words[0] + " armor piece" in old_by:
        return words[0] + " armor piece"
    return None


def keep(item, mob):
    """Dyes have their own rows; hunting shards aren't part of the rework (slayer boss shards are real loot)."""
    return "Dye" not in item and (not item.endswith(" Shard") or item == "Earth Shard" or mob in SLAYERS)


def main():
    nov10 = first_post_text(fetch(NOV10, "nov10.html"))
    tables = parse_new_tables(nov10)
    slayers, sheet_dyes = slayer_tables()
    tables.update(slayers)
    pages = wiki_pages(page_for(r, m) for (r, m, _) in tables if page_for(r, m))
    texts = wiki_pages(SLAYERS)
    bosses = {b: slayer_live(t) for b, t in texts.items()}

    rows, missing = [], []
    for (region, mob, variant), new_rows in tables.items():
        page = pages.get(page_for(region, mob))
        old_rows = (bosses[mob].get(variant) if mob in bosses else
                    pick_tab(parse_wiki_drops(page), mob, variant) if page and region != "Slayer" else None)
        if old_rows is None:
            missing.append(f"{region} / {mob} {variant}".strip())
        old_by = {norm(r["item"]): r for r in (old_rows or []) if keep(r["item"], mob)}
        rule = SLAYER_RULE.get(mob, {}) if mob in bosses else {}
        seen = set()
        for i, r in enumerate(new_rows):
            k = old_lookup(old_by, r["item"])
            # a second roll of the same item (e.g. 100% + 40%) has no live counterpart
            o = None if any(x["item"] == r["item"] for x in new_rows[:i]) else old_by.get(k)
            seen.add(k)
            rows.append({"region": region, "mob": mob, "variant": variant, "item": r["item"],
                         "newChance": r["chance"], "newAmount": r["amount"],
                         "oldChance": o["chance"] if o else None, "oldAmount": o["amount"] if o else None,
                         "status": ("changed" if (o["chance"], o["amount"]) != (r["chance"], r["amount"]) else "same") if o
                         else ("unknown" if old_rows is None else "added"), **rule})
        if old_rows is not None:
            for k, o in old_by.items():
                if k not in seen:
                    rows.append({"region": region, "mob": mob, "variant": variant, "item": o["item"],
                                 "newChance": None, "newAmount": None, "oldChance": o["chance"], "oldAmount": o["amount"],
                                 "status": "removed", **rule})

    rows += slayer_dyes(nov10, sheet_dyes)
    # Nov 10 Dyes spoiler: "Increased Superior Dragon drop rate from 1/50,000 → 1/25,000" (other dragons unchanged)
    rows.append({"region": "Dragon's Nest", "mob": "Ender Dragon", "variant": "Superior", "item": "Pearlescent Dye",
                 "newChance": 1 / 25000, "newAmount": 1, "oldChance": 1 / 50000, "oldAmount": 1, "status": "changed"})
    # End Stone Protector's wiki loot is a plain wikitable (quality-based), not Mob Drops Rows
    rows += [{"region": "The End", "mob": "End Stone Protector", "variant": "", "item": item, "newChance": c,
              "newAmount": 1, "oldChance": c, "oldAmount": 1, "status": "unlisted"}
             for item, c in [("Tier Boost Core", 0.002), ("LEGENDARY Golem Pet", 0.006), ("EPIC Golem Pet", 0.02)]]
    texts.update(wiki_pages(["End Stone Protector", "Arachne"]))
    # Arachne's wiki loot is a plain wikitable per tier: Drop | Count | Requirement | Chance
    sec = texts["Arachne"][texts["Arachne"].find("== Drops"):texts["Arachne"].find("</tabber>")]
    for tier, body in re.findall(r"\|-\|([^=\n]+)=(.*?)(?=\|-\|[^=\n]+=|$)", sec, re.S):
        for row in body.split("\n|-")[1:]:
            c = wt_cells(row)
            if len(c) == 4 and keep(c[0], "Arachne"):
                pet = re.search(r"rarity=(\w)", row)
                item = (rarity(pet[1]) + " " if pet else "") + c[0]
                rows.append({"region": "Spider's Den", "mob": "Arachne", "variant": tier.strip(), "item": item,
                             "newChance": parse_chance(c[3]), "newAmount": avg_amount(c[1].split(" +")[0]),
                             "oldChance": parse_chance(c[3]), "oldAmount": avg_amount(c[1].split(" +")[0]),
                             "status": "unlisted"})
    for (region, mob, variant), old_rows in unlisted_tables(set(pages.values()) | set(pages), texts).items():
        rows += [{"region": region, "mob": mob, "variant": variant, "item": o["item"],
                  "newChance": o["chance"], "newAmount": o["amount"], "oldChance": o["chance"], "oldAmount": o["amount"],
                  "status": "unlisted"} for o in old_rows if keep(o["item"], mob)]
    apply_changes(rows)

    for r in rows:
        text = texts.get(r["mob"]) or pages.get(page_for(r["region"], r["mob"]))
        r["types"] = mob_tags(r["mob"], text)
        if {"Magmatic", "Sea Creature"} <= set(r["types"]):
            r["types"].append("Lava Sea Creature")
        if r["mob"] in ("Arachne", "Broodmother", "Tarantula Broodfather"):  # Shriveled Bracelet
            r["types"].append("Arachne / Broodmother / Tarantula")
        if r["region"] == "Slayer" and r["mob"] in SLAYER_TYPE:
            r["types"] = [SLAYER_TYPE[r["mob"]]] if r.get("rift") else r["types"] + [SLAYER_TYPE[r["mob"]]]
        if "Catacombs" in r["region"]:
            r["floors"] = dungeon_floors(r["mob"], r["region"], text)
            r["region"] = "Catacombs"

    out = HERE.parent / "data.js"
    out.write_text("// Generated by build/build.py — do not edit.\nconst DROPS = " + json.dumps(rows, indent=0) + ";\n", encoding="utf8")
    counts = {s: sum(r["status"] == s for r in rows) for s in ("changed", "same", "added", "removed", "unknown", "unlisted")}
    print(f"{len(tables)} mob tables, {len(rows)} rows -> {out}\n{counts}")
    print("no old wiki table for:", ", ".join(missing), file=sys.stderr)


if __name__ == "__main__":
    main()
