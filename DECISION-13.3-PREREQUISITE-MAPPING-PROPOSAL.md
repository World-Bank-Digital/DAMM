# Decision 13.3 — prerequisite-to-use-case mapping proposal

**Status: PROPOSED / UNRATIFIED.** This is the closing artifact requested for decision
13.3. It is a decision proposal, not a change to the model. No engine, workbook,
assessment, generated report, or historical review-package file has been changed.

**Baseline inspected:** repository `HEAD` `6429a8e`, with the uncommitted Issue 1 work
left untouched. Country impacts use `gauntlet/loop-1/EGY_v17.json` and
`gauntlet/loop-1/NGA_v17.json`, the documented verified oracles. The newer
`EGY_202608260342_clean_v17.json` is shown only as a non-authoritative sensitivity check.

## Decision proposed

Adopt an explicit 12-prerequisite × 6-use-case edge graph with three kinds of positive
edge and an explicit no-edge value:

- **G — unconditional gate.** The prerequisite is part of the national-scale readiness
  floor for that use-case column.
- **C — conditional gate.** It becomes a gate only when the candidate intervention has
  the named design property. A generic country-level column cannot silently assume that
  property.
- **R — delivery-risk overlay.** It may raise a delivery warning but must never change
  `Ready / Partial / Blocked / Unverified`.
- **— — no prerequisite edge.** The row may still be a bearing enabler in the use-case
  mean; “not a gate” does not mean “irrelevant.”

The decisive change from the carried model is to represent 7.12 as **six conditional
edges**, not four unconditional column edges. Every DAMM use-case can be implemented in
a way that uses personal or farm-level data, and every one also has at least one variant
for which that fact cannot be inferred from the six-letter column code alone. The working
13.4 ruling is therefore encoded literally as a predicate — `uses personal or farm-level
data` — rather than approximated by a hard-coded subset of columns.

Two narrow conditional edges make existing model intent explicit without turning a
subtype into a blanket block: 3.3 conditions targeted/beneficiary-linked ADV, and 4.5
conditions FIN that shares agricultural data across organizations. The current hard
3.3→FIN/AGI and 4.5→AGI edges remain in the proposal because the model treats those
columns as national-scale, integrated capabilities rather than proof that one isolated
service can exist.

This proposal should remain unratified until decision 13.5 resolves the construct of
7.12. Egypt and Nigeria currently score opposite rungs on the same central fact — a
general cross-sector regime exists, while no agriculture-specific instrument exists.
That definition, not evidence retrieval, determines whether Egypt's 7.12 is `Absent` or
`Present` and therefore determines the largest 13.3 consequence.

## Evidence-backed facts and design judgments

To keep the decision record honest, claims below are classified explicitly.

### Repository facts

1. The model declares six use cases: ADV advisory & extension; SMF smart farming; MKT
   market linkage & pricing; SCM supply chain; FIN financial services; and AGI
   agricultural intelligence.
2. The specification declares twelve prerequisite rows: three universal (2.1, 2.9,
   4.1), seven use-case prerequisites (3.3, 3.11, 4.5, 4.7, 5.5, 6.14, 7.12), and two
   delivery-risk flags (4.9, 5.7).
3. The carried static mapping is: all three universal rows→all six; 3.3→FIN/AGI;
   3.11→AGI; 4.5→AGI; 4.7→FIN; 5.5→ADV; 6.14→FIN; and
   7.12→ADV/SMF/FIN/AGI. Delivery rows block nothing.
4. The 7.12 four-column set is explicitly marked as a proposal in the model, engine,
   workbook builder, commit `a57fcae`, and `THREAD-4-HANDOFF.md`. It is not ratified.
5. The indicator census says 3.3 bears on FIN/AGI/ADV and calls it a prerequisite for
   “targeted credit/subsidy/advisory,” while its carried gate string names only FIN/AGI.
   It says 4.5 bears on AGI/FIN while its carried gate string names only AGI. Bearing
   tags and gating edges are therefore already distinct concepts.
6. The current machine form is a free-form indicator string — `UNIVERSAL`,
   `UC:<comma-list>`, or `DELIVERY`. It cannot encode an applicability predicate, a
   rationale, or an explicit no-edge.
7. The mapping is duplicated. The engine/model carry the prerequisite strings, while
   `build_workbook_v17.py` separately carries `PREREQ_SCOPE` and `UC_SPECIFIC`. The
   workbook Config prose also contains a stale sentence saying 7.12 “binds the
   agricultural-intelligence column” beside a value naming four columns.
