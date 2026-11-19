# Rubric Survey — Inputs for OQ-03 (Rubric Anchors)

Surveyed 2026-10-28 to inform the 1-to-5 behavioral anchors for the six fixed SDD categories
(RC-17). This is research input, not the final rubric. MVP scenarios remain counseling and clinical
psychology only (SDD §2.3); other disciplines are surveyed for anchor ideas, not for new scenario
libraries.

## Decisions (project owner, 2026-10-28)

- **Hybrid anchors:** the grader scores against observable behaviors per level (EQUIP style), and
  students see developmental level labels.
- **Free instruments only:** EQUIP/ENACT, FIS, CTS-R, Bogo OSCE, CSWE EPAS, SIRI-2. Ivey
  microskills and MI principles are cited as concepts. CCS-R and the MITI manual are **not** used,
  and no item text is reproduced from any instrument.
- **No faculty review:** this supersedes SDD OQ-03 and the crisis faculty review in RISK-03. A
  labeled synthetic calibration set and labeled safeguard tests are the release gate (Plan §1.3 PA-10).
- **Timing:** drafting the anchor spec is an early Issue in the grading phase.

## Instruments surveyed

| Instrument | Field | Scale | What it rates | Fit for CaseStudy Tech | Use terms |
|---|---|---|---|---|---|
| [Counselor Competencies Scale–Revised (CCS-R)](https://eagle.northwestu.edu/academics/college-of-social-behavioral-sciences/files/2025/12/Appendix-F-Counselor-Competencies-Scale-–-Revised.pdf), Lambie et al. | Counselor education | 5 levels: Harmful · Below · Near · Meets · Exceeds expectations | 12 counseling-skill items + 11 professional-disposition items | Closest match to our 1–5 scale and to *active listening*, *questioning*, *professionalism*. Level 1 = "Harmful" parallels our crisis safety override. | Copyrighted; contact the author (UCF) before reproducing item text |
| [ENACT](https://www.gov.uk/research-for-development-outputs/therapist-competence-in-global-mental-health-development-of-the-enhancing-assessment-of-common-therapeutic-factors-enact-rating-scale), Kohrt et al. 2015, and [WHO EQUIP](https://pmc.ncbi.nlm.nih.gov/articles/PMC9305729) competency tools | Global mental health, common factors | 4 competency levels, each defined by observable behaviors ("attributes"); level 1 flags harmful behavior | Common therapeutic factors, rated from **standardized role plays** | Strongest fit for *how* to write anchors: each level is a list of observable behaviors, which a grader can tie to transcript turns (RC-18). Built for role-play assessment. | Free via the EQUIP platform |
| [Facilitative Interpersonal Skills (FIS)](https://www.psykologtidsskriftet.no/asset/article/2021/03/En-norsk-pilotstudie-av-ferdighetstesten-fasiliterende-interpersonlige-ferdigheter/En-norsk-pilotstudie-av-ferdighetstesten-fasiliterende-interpersonlige-ferdigheter.pdf), Anderson et al. | Psychotherapy research | 1 = skill deficit … 5 = optimal presence | 8 dimensions incl. empathy, warmth, hope, alliance-bond, rupture-repair, rated on responses to **simulated difficult-client clips** | Good anchor source for *empathic engagement* and the resistant-client scenario; it predicts therapy outcome. | Research instrument; cite, don't copy |
| [MITI 4.2.1](https://www.MotivationalInterviewing.org/sites/default/files/miti4_2.pdf), Moyers et al. | Motivational interviewing | Global scores 1–5, default 3 | Cultivating change talk, softening sustain talk, partnership, empathy | *Scenario-specific competence* for the resistant client and part of *collaboration/autonomy*. SDD RC-18 forbids labeling output as an official MITI score. | Manual marked draft — do not cite without permission |
| [Cognitive Therapy Scale–Revised (CTS-R)](https://psychosisresearch.com/wp-content/uploads/2022/01/CTS-R.pdf), Blackburn et al. 2001 | Clinical psychology (CBT) | 0–6 (0 absent/inappropriate, 3 competent, 6 expert) | 12 items; items 1–5 general interpersonal (agenda, feedback, collaboration, pacing) | Anchor ideas for *session structure*; CBT-specific items are out of scope. Raters adjust for client difficulty, which is useful for the resistant scenario. | Manual freely hosted; cite |
| [OSCE adapted for social work](https://socialwork.utoronto.ca/wp-content/uploads/2018/12/OSCE-for-Social-Work.pdf), Bogo et al. | Social work | 5-point scale with descriptors per level, plus a reflection rating scale | 15-minute interview with a **standardized client** | Closest *format* match: timed simulated-client session, rated afterward. Anchor ideas for engagement and collaboration. | Published by CSWE Press (2014); cite |
| [CSWE 2022 EPAS](https://www.siue.edu/artsandsciences/socialwork/about/2022-EPAS.Competencies.pdf) | Social work accreditation | Competency framework, not a rating scale | 9 competencies; #3 Anti-racism/DEI, #6 Engage with individuals… | Source for *cultural humility* expectations. | Public |
| [Basic Skills Evaluation Device (BSED)](https://scholarsarchive.byu.edu/facpub/2494), Nelson & Johnson 1999 | Marriage & family therapy | Supervisor rating of beginning therapists (secondary adaptations use 1–5) | Basic family-therapy skills | Weak fit: relational/systemic skills are outside our scenarios. | Cite |
| [Suicide Intervention Response Inventory (SIRI-2)](https://nsuworks.nova.edu/cps_facarticles/1355) | Crisis / suicide intervention | Rates appropriateness of helper responses vs. expert ratings | Recognizing helpful vs. harmful responses to suicidal clients | Anchor ideas for the crisis scenario's *critical safety failure* (RC-19); evidence on training effects is mixed. | Research instrument; cite |

## Mapping to the six SDD categories

| SDD category (weight) | Primary anchor sources | Secondary |
|---|---|---|
| Empathic engagement (20%) | FIS empathy/warmth; ENACT/EQUIP empathy | MITI empathy global |
| Active listening & responding (20%) | CCS-R counseling-skill items; Ivey microskills (SDD §8) | ENACT |
| Purposeful questioning & exploration (15%) | CCS-R questioning items; Ivey microskills | Bogo OSCE |
| Collaboration, autonomy & cultural humility (15%) | MITI partnership; CSWE EPAS #3 and #6 | CTS-R collaboration |
| Session structure & professionalism (10%) | CCS-R professional dispositions; CTS-R items 1–5 | Bogo OSCE |
| Scenario-specific competence (20%) | Resistant: MITI change-talk/sustain-talk globals (not labeled MITI). Crisis: SIRI-2 principles + RC-19 critical-failure list. Intake: CCS-R structure | FIS rupture-repair |

## Implications for automated grading (RISK-01)

- LLM judges tend to **inflate scores**. They are **least precise on empathy** and **miss safety issues** that
  human experts catch ([EACL 2026 benchmark](https://preview.aclanthology.org/credits/2026.eacl-long.180)).
  Automated ratings of psychotherapy process reach fair-to-excellent agreement with humans
  (ICC 0.45–0.81, [JMIR preprint](https://preprints.jmir.org/preprint/95389)).
- Anchors written as **observable behaviors per level** (EQUIP style) give the grader something
  checkable to cite. That supports RC-18 grounding and the cited-turn validation in RISK-01.
- The crisis safety override (RC-19) should not rest on the LLM's numeric judgment alone. That's an
  architecture question for `docs/ARCHITECTURE.md`.
- The calibration set in RISK-01 should include transcripts that are deliberately strong, weak and
  harmful in each category, so inflation is measurable.
