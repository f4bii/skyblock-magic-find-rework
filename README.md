# Magic Find Rework — Drop Rate Compare

Static site that compares Hypixel SkyBlock drop rates on the live game vs. the Alpha Magic Find rework (Oct 15 + Oct 22, 2026) for the Magic Find you enter.

- Open `index.html` directly, or serve the folder: `python3 -m http.server`.
- `python3 build/build.py` regenerates `data.js`: it parses the new tables from the Oct 15 forum post, applies the Oct 22 changes (hand-transcribed in `patch_oct22`), adds the Zombie Slayer sheet and the slayer dye changes, adds every other wiki mob with a drop table (same base rates, new MF rules), and joins everything with the live drop tables scraped from the wiki. Downloads are cached in `build/cache/`; delete it to refresh.
- `node test.cjs` checks the formulas in `mf.js` against the worked examples from Hypixel's design thread and the wiki.

When a new Alpha patch lands, add its changes to `patch_oct22` (or a new function next to it) and rebuild.

## Deploy to GitHub Pages

1. Push this folder to a GitHub repo, on the `main` branch.
2. In the repo, open **Settings → Pages** and set **Source** to **GitHub Actions**.
3. Every push to `main` runs `node test.cjs`. If the tests pass, the workflow publishes `index.html`, `app.js`, `mf.js` and `data.js`.
4. Pull requests only run the tests.

The workflow doesn't run `build/build.py`, which scrapes the wiki. Rebuild locally and commit `data.js`.
