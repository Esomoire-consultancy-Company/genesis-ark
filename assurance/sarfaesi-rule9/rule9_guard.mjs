/**
 * SARFAESI Rule 9 documentary screening R0.3 (pure, read-only).
 * NOT a legal determination or permission to execute any recovery action.
 * Dates are calendar-day illustrations and require counsel verification.
 */
const EFFECTS = new Set(['none', 'subject_to_outcome', 'payment_prohibited', 'other', 'unknown']);
const IBC = new Set(['not_applicable', 'active', 'inactive', 'unknown']);
const MATERIAL = new Set([
  'ORDER_TEXT_MISSING', 'ORDER_EFFECT_UNKNOWN', 'JUDICIAL_PAYMENT_RESTRAINT',
  'BANK_DEFERRAL_UNVERIFIED', 'CONFIRMATION_DATE_MISSING',
  'EXTENSION_NOT_PROVED', 'EXTENSION_OVER_OUTER_LIMIT',
  'PAYMENT_RECONCILIATION_MISSING', 'PAYMENT_DATE_MISSING',
  'PAYMENT_AMOUNT_MISSING', 'UNPAID_BALANCE', 'OVERPAYMENT_RECONCILIATION',
  'POTENTIAL_RULE9_4_BREACH', 'LATE_PAYMENT_RECORD',
  'IBC_ENFORCEMENT_GATE', 'IBC_STATUS_UNRESOLVED',
]);
function date(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const d = new Date(value + 'T00:00:00.000Z');
  return Number.isFinite(d.getTime()) && d.toISOString().slice(0, 10) === value ? d : null;
}
function plusDays(value, days) {
  const d = date(value); d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
function plusMonthsClamped(value, months) {
  const d = date(value), day = d.getUTCDate();
  const monthStart = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + months, 1));
  const lastDay = new Date(Date.UTC(monthStart.getUTCFullYear(), monthStart.getUTCMonth() + 1, 0)).getUTCDate();
  monthStart.setUTCDate(Math.min(day, lastDay));
  return monthStart.toISOString().slice(0, 10);
}
function money(value, field) {
  if (value !== null && value !== undefined && (!Number.isSafeInteger(value) || value < 0)) {
    throw new TypeError(field + ' must be a nonnegative integer INR amount or null');
  }
}
function validate(a) {
  if (!a || typeof a !== 'object' || Array.isArray(a)) throw new TypeError('review input must be an object');
  if (!date(a.asOf)) throw new TypeError('asOf is required as valid YYYY-MM-DD');
  for (const key of ['confirmationDate', 'balance75PaymentDate']) {
    if (a[key] != null && !date(a[key])) throw new TypeError(key + ' must be valid YYYY-MM-DD or null');
  }
  money(a.balance75ExpectedINR, 'balance75ExpectedINR');
  money(a.balance75ReceivedINR, 'balance75ReceivedINR');
  if (a.interimOrderEffect != null && !EFFECTS.has(a.interimOrderEffect)) throw new TypeError('unknown interimOrderEffect');
  if (a.ibcMoratorium != null && !IBC.has(a.ibcMoratorium)) throw new TypeError('unknown ibcMoratorium');
  const ext = a.writtenExtension;
  if (ext != null) {
    if (typeof ext !== 'object' || Array.isArray(ext)) throw new TypeError('writtenExtension must be an object');
    if (ext.agreedDeadline != null && !date(ext.agreedDeadline)) throw new TypeError('writtenExtension.agreedDeadline is invalid');
  }
}
export function reviewAuction(input) {
  validate(input);
  const a = input, flags = [];
  const add = (code, detail) => flags.push({code, detail});
  const confirmation = a.confirmationDate ?? null;
  const paidDate = a.balance75PaymentDate ?? null;
  const expected = a.balance75ExpectedINR ?? null;
  const received = a.balance75ReceivedINR ?? null;
  const effect = a.interimOrderEffect ?? 'unknown';
  if (!a.authoritativeInterimOrderAvailable) add('ORDER_TEXT_MISSING', 'Signed court order and modifications not verified.');
  if (effect === 'subject_to_outcome') add('ORDER_NOT_AUTOMATIC_PAYMENT_STAY', 'Subject-to-outcome does not itself prove that the bank could not receive payment.');
  if (effect === 'unknown') add('ORDER_EFFECT_UNKNOWN', "Determine the order's operative effect separately for receipt, certificate, possession and transfer.");
  if (effect === 'payment_prohibited') add('JUDICIAL_PAYMENT_RESTRAINT', 'Human counsel must interpret proven restraint; never automatically waive statutory deadlines.');
  if (a.bankDeferralClaimed && !a.bankDeferralDocumentAvailable) add('BANK_DEFERRAL_UNVERIFIED', "Obtain the bank's actual instruction and supporting metadata.");
  const ibc = a.ibcMoratorium ?? 'unknown';
  if (ibc === 'unknown') add('IBC_STATUS_UNRESOLVED', 'Verify whether an IBC moratorium affects the secured asset.');
  if (ibc === 'active' && a.collateralOwnedByCorporateDebtor !== false) add('IBC_ENFORCEMENT_GATE', 'Counsel must resolve asset ownership, the moratorium and statutory exceptions.');
  if (!confirmation) add('CONFIRMATION_DATE_MISSING', 'Never infer Rule 9(4) commencement from the auction date.');
  if (expected === null || received === null) add('PAYMENT_AMOUNT_MISSING', 'Missing verified expected or received consideration.');
  if (expected !== null && received !== null && received < expected) add('UNPAID_BALANCE', 'Recorded consideration is incomplete; it may be a reported rather than bank-verified amount.');
  if (expected !== null && received !== null && received > expected) add('OVERPAYMENT_RECONCILIATION', 'Received amount exceeds the expected amount; reconcile before making any assertion.');
  if (expected !== null && received === expected && !paidDate) add('PAYMENT_DATE_MISSING', 'Complete receipt amount lacks a dated credit record.');
  if (!a.paymentLedgerVerified) add('PAYMENT_RECONCILIATION_MISSING', 'Bank statement, receipts and ledger are not reconciled.');

  const nominal = confirmation ? plusDays(confirmation, 15) : null;
  const outer = confirmation ? plusMonthsClamped(confirmation, 3) : null;
  let effective = nominal;
  const extension = a.writtenExtension;
  if (extension?.claimed) {
    if (!extension.documentAvailable || !extension.agreedDeadline || !confirmation) {
      add('EXTENSION_NOT_PROVED', 'Written extension, valid confirmation and agreed deadline must be verified.');
    } else if (extension.agreedDeadline > outer) {
      add('EXTENSION_OVER_OUTER_LIMIT', 'Extension exceeds illustrative three-calendar-month upper boundary.');
    } else if (extension.agreedDeadline > nominal) {
      effective = extension.agreedDeadline;
    }
  }
  if (confirmation && effective && a.asOf > effective && expected !== null && received !== null && received < expected) {
    add('POTENTIAL_RULE9_4_BREACH', 'Recorded unpaid balance past provisional deadline: requires judicial and documentary review.');
  }
  if (confirmation && effective && paidDate && paidDate > effective) {
    add('LATE_PAYMENT_RECORD', 'Recorded payment date is after provisional deadline; assess actual order and extension.');
  }
  return {
    version: '0.3.0',
    asOf: a.asOf,
    disposition: flags.some(f => MATERIAL.has(f.code)) ? 'HOLD_FOR_DOCUMENTARY_LEGAL_REVIEW' : 'READY_FOR_COUNSEL_REVIEW_NOT_CERTIFIED',
    flags,
    candidateDeadlines: {
      fifteenDaysAfterConfirmation: nominal,
      threeCalendarMonthsAfterConfirmation: outer,
      illustrativeEffectiveDeadline: effective,
    },
    permittedActions: ['record_evidence', 'request_documents', 'seek_counsel_review'],
    prohibitedAutonomousActions: ['forfeit_deposit', 'resell_asset', 'issue_sale_certificate', 'transfer_title', 'enforce_possession', 'post_bank_ledger'],
    disclaimer: 'Read-only risk screen; no legal finding, statutory waiver, transaction posting or Warden execution grant.',
  };
}
