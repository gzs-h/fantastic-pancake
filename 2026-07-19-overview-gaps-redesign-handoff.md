# Session Handoff — July 19, 2026: Overview & Gaps Redesign

Continues from `2026-06-28-session-handoff.md`, which floated a "personalized scoring system" idea (use `myRating` history to find patterns in what GA actually likes) but shelved it as premature with thin data. This session's discussion arrived at a related but more specific problem — read that file too if you want the full arc.

## Where things stand

Two things happened this session: (1) routine sync/add-wine work that's done and deployed, and (2) an open-ended design discussion about the `OVERVIEW_PARAS` / `GAP_ITEMS` narrative sections that is **not resolved** and is the reason for this handoff. GA is moving the design discussion to a fresh instance to avoid context decay. Everything below the "Completed and deployed" section is unresolved — pick up the conversation, don't just implement something.

## Completed and deployed (no action needed)

1. Synced an exported dashboard HTML (`--sync` + `--pull-forms`), bringing the collection to 69 SKUs / 72 bottles / 10 countries. 39 active wines are still missing `purchasePrice` (flagged to GA, he chose to deploy anyway and hasn't asked for it to be fixed).
2. Manually added Weingut Keller Riesling "RR" 2025 (id 116, Rheinhessen, $99 purchase price, researched score/market price/drink window) directly to `wines.json`.
3. Rewrote `OVERVIEW_PARAS` in `generate_dashboard.py` from a long, list-heavy 3-paragraph block into a tighter 3-paragraph structure (scope → value → composition). Added new self-updating stat variables to support it: `france_count`, `usa_count`, `italy_count`, `germany_count`, `rose_count`, `dessert_count`, `avg_score`, `price_min`, `price_max`, `rndc_count`. Also fixed `multi_btl_str` to include producer name (was ambiguous with wine name alone).
4. Rewrote `GAP_ITEMS` (6 items) to reflect current collection state — notably reframed the Spain item from "still light" to "Rioja now covered" based on the López de Heredia Viña Tondonia acquisition.
5. Deployed. Live at https://ga-wine-cellar.netlify.app.

**Important wrinkle discovered *after* deploying #4**: the "Rioja now covered" framing is arguably wrong — see below. GA caught this in discussion, not before deploy. It's still live as-is; nobody has asked to revert it yet, but it's the trigger for everything that follows.

## The debate that unwound the Gaps section

GA pushed back on the Gaps section on two fronts, and both landed:

**1. "Value" framing is wrong.** The Overview claims things like "RNDC bottles bought at $18 are worth $150–225 at market" as if that's an achievement. GA's objection: if you don't like the wine, the market-price delta is irrelevant — you spent $18 on something you dislike, full stop. Market/critic price is only meaningful as a proxy for personal enjoyment if your palate actually agrees with the market, which is unverified for most of these bottles. Agreed as correct; not yet fixed in the actual Overview text (paragraph 2 still uses this framing as of the last deploy).

**2. Geographic breadth ("gaps" = unrepresented regions) isn't inherently virtuous.** Completism could just reflect available shelf space/budget, not curation quality. I'd used the phrase "canonical wine region syllabus" to describe the assumption baked into the Gaps section, which GA correctly called out as priming disagreement — it named the problem without arguing for it.

**Resolution reached**: GA is explicitly in an exploratory phase and does want to chase down regions like Rioja/Portugal/Northern Rhône — so breadth-as-a-goal is legitimate right now, not rejected outright. But the mechanism should be **tasting**, not **acquisition**. Owning an unopened bottle (López de Heredia) proves nothing about whether GA likes Rioja; only drinking it does. This reframes the whole Gaps section: it should track exploration status via `consumed` history (including ad-hoc Log Tasting entries, which don't require buying into the active collection), not via what's sitting on the shelf.

**Verified with real data** (this matters — don't take the old Gap text at face value):
- **Rioja**: has real signal, but modest — two Kirkland Signature Rioja Reserva ad-hoc/consumed entries, both rated `good` (not `very good`/`outstanding`). Plus one serious bottle (López de Heredia Viña Tondonia, id 115) sitting in the active collection, completely untasted/unrated. So "Rioja now covered" in the current live Gaps text is misleading — it's covered on the shelf, not covered by any actual positive tasting experience.
- **Northern Rhône**: zero footprint anywhere — active or consumed. Checked appellation/region/wine/producer text for "rhone/rhône/hermitage/cornas/côte-rôtie/condrieu/syrah" — only matches were the two already-known Southern Rhône bottles (Sablet, Châteauneuf-du-Pape) and an unrelated Maryland Syrah that just shares a grape.
- **Portugal**: zero footprint anywhere, active or consumed. Confirmed via direct country filter.

So there are at least two distinct tiers: **genuinely untouched** (Portugal, Northern Rhône) vs. **some signal, unresolved** (Rioja — tried at a casual tier, one serious bottle purchased but not yet tasted).

## Proposed restructure (agreed in direction, not yet built)

Split the current single "Collection Gaps" block into two:

**A. "For Further Exploration"** (new section) — forward-looking, discovery-oriented. Not fully computable — "worth exploring" is a judgment call — but the *evidence tier* (zero signal vs. partial signal) should be verified from data rather than asserted, the way the Rioja/Portugal/Rhône check above was done. Stays mostly hand-curated prose, like today's Gaps, but grounded in a real tasting-history check instead of a guess.

**B. Rebuilt "Collection Gaps" → renamed "Worth Restocking"** (GA's preferred name over my "reconnect with" suggestion) — backward-looking, restocking-oriented. Fully computable from `wines.json`, no hand-curation needed, regenerates every build. Logic as GA specified: flag something if (1) it's NOT in the current active `wines`, (2) it HAS appeared in `consumed` before (either drunk down from the collection or tasted ad-hoc — both count), and (3) it was rated `very good` or `outstanding` (GA explicitly wants the bar kept high — "I drink a lot of good wine, so the bar for collection should be higher" — `good` tier should NOT qualify, even though it's common in the data).

### Validated the "Worth Restocking" logic against real data

First pass matched on exact `(producer, wine)` string equality and produced a **false positive**: it flagged "Weingut Keller Riesling RR" as a restock candidate because the consumed entry (id 84, ad-hoc, rated `very good`) is logged as `Riesling RR` while the newly-added active wine (id 116) is `Riesling "RR"` — the quote marks broke the match, even though it's clearly the same wine GA already re-bought. **Fix**: normalize both fields (lowercase, strip non-alphanumeric) before comparing. After normalizing, that false positive disappears.

With normalization + `very good`/`outstanding` threshold, **9 real candidates** surface (as of this session's data):
- Louis Jadot Chapelle-Chambertin Grand Cru 2004 (consumed, `very good`)
- Littorai Pivot Pinot Noir 2023 (consumed, `very good`)
- Spring Mountain Vineyard Elivette (3L) 2001 (consumed, `very good`)
- Albert Bichot Chassagne-Montrachet 2022 (tasted **twice** — once ad-hoc id 76, once regular consumed id 14 — both `very good`; also a data quality inconsistency: one entry has `region: "Burgundy"`, the other `region: "France"` for the same wine)
- Ca' Del Baio Paolina Barbera 2024 (ad-hoc, `very good`)
- Hirsch Vineyards The Bohan-Dillon 2023 (ad-hoc, `very good`)
- Constant Crush Wine Co. Pinot Noir 2023 (ad-hoc, `very good`)
- Pierre-Marie Chermette Brouilly Pierruex 2022 (ad-hoc, `very good`)

Note: **nothing in the current rating history hits `outstanding`** — `very good` is the actual ceiling so far. Worth keeping in mind if the threshold ever feels too strict/loose.

## The unresolved core problem: bottle-level vs. trait-level matching

GA's objection to the 9-candidate list above: it's too literal. Two specific problems he raised:

1. **Littorai Pivot Pinot Noir** is flagged as "buy more of this" — but GA already has plenty of Littorai and Sonoma-region Pinot Noir active (Mays Canyon, Wendling, plus Calstar Sangiacomo, Ultramarine, Amity, Failla elsewhere in Sonoma/Oregon). Bottle-level matching doesn't see that the *category* (cool-climate Sonoma Pinot Noir) is already well covered, even though this exact bottling isn't currently on hand.
2. **Chapelle-Chambertin Grand Cru** should generalize to something like "Grand Cru/Premier Cru Pinot Noir from the Chambertin vineyard cluster" — a real gap — rather than literally "buy 2004 Chapelle-Chambertin again" (that exact vintage isn't even purchasable anymore).

So GA wants restocking to operate one level of abstraction up: trait/type, not exact bottle. I pulled the actual field data to test whether this is mechanically easy, and **it isn't** — two concrete problems surfaced:

**Problem 1 — cru-tier language is inconsistently located.** For the active Louis Jadot Gevrey-Chambertin Clos Saint-Jacques, "Premier Cru" is in the `appellation` field ("Gevrey-Chambertin Premier Cru"). For the consumed Chapelle-Chambertin, "Grand Cru" only appears in the `wine` field ("Chapelle-Chambertin Grand Cru") — the `appellation` field just says "Chapelle-Chambertin" with no tier qualifier. A keyword scan for tier would need to check both fields, and there's no guarantee every wine states its tier explicitly anywhere.

**Problem 2 — `region` is too coarse to carry the distinction that actually matters.** Both Chapelle-Chambertin (Côte de Nuits, grand cru) and Chassagne-Montrachet (Côte de Beaune, village-level) just have `region: "Burgundy"` — identical to 6 other active Burgundy Pinot Noirs (Marsannay, Fixin, Hautes-Côtes de Nuits, Nuits-Saint-Georges 1er Cru, Nuits-Saint-Georges village, Gevrey-Chambertin Premier Cru). If the trait is "region + varietal," Burgundy Pinot Noir reads as fully saturated and **neither** of GA's examples would surface — which contradicts what GA is asking for. Getting this right requires sub-region knowledge (Côte de Nuits vs. Côte de Beaune, or specific vineyard clusters like the nine "Chambertin" grand crus) that doesn't exist as a field today.

By contrast, region + varietal alone works fine for the Littorai case — Sonoma Coast + Pinot Noir is clearly saturated already, no sub-region nuance needed there. So the granularity that's "right" varies by region: Burgundy needs fine-grained cru/sub-region logic to be useful; Sonoma didn't need it at all for this test case.

**Three options were laid out, not yet decided between:**
1. Keep bottle-level matching as a computed shortlist; let GA apply the abstraction judgment manually during review (cheapest, least automation, matches the review pattern already in use for Overview/Gaps text).
2. Add a keyword-detected tier flag (village/premier cru/grand cru, scanning both `wine` and `appellation`) layered on region + varietal. Catches Chambertin reasonably, still blind to Côte de Nuits vs. Côte de Beaune, needs Burgundy-specific (and eventually region-specific) keyword upkeep — French crus, German VDP/Prädikat tiers, Italian DOCG/Riserva, Spanish Reserva/Gran Reserva, Napa single-vineyard/reserve naming (unregulated) would all need separate rules.
3. Add a real, explicitly-maintained sub-region/tier field to the wine schema going forward. Most accurate, but ongoing manual data-entry overhead every time a wine is added or a tasting logged — a schema change, not just a build-script change.

**This is where the conversation stopped.** GA said "let's take this to a new instance."

## Decisions GA has made so far (don't re-litigate these)

1. Section name: **"Worth Restocking"** (not "Collection Gaps" — that name is misleading once it's restock logic rather than a geography checklist).
2. Rating threshold for restocking: **strict — `very good`/`outstanding` only**, explicitly excluding `good`. GA's reasoning: he drinks a lot of good wine already, so the bar for "worth restocking" should be higher than average.
3. Restock matching needs **normalization** (case/punctuation) — confirmed necessary, already demonstrated why (Keller RR false positive).
4. Breadth/exploration is a legitimate goal for GA right now (he's in an active exploratory phase) — but must be measured via **tasting history**, not shelf acquisition.

## Still open — pick up here

- **The trait/type abstraction question above** (options 1–3) is the main unresolved item. Needs a real decision, and probably needs GA's input on how much manual-maintenance overhead he's willing to take on.
- Display format for "Worth Restocking" entries (just producer/wine/vintage/rating, or also a note excerpt + date?) — GA said "not sure."
- Placement — new card next to Gaps in the same Overview tab area, or its own tab? — GA said "not sure."
- The "For Further Exploration" section's actual shape/content hasn't been drafted at all yet — only the *evidence-tier logic* behind it (zero signal vs. partial signal) has been validated with data.
- The live "value" paragraph (Overview paragraph 2, RNDC $18→$225 framing) has an agreed-upon flaw (conflates market arbitrage with personal enjoyment) that hasn't been fixed yet — nobody's asked for a rewrite, but it's inconsistent with the conclusions reached later in the same conversation.
- The live "Spain: Rioja now covered" Gap item (currently deployed) is now understood to be wrong per the tasting-history logic — it should probably read as "Rioja: tried at a casual tier (2×, rated `good`), one serious bottle on hand but untasted" rather than "covered." Not yet reverted.
- Minor data quality bug spotted in passing: the two Albert Bichot Chassagne-Montrachet consumed entries (ids 14 and 76) disagree on `region` ("Burgundy" vs "France") for what should be the same field value. Small fix, unrelated to the main design question, but worth cleaning up whenever `wines.json` is next touched.
- Related, deferred idea from the prior session (`2026-06-28-session-handoff.md`): a full personalized-scoring system using rating history to find patterns across varietal/region/price. That was shelved as premature with thin data (~11 consumed, 7 rated at the time). Data has grown since (consumed is now up to ~48 entries). Worth asking GA whether the "Worth Restocking" trait-abstraction problem should actually be solved as part of that bigger scoring effort rather than as a standalone feature — they're clearly related (both need some notion of "what category does this wine belong to" derived from thin, inconsistent fields).

## Relevant files

- `generate_dashboard.py` — `OVERVIEW_PARAS` and `GAP_ITEMS` (search for "curated narrative" comment), plus the stat variables added this session (search for `france_count` or `rndc_count`).
- `wines.json` — source of truth; `wines` (active) and `consumed` (history, includes `adhoc: true` tastings and `myRating`/`myNote` fields).
- `template.html.j2` line ~52 — renders `gap_items` as `.gap-item` divs; would need a second loop/section for a new "Worth Restocking" or "For Further Exploration" block.
- `dashboard.css` — `.gap-item` / `.gap-label` classes, reusable or adaptable for new sections.
- CLAUDE.md in this folder has the full schema/workflow reference if needed.
