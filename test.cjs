// node test.cjs — checks mf.js against the worked examples Hypixel and the wiki published.
const assert = require("node:assert/strict");
const { oldDrop, newDrop, isPet } = require("./mf.js");
const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} != ${b}`);

// Design thread, "Player A" (300 MF, Looting IV) on live
const A = { mf: 300, looting: 4, petLuck: 0 };
near(oldDrop(0.20, 1, A).p, 0.32);       // Can of Worms: Looting only
near(oldDrop(0.045, 1, A).p, 0.072);     // Bronze Bowl: Looting pushes it past 5%, no MF
near(oldDrop(0.01, 1, A).p, 0.064);      // Calcified Heart
near(oldDrop(0.002, 1, A).p, 0.0128);    // Titanoboa Shed
near(oldDrop(1, 1, A).avg, 1.6);         // Alligator Skin: 1 + 60% for a 2nd
// Looting page: 2x Rotten Flesh at 100% with Looting IV -> avg 3.2
near(oldDrop(1, 2, { mf: 0, looting: 4, petLuck: 0 }).avg, 3.2);

// Design thread, "Player C" (100 MF) on alpha
const C = { mf: 100, petLuck: 0 };
near(newDrop(0.20, 1, C).p, 0.40);
near(newDrop(0.01, 1, C).p, 0.02);
near(newDrop(0.75, 1, C).avg, 1.5);      // Alligator Skin: 1 + 50% for a 2nd
// Wiki Magic Find/Alpha examples
near(newDrop(0.025, 1, { mf: 145, petLuck: 0 }).p, 0.06125);
near(newDrop(0.5, 1, { mf: 122, petLuck: 0 }).avg, 1.11);
near(newDrop(1, 8, { mf: 145, petLuck: 0 }).avg, 9.45);
near(newDrop(1, 4, { mf: 122, petLuck: 0 }).avg, 5.22);
// caps
near(newDrop(0.01, 1, { mf: 9999, petLuck: 0 }).p, 0.06);
near(oldDrop(0.01, 1, { mf: 9999, looting: 0, petLuck: 0 }).p, 0.10);

assert.ok(isPet("LEGENDARY Scatha Pet") && isPet("RARE Flying Fish") && !isPet("EPIC Combat XP Boost") && !isPet("Bone"));
// pets ignore Looting on live
near(oldDrop(0.001, 1, { mf: 0, looting: 5, petLuck: 0 }, true).p, 0.001);
console.log("ok");
