# Elements: where things stand (as of Oct 17, 2026)

Elements is an interactive explainer of North Carolina criminal offenses, built from each offense's legal elements. The page (`index.html`, formerly `elements.html`) reads everything from the data file (`elements-nc.json`). Keep both in one folder. Open through a local server (`python3 -m http.server`) for automatic loading, or use the "Choose file" button.

## Where the files live
- Source of truth: the folder `Documents\Elements` on the owner's computer (version controlled in Positron) and the public GitHub repository bjsykes254/Elements. Copies in the Claude Writing project are older snapshots.
- GitHub Pages is on: public beta at https://bjsykes254.github.io/Elements/ (live Oct 17). Pushing to main republishes in a minute or two.
- Licenses: MIT for code (LICENSE); CC BY 4.0 for the data (LICENSE-DATA.md). The data file's meta carries a draft/reuse notice.

## Verified so far (Oct 17, third pass)
- Homicide statutes G.S. 14-17, 14-18 and 14-23.2 read as full text on ncleg.gov; text saved in each record's `text_snapshot` with a SHA-256 fingerprint checked against the live page. Records corrected (see each record's `comparison_note`). Status is still draft until the owner signs off.
- Manslaughter has no statutory definition (14-18 sets punishment only), so its elements rest on case law and the pattern jury instructions, not statute text.

## Burglary and breaking or entering (Oct 17, fourth pass)
- G.S. 14-51, 14-52 and 14-54 read as full text; snapshots saved with SHA-256 fingerprints matching the live pages.
- Important finding: S.L. 2025-71, s. 10 (effective Dec 1, 2025, offenses on or after that date) rewrote G.S. 14-51. The statute no longer says burglary is 'as defined at the common law' and no longer mentions nighttime or the curtilage reach for second-degree. The tool now models the current text: nighttime element and flow question removed; the home must be 'of another'. The pattern jury instruction 214.10 is dated 2011 and predates the change, so it can't be fully relied on for burglary.
- The tool models current law only. Offenses before Dec 1, 2025 fall under the earlier text. Whether to show both versions is a design question for later.
- Not modeled: G.S. 14-53 (breaking out of a dwelling), 14-54(b1) business-area entry, and other breaking or entering statutes.

## Larceny (Oct 17, fifth pass)
- G.S. 14-72 read as full text; snapshot saved with a matching SHA-256 fingerprint. The felony-circumstance list was incomplete and is now the full statutory list (State Archives records added; 'several' prior convictions is four). Mail enhancement (14-72(c1)) and other larceny-type offenses are noted but not modeled.
- Decision (Oct 17): the tool shows only the current version of each statute. Historical language is not stored for now. Pages say current law applies to offenses on or after the effective date shown in each record's special rules.

## How to move a record from draft to verified
A record is verified when the owner has read the current statute text next to the record and found them consistent. Steps:
1. In Positron, open elements-nc.json and find the record by its "id". Read review.comparison_note.
2. Open the statute link (statutes[].url) on ncleg.gov. Check that the history line at the bottom of the section ends with the session law in last_session_law_seen. If a newer one appears, stop and re-read the section before verifying.
3. Compare, side by side: class, punishment_note, every element's plain text (elements are listed in the same file), and special_rules.
4. Read explain_like_5 and the element wording as a non-lawyer would. Nothing should add meaning the statute lacks.
5. For elements marked case_law or mixed, open the linked pattern jury instruction under cross_checks and confirm the note. Verified means the record matches the statute and those sources; it is not a legal opinion.
6. Edit the review block: "status": "verified", "verified_by": "Blake Sykes", "verified_on": "YYYY-MM-DD". Keep the quotes and commas exactly as they are.
7. Save, run the page locally (python -m http.server), open the record in Find, and confirm the Draft warning is replaced by a 'Checked against the statute text' line.
8. Commit with a message like 'Verify first-degree murder' and Sync Changes.
9. When every record is verified, change the beta banner text in index.html.
Re-verify a family whenever a legislative session changes the statutes it cites. The saved text_sha256 will let the change checker spot a changed section.

## Change checker and automation (Oct 17, sixth pass)
What exists:
- `tools/check_statutes.py check` reads every statute page the data cites, compares it with the saved `text_snapshot` (ignoring spacing), and reports changed, repealed or missing sections, new or removed sections in the four watched articles (6, 8, 14, 16), and newer versions of the pattern jury instructions the records cite. It never edits wording and never marks anything verified.
- `tools/check_statutes.py accept 14-52` is the approval step. After you have read a change and edited the affected records, it saves the new text, updates last_session_law_seen, and sets any verified record that cites the section to needs_review (with a note in review.history). Then you verify it again.
- `tools/validate_data.py` checks the data file (unknown elements, broken flows, hash mismatches, verified records missing a name, date or saved text).
- `.github/workflows/validate.yml` runs the validator, the tests and a JavaScript syntax check on every push. `.github/workflows/check-statutes.yml` runs the checker every Monday and on demand, opens or updates an Issue, and marks the run failed so GitHub emails you.
- The page shows a separate warning for needs_review records.

One-time setup for the owner:
1. Run `py tools/check_statutes.py baseline` once on your computer (it saves the section lists of the four watched articles into the data file). Commit and sync.
2. On GitHub, open the Actions tab, choose "Check statutes", and press Run workflow. Read the result. This first run is the real test of reaching ncleg.gov and the School of Government list from GitHub's servers. They could not be tested from here, so expect to adjust.
3. Make sure Issues are on for the repository (Settings, General, Features).

When the checker reports a change:
1. Open the Issue and the linked statute. Read what changed.
2. Edit the affected records in elements-nc.json so they match the new text.
3. Run `py tools/check_statutes.py accept 14-52` (use the section number), then `py tools/validate_data.py`.
4. Verify the records again using the steps above, commit, and sync. Close the Issue.

Limits to remember:
- The checker compares text only. It can't tell you what a change means for a record; that is your reading.
- GitHub turns off scheduled workflows in a repository with no activity for 60 days. Any commit turns them back on.
- If the checker says a page could not be read, the check is incomplete. Silence from the Monday run is only good news if the run itself shows as passed.
- Historical statute language is not stored (decision Oct 17). Only the current text is kept.

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
1. Owner reviews the homicide comparison notes and, if satisfied, sets review.status to verified for the four homicide records. Then read the remaining statutes word for word (the ncleg.gov site works in the browser) and verify one family line by line, then set `review.status` to `verified`. Capture `text_snapshot` for each statute while there; that seeds the change checker.
2. Change checker built (see above). Next: first Actions run, then more families.
3. Add more families, then more states.
