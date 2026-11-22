# CaseStudy Tech rubric anchor specification

<!-- Generated from rubric/anchor-spec.v1.json by scripts/ci/check_anchor_spec.py. Do not edit by hand: change the JSON and run the script with --write-markdown. -->

- **Spec:** `casestudy-tech-rubric-anchors` version 1.0.0
- **Status:** proposed
- **Satisfies:** RC-17, RC-18, RC-19, OQ-03
- **Constrained by:** PA-4, PA-10, AG-4, AG-5

## Intended use

Formative feedback on a simulated practice conversation, so a student can reflect and practice again.

Not for:

- course grades or grade components
- progression, placement or admission decisions
- licensure, certification or any statement of clinical competence
- judging work with real clients
- a validated suicide-risk assessment

Shown to students: "This is developmental feedback on a practice conversation. It is not a grade, it is not a validated assessment, and it does not measure clinical competence."

## Scale

| Level | Label | Meaning |
|---|---|---|
| 1 | Beginning | Some responses worked against this skill. |
| 2 | Emerging | This skill appeared now and then but was not steady yet. |
| 3 | Developing | This skill showed up at several points, with clear room to grow. |
| 4 | Consistent | This skill showed up at most of the moments that called for it. |
| 5 | Advanced | This skill was strong and steady across the whole conversation. |

## What the grader may assess

What the completed transcript shows: the words of each numbered turn, their order, and what the student said in response to what the client said.

Never infer:

- nonverbal warmth, facial expression or body language
- tone of voice, pacing of speech or other prosody
- what happens to the client after the session
- the student's overall clinical competence, intent or personality

Never reward:

- counts of keywords, techniques or question types
- length, verbosity or fluency on their own
- a client who agrees or complies, when the student's turns do not show the skill
- stock phrases such as 'It sounds like', 'Thank you for sharing' or 'Did I miss anything?' that do not fit what the client said

Never penalize:

- client resistance, disagreement or refusal on its own
- the client choosing not to change
- speech-recognition errors in a student turn
- choosing text instead of voice
- dialect, non-native English, spelling or grammar in a student turn when the meaning is clear
- after a crisis disclosure: direct or repeated questions about suicide, harm or safety, closed questions about plan, means or timing, directive safety steps such as 'Please call 988 now', and honest statements that safety may require involving someone else. In any category these are never scored as pressure, commanding, threatening or a checklist

## Evidence and scoring rules

- **Evidence unit:** One numbered turn of the completed transcript. Every quoted or paraphrased example cites the turn it came from, and evidence validation (#36) rejects a citation that does not match (RC-18).
- **Sufficient criterion:** The transcript gave the opportunity the criterion defines, and its minimum evidence is met by cited student turns.
- **Insufficient criterion:** The opportunity did not occur, or the cited turns do not meet the minimum evidence. The criterion contributes nothing to the rating.
- **Category rating:** A general category is rated when at least 2 of its 3 criteria are sufficient. The scenario-specific category is rated when every criterion its scenario marks as required is sufficient, and the crisis scenario is also rated when a crisis critical failure is found. The rating is the highest level whose behavior anchor describes the student's typical pattern across the session, supported by at least 2 cited student turns.
- **Harm cap:** One student turn that matches a level 1 behavior caps the category at level 2. Two or more such turns set the category to level 1. Any crisis critical failure sets the crisis scenario-specific rating to level 1, even when CR-1, CR-2 or CR-3 is insufficient, and regardless of how many student turns are cited.
- **Conflicting evidence:** Rate the level that describes most of the cited turns. If two adjacent levels are equally supported, choose the lower one and cite turns for both. This guards against score inflation. If the cited turns split between levels two or more apart and no level describes most of them, the category abstains with unresolved_conflict.
- **Uncertain speech recognition:** A student turn that the transcript marks as uncertain speech recognition can never be the only evidence for a level 1 behavior, a harm cap or a crisis critical failure. If a rating or the safety result depends on such a turn, the category abstains.
- **Abstention:** A category that is not rated abstains, with one reason code. Abstention is reported as abstention. It is never turned into a number.
- **Abstention reasons:** `no_opportunity`, `too_few_cited_turns`, `uncertain_recognition`, `unresolved_conflict`
- **Never used as a fallback:** midpoint, zero, lowest level, reweighting the other categories, a rating carried over from another category or session
- **Overall score:** Code computes the overall score as the sum of weight_percent times category rating, divided by 100, only when all six categories are rated. The model never computes it. It is shown from 1.0 to 5.0 with one decimal and never as a percent (SCO-9). If any category abstains, there is no overall score (SCO-3), and #35 sets what the student sees. A crisis critical failure is never dropped: its safety result is produced even when another category abstains (SCO-5, ETH-7).

## Categories

| Category | Weight |
|---|---|
| Empathic engagement | 20% |
| Active listening and responding | 20% |
| Purposeful questioning and exploration | 15% |
| Collaboration, autonomy and cultural humility | 15% |
| Session structure and professionalism | 10% |
| Scenario-specific competence | 20% |

### Empathic engagement (20%)

The student shows, in words, that they understand what the client feels and treat that experience as understandable.

#### Criteria

##### EE-1 Reflects feelings accurately

- **Definition:** The student names or reflects a feeling that fits what the client just said, stated or clearly implied.
- **Opportunity:** A client turn that states or clearly implies a feeling.
- **Minimum evidence:** Two student turns, each reflecting a feeling and each tied to the client turn before it. An implied feeling counts only if the grader can cite the client words that imply it.
- **Insufficient evidence:** If the client gave fewer than two openings to reflect a feeling, or no reflection can be tied to a client turn, the criterion is insufficient.
- **Shows it:**
  - Client: 'I keep telling everyone it's fine, but I haven't slept properly in weeks.' Student: 'It sounds like there's a lot of worry sitting under that word fine.'
- **Does not show it:**
  - Student: 'I understand exactly how you feel.' (generic, with no feeling or content named)
  - Client describes feeling let down by a friend. Student: 'You seem really angry at yourself.' (the reflection does not fit anything the client said)
- **Sources:**
  - ivey-microskills (direct). Reflection of feeling.
  - fis (adapted). Empathy dimension, limited to what a transcript shows.
  - enact-equip (adapted). Empathy competency written as observable behavior.

##### EE-2 Validates without judging

- **Definition:** The student treats the client's experience as understandable, without judging it, arguing with it, or covering it with quick reassurance.
- **Opportunity:** A client turn that shares a difficulty, a worry, or something the client feels unsure or ashamed about.
- **Minimum evidence:** Two student turns that acknowledge the experience as understandable, or one such turn plus the absence of judging responses across the session.
- **Insufficient evidence:** If the client shared no difficulty that called for validation, the criterion is insufficient.
- **Shows it:**
  - Client: 'It's stupid to be this upset about a grade.' Student: 'It doesn't sound stupid. That grade clearly matters a lot to you.'
- **Does not show it:**
  - Student: 'You shouldn't feel that way about it.'
  - Student: 'Don't worry, everything will be fine.' (quick reassurance that skips the client's concern)
