import os
import logging
from typing import Dict, List
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
from config import config

logger = logging.getLogger(__name__)


class MongoDB:
    def __init__(self):
        self.client = MongoClient(config.MONGODB_URI)
        self.db = self.client["telegram_quiz_bot"]
        self.users = self.db["users"]
        self.channels = self.db["channels"]
        self.groups = self.db["groups"]
        self.polls = self.db["polls"]
        self.auth_users = self.db["auth_users"]
        logger.info("✅ MongoDB connected")

    # ── User Settings ────────────────────────────────────────────────────────

    def get_user_settings(self, user_id: int) -> Dict:
        user = self.users.find_one({"user_id": user_id})
        if not user:
            default_settings = {
                "user_id": user_id,
                "quiz_marker": config.DEFAULT_QUIZ_MARKER,
                "explanation_tag": config.DEFAULT_EXPLANATION_TAG,
                "pdf_mode": config.DEFAULT_PDF_MODE,
                "created_at": datetime.now(),
            }
            self.users.insert_one(default_settings)
            return default_settings

        # Back-fill any keys added after initial creation
        updated = False
        defaults = {
            "quiz_marker": config.DEFAULT_QUIZ_MARKER,
            "explanation_tag": config.DEFAULT_EXPLANATION_TAG,
            "pdf_mode": config.DEFAULT_PDF_MODE,
        }
        for key, val in defaults.items():
            if key not in user:
                user[key] = val
                updated = True
        if updated:
            self.users.update_one(
                {"user_id": user_id},
                {"$set": {k: v for k, v in defaults.items() if k not in user}},
            )
        return user

    def update_user_settings(self, user_id: int, key: str, value: str):
        self.users.update_one(
            {"user_id": user_id},
            {"$set": {key: value, "updated_at": datetime.now()}},
            upsert=True,
        )

    # ── Channels / Groups ────────────────────────────────────────────────────

    def add_channel(self, user_id: int, channel_id: int, channel_name: str):
        existing = self.channels.find_one({"user_id": user_id, "channel_id": channel_id})
        if existing:
            self.channels.update_one(
                {"_id": existing["_id"]},
                {"$set": {"channel_name": channel_name, "updated_at": datetime.now()}},
            )
        else:
            self.channels.insert_one(
                {
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "type": "channel",
                    "created_at": datetime.now(),
                }
            )

    def add_group(self, user_id: int, group_id: int, group_name: str):
        existing = self.groups.find_one({"user_id": user_id, "group_id": group_id})
        if existing:
            self.groups.update_one(
                {"_id": existing["_id"]},
                {"$set": {"group_name": group_name, "updated_at": datetime.now()}},
            )
        else:
            self.groups.insert_one(
                {
                    "user_id": user_id,
                    "group_id": group_id,
                    "group_name": group_name,
                    "type": "group",
                    "created_at": datetime.now(),
                }
            )

    def get_user_channels(self, user_id: int) -> List[Dict]:
        return list(self.channels.find({"user_id": user_id}))

    def get_user_groups(self, user_id: int) -> List[Dict]:
        return list(self.groups.find({"user_id": user_id}))

    def delete_channel(self, channel_doc_id: str):
        self.channels.delete_one({"_id": ObjectId(channel_doc_id)})

    def delete_group(self, group_doc_id: str):
        self.groups.delete_one({"_id": ObjectId(group_doc_id)})


    # ── Authorization ────────────────────────────────────────────────────────

    def is_user_authorized(self, user_id: int) -> bool:
        """Return True if user_id is allowed to use the bot.
        Owner (from env) is always authorized.
        If PUBLIC_ACCESS env is 'true', everyone is authorized.
        Otherwise checks auth_users collection.
        """
        import os
        if os.getenv("PUBLIC_ACCESS", "false").lower() == "true":
            return True
        owner_id_str = os.getenv("OWNER_ID", "")
        if owner_id_str:
            try:
                if user_id == int(owner_id_str):
                    return True
            except ValueError:
                pass
        doc = self.auth_users.find_one({"user_id": user_id})
        return doc is not None

    def add_authorized_user(self, user_id: int, added_by: int = None, role: str = "user"):
        """Add or update a user in the auth list."""
        self.auth_users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "role": role,
                    "added_by": added_by,
                    "updated_at": datetime.now(),
                },
                "$setOnInsert": {"created_at": datetime.now()},
            },
            upsert=True,
        )
        logger.info(f"Auth: user {user_id} added with role={role} by {added_by}")

    def remove_authorized_user(self, user_id: int) -> bool:
        """Remove a user from the auth list. Returns True if deleted."""
        result = self.auth_users.delete_one({"user_id": user_id})
        removed = result.deleted_count > 0
        if removed:
            logger.info(f"Auth: user {user_id} removed")
        return removed

    def list_authorized_users(self) -> List[Dict]:
        """Return all authorized users."""
        return list(self.auth_users.find({}, {"_id": 0}))

    # ── Poll Collection ──────────────────────────────────────────────────────

    def store_poll(self, user_id: int, poll_id: str, poll_data: Dict):
        self.polls.update_one(
            {"poll_id": poll_id},
            {
                "$set": {
                    "user_id": user_id,
                    "poll_id": poll_id,
                    "data": poll_data,
                    "updated_at": datetime.now(),
                }
            },
            upsert=True,
        )

    def get_user_polls(self, user_id: int) -> List[Dict]:
        return list(self.polls.find({"user_id": user_id}))

    def clear_user_polls(self, user_id: int):
        self.polls.delete_many({"user_id": user_id})


db = MongoDB()
