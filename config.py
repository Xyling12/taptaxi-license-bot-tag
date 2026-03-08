"""Configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    bot_token: str = ""
    admin_ids: List[int] = field(default_factory=list)
    secret_key: str = ""
    db_path: str = "data/licenses.db"
    auto_approve: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        raw_admins = os.getenv("ADMIN_IDS", "")
        admin_ids = [int(x.strip()) for x in raw_admins.split(",") if x.strip()]
        auto_approve = os.getenv("AUTO_APPROVE", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        return cls(
            bot_token=os.getenv("BOT_TOKEN", ""),
            admin_ids=admin_ids,
            secret_key=os.getenv("SECRET_KEY", ""),
            db_path=os.getenv("DB_PATH", "data/licenses.db"),
            auto_approve=auto_approve,
        )

    def validate(self) -> List[str]:
        errors = []
        if not self.bot_token:
            errors.append("BOT_TOKEN is required")
        if not self.auto_approve and not self.admin_ids:
            errors.append("ADMIN_IDS is required when AUTO_APPROVE=false")
        if not self.secret_key or len(self.secret_key) < 32:
            errors.append("SECRET_KEY must be at least 32 characters")
        return errors
