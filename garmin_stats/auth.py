"""Authentication for Garmin Connect.

Resumes cached OAuth tokens when available, otherwise falls back to an
interactive login (email / password / MFA). `Garmin.login(tokenstore)`
persists the tokens itself on a credential login, so subsequent runs
restore without prompting.
"""

from __future__ import annotations

import getpass
import os

from garminconnect import Garmin

# Where garminconnect stores the OAuth tokens.
TOKENSTORE = os.path.expanduser("~/.garminconnect")


def get_client() -> Garmin:
    """Return an authenticated Garmin client.

    Tries to resume from cached tokens first; if that fails, prompts for
    credentials interactively. login() writes the tokens to TOKENSTORE on a
    fresh credential login, so this only prompts once.
    """
    # Token-only resume: with no credentials, login() raises immediately
    # (no network call) if the tokenstore is empty/invalid.
    client = Garmin()
    try:
        client.login(TOKENSTORE)
        return client
    except Exception:
        return _interactive_login()


def _interactive_login() -> Garmin:
    email = input("Garmin email: ").strip()
    password = getpass.getpass("Garmin password: ")

    client = Garmin(
        email=email,
        password=password,
        prompt_mfa=lambda: input("MFA code: ").strip(),
    )
    # Passing the tokenstore path makes login() persist tokens after a
    # successful credential login.
    client.login(TOKENSTORE)
    return client
