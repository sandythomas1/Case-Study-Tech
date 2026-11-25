# Interim persona prompts

These three prompts are **interim**. They are short, synthetic placeholders so the session service
can run text turns (#31), and #67 replaces them with the vetted persona prompts and the scripted
runner. No real client, name or case appears in them.

- One file per scenario, named after its id in `../configs/`: `routine_intake.txt`,
  `resistant_client.txt` and `crisis_risk.txt`.
- `cst_session/scenarios/prompts.py` loads them once at startup. It accepts exactly these three
  files, UTF-8 with no byte-order mark, not blank, at most 1,500 characters, and no control or
  format characters except tab and newline. Anything else stops the service.
- A prompt goes to the model only as the system instruction for its own scenario, the same text on
  every turn. It is never shown to the student and never stored in the session state.
- Each prompt keeps the client in role, keeps replies short, and never coaches, scores or hints
  (POLICY SES-7). The crisis prompt keeps the conversation going after a disclosure (SES-8).
- Prompts change only through a reviewed commit. Nothing writes these files.
