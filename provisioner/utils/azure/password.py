"""Azure SQL password generation.

Azure SQL Server requires the admin password to satisfy a complexity policy:
  - Length 8–128
  - Three of: uppercase, lowercase, digit, non-alphanumeric
  - Cannot match the login name

Templates that need an admin password should call `gen_sql_password()` for a
fallback when the deployer didn't supply one via config. Never hardcode a
default password string in template code — that's how the original
`P@ssw0rd!2024` defaults sat in the public repo for months.

The generated value is stable for the lifetime of the Pulumi stack (lives in
state) but unique per deploy.
"""

import secrets
import string


def gen_sql_password(length: int = 24) -> str:
    """Generate a SQL Server-policy-compliant random password.

    Guarantees at least one upper, one lower, one digit, one symbol; rest is
    drawn from the full alphabet. Uses `secrets` (CSPRNG)."""
    if length < 8:
        length = 8
    if length > 128:
        length = 128

    upper = secrets.choice(string.ascii_uppercase)
    lower = secrets.choice(string.ascii_lowercase)
    digit = secrets.choice(string.digits)
    # Symbols Azure SQL accepts — exclude characters that break connection strings.
    symbols = "!@#$%^&*()_+-="
    symbol = secrets.choice(symbols)

    alphabet = string.ascii_letters + string.digits + symbols
    rest = "".join(secrets.choice(alphabet) for _ in range(length - 4))

    # Shuffle the four required chars + filler so the policy chars aren't
    # always at the front.
    chars = list(upper + lower + digit + symbol + rest)
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)
