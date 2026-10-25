// Plain-language explanations for the words a new preparer meets on day one. Shown on hover (dotted underline
// when glossary hints are on) and listed in Help.
export const GLOSSARY: Record<string, string> = {
  AGI: 'Adjusted gross income: total income minus adjustments such as the self-employed health insurance or SEP deduction. Many limits and credits depend on it.',
  'Taxable income': 'AGI minus the standard or itemized deduction and the QBI deduction. The tax rate tables apply to this.',
  'Total tax': 'Income tax plus other taxes (self-employment tax, net investment income tax, additional Medicare tax), minus credits.',
  'Balance due': 'Total tax minus what was already paid (withholding, estimated and extension payments). Negative means a refund.',
  'Schedule C': "The business schedule: Erik's design studio. Gross receipts minus expenses = profit, which also drives self-employment tax.",
  'Schedule E': 'Rental and pass-through income. Property A is the Sacramento rental, property B the Austin condo.',
  '1099-K': 'A form from a card processor (here Paywell) reporting card payments. If the books already recorded those deposits, adding the 1099-K counts them twice.',
  Basis: 'What an asset cost, for working out the gain when it is sold. RSU shares have a basis equal to the value already taxed as wages.',
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
  SALT: 'State and local taxes (income and property tax). The federal deduction for them is capped.',
  QBI: 'Qualified business income deduction: up to 20% of business profit, subject to limits.',
  '540NR': 'California return for part-year residents. The family moved to Texas on 7/14/2025, so only California-source income is taxed by California.',
  'California-source': 'Income California can tax: everything while a resident, plus California income after moving (e.g. the Sacramento rental).',
  'Estimated payments': 'Tax paid during the year by the taxpayer. The amounts on the return must match the IRS and FTB records.',
  'Due diligence': 'Form 8867: the checks a preparer must document before claiming the child tax credit and similar credits.',
  Reconciliation: 'Two figures that should agree, checked against each other - e.g. a broker summary against the sum of its lots.',
  'Wash sale': 'A loss disallowed because the same security was bought back within 30 days; it is added to the new shares\' basis.',
}

export const GLOSSARY_TERMS = Object.keys(GLOSSARY).sort((a, b) => a.localeCompare(b))
