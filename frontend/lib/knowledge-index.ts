// ─────────────────────────────────────────────────────────────────────────────
// Knowledge Index — centralized term registry for the interpretability engine.
// All tooltip, panel, and diagram content is driven from this single source.
// ─────────────────────────────────────────────────────────────────────────────

export type TermCategory =
  | 'valuation'
  | 'signals'
  | 'regime'
  | 'scoring'

export interface KnowledgeTerm {
  id: string
  name: string
  category: TermCategory
  /** Hover layer: 12–18 words max. Precision over completeness. */
  quickDefinition: string
  /** Panel layer: institutional-grade paragraph. */
  analyticalDefinition: string
  /** Why it exists, what problem it solves, how it behaves. */
  conceptualIntuition: string
  /** Decision-context guidance for the user. */
  practicalInterpretation: string
  /** Explicit cognitive traps. Each string starts with the error statement. */
  commonMisinterpretations: string[]
  /** Term IDs that are conceptually adjacent. Drives panel chip navigation. */
  relatedTermIds: string[]
  /** Whether a micro-diagram component exists for this term. */
  hasDiagram: boolean
}

export const KNOWLEDGE_INDEX: Record<string, KnowledgeTerm> = {
  structural_value_anchor: {
    id: 'structural_value_anchor',
    name: 'Structural Value Anchor',
    category: 'valuation',
    quickDefinition:
      'Intrinsic value estimate from blended fundamental methodologies, insulated from market price and sentiment.',
    analyticalDefinition:
      'A multi-methodology intrinsic value estimate derived from a weighted blend of forward earnings-based multiples, EV/EBITDA normalization, and discounted cash flow analysis. The Structural Value Anchor represents the probability-weighted central tendency for fair intrinsic value, calibrated against sector-specific fundamental benchmarks and adjusted for capital structure. It is intentionally insulated from price momentum and short-term market dynamics.',
    conceptualIntuition:
      'Markets price expectations, not value. At any given moment, a stock price reflects consensus sentiment about the future — which can diverge substantially from what the underlying business actually produces. The anchor exists to disentangle "what the market thinks" from "what the business is worth." Blending across three methodologies — P/E, EV/EBITDA, and DCF — provides natural error-correction: when one method produces an outlier, the others constrain the result. The anchor behaves as a gravity well — prices may deviate from it for extended periods, but fundamental forces tend to pull them back over multi-year horizons.',
    practicalInterpretation:
      'Use the Structural Value Anchor as your fundamental baseline. When current price sits significantly above the anchor, the market is pricing in expectations the business has not yet validated — introducing execution risk. When price sits below the anchor, the market may be underpricing fundamental earning power. The gap between current price and anchor is the raw input to valuation assessment. How you interpret that gap depends on regime context, signal alignment, and conviction confidence.',
    commonMisinterpretations: [
      'The Structural Value Anchor is a price target. It is not. It is an intrinsic value estimate. The path and timing of price convergence toward fair value depends on catalyst timing, market sentiment, and regime conditions — none of which are embedded in the anchor.',
      'If price is below the anchor, it is automatically a buy. The anchor may be accurate, but the market may be correct to discount the business temporarily — pending earnings acceleration, margin recovery, or a catalyst that has not materialized.',
      'The anchor updates with every price move. The anchor is derived from fundamentals, not price. It updates when earnings estimates, cash flow projections, or sector multiples change.',
    ],
    relatedTermIds: [
      'market_implied_value',
      'structural_premium',
      'valuation_elasticity',
      'conviction_score',
    ],
    hasDiagram: false,
  },

  market_implied_value: {
    id: 'market_implied_value',
    name: 'Market-Implied Value',
    category: 'valuation',
    quickDefinition:
      'The fundamental performance the current stock price implicitly requires to be analytically rational.',
    analyticalDefinition:
      'The intrinsic value implied by the current market price, derived through reverse-engineering the pricing inputs that would justify the prevailing valuation multiple under standard discounted cash flow or earnings normalization frameworks. Market-Implied Value represents the market\'s consensus expectation for future fundamental performance, expressed in value terms. Comparing it to the Structural Value Anchor reveals the direction and magnitude of market optimism or pessimism.',
    conceptualIntuition:
      'Standard valuation asks: given these fundamentals, what should the stock be worth? Market-Implied Value inverts this: given what the stock is worth, what fundamentals must be true? This inversion is analytically powerful because it converts price into a falsifiable hypothesis. Instead of debating whether a stock is cheap or expensive in abstract terms, the question becomes: is the growth rate the market is pricing achievable? If the implied assumptions look realistic — the current price is defensible. If they require performance beyond historical capability or sector norms — the market has embedded fragile expectations.',
    practicalInterpretation:
      'Use Market-Implied Value to stress-test the market\'s assumptions, not to validate them. Ask: "What future is already in the price?" If that future seems highly achievable, the stock may still have upside. If it requires near-perfect execution across multiple uncertain variables, the risk-reward asymmetry shifts unfavorably even for fundamentally sound businesses.',
    commonMisinterpretations: [
      'High Market-Implied Value means the stock is overvalued. It means the market is pricing a high-performance scenario. That scenario may be entirely justified. The critical question is whether the implied assumptions are achievable, not whether the number is large.',
      'Market-Implied Value is the analyst consensus price target. Analyst price targets are forward projections of fair value. Market-Implied Value is a reverse-engineering of current price — a distinct and often conflicting data point.',
      'This metric is only useful for expensive growth stocks. It is equally applicable to value stocks, where it reveals whether a depressed price implies permanently impaired fundamentals or temporary market pessimism.',
    ],
    relatedTermIds: [
      'structural_value_anchor',
      'expectation_compression',
      'structural_premium',
      'valuation_elasticity',
    ],
    hasDiagram: false,
  },

  structural_premium: {
    id: 'structural_premium',
    name: 'Structural Premium',
    category: 'valuation',
    quickDefinition:
      'Justified valuation above intrinsic value attributable to durable competitive advantages standard models cannot fully price.',
    analyticalDefinition:
      'The premium embedded in market price above the Structural Value Anchor, attributable to identifiable and durable qualitative factors: competitive moat depth, pricing power sustainability, ecosystem lock-in, capital allocation discipline, and structural growth durability. A Structural Premium is analytically valid when the factors generating it are defensible across economic cycles and cannot be rapidly replicated by competitors. It is distinct from speculative premium, which reflects sentiment or momentum without fundamental underpinning.',
    conceptualIntuition:
      'Standard valuation models are fundamentally present-moment constructs: they value what the business produces today, extrapolated forward under conservative assumptions. They systematically undervalue businesses with compounding structural advantages because those advantages produce returns that accelerate non-linearly over time. The Structural Premium compensates for this systematic undervaluation. A business with genuine pricing power, high switching costs, or a durable network effect will generate returns on capital above its cost of capital for longer than the model assumes — creating value the model cannot price. The premium is therefore analytically rational if the structural advantage is durable and identifiable.',
    practicalInterpretation:
      'When the platform identifies a Structural Premium, evaluate it against the moat analysis: what specific advantages justify trading above intrinsic value? How defensible are those advantages over the investment horizon? Structural Premiums command patience — they are multi-year return vehicles, not short-cycle trades. If you observe a business trading with a Structural Premium alongside deteriorating moat indicators, the premium is at risk of compression — potentially more damaging to returns than a fundamental earnings miss.',
    commonMisinterpretations: [
      'Structural Premium equals overvaluation. Overvaluation implies price exceeds justified value. A Structural Premium implies price exceeds model-derived intrinsic value but remains within justifiable value once structural factors are accounted for. These are conceptually distinct.',
      'A high Structural Premium means avoid the stock. It means the investment thesis depends on sustained structural advantage. If you have conviction in that advantage, the premium is appropriate.',
      'Structural Premium is permanent. No premium is permanent. It is contingent on the ongoing durability of the underlying structural advantages.',
    ],
    relatedTermIds: [
      'structural_value_anchor',
      'market_implied_value',
      'expectation_compression',
      'valuation_elasticity',
    ],
    hasDiagram: true,
  },

  expectation_compression: {
    id: 'expectation_compression',
    name: 'Expectation Compression',
    category: 'valuation',
    quickDefinition:
      'Multiple contraction driven by expectation revision, independent of and often concurrent with positive fundamental performance.',
    analyticalDefinition:
      'A valuation contraction dynamic in which previously elevated Market-Implied Value assumptions undergo systematic downward revision, resulting in multiple compression independent of — and often concurrent with — positive underlying fundamental performance. Expectation Compression is a function of the gap between embedded market expectations and realized or revised forward expectations, amplified by the convexity of high-multiple valuations. At high multiples, a small reduction in expected growth produces disproportionately large price declines.',
    conceptualIntuition:
      'Once expectations are elevated, the path to further upside narrows while the downside from any disappointment widens. A company priced at 40× forward earnings has very little margin for error. If growth comes in at 80% of what was expected — not a disaster — the multiple may contract from 40× to 28× as the market reprices toward a more achievable trajectory. A 30% multiple contraction on top of a modest revenue miss can produce a 40–50% stock decline despite the business remaining fundamentally sound. This is why Expectation Compression is one of the most dangerous forces for high-quality businesses at high valuations.',
    practicalInterpretation:
      'Monitor Expectation Compression signals when analyzing high-multiple positions. Key early indicators include: earnings guidance that decelerates even mildly, analyst estimate revision trends turning negative, and growing gap between Street estimates and management tone. When the platform\'s Market-Implied Value significantly exceeds the Structural Value Anchor, the risk of Expectation Compression is elevated. Strong fundamental businesses experiencing compression can become exceptional opportunities — after the compression cycle completes.',
    commonMisinterpretations: [
      'Expectation Compression only happens to overvalued stocks. Compression can occur in reasonably valued stocks if the narrative shifts and the market re-anchors expectations downward. It is an expectation dynamic, not strictly a valuation level dynamic.',
      'A good quarter prevents compression. A "good" quarter may still disappoint if it was below the market\'s embedded expectation. The trigger is underperformance versus priced-in expectations — not absolute performance.',
      'Compression means sell immediately. Compression may be temporary — particularly when caused by macro regime shifts rather than fundamental degradation. The correct response depends on whether compression reflects expectation reset or fundamental deterioration.',
    ],
    relatedTermIds: [
      'market_implied_value',
      'structural_premium',
      'valuation_elasticity',
      'regime_sensitivity',
    ],
    hasDiagram: true,
  },

  signal_divergence: {
    id: 'signal_divergence',
    name: 'Signal Divergence',
    category: 'signals',
    quickDefinition:
      'Directional conflict between independent analytical dimensions — fundamental, technical, quantitative, and sentiment signals in opposition.',
    analyticalDefinition:
      'A multi-dimensional analytical condition in which signals from distinct analytical frameworks — fundamental valuation, momentum and technical structure, quantitative factor models, and institutional sentiment data — generate directionally inconsistent assessments of risk-adjusted attractiveness. Signal Divergence quantifies the degree of analytical conflict across the platform\'s signal architecture, identifying cases where the investment thesis requires non-trivial synthesis rather than straightforward aggregation.',
    conceptualIntuition:
      'Each signal type captures a different market information structure. Fundamental signals capture intrinsic value dynamics over multi-year horizons. Technical signals capture near-term price structure and order flow. Quantitative factor signals capture cross-sectional alpha exposures. Sentiment signals capture institutional consensus. These information structures respond to different catalysts and are derived from different data sources. Convergence — when all signals align — is analytically powerful precisely because it is rare. Divergence reveals that the various information structures are in conflict, which can occur because: (a) the fundamental thesis is correct but unpriced, (b) technical action reflects positioning unwinding that does not alter the long-term case, or (c) one signal is capturing real risk others are missing.',
    practicalInterpretation:
      'When Signal Divergence is elevated, the investment case requires more nuanced analysis before position-sizing decisions. Use divergence as an analytical prompt: what specifically is in conflict? Is the divergence between near-term and long-term signals (a timing issue) or between fundamental and technical signals (a structural conflict)? High divergence cases often warrant smaller initial position sizes, with a plan to add as signals resolve. They are frequently where the best asymmetric opportunities emerge — and where the most significant analytical mistakes occur.',
    commonMisinterpretations: [
      'Signal Divergence means avoid the stock. Divergence means proceed with elevated analytical rigor, not avoidance. Some of the strongest investment opportunities exhibit significant near-term signal divergence precisely because the fundamental thesis is not yet broadly recognized.',
      'If the fundamental signal is strong, divergence does not matter. Technical fragility or adverse quantitative factor exposure can create material near-term drawdown risk even when the fundamental thesis is sound.',
      'Divergence will resolve quickly. Signal divergence can persist for extended periods — particularly when near-term technical signals conflict with long-term fundamental signals.',
    ],
    relatedTermIds: [
      'signal_dispersion',
      'technical_fragility',
      'conviction_score',
      'thesis_stability',
    ],
    hasDiagram: true,
  },

  signal_dispersion: {
    id: 'signal_dispersion',
    name: 'Signal Dispersion',
    category: 'signals',
    quickDefinition:
      'The statistical spread of signal scores across the analytical framework — high dispersion indicates fragmented, heterogeneous consensus.',
    analyticalDefinition:
      'A statistical property of the platform\'s multi-factor signal output representing the variance or standard deviation of normalized signal scores across the analytical framework. High dispersion indicates low analytical consensus — signals are spread broadly across the assessment range, producing a heterogeneous view of risk-adjusted attractiveness. Low dispersion indicates analytical consensus, where signals cluster in directional agreement, supporting higher-confidence assessment. Dispersion quantifies the uncertainty embedded in the composite signal output.',
    conceptualIntuition:
      'When averaging signals across analytical dimensions, high dispersion in the underlying inputs produces a composite score that may appear moderate but conceals extreme underlying conflict. A stock with a fundamental score of 8.5 and a technical score of 2.5 would produce a blended score of approximately 5.5 — which looks neutral. But the underlying dispersion reveals this is not a neutral stock: it is a stock with a compelling fundamental case and severe technical fragility. The composite average hides the analytical conflict that changes both position sizing and entry timing decisions. Dispersion forces this hidden conflict into view.',
    practicalInterpretation:
      'Treat Signal Dispersion as an uncertainty multiplier on the Conviction Score. High dispersion does not make a thesis wrong — but it expands the range of probable outcomes, which has direct implications for position sizing, risk budgeting, and hedging strategy. When dispersion is low and composite scores are high, position sizing can reflect the analytical consensus. When dispersion is high, size accordingly — build positions to absorb the range of outcomes that the spread of signals implies.',
    commonMisinterpretations: [
      'Low dispersion means low risk. Low dispersion means high analytical consensus. Consensus can be wrong. When all signals align bearishly on a fundamentally sound business, that consensus may itself be the opportunity.',
      'High dispersion is a red flag. High dispersion is an uncertainty flag. Whether that uncertainty represents risk or opportunity depends entirely on the direction and nature of the conflicting signals.',
      'Dispersion and Divergence are the same concept. Divergence identifies directional conflict. Dispersion quantifies the spread magnitude. Both dimensions are analytically necessary.',
    ],
    relatedTermIds: [
      'signal_divergence',
      'stability_score',
      'conviction_score',
      'thesis_stability',
    ],
    hasDiagram: true,
  },

  thesis_stability: {
    id: 'thesis_stability',
    name: 'Thesis Stability',
    category: 'scoring',
    quickDefinition:
      'Resilience of the investment thesis to assumption perturbation, scenario stress, and regime variation.',
    analyticalDefinition:
      'A composite assessment of the durability and consistency of the multi-factor investment thesis across varying analytical scenarios, regime conditions, and assumption perturbations. Thesis Stability quantifies the degree to which the investment case is conditional (fragile, dependent on specific outcomes) versus structural (resilient, supported across multiple scenarios). High stability indicates the thesis is supported by broad, cross-dimensional analytical consensus with limited sensitivity to individual assumption failures.',
    conceptualIntuition:
      'A strong composite score at a single point in time may be highly fragile — dependent on benign macroeconomic conditions, sustained margin performance, and elevated multiple acceptance all simultaneously holding. Stability analysis stress-tests this: what happens to the thesis if rates rise? If revenue growth decelerates by two points? If the sector multiple contracts? A robust thesis survives most of these perturbations. A fragile thesis requires all assumptions to hold simultaneously. This is the platform\'s analytical equivalent of stress-testing a position across a scenario distribution, not just a central case.',
    practicalInterpretation:
      'High Thesis Stability supports conviction position sizing across investment horizons. Low stability is an explicit signal to review entry timing, position size, and hedging — the investment case may be correct but sensitive to execution or market conditions. Stability scores are particularly critical for positions held through earnings cycles, macro regime transitions, or sector rotation events — all of which can disrupt unstable theses while leaving robust ones intact.',
    commonMisinterpretations: [
      'High Thesis Stability means guaranteed returns. Stability indicates resilience of the analytical framework — not elimination of return uncertainty. Stable theses can still underperform if fundamental assumptions diverge from actuals.',
      'Low Thesis Stability means the stock is a bad investment. Many of the highest-return investments carry lower stability scores precisely because they are non-consensus, asymmetric opportunities.',
      'Stability does not change over time. Stability is dynamic. A thesis that was fragile entering a volatile regime may become robust as regime conditions normalize and signals converge.',
    ],
    relatedTermIds: [
      'signal_dispersion',
      'signal_divergence',
      'conviction_score',
      'regime_sensitivity',
    ],
    hasDiagram: true,
  },

  regime_sensitivity: {
    id: 'regime_sensitivity',
    name: 'Regime Sensitivity',
    category: 'regime',
    quickDefinition:
      'Degree to which the investment thesis changes character under macro regime transitions — rate cycles, growth dynamics, risk appetite shifts.',
    analyticalDefinition:
      'A multi-factor assessment of an instrument\'s beta to macro regime transitions, capturing systematic sensitivity across: interest rate duration exposure, economic cycle positioning, credit spread sensitivity, risk appetite dynamics, and liquidity regime dependence. High Regime Sensitivity indicates the investment thesis is conditionally valid — analytically sound within a specific regime but potentially structurally challenged under regime transition.',
    conceptualIntuition:
      'Most valuation and signal frameworks are implicitly regime-conditional: they are calibrated against a specific macro backdrop, and their predictive validity degrades under regime transitions. A long-duration growth stock has a fair value highly sensitive to the discount rate, because future cash flows are discounted back over a longer period. When rates rise — a regime shift — the discount rate increases and the present value of future cash flows contracts, even if the underlying business has not changed at all. Regime Sensitivity makes this exposure explicit before the regime shift occurs, rather than discovering it after.',
    practicalInterpretation:
      'Evaluate Regime Sensitivity in the context of current and anticipated regime conditions. High-sensitivity positions in an unfavorable regime environment require explicit risk management — either reduced sizing, hedging instruments, or acceptance of elevated drawdown potential. Regime Sensitivity also creates opportunity: when regime shifts occur, high-sensitivity stocks frequently overshoot on the downside, creating attractive entry points for investors with sufficient time horizon to absorb the volatility.',
    commonMisinterpretations: [
      'High Regime Sensitivity means poor quality. Many of the highest-quality, highest-compounding businesses carry high regime sensitivity precisely because their superior long-term cash flow generation commands a duration premium. The sensitivity is the price of owning duration, not evidence of business fragility.',
      'Low Regime Sensitivity means safe. Low sensitivity often correlates with limited growth, regulatory protection, or utility-like characteristics — which carry their own analytical risks.',
      'Regime shifts can be timed precisely. The appropriate response to high regime sensitivity is position sizing discipline and time horizon calibration — not tactical switching.',
    ],
    relatedTermIds: [
      'volatility_regime',
      'liquidity_regime',
      'valuation_elasticity',
      'thesis_stability',
    ],
    hasDiagram: false,
  },

  valuation_elasticity: {
    id: 'valuation_elasticity',
    name: 'Valuation Elasticity',
    category: 'valuation',
    quickDefinition:
      'Sensitivity of the fair value estimate to modeling assumption changes — quantifies the effective confidence interval around the valuation.',
    analyticalDefinition:
      'The rate of change in the Structural Value Anchor with respect to perturbations in key input assumptions: terminal growth rate, WACC/discount rate, normalized margin, sector multiple, and capital structure assumptions. Expressed as the partial derivative of fair value with respect to each critical input, Valuation Elasticity quantifies model sensitivity and the effective confidence interval width around the central valuation estimate. High elasticity indicates that the valuation estimate should be treated as a wide distributional range rather than a point estimate.',
    conceptualIntuition:
      'All valuation models are sensitivity machines: they convert assumptions into a fair value output. The relationship between assumptions and output is non-linear, particularly in DCF frameworks where changes in the terminal growth rate produce exponential impact through the Gordon Growth Model denominator effect. Two stocks might show identical fair value estimates, but one might have an elasticity so high that the fair value could plausibly range from $80 to $200 depending on reasonable assumption variations — while the other\'s range might be $95 to $115. The point estimate is the same, but the analytical confidence interval is radically different. Valuation Elasticity converts this hidden model uncertainty into an explicit, interpretable dimension.',
    practicalInterpretation:
      'Use Valuation Elasticity to calibrate how much weight to place on the Structural Value Anchor. When elasticity is high, treat the anchor as a directional indicator, not a precise target. When elasticity is low — common in stable, asset-heavy, dividend-paying businesses — the anchor is more reliable as a precision reference point. High-elasticity valuations call for wider scenario analysis across bull, base, and bear cases rather than anchoring on a single estimate.',
    commonMisinterpretations: [
      'High Valuation Elasticity means the model is wrong. It means the model\'s output is sensitive to assumption uncertainty — which is a property of the business type and investment horizon, not a model failure.',
      'If fair value is $150, the stock is worth exactly $150. Point estimates from high-elasticity models should be understood as the center of a distribution, not a reliable target.',
      'Low elasticity is always better. Low elasticity often co-occurs with limited growth optionality and mature business models. High elasticity is frequently the signature of high-upside businesses — it is a two-sided property.',
    ],
    relatedTermIds: [
      'structural_value_anchor',
      'thesis_stability',
      'regime_sensitivity',
      'expectation_compression',
    ],
    hasDiagram: true,
  },

  technical_fragility: {
    id: 'technical_fragility',
    name: 'Technical Fragility',
    category: 'signals',
    quickDefinition:
      'Price structure vulnerability to accelerated selling — a supply/demand condition independent of fundamental quality.',
    analyticalDefinition:
      'A technical analysis condition characterized by one or more of: price trading below critical structural support levels with deteriorating volume confirmation, breakdown of primary trend integrity under sustained distribution, exhausted momentum oscillators with adverse divergence patterns, elevated short interest relative to float, and options market skew indicating institutional hedging activity. Technical Fragility indicates elevated near-term downside risk that exists in the price structure independently of fundamental developments.',
    conceptualIntuition:
      'Markets are populated by heterogeneous actors with different holding periods, risk tolerances, and liquidation triggers. Technical Fragility maps the structural vulnerabilities in a stock\'s price architecture that can be activated by these actor behaviors. Support levels represent price zones where prior buying interest emerged and where stop-loss orders, institutional re-entry mandates, and algorithmic triggers concentrate. When price approaches these zones, the balance of mechanical sell orders and discretionary support becomes the determining factor. This is analytically distinct from fundamental risk: a fundamentally excellent business can exhibit severe technical fragility during institutional position unwinding, index rebalancing, or sentiment-driven rotation.',
    practicalInterpretation:
      'Technical Fragility does not invalidate a fundamental thesis — but it creates near-term entry timing risk. If the platform identifies fragility concurrent with a compelling fundamental case, the correct analytical response is typically to await technical resolution rather than deploying capital into an unstable price structure. Fragility also creates opportunity: when technical breakdowns overshoot fundamental fair value, the conditions for asymmetric entry are established.',
    commonMisinterpretations: [
      'Technical Fragility means sell the position. For a long-term fundamental investor, fragility signals a timing and sizing decision — not necessarily an exit. The investment thesis duration matters critically here.',
      'Good fundamentals protect against technical fragility. Fundamentals determine where price ultimately goes. Technical structure determines the path it takes to get there. These are non-overlapping analytical dimensions.',
      'Technical analysis is not rigorous. Applied with volume confirmation and cross-dimensional signal integration, technical analysis is a systematic study of supply/demand dynamics and market microstructure behavior.',
    ],
    relatedTermIds: [
      'signal_divergence',
      'regime_sensitivity',
      'volatility_regime',
      'thesis_stability',
    ],
    hasDiagram: false,
  },

  conviction_score: {
    id: 'conviction_score',
    name: 'Conviction Score',
    category: 'scoring',
    quickDefinition:
      'Composite analytical confidence integrating signal alignment, dispersion, thesis stability, data quality, and regime compatibility.',
    analyticalDefinition:
      'A composite scoring metric representing the platform\'s probability-weighted confidence in the analytical assessment of a security, derived from: (1) the directional alignment of multi-factor signals, (2) the dispersion and divergence profile of the underlying signal architecture, (3) the stability of the investment thesis across scenario perturbations, (4) the quality and completeness of input data, and (5) regime compatibility with the investment thesis. The Conviction Score functions as an analytically derived confidence interval on the investment thesis.',
    conceptualIntuition:
      'A fundamental problem in multi-factor analytics is the conflation of signal strength with analytical confidence. A single very strong signal from one dimension might produce an apparently high composite score — but if that signal is unsupported by other dimensions and the underlying data quality is uncertain, the strength is illusory. Conviction Score decouples these dimensions: it measures both the thesis strength and the analytical confidence. A high-conviction, moderate-score position — where signals are moderate but tightly clustered, thesis is stable, and data quality is high — may be analytically superior to a high-score, low-conviction position with a single dominant signal and high underlying dispersion.',
    practicalInterpretation:
      'Use the Conviction Score to inform position sizing and portfolio risk budgeting. High conviction positions support larger allocations within strategy guidelines. Low conviction positions — even with favorable composite scores — should be sized conservatively. The Conviction Score also informs monitoring frequency: low-conviction positions require closer active monitoring as conditions evolve, because the analytical foundation is more sensitive to changes in signal state.',
    commonMisinterpretations: [
      'High Conviction Score equals high return certainty. Conviction quantifies analytical confidence, not return probability. Even a perfectly constructed, high-conviction thesis can underperform due to unpredictable external events.',
      'A low Conviction Score means avoid the position. Low conviction is often characteristic of early-stage theses before signals have time to converge. Managing a position with a deliberate scaling plan as conviction develops is often analytically appropriate.',
      'Conviction Score is the same as the composite investment score. The investment score measures thesis attractiveness. Conviction Score measures analytical confidence in that assessment. They are complementary but distinct.',
    ],
    relatedTermIds: [
      'stability_score',
      'signal_dispersion',
      'signal_divergence',
      'thesis_stability',
    ],
    hasDiagram: false,
  },

  stability_score: {
    id: 'stability_score',
    name: 'Stability Score',
    category: 'scoring',
    quickDefinition:
      'Temporal and cross-sectional consistency of platform signals — measures analytical durability, not price stability.',
    analyticalDefinition:
      'A time-series and cross-sectional consistency metric that quantifies the variance in platform signal outputs, valuation assessments, and thesis components across rolling analytical windows. Stability Score captures two dimensions: (1) temporal stability — how consistent signals are across successive evaluation periods, and (2) cross-sectional stability — how consistent the signal picture is across independent analytical frameworks evaluated at the same point in time. High scores indicate convergent, durable analytical configurations.',
    conceptualIntuition:
      'Individual signals can be highly informative at any point in time but highly volatile over time — meaning that acting on them requires constant revision as underlying data changes. This creates transaction cost risk, positioning whipsaw, and analytical noise that interferes with strategic decision-making. Stability Score operates as a meta-analytical filter: it tells you not just what the signals say, but how much you should trust that they will continue to say the same thing next period. A high Stability Score is an indicator that the analytical evidence base is durable — conclusions drawn from it will likely remain valid for longer.',
    practicalInterpretation:
      'Stability Score directly informs position horizon. High-stability analytical configurations support longer holding periods with reduced monitoring overhead. Low-stability configurations call for shorter-horizon active management, tighter disciplines, and more frequent thesis review. Stability Score also combines with Conviction Score: high conviction, high stability is the ideal configuration for significant allocation. High conviction, low stability requires conviction discounting until stability develops.',
    commonMisinterpretations: [
      'High Stability Score means the stock will not be volatile. Stability Score measures analytical signal consistency — not price volatility. A stable analytical picture can coexist with high price volatility in choppy market conditions.',
      'Low Stability Score means the analytical model is broken. Instability in signals often reflects genuine analytical uncertainty about a business in transition. The model is functioning correctly — it is faithfully reflecting an analytically uncertain environment.',
    ],
    relatedTermIds: [
      'conviction_score',
      'signal_dispersion',
      'thesis_stability',
      'regime_sensitivity',
    ],
    hasDiagram: false,
  },

  volatility_regime: {
    id: 'volatility_regime',
    name: 'Volatility Regime',
    category: 'regime',
    quickDefinition:
      'Classification of current market volatility character — level, clustering behavior, and structural type — affecting signal reliability and position sizing.',
    analyticalDefinition:
      'A macro-market classification system that categorizes the current volatility environment based on: implied volatility level and term structure, realized volatility dynamics, volatility-of-volatility, cross-asset correlation regime, and volatility clustering properties. Volatility regimes exhibit mean-reversion tendencies at extremes but can persist in intermediate states for extended periods. The regime classification directly affects position sizing, option pricing dynamics, signal reliability weights, and the risk-adjusted attractiveness of different strategy types.',
    conceptualIntuition:
      'Volatility exhibits a well-documented property called clustering — high-volatility periods tend to cluster together, as do low-volatility periods. This means that today\'s volatility reading is informative about tomorrow\'s expected volatility range, and that regime transitions between high and low volatility states are meaningful analytical signals. The Volatility Regime classification identifies not just the current level but whether the market is in a structurally stable low-vol regime (where signal reliability is higher and position sizing can be larger) or a structurally elevated high-vol regime (where signal noise increases and sizing discipline is critical).',
    practicalInterpretation:
      'In low-volatility regimes: analytical signals are generally more reliable, trend-following dynamics dominate, and position sizing can be calibrated toward fuller analytical conviction. In elevated volatility regimes: signal noise increases, mean-reversion of extremes becomes more actionable, and position sizing should be reduced to maintain equivalent risk-adjusted exposure. In transition regimes: monitor carefully as signal weights should shift with regime classification.',
    commonMisinterpretations: [
      'Low volatility equals a safe market. Low volatility regimes can be environments of risk accumulation, where complacency suppresses price discovery and creates fragility that releases violently during regime transitions.',
      'High volatility equals a bad market. Elevated volatility often creates the most compelling entry opportunities for investors with appropriate time horizons and conviction.',
      'Volatility Regime only matters for options strategies. Volatility regime affects equity position sizing, signal weighting, risk budgeting, and thesis stability assessments across all strategy types.',
    ],
    relatedTermIds: [
      'liquidity_regime',
      'regime_sensitivity',
      'technical_fragility',
      'signal_dispersion',
    ],
    hasDiagram: false,
  },

  liquidity_regime: {
    id: 'liquidity_regime',
    name: 'Liquidity Regime',
    category: 'regime',
    quickDefinition:
      'Aggregate financial market liquidity availability — primary driver of risk premium dynamics and valuation multiple expansion or contraction.',
    analyticalDefinition:
      'A macro-financial classification that quantifies the aggregate availability of market liquidity and financial system credit capacity, measured across: bid-ask spread dynamics, credit spread levels and trajectory, central bank balance sheet and rate posture, repo market functioning, and institutional leverage capacity. Liquidity regime is a systematic driver of risk premium dynamics, sector rotation patterns, and the valuation multiples markets assign to future earnings streams.',
    conceptualIntuition:
      'Liquidity functions as the transmission mechanism between monetary policy and asset prices. When liquidity is abundant — central banks are expansionary, credit spreads are narrow, financial conditions are loose — the cost of capital declines, risk premiums compress, and investors are willing to pay higher multiples for future cash flows. When liquidity contracts — rates rise, credit spreads widen, leverage capacity declines — the discount rate rises, risk premiums expand, and the multiple the market is willing to pay for future earnings compresses. This occurs even in the absence of fundamental deterioration: it is pure liquidity-driven repricing.',
    practicalInterpretation:
      'Liquidity Regime is a first-order determinant of whether to be positioned for multiple expansion (expansionary regime) or defensive positioning (contractionary regime). In expansionary regimes: growth assets, long-duration positions, and high-valuation premium names are structurally favored. In contractionary regimes: short-duration value, cash-generative defensives, and inflation-linked assets structurally outperform. The Liquidity Regime assessment should inform how aggressively to pursue opportunities identified by the platform.',
    commonMisinterpretations: [
      'Liquidity Regime only matters for credit investors. Every equity investor is implicitly a liquidity-regime investor: equity valuations are directly affected by risk premium dynamics that liquidity conditions drive.',
      'Individual stock quality protects against liquidity regime risk. During liquidity contractions, forced selling and risk-off rotation create indiscriminate selling that affects high-quality and low-quality assets simultaneously.',
      'Liquidity Regime changes are predictable. Regime transitions are structurally unpredictable in timing. Position for the regime, not the precise transition date.',
    ],
    relatedTermIds: [
      'volatility_regime',
      'regime_sensitivity',
      'structural_premium',
      'expectation_compression',
    ],
    hasDiagram: false,
  },
}

/** Convenience lookup by term ID. Returns undefined if not found. */
export function getTerm(id: string): KnowledgeTerm | undefined {
  return KNOWLEDGE_INDEX[id]
}

/** All terms as a sorted array (alphabetical by name). */
export const ALL_TERMS: KnowledgeTerm[] = Object.values(KNOWLEDGE_INDEX).sort(
  (a, b) => a.name.localeCompare(b.name)
)

/** Terms that have micro-diagram components. */
export const TERMS_WITH_DIAGRAMS = ALL_TERMS.filter(t => t.hasDiagram)

/** Category label map for display. */
export const CATEGORY_LABELS: Record<TermCategory, string> = {
  valuation: 'Valuation Framework',
  signals: 'Signal Architecture',
  regime: 'Regime Classification',
  scoring: 'Analytical Scoring',
}
