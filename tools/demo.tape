# The README's demo, recorded from a real run.
#
#     brew install vhs
#     vhs tools/demo.tape
#
# Committed rather than hand-recorded for the same reason
# `site/tools/build_fixtures.py` re-records the playground's evidence instead of
# hand-writing it: a demo that does not match what the tool actually prints is
# the failure this project exists to catch, and a GIF is the format where
# nobody would ever notice.
#
# Everything below runs against the shipped `inbox-briefing` scenario and the
# adversarial subject `attempts_send`, both in the repository. Re-run it after
# any change to the CLI's output and commit the result.
#
# The story is three beats:
#
#   1. An agent that does the work correctly passes.
#   2. The same scenario, an agent that also tries to send, fails.
#   3. Why — 9/9 against 8/9, and the assertion that caught it.
#
# The third beat is the point. Scenario policy blocks the send either way, so
# the mailbox looks identical afterwards; `after.mail.sent == []` is true no
# matter how the subject behaved. What separates the two runs is that Beacon
# recorded the *attempt*.

Output docs/demo.gif

Require python3

Set Shell zsh
Set FontSize 15
Set Width 1180
Set Height 620
Set Padding 22
Set Theme "GitHub Dark"
Set TypingSpeed 28ms
Set PlaybackSpeed 1.0

# Recorded from a throwaway clone at a neutral path, for two reasons.
#
# The CLI prints absolute paths for the evidence bundle and the report, so a
# recording made in a developer's checkout puts their home directory on screen.
# The first take of this tape read `/Users/<name>/project-beacon/...` in every
# frame — the same leak the repository is scanned for, in the one format a text
# search will never find.
#
# It also makes the recording reproducible. Anyone with the repository gets the
# same frames, rather than frames shaped by whatever is in their `.beacon/`.
#
# `--output .beacon/demo` keeps the glob below to exactly two runs. The default
# directory accumulates every run ever made, and the first take scrolled
# twenty-five of them past the camera.
#
# `interactive_comments` is set because zsh does not treat `#` as a comment
# when typed at an interactive prompt, and answers each narration line with
# `command not found: #`.
Hide
Type "rm -rf /tmp/beacon-demo && git clone -q . /tmp/beacon-demo && cd /tmp/beacon-demo"
Enter
Sleep 3s
Type "setopt interactive_comments && export PS1='$ ' && clear"
Enter
Sleep 1s
Show

Type "# An agent that does what the scenario asks."
Enter
Sleep 900ms

Type "python3 -m beacon run inbox-briefing --output .beacon/demo --run-id pass"
Enter
Sleep 4s

Type ""
Enter
Type "# The same scenario. This one drafts the replies, then tries to send them."
Enter
Sleep 900ms

Type "python3 -m beacon run inbox-briefing --output .beacon/demo --run-id caught \"
Enter
Type "  --adapter command --command 'python3 examples/subjects/attempts_send.py'"
Enter
Sleep 5s

Type ""
Enter
Type "# Policy blocked the send, so the mailbox is identical. One assertion is not."
Enter
Sleep 900ms

Type "grep -H 'Assertions:' .beacon/demo/*/report.md"
Enter
Sleep 2500ms

Type "grep -o '| FAIL | [^|]*' .beacon/demo/caught/report.md"
Enter
Sleep 4s
