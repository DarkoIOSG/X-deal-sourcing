---
name: deal-briefing
description: |
  Produces an IOSG-style investment briefing for a single startup/project — covers one-liner, value proposition, target customer, alternatives, sector funding landscape, VC thesis, the company's specific differentiation, risks & upsides, and a concrete recommendation. Use whenever the user gives you a project name, URL, pitch deck, transcript, or demo-day reference and asks for a "deal briefing", "投资简评", "投资简报", "项目简评", "evaluate this startup", "write up this project", "add this to the list", or similar. Also use proactively when the user pastes multiple projects/links from a luma/demo-day list and wants short investment writeups for each.
---

# Deal Briefing — IOSG Format

You're producing a single-project investment briefing in IOSG Ventures' house style. The output is always in English, regardless of input language. The briefing goes into a deal-flow doc that gets read by IOSG investment partners, so it must be data-dense, opinionated, and end with a concrete recommendation.

## When this skill triggers

- User gives you a project name + URL ("add Reactor", "write up Newsliquid", "把 Waybox 加进去" / "add Waybox in")
- User pastes a list of demo-day projects/founders and wants briefings for each
- User attaches a pitch deck PDF, transcript, or founder meeting notes and asks for an evaluation
- User says "投资简评" (investment brief), "deal brief", "项目评估" (project assessment), "评一下这个项目" (rate this project), "add this one"

## Required structure

**Always 7 bullets. Always in this order. Always in English.** Load `references/output-template.md` for the BLOCKING template and `references/example-jigsaw.md` + `references/example-fireworks-7section.md` for the gold-standard worked examples.

```
## [Project Name](official website link) 🟢/🟡/🔴

* **One-liner intro:** One sentence making clear what it does and who it sells to. If there's a clear product-line breakdown, point it out here.
* **Value proposition:** What the product does, what pain point it solves, what specific features/data/customer cases it has. 2-4 sentences, must include numbers.
* **Target customer:** Who the short-term, mid-term, and long-term customer profiles are, respectively.
* **Alternatives:** Direct competitors + indirect substitutes + the user's DIY solution. Each comp **bolded** + a one-sentence positioning + latest funding/valuation figures.
* **Sector capitalization status:** How much money the sector has raised overall, which well-funded comps exist, where the valuation water level sits. **Only data and facts, no opinions.** List 3-6 named comps + each one's latest funding data + investors.
* **The VC thesis:** Why VCs are betting on this sector, the underlying judgment, the historical analogy ("X is to the Y era what Z is"). **Sector-level judgment, unrelated to the specific company.** Must answer "why now."
* **Differentiation:** This company vs. other players in the sector — what's different: technology / team / channel / business model / geography. Then at the end of the paragraph attach **Risks: (1)(2)(3) + Upsides: (a)(b)(c)**. Risks must be specific and falsifiable, upsides must be concrete.
```

**Why the VC thesis and differentiation are split apart:** Previous versions lumped these two things together inside "sector capitalization status," and readers had a hard time distinguishing "why the VC likes this sector" (sector-level judgment) from "why this company" (company-level judgment). The investment committee's two distinct decision points — "should we look at this sector" and "should we invest in this company" — need to be answered separately.

**Don't write a standalone "conclusion" section.** The sense of direction (recommend follow-up / pass / pending in-person meeting) is expressed implicitly in the "upsides" at the end of the differentiation section, or just let the data speak for itself. If the user explicitly says "I want an IC memo / investment-committee version / full version," then add a conclusion section, but by default 7 sections is enough.

## Confidence label

Place it on the title line right after the project name:

* 🟢 = official website verified + public funding data verifiable + team background verifiable
* 🟡 = mainly pieced together from the official website + public news, but the product is evolving rapidly / public data is incomplete / details need to be confirmed in person
* 🔴 = public information is seriously insufficient, the description is largely speculation — **an in-person meeting is mandatory** before a real judgment can be made

If a batch of projects contains multiple 🔴/🟡, add an "uncertain projects list" subsection at the top of the document so readers can see at a glance which ones need further communication.

## Research methodology

