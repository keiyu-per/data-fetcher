# GORAGGIO Data Fetcher — verification stage

An iPhone-first data acquisition project. The first milestone is **not** the Web app: it is verifying whether a GitHub Actions runner can retrieve a normal, publicly accessible GORAGGIO all-machine HTML page without evading access restrictions.

## Existing code reused

- `goraggio.py` (v2.1.1): offline HTML parsing; three shops, CSV / JSON exports, coverage checks and self-test.
- `fetch_goraggio.py`: a **new single-request** public-page fetch test. Does not log in, simulate consent, solve CAPTCHA or circumvent HTTP 403 / 429 responses.
- `.github/workflows/goraggio-fetch.yml`: manual workflow with shop selection; initial `main` push also tests P-ARK Kitasenju SSS.

| Shop | Key | GORAGGIO ID |
| --- | --- | --- |
| ピーアーク北千住SSS | `p-ark-kitasenju-sss` | `100831` |
| コンサートホール北千住 | `concert-hall-kitasenju` | `100983` |
| ピーアーク竹ノ塚スタジオ | `p-ark-takenotsuka-studio` | `100883` |

IDs are reference values checked on 2026-09-03. Confirm any live shop identity before relying on its data.

## Test from an iPhone

Open **Actions → GORAGGIO HTML retrieval test → Run workflow**. Choose a shop and start the run. Open the run to inspect its success/failure and logs. Where available, download the `goraggio-test-results` artifact, retained 7 days.

- `fetch_status.json`: HTTP status, fetch time (UTC), parser result, row counts and diagnostics.
- `all_list.html`: the server's HTML response *only if an ordinary request succeeds*; the response might still lack machine data.
- `all_machines.csv` and `.json`: created only if the response contains parseable machine rows and the parser runs.

### Local tests

```bash
python goraggio.py --self-test
python -m unittest discover -s tests -v
python fetch_goraggio.py --shop p-ark-kitasenju-sss --output-dir output
```

`HTTP 403`, `HTTP 429`, CAPTCHA and consent pages are **not** evidence of successful acquisition. The status file distinguishes these from usable all-machine data. No credential or cookie should be committed.

## Planned architecture (not yet implemented)

iPhone Web UI (GitHub Pages) → authenticated backend/job trigger → fetcher → validated HTML → offline parser → downloadable artifact. A public GitHub Pages client must **not** embed GitHub credentials. Download-on-one-tap is not implemented yet; choose a secure way to trigger and retrieve files after the acquisition test succeeds.
