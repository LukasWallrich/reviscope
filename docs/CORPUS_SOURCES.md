# Open-review corpus sources

Public reviewer reports and an exact manuscript version are separate eligibility
requirements. A journal can publish excellent peer-review files while exposing
only the version of record. Such a case is useful for product testing, but it is
not eligible for comparing an AI review with the human reports until the
manuscript reviewed in that round is found and verified.

| Source | Public review record | Exact reviewed submission | Current use |
|---|---|---|---|
| **PeerJ** | Its review histories contain decisions, individual reports, rebuttals, and revision-specific manuscript links. The history states that its text and materials are CC BY. | Available per round when the linked submission file can be retrieved. Our Nettle et al. case has the original Version 0.1 PDF and all four Version 0.1 reports. | Best current mainstream matched empirical case. |
| **Nature Human Behaviour** | [Transparent review](https://www.nature.com/articles/s41562-019-0799-8) has been available on an opt-in basis for research manuscripts submitted since December 2019; published records contain reviewer comments, decisions, and author responses. | A published peer-review bundle does not by itself establish access to the corresponding submitted manuscript. Check each article and any dated preprint separately. | Strong discovery source; case-by-case version matching remains necessary. |
| **Nature Communications** | [Peer-review files](https://www.nature.com/ncomms/submit/tpr-faq) contain reviewer comments and rebuttals. They became standard for primary research submitted from November 2022; earlier participation was optional. | The standard bundle documents the exchange but does not necessarily include the manuscript version reviewed in each round. | Broad discovery source; include only after matching a public submission or preprint. |
| **Communications Psychology** | The journal's [submission guidance](https://www.nature.com/commspsychol/submit/submission-guidelines) says decision letters, reviewer comments, and author rebuttals are published as a supplementary peer-review file. | In the cases inspected so far, the bundle labels review rounds but has not supplied the corresponding pre-review manuscript. A dated public preprint may solve this for an individual article. | Excellent target population; current Barry case is product-test only because only the version of record is verified. |
| **Royal Society Open Science** | The Royal Society says [publication of review information is mandatory](https://royalsociety.org/journals/ethics-policies/editorial-standards/) and makes reports, decisions, and responses available; reports are [CC BY](https://royalsociety.org/journals/open-access/open-science/). | The public record may be alongside the article without preserving every submitted manuscript file. Verify the actual assets for each candidate. | Promising broad source, especially its psychology and cognitive-neuroscience section. |
| **Collabra: Psychology** | An official [UC Press policy announcement](https://www.ucpress.edu/blog-posts/52861-whats-new-with-collabra-psychology-a-qa-with-editor-in-chief-simine-vazire) states that, from the 2020 change, reviews and decisions accompany all published papers. Authors may share rejected reviews and letters, but the journal does not provide a systematic rejected-paper archive. | The policy does not promise the precise manuscript read by reviewers. A preprint is only a proxy unless explicitly tied to the reviewed round or matched to a known submission. | Strong psychology-specific discovery source; exact manuscript matching remains the gate. |
| **Meta-Psychology** | The journal describes a [fully transparent OSF editorial workflow](https://open.lnu.se/index.php/metapsychology/about), including reviews and decisions. | Its OSF folders often distinguish the initial manuscript, reviews, responses, and revised manuscript explicitly. | Two exact pairs are already verified, including the empirical Sætrevik–Sjåstad fallback; the journal is valuable but is not the sole target population. |

This inventory records what the cited policies and inspected cases expose. It
does not claim that an unlocated version is absent across a journal or even
permanently absent for a particular article.

## Current matched empirical case

Nettle, Pepper, Jobling, and Schroeder (2014), *Being there: a brief visit to a
neighbourhood induces the social attitudes of that neighbourhood*, is the
current seven-review ranking case. The [PeerJ review
history](https://peerj.com/articles/236/reviews/) identifies Version 0.1 as the
original submission received on 4 October 2013 and associates four reports
with that version. The recovered PDF identifies itself as a “Reviewing
Manuscript” and carries PeerJ's matching `4 Oct 2013` version footer. Source
URLs, local cache paths, hashes, and licensing evidence are recorded in
[`empirical_pilot.v1.json`](../eval/corpus/empirical_pilot.v1.json).

Human reports remain held out until AI generation finishes. Ranking must use
all four reports as separate candidates. Reviewer names, source headers, model
names, and pipeline metadata must not be shown to the ranking judge.

For the format-controlled sensitivity analysis, every review is converted to
the same atomic inventory schema and audited against its source. Normalization
must preserve positive assessments as well as criticisms, including short
approving sections such as “This is all fine” or “They do not raise any
particular worries.” Dropping those statements would systematically make brief
human reviews look harsher and less informative than they were. The original
prose ranking remains useful as a format-sensitive analysis, not as evidence
that presentation differences have been eliminated.
