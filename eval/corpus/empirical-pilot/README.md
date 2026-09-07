# Empirical social-psychology pilot cache

The tracked manifest at `eval/corpus/empirical_pilot.v1.json` records source
URLs, version evidence, hashes, and licensing qualifications. Downloaded source
files live in the ignored `eval/corpus/cache/empirical-pilot/` tree.

Files under `human-reviews/` are held-out evaluation references. Never pass
that directory or its contents to `coarse-socpsy review`; generation receives
only the file under `manuscript/`.

The Sætrevik–Sjåstad pair is a completed empirical report with two experiments,
rather than a methods article or registered-report proposal. Its two raw
round-1 reports can be combined as the human comparator only after candidate
reviews have completed.
