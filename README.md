# Magic Find Rework — Drop Rate Compare

Static site that compares Hypixel SkyBlock drop rates on the live game vs. the Magic Find rework in the 0.27.3 release candidate on Alpha (Nov 10 + Nov 12, 2026) for the Magic Find you enter.

- Open `index.html` directly, or serve the folder: `python3 -m http.server`.
- `python3 build/build.py` regenerates `data.js`: it parses the drop tables from the Nov 10 release candidate post, adds Hypixel's six slayer sheets and the slayer dye changes, applies the Nov 12 changes and the Nov 10 changes written as sentences (hand-transcribed in `CHANGES`), adds every other wiki mob with a drop table (same base rates, new MF rules), and joins everything with the live drop tables scraped from the wiki. Downloads are cached in `build/cache/`; delete it to refresh.
- `python3 build/check.py` then validates every row of `data.js` against the raw sources (forum posts, slayer sheets, wiki), the formulas in `mf.js` and the MF numbers in `index.html`.
- `node test.cjs` checks the formulas in `mf.js` against the worked examples from Hypixel's design thread and the wiki.

When a new Alpha patch lands, add its changes to `CHANGES` in `build/build.py` and rebuild. If it reposts full tables, point `NOV10` at it instead.

## Deploy to GitHub Pages

1. Push this folder to a GitHub repo, on the `main` branch.
2. In the repo, open **Settings → Pages** and set **Source** to **GitHub Actions**.
3. Every push to `main` runs `node test.cjs`. If the tests pass, the workflow publishes `index.html`, `app.js`, `mf.js` and `data.js`.
4. Pull requests only run the tests.

The workflow doesn't run `build/build.py`, which scrapes the wiki. Rebuild locally and commit `data.js`.
