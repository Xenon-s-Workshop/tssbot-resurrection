"""
Database Module - MongoDB Integration
Handles user authorization, channels, groups, and settings
WITH DEFAULT DESTINATION SUPPORT
"""

from pymongo import MongoClient
from config import config

class Database:
    def __init__(self):
        self.client = MongoClient(config.MONGODB_URI)
        self.db = self.client['tss_bot']
        
        # Initialize collections
        self.users = self.db.users
        self.channels = self.db.channels
        self.groups = self.db.groups
        self.user_settings = self.db.user_settings
        
        print("✅ MongoDB connected")
        
        # Initialize sudo users
        for user_id in config.SUDO_USER_IDS:
            self.authorize_user(user_id)
        print(f"✅ {len(config.SUDO_USER_IDS)} sudo users initialized")
    
    # ==================== USER AUTHORIZATION ====================
    
    def is_user_authorized(self, user_id: int) -> bool:
        """Check if user is authorized"""
        if not config.AUTH_ENABLED:
            return True
        return self.users.find_one({'user_id': user_id}) is not None
    
    def authorize_user(self, user_id: int):
        """Authorize a user"""
        self.users.update_one(
            {'user_id': user_id},
            {'$set': {'user_id': user_id, 'authorized': True}},
            upsert=True
        )
    
    def revoke_user(self, user_id: int):
        """Revoke user authorization"""
        self.users.delete_one({'user_id': user_id})
    
    def get_authorized_users(self):
        """Get all authorized users"""
        return list(self.users.find())
    
    # ==================== CHANNELS ====================
    
    def add_channel(self, user_id: int, channel_id: int, channel_name: str):
        """Add a channel"""
        self.channels.insert_one({
            'user_id': user_id,
            'channel_id': channel_id,
            'channel_name': channel_name
        })
    
    def get_user_channels(self, user_id: int):
        """Get user's channels"""
        return list(self.channels.find({'user_id': user_id}))
    
    def delete_channel(self, channel_id: str):
        """Delete a channel by MongoDB _id"""
        from bson.objectid import ObjectId
        self.channels.delete_one({'_id': ObjectId(channel_id)})
    
    # ==================== GROUPS ====================
    
    def add_group(self, user_id: int, group_id: int, group_name: str):
        """Add a group"""
        self.groups.insert_one({
            'user_id': user_id,
            'group_id': group_id,
            'group_name': group_name
        })
    
    def get_user_groups(self, user_id: int):
        """Get user's groups"""
        return list(self.groups.find({'user_id': user_id}))
    
    def delete_group(self, group_id: str):
        """Delete a group by MongoDB _id"""
        from bson.objectid import ObjectId
        self.groups.delete_one({'_id': ObjectId(group_id)})
    
    # ==================== USER SETTINGS ====================
    
    def get_user_settings(self, user_id: int) -> dict:
        """Get user settings"""
        settings = self.user_settings.find_one({'user_id': user_id})
        
        if not settings:
            # Create default settings
            settings = {
                'user_id': user_id,
                'quiz_marker': '🎯',
                'explanation_tag': 'Exp'
            }
            self.user_settings.insert_one(settings)
        
        return settings
    
    def update_user_settings(self, user_id: int, settings: dict):
        """Update user settings"""
        self.user_settings.update_one(
            {'user_id': user_id},
            {'$set': settings},
            upsert=True
        )
    
    # ==================== DEFAULT DESTINATIONS ====================
    
    def set_default_channel(self, user_id: int, channel_id: int):
        """Set default channel for user"""
        self.user_settings.update_one(
            {'user_id': user_id},
            {'$set': {'default_channel': channel_id}},
            upsert=True
        )
    
    def set_default_group(self, user_id: int, group_id: int):
        """Set default group for user"""
        self.user_settings.update_one(
            {'user_id': user_id},
            {'$set': {'default_group': group_id}},
            upsert=True
        )
    
    def get_default_channel(self, user_id: int):
        """Get default channel"""
        settings = self.user_settings.find_one({'user_id': user_id})
        return settings.get('default_channel') if settings else None
    
    def get_default_group(self, user_id: int):
        """Get default group"""
        settings = self.user_settings.find_one({'user_id': user_id})
        return settings.get('default_group') if settings else None
    
    def clear_default_channel(self, user_id: int):
        """Clear default channel"""
        self.user_settings.update_one(
            {'user_id': user_id},
            {'$unset': {'default_channel': ''}}
        )
    
    def clear_default_group(self, user_id: int):
        """Clear default group"""
        self.user_settings.update_one(
            {'user_id': user_id},
            {'$unset': {'default_group': ''}}
        )

# Global instance
db = Database()
