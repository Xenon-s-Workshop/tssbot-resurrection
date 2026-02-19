import os
from typing import Dict, List
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
from config import config
from processors.deepseek_processor import DEEPSEEK_MODELS

class MongoDB:
    def __init__(self):
        self.client = MongoClient(config.MONGODB_URI)
        self.db = self.client['telegram_quiz_bot']
        self.users = self.db['users']
        self.channels = self.db['channels']
        self.groups = self.db['groups']
        self.authorized_users = self.db['authorized_users']
        print("✅ MongoDB connected")
        self._init_sudo_users()
    
    def _init_sudo_users(self):
        for user_id in config.SUDO_USER_IDS:
            self.authorized_users.update_one(
                {'user_id': user_id},
                {'$set': {'user_id': user_id, 'is_sudo': True, 'authorized_at': datetime.now()}},
                upsert=True
            )
    
    def is_authorized(self, user_id: int) -> bool:
        if not config.AUTH_ENABLED:
            return True
        return self.authorized_users.find_one({'user_id': user_id}) is not None
    
    def is_sudo(self, user_id: int) -> bool:
        user = self.authorized_users.find_one({'user_id': user_id})
        return user and user.get('is_sudo', False)
    
    def authorize_user(self, user_id: int, authorized_by: int):
        self.authorized_users.update_one(
            {'user_id': user_id},
            {'$set': {'user_id': user_id, 'authorized_by': authorized_by,
                      'authorized_at': datetime.now(), 'is_sudo': False}},
            upsert=True
        )
    
    def revoke_user(self, user_id: int):
        self.authorized_users.delete_one({'user_id': user_id})
    
    def get_authorized_users(self) -> List[Dict]:
        return list(self.authorized_users.find({}))
    
    def get_user_settings(self, user_id: int) -> Dict:
        user = self.users.find_one({'user_id': user_id})
        if not user:
            default = {
                'user_id': user_id,
                'quiz_marker': os.getenv("QUIZ_MARKER", "[TSS]"),
                'explanation_tag': os.getenv("EXPLANATION_TAG", "t.me/tss"),
                # AI Provider settings
                'ai_provider': 'gemini',        # 'gemini' or 'deepseek'
                'deepseek_model': DEEPSEEK_MODELS[7],  # Default: DeepSeek-R1
                'created_at': datetime.now()
            }
            self.users.insert_one(default)
            return default
        # Ensure existing users have new fields
        updated = False
        if 'ai_provider' not in user:
            user['ai_provider'] = 'gemini'
            updated = True
        if 'deepseek_model' not in user:
            user['deepseek_model'] = DEEPSEEK_MODELS[7]
            updated = True
        if updated:
            self.users.update_one(
                {'user_id': user_id},
                {'$set': {'ai_provider': user['ai_provider'], 'deepseek_model': user['deepseek_model']}}
            )
        return user
    
    def update_user_settings(self, user_id: int, key: str, value):
        self.users.update_one(
            {'user_id': user_id},
            {'$set': {key: value, 'updated_at': datetime.now()}},
            upsert=True
        )
    
    def set_ai_provider(self, user_id: int, provider: str):
        """Toggle between gemini and deepseek"""
        self.update_user_settings(user_id, 'ai_provider', provider)
    
    def set_deepseek_model(self, user_id: int, model: str):
        """Set preferred DeepSeek model"""
        self.update_user_settings(user_id, 'deepseek_model', model)
    
    def add_channel(self, user_id: int, channel_id: int, channel_name: str):
        existing = self.channels.find_one({'user_id': user_id, 'channel_id': channel_id})
        if existing:
            self.channels.update_one({'_id': existing['_id']}, {'$set': {'channel_name': channel_name}})
        else:
            self.channels.insert_one({'user_id': user_id, 'channel_id': channel_id,
                                      'channel_name': channel_name, 'created_at': datetime.now()})
    
    def add_group(self, user_id: int, group_id: int, group_name: str):
        existing = self.groups.find_one({'user_id': user_id, 'group_id': group_id})
        if existing:
            self.groups.update_one({'_id': existing['_id']}, {'$set': {'group_name': group_name}})
        else:
            self.groups.insert_one({'user_id': user_id, 'group_id': group_id,
                                    'group_name': group_name, 'created_at': datetime.now()})
    
    def get_user_channels(self, user_id: int) -> List[Dict]:
        return list(self.channels.find({'user_id': user_id}))
    
    def get_user_groups(self, user_id: int) -> List[Dict]:
        return list(self.groups.find({'user_id': user_id}))
    
    def delete_channel(self, channel_doc_id: str):
        self.channels.delete_one({'_id': ObjectId(channel_doc_id)})
    
    def delete_group(self, group_doc_id: str):
        self.groups.delete_one({'_id': ObjectId(group_doc_id)})

db = MongoDB()
