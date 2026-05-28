# Deal Briefing Output Template

**BLOCKING template** for the deal-briefing skill. Every briefing MUST follow this exact 7-bullet structure, in this order, in English. No exceptions. Fill in the `{{...}}` placeholders; delete the meta-comment block before output.

Worked examples to match for format + data density:
- `example-jigsaw.md` — gold standard (Jigsaw, RL environments + world models)
- `example-fireworks-7section.md` — AI inference cloud (Fireworks)

---

## Template

```
## [{{Project name}}]({{official website URL}}) {{🟢 / 🟡 / 🔴}}

- **One-liner intro:** {{1-2 sentences: what it does, who it sells to. If there's a clear product-line breakdown (e.g., Product A + Product B), point it out here.}}
- **Value proposition:** {{2-4 sentences: the pain point solved + how the product solves it + a one-sentence positioning ("selling shovels to X" / "the Stripe of X" / "X is to the Y era what Z is"). Must include concrete numbers (performance / cost / customer cases).}}
- **Target customer:** {{Short-term, mid-term, long-term customer profiles. Specific down to industry + company type, ideally naming 2-5 representative customers/customer types.}}
- **Alternatives:** {{3-8 comps. Each comp's company name in **bold**, immediately followed by a one-sentence positioning + latest funding/valuation figures. Cover direct competitors + indirect substitutes + the user's DIY solution.}}
- **Sector capitalization status:** {{How much money the sector has raised overall, which well-funded comps exist, where the valuation water level sits. **Only data and facts, no opinions.** List 3-6 named comps + each one's latest funding data.}}
- **The VC thesis:** {{1-3 sentences: why VCs are betting on this sector, the underlying judgment, the historical analogy ("X is to the Y era what Z is"). This is a sector-level judgment, unrelated to the specific company. Must answer "why now."}}
- **Differentiation:** {{This company vs. other players in this sector — what's different: technology / team / channel / business model / geography. Then attach **Risks: (1)(2)(3) + Upsides: (a)(b)(c)**. Risks must be specific and falsifiable (don't write "intense market competition"); upsides must be grounded in concrete team/technology/narrative advantages.}}

Sources:
- [Project name]({{URL}})
- [Key article or pitch deck]({{URL}})
- [Founder LinkedIn / Crunchbase]({{URL}})
```

---

## Confidence label (immediately follows the project name)

- **🟢** = official website verified + public funding data verifiable + team background verifiable
- **🟡** = mainly pieced together from the official website + public news, but the product is evolving rapidly / public data is incomplete / details need to be confirmed in person
- **🔴** = public information is seriously insufficient, the description is largely speculation — **an in-person meeting is mandatory** before a real judgment can be made

If a batch of projects contains multiple 🔴/🟡, add an "uncertain projects list" subsection at the top of the document.

---

## Hard writing rules

1. **Data density first:** every section must have concrete numbers (funding / valuation / ARR / user count / performance benchmarks / price / percentages). Adjectives without numbers ("rapid growth" / "vast market" / "competition from giants") must be deleted or replaced.
2. **Position by comparison, not by adjectives:** don't say "an excellent team," say "the founder is the third employee at Stripe / a former OpenAI researcher / a Stanford CS PhD co-founder." Don't say "a huge market," say "the Bloomberg terminal generates $12B annually / there are 297 million cars in the US."
3. **The sector capitalization section must list 3-6 named comps + each one's latest funding data + investor list.** This is the anchor for valuation reasonableness.
4. **The risk section must be specific and falsifiable:** don't write "competition from giants," write "Anthropic has already built memory into Claude Code and could ship an official version within 6 months."
5. **The VC thesis must have a "why now":** explain why this sector suddenly became viable in 2025-26, rather than 2020 or 2030. Use a historical analogy to make the judgment intuitive.
6. **The VC thesis and differentiation are two independent judgments:** thesis = "why look at this sector" (sector level); differentiation = "why this company" (company level). Don't mix them.
7. **Comp names use `**bold**` + a one-sentence positioning + funding figures.** For example: `**Mercor** (expert-data marketplace, valuation $2B+)`.
8. **Risks/upsides are folded into the end of the differentiation section:** use `(1)(2)(3)` to list risks, `(a)(b)(c)` to list upsides. Don't split them into a separate section. Don't write a standalone "conclusion" section — put the sense of direction in the final sentence, or just let the data speak for itself.

---

## IOSG synergy (optional final sentence)

If the project has synergy with IOSG's portfolio or internal tools (usable by portfolio companies / handles post-investment management for IOSG / solves an internal IOSG pain point), explicitly point it out in the final sentence of the differentiation section. This is an IC plus, but not mandatory.
