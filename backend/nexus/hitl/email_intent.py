"""Did the prompt ask for the result by email, and to whom?

Results are emailed only when the request says so: "... and send the output to
boss@example.com", "email me the result", "... and also share email". Addresses in
the prompt are the targets; "me" / no address means the owner's own address (the
Google account they signed in with, or Settings → Email results). The clause is
removed from the task the agents see, so a blog post never talks about emailing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Bounded (RFC 5321 limits) and anchored at the start of a run, so matching stays linear
# even on hostile input such as thousands of "a." (CodeQL py/polynomial-redos).
ADDRESS = re.compile(r"(?<![\w.+-])[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63}){1,8}")
VERB = r"(?:send|e-?mail|mail|share|forward|deliver)"
CONNECTOR = r"(?:\s*(?:,|\band\b|\balso\b|\bthen\b|\bplease\b|\bpls\b))*\s*"
FILLER = (
    r"(?:outputs?|results?|answer|report|summary|ticket|page|link|myself|final|full|whole|"
    r"the|this|that|them|it|me|my|an|a|over|back|via|by|through|as|in|on|e-?mail|mail|"
    r"inbox|to|too|also|please)"
)
# "send (the output|it) to x@y.com", "email it to me", "send the result to my email"
REQUEST = re.compile(
    CONNECTOR
    + rf"\b{VERB}\b"
    + rf"(?:\s+{FILLER}\b(?!@))*"
    + r"(?:\s*:?\s*"
    + ADDRESS.pattern
    + r"(?:\s*(?:,|\band\b)\s*"
    + ADDRESS.pattern
    + r")*)?",
    re.I,
)
TARGET = re.compile(r"\b(me|my|myself|outputs?|results?|answer|report|summary|ticket|it)\b", re.I)
SHARE_EMAIL = re.compile(r"\b(and|also|then)\s+(?:also\s+)?share\s+(?:an?\s+)?e-?mail\b", re.I)
SELF_WORDS = re.compile(r"\b(me|my|myself|e-?mail|mail|inbox)\b", re.I)


@dataclass
class EmailRequest:
    requested: bool = False
    to: list[str] = field(default_factory=list)
    to_self: bool = False
    task: str = ""


def email_request(task: str) -> EmailRequest:
    addresses = list(dict.fromkeys(ADDRESS.findall(task)))
    best: re.Match[str] | None = None
    for m in REQUEST.finditer(task):
        text = m.group(0)
        after_verb = re.split(rf"\b{VERB}\b", text, maxsplit=1, flags=re.I)[-1]
        # "email marketing" / "send an email with Python" are topics, not requests:
        # a request names a target (an address, me/my) or the thing to deliver
        if ADDRESS.search(text) or TARGET.search(after_verb) or SHARE_EMAIL.search(text):
            best = m
            break
    if best is None and not addresses:
        return EmailRequest(task=task)
    if best is None:  # an address with no verb is just text (e.g. "contact a@b.com")
        return EmailRequest(task=task)
    cleaned = (task[: best.start()] + task[best.end() :]).strip(" ,.;:") or task
    in_clause = ADDRESS.findall(best.group(0))
    to = list(dict.fromkeys(in_clause or addresses))
    to_self = not to and bool(SELF_WORDS.search(best.group(0)))
    return EmailRequest(requested=bool(to) or to_self, to=to, to_self=to_self, task=cleaned)
