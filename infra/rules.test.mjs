import { after, before, test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { initializeTestEnvironment, assertFails, assertSucceeds } from '@firebase/rules-unit-testing';
import { doc, getDoc, setDoc, updateDoc, deleteDoc, collection, getDocs } from 'firebase/firestore';
let env;
// Every record that must read nothing. null means no access record at all.
const UNAPPROVED = {
  missing: null,
  pending: { state: 'pending' },
  denied: { state: 'denied' },
  nostate: { email: 'nostate@test.invalid' },
  capital: { state: 'Approved' },
  revoked: { state: 'revoked' },
  numeric: { state: 1 },
  listed: { state: ['approved'] },
};
before(async () => {
  env = await initializeTestEnvironment({ projectId: 'demo-casestudy-tech', firestore: { host: '127.0.0.1', port: 8085, rules: await readFile(new URL('./firestore.rules', import.meta.url), 'utf8') } });
  await env.withSecurityRulesDisabled(async (context) => {
    await setDoc(doc(context.firestore(), 'students/a/scores/one'), { overall: 4 });
    await setDoc(doc(context.firestore(), 'students/b/scores/one'), { overall: 2 });
    await setDoc(doc(context.firestore(), 'students/deleting/scores/one'), { overall: 3 });
    await setDoc(doc(context.firestore(), 'account_deletions/deleting'), { state: 'pending' });
    // Synthetic access records (POLICY ACC-9). a and b are approved.
    const db = context.firestore();
    for (const uid of ['a', 'b', 'deleting']) {
      await setDoc(doc(db, `access/${uid}`), { state: 'approved', display_name: 'Synthetic', email: `${uid}@test.invalid`, version: 2 });
    }
    for (const [uid, record] of Object.entries(UNAPPROVED)) {
      await setDoc(doc(db, `students/${uid}/scores/one`), { overall: 3 });
      if (record) await setDoc(doc(db, `access/${uid}`), record);
    }
  });
});
after(async () => { await env?.cleanup(); });
const student = (uid, provider = 'google.com') => env.authenticatedContext(uid, { firebase: { sign_in_provider: provider } }).firestore();
test('Google student can read only their own scores', async () => {
  await assertSucceeds(getDoc(doc(student('a'), 'students/a/scores/one')));
  await assertSucceeds(getDocs(collection(student('a'), 'students/a/scores')));
  await assertFails(getDoc(doc(student('a'), 'students/b/scores/one')));
  await assertFails(getDocs(collection(student('a'), 'students/b/scores')));
});
test('unauthenticated and non-Google identities cannot read scores', async () => {
  await assertFails(getDoc(doc(env.unauthenticatedContext().firestore(), 'students/a/scores/one')));
  await assertFails(getDoc(doc(student('a', 'password'), 'students/a/scores/one')));
});
test('clients cannot create grades or alter deletion markers', async () => {
  await assertFails(setDoc(doc(student('a'), 'students/a/scores/fabricated'), { overall: 5 }));
  await assertFails(setDoc(doc(student('a'), 'account_deletions/a'), { state: 'completed' }));
});
test('queued deletion denies direct reads even with an old valid token', async () => {
  await assertFails(getDoc(doc(student('deleting'), 'students/deleting/scores/one')));
  await assertFails(getDoc(doc(student('deleting'), 'account_deletions/deleting')));
});

test('an unapproved owner cannot read their own scores (AC5)', async () => {
  for (const uid of Object.keys(UNAPPROVED)) {
    await assertFails(getDoc(doc(student(uid), `students/${uid}/scores/one`)));
    await assertFails(getDocs(collection(student(uid), `students/${uid}/scores`)));
  }
});
test('an approved owner can read and another user cannot read either (AC5)', async () => {
  await assertSucceeds(getDoc(doc(student('a'), 'students/a/scores/one')));
  await assertFails(getDoc(doc(student('b'), 'students/a/scores/one')));
  await assertFails(getDoc(doc(student('b'), 'students/pending/scores/one')));
  await assertFails(getDoc(doc(student('pending'), 'students/a/scores/one')));
});
test('approval does not outrank a queued deletion', async () => {
  // 'deleting' has an approved record and a deletion marker.
  await assertFails(getDoc(doc(student('deleting'), 'students/deleting/scores/one')));
});
test('no client can read the access record, its own included (AC5)', async () => {
  const unauthenticated = env.unauthenticatedContext().firestore();
  for (const db of [student('a'), student('pending'), student('b'), unauthenticated]) {
    await assertFails(getDoc(doc(db, 'access/a')));
    await assertFails(getDoc(doc(db, 'access/pending')));
    await assertFails(getDocs(collection(db, 'access')));
  }
});
test('no client can write the access record (AC5)', async () => {
  for (const [db, uid] of [[student('missing'), 'missing'], [student('pending'), 'pending'], [student('denied'), 'denied'], [student('a'), 'a'], [student('b'), 'a']]) {
    await assertFails(setDoc(doc(db, `access/${uid}`), { state: 'approved' }));
    await assertFails(setDoc(doc(db, `access/${uid}`), { state: 'approved' }, { merge: true }));
    await assertFails(deleteDoc(doc(db, `access/${uid}`)));
  }
  await assertFails(updateDoc(doc(student('pending'), 'access/pending'), { state: 'approved' }));
  await assertFails(setDoc(doc(env.unauthenticatedContext().firestore(), 'access/x'), { state: 'approved' }));
  await env.withSecurityRulesDisabled(async (context) => {
    const record = await getDoc(doc(context.firestore(), 'access/pending'));
    if (record.data().state !== 'pending') throw new Error('a client write changed the record');
    if ((await getDoc(doc(context.firestore(), 'access/missing'))).exists()) throw new Error('a client created a record');
  });
});
