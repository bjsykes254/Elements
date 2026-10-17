# Elements: where things stand (as of Oct 17, 2026)

Elements is an interactive explainer of North Carolina criminal offenses, built from each offense's legal elements. The page (`index.html`, formerly `elements.html`) reads everything from the data file (`elements-nc.json`). Keep both in one folder. Open through a local server (`python3 -m http.server`) for automatic loading, or use the "Choose file" button.

## Where the files live
- Source of truth: the folder `Documents\Elements` on the owner's computer (version controlled in Positron) and the public GitHub repository bjsykes254/Elements. Copies in the Claude Writing project are older snapshots.
- GitHub Pages is on: public beta at https://bjsykes254.github.io/Elements/ (live Oct 17). Pushing to main republishes in a minute or two.
- Licenses: MIT for code (LICENSE); CC BY 4.0 for the data (LICENSE-DATA.md). The data file's meta carries a draft/reuse notice.

## Built
- Data file (schema 0.5): 22 offenses in 4 families (homicide 4, burglary and breaking or entering 4, larceny 2, assault 12), plus elements, bubble flows, compare presets, and search aliases. Every record has a `jurisdiction` field.
- Three modes: Build an offense (bubble game), Compare (2 offenses, 3 on wide screens), Find (category drill-down, search, plain-language offense pages).
- Beta banner and a collapsed "questions for testers" block on the page; README added.
- Guards against misreading: a permanent scope note under the title, neutral Build-mode wording (questions describe an offense, not an incident), a "Keep in mind" section on every offense card and compare view (overlap between offenses; not a prediction of any charge), and a "What this tool doesn't cover" box at the bottom of every mode.
- Offenses can carry `cross_checks` (comparison against outside sources). A cross-check is not verification.
- Schema notes are in the data file under `meta.schema_changes`.

## Changed Oct 17 (cross-check against the free NC Pattern Jury Instructions)
Read in full through the School of Government website (PDFs open in a browser; the shell and fetch tool can't reach them reliably). Read: 206.10, 206.30A, 206.40, 214.10, 214.34, 214.47, 216.05, 216.10, 216.20, 216.35, 120.20, and assault instructions 208.10, 208.14, 208.15, 208.16, 208.40, 208.55, 208.60, 208.61, 208.70, 208.72, 208.75, 208.85, 208.95H, 208.95J. Earlier summary reads: 206.15, 206.41, 206.50. Each record's `cross_checks` lists what was compared and the result.
- Manslaughter was rebuilt. The line between voluntary and involuntary is the kind of act, not whether it was "on purpose": voluntary is a deliberate act that is itself a felony-level assault or likely to cause death or serious injury, done in heat of passion or imperfect self-defense; involuntary is an unintended death from a lesser unlawful act (not a felony) or criminal negligence. Intent to kill is not required for either second-degree murder or voluntary manslaughter (206.10 footnote 21, citing State v. Ray). The bubble now offers three choices after "no malice".
- Proximate cause added as an element on all four homicide offenses.
- "No consent from the owner or tenant" was missing from every burglary and breaking-or-entering record; added.
- Definitions updated to the instructions' wording: malice, premeditation, deliberation, heat of passion, imperfect self-defense (acted in self-defense but used excessive force or was the aggressor without murderous intent), nighttime, breaking and entering, dwelling, terrorize, larceny taking (consent, knowledge, permanent deprivation), assault, deadly weapon, serious injury (great pain and suffering), strangulation, minor in the presence of an assault, pointing a gun.
- Two instructions are older than the statute and were not followed: 208.14 (sports official, says assault; G.S. 14-33(b)(9) says assault and battery) and 208.55 (attempt to inflict serious injury; current 14-33(c)(1) does not say attempt). Statute text was read in full on the ncleg.gov site for these.
- The instructions also say a jury may infer malice from an intentional killing with a deadly weapon. That is evidence guidance and was deliberately not added to the records.
- Larceny and burglary elements otherwise matched.

## Not verified yet
- Every record is `draft`. Homicide statutes (G.S. 14-17, 14-18) were read as full text. Property and assault statutes (14-32, 14-32.4, 14-33, 14-34, 14-51, 14-52, 14-54, 14-72) were read through summaries only and need a line-by-line check.
- The instructions are the judges' summary of the law, so common-law terms still deserve a check against NC appellate cases before anything is marked verified. Not yet cross-checked: 206.00, the other 206-series variants, 214.30/214.32, 208.25, the remaining statutes word for word.
- `text_snapshot` fields are empty for every statute.

## Not built yet
- Change checker: compare live ncleg.gov pages to stored snapshots, flag changes for human approval, then update the data. Plan: data in a GitHub repo, scheduled script, proposed change reviewed by the owner. Scheduled runs are not available from the chat on the free plan.
- Crimes against society category (planned, empty).
- Other assault statutes in Chapter 14 (domestic, firearm, protected-victim offenses) not yet classified.
- Multi-state support and the "closest equivalent in another state" idea (future).

## Decisions made
- Name: Elements. Tagline: "How North Carolina's crimes are built."
- Public explainer, not a charging or conviction tool. The proof standard (probable cause or beyond a reasonable doubt) does not change what the elements are, so the tool stays at the definition layer and says so.
- Plain-language text is stored in each record and reviewed, never generated live.
- Free source for checking elements: NC Pattern Jury Instructions, sog.unc.edu (criminal series list: .../north-carolina-pattern-jury-instructions-criminal-cases). The $200 SOG guidebook is not being bought. Instructions summarize the law; statute and cases win if they differ.
- Decided Oct 17: run a labeled public beta (family, friends, maybe coworkers) while records are still drafts, with the beta banner and scope safeguards. The owner decided the project does not interfere with his job and needs nothing from his employer.
- Open license chosen (MIT code, CC BY 4.0 data) so others may reuse it for the public good. Credit and the draft notice travel with the data.
- Publishing venue (personal vs. official) is undecided.

## Suggested next steps
1. Read the remaining statutes word for word (the ncleg.gov site works in the browser) and verify one family line by line, then set `review.status` to `verified`. Capture `text_snapshot` for each statute while there; that seeds the change checker.
2. Build the change checker.
3. Add more families, then more states.
