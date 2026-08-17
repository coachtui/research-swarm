"""DVRG-branded CSS styles for WeasyPrint PDF generation."""

PDF_CSS = """
/* ===== DVRG PDF Report Styles ===== */

:root {
    --dvrg-teal: #0E6E5C;
    --dvrg-teal-dark: #00B396;
    --dvrg-dark: #0A0E1A;
    --dvrg-surface: #1A1F2E;
    --dvrg-border: #2A3040;
    --text-primary: #1a1a2e;
    --text-secondary: #4a5568;
    --text-muted: #718096;
    --success: #10B981;
    --warning: #F59E0B;
    --error: #EF4444;
    --info: #3B82F6;
}

@page {
    size: letter;
    margin: 0.75in 0.75in 0.9in 0.75in;
    @top-left {
        content: element(pagelogo);
        padding-top: 0.15in;
        vertical-align: bottom;
    }
    @top-right {
        content: string(ticker-name);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        font-size: 9pt;
        color: #718096;
        padding-top: 0.15in;
    }
    @bottom-center {
        content: counter(page) " of " counter(pages);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        font-size: 8pt;
        color: #718096;
    }
    @bottom-right {
        content: "";
        font-size: 7pt;
        color: #a0aec0;
    }
}

@page :first {
    @top-left { content: none; }
    @top-right { content: none; }
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 9.5pt;
    line-height: 1.45;
    color: var(--text-primary);
    margin: 0;
    padding: 0;
}

/* ===== PAGE BREAKS ===== */
.page-break { page-break-before: always; }
.avoid-break { page-break-inside: avoid; }

/* ===== COVER / PAGE 1 ===== */
.cover-header {
    border-top: 2px solid #1A2233;
    padding-top: 0.3in;
    margin-bottom: 0.25in;
}

.cover-header .brand {
    font-size: 20pt;
    font-weight: 800;
    color: #0E6E5C;
    letter-spacing: -0.5px;
    margin: 0;
    string-set: ticker-name attr(data-ticker);
}

.cover-header .subtitle {
    font-size: 10pt;
    color: #718096;
    margin: 2pt 0 0 0;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}

.cover-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin: 0.15in 0;
    padding: 8pt 0;
    border-bottom: 1px solid #e2e8f0;
}

.cover-meta .ticker {
    font-size: 17pt;
    font-weight: 700;
    color: var(--text-primary);
}

.cover-meta .date {
    font-size: 10pt;
    color: var(--text-muted);
}

/* ===== THE CALL BOX ===== */
.the-call-box {
    background: #FFFFFF;
    border: 0.5pt solid #D9DDE3;
    border-left: 2.5pt solid #0E6E5C;
    padding: 7pt 10pt;
    margin: 6pt 0;
    page-break-inside: avoid;
}

.the-call-box .call-header {
    display: flex;
    align-items: center;
    gap: 10pt;
    margin-bottom: 8pt;
}

.the-call-box .call-label {
    font-size: 6.5pt;
    font-weight: 700;
    color: #0E6E5C;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

.the-call-box .one-liner {
    font-size: 9.5pt;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.4;
    margin: 0;
}

/* ===== RATING BADGES ===== */
.badge {
    display: inline-block;
    font-size: 7.5pt;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    padding: 1.5pt 5pt;
    border: 1px solid currentColor;
    border-radius: 0;
    background: transparent;
}

.badge-strong-buy { color: #0E6E45; }
.badge-buy { color: #0E6E45; }
.badge-hold { color: #8A6410; }
.badge-sell { color: #9C3325; }
.badge-strong-sell { color: #9C3325; }
.badge-high { color: #9C3325; }
.badge-moderate { color: #8A6410; }
.badge-low { color: #0E6E45; }
.badge-medium { color: #8A6410; }

/* ===== SCORE DISPLAY ===== */
.score-display {
    display: flex;
    align-items: center;
    gap: 12pt;
    margin: 0.1in 0;
    page-break-inside: avoid;
}

.score-big {
    font-size: 20pt;
    font-weight: 750;
    line-height: 1;
}

.score-label {
    font-size: 14pt;
    color: var(--text-muted);
    font-weight: 400;
}

.score-band {
    font-size: 9pt;
    color: var(--text-muted);
    margin-top: 4pt;
}

.score-band .active {
    font-weight: 700;
    color: var(--text-primary);
    background: #f0fdf9;
    padding: 1pt 4pt;
    border-radius: 0;
}

.score-strong-buy { color: #0E6E45; }
.score-buy { color: #0E6E45; }
.score-hold { color: #1A2233; }
.score-sell { color: #9C3325; }
.score-strong-sell { color: #9C3325; }

/* ===== DIVERGENCE ALERT ===== */
.divergence-alert {
    background: #FFFFFF;
    border: 1px solid #D9DDE3;
    border-left: 3px solid #9C3325;
    padding: 8pt 12pt;
    margin: 0.1in 0;
}

.divergence-alert.moderate {
    background: #fffbeb;
    border-left-color: #F59E0B;
}

.divergence-alert .alert-title {
    font-size: 7.8pt;
    font-weight: 700;
    color: #991b1b;
    margin: 0 0 4pt 0;
}

.divergence-alert.moderate .alert-title {
    color: #92400e;
}

.divergence-alert p {
    font-size: 7.5pt;
    color: var(--text-secondary);
    margin: 3pt 0;
}

/* ===== ALL CLEAR BANNER ===== */
.all-clear {
    background: #FFFFFF;
    border: 1px solid #D9DDE3;
    border-left: 3px solid #0E6E45;
    padding: 8pt 12pt;
    margin: 0.1in 0;
}

.all-clear .alert-title {
    font-size: 7.8pt;
    font-weight: 700;
    color: #065f46;
    margin: 0 0 2pt 0;
}

.all-clear p {
    font-size: 7.5pt;
    color: var(--text-secondary);
    margin: 2pt 0;
}

/* ===== TWO COLUMN LAYOUT ===== */
.two-col {
    display: flex;
    gap: 16pt;
    margin: 0.1in 0;
    page-break-inside: avoid;
}

.two-col .col {
    flex: 1;
}

.two-col .col-header {
    font-size: 6.8pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8pt;
    margin: 0 0 4pt 0;
    padding-bottom: 2pt;
    border-bottom: 0.5pt solid #D9DDE3;
}

.two-col .col-working .col-header { color: #059669; border-bottom-color: #10B981; }
.two-col .col-concerning .col-header { color: #DC2626; border-bottom-color: #EF4444; }

.two-col ul {
    margin: 0;
    padding: 0 0 0 14pt;
}

.two-col li {
    font-size: 7.3pt;
    color: var(--text-secondary);
    margin: 4pt 0;
    line-height: 1.4;
}

/* ===== METRICS ROW ===== */
.metrics-row {
    border-top: 1px solid #1A2233;
    border-bottom: 1px solid #D9DDE3;
    display: flex;
    justify-content: space-between;
    background: #FFFFFF;
    padding: 7pt 2pt;
    margin: 0.1in 0;
    page-break-inside: avoid;
}

.metric-item {
    text-align: center;
}

.metric-item .metric-label {
    font-size: 8pt;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 0;
}

.metric-item .metric-value {
    font-size: 11.5pt;
    font-weight: 700;
    color: var(--text-primary);
    margin: 2pt 0 0 0;
}

/* ===== SECTION HEADERS ===== */
.section-header {
    font-size: 8.5pt;
    font-weight: 700;
    letter-spacing: 1.1pt;
    text-transform: uppercase;
    color: #1A2233;
    border-bottom: 0.75pt solid #1A2233;
    padding-bottom: 2pt;
    margin: 11pt 0 5pt 0;
    page-break-after: avoid;
}

.section-header::before {
    content: "";
    display: inline-block;
    width: 6pt;
    height: 6pt;
    background: #0E6E5C;
    margin-right: 5pt;
}

.section-header .hdr-note {
    font-size: 6.3pt;
    font-weight: 400;
    letter-spacing: 0.3pt;
    text-transform: none;
    color: #8A93A0;
}

.section-subheader {
    font-size: 7pt;
    font-weight: 700;
    letter-spacing: 0.8pt;
    text-transform: uppercase;
    color: #5D6570;
    margin: 8pt 0 3pt 0;
    page-break-after: avoid;
}

.doc-title {
    font-size: 13pt;
    font-weight: 800;
    letter-spacing: -0.2pt;
    color: #1A2233;
    border-top: 3pt solid #1A2233;
    padding-top: 8pt;
    margin: 0 0 6pt 0;
}

.doc-tag {
    font-size: 7pt;
    font-weight: 700;
    letter-spacing: 1pt;
    text-transform: uppercase;
    color: #8A6410;
    border: 0.75pt solid #8A6410;
    padding: 1pt 4pt;
    vertical-align: 3pt;
}

/* ===== DATA TABLES ===== */
.data-table {
    page-break-inside: avoid;
    width: 100%;
    border-collapse: collapse;
    margin: 4pt 0 6pt;
    font-size: 7pt;
}

.data-table th {
    background: #FFFFFF;
    color: #8A93A0;
    border-bottom: 0.75pt solid #1A2233;
    text-transform: uppercase;
    letter-spacing: 0.4pt;
    font-weight: 600;
    padding: 2.5pt 5pt 2.5pt 0;
    text-align: left;
    font-size: 6pt;
}

.data-table td {
    padding: 2.5pt 5pt 2.5pt 0;
    border-bottom: 0.5pt solid #E5E8EC;
    color: #384250;
    vertical-align: top;
}

.data-table .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
    color: #1A2233;
}
.data-table .strong { font-weight: 600; color: var(--text-primary); }

/* ===== SIGNAL BARS ===== */
.signal-row {
    display: flex;
    align-items: center;
    gap: 8pt;
    margin: 5pt 0;
    page-break-inside: avoid;
}

.signal-label {
    width: 70pt;
    font-size: 7pt;
    color: var(--text-secondary);
}

.signal-bar-bg {
    flex: 1;
    height: 6pt;
    background: #e2e8f0;
    border-radius: 0;
    overflow: hidden;
}

.signal-bar-fill {
    height: 100%;
    border-radius: 0;
    min-width: 2pt;
}

.signal-score {
    width: 28pt;
    text-align: right;
    font-size: 7pt;
    font-weight: 600;
}

.bar-strong { background-color: #10B981; }
.bar-moderate { background-color: #F59E0B; }
.bar-weak { background-color: #EF4444; }

/* ===== TRADE SETUP TABLE ===== */
.trade-table {
    width: 100%;
    border-collapse: collapse;
    margin: 4pt 0 6pt;
    font-size: 7pt;
    page-break-inside: avoid;
}

.trade-table th {
    padding: 2.5pt 5pt;
    font-weight: 700;
    font-size: 6.2pt;
    text-transform: uppercase;
    letter-spacing: 0.5pt;
}

.trade-table th.conservative { color: #0E6E5C; border-bottom: 0.75pt solid #0E6E5C; }
.trade-table th.aggressive { color: #8A6410; border-bottom: 0.75pt solid #8A6410; }
.trade-table th.label-col { color: #8A93A0; }

.trade-table td {
    padding: 2.5pt 5pt;
    border-bottom: 0.5pt solid #E5E8EC;
    text-align: center;
}

.trade-table td.label-col {
    text-align: left;
    font-weight: 500;
    color: var(--text-primary);
}

/* ===== CONVICTION BOX ===== */
.conviction-box {
    background: #FFFFFF;
    border: 0.5pt solid #D9DDE3;
    border-left: 2.5pt solid #0E6E5C;
    padding: 6pt 9pt;
    font-size: 7.5pt;
    margin: 0.08in 0;
    page-break-inside: avoid;
}

.conviction-box .conv-level {
    font-weight: 700;
    color: #0E6E5C;
}

/* ===== BEST SUITED FOR ===== */
.suited-box {
    background: #FFFFFF;
    border-top: 0.75pt solid #1A2233;
    border-bottom: 0.5pt solid #E5E8EC;
    padding: 6pt 0;
    margin: 0.08in 0;
    page-break-inside: avoid;
}

.suited-row {
    display: flex;
    gap: 20pt;
    margin: 4pt 0;
}

.suited-item .suited-label {
    font-size: 6.3pt;
    color: var(--text-muted);
    text-transform: uppercase;
}

.suited-item .suited-value {
    font-size: 7.8pt;
    font-weight: 600;
    color: var(--text-primary);
}

/* ===== TRIGGERS ===== */
.trigger-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 7pt;
    margin: 0.06in 0;
    page-break-inside: avoid;
}

.trigger-table th {
    padding: 4pt 8pt;
    font-weight: 600;
    text-align: left;
    font-size: 8.5pt;
}

.trigger-table th.upgrade { color: #0E6E5C; border-bottom: 0.75pt solid #0E6E5C; }
.trigger-table th.downgrade { color: #9C3325; border-bottom: 0.75pt solid #9C3325; }

.trigger-table td {
    padding: 3pt 8pt;
    border-bottom: 1px solid #e2e8f0;
    color: var(--text-secondary);
}

/* ===== FOOTER ===== */
.report-footer {
    margin-top: 0.3in;
    padding-top: 0.1in;
    border-top: 2px solid #0E6E5C;
    text-align: center;
    font-size: 8pt;
    color: var(--text-muted);
}

.report-footer .brand-footer {
    font-weight: 700;
    color: #0E6E5C;
}

/* ===== CATALYST TABLE ===== */
.catalyst-table {
    width: 100%;
    border-collapse: collapse;
    margin: 4pt 0 6pt;
    font-size: 7pt;
    page-break-inside: avoid;
}

.catalyst-table th {
    background: #FFFFFF;
    color: #8A93A0;
    border-bottom: 0.75pt solid #1A2233;
    text-transform: uppercase;
    letter-spacing: 0.4pt;
    font-weight: 600;
    padding: 2.5pt 5pt 2.5pt 0;
    text-align: left;
    font-size: 6pt;
}

.catalyst-table td {
    padding: 2.5pt 5pt 2.5pt 0;
    border-bottom: 0.5pt solid #E5E8EC;
    color: #384250;
    vertical-align: top;
}

/* ===== THESIS BLOCK ===== */
.thesis-block {
    background: #FFFFFF;
    border: 0.5pt solid #D9DDE3;
    border-left: 2.5pt solid #0E6E5C;
    padding: 6pt 9pt;
    margin: 4pt 0 6pt;
    font-size: 7.6pt;
    line-height: 1.5;
    color: #384250;
    page-break-inside: avoid;
}

/* ===== COMPETITIVE ADVANTAGE CATEGORY TABLE ===== */
.advantage-indicator {
    display: inline-block;
    width: 8pt;
    height: 8pt;
    border-radius: 50%;
    margin-right: 4pt;
}

.moat-strong, .advantage-strong { background: #10B981; }
.moat-moderate, .advantage-moderate { background: #F59E0B; }
.moat-weak, .advantage-weak { background: #EF4444; }

/* ===== PEER COMPARISON ===== */
.rank-badge {
    display: inline-block;
    background: #e2e8f0;
    color: var(--text-primary);
    font-weight: 700;
    font-size: 9pt;
    padding: 1pt 6pt;
    border-radius: 0;
}

/* ===== DISCLAIMER ===== */
.disclaimer {
    font-size: 7.5pt;
    color: #a0aec0;
    line-height: 1.4;
    margin-top: 0.2in;
    padding-top: 0.08in;
    border-top: 1px solid #e2e8f0;
}

/* ===== GENERAL UTILITIES ===== */
.text-success { color: #10B981; }
.text-warning { color: #F59E0B; }
.text-error { color: #EF4444; }
.text-muted { color: #718096; }
.font-bold { font-weight: 700; }
.font-mono { font-variant-numeric: tabular-nums; }
.text-right { text-align: right; }
.text-center { text-align: center; }
.mt-sm { margin-top: 0.06in; }
.mb-sm { margin-bottom: 0.06in; }

/* ===== THE VERDICT BOX ===== */
.verdict-box {
    background: #FFFFFF;
    border: 3px solid #0E6E5C;
    border-radius: 0;
    padding: 16pt 20pt;
    margin: 0.2in 0;
    page-break-inside: avoid;
    
}

.verdict-header {
    font-size: 10pt;
    font-weight: 700;
    color: #1A2233;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin: 0 0 6pt 0;
    border-bottom: 1px solid #D9DDE3;
    padding-bottom: 4pt;
}

.verdict-summary {
    font-size: 10.5pt;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.5;
    margin: 6pt 0;
}

.verdict-detail {
    font-size: 10pt;
    color: var(--text-secondary);
    line-height: 1.5;
    margin: 4pt 0 0 0;
}

/* ===== ACTION SUMMARY (Current Holders vs New Buyers) ===== */
.action-summary {
    display: flex;
    gap: 14pt;
    border-top: 0.75pt solid #1A2233;
    border-bottom: 0.5pt solid #E5E8EC;
    padding: 6pt 0;
    margin: 6pt 0;
    page-break-inside: avoid;
}

.action-col {
    flex: 1;
}

.action-header {
    font-size: 6.5pt;
    font-weight: 700;
    color: #0E6E5C;
    text-transform: uppercase;
    letter-spacing: 0.8pt;
    margin: 0 0 3pt 0;
}

.action-text {
    font-size: 7.5pt;
    color: var(--text-secondary);
    line-height: 1.4;
    margin: 4pt 0 0 0;
}

/* ===== COMPACT LISTS ===== */
.compact-list {
    margin: 0;
    padding: 0 0 0 14pt;
}

.compact-list li {
    font-size: 7.3pt;
    color: var(--text-secondary);
    margin: 2.5pt 0;
    line-height: 1.4;
}

/* ===== NOTE FLOW — two-column inner pages ===== */
.running-logo {
    position: running(pagelogo);
    font-weight: 700;
    font-size: 9pt;
    color: #0E6E5C;
}
.running-logo img { height: 11pt; width: auto; }

.note-flow {
    column-count: 2;
    column-gap: 20pt;
    column-fill: auto;
    font-size: 7.6pt;
    line-height: 1.5;
    margin-top: 4pt;
}
.note-flow > :first-child { margin-top: 0; }
.note-flow .section-header:first-child { margin-top: 0; }
/* stacked, not nested-halved, inside a column */
.note-flow .two-col { display: block; }
.note-flow .two-col .col { margin-bottom: 6pt; }
.note-flow .action-summary { display: block; }
.note-flow .action-col { margin-bottom: 5pt; }
.note-flow .suited-row { display: block; }
.note-flow .suited-item { margin: 3pt 0; }
.note-flow ul, .note-flow ol { padding-left: 10pt; }
.note-flow .report-footer { page-break-inside: avoid; }
.note-flow .divergence-alert,
.note-flow .all-clear { padding: 5pt 8pt; }

/* ===== PAGE ONE — the research-note front page ===== */
/* Palette shared with note_charts.py: ink #1A2233, accent #0E6E5C,
   muted #5D6570, faint #8A93A0, hairline #D9DDE3. */

.masthead {
    border-top: 3pt solid #1A2233;
    padding-top: 8pt;
    margin-bottom: 2pt;
}
.masthead td { vertical-align: top; }
.masthead .brand-cell { string-set: ticker-name attr(data-ticker); }
.masthead .brand-logo { height: 16pt; width: auto; display: block; }
.masthead .brand-word {
    font-size: 15pt; font-weight: 800; letter-spacing: -0.3pt;
    color: #0E6E5C; margin: 0;
}
.masthead .brand-sub {
    font-size: 6.5pt; letter-spacing: 2pt; color: #8A93A0;
    text-transform: uppercase; margin: 2pt 0 0;
}
.masthead .gen {
    text-align: right; font-size: 6.5pt; color: #8A93A0; margin: 0; line-height: 1.5;
}
.masthead .gen b { display: block; font-size: 8pt; color: #1A2233; }

.companyrow {
    width: 100%; border-collapse: collapse;
    border-bottom: 0.75pt solid #D9DDE3; margin-bottom: 6pt;
}
.companyrow td { vertical-align: bottom; padding: 4pt 0 6pt; }
.companyrow h2 { font-size: 17pt; margin: 0; letter-spacing: -0.3pt; color: #1A2233; }
.companyrow .tick { text-align: right; font-size: 7.5pt; color: #5D6570; padding-right: 8pt; }
.companyrow .tick b { font-size: 10pt; color: #1A2233; display: block; }
.companyrow .chip-cell { width: 72pt; text-align: right; }
.chip {
    display: inline-block; background: #1A2233; color: #fff;
    font-weight: 800; font-size: 11pt; padding: 4pt 8pt; letter-spacing: 0.5pt;
    text-align: center;
}
.chip small {
    display: block; font-weight: 400; font-size: 5.5pt;
    letter-spacing: 1pt; opacity: 0.75;
}

/* two-column shell: table layout for deterministic WeasyPrint rendering */
table.cols { width: 100%; border-collapse: collapse; table-layout: fixed; }
table.cols > tr > td, table.cols > tbody > tr > td { vertical-align: top; }
td.main-col { padding-right: 12pt; }
td.rail-col {
    width: 170pt; border-left: 0.75pt solid #D9DDE3;
    padding-left: 10pt; font-size: 7pt;
}

/* section bar with accent tick */
.bar {
    border-bottom: 0.75pt solid #1A2233;
    padding-bottom: 1.5pt; margin: 8pt 0 4pt;
}
.bar b {
    font-size: 7.5pt; letter-spacing: 1pt; text-transform: uppercase; color: #1A2233;
}
.bar b::before {
    content: ""; display: inline-block; width: 6pt; height: 6pt;
    background: #0E6E5C; margin-right: 5pt;
}
.bar span { float: right; font-size: 6pt; color: #8A93A0; padding-top: 1.5pt; }

/* rating matrix */
table.matrix { border-collapse: collapse; font-size: 6.5pt; }
table.matrix th {
    font-weight: 600; color: #8A93A0; padding: 2pt 4pt;
    text-transform: uppercase; letter-spacing: 0.4pt; font-size: 5.7pt;
}
table.matrix td {
    border: 0.5pt solid #D9DDE3; padding: 4pt 6pt; text-align: center;
    color: #8A93A0; min-width: 46pt;
}
table.matrix td.on {
    background: #E3EFEB; border: 1.2pt solid #0E6E5C;
    color: #1A2233; font-weight: 700;
}
table.matrixwrap { width: 100%; border-collapse: collapse; }
table.matrixwrap td { vertical-align: top; }
.axisnote { font-size: 7.5pt; padding-left: 10pt; color: #1A2233; line-height: 1.45; }
.axisnote .big { font-size: 9.5pt; font-weight: 700; margin: 0 0 2pt; }
.axisnote .delta { color: #8A93A0; font-size: 6.7pt; margin-top: 3pt; }

/* page-one verdict (tighter than the inner-page verdict-box) */
.verdict {
    border: 0.5pt solid #D9DDE3; border-left: 2.5pt solid #0E6E5C;
    padding: 6pt 8pt; margin-top: 6pt; font-size: 7.7pt; line-height: 1.45;
}
.verdict b { font-size: 8.2pt; }

/* charts */
.chartsec { page-break-inside: avoid; }
.chart { margin: 1pt 0 0; }
.chart svg { width: 100%; height: auto; display: block; }
.chart-caption { font-size: 6.6pt; color: #5D6570; margin: 2pt 0 0; line-height: 1.4; }
table.duo { width: 100%; border-collapse: collapse; }
table.duo td { vertical-align: top; width: 50%; }
table.duo td + td { padding-left: 10pt; }
.duo-cap {
    font-size: 6.4pt; color: #5D6570; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.5pt; margin: 0 0 1pt;
}

/* falsifier strip */
table.falsifier { width: 100%; border-collapse: collapse; font-size: 7pt; }
table.falsifier td { vertical-align: top; width: 50%; padding-right: 8pt; line-height: 1.4; }
table.falsifier td + td {
    border-left: 0.5pt solid #D9DDE3; padding-left: 8pt; padding-right: 0;
}
table.falsifier .trig-up { color: #0E6E5C; font-size: 6.2pt; letter-spacing: 0.6pt; font-weight: 700; }
table.falsifier .trig-down { color: #9C3325; font-size: 6.2pt; letter-spacing: 0.6pt; font-weight: 700; }

/* rail */
.rail-col .bar { margin: 9pt 0 4pt; }
.rail-col .bar:first-child { margin-top: 0; }
.rail-col p { margin: 0 0 3pt; line-height: 1.45; color: #1A2233; }
table.kv { width: 100%; border-collapse: collapse; font-size: 7pt; }
table.kv td { padding: 2pt 0; border-bottom: 0.5pt solid #D9DDE3; color: #5D6570; }
table.kv td:last-child {
    text-align: right; font-weight: 600; color: #1A2233;
    font-variant-numeric: tabular-nums;
}
table.cmp { width: 100%; border-collapse: collapse; font-size: 6.8pt; }
table.cmp th {
    text-align: right; font-size: 5.8pt; color: #8A93A0; text-transform: uppercase;
    letter-spacing: 0.4pt; padding: 2pt 0; border-bottom: 0.75pt solid #1A2233;
}
table.cmp th:first-child { text-align: left; }
table.cmp td {
    padding: 2pt 0; border-bottom: 0.5pt solid #D9DDE3;
    text-align: right; font-variant-numeric: tabular-nums;
}
table.cmp td:first-child { text-align: left; color: #5D6570; }
table.cmp td.us { font-weight: 700; color: #1A2233; }
tr.grp td {
    padding-top: 5pt; font-weight: 700; color: #1A2233;
    font-size: 6pt; text-transform: uppercase; letter-spacing: 0.5pt;
    border-bottom: none; text-align: left;
}

.pfoot {
    border-top: 0.5pt solid #D9DDE3; margin-top: 10pt; padding-top: 4pt;
    font-size: 5.8pt; color: #8A93A0;
}
"""
