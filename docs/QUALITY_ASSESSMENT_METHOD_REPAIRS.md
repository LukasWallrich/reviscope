# Assessment-method repairs found during the training run

Read-only subscription-backed Opus reviews of the implementation and assessment harness
found a numeric quotation bug and provenance/reporting issues. Reviews and responses are
retained under `docs/pipeline-integration-review/`. These are model code reviews, not
human scientific adjudication.

## Engineering changes

* Exact quotes ending in a number now anchor before sentence/list punctuation. Decimal,
  grouping, sign, exponent and superscript truncations remain rejected. This changes
  evidence anchoring, not the inferential or external-source support requirements.
  Existing pipeline caches retain raw discovery/verifier responses; deterministic
  anchoring is applied again, and changed upstream evidence changes subsequent keys.
* The eval-only criticism assessor shares identical complete presentations across
  nested arms once, retains every origin, and records same-ID presentations whose
  evidence differs. It distinguishes inherited/new audit findings and holistic findings
  not published by the audit editorial pass, including merges and their reasons.
  An excluded audit arm is not described as an editorial loss.
* Packets are retained as immutable hash-addressed snapshots. Each assessment binds its
  own full origin map, packet hash, source hashes, raw-call artifact and matcher identity.
  Schema failures and author-visible unresolved exclusions are recorded per arm.
* Raw judge calls are cached on their full input, schema, backend and protocol. Quote
  bookkeeping can be rederived without new sampling; `--offline` refuses a missing raw
  cache instead of silently making a model call. Raw labels remain separate from checked
  labels. Failed quote checks remain explicit even for a raw unresolved judgment.
* Whole-report comparisons require the visual/genre restraint prompt and use a distinct
  `comparisons-v4/` directory. Changed/invalid conditions are archived. Reuse records
  preserve earlier prompt provenance. The frozen v3 runner cannot overwrite v4.
* Startup guards reject the original generation matcher or an old comparison prompt.
  Both new assessment drivers and the selected arithmetic script enter code snapshots.

No human reports, primary-source follow-up, control expectations or judge feedback were
inserted into generation or its caches. Neither remedy/severity rules nor publication
and source-dependency gates were loosened.

## Historical and repaired conditions

Generation remains frozen at `f7aab38`; it contains the numeric-boundary bug. Original
v1 criticism judgments and v3 preferences remain intact. Offline rederivation restores
14 Bonetto Opus labels and one Sol label that failed only quote bookkeeping. These are
restored model opinions, not newly confirmed scientific criticisms. At the first impact
check, the only candidate quotation changed by the matcher was Sætrevik's `N = 781`,
repeated in both nested arms; its finding was already published. Recheck the completed
corpus before reporting a final count. No published decision is rewritten by this check.

Fresh deduplicated v2 judgments and v4 preferences use a separate frozen assessment
snapshot, `09dd60b0a0b8a826…`. Final metadata/guard corrections are applied using retained
raw calls with the offline flag, under a separately recorded rewrap snapshot. They do
not constitute a new generation condition or a causal comparison of the repair.

The initial five control fields have easy cues. Two later mixed source probes had
mistaken expected labels because the manuscript could defeat another assertion without
settling the external source. Keep these as probe-design errors. A source-only follow-up
has no manuscript-misstatement or cross-dataset-transfer allegation; both raw judgments
abstain. It was designed after seeing the earlier outputs, so it is exploratory protocol
checking, not independent judge validation.

## Scientific limits

Pipeline items were verifier-filtered; plain items were not. Their support proportions
are not comparable quality estimates. Opus verified/reconciled pipeline text and Sol
generated both arms, creating related-output bias risks. Formats can reveal origin despite
hidden labels. Pooled calls allow cross-item influence; native items can bundle claims.
Human comparators are full prose, AI comparisons are criticism-focused, and human
comparisons use Opus only. None establishes expert correctness.

Author-visible unresolved concerns are counted but excluded from this primary condition.
Actual usefulness requires a separate assessment. One replicate, nested arms and no
compute-matched alternative prevent variance or causal-stage claims. Targeted source and
arithmetic checks were selected post hoc by the assessing agent. Expert adjudication,
a sampled atomic inventory, repeat runs, an equal-compute broad read and a separately
selected independent corpus remain necessary.
