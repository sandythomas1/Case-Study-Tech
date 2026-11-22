# Student navigation preview

## Scope and language
- Seven destinations only; no sign-in, profile fields, client selection, conversation, scoring, or saved work.
- Copy follows the spec's domain nouns and existing account branch's Library/Preparation/Session/Report labels.
- Use **Score history** consistently, including its tab; do not shorten it to History.
- No Figma reference or design system exists on dev. Reuse Expo Router navigation and React Native primitives; no new UI library.
- This is navigation review, not final visual design or evidence that practice/account features work.

## Flow and screens
- Entry: Welcome -> Library. Welcome has no bottom tabs; its only forward action is **Explore the preview**.
- Main destinations: **Library**, **Score history**, **Account**, in that order; mobile bottom tabs and equivalent web navigation.
- Library -> Preparation -> Session -> Report is a nested preview path associated with Library.
- Preparation, Session, and Report are not additional top-level tabs. Keep a clear path back to Library.
- Use **Back to Library** from Preparation; **Back to Preparation** from Session; **Back to Session** from Report.
- Back must work for direct links without earlier navigation history; use explicit destination links when necessary.
- Report also offers **Return to Library**. Do not imply completion, submission, or a saved result.
- All seven routes must render their own title and preview notice when opened directly.

## Exact shared copy
- App name: **Case-Study-Tech**.
- Visible notice on every screen: **Navigation preview**.
- Notice body: **Explore the planned screens. Practice, scores, and accounts are not available in this preview.**
- Titles are exactly Welcome, Library, Preparation, Session, Report, Score history, and Account.
- Forward actions use destination-specific preview labels below; never Start practice, Sign in, Create account, Submit, or Finish session.

| Destination | Body copy | Forward navigation |
| --- | --- | --- |
| Welcome | Welcome to Case-Study-Tech. Explore the planned counseling practice screens. | Explore the preview -> Library |
| Library | This is where you will find counseling practice cases. Cases are not available in this preview. | Preview Preparation -> Preparation |
| Preparation | This is where you will prepare for a practice session. Preparation materials are not available in this preview. | Preview Session -> Session |
| Session | This is where you will practice counseling with a simulated client. Conversations are not available in this preview. | Preview Report -> Report |
| Report | This is where you will review feedback after a practice session. Feedback and scores are not available in this preview. | Return to Library -> Library |
| Score history | This is where you will review scores from past practice sessions. Score history is not available in this preview. | None; retain main navigation |
| Account | This is where you will manage your account. Sign-in and account settings are not available in this preview. | None; retain main navigation |

## Components and layout
- Reuse one screen frame: safe-area container, scrollable content, screen heading, shared preview notice, body, and navigation links.
- Reuse one navigation-link style with visible focus and pressed feedback; native links/buttons expose accurate accessibility roles.
- Reuse Expo tab selection semantics and text labels. Icons are optional, decorative when text repeats their meaning.
- Keep content in a readable centered column on wide web layouts; use available width with padding on narrow screens.
- Allow body text and action labels to wrap. Do not fix content height or position actions over content.
- Default light palette is sufficient; if dark mode is supported, verify all text, focus, and selection colors in both modes.

## States
- Default/empty: render the explanatory preview body above. Do not use empty score charts, numeric scores, invented clients, or fake user names.
- Loading: none expected for these local screens; render immediately without a spinner or loading promise.
- Success: navigation displays the destination; no toast suggesting a completed practice session or account action.
- Offline: after the app loads, navigation uses local content and needs no connectivity warning. Fresh web loading still requires its host.
- Error: if a user-facing route fallback is included, title **Page unavailable**, body **We couldn't find that page. Return to the Library to explore the preview.**, link **Return to Library**.
- No disabled practice/account controls: explain unavailability in prose and expose only working navigation.

## Accessibility and narrow-layout checks
- [ ] Each page exposes one clear primary heading; decorative text is not announced as a control.
- [ ] Keyboard order follows visible reading order; all web links/tabs work without a pointer and have visible focus.
- [ ] Destination changes expose the new page title to assistive technology; web focus does not remain on a removed control.
- [ ] Main navigation announces names and the selected destination; do not communicate selection with color alone.
- [ ] Text contrast meets WCAG AA (4.5:1 for ordinary text); meaningful focus/selection indicators meet 3:1.
- [ ] Aim for at least 44 x 44 logical units for navigation targets; keep adjacent targets separate.
- [ ] At 320 CSS pixels and 200% web zoom, text/actions remain readable and scrollable without horizontal content overflow.
- [ ] On narrow Android/iOS, all three tab labels remain legible, content clears safe areas, and last actions can be scrolled into view.
- [ ] Increased device text size does not clip notice, title, body, or action labels; avoid arbitrary font-scale caps.
- [ ] No motion is necessary; any retained router transition respects reduced-motion preferences where available.

## Evidence required for review
- Capture all seven destinations from the running web app, including at least one 320-pixel view and one keyboard-focused control.
- Capture the mobile shell and nested path on available native simulators/emulators; record platform checks separately from responsive web checks.
- Exercise Welcome -> Library -> Preparation -> Session -> Report -> Library, both remaining tabs, direct links, and backward navigation.
- Record missing native runtime or screen-reader evidence explicitly; web exports and responsive browser screenshots do not prove native behavior.
