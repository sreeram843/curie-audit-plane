# IEEE J-BHI Submission Requirements

**Project:** Curie Audit Plane / Clinical AI Flight Recorder  
**Target:** IEEE Journal of Biomedical and Health Informatics (J-BHI)  
**Accessed:** 2026-08-27  
**Status:** Working submission note; re-check the J-BHI author page and portal immediately before submission.

## 1. Journal fit

J-BHI publishes original research at the intersection of information and communication technologies with health, healthcare, life sciences, and biomedicine. Curie is a plausible fit if the paper is framed as a validated health-informatics method for verifiable clinical-AI provenance, rather than as a general software product description. This fit assessment is an inference from the journal scope.

- [J-BHI on IEEE Xplore](https://ieeexplore.ieee.org/xpl/aboutJournal.jsp?punumber=6221020)
- [J-BHI official EMBS site](https://www.embs.org/jbhi/)
- [J-BHI Information for Authors](https://ieeexplore.ieee.org/document/10422889)

## 2. Recommended article type and length

For Curie, prepare a **Regular Paper**. The current IEEE 2026 publication-charge table lists J-BHI as a hybrid journal and gives the following page allowances before overlength charges:

| Type | Allowance |
|---|---:|
| Regular | 8 pages |
| Brief | 10 pages |
| Letter | 2 pages |
| Review | 10 pages |

The same table lists a $2,800 open-access fee, $250/$350 overlength charges, and a $1,275 repository licensing fee. These are financial terms, not a substitute for the J-BHI author instructions; confirm the applicable amount and page calculation in the submission portal.

- [2026 IEEE Publications APC List](https://magazines.ieeeauthorcenter.ieee.org/wp-content/uploads/sites/10/IEEE-Article-Processing-Charges-List.pdf)
- [IEEE guidance on page length and charges](https://journals.ieeeauthorcenter.ieee.org/your-role-in-article-production/about-potential-article-processing-charges/)

Use the J-BHI/IEEE template selected through the official template tool. Keep the manuscript in the journal template from the beginning, with figures and tables placed and cited consistently.

- [IEEE Article Templates](https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/authoring-tools-and-templates/tools-for-ieee-authors/ieee-article-templates/)
- [IEEE Template Selector](https://template-selector.ieee.org/)

## 3. Manuscript structure

Use the standard IEEE research structure, adapted to the J-BHI template:

1. Title, authors, affiliations, and ORCID iDs
2. Abstract and keywords
3. Introduction and research question
4. Related work and contribution
5. Methods/system architecture
6. Experimental design and evaluation protocol
7. Results
8. Discussion, limitations, and clinical-safety implications
9. Conclusion
10. References and acknowledgments

IEEE’s general guidance recommends a single-paragraph abstract of no more than 250 words, without citations, footnotes, or equations, followed by 3–5 keywords. Confirm the current J-BHI-specific abstract and article-type instructions in the portal.

- [IEEE Structure Your Article](https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/create-the-text-of-your-article/structure-your-article/)

## 4. What the Curie paper must demonstrate

The paper should make one primary claim:

> A privacy-preserving provenance plane can reconstruct and verify a complete FHIR-to-LLM clinical-AI transaction, detect tampering, and record human review without storing hidden chain-of-thought or immutable PHI.

Minimum evaluation package:

- Synthetic FHIR transaction fixtures and a clearly documented data-generation process.
- Baseline comparison against ordinary application logs and a simpler hash-chain design.
- Repeated transactions covering normal completion, guardrail warning/block, tool use, human ACCEPT/MODIFY/REJECT, replay, and injected tampering.
- Metrics defined before analysis: Audit Reconstruction Completeness, tamper-detection rate, false-positive/false-negative verification rate, replay agreement, audit overhead, latency, storage overhead, and access-control test results.
- Ablations showing the contribution of input manifests, transformation references, model/prompt manifests, evidence references, signatures/Merkle verification, and human-action provenance.
- A limitations section stating that hosted-model replay may diverge and that the prototype is not a clinical decision-maker or regulatory approval.

These are research recommendations for making the work publishable, not additional IEEE portal requirements.

## 5. Ethics, privacy, and clinical data

IEEE requires articles involving human or animal subjects to state the name of the reviewing IRB/ethics committee, or explain why review was not conducted. Human-subject articles must also state that consent was obtained or explain why it was not obtained.

For the current prototype, use synthetic, non-identifiable FHIR fixtures only. Obtain an institutional determination if there is any uncertainty, and include a clear statement such as: the evaluation used synthetic data and did not involve human or animal participants or real patient records; therefore, no human-subject data were analyzed. Do not describe this as an IRB approval unless an institution actually issued one.

Do not submit PHI, secrets, access tokens, private clinical records, or undisclosed customer data in the manuscript, repository, screenshots, logs, supplementary files, or public demo.

- [IEEE Submission and Peer Review Policies](https://journals.ieeeauthorcenter.ieee.org/become-an-ieee-journal-author/publishing-ethics/guidelines-and-policies/submission-and-peer-review-policies/)

## 6. Originality, authorship, and AI-use disclosure

- Submit original work to one publication at a time.
- Disclose any related conference paper, preprint, thesis, or prior submission and explain precisely what is new.
- Cite and obtain permission for reused text, figures, tables, or other copyrighted material.
- IEEE authorship requires a significant intellectual contribution, participation in drafting/revising for intellectual content, and approval of the final version. Agree on author order before submission.
- All authors need ORCID records for IEEE journal publishing workflows.
- IEEE checks articles for plagiarism and treats plagiarism, fabrication, falsification, and misleading data presentation as serious misconduct.
- If generative AI produces text, figures, images, or code in the article, disclose the AI system and the affected sections/level of use in the acknowledgments. AI used only for grammar/editing generally does not require disclosure, but IEEE recommends disclosure; references should not be passed to an editing system without careful checking.

- [IEEE Author Ethics Guidelines](https://journals.ieeeauthorcenter.ieee.org/wp-content/uploads/IEEE-Author-Ethics-Guidelines.pdf)
- [IEEE Submission and Peer Review Policies: AI, originality, and human-subject rules](https://journals.ieeeauthorcenter.ieee.org/become-an-ieee-journal-author/publishing-ethics/guidelines-and-policies/submission-and-peer-review-policies/)
- [IEEE Author Center checklist](https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/authoring-tools-and-templates/checklist-for-creating-your-article/)

For this project, distinguish between **AI used by the system under study** and **AI used to create article content**. The paper must document the former in the methods and disclose the latter under the IEEE AI policy.

## 7. Data, code, and supplementary material

IEEE strongly encourages sharing research processes, methods, data, code, and findings as openly as possible. Curie should provide, subject to license and security review:

- A versioned source-code release.
- Synthetic FHIR fixtures and schemas.
- Reproducible environment and run instructions.
- Experiment configuration and result-generation scripts.
- Hash-chain, signature, tamper-injection, and replay test cases.
- A data/code availability statement with repository DOI or stable URL when available.

Do not publish real patient data or credentials. If any data cannot be shared, state why and provide synthetic substitutes, schemas, aggregate results, and an executable evaluation path. Supplementary files may include code, datasets, README instructions, graphical abstracts, or video, and should be uploaded separately when used.

- [IEEE Research Reproducibility](https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/research-reproducibility/)
- [IEEE Tools for Authors: ORCID and data/code sharing](https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/authoring-tools-and-templates/tools-for-ieee-authors/)
- [IEEE Supplementary Materials](https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/prepare-supplementary-materials/)

## 8. Submission workflow

1. Confirm the current J-BHI aims/scope, article type, page rules, and special-issue status.
2. Prepare the manuscript in the J-BHI IEEE template.
3. Confirm author list, order, affiliations, funding, conflicts, ORCIDs, ethics/data statement, AI disclosure, and code/data availability statement.
4. Validate references, LaTeX/source files, PDF rendering, figures, captions, and accessibility.
5. Prepare the manuscript, any required cover-letter text, and separate supplementary files requested by the portal.
6. Submit through the [IEEE Publishing Portal](https://publishingportal.ieee.org/), following the J-BHI-specific instructions and submission-system prompts.
7. Keep the manuscript confidential during peer review and do not send unpublished review materials to public AI systems.
8. Track revisions and respond to reviewers with a point-by-point response; preserve a clear record of changes.

- [IEEE Submission Checklist](https://journals.ieeeauthorcenter.ieee.org/submit-your-article-for-peer-review/checklist-for-submitting-your-article-for-peer-review/)
- [IEEE Article Submission Process](https://journals.ieeeauthorcenter.ieee.org/submit-your-article-for-peer-review/the-ieee-article-submission-process/)
- [IEEE Publishing Portal](https://journals.ieeeauthorcenter.ieee.org/submit-your-article-for-peer-review/ieee-publishing-portal/)

## 9. Curie pre-submission gate

Do not submit until the repository can produce a blinded, reproducible evidence package showing:

- The same synthetic FHIR input can be replayed or checked with the in-repository verifier after records are reloaded.
- Every event hash is recomputed and tamper tests fail closed.
- Sankey/timeline/table selections resolve to authoritative event IDs.
- Protected content access is role-controlled and itself audited.
- Recorded model, prompt, retrieval, tool, and decoding configuration is available for replay classification.
- Exact status labels and exports match the documented event model.
- No secrets or PHI appear in source, fixtures, generated artifacts, screenshots, or manuscript files.

### Source-of-truth note

IEEE and J-BHI requirements can change by article type, special issue, and submission-system migration. Before uploading, re-open the J-BHI **Information for Authors** page and the current IEEE Publishing Portal instructions; treat the portal’s displayed checklist and fee schedule as authoritative for the specific submission.