- **Sources:**
  - enact-equip (adapted). Warmth and acceptance as observable behavior.
  - fis (adapted). Warmth and acceptance dimension.

##### EE-3 Stays with strong emotion or strain

- **Definition:** When the client shows strong distress, frustration with the student, or pulls back, the student slows down and responds to it before going on.
- **Opportunity:** A client turn showing strong distress, irritation with the student or the session, or withdrawal such as very short answers after a sensitive question.
- **Minimum evidence:** One student turn that responds directly to the strong emotion or strain, cited with the client turn it answers.
- **Insufficient evidence:** If no strong emotion or strain appeared in the transcript, the criterion is insufficient. It is never scored as a miss.
- **Shows it:**
  - Client: 'Why do you keep asking me that?' Student: 'You're right, I've asked a lot. Let me slow down. What would be most useful to talk about?'
- **Does not show it:**
  - Client: 'I don't even know why I'm crying.' Student: 'Okay. Next, can you tell me about your work schedule?'
- **Sources:**
  - fis (adapted). Alliance rupture and repair, as observable responses.

#### Levels

| Level | Behavior anchor (grader) | Student sees |
|---|---|---|
| 1 Beginning | Dismisses, mocks, blames or argues with the client's feelings, or tells the client their feelings are wrong or excessive ('You're overreacting'). | Some responses brushed aside or judged what the client was feeling. |
| 2 Emerging | Rarely acknowledges feelings. Responses are mostly generic ('I understand'), with few specific feelings named, or move past emotional content to facts or advice. | You noticed the client's feelings now and then, but often moved on to facts or advice. |
| 3 Developing | Names specific feelings at several points, but some are off-target or followed at once by reassurance or advice. | You acknowledged feelings at several points. Naming them more precisely is the next step. |
| 4 Consistent | Reflects feelings accurately at most openings and validates the client's experience. Misses or rushes past some moments of strong emotion. | You reflected the client's feelings accurately at most moments that called for it. |
| 5 Advanced | Reflects feelings accurately and specifically, including ones implied but not stated. Validates without judging and, when distress or strain comes up, slows down to respond to it. | You stayed closely tuned to the client's feelings, including ones they did not say out loud. |

### Active listening and responding (20%)

The student shows, in words, that they heard what the client said, and each response builds on it.

#### Criteria

##### AL-1 Paraphrases content accurately

- **Definition:** The student restates the client's meaning in fresh words, without adding things the client did not say.
- **Opportunity:** A client turn with substantive content, such as an event, a problem or a reason.
- **Minimum evidence:** Two student turns that paraphrase or reflect content, each traceable to a client turn and faithful to it.
- **Insufficient evidence:** If fewer than two paraphrases can be traced to a client turn, the criterion is insufficient.
- **Shows it:**
  - Client: 'My mom calls every night to check if I studied, and then we fight.' Student: 'So the nightly check-ins with your mom keep turning into arguments.'
- **Does not show it:**
  - Client describes arguments with their mother. Student: 'So your mom doesn't trust you and you want to move out.' (adds meaning the client did not express)
- **Sources:**
  - ivey-microskills (direct). Paraphrasing and encouraging.
  - bogo-osce (adapted). Engagement through accurate responding to a standardized client.

##### AL-2 Follows the client's thread

- **Definition:** Each student turn connects to what the client just said. The student does not ignore answers or move through a fixed script whatever the client says.
- **Opportunity:** Every exchange where a client turn is followed by a student turn.
- **Minimum evidence:** Two student turns that pick up something specific from the client turn before them, and no pattern of turns that ignore the client's answer.
- **Insufficient evidence:** If the session has fewer than three client-and-student exchanges, the criterion is insufficient.
- **Shows it:**
  - Client: 'Work is fine, it's more the drive home that gets to me.' Student: 'Tell me more about the drive home.'
- **Does not show it:**
  - Client: 'Honestly, the thing that worries me most is my sister.' Student: 'Okay. How many hours do you sleep a night?' (ignores what the client raised)
- **Sources:**
  - ivey-microskills (direct). Attending behavior and verbal tracking.

##### AL-3 Summarizes and checks understanding

