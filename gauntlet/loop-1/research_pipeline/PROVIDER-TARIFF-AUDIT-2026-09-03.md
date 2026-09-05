# Provider Tariff and Model-Identifier Audit — 2026-09-03

**Audit target:** DAMM committed tree `92160286dcad8563c5b7d345467b2e2b4d9cfbc3`, specifically the committed versions of `prices.json` and the model-selection and metering code in `vendors.py`. Concurrent working-tree changes made after that commit are outside this tariff verdict.

**Verification date:** 2026-09-03 (Asia/Bangkok).

**Price basis:** published first-party API list prices in USD, before tax, credits, negotiated discounts, or account-specific legacy pricing.

**Method:** static source inspection plus current official provider documentation. No provider request, paid workflow, production mutation, or secret value inspection was performed. A later read-only view of the logged-in Jina account dashboard supplied the account-specific package evidence recorded in the supplement below; it did not make an API request or change account state.

> **Tariff/accounting verdict: NO-GO for a paid canary on the audited baseline.** The canonical route's main model (`claude-opus-5`) is priced correctly and its OpenAI challenger (`gpt-5.6-terra`) is conservatively priced, but the ledger understates Exa Search, cannot meter or hard-cap Jina Reader, mixes the wrong Perplexity token and request rates, and can silently apply one generic price to distinct model/context tiers. Consequently, the configured `$500` ceiling is a nominal internal-accounting ceiling, not an evidence-backed upper bound on provider charges.

### Post-baseline account evidence and remediation status

A read-only view of the logged-in official Jina dashboard on 2026-09-03 showed a current package menu of $50 for 1 billion tokens ($0.05/MTok standard) and $500 for 11 billion tokens (approximately $0.045/MTok premium). This verifies $0.05/MTok as a conservative upper menu rate for the current account. It does **not** identify which package the Render production key uses. Account balances and automatic-funding settings are intentionally omitted from this public artifact. Before a canary, operators should privately identify the production key's package and verify an explicitly authorized funding control.

The candidate remediation replaces the baseline's flat Jina charge with the conservative $0.05/MTok rate, sends separately bounded Reader content and total-cost headers, requests JSON usage, and settles `data.usage.tokens`. It also corrects the other listed tariffs, fails closed for unknown LLM models, reserves worst-case cost before paid transport, disables hidden paid retries, and durably retains unresolved headroom after an ambiguous transport outcome. Those changes require the regression and simulation evidence reported separately; they do not alter the baseline verdict above or retroactively rewrite terminal ledgers.

### 2026-09-05 Reader rejection correction