8. The engine and workbook apply this precedence to active gates:
   `Blocked > Unverified > Partial > Ready`. A known absent gate outranks an unknown
   one. Level 2 (`Present (narrow)`) caps a use-case-specific column at `Partial`, even
   though that per-use-case narrow rule is not stated in the exported `binding_rules`
   prose.
9. Mapping changes do not change indicator levels, pillar or layer means, use-case role
   means, evidence counts, or prerequisite presence statuses. They change the readiness
   category, the named reason, blocker-derived strategic questions, roadmap sequencing,
   Practice Library joins, and the DAR evidence binding that follows prerequisite edges.
10. Eight prerequisite definitions remain open under 13.5: 2.1, 3.3, 3.11, 4.7, 4.9,
    5.7, 6.14, and 7.12. Decision 13.6 concerns A1 thresholds; after 13.12 separated
    need from readiness, those thresholds do not alter any prerequisite edge or
    readiness status.

### Design judgments in this proposal

1. A hard edge means a required floor for a **national-scale portfolio**, not a claim
   that no pilot or workaround can exist.
2. The three existing universal classifications are retained. Their breadth is a prior
   model judgment, not a conclusion tested by the Egypt/Nigeria runs.
3. The existing hard edges other than 7.12 are retained unless the census itself names
   a narrower subtype. This minimizes change while making the graph reviewable.
4. A use-case tag is not automatically a gate. A row may affect a readiness mean without
   having enough necessity to block the whole column.
5. Conditional edges require an intervention profile. When that profile is absent, the
   base country-level status is computed from unconditional gates and the unresolved
   condition is reported separately; it is neither silently activated nor silently
   discarded.
6. 7.12 follows all six use cases conditionally because data use is an intervention
   property, not a stable property of a broad use-case label.

## Exact edge matrix

| Prerequisite | ADV | SMF | MKT | SCM | FIN | AGI |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **2.1 Rural mobile broadband** | G | G | G | G | G | G |
| **2.9 Rural electricity** | G | G | G | G | G | G |
| **3.3 National farmer registry** | C¹ | — | — | — | G | G |
| **3.11 Agricultural-data interoperability** | — | — | — | — | — | G |
| **4.1 Data-protection/privacy law** | G | G | G | G | G | G |
| **4.5 Agricultural-data governance** | — | — | — | — | C² | G |
| **4.7 Digital-ID coverage** | — | — | — | — | G | — |
| **4.9 Inter-ministerial coordination** | R³ | R³ | R³ | R³ | R³ | R³ |
| **5.5 Digital-extension capability** | G | — | — | — | — | — |
| **5.7 MoAg digital/AI unit** | R⁴ | R⁴ | R⁴ | R⁴ | R⁴ | R⁴ |
| **6.14 Agri-fintech rails** | — | — | — | — | G | — |
| **7.12 Consent and data rights** | C⁵ | C⁵ | C⁵ | C⁵ | C⁵ | C⁵ |

Conditions:

1. `targeted_farmer_level_delivery == true` — the intervention selects, authenticates,
   targets, or tracks named farmers/holdings.
2. `cross_organization_agricultural_data_sharing == true` — the finance intervention
   combines or transfers agricultural data across institutions, for example for
   alternative credit scoring or insurance.
3. `cross_ministerial_delivery == true` — otherwise 4.9 remains a package-level risk
   reading only.
4. `moag_led_or_owned == true` — otherwise 5.7 remains a package-level institutional
   reading only.
5. `uses_personal_data == true OR uses_farm_level_data == true`. Under the current
   indicator name, 13.5 must also decide whether `ai_enabled == true` is required. The
   working 13.4 wording does not require it; the name “Responsible-AI safeguards” does.

## Complete 72-cell edge register and rationale

“Repository basis” identifies what is carried in the current artifacts. “Proposal
rationale” is the judgment offered for ratification.

### 2.1 — Rural mobile broadband coverage (3G/4G)