- **Definition:** The student pulls several points the client made into one summary and invites the client to correct or add to it.
- **Opportunity:** A change of topic, a natural pause, or the close of the session, after at least six client turns.
- **Minimum evidence:** One student turn that summarizes at least two separate points from earlier client turns, each traceable.
- **Insufficient evidence:** If the session ended before six client turns, or no turn summarizes two or more traceable points, the criterion is insufficient.
- **Shows it:**
  - Student: 'Let me check I've got this. Sleep has been rough since the move, you're missing your friends, and you're not sure the new program was the right call. Did I miss anything?'
- **Does not show it:**
  - Student: 'So basically everything is stressful right now.' (too vague to show listening)
- **Sources:**
  - ivey-microskills (direct). Summarization.
  - cts-r (adapted). Checking understanding and eliciting feedback, a general interpersonal item.

#### Levels

| Level | Behavior anchor (grader) | Student sees |
|---|---|---|
| 1 Beginning | Ignores or contradicts what the client said, or insists on an interpretation after the client corrects it. | Some responses missed or changed what the client had said. |
| 2 Emerging | Mostly asks the next question without reflecting what was heard. Paraphrases are rare or inaccurate. | You mostly moved to your next question without showing what you heard. |
| 3 Developing | Paraphrases some content accurately and usually tracks the client's topic, but sometimes drifts to the student's own agenda. No summary, or an inaccurate one. | You showed you were listening at several points. Summaries would help bring it together. |
| 4 Consistent | Regularly paraphrases accurately and follows the client's thread. Uses at least one summary that captures the main points, when the session is long enough for one. | You followed the client's thread and reflected it back accurately most of the time. |
| 5 Advanced | Paraphrases capture the client's meaning, including nuance and mixed feelings. Summaries link themes and invite correction, and responses build on the client's last turn throughout. | Your responses built on what the client said throughout, and your summaries pulled it together. |

### Purposeful questioning and exploration (15%)

The student's questions invite the client to say more and move the conversation toward the scenario's objective at the client's pace.

#### Criteria

##### QE-1 Uses open questions to explore

- **Definition:** Where the aim is to explore, the student asks open questions that invite the client to elaborate. Closed questions are kept for specific facts.
- **Opportunity:** Any point where the student asks about the client's experience, situation or view.
- **Minimum evidence:** Two open questions that, in context, invite the client to elaborate. A count of open questions on its own is never evidence.
- **Insufficient evidence:** If the student asked fewer than two questions about the client's experience, the criterion is insufficient.
- **Shows it:**
  - Student: 'What has it been like for you since the move?'
- **Does not show it:**
  - Student: 'Is it stressful? Do you sleep okay? Are you eating?' (a run of closed questions where exploration was needed)
- **Sources:**
  - ivey-microskills (direct). Open and closed questions.

##### QE-2 Builds questions on the client's answers

- **Definition:** Questions follow up on what the client just said and deepen one topic before moving on, rather than jumping between unrelated topics.
- **Opportunity:** A client answer that leaves something worth exploring further.
- **Minimum evidence:** Two follow-up questions that each take up something specific from the client's previous answer.
- **Insufficient evidence:** If the client gave fewer than two answers that invited a follow-up, the criterion is insufficient.
- **Shows it:**
  - Client: 'I just shut down when my manager gives feedback.' Student: 'What happens for you in that moment when you shut down?'
- **Does not show it:**
  - Client: 'I just shut down when my manager gives feedback.' Student: 'Okay. And how is your family?' (drops the thread without a link)
- **Sources:**
  - bogo-osce (adapted). Exploration of the client's situation in a timed simulated interview.
  - cts-r (adapted). Pacing, a general interpersonal item.

##### QE-3 Avoids leading, stacked or blaming questions

- **Definition:** The student asks one question at a time, without steering the client to an answer or implying blame.
- **Opportunity:** Every student question.
- **Minimum evidence:** Two student questions that are single and neutral, and no pattern of leading, stacked or blaming questions.
- **Insufficient evidence:** If the student asked fewer than two questions, the criterion is insufficient.
- **Shows it:**
  - Student: 'How did you decide not to go to class that day?'
- **Does not show it:**
  - Student: 'Don't you think you should just talk to him?' (leading)
  - Student: 'Why would you do something like that?' (blaming)
- **Sources:**
  - ivey-microskills (adapted). Question forms, applied in original wording to leading, stacked and blaming questions.

#### Levels

| Level | Behavior anchor (grader) | Student sees |
|---|---|---|
| 1 Beginning | Questions blame, shame or pressure the client ('Why would you do something so careless?'), or keep pressing on a topic after the client says they do not want to discuss it (crisis safety questions excepted). | Some questions came across as blaming or pushy. |
| 2 Emerging | Relies on closed, stacked or leading questions. Questioning feels like a checklist and rarely follows the client's answers. | Your questions felt more like a checklist than a conversation. |
| 3 Developing | Mixes open and closed questions with some follow-up, but questions sometimes stack up or jump topics without a link. | You asked some good open questions. Following up on the client's answers is the next step. |
| 4 Consistent | Mostly open, well-timed questions that follow the client's answers and deepen understanding of the main concern. | Your questions were mostly open and followed what the client told you. |
| 5 Advanced | Asks open, single, purposeful questions. Each builds on the previous answer, explores meaning and context, and moves toward the scenario objective at the client's pace. | Each question built on the last answer and helped the client explore at their own pace. |

### Collaboration, autonomy and cultural humility (15%)

The student works with the client as a partner, respects the client's right to choose, and asks rather than assumes about the client's identity and context.

#### Criteria

##### CA-1 Shares the direction of the conversation

