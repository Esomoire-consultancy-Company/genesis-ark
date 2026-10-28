import test from 'node:test';
import assert from 'node:assert/strict';
import {reviewAuction} from './rule9_guard.mjs';

const baseline = Object.freeze({
  asOf: '2026-10-06',
  authoritativeInterimOrderAvailable: false,
  interimOrderEffect: 'subject_to_outcome',
  bankDeferralClaimed: true,
  bankDeferralDocumentAvailable: false,
  confirmationDate: null,
  balance75ExpectedINR: 12_262_500,
  balance75ReceivedINR: 0,
  balance75PaymentDate: null,
  paymentLedgerVerified: false,
  ibcMoratorium: 'not_applicable',
});
const check = (changes = {}) => reviewAuction({...baseline, ...changes});
const codes = r => r.flags.map(f => f.code);

test('unknown confirmation date results in legal hold with no manufactured deadline', () => {
  const r = check();
  assert.equal(r.disposition, 'HOLD_FOR_DOCUMENTARY_LEGAL_REVIEW');
  assert.equal(r.candidateDeadlines.fifteenDaysAfterConfirmation, null);
  assert.ok(codes(r).includes('CONFIRMATION_DATE_MISSING'));
});

test('subject-to-outcome alone does not become a payment stay', () => {
  const r = check({authoritativeInterimOrderAvailable:true});
  assert.ok(codes(r).includes('ORDER_NOT_AUTOMATIC_PAYMENT_STAY'));
  assert.ok(!codes(r).includes('JUDICIAL_PAYMENT_RESTRAINT'));
});

test('15-day candidate deadline derives from confirmation, never auction', () => {
  const r = check({confirmationDate:'2024-08-29'});
  assert.equal(r.candidateDeadlines.fifteenDaysAfterConfirmation, '2024-09-13');
  assert.ok(codes(r).includes('POTENTIAL_RULE9_4_BREACH'));
});

test('written extension longer than 3 calendar months cannot be used', () => {
  const r = check({confirmationDate:'2024-08-29',writtenExtension:{claimed:true,documentAvailable:true,agreedDeadline:'2025-02-01'}});
  assert.ok(codes(r).includes('EXTENSION_OVER_OUTER_LIMIT'));
  assert.equal(r.candidateDeadlines.illustrativeEffectiveDeadline, '2024-09-13');
});

test('documented valid extension moves candidate deadline, not legal outcome', () => {
  const r = check({confirmationDate:'2024-08-29',asOf:'2024-09-20',writtenExtension:{claimed:true,documentAvailable:true,agreedDeadline:'2024-10-20'}});
  assert.equal(r.candidateDeadlines.illustrativeEffectiveDeadline, '2024-10-20');
  assert.ok(!codes(r).includes('POTENTIAL_RULE9_4_BREACH'));
  assert.equal(r.disposition,'HOLD_FOR_DOCUMENTARY_LEGAL_REVIEW');
});

test('active IBC moratorium flags ownership and enforcement gate', () => {
  assert.ok(codes(check({ibcMoratorium:'active',collateralOwnedByCorporateDebtor:true})).includes('IBC_ENFORCEMENT_GATE'));
  assert.ok(codes(check({ibcMoratorium:'active',collateralOwnedByCorporateDebtor:null})).includes('IBC_ENFORCEMENT_GATE'));
});

test('verified complete on-time payment does not constitute certification', () => {
  const r = check({
    asOf:'2024-09-14',confirmationDate:'2024-08-29',balance75ReceivedINR:12_262_500,
    balance75PaymentDate:'2024-09-12',paymentLedgerVerified:true,
    authoritativeInterimOrderAvailable:true,interimOrderEffect:'none',
    bankDeferralClaimed:false, ibcMoratorium:'inactive',
  });
  assert.equal(r.disposition,'READY_FOR_COUNSEL_REVIEW_NOT_CERTIFIED');
  assert.deepEqual(r.flags,[]);
  assert.ok(r.prohibitedAutonomousActions.includes('forfeit_deposit'));
});

test('full payment without date cannot silently pass', () => {
  const r = check({confirmationDate:'2024-08-29',balance75ReceivedINR:12_262_500,paymentLedgerVerified:true});
  assert.ok(codes(r).includes('PAYMENT_DATE_MISSING'));
});

test('payment after deadline is flagged regardless of later full receipt', () => {
  const r = check({confirmationDate:'2024-08-29',balance75ReceivedINR:12_262_500,balance75PaymentDate:'2024-09-15',paymentLedgerVerified:true});
  assert.ok(codes(r).includes('LATE_PAYMENT_RECORD'));
});

test('invalid dates and negative, fractional or unsafe amounts are rejected', () => {
  assert.throws(()=>check({asOf:'2026-02-30'}),/asOf/);
  assert.throws(()=>check({confirmationDate:'2024-13-29'}),/confirmationDate/);
  assert.throws(()=>check({balance75ReceivedINR:-1}),/integer INR/);
  assert.throws(()=>check({balance75ExpectedINR:1.1}),/integer INR/);
  assert.throws(()=>check({balance75ExpectedINR:Number.MAX_SAFE_INTEGER+1}),/integer INR/);
});

test('calendar-month clamping handles month-end deterministically', () => {
  const r=check({confirmationDate:'2024-11-30'});
  assert.equal(r.candidateDeadlines.threeCalendarMonthsAfterConfirmation,'2025-02-28');
});

test('unverified bank deferral remains disputed rather than a waiver', () => {
  const r=check({confirmationDate:'2024-08-29'});
  assert.ok(codes(r).includes('BANK_DEFERRAL_UNVERIFIED'));
  assert.ok(codes(r).includes('POTENTIAL_RULE9_4_BREACH'));
});
