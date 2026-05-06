# Studio AI Prompts

Reference prompts for generating Archie blueprints via Studio → Generate. Each
file is a self-contained prompt that produces a working, deployable blueprint
with `temperature: 0` and the current Studio system prompt rules.

## Why these are versioned

Studio AI is non-deterministic across model + system-prompt versions. A prompt
that produced clean code on Monday may produce broken code on Tuesday after a
model upgrade. Pinning the working prompts here gives you:

- A reproducible starting point for demos
- A diff-able record when a prompt stops working (model regression, system
  prompt change)
- Shareable templates for customers / users group sessions

## Usage

1. Open Studio → Generate
2. Paste the prompt verbatim
3. Verify the resulting blueprint deploys (HTTP 200 / resources up)
4. If the blueprint breaks, file an issue with the date + the diff vs the
   prompt that last worked

## Conventions

- One prompt per file, named after what it produces
- Keep the "Implementation requirement" notes — they steer the AI away from
  common pitfalls (nested f-strings, brace-escape bugs, etc.)
- If you tweak a prompt, update the file rather than creating a new one;
  prompts are meant to be the canonical version