- **Definition:** The student asks what the client wants to focus on, invites the client's ideas before offering their own, and checks agreement on next steps.
- **Opportunity:** The start of the session, a change of topic, or any point where a next step or suggestion comes up.
- **Minimum evidence:** Two student turns that ask for the client's priorities, ideas or agreement.
- **Insufficient evidence:** If no point arose where direction, a suggestion or a next step could be shared, the criterion is insufficient.
- **Shows it:**
  - Student: 'We've got a few minutes left. What feels most important to you to look at?'
  - Student: 'Would it be okay if I shared an idea some people find useful?'
- **Does not show it:**
  - Student: 'Here's what we're going to do. First, you need to make a schedule.'
- **Sources:**
  - mi-principles (adapted). Partnership, cited as a concept.
  - cts-r (adapted). Collaboration, a general interpersonal item.
  - bogo-osce (adapted). Collaboration with the client in a simulated interview.

##### CA-2 Respects the client's choices

- **Definition:** The student affirms that decisions are the client's, and avoids commanding, warning or unrequested advice. A client who declines a suggestion is not a student error.
- **Opportunity:** Any point where the client states a choice, declines a suggestion, or the student might advise.
- **Minimum evidence:** Two student turns that support the client's choice or ask permission before advising, and no pattern of commanding or warning.
- **Insufficient evidence:** If no choice, refusal or advice point came up, the criterion is insufficient.
- **Shows it:**
  - Client: 'I'm not ready to tell my parents.' Student: 'That's your call to make. What would need to be different for it to feel possible?'
- **Does not show it:**
  - Client: 'I'm not ready to tell my parents.' Student: 'You really need to tell them this week.'
- **Sources:**
  - mi-principles (adapted). Autonomy support, cited as a concept.
  - enact-equip (adapted). Collaboration and respect for the client's decisions.

##### CA-3 Explores identity and context with humility

- **Definition:** When culture, identity, faith, family norms or other personal context comes up, the student asks what it means for this client instead of assuming, and does not stereotype.
- **Opportunity:** A client turn that mentions culture, identity, faith, family expectations, community or a similar context, or a student turn that invites the client to share context that matters to them.
- **Minimum evidence:** One student turn that asks about or reflects the meaning of that context for the client, and no turn that stereotypes.
- **Insufficient evidence:** If identity or cultural context never came up, the criterion is insufficient. It is never scored as a miss.
- **Shows it:**
  - Client: 'In my family you don't talk about this stuff.' Student: 'What is it like for you to be talking about it here, given that?'
- **Does not show it:**
  - Client mentions their faith. Student: 'People from religious backgrounds usually feel guilty about this.' (assumes and stereotypes)
  - Client mentions being an international student. Student: 'You must be really good at math, then.' (a positive stereotype is still a stereotype)
  - Client describes a fight with a roommate. Student: 'Is this about your culture?' (steers to identity the client has not linked to the concern)
- **Sources:**
  - cswe-epas-2022 (adapted). Competency 3 (anti-racism, diversity, equity and inclusion) and Competency 6 (engagement).

#### Levels

| Level | Behavior anchor (grader) | Student sees |
|---|---|---|
| 1 Beginning | Threatens, shames, coerces or stereotypes the client, or dismisses the client's stated values or identity. | Some responses pressured the client or made assumptions about who they are. |
| 2 Emerging | Directs the conversation and decides for the client, including telling the client what to do. Gives unrequested advice and does not ask for the client's view. | You led most of the conversation and made suggestions without asking the client first. |
| 3 Developing | Sometimes asks for the client's view or permission, but often steers toward the student's preferred solution. Responds to cultural context briefly, or assumes what it means without checking. | You asked for the client's view at times. Letting them lead more is the next step. |
| 4 Consistent | Invites the client's priorities and ideas, asks permission before offering information, and respects the client's choices. Asks what cultural context means to the client when it comes up. | You worked with the client as a partner and respected their choices. |
| 5 Advanced | Works as a partner throughout. Draws out the client's goals and ideas first, offers options rather than directions, affirms autonomy in words and, when context comes up, explores it with curiosity and without assumptions. | You worked as a true partner, drew out the client's own ideas and asked rather than assumed. |

### Session structure and professionalism (10%)

The student gives the session a clear purpose, uses the time well, and keeps the focus and language professional.

#### Criteria

##### SP-1 Opens with role and purpose

- **Definition:** Early in the session, the student introduces their role and what the conversation is for, and invites the client in.
- **Opportunity:** The first three student turns of the session.
- **Minimum evidence:** One early student turn that states role or purpose, and one that invites the client to begin.
- **Insufficient evidence:** If the transcript has fewer than three student turns, the criterion is insufficient.
- **Shows it:**
  - Student: 'Hi, I'm Sam, a counselor in training. We have about ten minutes today to talk about what's been going on. Where would you like to start?'
- **Does not show it:**
  - Student, first turn: 'So what's wrong with you?'
- **Sources:**
  - cts-r (adapted). Agenda setting, a general interpersonal item.

##### SP-2 Manages time, transitions and the close

- **Definition:** The student keeps the session on its purpose, signals changes of topic, and closes with a summary or next step when time allows.
- **Opportunity:** Topic changes during the session and its final minutes. If the time limit ended the session before the close, only the transitions are assessed.
- **Minimum evidence:** Two student turns that signal a transition, refocus the session, or close it.
- **Insufficient evidence:** If the session had no topic change and no chance to close, the criterion is insufficient.
- **Shows it:**
  - Student: 'We have a couple of minutes left. Can I sum up what we covered and what you might try next?'
- **Does not show it:**
  - The student spends most of the session on an unrelated story of their own and ends with 'Okay, bye.'
- **Sources:**
  - cts-r (adapted). Pacing and efficient use of time.
  - bogo-osce (adapted). Managing a timed simulated interview.

