const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const num = (el) => Math.max(0, Number(el.value) || 0);
const ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII"];
const NO_MF = { mf: 0, looting: 0, petLuck: 0 };
// Alpha conditional MF by mob type: [max when every source is stacked, sources] (Oct 15 + Oct 22 posts)
const TYPE_MF = {
  "Slayer Boss": [30, "Wolf Fur Mixin 5, Habanero Tactics V 5, Aatrox Pathfinder doubled +20"],
  Mythological: [84, "Crown of Avarice 10, King of Kings 10, Daedalus Blade 0.2/bestiary tier (~46), Four-Eyed Fish 5, Golden Fleece 5, Minotaur Shard 5, Diana's Favor 3"],
  "Sea Creature": [5, "Bobbin' Time V 5"],
  Shark: [18, "Megalodon Blood Scent 10, Shark Tooth Souvenir 5, Denture Collector 3"],
  "Winter Sea Creature": [10, "Nutcracker Armor 10"],
  Magmatic: [15, "Lava Flame Shard 10, Magma Lord Armor 5"],
  Ghost: [10, "Sorrow Armor 10"],
  Automaton: [10, "Mole Magnetic Nose 10"],
  Undead: [5, "Drowned Shard 5"], Arthropod: [5, "Black Widow Shard 5"], Frozen: [5, "Billygoat Shard 5"],
  Subterranean: [5, "Chuckwalla Shard 5"], Aquatic: [5, "Giant Water Bug Shard 5"], Critter: [5, "Hewver Shard 5"],
  Woodland: [5, "Hideonfloor Shard 5"], Arcane: [5, "Hideonwall Shard 5"], Elusive: [5, "Hideyho Shard 5"],
  Cubic: [5, "Hivethief Shard 5"], Airborne: [5, "Parakeet Shard 5"], Construct: [5, "Wiki Tiki Shard 5"], Animal: [5, "Wild Hog Shard 5"],
};
$("types").innerHTML = Object.entries(TYPE_MF).map(([t, [max, src]]) =>
  `<label><span>${t} (max ${max})<span class="sub">${src}</span></span><input type="number" min="0" step="0.5" value="${max}" data-type="${t}" data-max="${max}"></label>`).join("");

for (const r of [...new Set(DROPS.map((d) => d.region))].sort()) $("region").add(new Option(r, r));

// Slayer -> tier, Catacombs -> floor; other areas have no second filter
const SUB = {
  Slayer: ["All tiers", [1, 2, 3, 4, 5].map((t) => [`Tier ${t}`, `Tier ${t}`])],
  Catacombs: ["All floors", [["0", "Entrance"], ...[1, 2, 3, 4, 5, 6, 7].map((f) => [String(f), `Floor ${f}`])]],
};
function updateSub() {
  const s = SUB[$("region").value];
  $("subWrap").hidden = !s;
  if (!s) return;
  $("subName").textContent = s[0] === "All tiers" ? "Slayer tier" : "Dungeon floor";
  $("sub").replaceChildren(new Option(s[0], ""), ...s[1].map(([v, t]) => new Option(t, v)));
}

function pct(p) {
  return `${+(p * 100).toPrecision(3)}%`;
}

function fmtResult(r, amount) {
  if (!r) return "—";
  if (r.p >= 1) return `<b>${+r.avg.toFixed(2)}</b> / kill`;
  const stack = amount > 1 ? ` <span class="sub">×${+amount.toFixed(1)} per drop</span>` : "";
  return `<b>${pct(r.p)}</b><span class="sub">1 in ${Math.round(1 / r.p).toLocaleString()}</span>${stack}`;
}

function fmtBase(chance, amount) {
  if (chance == null) return "—";
  return (amount > 1 ? `${+amount.toFixed(1)}× ` : "") + pct(chance);
}

function fmtChange(row, ratio) {
  if (row.status === "added") return `<span class="badge up">new drop</span>`;
  if (row.status === "removed") return `<span class="badge down">removed</span>`;
  if (ratio == null) return `<span class="badge same">no live data</span>`;
  const d = (ratio - 1) * 100;
  if (Math.abs(d) < 0.5) return `<span class="delta same">±0%</span>`;
  const text = ratio >= 2 ? `×${ratio.toFixed(ratio >= 10 ? 0 : 1)}` : `${d > 0 ? "+" : "−"}${Math.abs(d).toFixed(0)}%`;
  return `<span class="delta ${d > 0 ? "up" : "down"}">${text}</span>`;
}

function updateEstimate() {
  let sum = 0, mult = 1;
  for (const el of $("est").querySelectorAll("input")) {
    if (el.dataset.mult) { if (el.checked) mult *= Number(el.dataset.mult); continue; }
    if (el.type === "checkbox") sum += el.checked ? Number(el.dataset.mf) : 0;
    else if (el.dataset.per) sum += Math.floor(num(el) / Number(el.dataset.per));
    else sum += num(el) * Number(el.dataset.mf);
  }
  $("newMf").value = +(sum * mult).toFixed(1);
  render();
}

