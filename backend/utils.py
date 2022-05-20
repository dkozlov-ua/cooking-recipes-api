import secrets
import string


def generate_secret_key(length: int = 128) -> str:
    if length < 16:
        raise ValueError('Secret key with less then 16 symbols is not secure')
    alphabet = string.ascii_letters + string.digits
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        if (
                any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and sum(c.isdigit() for c in password) >= 3
        ):
            return password