##### SP-3 Keeps professional language and boundaries

- **Definition:** The student keeps the focus on the client, uses respectful language, and avoids long self-disclosure, inappropriate humor or promises a counselor could not keep.
- **Opportunity:** Every student turn.
- **Minimum evidence:** No student turn crosses a boundary, judged across at least three student turns.
- **Insufficient evidence:** If the transcript has fewer than three student turns, the criterion is insufficient.
- **Shows it:**
  - Student: 'I can hear how hard that was. Let's stay with what it's been like for you.'
- **Does not show it:**
  - Student: 'Ugh, same. My ex did exactly that, let me tell you what happened to me.' (shifts the focus to the student)
  - Student: 'I promise I'll fix this for you.' (a promise a counselor cannot keep)
- **Sources:**
  - bogo-osce (adapted). Professional conduct in a simulated interview.
  - cswe-epas-2022 (adapted). Ethical and professional behavior expectations.

#### Levels

| Level | Behavior anchor (grader) | Student sees |
|---|---|---|
| 1 Beginning | Crosses a professional boundary: demeaning or sexualized remarks, long talk about the student's own problems, or promises a counselor could not keep. | Some responses moved away from a professional, client-focused conversation. |
| 2 Emerging | Gives no orientation to role or purpose. The session drifts without direction, and the student ends it abruptly. | The conversation had little structure, with no clear opening or close. |
| 3 Developing | Has some structure, such as a brief opening or a close, but drifts or loses time, and transitions are abrupt. | You gave the session some structure. Clearer transitions and a planned close are the next step. |
| 4 Consistent | Opens with role and purpose, keeps a clear focus, signals transitions, and closes or signals the end when time allows. | Your session had a clear opening, a steady focus and a close. |
| 5 Advanced | Sets purpose and expectations at the start, paces the time, signals each transition, and closes together with the client with a summary and next step when time allows. Language and focus stay professional and on the client throughout. | You ran a well-paced session from a clear opening to a shared close. |

### Scenario-specific competence (20%)

The skills the chosen scenario is built to practice. Each scenario has its own criteria and levels.

#### Routine intake (`routine_intake`)

Building a clear picture of why the client came in, and what they want, while building rapport.

Required for a rating: RI-1.

##### RI-1 Explores the presenting concern

- **Definition:** The student learns what brings the client in, when it started, how it affects daily life, and what the client hopes will change.
- **Opportunity:** The whole intake conversation.
- **Minimum evidence:** Student turns that explore at least three of these four areas: the concern, when it started, its impact and the client's hopes.
- **Insufficient evidence:** If the transcript is too short to explore two or more areas, the criterion is insufficient.
- **Shows it:**
  - Student: 'How has this been affecting your classes and sleep?' followed later by 'If things got better, what would you notice first?'
- **Does not show it:**
  - The student asks only for name, year and major, then ends the session.
- **Sources:**
  - ivey-microskills (adapted). Five-stage interview, story and goals stages.
  - bogo-osce (adapted). Assessment in a first interview with a standardized client.

##### RI-2 Gathers context without interrogating

- **Definition:** The student learns relevant context, such as supports, earlier help and strengths, and keeps responding to the client rather than running through a list.
- **Opportunity:** Any point after the presenting concern is on the table.
- **Minimum evidence:** Two student turns that gather context, and at least one of them that is linked to something the client said.
- **Insufficient evidence:** If the session ended before the concern was explored, the criterion is insufficient.
- **Shows it:**
  - Client: 'My roommate's been great, actually.' Student: 'It sounds like your roommate has been a real support. Who else do you lean on?'
- **Does not show it:**
  - Student asks eight closed background questions in a row without responding to any answer.
- **Sources:**
  - bogo-osce (adapted). Balancing information gathering and engagement.
  - enact-equip (adapted). Exploring the client's supports and strengths.

##### RI-3 Agrees on goals and a next step

- **Definition:** Before the end, the student checks what the client wants from support and agrees on a concrete next step together.
- **Opportunity:** The final part of the session, when time allows a close.
- **Minimum evidence:** One student turn that names or asks about the client's goal, and one that agrees on a next step.
- **Insufficient evidence:** If the time limit ended the session before any close was possible, the criterion is insufficient.
- **Shows it:**
  - Student: 'So you'd like to get back to sleeping through the night. Shall we start there next time?'
- **Does not show it:**
  - Student: 'Okay, that's time. Bye.'
- **Sources:**
  - ivey-microskills (adapted). Five-stage interview, goals and action stages.
  - mi-principles (adapted). Shared planning, cited as a concept.

| Level | Behavior anchor (grader) | Student sees |
|---|---|---|
| 1 Beginning | Interrogates or judges the client, or learns nothing about why the client came in. | The conversation did not get to why the client came in, or felt like an interrogation. |
| 2 Emerging | Gathers facts like a checklist, with little link to the client's story. Key areas such as the concern, its impact or the client's goals are missing. | You collected facts, but the client's own story and goals were mostly missing. |
| 3 Developing | Covers the presenting concern and some context. Impact or goals are thin, and the balance tips toward collecting facts. | You learned what brought the client in. Exploring its impact and their goals is the next step. |
| 4 Consistent | Builds a clear picture of the concern, its impact and the client's goals while staying responsive. Most key areas are covered. | You built a clear picture of the client's concern and goals while staying responsive. |
| 5 Advanced | Covers the concern, its history, impact, supports, strengths and goals in a natural flow, checks understanding with the client, and agrees on a clear next step when time allows. | You covered the full picture in a natural conversation and agreed on a next step together. |

#### Emotionally resistant client (`resistant_client`)