| Use case | Edge | Repository basis | Proposal rationale |
|---|---|---|---|
| ADV | G | Census/spec: `UNIVERSAL`, `ALL`. | National-scale digital advisory needs a rural communications path for delivery and feedback. Offline and 2G/USSD variants expose the unresolved 2.1 definition but do not justify a one-off exception in the column rule. |
| SMF | G | Census/spec: `UNIVERSAL`, `ALL`. | Connected sensors, devices, and remote support need rural connectivity at portfolio scale. Local/offline automation is an edge case, not the national readiness floor represented here. |
| MKT | G | Census/spec: `UNIVERSAL`, `ALL`. | Digital price discovery, buyer matching, and transactions need rural users to reach the service. |
| SCM | G | Census/spec: `UNIVERSAL`, `ALL`. | Digital coordination and traceability need field-to-chain data exchange. A back-office-only tool is not the full supply-chain use case. |
| FIN | G | Census/spec: `UNIVERSAL`, `ALL`. | Digital onboarding, transactions, servicing, and claims require a rural communications channel. |
| AGI | G | Census/spec: `UNIVERSAL`, `ALL`. | A national intelligence capability needs data ingestion and dissemination beyond a disconnected central model. |

### 2.9 — Rural electricity access

| Use case | Edge | Repository basis | Proposal rationale |
|---|---|---|---|
| ADV | G | Census/spec: `UNIVERSAL`, `ALL`. | User devices, extension devices, and network equipment need reliable charging/power at scale. |
| SMF | G | Census/spec: `UNIVERSAL`, `ALL`. | Sensors, controllers, gateways, and farmer devices depend on power. Solar workarounds can be part of delivery design but do not erase the national foundation constraint. |
| MKT | G | Census/spec: `UNIVERSAL`, `ALL`. | Market access through digital devices and platforms requires power across rural users and market nodes. |
| SCM | G | Census/spec: `UNIVERSAL`, `ALL`. | Collection points, traceability devices, cold-chain monitoring, and logistics systems need power. |
| FIN | G | Census/spec: `UNIVERSAL`, `ALL`. | Devices, agents, payment endpoints, and connectivity infrastructure need power. |
| AGI | G | Census/spec: `UNIVERSAL`, `ALL`. | Data collection, processing access points, and dissemination devices need power. |

### 3.3 — National farmer registry

| Use case | Edge | Repository basis | Proposal rationale |
|---|---|---|---|
| ADV | C¹ | Census bearing tag includes ADV and rationale says “targeted … advisory”; current gate omits ADV. | A registry is required when advisory selects or personalizes for named farmers/holdings. Broadcast, open web, call-center, radio, and untargeted USSD advisory can operate without a national registry, so this must not be an unconditional ADV block. |
| SMF | — | No current bearing or gate tag. | A farm can adopt sensors, machinery, or precision tools using a local account or device identity; a national farmer registry is not a categorical prerequisite. |
| MKT | — | No current bearing or gate tag. | A marketplace can onboard sellers directly. A registry may improve verification or targeting but is not necessary for the whole MKT column. |
| SCM | — | No current bearing or gate tag. | Supply-chain actors can use commercial, cooperative, plot, or consignment identifiers without a national farmer register. |
| FIN | G | Current `UC:FIN,AGI`; census says targeted credit/subsidy. | The DAMM FIN column is read as national-scale agricultural finance/benefit delivery, for which a stable farmer/holding key supports eligibility, targeting, deduplication, and linkage. Generic retail finance is outside that narrower gate rationale. |
| AGI | G | Current `UC:FIN,AGI`; use-case tag AGI. | Integrated farmer/holding intelligence at national scale needs a stable entity key to join observations and act on results. Aggregate or remote-sensing-only analytics are the main edge case. |

### 3.11 — Agricultural-data interoperability standards

| Use case | Edge | Repository basis | Proposal rationale |
|---|---|---|---|
| ADV | — | Current gate only AGI; `ALL` is a bearing tag. | One advisory channel can use a bounded dataset and interface. Interoperability improves the portfolio and remains in its bearing mean, but absence need not block all advisory. |
| SMF | — | Current gate only AGI. | Individual smart-farming products can operate with proprietary/local schemas. Lock-in is a risk, not proof that the category is impossible. |
| MKT | — | Current gate only AGI. | A market platform can operate on its own data model; cross-platform exchange is beneficial rather than universally necessary. |
| SCM | — | Current gate only AGI. | Particular traceability or logistics schemes can define their own standards. A future SCM-specific standard may be warranted, but the repository records no such gate decision. |
| FIN | — | Current gate only AGI. | Finance can use established financial APIs and bilateral agricultural-data interfaces; an agriculture-wide interoperability standard is not a categorical FIN prerequisite. |
| AGI | G | Current `UC:AGI`; census calls it a data-exchange prerequisite for integrated/AGI uses. | The column denotes integrated agricultural intelligence across datasets and institutions; interoperability is a necessary ecosystem rail at that scale. |

### 4.1 — Data-protection/privacy law

