# Synthea provenance

This repository does not contain Synthea patient dumps. Evaluation may slice
external Synthea FHIR Bundles that appear under an **approved root** listed in
`fixtures/synthea/approved-manifest.json`.

## Source and license

- Generator: [Synthea](https://github.com/synthetichealth/synthea)
- Patient identifier system required on `Patient.identifier.system`:
  `https://github.com/synthetichealth/synthea`
- Typical output license: Creative Commons Attribution 4.0 (CC-BY 4.0), as
  stated by the Synthea project. Confirm the license of any local dump before
  publication.
- Primary citation: J. Walonoski *et al.*, “Synthea: An approach, method, and
  software mechanism for generating synthetic patients and the synthetic
  electronic health care record,” *J. Amer. Med. Inform. Assoc.*, vol. 25,
  no. 3, pp. 230–238, 2018, doi: 10.1093/jamia/ocx079.

## Local acquisition

The prototype looks only at roots in the approved manifest, resolved relative
to the repository root. The default root is the sibling checkout:

`curie-prediction-pipeline/data/synthea/fhir`

Environment variables `CURIE_SYNTHEA_BUNDLE` and `CURIE_SYNTHEA_DIR` are
ignored unless the resolved path is inside an approved root. Bundles must
still carry the Synthea identifier system.

## Generator parameters

This repository does **not** pin a Synthea generator version, population seed,
module set, or CLI invocation (`pinned: false` in the approved manifest).
Optional slice arms are protocol demonstrations when dumps exist under an
approved root. Treat generator version, seed, modules, and CLI as
**NOT_MEASURED** until an operator records them in the manifest. Fixture hashes
for sliced encounters appear in scenario `notes` as a 12-character SHA-256
prefix of the **source file bytes**.

## Paper claim

Synthea arms are a protocol demonstration on external synthetic patients when
those files are present. They do not convert the cloned one-fixture cohort
into a clinical population sample. Generator version is **NOT_PINNED**.
