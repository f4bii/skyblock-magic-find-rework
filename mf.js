// Drop math for the live (old) and alpha (new) Magic Find systems.
// Each function returns { p: chance of at least one drop per kill, avg: expected items per kill }.

const OLD_CAP = 900;
const NEW_CAP = 500;
// Oct 23 / Nov 10: Looting I-VII = +2.5/5/7.5/10/15/20/25 Magic Find
const NEW_LOOTING_MF = [0, 2.5, 5, 7.5, 10, 15, 20, 25];
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

// Alpha (Nov 10 RC): MF scales every drop's chance; past 100% the overflow is a chance at another full stack
// ("150 MF, 8x Lily Pad (100%) -> guaranteed 16x with a 50% chance of 24"). Pet Luck is assumed to work as before.
function newDrop(chance, amount, { mf, petLuck }, pet) {
  const x = chance * (1 + (Math.min(mf, NEW_CAP) + (pet ? petLuck : 0)) / 100);
  return { p: Math.min(x, 1), avg: x * amount };
}

if (typeof module !== "undefined") module.exports = { oldDrop, newDrop, isPet, NEW_LOOTING_MF, OLD_TO_NEW_LOOTING, OLD_CAP, NEW_CAP };