| Use case | Edge | Repository basis | Proposal rationale |
|---|---|---|---|
| ADV | G | Census/spec: `UNIVERSAL`, `ALL`. | Advisory portfolios commonly collect contact, location, crop, and feedback data; a national legal floor is retained even though anonymous broadcast variants exist. |
| SMF | G | Census/spec: `UNIVERSAL`, `ALL`. | Farm telemetry can identify holdings and people; a legal basis, rights, and accountability floor is required. |
| MKT | G | Census/spec: `UNIVERSAL`, `ALL`. | Market platforms process seller/buyer identities, listings, and transactions. |
| SCM | G | Census/spec: `UNIVERSAL`, `ALL`. | Traceability and logistics data can identify farms, workers, and commercial actors. |
| FIN | G | Census/spec: `UNIVERSAL`, `ALL`. | Financial services necessarily process identity and sensitive transaction/credit data. |
| AGI | G | Census/spec: `UNIVERSAL`, `ALL`. | Intelligence systems can combine data at scale; the general legal floor applies independently of the more specific 4.5 and 7.12 safeguards. |

### 4.5 — Agricultural-data governance framework

| Use case | Edge | Repository basis | Proposal rationale |
|---|---|---|---|
| ADV | — | Current gate only AGI; no ADV bearing tag. | A provider can govern its own advisory data under the general 4.1 regime. Sector-wide sharing rules are valuable but not categorically necessary for every ADV model. |
| SMF | — | Current gate only AGI; no SMF bearing tag. | A farm/provider relationship can operate under contract and the general privacy law without a national agricultural-data framework. |
| MKT | — | Current gate only AGI; no MKT bearing tag. | Platform and commercial rules can govern a standalone market service; the repository provides no basis for a blanket block. |
| SCM | — | Current gate only AGI; no SCM bearing tag. | Contractual/sector traceability rules can support a bounded chain. Agriculture-wide governance is an enabler, not yet a demonstrated universal SCM gate. |
| FIN | C² | Indicator use-case tags include FIN, but the carried gate omits it. | Activate when a finance/insurance design shares agricultural data across institutions or uses it for scoring. Ordinary finance relying only on identity and financial data remains governed by 4.1/4.7/6.14. |
| AGI | G | Current `UC:AGI`; indicator use-case tag AGI. | Integrated agricultural intelligence needs rules for ownership, access, sharing, stewardship, and reuse across the sector. |

### 4.7 — Digital-ID coverage

| Use case | Edge | Repository basis | Proposal rationale |
|---|---|---|---|
| ADV | — | Current gate only FIN; `ALL` is a bearing tag. | Anonymous or phone-number-based advisory can operate without foundational digital ID. Authenticated entitlement delivery is covered by the conditional 3.3 edge. |
| SMF | — | Current gate only FIN. | Equipment/device and farm accounts can use provider-issued identities; national digital ID is not necessary for the whole category. |
| MKT | — | Current gate only FIN. | Platforms can perform their own onboarding. Regulated payments inside the platform are evaluated under FIN rather than making ID a blanket MKT gate. |
| SCM | — | Current gate only FIN. | Supply chains can identify firms, consignments, plots, or cooperatives without population-wide digital ID. |
| FIN | G | Current `UC:FIN`; census rationale: DPI rail for KYC/targeting. | Scaled digital agricultural finance requires legally usable identity coverage for onboarding, KYC, targeting, and redress. The unresolved 13.5 question is whether the recorded ID series actually measures digital ID. |
| AGI | — | Current gate only FIN. | Aggregate/open-data intelligence can operate without identifying individuals. Farmer-linked AGI instead activates 3.3 and 7.12. |

### 4.9 — Inter-ministerial coordination mechanism

| Use case | Edge | Repository basis | Proposal rationale |
|---|---|---|---|
| ADV | R³ | `DELIVERY`, `ALL`; census says every cross-ministry initiative is at risk. | Flag when advisory spans agriculture, telecom, meteorology, local government, or other ministries; never change readiness status. |
| SMF | R³ | `DELIVERY`, `ALL`. | Flag cross-ministry spectrum, standards, subsidy, research, or extension delivery dependencies; never gate private adoption. |
| MKT | R³ | `DELIVERY`, `ALL`. | Flag public programs spanning agriculture, trade, commerce, and digital ministries; standalone market platforms are not blocked. |
| SCM | R³ | `DELIVERY`, `ALL`. | Flag multi-agency traceability, customs, standards, food-safety, and logistics programs; no categorical block. |
| FIN | R³ | `DELIVERY`, `ALL`. | Flag programs spanning agriculture, finance, identity, payments, and social-protection authorities; no readiness mutation. |
| AGI | R³ | `DELIVERY`, `ALL`. | Flag data programs requiring multiple ministries and agencies to share mandates/data; no readiness mutation. |

