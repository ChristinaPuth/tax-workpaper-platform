const money = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })

export function fmtValue(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'number') return money.format(v)
  if (typeof v === 'boolean') return v ? 'Yes' : 'No'
  return String(v)
}

export function fmtEffect(v: number | null | undefined): string {
  if (!v) return '—'
  return `${v > 0 ? '+' : '−'}${money.format(Math.abs(Math.round(v)))}`
}

export function fmtDate(iso: string): string {
  const d = new Date(iso)
  return isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export function fmtTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

// Friendly names for the forms the engine emits, in the order a reviewer reads a return.
export const FORMS: [string, string][] = [
  ['F1040', 'Form 1040'],
  ['Sch1', 'Schedule 1 — Additional income'],
  ['Sch2', 'Schedule 2 — Additional taxes'],
  ['Sch3', 'Schedule 3 — Credits & payments'],
  ['SchA', 'Schedule A — Itemized deductions'],
  ['F8283', 'Form 8283 — Noncash gifts'],
  ['SchB', 'Schedule B — Interest & dividends'],
  ['SchC', 'Schedule C — Business'],
  ['F4562-C', 'Form 4562 — Business depreciation'],
  ['SchSE', 'Schedule SE — Self-employment tax'],
  ['SchD', 'Schedule D — Capital gains'],
  ['F8949', 'Form 8949 — Sales detail'],
  ['F4797', 'Form 4797 — Business property'],
  ['SchE', 'Schedule E — Rentals & pass-throughs'],
  ['F4562-E', 'Form 4562 — Rental depreciation'],
  ['F8582', 'Form 8582 — Passive losses'],
  ['F7203', 'Form 7203 — S corporation basis'],
  ['F8995', 'Form 8995 — QBI deduction'],
  ['F6251', 'Form 6251 — AMT'],
  ['F8812', 'Schedule 8812 — Child tax credit'],
  ['F8863', 'Form 8863 — Education credits'],
  ['F2441', 'Form 2441 — Dependent care'],
  ['F8889', 'Form 8889 — HSA'],
  ['F8606', 'Form 8606 — Nondeductible IRAs'],
  ['F8959', 'Form 8959 — Additional Medicare tax'],
  ['F8960', 'Form 8960 — Net investment income tax'],
  ['F2210', 'Form 2210 — Underpayment penalty'],
  ['F8938', 'Form 8938 — Foreign assets'],
  ['F8867', 'Form 8867 — Due diligence'],
  ['SchCA540NR', 'Schedule CA (540NR)'],
  ['F540NR', 'California 540NR'],
  ['ScheduleS', 'California Schedule S'],
  ['FTB3885A', 'FTB 3885A — CA depreciation'],
  ['FTB5805', 'FTB 5805 — CA underpayment'],
]
export const FORM_NAME = Object.fromEntries(FORMS) as Record<string, string>

export function formOf(key: string): string {
  return key.split('.')[0]
}