The research steps before writing a briefing (in this order, don't skip):

1. **Official website fetch** (curl or WebFetch) — grab the meta description, tagline, product-page keywords. This is the project's own positioning, the most authoritative source.
2. **Founder/team search** — LinkedIn, Twitter, past companies, past projects. Assess founder-market fit.
3. **Funding lookup** — Crunchbase / PitchBook / TechCrunch / Chinese media (36Kr, ChainCatcher). **News from the last 6 months takes priority**; old funding data may already be outdated.
4. **Sector comp lookup** — find 5-10 well-funded direct/indirect competitors, record their latest funding rounds, valuations, lead investors, product differences. This is the source material for the "sector capitalization status" section.
5. **If the user provided a pitch deck / transcript / internal materials** — prioritize these, because the information density is an order of magnitude higher than public web pages. Dig out key data like BOM cost, ARR, customer names, contract amounts, pricing, token economics, etc.

If you've already obtained the official website link + team info + funding figures from the user's message or context, you can jump straight to the writing step; don't do redundant searches just to "look diligent."

## Writing style

* **Data density first:** every section must have concrete numbers (funding amount, valuation, ARR, user count, price, percentages). Adjectives without numbers ("rapid growth," "vast market") should be deleted or replaced with numbers as much as possible.
* **Position by comparison, not by adjectives:** don't say "an excellent team," say "the founder is the third employee at Stripe / a former OpenAI researcher / a Stanford CS PhD co-founder." Don't say "a huge market," say "the Bloomberg terminal generates $12B annually / there are 297 million cars in the US."
* **The sector capitalization section must list 3-6 named comps + each one's latest funding data.** This is the anchor for judging valuation reasonableness.
* **The risk section must be specific and falsifiable:** don't write "competition from giants," write "Anthropic has already built memory into Claude Code and could ship an official version within 6 months."
* **The VC thesis section must have a "why now":** explain why this sector suddenly became viable in 2025-26, rather than 2020 or 2030. You can use a historical analogy ("analogous to Scale AI relative to supervised learning in 2018") to make the judgment intuitive.
* **The risks/upsides at the end of the differentiation section must be concrete:** label risks with (1)(2)(3), label upsides with (a)(b)(c). Don't write "competition from giants," write "Anthropic has already built memory into Claude Code and could ship an official version within 6 months."

## IOSG context (default background knowledge)

When writing a briefing, assume these are known context by default and don't need explaining:

* IOSG is a crypto + AI infra–focused VC, currently on its third fund (~$100M scale), check size $500K–$3M
* Representative portfolio projects: Polygon, Arbitrum, Synthetix, Maker, 1inch, StarkWare, Worldcoin, Ondo, Eigenlayer
* Strong sectors: crypto infra, ZK, restaking, agent infra, AI x crypto intersection, East Asia ↔ West bridging
* For projects that can both issue a token and raise equity, IOSG typically cares about the equity → token mapping mechanism
* IOSG itself uses N8N + Slack + Notion + Otter + Telegram for internal AI workflows, so it has design-partner value for projects like AI-native CRM / KB / agent infra

If a project has synergy with IOSG's own portfolio or internal tools (e.g., it can be used by portfolio companies, can handle post-investment management for IOSG, or can solve an internal IOSG pain point), **explicitly point it out in the conclusion section** — this is often an IC plus.

## Output

After writing, if the user's current session is maintaining a Notion page (e.g., "AI Demo Day Investment Briefings") or a local markdown document, **proactively append to that document rather than only outputting in chat.** If the user says "add to this list" or "add this to the list," then definitely append to the existing document/Notion page.

If there's no existing document, after writing a single briefing, ask the user whether to save it to Notion / a local file, giving clear options.

## Sources

There must be a Sources list at the end, in markdown link form:

```
Sources:
- [Project name](URL)
- [Key article or pitch deck](URL)
- [Founder LinkedIn / Crunchbase](URL)
```

## Worked examples (reference)

Required reading before writing a new briefing:

- `references/example-jigsaw.md` — Jigsaw (RL environments + world models). The gold standard.
- `references/example-fireworks-7section.md` — Fireworks AI (inference cloud). The second benchmark, covering the infra sector + high valuation jump + hyperscaler coopetition scenario.

Both examples demonstrate the same thing: risks/upsides folded into the end of the differentiation section, no standalone conclusion section, all comp names bolded + immediately followed by funding figures.

## Trigger reminder

Remember: when the user gives you a project URL / name / pitch deck, **do not fall back to the generic "summarize this startup" approach.** Always use the 7-section structure, always in Chinese, with risks/upsides folded into the end of the differentiation section. This is a format requirement of IOSG's investment-decision process, not optional.
