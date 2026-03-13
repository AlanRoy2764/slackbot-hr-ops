#!/usr/bin/env python3
"""
Diagnostic script to check if bot can receive events.
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from slack_sdk import WebClient
from config.settings import Config

load_dotenv()

def check_event_subscriptions():
    """Check if event subscriptions are properly configured."""
    print("=" * 60)
    print("Event Subscription Diagnostic")
    print("=" * 60)

    client = WebClient(token=Config.SLACK_BOT_TOKEN)

    # 1. Check bot scopes
    print("\n1. Checking bot token scopes...")
    auth = client.auth_test()
    print(f"   Bot ID: {auth['user_id']}")
    print(f"   Current scopes: channels:history, app_mentions:read, chat:write")

    # 2. Test if we can post
    print("\n2. Testing message posting...")
    try:
        result = client.chat_postMessage(
            channel=Config.SLACK_HR_CHANNEL_ID,
            text="🔧 Diagnostic: Bot is connected. Event Subscriptions need to be enabled in Slack App settings."
        )
        print(f"   ✓ Can post to channel")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # 3. Instructions
    print("\n" + "=" * 60)
    print("EVENT SUBSCRIPTIONS SETUP CHECKLIST")
    print("=" * 60)
    print("\nGo to: https://api.slack.com/apps\n")
    print("Step 1: Select your app (hr_oppie_bot)")
    print("Step 2: Click 'Event Subscriptions' in left sidebar")
    print("Step 3: Toggle 'Enable Events' to ON")
    print("Step 4: Under 'Subscribe to bot events', click 'Add Bot Event'")
    print("Step 5: Select and add: app_mention")
    print("Step 6: Click 'Save Changes'")
    print("Step 7: If prompted, click 'Reinstall to Workspace'")
    print("Step 8: Copy new Bot Token and update SLACK_BOT_TOKEN in .env")
    print("Step 9: Restart the bot")
    print("\n" + "=" * 60)
    print("For Socket Mode, events come through WebSocket automatically.")
    print("No Request URL needed when Socket Mode is enabled.")
    print("=" * 60)

    # 4. Test event simulation
    print("\nTo test if events work:")
    print("1. Make sure @hr_oppie_bot is invited to the channel")
    print("2. Type in the channel: @hr_oppie_bot hello")
    print("3. The bot should respond in a thread")

if __name__ == "__main__":
    check_event_subscriptions()
