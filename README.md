# Machine-Learning-Venues

Public ML / learning-theory conference deadline tracker plus a global graduate-student funding tracker.

## Pages

- `index.html` — paper submission deadlines
- `funding.html` — graduate funding opportunities

## Funding architecture

`data/funding-programs.json` contains **verified** programs from official sources.

The funding page includes:
- conference-specific student grants;
- umbrella grants usable at many conferences;
- society travel grants;
- PhD/research fellowships that explicitly include research or conference travel;
- future-call watches such as ICLR/ECML PKDD.

The default verified dataset intentionally excludes grants where an **accepted paper is a hard requirement**.

### Dynamic updates

Every day, GitHub Actions runs:

```text
scripts/update_deadlines.py
scripts/update_funding_programs.py
scripts/discover_funding.py
```

`update_funding_programs.py` conservatively checks official pages for newly posted deadlines.

`discover_funding.py` scans official organizations for new pages containing terms such as grant, scholarship, travel support, subsidy, mobility, and fellowship. New links go to:

`data/discovered-funding.json`

They are **not automatically published** as verified programs. This prevents a scraper from accidentally turning an unrelated or accepted-paper-only grant into a public recommendation.

## Why the discovery queue exists

There is no single public registry of every student conference/travel grant in every country. Programs are announced by conferences, ACM/IEEE societies, universities, research networks, government projects, and companies at different times.

The discovery queue lets the site keep expanding while preserving source quality.

## GitHub Pages

Settings → Pages → Deploy from branch → `main` → `/ (root)`.

Expected URL:

`https://ritaadhikari.github.io/Machine-Learning-Venues/`

Funding page:

`https://ritaadhikari.github.io/Machine-Learning-Venues/funding.html`

## GitHub Actions permission

Settings → Actions → General → Workflow permissions → **Read and write permissions**.

Then you can manually test:

Actions → **Update ML deadlines and funding** → **Run workflow**.

## Local preview

Because the pages load JSON:

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000/`.
# Graduate-students-funding-opportunites
