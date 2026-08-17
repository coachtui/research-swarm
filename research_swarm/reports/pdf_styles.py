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
        content: "DVRG";
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        font-size: 9pt;
        font-weight: 700;
        color: #0E6E5C;
        padding-top: 0.15in;
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
    background: #f0fdf9;
    border: 2px solid #0E6E5C;
    border-radius: 0;
    padding: 14pt 16pt;
    margin: 0.15in 0;
    page-break-inside: avoid;
}

.the-call-box .call-header {
    display: flex;
    align-items: center;
    gap: 10pt;
    margin-bottom: 8pt;
}

.the-call-box .call-label {
    font-size: 9pt;
    font-weight: 700;
    color: #0E6E5C;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

.the-call-box .one-liner {
    font-size: 13pt;
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
    font-size: 10pt;
    font-weight: 700;
    color: #991b1b;
    margin: 0 0 4pt 0;
}

.divergence-alert.moderate .alert-title {
    color: #92400e;
}

.divergence-alert p {
    font-size: 9.5pt;
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
    font-size: 10pt;
    font-weight: 700;
    color: #065f46;
    margin: 0 0 2pt 0;
}

.all-clear p {
    font-size: 9.5pt;
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
    font-size: 10pt;
    font-weight: 700;
    margin: 0 0 6pt 0;
    padding-bottom: 4pt;
    border-bottom: 2px solid #e2e8f0;
}

.two-col .col-working .col-header { color: #059669; border-bottom-color: #10B981; }
.two-col .col-concerning .col-header { color: #DC2626; border-bottom-color: #EF4444; }

.two-col ul {
    margin: 0;
    padding: 0 0 0 14pt;
}

.two-col li {
    font-size: 9.5pt;
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
    font-size: 14pt;
    font-weight: 700;
    color: var(--text-primary);
    border-bottom: 2px solid #0E6E5C;
    padding-bottom: 4pt;
    margin: 0.2in 0 0.1in 0;
    page-break-after: avoid;
}

.section-subheader {
    page-break-after: avoid;
    font-size: 10pt;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0.12in 0 0.06in 0;
    page-break-after: avoid;
}

/* ===== DATA TABLES ===== */
.data-table {
    page-break-inside: avoid;
    width: 100%;
    border-collapse: collapse;
    margin: 0.08in 0;
    font-size: 9.5pt;
    page-break-inside: avoid;
}

.data-table th {
    background: #FFFFFF;
    color: #1A2233;
    border-bottom: 1.5px solid #1A2233;
    text-transform: uppercase;
    letter-spacing: 0.5px;
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
    color: var(--text-secondary);
}

.data-table tr:nth-child(even) td {
    background: #f7fafc;
}

.data-table .num { text-align: right; font-family: "Courier New", monospace; }
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
    width: 120pt;
    font-size: 9pt;
    color: var(--text-secondary);
}

.signal-bar-bg {
    flex: 1;
    height: 10pt;
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
    width: 35pt;
    text-align: right;
    font-size: 9pt;
    font-weight: 600;
}

.bar-strong { background-color: #10B981; }
.bar-moderate { background-color: #F59E0B; }
.bar-weak { background-color: #EF4444; }

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
.trade-table th.aggressive { background: #fef3c7; color: #92400e; }
.trade-table th.label-col { background: #f1f5f9; color: var(--text-secondary); }

.trade-table td {
    padding: 5pt 10pt;
    border-bottom: 1px solid #e2e8f0;
    text-align: center;
}

.trade-table td.label-col {
    text-align: left;
    font-weight: 500;
    color: var(--text-primary);
}

/* ===== CONVICTION BOX ===== */
.conviction-box {
    background: #f0fdf9;
    border: 1px solid #99f6e4;
    border-radius: 0;
    padding: 8pt 14pt;
    margin: 0.08in 0;
    page-break-inside: avoid;
}

.conviction-box .conv-level {
    font-weight: 700;
    color: #0E6E5C;
}

/* ===== BEST SUITED FOR ===== */
.suited-box {
    background: #f7fafc;
    border-radius: 0;
    padding: 10pt 14pt;
    margin: 0.08in 0;
    page-break-inside: avoid;
}

.suited-row {
    display: flex;
    gap: 20pt;
    margin: 4pt 0;
}

.suited-item .suited-label {
    font-size: 8pt;
    color: var(--text-muted);
    text-transform: uppercase;
}

.suited-item .suited-value {
    font-size: 10pt;
    font-weight: 600;
    color: var(--text-primary);
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

.trigger-table th.upgrade { background: #d1fae5; color: #065f46; }
.trigger-table th.downgrade { background: #fee2e2; color: #991b1b; }

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
    color: var(--text-secondary);
}

/* ===== THESIS BLOCK ===== */
.thesis-block {
    background: #f7fafc;
    border-left: 3px solid #0E6E5C;
    padding: 10pt 14pt;
    margin: 0.1in 0;
    font-size: 10pt;
    line-height: 1.6;
    color: var(--text-secondary);
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
.font-mono { font-family: "Courier New", monospace; }
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
    background: #f7fafc;
    border-radius: 0;
    padding: 12pt 14pt;
    margin: 0.12in 0;
    page-break-inside: avoid;
}

.action-col {
    flex: 1;
}

.action-header {
    font-size: 9pt;
    font-weight: 700;
    color: #0E6E5C;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 0 0 4pt 0;
    padding-bottom: 3pt;
    border-bottom: 2px solid #0E6E5C;
}

.action-text {
    font-size: 9pt;
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
    font-size: 8.5pt;
    color: var(--text-secondary);
    margin: 3pt 0;
    line-height: 1.35;
}
"""