function render() {
  const oldLoot = Number($("oldLoot").value), newLoot = Number($("newLoot").value);
  const petLuck = num($("petLuck"));
  const oldS = { mf: num($("oldMf")), looting: oldLoot, petLuck };
  const lootMf = NEW_LOOTING_MF[newLoot];
  const newS = { mf: num($("newMf")) + lootMf, petLuck };
  const typeMf = {};
  for (const el of $("types").querySelectorAll("input")) typeMf[el.dataset.type] = num(el);

  $("summary").innerHTML =
    `Live: <strong>${Math.min(oldS.mf, OLD_CAP)} MF</strong>${oldS.mf > OLD_CAP ? " (capped)" : ""}` +
    (oldLoot ? `, Looting ${ROMAN[oldLoot]} = ×${(1 + 0.15 * oldLoot).toFixed(2)} base chance` : "") +
    ` &nbsp;·&nbsp; Alpha: <strong>${+Math.min(newS.mf, NEW_CAP).toFixed(1)} MF</strong>${newS.mf > NEW_CAP ? " (capped at 500)" : ""}` +
    (lootMf ? ` incl. +${lootMf} from Looting ${ROMAN[newLoot]}` : "");

  const q = $("q").value.trim().toLowerCase(), region = $("region").value, status = $("status").value;
  const sub = SUB[region] ? $("sub").value : "";
  const rows = [];
  for (const r of DROPS) {
    if (region && r.region !== region) continue;
    // rows without a tier (slayer minibosses) or a known floor show for every choice
    if (sub && (region === "Slayer" ? r.variant && r.variant !== sub : r.floors?.length && !r.floors.includes(Number(sub)))) continue;
    if (q && !`${r.mob} ${r.variant} ${r.item}`.toLowerCase().includes(q)) continue;
    if (status === "rare" ? (r.newChance ?? r.oldChance) > 0.05 : status && r.status !== status) continue;
    const pet = isPet(r.item);
    // slayer boss loot: weighted tables ignore Looting and only boost drops under 5%; the Rift has no MF
    const os = r.noMf ? NO_MF : r.weighted ? { ...oldS, looting: 0 } : oldS;
    const extra = r.types.reduce((s, t) => s + (typeMf[t] || 0), 0);
    const ns = r.noMf ? NO_MF : { ...newS, mf: newS.mf + extra };
    const o = r.oldChance != null ? oldDrop(r.oldChance, r.oldAmount, os, pet) : null;
    const n = r.newChance == null ? null : r.weighted === "both" || r.noMf
      ? oldDrop(r.newChance, r.newAmount, { mf: Math.min(ns.mf, NEW_CAP), looting: 0, petLuck: ns.petLuck }, pet)
      : newDrop(r.newChance, r.newAmount, ns, pet);
    rows.push({ r, o, n, extra: r.noMf ? 0 : extra, ratio: o && n ? n.avg / o.avg : null });
  }

  const sort = $("sort").value;
  const key = { gain: (x) => -(x.ratio ?? -Infinity), loss: (x) => x.ratio ?? Infinity, rarest: (x) => x.n?.p ?? Infinity }[sort];
  if (key) rows.sort((a, b) => key(a) - key(b));

  $("count").textContent = `Showing ${rows.length.toLocaleString()} of ${DROPS.length.toLocaleString()} drops`;
  $("rows").innerHTML = rows.map(({ r, o, n, extra, ratio }) => {
    const rare = (r.newChance ?? r.oldChance) <= 0.05 ? " rare" : "";
    return `<tr>
      <td><span class="mob">${esc(r.mob)}</span>${r.variant ? `<span class="chip">${esc(r.variant)}</span>` : ""}<span class="sub">${esc(r.region)}${r.types.length ? ` · ${esc(r.types.join(", "))}` : ""}</span></td>
      <td class="${rare}">${esc(r.item)}</td>
      <td class="num">${fmtBase(r.oldChance, r.oldAmount)} → ${fmtBase(r.newChance, r.newAmount)}</td>
      <td class="num">${fmtResult(o, r.oldAmount)}</td>
      <td class="num">${fmtResult(n, r.newAmount)}${extra && n ? `<span class="sub">incl. +${+extra.toFixed(1)} type MF</span>` : ""}</td>
      <td>${fmtChange(r, ratio)}</td>
    </tr>`;
  }).join("");
}

$("oldLoot").addEventListener("change", () => { $("newLoot").value = OLD_TO_NEW_LOOTING[$("oldLoot").value]; render(); });
$("est").addEventListener("input", updateEstimate);
$("types").addEventListener("input", render);
for (const [id, fill] of [["typeMax", (el) => el.dataset.max], ["typeZero", () => 0]])
  $(id).addEventListener("click", () => { for (const el of $("types").querySelectorAll("input")) el.value = fill(el); render(); });
$("region").addEventListener("input", updateSub);
for (const id of ["oldMf", "newMf", "newLoot", "petLuck", "q", "region", "sub", "status", "sort"]) $(id).addEventListener("input", render);
updateEstimate();
