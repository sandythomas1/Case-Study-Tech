import { after, before, test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { initializeTestEnvironment, assertFails, assertSucceeds } from '@firebase/rules-unit-testing';
import { doc, getDoc, setDoc, collection, getDocs } from 'firebase/firestore';
let env;
before(async () => {
  env = await initializeTestEnvironment({ projectId: 'demo-casestudy-tech', firestore: { host: '127.0.0.1', port: 8085, rules: await readFile(new URL('./firestore.rules', import.meta.url), 'utf8') } });
  await env.withSecurityRulesDisabled(async (context) => {
    await setDoc(doc(context.firestore(), 'students/a/scores/one'), { overall: 4 });
    await setDoc(doc(context.firestore(), 'students/b/scores/one'), { overall: 2 });
    await setDoc(doc(context.firestore(), 'students/deleting/scores/one'), { overall: 3 });
    await setDoc(doc(context.firestore(), 'account_deletions/deleting'), { state: 'pending' });
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
