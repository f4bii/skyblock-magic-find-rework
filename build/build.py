"""Builds ../data.js: new (alpha) drop tables from the Hypixel forum posts joined
with the current live drop tables scraped from the Hypixel SkyBlock wiki.

Run: python3 build/build.py   (downloads into build/cache on first run; delete it to refresh)
"""
import hashlib, html, json, re, sys, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).parent
CACHE = HERE / "cache"
CACHE.mkdir(exist_ok=True)
OCT15 = "https://hypixel.net/threads/october-15-magic-find-rework-ghost-visitors.6162638/"
SHEET = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQQA1fvuNx1bVwfTI9066zQ64JnNP6UhJyTy9P7PcD2SrokmZ4BR6GZ0vOJp5hI2pCpPLwS08o-N-YO/pub?output=csv&gid="
REV_TIERS = {"Tier 1": "0", "Tier 2": "1124738662", "Tier 3": "659254893", "Tier 4": "2114925198", "Tier 5": "827796101"}
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


DROP_RE = re.compile(r"^(?:([\d,]+)x )?(.+?) \(([\d.]+)%\)$")
GRIFFIN = ["COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY", "MYTHIC"]
SKIP_SECTIONS = {"Dyes", "Jerrypocalypse"}


def parse_new_tables(lines):
    """-> {(region, mob, variant): [ {item, amount, chance} ]}"""
    start = lines.index("➥ New Drop Tables")
    end = lines.index("➥ Related Changes")
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
            out[key].append({"item": m[2], "amount": int((m[1] or "1").replace(",", "")), "chance": float(m[3]) / 100})
    return {k: v for k, v in out.items() if v}


def patch_oct22(t):
    """Oct 22 alpha changes, transcribed from the 'Magic Find Rework Testing #2' post."""
    def mob(region, name, variant=""):
        return t.setdefault((region, name, variant), [])

    def set_chance(rows, item, pct):
        for r in rows:
            if r["item"] == item:
                r["chance"] = pct / 100
                return
        rows.append({"item": item, "amount": 1, "chance": pct / 100})

    def remove(rows, item):
        rows[:] = [r for r in rows if r["item"] != item]

    for v in ("LEGENDARY", "MYTHIC"):
        set_chance(mob("Mythological Ritual", "Sphinx", v), "Looting VII", 1)
    set_chance(mob("Crimson Isle", "Milennia-Aged Blaze"), "Fire Aspect III", 0.1)
    grim = mob("Spooky Festival", "Grim Reaper")
    set_chance(grim, "Shredded Line", 1)
    set_chance(grim, "Deep Sea Orb", 4)
    set_chance(mob("Spooky Festival", "Werewolf"), "Deep Sea Orb", 0.2)
    set_chance(mob("Spooky Festival", "Phantom Fisher"), "Deep Sea Orb", 1)
    set_chance(mob("Backwater Bayou", "Alligator"), "Box of Junk", 20)
    for size, n in (("Small", 1), ("Medium", 2), ("Large", 4), ("Bloated", 12)):
        mob("Dwarven Mines", f"{size} Mithril Grubber").append({"item": "Plasma", "amount": n, "chance": 0.025})
    # Lotus Atoll wasn't in the Oct 15 tables, so these mobs only list what Oct 22 touched.
    for name, rows in {
        "Atoll Croaker": [("Tropical Fish", 100)],
        "Lotus Guardian": [("Tropical Fish", 100)],
        "gorF": [("Tropical Fish", 100), ("Enchanted Tropical Fish", 5)],
        "Drowned Captain": [("Enchanted Tropical Fish", 20), ("Unlucky Doubloon", 2.5)],
        "Puddle Jumper": [("Enchanted Tropical Fish", 100)],
        "Frog Prince": [("Enchanted Tropical Fish", 100), ("Prince's Crown Jewel", 1)],
        "Puck": [("Bottled Mischief", 10)],
    }.items():
        for item, pct in rows:
            set_chance(mob("Lotus Atoll", name), item, pct)
    for v, pct in (("EPIC", 0.15), ("LEGENDARY", 0.2), ("MYTHIC", 0.25)):
        set_chance(mob("Mythological Ritual", "Minotaur", v), "Daedalus Stick", pct)
    zombie = [{"item": "Rotten Flesh", "amount": 1, "chance": 1}, {"item": "Poisonous Potato", "amount": 1, "chance": 0.05},
              {"item": "Potato", "amount": 1, "chance": 0.025}, {"item": "Carrot", "amount": 1, "chance": 0.025}]
    t[("Private Island", "Zombie", "")] = [dict(r) for r in zombie]
    t[("Hub", "Graveyard Zombie", "")] = [dict(r) for r in zombie]
    set_chance(mob("Mythological Ritual", "Manticore", "MYTHIC"), "Manti-Core", 0.75)
    set_chance(mob("Mythological Ritual", "King Minos", "MYTHIC"), "Shimmering Wool", 0.75)
    littlefoot = mob("Glacite Mineshafts", "Littlefoot")
    set_chance(littlefoot, "Glacite Amalgamation", 5)
    for item in ("Umber Key", "Tungsten Key", "Skeleton Key"):
        remove(littlefoot, item)