Engaging a client who is reluctant or of two minds, without arguing or pushing. The client's resistance is never scored. Only the student's response to it is.

Required for a rating: RS-1.

##### RS-1 Responds to reluctance without arguing

- **Definition:** When the client pushes back, the student reflects the reluctance or the client's view instead of arguing, warning or trying to persuade.
- **Opportunity:** A client turn that resists, disagrees, minimizes the problem or questions the point of the session.
- **Minimum evidence:** Two student turns that answer pushback with reflection or curiosity, each cited with the client turn it answers.
- **Insufficient evidence:** If the client never pushed back, the criterion is insufficient.
- **Shows it:**
  - Client: 'My drinking isn't a problem. My advisor is overreacting.' Student: 'It feels like this got blown out of proportion, and being sent here is frustrating.'
- **Does not show it:**
  - Client: 'My drinking isn't a problem.' Student: 'Drinking that much is dangerous, and you need to cut back.'
- **Sources:**
  - mi-principles (adapted). Responding to discord, cited as a concept.
  - fis (adapted). Responding to a difficult client, rated from simulated clips.

##### RS-2 Draws out the client's own reasons

- **Definition:** The student asks about and reflects the client's own values, concerns or reasons for change, without supplying the reasons for them.
- **Opportunity:** Any point after the client's view of the problem is on the table.
- **Minimum evidence:** One student turn that asks for the client's own reasons or values, and one that reflects something the client offered.
- **Insufficient evidence:** If the session ended before the client's view was explored, the criterion is insufficient. A client who offers no reasons for change does not lower the rating.
- **Shows it:**
  - Student: 'What matters most to you about how this semester goes?'
  - Client: 'I guess I don't love missing my morning classes.' Student: 'Missing those classes bothers you.'
- **Does not show it:**
  - Student: 'Here are five reasons you should stop.'
- **Sources:**
  - mi-principles (adapted). Evoking the client's own reasons, cited as a concept.

##### RS-3 Repairs strain in the relationship

- **Definition:** When the client shows frustration with the student or the session, the student acknowledges it, adjusts, and keeps the relationship intact.
- **Opportunity:** A client turn that shows frustration with the student, the questions or the session itself.
- **Minimum evidence:** One student turn that acknowledges the strain and adjusts the approach.
- **Insufficient evidence:** If the client never showed frustration with the student or session, the criterion is insufficient.
- **Shows it:**
  - Client: 'This is pointless.' Student: 'You didn't choose to be here, and I've been asking a lot. What would make the next few minutes worth your time?'
- **Does not show it:**
  - Client: 'This is pointless.' Student: 'Well, you have to be here, so let's continue.'
- **Sources:**
  - fis (adapted). Alliance rupture and repair.

| Level | Behavior anchor (grader) | Student sees |
|---|---|---|
| 1 Beginning | Argues with, threatens, shames or ridicules the client for being reluctant. | Some responses argued with the client, which tends to increase pushback. |
| 2 Emerging | Keeps trying to persuade, warn, lecture or give reasons for change, and treats reluctance as something to push past. | You worked hard to convince the client. Exploring their side first is the next step. |
| 3 Developing | Sometimes reflects reluctance, but slips into persuading or advice when the client pushes back. The client's own reasons are rarely explored. | You reflected the client's reluctance at times, but sometimes slipped into persuading. |
| 4 Consistent | Mostly meets reluctance with reflection and curiosity, invites the client's own view and reasons, and avoids arguing. | You met the client's reluctance with curiosity and helped them share their own view. |
| 5 Advanced | Consistently meets reluctance with accurate, nonjudgmental reflection. Draws out and reflects the client's own values and reasons, and adjusts and repairs when tension rises. Never argues for change. Offering information with the client's permission is not arguing. | You stayed steady and curious through the pushback and drew out what matters to the client. |

#### Crisis risk (opt-in) (`crisis_risk`)

Recognizing a disclosure of risk, responding directly and calmly, and putting immediate safety and help first. This rates a practice response. It is not a validated risk assessment (RC-21). Calm means steady wording, without alarm or panic statements. It is never judged from tone of voice.

Required for a rating: CR-1, CR-2, CR-3.

##### CR-1 Recognizes and acknowledges the disclosure

- **Definition:** The student responds directly to the client's disclosure of self-harm, abuse or danger, without changing the subject or minimizing it.
- **Opportunity:** The client turn that discloses self-harm, abuse or imminent danger, and at least one student turn after it.
- **Minimum evidence:** The disclosure turn and the student turn that acknowledges it, both cited.
- **Insufficient evidence:** If no disclosure occurred, or the time limit ended the session with no student turn after it, the criterion is insufficient and the category abstains.
- **Shows it:**
  - Client: 'Sometimes I think everyone would be better off without me.' Student: 'Thank you for telling me that. It sounds like you're in a lot of pain right now.'
- **Does not show it:**
  - Client: 'Sometimes I think everyone would be better off without me.' Student: 'Everyone feels that way sometimes. So, how are classes going?'
- **Sources:**
  - siri-2 (adapted). Facilitative versus dismissive responses to a person at risk.
  - sdd-v1 (original). RC-19: the student must be able to respond to the disclosure.

##### CR-2 Asks directly about risk

- **Definition:** The student asks clearly and calmly about thoughts of harm, intent, plans or immediate danger, in plain words that fit the disclosure.
- **Opportunity:** Any student turn after the disclosure.
- **Minimum evidence:** One student turn that asks directly about risk or immediate danger, cited with the disclosure.
- **Insufficient evidence:** If no disclosure occurred, the criterion is insufficient and the category abstains.
- **Shows it:**
  - Student: 'When you say everyone would be better off without you, are you having thoughts of ending your life?'
  - Client: 'He gets rough when he drinks.' Student: 'Are you safe at home tonight? Is the person who hurt you there now?'
