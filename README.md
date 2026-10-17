# Elements

**How North Carolina's crimes are built.**

Elements is an interactive explainer of North Carolina criminal offenses, organized by each offense's legal elements. You can drill down from broad categories to specific offenses, compare two or three offenses side by side, build an offense by answering questions, or search for a crime and read a plain-language explanation.

It explains what the law says an offense is made of. It does not say whether anyone did it, it does not predict any charge or outcome, and it is not legal advice.

## Status: early beta, unverified drafts

Every record in the data file is marked `draft`. None has been verified line by line against the current statutes, and some may be wrong. Do not rely on this for any real situation.

What has been checked so far:

- The homicide statutes (G.S. 14-17 and 14-18) were read as full text.
- Many records were compared with the North Carolina Pattern Jury Instructions (N.C.P.I.-Crim.). Each record lists what it was compared against under `cross_checks`. A cross-check is a comparison, not verification.
- The remaining statutes need a word-for-word check.

See `handoff.md` for the full list of what is verified, what is not, and what is planned.

## Files

| File | What it is |
| --- | --- |
| `index.html` | The whole tool: plain HTML, CSS and JavaScript, no libraries. |
| `elements-nc.json` | The data: categories, elements, offenses, question flows, and compare presets. Every record has a `jurisdiction` field. |
| `handoff.md` | Where things stand, decisions made, and next steps. |

## Run it on your computer

The page loads `elements-nc.json` from the same folder, so keep the two files together. Browsers block that automatic load when a page is opened straight from a folder, so use a local server:

```
python -m http.server
```

Then open `http://localhost:8000` in your browser. If you open the page directly instead, use the "Choose file" button to load `elements-nc.json`.

## How the data works

Everything the page shows comes from the JSON file, so adding or fixing an offense is mostly a data edit. Plain-language text is written and reviewed by a person, stored in each record, and never generated live. The schema version and a log of schema changes are in the file's `meta` section.

## Sources

- North Carolina General Statutes, https://www.ncleg.gov/Laws/GeneralStatutes
- North Carolina Pattern Jury Instructions for Criminal Cases, UNC School of Government, https://www.sog.unc.edu/resources/microsites/north-carolina-pattern-jury-instructions/north-carolina-pattern-jury-instructions-criminal-cases

Pattern jury instructions are a summary of the law written for judges. Where an instruction is older than the statute, the statute is followed.

## About

A personal prototype. It is not an official publication of any government agency.
