// Plain-language explanations for the words a new preparer meets on day one. Shown on hover (dotted underline
// when glossary hints are on) and listed in Help.
export const GLOSSARY: Record<string, string> = {
  AGI: 'Adjusted gross income: total income minus the adjustments to income on Schedule 1, Part II (e.g. self-employed health insurance, the SEP contribution, half of self-employment tax). Many limits and phase-outs depend on it.',
  'Taxable income': 'AGI minus the standard or itemized deduction and the QBI deduction. Tax is computed on it from the rate schedules, or the qualified dividends and capital gain worksheet when there are long-term gains.',
  'Total tax': 'Income tax less nonrefundable credits, plus the other taxes on Schedule 2 (self-employment tax, net investment income tax, Additional Medicare Tax). Refundable credits count as payments.',
  'Balance due': 'Total tax minus payments: withholding, estimated and extension payments, and refundable credits. Negative means an overpayment (refund).',
  'Schedule C': "The business schedule: Erik's design studio. Gross receipts minus expenses = profit, which also drives self-employment tax.",
  'Schedule E': 'Supplemental income: rental real estate (Part I) and partnerships and S corporations (Part II). Property A is the Sacramento rental, property B the Austin condo.',
  '1099-K': 'A form from a card processor (here Paywell) reporting card payments. If the books already recorded those deposits, adding the 1099-K counts them twice.',
  Basis: 'What an asset cost, adjusted over time, for working out the gain or loss when it is sold. RSU shares have a basis equal to their fair market value at vesting, which was already taxed as wages.',
  RSU: 'Restricted stock units: shares an employer gives as pay. Their value is taxed as wages when they vest; the broker form often shows no basis.',
  Carryover: 'An amount that moves from last year\'s return to this one - unused losses, credits or basis.',
  'Prior-year variance': 'A line that moved more than the firm threshold (10% and 1,000) since last year. Each one needs an explanation or a correction.',
  Engine: 'The tax software that computed the return from the documents. We cannot rerun it; we check it and record changes on top.',
  Adjusted: 'A number someone changed by hand, with a reason. The engine value is kept and shown crossed out.',
  Propagated: 'A number that moved because a number it is built from was adjusted (sums and carries follow automatically).',
  'Needs recompute': 'A number computed by a formula (e.g. tax from the rate tables) that may be out of date after an adjustment. The real system recomputes it.',
  Estimated: 'Tax effect worked out as change × the rate the packet gives for that kind of income. A direction, not an exact number.',
  'Sign-off': 'A reviewer or partner confirming what they checked. It covers the number and everything it is built from.',
  Reopened: 'A sign-off that no longer holds because something it covered changed after it was given. Sign again after reviewing what changed.',
  'Review note': 'A comment from a reviewer. A blocking note stops filing until the reviewer resolves it.',
  Decision: 'A recorded judgment (an explanation, an election, due diligence) with the authority relied on. It settles an issue that cannot be fixed by changing a number.',
  SALT: 'State and local taxes: income (or sales) tax plus real estate and personal property tax. The itemized deduction is capped - 40,000 for 2025, reduced when modified AGI is over 500,000.',
  QBI: 'Qualified business income deduction (section 199A): generally 20% of qualified business income, limited by taxable income and, above the threshold, by wages and property or for a specified service business.',
  '540NR': 'California return for nonresidents and part-year residents. Tax is computed on all income as if a resident, then prorated by the California share: income while a resident (to 7/14/2025, the move to Texas) plus California-source income after.',
  'California-source': 'Income California can tax: all income while a resident, plus income from California sources while a nonresident (e.g. the Sacramento rental, wages for work done in California).',
  'Estimated payments': 'Tax paid during the year by the taxpayer. The amounts on the return must match the IRS and FTB records.',
  'Due diligence': 'Form 8867: the knowledge, record-keeping and documentation requirements a paid preparer must meet when claiming the EITC, CTC/ACTC/ODC, AOTC or head of household status. Failing them carries a penalty per credit (IRC 6695(g)).',
  Reconciliation: 'Two figures that should agree, checked against each other - e.g. a broker summary against the sum of its lots.',
  'Wash sale': 'A loss disallowed because substantially identical securities were bought within 30 days before or after the sale; the loss is added to the basis of the replacement shares.',
}

export const GLOSSARY_TERMS = Object.keys(GLOSSARY).sort((a, b) => a.localeCompare(b))
