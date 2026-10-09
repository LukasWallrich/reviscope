"""Shared substantive reasoning guidance; no scoring or additional review stage."""

ARGUMENT_ASSESSMENT = """For consequential claims you inspect, connect the located claim to
its premises and evidence, the inferential step, necessary assumptions, qualifications
and strongest defeating context. Support may occur before or after the claim, across
sections or supplied supplements; sentence order and linguistic similarity do not
establish support. Distinguish a missing premise, a false premise, circular support,
and evidence compatible with several explanations. Identify the particular connection
that fails and its consequence, rather than merely labelling the argument weak.
A predicted contrast can be estimable without identifying a mechanism. Record successful
and unresolved assessments in operation records where the schema provides them; do not create a finding
or a quota of claims just to populate a reasoning record.
"""

LITERATURE_ASSESSMENT = """For literature-based claims consequential to the question or
contribution, identify the manuscript claim, target prior works, comparison criterion
and asserted relation: limitation, comparison, use, extension, conflicting predictions
or theoretical synthesis, or support when prior work supplies a substantive premise.
Leave an unidentifiable relation unspecified. Resolve targets from the surrounding argument and supplied
sources only when unambiguous; leave unspecified targets or criteria explicit rather
than inventing them. Establish what the fetched source evidence supports before judging
the relation. For 'prior studies cannot distinguish X from Y', specify what would
distinguish them and check the target studies' designs. A singly cited accurate summary
is acceptable; multiple citations do not establish a correct comparison or synthesis.
Search before asserting or denying novelty or missing literature. Inconclusive search
does not prove absence; inaccessible essential sources leave the relation unresolved.
Retain exact fetched quotations, URL/DOI and what they establish in external_evidence
for any resulting finding, under the existing verification rules.
"""

MATERIAL_ASSESSMENT = """Check examples or materials selectively, only when their absence
prevents assessing a specific inference: for example, a coding rule's application,
a stimulus-dependent construct interpretation, or a claimed failure pattern. Aggregate
estimates can suffice for quantitative conclusions; an illustrative case alone does not
establish prevalence or a mechanism. Check supplied supplements and accessible materials
before reporting a gap. Distinguish material unavailable to the reviewer from material
not retained or inspected by authors; the former never establishes the latter. Preserve
privacy-based withholding and request the smallest necessary clarification or a feasible
privacy-preserving alternative. A caption or extracted figure text is not inspectable
image evidence: do not invent visual contents. Questions about visual patterns, arrows
or readability require actual image inspection; otherwise leave those steps unresolved.
Extracted table values may support a numerical comparison without visual inspection.
"""

REASONING_ASSESSMENT = ARGUMENT_ASSESSMENT + LITERATURE_ASSESSMENT + MATERIAL_ASSESSMENT
