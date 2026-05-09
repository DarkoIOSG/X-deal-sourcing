"""Run the deep-dive agent on one hardcoded project. Edit TEST_PROJECT below."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from deep_dive.agent import deep_dive_and_log

# === Edit this with a real project you have an opinion on ===
TEST_PROJECT = {
    "handle": "@D2_Finance",
    "description": "Institutional-grade Derivatives Strategies for DeFi | Stablecoin, BTC, ETH, tokenized derivative strategies since 2023 | Real Risk-adjusted Returns at Scale",
    "categories": ["DeFi","Infrastructure"],  # match your Notion categories
    "tweets": [
        (
            "Why looping in crypto is broken, why we stopped, why you’re being sold repackaged "
            "credit risk as a savings account, and why we don’t need it anymore. "
            "Thanks to @chameleon_jeff and @HyperliquidX. "
            "Before founding D2, we spent a decade in institutional derivatives. "
            "Started at Bloomberg, then moved to global multi-billion-dollar hedge funds, "
            "and finished with a few years at PAG, a $55B Asian multi-strategy fund, "
            "trading volatility as a PM responsible for a multi-billion notional book. "
            "So when we say what the market is being sold as ‘stablecoin yield’ looks like "
            "a leveraged credit strategy in a wrapper, this isn’t theory. "
            "@ethena has executed beautifully on a favorable market setup. "
            "Funding has been positive, basis has been wide, delta-hedged shorts have earned. "
            "Mechanically it remains a leveraged basis trade that pays until funding flips, "
            "liquidity thins, or the short leg breaks. That is not a savings account. "
            "That is a credit hedge fund wrapped in USDe. "
            "Same logic applies to every looping stablecoin variant: sUSDe loops on Aave, "
            "syrup loops on Maple, avUSD, others. Borrow cheaper stable, lend richer "
            "yield-bearing stable, pocket the spread, repeat 5x. Works until it doesn’t. "
            "This week we documented two of these positions at -93% and -135% net APY, "
            "HF 1.01 and 1.02, ~$1B combined gross exposure. "
            "D2’s on-chain auditable track record: +3.8% (Dec 2023), +115% (2024), "
            "+31% (2025), +3% (2026 YTD). 2.6 Sharpe. 28 of 28 positive months. "
            "200% cumulative. "
            "We looped actively in February 2024. Long ETH looped into USDC on @aave, "
            "short ETH on @GMX_IO, at funding rates that peaked above 100% APR. "
            "One of the trades that made 2024 our best year. "
            "In 2025 we did lighter looping on the @fundstrat ETH run from $1,500. "
            "We exited when the setup started to look like a bubble, and rolled the delta "
            "exposure into call options on @DeriveXYZ. July expiry paid materially. "
            "August expired mostly worthless. Net result: we captured the DAT mania with "
            "defined downside. We did not need a crystal ball. We needed convex payoffs. "
            "Since then we have not found a looping setup worth taking. Not ideology — "
            "the risk-reward no longer clears. "
            "Hyperliquid liquidity has made gamma replication, delta hedging, and structured "
            "payoffs executable at spreads that do not exist anywhere else on-chain. "
            "We can now replicate most payoff profiles we like, with defined downside and "
            "substantially better risk-reward, without taking liquidation risk at HF 1.01. "
            "For fund managers: if your product is ‘leveraged credit, short convexity, "
            "earn carry until you cannot,’ label it correctly. "
            "For everyone else: if a product offers double-digit ‘stable yield,’ ask what "
            "happens in tail conditions. Ask for the funding chart, liquidity depth in stress, "
            "concentration of the borrower base, unwind mechanics. "
            "Looping pays carry until it doesn’t. Options pay when it matters. "
            "Fade D2 at your own risk."
        ),
        (
            "Counterparty risk on our $20M DeFi book just repriced. "
            "@aave shipped the recovery playbook: 8 thief positions liquidated cleanly on Aave V3. "
            "$71M recovered. Federal judge authorized an onchain DAO vote. "
            "Restraining order attaches on transfer. Other users untouched. "
            "Recovery used to be hope. Now it’s a process. "
            "Special credit to @ether_fi for kickstarting DeFi United. "
            "Without that early leadership, the coalition doesn’t exist."
        ),
        (
            "Is Claude also EVIL at trading? No. Out of the box, @claudeai is just NAIVE at it. "
            "It flags +5% NAV moves as ‘aggressive’ on a book with +200% mandate. "
            "It assumes hedge expiry cuts margin when ours can double. "
            "It defaults to ‘market neutral’ intuitions on an upside strategy. "
            "Anthropic’s new paper hit the same wall. Showing Claude ‘good behavior’ isn’t enough. "
            "The WHY is the asset. We don’t show Claude trades. We encode reasoning: "
            "1. Mandate framing. 2. Margin model under stress. 3. Vol regime priors. "
            "4. Position parsing rules. 5. Carry math. 6. Why we are not market neutral. "
            "7. The PM is the principal, Claude is the harness. "
            "200%+ cumulative. 2.6 Sharpe. 0% monthly DD. 28 epochs. "
            "The model didn’t get us there. The scaffolding did. "
            "Be skeptical of ‘build a hedge fund in 10 prompts’ threads. "
            "Don’t point Claude at copy trading on @HyperliquidX. Don’t expect alpha from a model. "
            "Claude accelerates prototyping, data wrangling, and risk flagging. "
            "Workflow leverage, not alpha. Claude is naive at trading."
        ),
        (
            "Or systematise it. Monetize volatility on the bitcoin. Never bottom sell your @unitxyz $BTC. "
            "hXXI since May 2025: +5.5% BTC denominated. ~7.95% net APR. "
            "14 epochs, 13 green, 92.9% win rate. 1.3 BTC Sharpe. Max DD -0.3%. "
            "Thanks to @phtevenstrong for the EOY yields review at the start of the year. "
            "BTC was down bad through that stretch. Listeners who allocated to hXXI protected capital. "
            "hXXI approaching 1 year live. D2 has been on-chain since December 2023. "
            "Through Aug 2024 deleveraging, Feb 2025 correction, Oct 2025 ADL cascade. "
            "80+ months of risk-adjusted returns across TradFi and DeFi. "
            "Two top-tier audits. Bootstrapped, not VC-funded. "
            "Show us anyone matching this on a full year of real BTC yield on @HyperliquidX. "
            "Fade D2 at your own risk."
        ),
        (
            "D2 is not an options vault. It’s a multi-strategy hedge fund that uses options. "
            "The distinction does real work. Thanks @DefiIgnas. "
            "The 2021-2022 vaults failed on structure D2 was deliberately built against. "
            "What those vaults shared: single-strategy short-vol exposure with no overlay, "
            "fixed weekly selling schedule regardless of regime, no regime awareness in sizing, "
            "retail users bearing convex losses without understanding the embedded short gamma. "
            "What D2 is: multi-strategy book — vol arb, dispersion, funding carry, "
            "spread monetization, event-driven RV. Options are one instrument across sleeves. "
            "Cross-portfolio margining through D2’s Central Book architecture. "
            "Regime-conditional sizing with ensemble models and CRO oversight. "
            "Institutional ops stack: ISDA/CSA, audited custody, BVI Approved Investment Manager, "
            "multi-firm smart contract audits. "
            "Return source: vol mispricings, dispersion, funding carry, spread monetization. "
            "Not token emissions. Not recursive stablecoin looping. Real external flows. "
            "Named failure modes: vol regime shift, liquidity gap, oracle failure, "
            "OTC counterparty default, correlation break, margin sequencing on stress day. "
            "Controls matched to each. $50-100M soft cap for flagship. "
            "Track record live at @defillama. Fade D2 at your own risk."
        ),
        (
            "Meanwhile KOSPI2 +6.62% today. +230% in twelve months. "
            "And crypto Twitter is still litigating which DVN config a bridge integrator ran in 2024. "
            "Feb 6, 2024, rsETH deployed on the MultiDVN default. LZ Labs plus Google. Two pathways. "
            "April 1, 2024, @KelpDAO manually migrates to a 1/1 config on both send and receive. "
            "Deliberate deviation from a stronger default toward weaker security. "
            "April 1, 2025, Kelp opens Unichain to Ethereum. ULN set 6 seconds later. Again at 1/1. "
            "The @LayerZero_Core integration checklist has explicitly warned against 1/1 for production "
            "since early 2025. "
            "@PrimordialAA has real questions to answer on RPC quorum default of 1, "
            "monitoring failure, and ~94% admin role overlap between LZ Labs and Nethermind DVNs. "
            "The conversation serious allocators should be having is portable alpha instead. "
            "How to stack uncorrelated return streams on top of beta. "
            "80+ months of audited track record across TradFi and DeFi. "
            "Capacity opening soon on top @nativemarkets $USDH."
        ),
    ],
}

# Mock or real Phase 2 scoring output
TEST_PHASE2 = {
    "thesis_fit_score": 62,
    "primary_thesis_match": "2.4 RWA on-chain, but credit/yield > tokenized equities",
    "category_fit": "moderate",
    "investment_pattern_matches": [
        "Pattern A \u2014 World-class crypto-native operator with shipped-at-scale credentials",
        "Pattern D \u2014 Real revenue, sustainable across cycles, with token-aligned value accrual",
        "Pattern G \u2014 Structural primitive enabled only by crypto rails",
    ],
    "pass_pattern_matches": [
        "Pattern P5 \u2014 Founder over-emphasizes financial engineering over distribution/GTM",
        "Pattern P3 \u2014 Token without value accrual, no clear narrative, no buyback commitment",
        "Anti-Pattern A3 \u2014 Web3 version of [Web2 thing] without identifying what crypto specifically unlocks",
        "Anti-Pattern A5 \u2014 Using AI/complexity to hide weak GTM",
    ],
    "hard_disqualifiers": [],
    "top_reasons": [
        "Former Bloomberg and multi-billion hedge fund traders with audited TradFi track record "
        "('80+ months of audited track record across TradFi and DeFi') \u2014 directly matches Pattern A "
        "founder bar set by Chromatic and Bifrost",
        "Real revenue stream from vol arb, dispersion, funding carry, and spread monetization "
        "('Return source. Vol mispricings, dispersion, funding carry, spread monetization. Not token emissions') "
        "\u2014 explicitly de-risks on Pattern D by naming external cash flows vs recursive stablecoin loops",
        "Institutional ops stack (ISDA/CSA, BVI Approved Investment Manager, multi-firm smart contract audits) "
        "with published loss distribution and capacity decay logic \u2014 directly aligns with Maple/Chromatic "
        "pattern of naming failure modes in advance",
    ],
    "top_red_flags": [
        "Founder communication heavily leans on sophisticated financial engineering vocabulary "
        "('ensemble regime models,' 'convexity buyers,' 'structural primitives') with minimal GTM detail "
        "\u2014 matches Anti-Pattern A5 and Pattern P5 diagnostic ('stuck in their head, dropping vocabulary "
        "to look smart'). Tweets explain *why* the strategy works, not *how* it scales or acquires.",
    ],
    "open_debate_relevance": None,
    "recommendation": "deep_dive",
    "one_line_summary": "Bootstrapped institutional DeFi hedge fund with audited 80+ month track record, "
                        "real external cash flows, and TradFi ops stack \u2014 thesis fit gated on token strategy.",
}

if __name__ == "__main__":
    thesis = Path("shared/prompts/thesis_doc.md").read_text()
    print(f"Running deep dive on {TEST_PROJECT['handle']}...\n")
    memo = deep_dive_and_log(TEST_PROJECT, thesis, TEST_PHASE2)
    print("\n" + "=" * 80)
    print("MEMO")
    print("=" * 80 + "\n")
    print(memo)
