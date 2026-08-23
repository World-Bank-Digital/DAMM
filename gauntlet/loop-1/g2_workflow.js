export const meta = {
  name: 'gauntlet-loop1-g2',
  description: 'G2 peer review: adversarial verification of prerequisites, Judged rows, gaps, and a Documented sample for Egypt + Nigeria',
  phases: [
    { title: 'Verify', detail: '3 reviewers per country: prerequisites, evidence sample, gap refutation' },
  ],
}

const BASE = '/Users/randeepsudan/pCloud Drive/02 World Bank/Projects/DAR/DAMM'
const L1 = BASE + '/gauntlet/loop-1'
const PROTO = BASE + '/DAMM-v1.6-Source-Tier-Protocol.md'
const QCP = BASE + '/DAMM-v1.6-QC-Protocol.md'

const V_SCHEMA = {
  type: 'object',
  required: ['findings'],
  properties: {
    findings: { type: 'array', items: {
      type: 'object',
      required: ['id', 'verdict', 'reason'],
      properties: {
        id: { type: 'string' },
        verdict: { type: 'string', enum: ['confirmed', 'refuted', 'adjust'] },
        reason: { type: 'string' },
        proposed_value: {},
        proposed_level: { type: ['integer', 'null'] },
        proposed_tier: { type: 'string' },
        evidence_url: { type: 'string' },
        severity: { type: 'string', enum: ['high', 'medium', 'low'] },
      } } },
    protocol_issues: { type: 'string' },
  },
}

const COMMON = `You are a G2 peer reviewer under the DAMM QC Protocol (read "${QCP}" and "${PROTO}" first). You are NOT the assessor — your job is to REFUTE, not to confirm. Default to skepticism. For each row you review: does the source URL resolve and actually say what the value claims? Is the evidence class correctly derived from the value (number->Measured, citation-with-artefact->Documented, no artefact->Judged, gap->Gap)? Is the tier right per the protocol lookup? For ladder rows, does the cited evidence actually establish the claimed presence rung, and does quality/scale evidence justify any level above 3? Verdicts: "confirmed" (survives your attack), "refuted" (wrong — give the reason and, if you found better evidence, proposed_value/evidence_url), "adjust" (right substance, wrong tier/class/level/vintage — give the proposal). Severity: high = would change a prerequisite status, matrix cell, or pillar band; medium = changes a level or tier; low = cosmetic/provenance polish. Load WebSearch/WebFetch via ToolSearch. Return findings for EVERY row you were assigned, including confirmed ones.`

phase('Verify')
const jobs = []
for (const iso of ['EGY', 'NGA']) {
  const inp = `${L1}/${iso}_v17_input.json`
  jobs.push(() => agent(`${COMMON}

Country: ${iso}. Read "${inp}". Review EVERY row whose id is one of the 12 prerequisites: 2.1, 2.9, 4.1, 3.3, 3.11, 4.5, 4.7, 5.5, 6.14, 7.12, 4.9, 5.7. These rows carry blocking power — they get 100% adversarial review. Independently re-verify each one's factual basis with your own searches, not just the cited link.`,
    { label: `${iso}:G2-prerequisites`, phase: 'Verify', schema: V_SCHEMA }))

  jobs.push(() => agent(`${COMMON}

Country: ${iso}. Read "${inp}". Review: (a) EVERY row with cls "Judged"; (b) a deterministic sample of Documented/Measured rows — for each pillar prefix (1,2,3,4,5,6,7,8), the two lowest-numbered non-prerequisite rows that are Documented or Measured (skip prerequisite ids 2.1,2.9,4.1,3.3,3.11,4.5,4.7,5.5,6.14,7.12,4.9,5.7 — another reviewer has them). State in your first finding's reason field which ids your sample resolved to.`,
    { label: `${iso}:G2-evidence-sample`, phase: 'Verify', schema: V_SCHEMA }))

  jobs.push(() => agent(`${COMMON}

Country: ${iso}. Read "${inp}". You are the GAP REFUTER: for EVERY row with cls "Gap", try hard to FIND the data the assessor could not — different search phrasings, national statistical office publications, sector surveys, IO databases, recent releases. A gap you cannot fill after a genuine tier-ordered attempt gets verdict "confirmed" (the gap is legitimate — say what you tried). A gap you CAN fill gets "refuted" with proposed_value, evidence_url, year, and tier (T1-T4 only; T5 does not fill a gap).`,
    { label: `${iso}:G2-gap-refuter`, phase: 'Verify', schema: V_SCHEMA }))
}
const results = await parallel(jobs)
const flat = results.filter(Boolean)
log(`G2 complete: ${flat.length}/6 reviewers returned`)
return { reviewers: flat.length, results: flat.map((r, i) => ({ i, n: r.findings.length, refuted: r.findings.filter(f => f.verdict === 'refuted').length, adjust: r.findings.filter(f => f.verdict === 'adjust').length })) , full: flat }
