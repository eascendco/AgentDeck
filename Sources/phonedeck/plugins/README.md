# AI plugins

Each file here feeds the AI page: one AI tool's plan limits or credits, the agent sessions running
on your Mac, or GitHub. Add your own by copying `_template.py` into `~/.phonedeck/plugins/`,
renaming it (say `gemini.py`) and filling it in. No rebuild: PhoneDeck picks it up on the next refresh.
A file in `~/.phonedeck/plugins/` with the same name as a shipped one replaces it.

## Shipped

| File | Shows | Needs |
|---|---|---|
| `claude.py` | Claude 5-hour and weekly limits | Claude Code signed in with a Pro or Max plan |
| `codex.py` | Codex 5-hour and weekly limits, as of your last Codex turn | Codex used at least once |
| `openrouter.py` | OpenRouter credit balance | Keychain item `openrouter` or `OPENROUTER_API_KEY` |
| `fal.py` | fal.ai balance | Keychain item `fal` (an admin key) or `FAL_KEY` |
| `elevenlabs.py` | ElevenLabs credits this billing period | Keychain item `elevenlabs` or `ELEVENLABS_API_KEY` |
| `claude_code.py` | Running Claude Code sessions: folder, working or idle, model, context, last prompt | Claude Code |
| `agents_running.py` | Codex, OpenCode, Gemini CLI, Grok CLI, Cursor agent, Antigravity, Aider, Goose and Amp processes and their folders | Nothing |
| `herdr.py` | Space and tab names for agents run in [Herdr](https://herdr.dev) | Herdr (optional) |
| `github.py` | Your open PRs with CI and review state, and PRs waiting on your review | `gh auth login` |

Store a key in the Keychain with:

```bash
security add-generic-password -s openrouter -a "$USER" -w 'sk-or-...'
```

Turn a plugin off without deleting it: `~/.phonedeck/ai.json`

```json
{ "disabled": ["fal"], "refreshMinutes": 5 }
```

## The format

A plugin is any program that prints one JSON object on its last line and exits within 30 seconds.
`.py` files run with `/usr/bin/python3` (there whenever the Xcode Command Line Tools are, which
PhoneDeck needs anyway), `.sh` with `/bin/sh`, anything else directly. It gets your login shell's
`PATH`, so `claude`, `gh` and friends are found. Files starting with `_` are skipped.

Every reply has:

| Field | |
|---|---|
| `type` | `"quota"`, `"credits"`, `"sessions"` or `"github"` |
| `id`, `name` | `"gemini"`, `"Gemini"` |
| `available` | `false` when the tool isn't installed or set up. Add `"setup": "how to set it up"` |
| `error` | Optional. Shown instead of numbers; the last good numbers stay, dimmed |
| `color` | Optional bar color, `"#4285F4"` |

**Limits** (`"type": "quota"`): `"windows": [{ "label": "5 h", "used": 42, "resetsAt": ..., "windowSeconds": 18000 }]`.
`used` is a percent. `resetsAt` is ISO 8601 or epoch seconds or milliseconds. With `windowSeconds`, the
deck adds "at this pace full in 2 h 10 min" when you'd hit the limit before it resets.

**Credits** (`"type": "credits"`): `"credits": { "left": 100.87, "total": 138.51, "unit": "$", "resetsAt": ... }`.
`total` and `resetsAt` are optional; `unit` is `"$"` or a word like `"credits"`.

**Sessions** (`"type": "sessions"`): `"sessions": [{ "id", "pid", "group", "title", "status", "app", "model", "tokens", "cwd" }]`.
`status` is `working`, `waiting` (needs you), `running` (unknown), `done` or `idle`. `group` is the
heading it's listed under (usually the project folder). Add `"enrich": true` to the reply when your
plugin describes sessions another plugin already lists (as `herdr.py` does): the deck matches them
by `pid` and uses your `group`, `title` and `status`.

**GitHub** (`"type": "github"`): `"prs": [{ "repo", "number", "title", "url", "ci": "pass|fail|running|none", "review": "approved|changes|waiting", "draft" }]`
and `"reviews": [{ "repo", "number", "title", "url" }]`.

Test one with `python3 ~/.phonedeck/plugins/gemini.py`, or open `/ai?k=<your code>` on the Mac to see
what the deck gets.

## Privacy

Plugins run on your Mac and only while a deck is showing the AI page. Keys stay in the Keychain;
the phone gets the numbers, never a key. The deck page needs the access code like every other API call.
Sessions show your last prompt, so anyone who can see the phone can read it.
