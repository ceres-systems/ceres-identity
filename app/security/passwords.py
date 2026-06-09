import bcrypt


def hash_password(plain: str) -> str:
    digest = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())
    return digest.decode("ascii")


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False
