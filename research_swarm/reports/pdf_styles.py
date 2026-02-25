"""DVRG-branded CSS styles for xhtml2pdf PDF generation.

CSS variables expanded to literal values; WeasyPrint-only features removed
(running headers, string-set, flex, linear-gradient, box-shadow).
"""

PDF_CSS = """
/* ===== DVRG PDF Report Styles ===== */

@page {
    size: letter;
    margin: 0.75in 0.75in 0.9in 0.75in;
}

body {
    font-family: Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.55;
    color: #1a1a2e;
    margin: 0;
    padding: 0;
}

/* ===== PAGE BREAKS ===== */
.page-break { page-break-before: always; }
.avoid-break { page-break-inside: avoid; }

/* ===== COVER / PAGE 1 ===== */
.cover-header {
    border-top: 4px solid #00D9B5;
    padding-top: 0.3in;
    margin-bottom: 0.25in;
}

.cover-header .brand {
    font-size: 28pt;
    font-weight: 800;
    color: #00D9B5;
    margin: 0;
}

.cover-header .subtitle {
    font-size: 10pt;
    color: #718096;
    margin: 2pt 0 0 0;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}

.cover-meta {
    margin: 0.15in 0;
    padding: 8pt 0;
    border-bottom: 1px solid #e2e8f0;
}

.cover-meta .ticker {
    font-size: 22pt;
    font-weight: 700;
    color: #1a1a2e;
}

.cover-meta .date {
    font-size: 10pt;
    color: #718096;
}

/* ===== THE CALL BOX ===== */
.the-call-box {
    background: #f0fdf9;
    border: 2px solid #00D9B5;
    padding: 14pt 16pt;
    margin: 0.15in 0;
    page-break-inside: avoid;
}

.the-call-box .call-label {
    font-size: 9pt;
    font-weight: 700;
    color: #00D9B5;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

.the-call-box .one-liner {
    font-size: 13pt;
    font-weight: 600;
    color: #1a1a2e;
    line-height: 1.4;
    margin: 0;
}

/* ===== RATING BADGES ===== */
.badge {
    display: inline-block;
    padding: 3pt 10pt;
    font-size: 9pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.badge-strong-buy { background: #d1fae5; color: #065f46; }
.badge-buy        { background: #d1fae5; color: #065f46; }
.badge-hold       { background: #fef3c7; color: #92400e; }
.badge-sell       { background: #fee2e2; color: #991b1b; }
.badge-strong-sell{ background: #fee2e2; color: #991b1b; }
.badge-high       { background: #fee2e2; color: #991b1b; }
.badge-moderate   { background: #fef3c7; color: #92400e; }
.badge-low        { background: #d1fae5; color: #065f46; }

/* ===== SCORE DISPLAY ===== */
.score-display {
    margin: 0.1in 0;
    page-break-inside: avoid;
}

.score-big {
    font-size: 36pt;
    font-weight: 800;
    line-height: 1;
}

.score-label {
    font-size: 14pt;
    color: #718096;
    font-weight: 400;
}

.score-band {
    font-size: 9pt;
    color: #718096;
    margin-top: 4pt;
}

.score-band .active {
    font-weight: 700;
    color: #1a1a2e;
    background: #f0fdf9;
    padding: 1pt 4pt;
}

.score-strong-buy  { color: #059669; }
.score-buy         { color: #10B981; }
.score-hold        { color: #F59E0B; }
.score-sell        { color: #EF4444; }
.score-strong-sell { color: #DC2626; }

/* ===== DIVERGENCE ALERT ===== */
.divergence-alert {
    background: #fef2f2;
    border-left: 4px solid #EF4444;
    padding: 10pt 14pt;
    margin: 0.12in 0;
    page-break-inside: avoid;
}

.divergence-alert.moderate {
    background: #fffbeb;
    border-left-color: #F59E0B;
}

.divergence-alert .alert-title {
    font-size: 10pt;
    font-weight: 700;
    color: #991b1b;
    margin: 0 0 4pt 0;
}

.divergence-alert.moderate .alert-title { color: #92400e; }

.divergence-alert p {
    font-size: 9.5pt;
    color: #4a5568;
    margin: 3pt 0;
}

/* ===== ALL CLEAR BANNER ===== */
.all-clear {
    background: #f0fdf4;
    border-left: 4px solid #10B981;
    padding: 8pt 14pt;
    margin: 0.12in 0;
    page-break-inside: avoid;
}

.all-clear .alert-title {
    font-size: 10pt;
    font-weight: 700;
    color: #065f46;
    margin: 0 0 2pt 0;
}

.all-clear p {
    font-size: 9.5pt;
    color: #4a5568;
    margin: 2pt 0;
}

/* ===== TWO COLUMN LAYOUT (inline-block fallback) ===== */
.two-col {
    margin: 0.1in 0;
    page-break-inside: avoid;
}

.two-col .col {
    display: inline-block;
    width: 47%;
    vertical-align: top;
    padding-right: 2%;
}

.two-col .col-header {
    font-size: 10pt;
    font-weight: 700;
    margin: 0 0 6pt 0;
    padding-bottom: 4pt;
    border-bottom: 2px solid #e2e8f0;
}

.two-col .col-working   .col-header { color: #059669; border-bottom-color: #10B981; }
.two-col .col-concerning .col-header { color: #DC2626; border-bottom-color: #EF4444; }

.two-col ul { margin: 0; padding: 0 0 0 14pt; }

.two-col li {
    font-size: 9.5pt;
    color: #4a5568;
    margin: 4pt 0;
    line-height: 1.4;
}

/* ===== METRICS ROW ===== */
.metrics-row {
    background: #f7fafc;
    padding: 8pt 14pt;
    margin: 0.1in 0;
    page-break-inside: avoid;
}

.metric-item {
    display: inline-block;
    text-align: center;
    padding: 0 12pt;
}

.metric-item .metric-label {
    font-size: 8pt;
    color: #718096;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 0;
}

.metric-item .metric-value {
    font-size: 14pt;
    font-weight: 700;
    color: #1a1a2e;
    margin: 2pt 0 0 0;
}

/* ===== SECTION HEADERS ===== */
.section-header {
    font-size: 14pt;
    font-weight: 700;
    color: #1a1a2e;
    border-bottom: 2px solid #00D9B5;
    padding-bottom: 4pt;
    margin: 0.2in 0 0.1in 0;
    page-break-after: avoid;
}

.section-subheader {
    font-size: 11pt;
    font-weight: 600;
    color: #1a1a2e;
    margin: 0.12in 0 0.06in 0;
    page-break-after: avoid;
}

/* ===== DATA TABLES ===== */
.data-table {
    width: 100%;
    border-collapse: collapse;
    margin: 0.08in 0;
    font-size: 9.5pt;
    page-break-inside: avoid;
}

.data-table th {
    background: #1a1a2e;
    color: white;
    font-weight: 600;
    padding: 6pt 10pt;
    text-align: left;
    font-size: 8.5pt;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.data-table td {
    padding: 5pt 10pt;
    border-bottom: 1px solid #e2e8f0;
    color: #4a5568;
}

.data-table .num    { text-align: right; font-family: "Courier New", monospace; }
.data-table .strong { font-weight: 600; color: #1a1a2e; }

/* ===== SIGNAL BARS ===== */
.signal-row {
    margin: 5pt 0;
    page-break-inside: avoid;
}

.signal-label {
    font-size: 9pt;
    color: #4a5568;
}

.signal-bar-bg {
    height: 10pt;
    background: #e2e8f0;
}

.signal-bar-fill {
    height: 100%;
    min-width: 2pt;
}

.signal-score {
    font-size: 9pt;
    font-weight: 600;
}

.bar-strong   { background-color: #10B981; }
.bar-moderate { background-color: #F59E0B; }
.bar-weak     { background-color: #EF4444; }

/* ===== TRADE SETUP TABLE ===== */
.trade-table {
    width: 100%;
    border-collapse: collapse;
    margin: 0.08in 0;
    font-size: 9.5pt;
    page-break-inside: avoid;
}

.trade-table th {
    padding: 6pt 10pt;
    font-weight: 600;
    font-size: 9pt;
    text-transform: uppercase;
    letter-spacing: 0.3px;
}

.trade-table th.conservative { background: #d1fae5; color: #065f46; }
.trade-table th.aggressive   { background: #fef3c7; color: #92400e; }
.trade-table th.label-col    { background: #f1f5f9; color: #4a5568; }

.trade-table td {
    padding: 5pt 10pt;
    border-bottom: 1px solid #e2e8f0;
    text-align: center;
}

.trade-table td.label-col {
    text-align: left;
    font-weight: 500;
    color: #1a1a2e;
}

/* ===== CONVICTION BOX ===== */
.conviction-box {
    background: #f0fdf9;
    border: 1px solid #99f6e4;
    padding: 8pt 14pt;
    margin: 0.08in 0;
    page-break-inside: avoid;
}

.conviction-box .conv-level {
    font-weight: 700;
    color: #00D9B5;
}

/* ===== BEST SUITED FOR ===== */
.suited-box {
    background: #f7fafc;
    padding: 10pt 14pt;
    margin: 0.08in 0;
    page-break-inside: avoid;
}

.suited-row { margin: 4pt 0; }

.suited-item .suited-label {
    font-size: 8pt;
    color: #718096;
    text-transform: uppercase;
}

.suited-item .suited-value {
    font-size: 10pt;
    font-weight: 600;
    color: #1a1a2e;
}

/* ===== TRIGGERS ===== */
.trigger-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 9pt;
    margin: 0.06in 0;
    page-break-inside: avoid;
}

.trigger-table th {
    padding: 4pt 8pt;
    font-weight: 600;
    text-align: left;
    font-size: 8.5pt;
}

.trigger-table th.upgrade   { background: #d1fae5; color: #065f46; }
.trigger-table th.downgrade { background: #fee2e2; color: #991b1b; }

.trigger-table td {
    padding: 3pt 8pt;
    border-bottom: 1px solid #e2e8f0;
    color: #4a5568;
}

/* ===== FOOTER ===== */
.report-footer {
    margin-top: 0.3in;
    padding-top: 0.1in;
    border-top: 2px solid #00D9B5;
    text-align: center;
    font-size: 8pt;
    color: #718096;
}

.report-footer .brand-footer {
    font-weight: 700;
    color: #00D9B5;
}

/* ===== CATALYST TABLE ===== */
.catalyst-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 9pt;
    margin: 0.06in 0;
    page-break-inside: avoid;
}

.catalyst-table th {
    background: #1a1a2e;
    color: white;
    padding: 4pt 8pt;
    font-size: 8pt;
    text-transform: uppercase;
}

.catalyst-table td {
    padding: 4pt 8pt;
    border-bottom: 1px solid #e2e8f0;
    color: #4a5568;
}

/* ===== THESIS BLOCK ===== */
.thesis-block {
    background: #f7fafc;
    border-left: 3px solid #00D9B5;
    padding: 10pt 14pt;
    margin: 0.1in 0;
    font-size: 10pt;
    line-height: 1.6;
    color: #4a5568;
    page-break-inside: avoid;
}

/* ===== COMPETITIVE ADVANTAGE ===== */
.advantage-indicator {
    display: inline-block;
    width: 8pt;
    height: 8pt;
    margin-right: 4pt;
}

.moat-strong,    .advantage-strong   { background: #10B981; }
.moat-moderate,  .advantage-moderate { background: #F59E0B; }
.moat-weak,      .advantage-weak     { background: #EF4444; }

/* ===== PEER COMPARISON ===== */
.rank-badge {
    display: inline-block;
    background: #e2e8f0;
    color: #1a1a2e;
    font-weight: 700;
    font-size: 9pt;
    padding: 1pt 6pt;
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
.text-error   { color: #EF4444; }
.text-muted   { color: #718096; }
.font-bold    { font-weight: 700; }
.font-mono    { font-family: "Courier New", monospace; }
.text-right   { text-align: right; }
.text-center  { text-align: center; }
.mt-sm        { margin-top: 0.06in; }
.mb-sm        { margin-bottom: 0.06in; }

/* ===== THE VERDICT BOX ===== */
.verdict-box {
    background: #f0fdf9;
    border: 3px solid #00D9B5;
    padding: 16pt 20pt;
    margin: 0.2in 0;
    page-break-inside: avoid;
}

.verdict-header {
    font-size: 13pt;
    font-weight: 700;
    color: #00D9B5;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin: 0 0 8pt 0;
    border-bottom: 2px solid #00D9B5;
    padding-bottom: 4pt;
}

.verdict-summary {
    font-size: 12pt;
    font-weight: 600;
    color: #1a1a2e;
    line-height: 1.5;
    margin: 6pt 0;
}

.verdict-detail {
    font-size: 10pt;
    color: #4a5568;
    line-height: 1.5;
    margin: 4pt 0 0 0;
}

/* ===== ACTION SUMMARY ===== */
.action-summary {
    background: #f7fafc;
    padding: 12pt 14pt;
    margin: 0.12in 0;
    page-break-inside: avoid;
}

.action-col {
    display: inline-block;
    width: 47%;
    vertical-align: top;
    padding-right: 2%;
}

.action-header {
    font-size: 9pt;
    font-weight: 700;
    color: #00D9B5;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 0 0 4pt 0;
    padding-bottom: 3pt;
    border-bottom: 2px solid #00D9B5;
}

.action-text {
    font-size: 9pt;
    color: #4a5568;
    line-height: 1.4;
    margin: 4pt 0 0 0;
}

/* ===== COMPACT LISTS ===== */
.compact-list {
    margin: 0;
    padding: 0 0 0 14pt;
}

.compact-list li {
    font-size: 8.5pt;
    color: #4a5568;
    margin: 3pt 0;
    line-height: 1.35;
}
"""
