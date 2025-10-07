#!/usr/bin/env python3
"""
Script to check and update user role to admin
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from database.engine import async_session
from database.models import User


async def check_and_update_role(telegram_id: int = None, username: str = None, set_admin: bool = False):
    """Check user role and optionally set to admin"""
    async with async_session() as session:
        # Find user
        if telegram_id:
            stmt = select(User).where(User.telegram_id == telegram_id)
        elif username:
            stmt = select(User).where(User.username == username)
        else:
            # Show all users
            stmt = select(User)
        
        result = await session.execute(stmt)
        users = result.scalars().all()
        
        if not users:
            print("❌ User not found!")
            return
        
        if len(users) > 1 and (telegram_id or username):
            print(f"⚠️  Multiple users found!")
        
        for user in users:
            print(f"\n📋 User Info:")
            print(f"   ID: {user.id}")
            print(f"   Telegram ID: {user.telegram_id}")
            print(f"   Username: {user.username or 'N/A'}")
            print(f"   Display Name: {user.display_name}")
            print(f"   Role: {user.role}")
            print(f"   Created: {user.created_at}")
            print(f"   Last Login: {user.last_login_at or 'Never'}")
            
            if set_admin and user.role != 'admin':
                user.role = 'admin'
                await session.commit()
                print(f"\n✅ Role updated to ADMIN!")
            elif user.role == 'admin':
                print(f"\n✅ Already ADMIN!")
            else:
                print(f"\n💡 To set as admin, run: python scripts/check_user_role.py --set-admin --username {user.username or user.telegram_id}")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description='Check and update user roles')
    parser.add_argument('--telegram-id', type=int, help='Telegram ID')
    parser.add_argument('--username', type=str, help='Username')
    parser.add_argument('--set-admin', action='store_true', help='Set role to admin')
    parser.add_argument('--list-all', action='store_true', help='List all users')
    
    args = parser.parse_args()
    
    if args.list_all:
        await check_and_update_role()
    elif args.telegram_id or args.username:
        await check_and_update_role(
            telegram_id=args.telegram_id,
            username=args.username,
            set_admin=args.set_admin
        )
    else:
        print("Usage:")
        print("  List all users:      python scripts/check_user_role.py --list-all")
        print("  Check by username:   python scripts/check_user_role.py --username YOUR_USERNAME")
        print("  Check by telegram:   python scripts/check_user_role.py --telegram-id YOUR_TG_ID")
        print("  Set admin:           python scripts/check_user_role.py --username YOUR_USERNAME --set-admin")


if __name__ == '__main__':
    asyncio.run(main())
