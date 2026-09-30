# External discipline profile example

This directory demonstrates a data-only extension of the bundled `quantitative_social_science` profile. Load it with `load_profile_path("examples/education_profile")`. A profile consists of `profile.json` plus generation and verification Markdown for each new or overridden module. Sibling profile directories can be inherited by id. Loading a profile executes no profile code.

The inherited base supplies shared quantitative-social-science criteria, maturity handling, severity calibration, verification rules, and editorial restraint. The files in this directory add authored education-specific criteria about assignment level, nesting, implementation, attrition, and transfer. They demonstrate how a discipline can tailor the common engine; they have not been validated for education research and do not justify claims about education-review quality.