This addendum supersedes the earlier suggestion to send `X-Token-Budget` and `X-Max-Tokens` with the same value. Current official Reader material checked on 2026-09-05 distinguishes a strict total budget from an output trim: [`X-Token-Budget`](https://github.com/jina-ai/reader/blob/main/src/dto/crawler-options.ts#L320-L333) rejects a response that exceeds its budget, whereas [`X-Max-Tokens`](https://github.com/jina-ai/reader/blob/main/src/services/snapshot-formatter.ts#L724-L736) trims returned content. The Reader source applies the trim before calculating formatted-response cost, which can include text-mode description/envelope material; equal low values therefore leave no headroom and can yield `BudgetExceededError` / `40904`. See the [charge calculation](https://github.com/jina-ai/reader/blob/main/src/api/crawler.ts#L1191-L1230), [budget comparison](https://github.com/jina-ai/reader/blob/main/src/api/crawler.ts#L1603-L1650), and [error definition](https://github.com/jina-ai/reader/blob/main/src/services/errors.ts#L32-L36).

The revised route uses `C = max(500, max_chars)` for `X-Max-Tokens`, and `T = C + 4,096` for both `X-Token-Budget` and the local Jina reservation. The 4,096-token difference is a deliberately conservative policy headroom for the response envelope, not a Jina-documented maximum; the strict provider budget, not the headroom estimate, is the hard per-request spend bound. It does not assume that an explicit HTTP rejection was free: public documentation does not promise zero billing for every rejected SaaS request, and the open-source Reader repository excludes hosted billing. The local `T` reservation is therefore retained and the outcome journalled so an immediate retry cannot make the identical paid request again. The only source-local outcomes are exact known Reader tuples (`409/40904/BudgetExceededError` and `422/42203/SubmittedDataMalformedError`); credential, balance, throttle, malformed/unclassified, and service responses fail closed as terminal paid outcomes.

The candidate also propagates ambiguous, unresolved, unmetered, and over-bound paid outcomes through every canonical Stage 1–7 command using exit 78, which the coordinator classifies as non-retryable. Ordinary incomplete or locally recoverable failures retain their existing bounded retry behavior; a terminal paid outcome does not trigger an automatic second stage attempt.

## Scope and runtime route

The audit covers every numeric provider tariff in `prices.json`, all model IDs named by that file, all model IDs in `_MODEL_PREFS`, and Perplexity's helper default:

- Anthropic: `claude-opus-5`, `claude-opus-4-8`, `claude-sonnet-5`, `claude-haiku-4-5`, and `_default`.
- OpenAI: `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.6-sol`, all currently billed through one `_default` tariff.
- Gemini: `gemini-3.1-pro-preview`, `gemini-2.5-pro`, `gemini-pro-latest`, all currently billed through one `_default` tariff.
- Perplexity: `sonar-pro`, billed through `_default` plus `per_request`.
- Exa: `per_search` and `per_content_page`.
- Jina Reader: `per_fetch`.

The canonical default workflow uses Anthropic Opus 5 for primary LLM work, OpenAI Terra for the independent Stage 1 challenge, Exa for search, Jina Reader for fetched evidence, and Perplexity Sonar Pro as a discovery peer. Gemini is a configured fallback/preflight surface, rather than part of that default paid route.

## Findings at a glance

| Provider / configured key | Configured tariff | Official tariff on 2026-09-03 | Identifier status | Assessment | Confidence / uncertainty |
|---|---:|---:|---|---|---|
| Anthropic `claude-opus-5` | $5 input / $25 output per MTok | $5 / $25 | Current pinned, dateless API model ID | Exact for standard, global, non-fast inference | High. Fast mode is $10 / $50 and US-only inference adds 10%, but DAMM sets neither option. |
| Anthropic `claude-opus-4-8` | $5 / $25 | $5 / $25 | Current pinned, dateless API model ID | Exact under the same standard assumptions | High; same modifier caveat as Opus 5. |
| Anthropic `claude-sonnet-5` | $3 / $15 | **$2 / $10** | Current pinned, dateless API model ID | Stale by +50%; conservative, not exact | High. Anthropic explicitly cancelled the planned 2026-09-01 increase. |
| Anthropic `claude-haiku-4-5` | $1 / $5 | $1 / $5 | Valid convenience alias; canonical dated ID is `claude-haiku-4-5-20251001` | Numerically exact today; identifier is not pinned | High on tariff and alias behavior. |
| Anthropic `_default` | $5 / $25 | No universal default exists | Not a model ID | Unsafe as a provider-wide fallback: current Fable/Mythos and Opus fast mode are $10 / $50 | High. It is conservative only for the currently listed standard resolver candidates. |
| OpenAI `gpt-5.6-terra` via `_default` | $5 / $25 | $2 / $12 through 272K input; $4 / $18 above 272K | Current official model ID | Conservative for both context tiers, but not exact | High. This is the canonical challenger. |
| OpenAI `gpt-5.6-luna` via `_default` | $5 / $25 | $0.20 / $1.20 through 272K; $0.40 / $1.80 above 272K | Current official model ID | Materially conservative, not exact | High. |
| OpenAI `gpt-5.6-sol` via `_default` | $5 / $25 | $4 / $20 through 272K; **$8 / $30 above 272K** | Current official model ID | Conservative at short context; **understates both rates at long context** | High. Sol's $4 / $20 price is promotional through at least 2026-11-21. |
| Gemini `gemini-3.1-pro-preview` via `_default` | $5 / $25 | $2 / $12 at <=200K prompt; $4 / $18 above 200K | Current preview ID; no shutdown date announced | Conservative, not exact | High on today's tariff; medium on preview longevity. |
| Gemini `gemini-2.5-pro` via `_default` | $5 / $25 | $1.25 / $10 at <=200K; $2.50 / $15 above 200K | Current stable ID; no shutdown date announced | Conservative, not exact | High. |
| Gemini `gemini-pro-latest` via `_default` | $5 / $25 | **Cannot be assigned deterministically** | Still documented as an accepted alias, but its current target is unclear | Not production-safe as a deterministic fallback | High on uncertainty: Google's last explicit mapping (2026-01-21) points to `gemini-3-pro-preview`, which shut down 2026-03-09; no later official re-point notice was found. |
| Perplexity `sonar-pro` via `_default` | $5 / $25 + $0.005/request | **$3 / $15 + $0.006/request** at default low search context | Current official model ID | Mixed: tokens are overstated; request fee is understated | High. DAMM supplies neither search-context nor Pro Search options, so standard fast/low defaults apply. |
| Exa `per_search` | **$0.005** | **$0.007** for Search with up to 10 results | No model ID | **Understates every canonical Search request by $0.002 (28.6%; actual/configured ratio 1.4)** | High. DAMM uses `type: auto` and no more than eight results. |
| Exa `per_content_page` | $0.001 | $0.001/page for stand-alone Contents and chargeable content types | No model ID | Number matches the stand-alone price, but is applied to the wrong request shape | High. Text/highlights embedded in Search are free through 10 results; AI summaries remain separately chargeable. |
| Jina `per_fetch` | **$0.001/fetch** | Reader is billed by output-response tokens, not by fetch | No model ID | **Not an official tariff and not a proven upper bound** | High on billing dimension. A later read-only account view verified $0.05/MTok as a conservative current-account upper rate; the production key-to-package mapping remains uncertain. |

MTok means one million tokens. Official source support for these rows is recorded below.

## Provider-by-provider evidence

### Anthropic

Anthropic's current [model pricing table](https://platform.claude.com/docs/en/about-claude/pricing) publishes $5/$25 for Opus 5 and Opus 4.8, $2/$10 for Sonnet 5, and $1/$5 for Haiku 4.5. The same page states that Sonnet 5's announced September 1 move to $3/$15 will not occur. It also publishes the relevant modifiers: first-party `inference_geo: "us"` is 1.1x, and Opus fast mode is $10/$50. Static inspection found no such modifier in DAMM.

Anthropic's [model-ID and versioning guide](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions) confirms `claude-opus-5`, `claude-opus-4-8`, and `claude-sonnet-5` are pinned dateless IDs. It also explains that pre-4.6 short names such as `claude-haiku-4-5` are convenience aliases to dated snapshots; the current dated Haiku ID appears in the same guide. Current availability can be checked against Anthropic's [models overview](https://platform.claude.com/docs/en/models/overview) and [deprecation schedule](https://platform.claude.com/docs/en/about-claude/model-deprecations).

The generic Anthropic `_default` is not a valid provider-wide ceiling. The current pricing table lists Fable 5/5.1 and Mythos 5/5.1 at $10/$50, and Opus fast mode is also $10/$50. Although those models/options are not in the audited resolver route, a price lookup should fail closed for an unknown model instead of silently assigning $5/$25.

### OpenAI

Official OpenAI documentation confirms all three IDs and their standard token prices:

- [`gpt-5.6-terra`](https://developers.openai.com/api/docs/models/gpt-5.6-terra): $2 input / $12 output per MTok; prompts above 272K input tokens are charged at 2x input and 1.5x output for the full request, yielding $4/$18.
- [`gpt-5.6-luna`](https://developers.openai.com/api/docs/models/gpt-5.6-luna): $0.20/$1.20, or $0.40/$1.80 above 272K.
- [`gpt-5.6-sol`](https://developers.openai.com/api/docs/models/gpt-5.6-sol): $4/$20, or $8/$30 above 272K. The model page says the short-context promotional price lasts at least through 2026-11-21.

The general [OpenAI API pricing page](https://developers.openai.com/api/docs/pricing) is consistent with those model pages. The configured $5/$25 default is conservative for canonical Terra and for Luna at both context tiers. It is not conservative for a long-context Sol fallback, contradicting `prices.json`'s claim that the placeholder “never reads low.” Model-specific, context-tier-aware rows are required.

### Google Gemini

Google's current [Gemini API pricing page](https://ai.google.dev/gemini-api/docs/pricing) publishes:

- `gemini-3.1-pro-preview`: $2/$12 at prompts up to 200K tokens and $4/$18 above 200K.
- `gemini-2.5-pro`: $1.25/$10 at prompts up to 200K and $2.50/$15 above 200K.

The dedicated model pages confirm the exact IDs and lifecycle class: [`gemini-3.1-pro-preview`](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-pro-preview) is a preview, while [`gemini-2.5-pro`](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-pro) is stable. Google's [deprecation table](https://ai.google.dev/gemini-api/docs/deprecations) lists no shutdown date for either.

`gemini-pro-latest` is documented as a possible alias value in Google's [Triggers API reference](https://ai.google.dev/api/triggers), but its target is not currently auditable. The last explicit mapping found in Google's [Gemini release notes](https://ai.google.dev/gemini-api/docs/changelog) says the alias switched to `gemini-3-pro-preview` on 2026-01-21; the deprecation table says that target shut down on 2026-03-09 and recommends 3.1 Pro Preview. No later official mapping notice was found. This may be a documentation lag or an unannounced re-point, but either interpretation makes a mutable alias unsuitable for a deterministic, exactly priced fallback. Pin the two exact IDs already ahead of it and fail closed if neither is available.

### Perplexity

Perplexity's current [pricing documentation](https://docs.perplexity.ai/docs/getting-started/pricing) lists Sonar Pro at $3 input / $15 output per MTok. Its low/medium/high search-context request fees are $6/$10/$14 per 1,000 requests; low is the default. For Sonar Pro, `search_type: fast` is the default standard behavior; Pro Search (`pro`) is not enabled unless requested. The [`sonar-pro` model page](https://docs.perplexity.ai/docs/sonar/models/sonar-pro) confirms the ID and shows response metadata containing both token usage and provider-calculated cost, including a $0.006 low-context request charge. Perplexity's [OpenAI-compatibility guide](https://docs.perplexity.ai/docs/sonar/openai-compatibility) confirms DAMM's `/chat/completions` path remains an accepted alias for the canonical `/v1/sonar` endpoint.

Relative to official low-context pricing, the configured-minus-official difference per request is:

```text
configured - official = (2 × input_tokens + 10 × output_tokens) / 1,000,000 - $0.001
```

Therefore the placeholder is conservative only when `2 × input_tokens + 10 × output_tokens >= 1,000`; tiny/error-like successful responses can still be undercounted by up to $0.001. A cleaner implementation would use the exact $3/$15 + $0.006 tariff and persist the provider's `usage.cost.total_cost` as a reconciliation value.

### Exa

Exa's current [API pricing page](https://exa.ai/pricing?tab=api) charges $7 per 1,000 Search requests with up to 10 results, or $0.007/request. The audited helper sends `type: "auto"`; all production call sites request at most eight results. Its configured $0.005 is therefore low by exactly $0.002 on every canonical Search call.

Exa's [Contents API guide](https://exa.ai/docs/reference/contents-api-guide) says content features embedded in `/search` are included at no extra charge through 10 results and cost $1 per 1,000 pages thereafter. The endpoint table separately prices stand-alone Contents at $1 per 1,000 pages and AI summaries at $1 per 1,000 pages. DAMM only increments `content_pages` when it embeds `contents.text` in Search (the paid production route does not request embedded text; the vendor smoke probe does). Thus `$0.001/page` is a real Exa tariff but is not the correct charge for DAMM's current embedded-text shape. For the bounded <=10-result helper, reserve and settle $0.007 flat, with zero content-page charge; add explicit pricing before permitting summaries or more than 10 results.

### Jina Reader

Jina's current [Reader page](https://jina.ai/reader/) says `r.jina.ai` meters the number of tokens in the output response and includes a high-level statement about failed requests. That statement does not establish the billing treatment for every explicit SaaS HTTP rejection, so this audit does not use it to release a local reservation. The audited code instead records a flat `fetches=1` at `$0.001` for both successful and failed fetches, does not record returned tokens, requests plain text, reads the full response, and only then slices the string to `max_chars`. That local slice neither limits provider billing nor bounds bytes read.

The fixed `$0.001/fetch` is not an official tariff. An older first-party Jina [pricing analysis](https://jina.ai/news/a-practical-guide-to-deploying-search-foundation-models-in-production/) published prepaid rates of $0.045–$0.05 per MTok; at the higher of those rates, `$0.001` buys 20,000 tokens. However, the current Reader page says a new pricing model took effect in May 2025, notes that some keys retain legacy package pricing, and hides the applicable top-up price until an API key is supplied. The old article therefore does **not** establish this production key's current effective USD/token rate. The later read-only account view recorded above establishes $0.05/MTok as a conservative account-level upper rate, but not which package is bound to the Render production key.

There is a technically sound metering and bounding path in Jina's current first-party documentation:

- Jina's official Reader repository documents [`X-Token-Budget`](https://github.com/jina-ai/reader#using-request-headers) as an integer that rejects a Reader request if resulting token cost exceeds the budget, and `X-Max-Tokens` as an integer >=500 that trims returned content to that maximum. The repository names [`crawler-options.ts`](https://github.com/jina-ai/reader/blob/main/src/dto/crawler-options.ts) as the source of truth; it also states the token-budget header is ignored only for the Search endpoint, not `r.jina.ai` Reader.
- With `Accept: application/json`, the authoritative response field is `data.usage.tokens`. Jina's own [DeepResearch Reader integration](https://github.com/jina-ai/node-DeepResearch/blob/main/src/tools/read.ts#L40-L64) reads that exact field.
- The public Reader materials do not provide a per-error billing guarantee sufficient to treat every explicit HTTP rejection as free. The hosted billing layer is outside the open-source repository, so the ledger must retain its bounded reservation when no authoritative usage field is returned.

A defensible implementation should use `X-Max-Tokens=C` to cap returned content and `X-Token-Budget=T` to cap total provider usage, where `T` contains deliberate headroom above `C`; reserve `T × conservative_account_rate_per_token` before the call, settle from `data.usage.tokens` on success, and retain `T` when a rejected request supplies no authoritative usage. The `4,096`-token policy headroom improves ordinary-page success but cannot prove that every malformed or adversarial description will avoid a 409; the strict provider cap plus typed source-local handling is the safety invariant. The baseline does none of those things, so Jina makes a finite real-dollar canary maximum impossible to prove there. The concurrent remediation uses the verified conservative account rate; exact production key/package attribution remains an operational pre-canary check.

## Accounting-integrity defects beyond the numeric table

### Historical costs do not automatically recompute

`prices.json` says correcting a price causes every past run to recompute from recorded counts. The implementation does not do that:

- `Ledger.record()` calculates and stores a rounded `cost` in each call record.
- `Ledger.spent()` sums the stored `cost` field.
- `Ledger.restore()` copies prior call dictionaries, including their old `cost`, into the live ledger.
- No re-pricing path was found in the audited tree.

Changing `prices.json` affects new records only. It does not retroactively correct checkpointed runs. Existing terminal Nigeria records must remain immutable; any historical correction should be a separate read-only derived report, never a rewrite of those runs.

### Generic defaults hide model/tier changes

`Ledger._price()` silently uses `_default` when no exact model row exists. `_resolve()` can select an exact candidate or a near-match from a live model list, while the ledger still receives the generic tariff. This collapses distinct model/context tiers and makes an unknown future model appear priced. Production accounting should fail closed when the selected provider/model/tier has no explicit tariff, and should journal the resolved model plus the applicable context/service modifiers.

### Retrieval calls lack a provider-cost reservation on the audited baseline

The Exa, Jina, and Perplexity helpers call `ledger.check(pass_name)` with zero headroom before making a request and record cost only afterward. Even with correct unit prices, a final retrieval call can cross a pass allocation. This compounds the tariff errors: Exa is already 40% more expensive than the configured search unit, and Jina/Perplexity are not request-bounded in the audited implementation.

## Maximum-spend implications

The workflow's default ceiling is `$500`; its protected allocations total 100% (Stage 1 45%, Stage 2 7.5%, Stage 3 10%, Stage 4 7.5%, Stage 5 10%, Stage 6 5%, Stage 7 15%, Stage 8 0%). That controls the ledger's configured-cost domain. It does not currently establish a provider-invoice ceiling.

For the canonical provider route, the reconciliation shape is:

```text
actual - configured
  = + $0.002 × Exa_search_requests
    + (Jina_output_tokens × effective_Jina_USD_per_token
       - $0.001 × recorded_Jina_fetches)
    + ($0.001 × Perplexity_requests
       - $2/MTok × Perplexity_input_tokens
       - $10/MTok × Perplexity_output_tokens)
    + Terra_context_tier_adjustment   # always <= 0 against configured $5/$25
```

Anthropic Opus 5 contributes no base-rate adjustment under standard global inference. Terra's adjustment is negative because the placeholder is above both official tiers. Perplexity is normally overcounted once a response contains modest output, but can be undercounted by at most `$0.001` per request. Exa always adds `$0.002` per canonical search. Jina's term is uncomputable from current checkpoints because output tokens were never recorded, and unbounded before the call because neither official header is sent.

Two counterfactuals show why a generic `$500` statement is unsafe (they are sensitivity bounds, not forecasts of the actual workflow mix):

- If `$500` of configured cost were entirely Exa Search at `$0.005`, it would authorize 100,000 searches whose official list-price cost is `$700`.
- If `$500` of configured cost were entirely long-context OpenAI Sol input at `$5/MTok`, the official `$8/MTok` tier would cost `$800`.

The actual canonical route is materially less exposed than either counterfactual, but a **hard current maximum cannot be calculated** because the Jina token count/rate is missing and retrieval calls lack pre-call reservations. Free credits must not be used to justify a maximum; they can expire or be shared with other workloads.

After remediation, the desired invariant is: every paid call reserves a worst-case list-price charge before network I/O, every successful call settles authoritative usage, only a provider-confirmed zero-billed failure releases that bound, and unknown model/tier combinations fail closed. Only then can the selected `--ceiling` be represented as a pre-tax maximum provider usage charge (subject to documented provider rounding and any separately disclosed non-token fees).

## Required remediation before a paid canary

1. Replace generic LLM defaults with explicit model and context-tier tariffs; update Sonnet 5 to $2/$10; encode Terra, Luna, Sol, Gemini 3.1 Pro Preview, and Gemini 2.5 Pro separately.
2. Remove `gemini-pro-latest` from deterministic fallback or resolve and price its exact target before any paid request. Unknown model/tier combinations must fail closed.
3. Set canonical Exa Search to $0.007 for <=10 results, charge embedded text/highlights at zero in that shape, validate the result-count bound, and reserve the full search charge before calling.
4. Set Sonar Pro to $3/$15 plus $0.006 for the explicit low-context/fast mode, bound output, reserve worst-case charge, and reconcile against Perplexity's returned cost metadata.
5. Identify the production Jina key's effective token package read-only and privately verify an explicitly authorized account-funding control. Send `X-Max-Tokens=C` plus `X-Token-Budget=C+4,096`, request JSON, record `data.usage.tokens`, reserve the strict total cap at the verified conservative account maximum token rate, and retain that bound for a provider rejection without authoritative usage.
6. Add a read-only re-pricer for historical usage or correct `prices.json`'s recomputation claim. Do not mutate terminal run ledgers.
7. Add regression tests first for every corrected tariff, context threshold, unknown-model failure, Exa <=10 shape, Perplexity request fee, Jina output-cap/usage extraction, rejected-request bounds, and checkpoint restore semantics.

## Official source register

All sources below were read on 2026-09-03. They are first-party provider documentation or first-party provider source repositories.

| Provider | Official source | What it establishes | Residual uncertainty |
|---|---|---|---|
| Anthropic | [Pricing](https://platform.claude.com/docs/en/about-claude/pricing) | Current base rates, Sonnet price decision, caching/fast/residency modifiers | Account discounts and future changes excluded. |
| Anthropic | [Model IDs and versioning](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions), [models overview](https://platform.claude.com/docs/en/models/overview), [deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations) | Exact IDs, pinned-vs-alias behavior, lifecycle | None material for today's listed IDs. |
| OpenAI | [API pricing](https://developers.openai.com/api/docs/pricing) | Current standard list-price framework | Account discounts excluded. |
| OpenAI | [Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol), [Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra), [Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna) | Exact IDs, short-context rates, >272K multipliers | Sol promotional rate has a stated minimum duration, not a permanent guarantee. |
| Google | [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) | Standard <=200K and >200K tariffs | Preview pricing/lifecycle can change. |
| Google | [3.1 Pro Preview](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-pro-preview), [2.5 Pro](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-pro), [deprecations](https://ai.google.dev/gemini-api/docs/deprecations) | Exact IDs, stability class, shutdown status | None material for exact IDs today. |
| Google | [Release notes](https://ai.google.dev/gemini-api/docs/changelog), [Triggers reference](https://ai.google.dev/api/triggers) | Last published `gemini-pro-latest` mapping and continued alias listing | Current alias target and tariff unresolved. |
| Perplexity | [Pricing](https://docs.perplexity.ai/docs/getting-started/pricing), [`sonar-pro`](https://docs.perplexity.ai/docs/sonar/models/sonar-pro) | Token rates, request-context fees/default, model ID, returned provider cost | Account discounts excluded. |
| Perplexity | [OpenAI compatibility](https://docs.perplexity.ai/docs/sonar/openai-compatibility) | `/chat/completions` remains an accepted Sonar alias | None material. |
| Exa | [API pricing](https://exa.ai/pricing?tab=api), [Contents guide](https://exa.ai/docs/reference/contents-api-guide) | Search, additional-result, content, and summary tariffs; embedded-content rule | Future beta features require separate review. |
| Jina | [Reader](https://jina.ai/reader/) plus read-only logged-in account dashboard viewed 2026-09-03 | Output-token metering, package-menu rates, key-specific pricing caveat | $0.05/MTok is a verified conservative account upper rate; exact Render key/package attribution and per-error billing remain unresolved. |
| Jina | [Reader request headers](https://github.com/jina-ai/reader#using-request-headers), [`crawler-options.ts`](https://github.com/jina-ai/reader/blob/main/src/dto/crawler-options.ts) | `X-Token-Budget`, `X-Max-Tokens`, validation/endpoint applicability | Hosted service could change after the cited commit; recheck at canary time. |
| Jina | [Jina's own Reader client](https://github.com/jina-ai/node-DeepResearch/blob/main/src/tools/read.ts#L40-L64) | Authoritative JSON usage path `data.usage.tokens` | Exact response schema is operationally testable only with a request; no request was made in this audit. |
| Jina | [2025 first-party pricing analysis](https://jina.ai/news/a-practical-guide-to-deploying-search-foundation-models-in-production/) | Historical $0.045–$0.05/MTok packages | **Not accepted as proof of the current production-key tariff.** |
