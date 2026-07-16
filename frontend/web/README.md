# Web frontend — BSBA Freshman Scheduling Tool

Static HTML/CSS/JS app (no build step, no framework) built from
`../bsba-scheduling-tool-mockup.html`, wired to real data. This is the
deployable frontend — `frontend/app.py` (Streamlit) still exists as a
quick internal tool but this is the one that matches the approved design.

## Run it locally, no AWS deploy needed

Browsers block `fetch()` of local JSON over `file://`, so open this folder
through a tiny static server instead of double-clicking `index.html`:

```
cd frontend/web
python -m http.server 8000
```

Then open **http://localhost:8000**. With `config.js`'s `API_BASE_URL` left
as `""` (the default), the app runs in **demo mode**: it reads
`data/recommendation.json` (a checked-in snapshot of the mining output) for
the term picker, top pick, calendar, and comparison view. The AI rationale
and the Q&A box are disabled in this mode and say so — there's no Bedrock
call to make without a deployed API.

Any other static server works the same way — `npx serve`, VS Code's Live
Server extension, etc. The only requirement is "served over http, not
opened as a file."

## Point it at the real AWS API

Once `infra/deploy.sh` has run and you have the `ApiUrl` stack output:

1. Open `config.js`.
2. Set `API_BASE_URL` to that URL, e.g.
   `const API_BASE_URL = "https://abc123.execute-api.us-west-2.amazonaws.com/Prod";`
   (no trailing slash needed, the app strips one if present).
3. Reload. The status ribbon at the top switches to "LIVE — connected to
   ...", the rationale box calls Bedrock through `/recommendation`, and the
   Q&A box calls `/ask`.

If the API is unreachable (wrong URL, CORS not deployed yet, stack down),
the app automatically falls back to the local snapshot and says so in the
ribbon and a banner — it won't just show a blank page.

## Refreshing the offline snapshot

`data/recommendation.json` is a point-in-time copy of
`../../data/output/recommendation.json`. Regenerate the source with:

```
python -m mining.co_occurrence
```

then copy it over:

```
cp ../../data/output/recommendation.json data/recommendation.json
```

## Editing the BSBA concentration list or terms

Everything configurable lives in `config.js`:
- `BSBA_CONCENTRATIONS` — the options in the "Concentration" picker.
  UI-only today; see the comment in `config.js` and the assumptions panel
  in the app itself for why (freshman-year data is pooled across
  concentrations, per `CHANGES.md`).
- `API_BASE_URL` / `LOCAL_SNAPSHOT_PATH` — see above.

## Deploying as a real static site

Any static host works (S3 + CloudFront, GitHub Pages, Netlify). Upload
`index.html`, `styles.css`, `config.js`, `app.js`, and `data/` as-is — set
`API_BASE_URL` in `config.js` before uploading so it goes live pointed at
the deployed API.