### 5.5 — Digital-extension capability

| Use case | Edge | Repository basis | Proposal rationale |
|---|---|---|---|
| ADV | G | Current `UC:ADV`; census says ADV prerequisite. | At national scale, advisory needs an operating digital-extension delivery capability, including programs, trained staff/partners, and reach. |
| SMF | — | No current SMF bearing or gate tag. | Smart-farming tools can be delivered by vendors, cooperatives, or service providers without a national extension capability. Extension remains a possible adoption channel. |
| MKT | — | No current MKT bearing or gate tag. | Market platforms do not inherently require the extension system to operate. |
| SCM | — | No current SCM bearing or gate tag. | Supply-chain digitization can be led by buyers, aggregators, logistics providers, or regulators. |
| FIN | — | No current FIN bearing or gate tag. | Financial providers and agents can deliver services without a digital-extension institution, though extension may support uptake. |
| AGI | — | No current AGI bearing or gate tag. | Intelligence systems can be built and used by government/research/industry without extension; dissemination to farmers is an ADV dependency. |

### 5.7 — MoAg digital/AI unit

| Use case | Edge | Repository basis | Proposal rationale |
|---|---|---|---|
| ADV | R⁴ | `DELIVERY`, `ALL`; census calls it a public-delivery prerequisite. | Flag ministry-led ownership, procurement, standards, or scaling risk; private/non-ministry delivery is not blocked. |
| SMF | R⁴ | `DELIVERY`, `ALL`. | Flag when the ministry owns adoption programs, subsidies, or coordination; private adoption remains possible. |
| MKT | R⁴ | `DELIVERY`, `ALL`. | Flag ministry-owned marketplaces or public market-information systems; commercial platforms are not blocked. |
| SCM | R⁴ | `DELIVERY`, `ALL`. | Flag ministry-owned traceability/logistics programs and institutional continuity risk; no categorical gate. |
| FIN | R⁴ | `DELIVERY`, `ALL`. | Flag ministry-owned subsidy/credit/insurance programs; financial-sector delivery remains possible without the unit. |
| AGI | R⁴ | `DELIVERY`, `ALL`. | Flag ministry ownership, model/data stewardship, and sustained operational capacity; other institutions can still operate intelligence services. |

### 6.14 — Agri-fintech rails for smallholders

| Use case | Edge | Repository basis | Proposal rationale |
|---|---|---|---|
| ADV | — | Current gate/use-case tag only FIN. | Payments may be bundled with advisory, but advisory itself can operate without financial rails. |
| SMF | — | Current gate/use-case tag only FIN. | Equipment finance is one adoption model; smart-farming technology can be purchased or provided through other arrangements. |
| MKT | — | Current gate/use-case tag only FIN. | Market linkage and price information can operate without embedded payments, although payments improve a transactional platform. |
| SCM | — | Current gate/use-case tag only FIN. | Supply-chain coordination can operate without smallholder fintech rails; embedded finance is an optional combined use case. |
| FIN | G | Current `UC:FIN`; census says FIN prerequisite. | A financial-services column for smallholders requires accessible payment/finance rails, not merely a policy or pilot. |
| AGI | — | Current gate/use-case tag only FIN. | Intelligence/analytics does not inherently require a payment rail. |

### 7.12 — Consent and data-rights safeguards

| Use case | Edge | Repository basis | Proposal rationale |
|---|---|---|---|
| ADV | C⁵ | Current proposal hard-binds ADV; 13.4 says follow personal/farm-level data. | Activate for personalized, profiled, feedback-rich, geolocated, or AI-mediated advisory. Do not block anonymous/broadcast advisory solely from the ADV code. |
| SMF | C⁵ | Current proposal hard-binds SMF. | Activate where telemetry, field boundaries, production records, imagery, or device data are attributable to a farm/person. A purely local device with no external data processing is the edge case. |
| MKT | C⁵ | Current proposal omits MKT. | Activate for account-based matching, listings tied to farms, transaction histories, reputation, profiling, or AI pricing. Anonymous public price information is the counterexample, so the edge is conditional rather than absent or unconditional. |
| SCM | C⁵ | Current proposal omits SCM. | Activate for farm-level traceability, supplier profiles, worker data, or AI risk/quality decisions. Aggregate logistics without farm/person linkage is the counterexample. |
| FIN | C⁵ | Current proposal hard-binds FIN. | Most finance will activate the condition because identity, transactions, credit, and farm records are processed; the predicate makes the reason explicit and supports rare non-personal analytic variants. |
| AGI | C⁵ | Current proposal hard-binds AGI; original mapping was AGI-only. | Activate when analytics/AI uses farm-level or personal records. Public, aggregate, or sufficiently anonymized satellite/climate analytics shows why AGI alone is not a reliable proxy for data scope. |