- **Does not show it:**
  - Student: 'You're not going to do anything silly, are you?' (vague, and leads toward 'no')
- **Sources:**
  - siri-2 (adapted). Direct, nonjudgmental inquiry about risk.

##### CR-3 Puts immediate safety and help first

- **Definition:** The student turns to the client's immediate safety: whether they are safe now, who can be with them, and how to reach help now, such as the 988 Suicide and Crisis Lifeline or emergency services. Where it matters, the student is honest about the limits of confidentiality.
- **Opportunity:** Any student turn after the disclosure.
- **Minimum evidence:** One student turn that addresses immediate safety or connects the client with immediate help, cited with the disclosure.
- **Insufficient evidence:** If no disclosure occurred, or the time limit ended the session with no student turn after it, the criterion is insufficient and the category abstains.
- **Shows it:**
  - Student: 'Your safety matters most right now. Is anyone with you tonight? Can we look at calling or texting 988 together?'
  - Student: 'If you're in danger right now, we can call 911 together. Is there somewhere safe you could stay tonight?'
- **Does not show it:**
  - The student acknowledges the disclosure, then spends the rest of the session on study habits.
- **Sources:**
  - siri-2 (adapted). Prioritizing safety in a response to a person at risk.
  - sdd-v1 (original). RC-19 and SDD Fig. 7 crisis resources, including 988.

| Level | Behavior anchor (grader) | Student sees |
|---|---|---|
| 1 Beginning | Any crisis critical failure (see crisis_critical_failures). A critical failure always sets this rating to level 1. | Safety requirement not demonstrated. Your response missed a key safety step for this scenario. Review the safety steps in this report. |
| 2 Emerging | Acknowledges the disclosure but responds vaguely or with euphemisms, or moves on before understanding the risk. Safety steps are weak or late. | You noticed the disclosure, but your response stayed vague about the risk. |
| 3 Developing | Acknowledges the disclosure and asks about risk, but questions are indirect or incomplete. Safety steps or resources come up only briefly. | You acknowledged the disclosure and asked about risk. Being more direct about safety is the next step. |
| 4 Consistent | Responds calmly and directly, asks clearly about risk and how immediate it is, and turns to immediate safety and help that fits what the client said, with minor gaps in empathy shown in words or in follow-through. | You responded directly and calmly and put the client's safety first. |
| 5 Advanced | Responds calmly and with empathy, asks directly about risk, puts immediate safety first, connects the client with help now that fits what they said (including crisis resources such as 988 when appropriate), is honest about confidentiality limits when secrecy or involving others comes up, and stays engaged throughout. | You responded with calm, direct care, put safety first and connected the client with help. |

## Crisis critical failures

Applies to `crisis_risk` only.

- **Precedence:** Any one critical failure makes the safety result 'safety requirement not demonstrated'. That result leads the report, and the average is shown only as a secondary measure. No category rating or average can outweigh it (RC-19, SCO-5).
- **Safety result:** The safety result is 'safety requirement not demonstrated' when any critical failure is found, whatever any category or other rule yields. The result is 'safety requirement met' when CR-1, CR-2 and CR-3 are all sufficient and no critical failure is found. Otherwise the scenario-specific category abstains and no safety result is given.
- **Evidence:** A critical failure cites the disclosure turn and the student turn or turns that show the failure. A failure that rests on the absence of a response cites the disclosure and states that no later student turn addresses it.

### CF-IGNORE Ignoring explicit risk

After an explicit disclosure of self-harm, abuse or danger, no later student turn addresses it, or the student dismisses or minimizes it.

Indicators:

- the student changes the subject right after the disclosure and never returns to it
- the student dismisses or minimizes the disclosure itself, for example 'you don't really mean that', or 'everyone feels like that' with no question about risk after it

Not a failure:

- a brief reflection of feeling before asking about risk
- letting the client finish a thought, then returning to the disclosure
- a normalizing lead-in followed in the same or next student turn by a direct risk question, for example 'When people are in this much pain, they sometimes think about ending their life. Have you had thoughts like that?'

Sources: sdd-v1 (direct); siri-2 (adapted).

### CF-ENCOURAGE Encouraging harm

The student endorses, suggests or agrees with harming oneself or others, or with staying in danger, or gives information that would make harm easier.

Indicators:

- agreeing that harm would be a good or reasonable option
- suggesting a method, or giving information about methods, lethality or how to get means
- telling the client to stay in or return to a dangerous situation

Not a failure:

- reflecting the client's own words, for example 'part of you feels it would be a relief not to be here', as a step toward asking about risk
- asking directly whether the client has a plan or access to means
- talking about putting time or distance between the client and the means, for example asking whether someone could hold the medication

Sources: sdd-v1 (direct); siri-2 (adapted).

### CF-SECRECY Promising secrecy

The student promises to keep a disclosure of risk or abuse confidential without conditions, or agrees not to tell anyone or seek help when safety is at stake.

Indicators:

- 'I promise I won't tell anyone.'
- agreeing to the client's request to keep the danger secret

Not a failure:

- explaining confidentiality and its limits honestly
- asking who the client would want involved, while being clear that safety may require telling someone

Sources: sdd-v1 (direct).

### CF-NO-PRIORITY Failing to prioritize immediate help

After an explicit disclosure, the student never asks about or addresses the client's immediate safety, and never points toward help now, before the session ends.

Indicators:

- the student ends the session after the disclosure without any safety step
- the student moves on to unrelated topics, such as scheduling or study habits, and does not return to safety

Not a failure:

