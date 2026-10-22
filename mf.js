// Drop math for the live (old) and alpha (new) Magic Find systems.
// Each function returns { p: chance of at least one drop per kill, avg: expected items per kill }.

const OLD_CAP = 900;
const NEW_CAP = 500;
// Oct 22: Looting I-VII = +1/2/3/4/6/8/10 Magic Find
const NEW_LOOTING_MF = [0, 1, 2, 3, 4, 6, 8, 10];
// Oct 22 /reclaim: Looting I-III -> V, IV -> VI, V -> VII (Chance/Luck likewise)
const OLD_TO_NEW_LOOTING = [0, 5, 5, 5, 6, 7];

function isPet(item) {
  return /^(COMMON|UNCOMMON|RARE|EPIC|LEGENDARY|MYTHIC) /.test(item) && !/Boost/i.test(item);
}

// Live: Looting multiplies the base chance (not for pets); MF only applies if the result is below 5%.
// Chances above 100% roll extra copies of the whole stack.
function oldDrop(chance, amount, { mf, looting, petLuck }, pet) {
  let x = pet ? chance : chance * (1 + 0.15 * looting);
  if (x < 0.05) x *= 1 + (Math.min(mf, OLD_CAP) + (pet ? petLuck : 0)) / 100;
  return { p: Math.min(x, 1), avg: x * amount };
}

// Alpha: MF applies to every drop. Below 100% it scales the chance (overflow = extra roll);
// at 100% it adds MF/100 items to the stack (wiki "Magic Find/Alpha" examples).
// Pet Luck on alpha pet drops is assumed to work as before.
function newDrop(chance, amount, { mf, petLuck }, pet) {
  const bonus = (Math.min(mf, NEW_CAP) + (pet ? petLuck : 0)) / 100;
  if (chance >= 1) return { p: 1, avg: amount + bonus };
  const x = chance * (1 + bonus);
  return { p: Math.min(x, 1), avg: x * amount };
}

if (typeof module !== "undefined") module.exports = { oldDrop, newDrop, isPet, NEW_LOOTING_MF, OLD_TO_NEW_LOOTING, OLD_CAP, NEW_CAP };
