# Legal Notes

## Securities Attorney Consultation

**Status:** Pending — schedule before any public leaderboard or track record page goes live.

**Research question to bring to the call:**
"Do I need to register as an investment advisor if I publish automated stock analysis reports for a subscription fee — specifically, reports that include verdicts (buy/hold/avoid), price targets, and probability scores?"

**Key context for the attorney:**
- Platform is AI-generated research, not personalized advice
- Reports aggregate public data (SEC filings, price data, news)
- No direct management of client assets
- Subscription model (not AUM fees)
- Disclaimers are in place at `/disclaimer` and in the ToS

**Existing disclaimer coverage (confirmed):**
- `/frontend/app/disclaimer/page.tsx` — full standalone disclaimer page
- `/frontend/app/terms-of-service/page.tsx` — ToS with investment disclaimer language
- `/frontend/components/ui/InlineDisclaimer.tsx` — inline component for leaderboard/report pages

**Next step:** Book a 30-min consult via state bar securities attorney referral or a fintech-focused firm. Update this file after the call: [date], outcome: [register required / not required / conditional].