- exploring feelings for a few turns before turning to safety, when the student does turn to it
- a session ended by the time limit with no student turn after the disclosure (the category abstains instead)

Sources: sdd-v1 (direct); siri-2 (adapted).

## Sources

Relation markers: **direct** names the source's concept as is, **adapted** rewrites a concept in original words for a transcript, **original** is written for this project. No item text is reproduced from any instrument.

- **ivey-microskills** (counseling_core_skills). Ivey, A. E., Ivey, M. B., and Zalaquett, C. P. Intentional Interviewing and Counseling (microskills hierarchy and five-stage interview). <https://www.cengage.com/c/intentional-interviewing-and-counseling-facilitating-client-development-in-a-multicultural-society-10e-ivey/>
  - Use: Cited as concepts only (attending, verbal tracking, open and closed questions, paraphrase, reflection of feeling, summary, five-stage interview). No text is reproduced (PA-4).
- **fis** (counseling_core_skills). Anderson, T., Ogles, B. M., Patterson, C. L., Lambert, M. J., and Vermeersch, D. A. (2009). Therapist effects: Facilitative interpersonal skills as a predictor of therapist success. Journal of Clinical Psychology, 65(7), 755-768. <https://www.psykologtidsskriftet.no/asset/article/2021/03/En-norsk-pilotstudie-av-ferdighetstesten-fasiliterende-interpersonlige-ferdigheter/En-norsk-pilotstudie-av-ferdighetstesten-fasiliterende-interpersonlige-ferdigheter.pdf>
  - Use: Research instrument. Its dimensions (empathy, warmth, alliance bond, rupture repair) are cited as concepts. Nothing is copied. The link is the copy the rubric survey used, a 2021 Norwegian pilot study of the FIS test. The citation is the original FIS paper.
- **cts-r** (counseling_core_skills). Blackburn, I.-M., James, I. A., Milne, D. L., Baker, C., Standart, S., Garland, A., and Reichelt, F. K. (2001). The Revised Cognitive Therapy Scale (CTS-R): Psychometric properties. Behavioural and Cognitive Psychotherapy, 29(4), 431-446. <https://psychosisresearch.com/wp-content/uploads/2022/01/CTS-R.pdf>
  - Use: Freely hosted manual. Only its general interpersonal items (agenda, feedback, collaboration, pacing) inform structure and collaboration criteria. CBT-specific items are out of scope.
- **enact-equip** (common_factors). Kohrt, B. A., et al. (2015). Therapist competence in global mental health: Development of the ENhancing Assessment of Common Therapeutic factors (ENACT) rating scale. Behaviour Research and Therapy, 69, 11-21; and the WHO EQUIP competency tools. <https://www.gov.uk/research-for-development-outputs/therapist-competence-in-global-mental-health-development-of-the-enhancing-assessment-of-common-therapeutic-factors-enact-rating-scale>
  - Use: Free via the WHO EQUIP platform (EQUIP paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC9305729). Its method (each level is a list of observable behaviors, with level 1 for harmful behavior) shapes every anchor in this spec. Item text is not reproduced.
- **bogo-osce** (social_work_mft). Bogo, M., Rawlings, M., Katz, E., and Logie, C. (2014). Using Simulation in Assessment and Teaching: OSCE Adapted for Social Work. CSWE Press. <https://socialwork.utoronto.ca/wp-content/uploads/2018/12/OSCE-for-Social-Work.pdf>
  - Use: Cited for format (a timed interview with a standardized client, rated afterward) and for engagement, exploration and collaboration concepts. Nothing is copied.
- **cswe-epas-2022** (social_work_mft). Council on Social Work Education (2022). Educational Policy and Accreditation Standards, Competency 3 (anti-racism, diversity, equity and inclusion) and Competency 6 (engage with individuals). <https://www.siue.edu/artsandsciences/socialwork/about/2022-EPAS.Competencies.pdf>
  - Use: Public competency framework. Cited for cultural humility and engagement expectations.
- **mi-principles** (scenario_specific). Miller, W. R., and Rollnick, S. (2013). Motivational Interviewing: Helping People Change (3rd ed.). Guilford Press. <https://www.guilford.com/books/Motivational-Interviewing/Miller-Rollnick/9781609182274>
  - Use: Selected principles (partnership, autonomy support, responding to discord, eliciting the client's own reasons) are cited as concepts for the resistant-client scenario. No coding manual is used and no rating is presented as a coded MI measure (RC-18, AG-5).
- **siri-2** (scenario_specific). Neimeyer, R. A., and Bonnelle, K. (1997). The Suicide Intervention Response Inventory: A revision and validation. Death Studies, 21(1), 59-81. <https://nsuworks.nova.edu/cps_facarticles/1355>
  - Use: Research instrument. Its distinction between facilitative and harmful helper responses to a person at risk informs the crisis criteria and critical failures. No items are reproduced.
- **sdd-v1** (project_requirement). CaseStudy Tech Software Design Document v1.0, sections 2.2 and 4.5 (RC-17, RC-18, RC-19). <https://github.com/sandythomas1/Case-Study-Tech/blob/dev/output/CSCI_5520_CaseStudy_Tech_Software_Design_Document_Final.pdf>
  - Use: Project requirement. Cited where a criterion or critical failure comes straight from a requirement rather than from an instrument.

## Excluded sources

- **ccs-r**, Counselor Competencies Scale-Revised (Lambie et al.). Copyrighted. The owner chose free instruments only (PA-4). No item text or level wording from it appears in this spec.
- **miti-manual**, Motivational Interviewing Treatment Integrity coding manual. The manual is marked draft and is not cited without permission (PA-4). Ratings in this spec are never presented as a coded MI measure (RC-18).
