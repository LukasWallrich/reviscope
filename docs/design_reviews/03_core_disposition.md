# Core disposition of final Fable integration review

Implemented for the alpha:

- Generated finding IDs are namespaced with module, position, and model ID; model-supplied provenance fields are reset.
- Verification decisions use a closed status enum. Unknown or duplicate IDs fail the stage; missing IDs make the run partial and remain unresolved.
- Epistemic status is separate from editorial disposition. Merge targets must exist, be non-self, be terminal, and remain inside the publication cap. Exact duplicates retain the best-grounded candidate and all alternatives remain in the audit trail.
- Codex reads the schema-constrained final message from `--output-last-message`. The strict schema transformer closes objects, requires explicit fields, and was exercised with live Luna output.
- Run metadata records the generation and verification backend, model, and effort. Fixture exports are prominently labelled as demonstrations.

The alpha keeps explicitly labelled partial artifacts because they are useful for debugging and expose coverage failures. Such artifacts are never labelled as completed reviews.