PARTIAL = {"Atoll Croaker", "Lotus Guardian", "gorF", "Drowned Captain", "Puddle Jumper", "Frog Prince", "Puck"}


def revenant_tables():
    out = {}
    for tier, gid in REV_TIERS.items():
        rows = []
        for line in fetch(SHEET + gid, f"revenant_{gid}.csv").splitlines()[1:]:
            item, amount, chance = re.match(r'([^,]+),([^,]+),("[^"]*"|[^,]+)', line).groups()
            if "Dye" in item:
                continue
            lo, _, hi = amount.partition("-")
            rows.append({"item": item, "amount": (int(lo) + int(hi or lo)) / 2, "chance": float(chance.strip("%")) / 100})
        out[("Slayer", "Revenant Horror", tier)] = rows
    return out


def slayer_dyes(lines):
    """Slayer bosses keep their weight-based tables on Alpha (only Revenant moved); the only
    rate changes for the others are their dyes, given in the Dyes spoiler as 'T1: 1/X → 1/Y'."""
    rows, dye, boss = [], None, None
    for line in lines:
        if line.rstrip(" |").endswith(" Dye"):
            dye, boss = line.rstrip(" |"), None
        elif m := re.match(r"Increased (.+) drop rates:$", line):
            boss = m[1] if dye and m[1] in SLAYERS else None
        elif boss and (m := re.match(r"T(\d): 1/([\d,]+) → 1/([\d,]+)", line)):
            old, new = (1 / int(x.replace(",", "")) for x in m.groups()[1:])
            rows.append({"region": "Slayer", "mob": boss, "variant": f"Tier {m[1]}", "item": dye,
                         "newChance": new, "newAmount": 1, "oldChance": old, "oldAmount": 1, "status": "changed",
                         **SLAYER_RULE.get(boss, {"weighted": "both"})})
    return rows


SLAYERS = {"Revenant Horror", "Tarantula Broodfather", "Sven Packmaster", "Voidgloom Seraph",
           "Inferno Demonlord", "Riftstalker Bloodfiend"}
# How app.js rolls slayer boss loot: "weighted" sides use the live slayer rule (MF only below 5%, no Looting).
# Revenant moved to the normal system on Alpha; Riftstalker is in the Rift, where MF doesn't exist.
SLAYER_RULE = {"Revenant Horror": {"weighted": "old"}, "Riftstalker Bloodfiend": {"noMf": True}}


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