## Country impact against the verified oracles

### What cannot change

The proposal changes no level and no arithmetic. These exact readiness means remain:

| Country | ADV | SMF | MKT | SCM | FIN | AGI |
|---|---:|---:|---:|---:|---:|---:|
| Egypt | 3.30 | 3.21 | 3.35 | 3.33 | 3.25 | 3.26 |
| Nigeria | 2.71 | 2.68 | 2.64 | 2.61 | 2.50 | 2.57 |

Pillar means/bands, layer means, the leapfrog gap, evidence counts, rated/held
denominators, and the twelve prerequisite statuses also remain unchanged.

### Base matrix after applying unconditional gates only

Conditional constraints are displayed beside the base status and become active when an
intervention profile is supplied.

| Country/use case | Current carried output | Proposed base output | Exact reason for change |
|---|---|---|---|
| Egypt ADV | Blocked — 7.12 | **Unverified — 2.1** | 7.12 moves from unconditional to conditional; rural coverage remains unverified. |
| Egypt SMF | Blocked — 7.12 | **Unverified — 2.1** | Same. |
| Egypt MKT | Unverified — 2.1 | **Unverified — 2.1** | No base-status change; 7.12 is now shown as a conditional constraint when data is used. |
| Egypt SCM | Unverified — 2.1 | **Unverified — 2.1** | Same. |
| Egypt FIN | Blocked — 7.12 | **Unverified — 2.1** | 3.3, 4.7, and 6.14 are Present; 7.12 becomes conditional. |
| Egypt AGI | Blocked — 3.11, 4.5, 7.12 | **Blocked — 3.11, 4.5** | The hard blockers remain; 7.12 becomes a conditional additional blocker. |
| Nigeria ADV | Partial — universal 2.9 | **Partial — universal 2.9** | No category change; 3.3 may additionally cap targeted ADV, but is already narrow and the universal cap already applies. |
| Nigeria SMF | Partial — universal 2.9 | **Partial — universal 2.9** | No change; 7.12 is Present. |
| Nigeria MKT | Partial — universal 2.9 | **Partial — universal 2.9** | No change; 7.12 is Present. |
| Nigeria SCM | Partial — universal 2.9 | **Partial — universal 2.9** | No change; 7.12 is Present. |
| Nigeria FIN | Partial — 3.3 | **Partial — 3.3** | The existing hard 3.3 edge is retained; 7.12 is Present. |
| Nigeria AGI | Blocked — 3.11, 4.5 | **Blocked — 3.11, 4.5** | No change; 7.12 is Present. |

Summary:

| Country | Current summary | Proposed base summary | Delta |
|---|---|---|---|
| Egypt | 4 Blocked · 2 Unverified | **1 Blocked · 5 Unverified** | Three columns move Blocked→Unverified. |
| Nigeria | 1 Blocked · 5 Partial | **1 Blocked · 5 Partial** | No category change. |

### Conditional activation effects

| Condition | Egypt effect | Nigeria effect |
|---|---|---|
| 3.3 targeted farmer-level ADV | None: 3.3 is Present. | 3.3 is Present (narrow), so targeted ADV is capped at Partial; the base column is already Partial on 2.9. |
| 4.5 cross-organization agricultural-data FIN | FIN becomes Blocked (4.5 is Absent); if 7.12 also activates, both blockers are named. | FIN becomes Blocked (4.5 is Absent), changing its base Partial status for that intervention profile. |
| 7.12 personal/farm-level data, any selected use case | Every selected column becomes Blocked because 7.12 is Absent. AGI was already Blocked on 3.11/4.5; the other five can each change when the condition is true. | No category change because 7.12 is Present. |
| 4.9 cross-ministerial delivery | No active risk: 4.9 is Present. | Delivery-risk warning on every selected cross-ministerial use case: 4.9 is Absent. |
| 5.7 MoAg-led/owned delivery | Verification warning: 5.7 is Unverified. | Delivery-risk warning on every selected MoAg-led use case: 5.7 is Absent. |

