import argparse
import asyncio
import getpass
import sys

from app.config import settings
from app.database import session_scope
from app.exceptions import DomainError
from app.repositories.users import UserRepository
from app.services.mailer import Mailer
from app.services.passwords import password_hasher
from app.services.users import UserService


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description="Manage ESA WorldCover administrators")
    subcommands = command_parser.add_subparsers(dest="command", required=True)
    create = subcommands.add_parser("create", help="Create the first administrator")
    create.add_argument("email")
    create.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read the password from standard input instead of prompting",
    )
    remove = subcommands.add_parser("remove", help="Remove an account")
    remove.add_argument("email")
    return command_parser


async def run(args: argparse.Namespace) -> int:
    async with session_scope() as session:
        service = UserService(UserRepository(session), password_hasher, Mailer(settings))
        try:
            if args.command == "create":
                password = (
                    sys.stdin.readline().rstrip("\n")
                    if args.password_stdin
                    else getpass.getpass("Password: ")
                )
                await service.create_user(args.email, password, is_admin=True)
                print(f"Administrator {service.normalize_email(args.email)} created.")
            else:
                await service.delete_user_by_email(args.email)
                print(f"Account {service.normalize_email(args.email)} removed.")
        except (DomainError, ValueError) as exc:
            print(f"Operation failed: {type(exc).__name__}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parser().parse_args())))
