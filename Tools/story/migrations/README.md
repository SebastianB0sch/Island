# Story data migrations (applied history)

These one-shot scripts patched `DuelAcademyIsland/Content/Data/{Story,World,Opponents}`
during the campaign integration (E07-E33 choices, contacts, Sheppard roster/deck,
reachability fixes, school-year dates). **Their changes are already in the committed
data.** They are kept only as a record of how the data was edited.

They will not run as-is: each hardcodes the original workstation path
(`C:\dev\GX\...`), and several are not idempotent. Do not re-run them; edit the JSON
directly (or write a new, repo-relative script) and validate with
`python Tools/validate/validate_all.py`.
