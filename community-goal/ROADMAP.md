# What needs doing

A list of specific, claimable work. If you want to help and don't know where to
start, take something from here and say so in an issue so two people don't do it
twice.

Nothing on this list requires writing code.

---

## 1. Source the 18 claims

Every figure in the guide came from a document that names no citations. Each one
below is published with a way to verify it locally, and an empty `sources` array
waiting for someone to close the gap. Coverage is at
[`api/v1/coverage.json`](https://caffeinated1.github.io/configurationRotBot/api/v1/coverage.json).

**One claim is a complete contribution.** Use the
[source form](https://github.com/caffeinated1/configurationRotBot/issues/new?template=cg-source.yml)
— no JSON required.

| id | Claim | Where the primary document probably lives |
|---|---|---|
| `ev-subsidy-per-job` | ~$1.95M subsidy per job across 11 projects | A subsidy-tracking watchdog's project database; state economic development award records |
| `ev-siting-factor` | Only 3% of owners named incentives as the top siting factor | An industry survey — trade association or consultancy; find the published methodology |
| `ev-notice-voided` | Virginia rezoning voided for defective notice; >$1.7M spent defending | The circuit court opinion, and the county's own legal spending records |
| `ev-zoned-too-close` | Largest data center county's economic development officer says facilities were zoned too close to homes | Meeting minutes, recorded board sessions, or contemporaneous local reporting quoting the statement |
| `ev-mitigation-litigation` | Acoustic mitigation installed; litigation continued anyway | The docket in the relevant nuisance case |
| `ev-a-weighting` | A-weighting discounts 63 Hz by 26.2 dB, 31.5 Hz by 39.4 dB; sub-20 Hz may not register | **The easiest one on this list** — the A-weighting curve is in IEC 61672-1 and is reproduced in most acoustics references |
| `ev-noise-class-actions` | Proposed class actions in Wisconsin and Mississippi; one class >10,000 | PACER dockets; the complaints themselves |
| `ev-self-generation` | Dozens of turbines, >500 MW self-supplied, unpermitted | The state's air permitting records and the litigation filings |
| `ev-capacity-market` | Capacity costs in one regional market rose by billions | The RTO's capacity auction results and the state consumer advocate's analysis |
| `ev-no-cost-shift` | A study of the largest market found no historical cost shift | The study itself — check its scope before citing it |
| `ev-rate-drivers` | Federal researchers attribute rising rates partly to equipment costs and an aging grid | A national laboratory or federal agency report |
| `ev-incentive-returns` | States lose 52–70 cents per dollar on data center sales tax exemptions | Legislative auditor or revenue department return analyses — usually published per state |
| `ev-billion-dollar-states` | Four states each losing >$1B/year | Annual tax expenditure reports |
| `ev-no-incentive-proceeded` | 2 of 7 benchmark agreements gave no local incentive; both proceeded | The seven agreements themselves — all should be public records |
| `ev-no-decommissioning-security` | None of 7 agreements contained decommissioning security; ~3,600 acres, 18M sq ft | Same seven agreements. **Sourcing these unlocks four claims at once** |
| `ev-sole-remedy` | A sole-remedy clause capped a $20M protection on a ~$10B project | Same set — the specific agreement and its remedies clause |
| `ev-equipment-life` | Equipment obsolete in 4–6 years; shell lasts 30 | Operator depreciation schedules in public filings; industry refresh-cycle studies |
| `ev-construction-jobs` | 1,000+ construction workers for 2–3 years | Project labor agreements, permit applications, or economic impact studies filed with an application |

If a source turns out **not** to support the claim as written, that is the most
valuable outcome on this page. File a
[correction](https://github.com/caffeinated1/configurationRotBot/issues/new?template=cg-correction.yml).

### The seven agreements

Four claims (`ev-no-incentive-proceeded`, `ev-no-decommissioning-security`,
`ev-sole-remedy`, and parts of section 10) rest on a benchmark of seven signed
data center agreements that the source guide does not identify. Assembling a
public, cited list of signed agreements — with links to the recorded documents —
would put four claims on solid ground and give every town a set of worked
examples to negotiate against. This is the single highest-leverage project on
this page and it is mostly public-records work.

---

## 2. Jurisdiction overlays

The requirements are portable; statutes are not. See
[CONTRIBUTING.md](CONTRIBUTING.md#2-adding-a-jurisdiction-overlay).

**Worth doing first**, because the guide's own evidence already points at them
and towns there are actively facing this:

- **Virginia** — the notice case, the largest concentration of facilities, and
  the county whose own economic development officer says it zoned too close.
- **Wisconsin** and **Mississippi** — the pending noise class actions.
- **Any state that has adopted a large-load tariff.** Section 7 tells towns to
  intervene in that docket rather than replicate it locally, which is only
  actionable if someone lists the docket. One line per state is a real
  contribution.
- **Any state with a data center sales tax exemption** — pair it with the
  forgone-revenue figure from that state's own tax expenditure report.

An overlay does not have to be complete. Six good notes beat seventy
placeholders, and `status: draft` is an honest, useful state to publish in.

---

## 3. Content gaps we know about

Named here so contributors can see the edges of what exists:

- **No section on construction-phase impacts** as a standalone topic — traffic,
  dust, hours, haul routes, and the complaints that arrive before anything is
  operating. Currently scattered across sections 2 and 8.
- **Section 5 gives drafting positions, not validated thresholds.** They are
  labelled as such deliberately. An acoustical engineer willing to review them
  and say which hold up would improve the most-used section in the guide.
- **Nothing on interconnection queue mechanics** — section 2 says
  interconnection capacity is given up, but not how a town finds out what is
  queued.
- **Water reuse and reclaimed supply** get one line. Somewhere a utility has
  written a good reclaimed-water condition; it should be here.
- **No non-US framing.** Every legal concept in section 3 is US land use law.
  A parallel note for another legal system would be a substantial contribution
  and probably needs its own instrument table.

---

## 4. Accessibility and translation

- **A screen reader pass** on the site. It has been built with semantic markup,
  labelled controls, and keyboard-reachable toggles, but it has not been tested
  with an actual screen reader.
- **A plain-language edition.** The guide reads at a level suited to staff and
  counsel. The people at the hearing are not always either.
- **Translation.** Content is separate from presentation, so a translation is a
  data file rather than a fork.

---

## 5. Things deliberately not on this list

- **Telling towns what to decide.** The guide is usable by a community that
  approves a project and one that refuses. Contributions that make it usable by
  only one of those will not be merged.
- **Ranking or scoring named projects or companies.** Out of scope, per
  [GOVERNANCE.md](GOVERNANCE.md#scope).
- **Legal advice.** Overlays describe what the law is; they do not advise.