### 7.12 definition × mapping sensitivity

Egypt's current 7.12 is `Absent`; Nigeria's is `Present`. Egypt records a general regime
but no agriculture-specific safeguards and treats that as Absent. Nigeria records the
same central distinction and treats the general regime as sufficient for Present. This
is the unresolved 13.5 construct question.

| 7.12 treatment | Egypt matrix if 7.12 remains Absent | Egypt matrix if 7.12 becomes Present | Nigeria |
|---|---|---|---|
| Original AGI-only hard edge | 1 B · 5 U (AGI already blocked on 3.11/4.5) | 1 B · 5 U | 1 B · 5 P |
| Current four hard edges (ADV/SMF/FIN/AGI) | 4 B · 2 U | 1 B · 5 U | 1 B · 5 P |
| All six hard edges | 6 B · 0 U | 1 B · 5 U | 1 B · 5 P |
| **Proposed six conditional edges; no intervention profile** | **1 B · 5 U, plus six disclosed conditions** | **1 B · 5 U** | **1 B · 5 P** |
| Proposed, condition activated for a selected column | That selected column is B; AGI already B | No change from base | No change from base |

This shows why 13.3 and 13.5 must be frozen together. Mapping alone can swing five
Egyptian columns, but the swing disappears if the definition reclassifies 7.12 as
Present.

### Non-authoritative clean-Egypt sensitivity

`EGY_202608260342_clean_v17.json` already reports 1 Blocked (AGI) and 5 Unverified under
the carried mapping because its 7.12 is Present rather than Absent. The proposed base
mapping leaves that summary unchanged. FIN remains Unverified on the universal 2.1 and,
independently, on 3.3, 4.7, and 6.14 in that run. This is a sensitivity check only and
does not replace the verified Egypt oracle.

## Recommended machine-readable form

Replace the overloaded `indicators[].prerequisite` string as the source of edge behavior
with a first-class, versioned mapping object. Keep an indicator-level boolean/role only
to identify the twelve rows; put all behavior on edges.

```json
{
  "prerequisite_mapping": {
    "decision_id": "13.3",
    "revision": 1,
    "status": "proposed",
    "ratified": false,
    "use_case_ids": ["ADV", "SMF", "MKT", "SCM", "FIN", "AGI"],
    "prerequisite_ids": [
      "2.1", "2.9", "3.3", "3.11", "4.1", "4.5",
      "4.7", "4.9", "5.5", "5.7", "6.14", "7.12"
    ],
    "status_precedence": ["Blocked", "Unverified", "Partial", "Ready"],
    "conditional_policy": {
      "missing_profile": "report_condition_without_mutating_base_status",
      "true": "activate_edge",
      "false": "ignore_edge"
    },
    "edges": [
      {
        "prerequisite_id": "2.1",
        "use_case_id": "ADV",
        "effect": "gate",
        "applicability": {"mode": "always"},
        "on_prerequisite_status": {
          "Absent": "Blocked",
          "Unverified": "Unverified",
          "Present (narrow)": "Partial",
          "Present": "no_change"
        },
        "rationale": "National-scale digital advisory needs a rural communications path.",
        "basis": ["specification.7", "indicator_census.2.1"],
        "decision_status": "proposed"
      },
      {
        "prerequisite_id": "7.12",
        "use_case_id": "MKT",
        "effect": "gate",
        "applicability": {
          "mode": "conditional",
          "predicate": {
            "any": [
              {"field": "uses_personal_data", "equals": true},
              {"field": "uses_farm_level_data", "equals": true}
            ]
          }
        },
        "on_prerequisite_status": {
          "Absent": "Blocked",
          "Unverified": "Unverified",
          "Present (narrow)": "Partial",
          "Present": "no_change"
        },
        "rationale": "Transactional or profiled MKT uses data rights safeguards; anonymous price information does not.",
        "basis": ["decision.13.4", "decision.13.3.judgment"],
        "decision_status": "proposed"
      },
      {
        "prerequisite_id": "5.7",
        "use_case_id": "AGI",
        "effect": "delivery_risk",
        "applicability": {
          "mode": "conditional",
          "predicate": {"field": "moag_led_or_owned", "equals": true}
        },
        "on_prerequisite_status": {
          "Absent": "flag",
          "Unverified": "verify",
          "Present (narrow)": "flag_narrow",
          "Present": "no_change"
        },
        "rationale": "A missing ministry unit raises ownership and continuity risk but never blocks the AGI column.",
        "basis": ["specification.7", "indicator_census.5.7"],
        "decision_status": "proposed"
      },
      {
        "prerequisite_id": "6.14",
        "use_case_id": "SCM",
        "effect": "none",
        "applicability": {"mode": "never"},
        "rationale": "Embedded finance is optional; supply-chain digitization can operate without smallholder fintech rails.",
        "basis": ["indicator_census.6.14", "decision.13.3.judgment"],
        "decision_status": "proposed"
      }
    ]
  }
}
```