RARITY_CODE = {"c": "COMMON", "u": "UNCOMMON", "r": "RARE", "e": "EPIC", "l": "LEGENDARY", "m": "MYTHIC"}


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
            item = re.sub(r"\$(\w+)\$\s*", lambda m: RARITY_CODE.get(m[1].lower(), m[1].upper()) + " ", f["drop"]).strip()
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
        if text in covered_texts or title == "Baby Magma Slug" or "motes" in text or "{{mt|Pest}}" in text \
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
    tables = parse_new_tables(first_post_text(fetch(OCT15, "oct15.html")))
    patch_oct22(tables)
    tables.update(revenant_tables())
    pages = wiki_pages(page_for(r, m) for (r, m, _) in tables if page_for(r, m))
    texts = wiki_pages(SLAYERS - {"Riftstalker Bloodfiend"})
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
        for r in new_rows:
            k = old_lookup(old_by, r["item"])
            o = old_by.get(k)
            seen.add(k)
            rows.append({"region": region, "mob": mob, "variant": variant, "item": r["item"],
                         "newChance": r["chance"], "newAmount": r["amount"],
                         "oldChance": o["chance"] if o else None, "oldAmount": o["amount"] if o else None,
                         "status": ("changed" if (o["chance"], o["amount"]) != (r["chance"], r["amount"]) else "same") if o
                         else ("unknown" if old_rows is None else "added"), **rule})
        if old_rows is not None and mob not in PARTIAL:
            for k, o in old_by.items():
                if k not in seen:
                    rows.append({"region": region, "mob": mob, "variant": variant, "item": o["item"],
                                 "newChance": None, "newAmount": None, "oldChance": o["chance"], "oldAmount": o["amount"],
                                 "status": "removed", **rule})

    rows += slayer_dyes(first_post_text(fetch(OCT15, "oct15.html")))
    # Oct 15 Dyes spoiler: "Increased Superior Dragon drop rate from 1/50,000 → 1/25,000" (other dragons unchanged)
    rows.append({"region": "Dragon's Nest", "mob": "Ender Dragon", "variant": "Superior", "item": "Pearlescent Dye",
                 "newChance": 1 / 25000, "newAmount": 1, "oldChance": 1 / 50000, "oldAmount": 1, "status": "changed"})
    # End Stone Protector's wiki loot is a plain wikitable (quality-based), not Mob Drops Rows
    rows += [{"region": "The End", "mob": "Endstone Protector", "variant": "", "item": item, "newChance": c,
              "newAmount": 1, "oldChance": c, "oldAmount": 1, "status": "unlisted"}
             for item, c in [("Tier Boost Core", 0.002), ("LEGENDARY Golem Pet", 0.006), ("EPIC Golem Pet", 0.02)]]
    texts.update(wiki_pages(["Endstone Protector"]))
    for (region, mob, variant), old_rows in unlisted_tables(set(pages.values()), texts).items():
        rows += [{"region": region, "mob": mob, "variant": variant, "item": o["item"],
                  "newChance": o["chance"], "newAmount": o["amount"], "oldChance": o["chance"], "oldAmount": o["amount"],
                  "status": "unlisted"} for o in old_rows if keep(o["item"], mob)]
    # the other bosses keep their weight tables on Alpha: same base rates, new MF
    for boss, tiers in bosses.items():
        if boss in SLAYER_RULE:
            continue
        for tier, old_rows in tiers.items():
            rows += [{"region": "Slayer", "mob": boss, "variant": tier,
                      # Oct 22: Fire Aspect III replaced by Smoldering VI, same weight
                      "item": "Smoldering VI (was Fire Aspect III)" if o["item"] == "Fire Aspect III" else o["item"],
                      "newChance": o["chance"], "newAmount": o["amount"], "oldChance": o["chance"], "oldAmount": o["amount"],
                      "status": "unlisted", "weighted": "both"} for o in old_rows if keep(o["item"], boss)]

    for r in rows:
        text = texts.get(r["mob"]) or pages.get(page_for(r["region"], r["mob"]))
        r["types"] = mob_tags(r["mob"], text)
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
