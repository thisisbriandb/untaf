"""
Le nom d'un employeur dans les phrases d'Alice (journal, e-mails).

Même règle que l'interface (frontend/lib/company.ts) : un employeur anonyme
ne s'écrit pas « chez Employeur non précisé », et une raison sociale en
capitales redevient un nom.
"""

import re

_ANONYMOUS = re.compile(r"^(employeur|entreprise)\s+non\s+pr[ée]cis[ée]e?$", re.I)
_SMALL = {"de", "du", "des", "la", "le", "les", "et", "en", "à", "au", "aux", "d", "l"}
_LEGAL = {"sas", "sarl", "sa", "eurl", "sasu", "sci"}


def display_company(name: str | None) -> str | None:
    """Le nom lisible, ou None quand l'employeur n'est pas communiqué."""
    n = (name or "").strip()
    if not n or _ANONYMOUS.match(n):
        return None
    letters = re.sub(r"[^\w]|\d|_", "", n)
    if letters != letters.upper():
        return n
    if " " not in n and len(letters) <= 5:
        return n  # sigle : SNCF, EDF
    parts = re.split(r"(\s+|-|')", n.lower())
    out = []
    for i, w in enumerate(parts):
        if not re.search(r"\w", w):
            out.append(w)
        elif i > 0 and w in _SMALL:
            out.append(w)
        elif w in _LEGAL:
            out.append(w.upper())
        else:
            out.append(w[:1].upper() + w[1:])
    return "".join(out)


def chez(name: str | None) -> str:
    """« chez Acme », ou rien quand l'employeur est anonyme."""
    c = display_company(name)
    return f" chez {c}" if c else ""