The production artifact must contain all 72 edge objects, including `effect: "none"`.
The examples above show the four allowed shapes; the complete register in this document
defines the content.

### Required schema invariants

1. Exactly 72 edges: the Cartesian product of the 12 prerequisite IDs and 6 use-case
   IDs; no duplicate pair and no omitted pair.
2. `effect` is closed to `gate | delivery_risk | none`.
3. `gate` edges have `applicability.mode` `always` or `conditional`; conditional edges
   must carry a valid predicate over a closed intervention-profile vocabulary.
4. `delivery_risk` may create warnings only. A test must prove it cannot mutate matrix
   status.
5. `none` must use `applicability.mode: never` and carry a rationale. Explicit no-edges
   prevent accidental behavior from absence or substring matching.
6. Every gate declares all four prerequisite-status outcomes. In particular,
   per-use-case `Present (narrow) → Partial` becomes model data rather than an engine-only
   rule.
7. Every edge carries `basis`, `rationale`, and `decision_status`; no consumer may render
   a proposed edge as ratified.
8. Country outputs pin `model version + model revision + prerequisite-mapping revision`.
9. A matrix cell exposes `active_gates`, `conditional_constraints`, `delivery_risks`,
   and `status_reason`, rather than only an opaque `why` string.
10. Status selection is structural and order-independent: aggregate active edge outcomes
    by declared precedence, then apply the enabler-mean rule at `Partial` severity.

## Implementation consequences after ratification

This proposal does not authorize implementation. Once ratified, the change should land
at the model root and be generated outward:

1. Add the mapping object and schema to the canonical model; bump model revision and
   mapping revision.
2. Make `engine_v17.py` and `reference_scorer.py` read edges instead of parsing
   `UC:<comma-list>` strings.
3. Generate workbook prerequisite scopes and formulas from the same edge list; remove
   the handwritten `PREREQ_SCOPE`, `UC_SPECIFIC`, and stale Config prose.
4. Update the renderer to show conditional constraints and delivery risks separately
   from active blockers.
5. Update `generate_dar.py` evidence-permission expansion to traverse mapping edges,
   including conditional edges, rather than infer use cases from a prerequisite string.
6. Extend Practice Library entries/intervention candidates with the four profile facts
   used by predicates. Its existing intervention-specific “prerequisite pattern” is the
   natural place to resolve those conditions.
7. Export app fixtures from the model and add parity tests for exact edge sets, edge
   effects, conditional activation, status precedence, and the 72-cell completeness
   invariant.
8. Regenerate Egypt and Nigeria only after 13.3 and the dependent 13.5 definitions are
   frozen. Generated outputs are never hand-edited.

## Ratification questions that remain

1. **7.12 construct:** Is it a general personal/farm-data rights safeguard, as the 13.4
   wording implies, or an AI-specific safeguard, as its name implies? If AI-specific,
   condition 5 becomes `(ai_enabled) AND (personal OR farm-level data)`.
2. **Use-case grain:** Confirm that the readiness columns represent national-scale
   portfolios. If they represent the existence of any service, several current hard
   edges — especially 3.3→FIN/AGI and 3.11/4.5→AGI — should also become conditional.
3. **3.3 ADV edge:** Confirm the census's “targeted advisory” reading and the proposed
   trigger rather than promoting 3.3 to an unconditional ADV block.
4. **4.5 FIN edge:** Confirm that cross-organization agricultural-data use in finance is
   the boundary between ordinary FIN and governance-dependent FIN.
5. **2.1 construct:** Resolve whether 2G/USSD and offline-capable services pass an
   indicator named 3G/4G. This is a 13.5 definition question, not a reason to hide the
   universal edge.
6. **Delivery flags:** Confirm that 4.9/5.7 are attached per intervention only when their
   predicates apply, while remaining visible as package-level institutional findings.

Subject to those confirmations, the edge graph above is complete, deterministic, and
machine-executable without pretending that a six-letter use-case code reveals the data
architecture of a future service.
