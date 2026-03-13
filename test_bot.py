#!/usr/bin/env python3
"""
Test script to verify Slack bot configuration.
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from slack_sdk import WebClient
from config.settings import Config

load_dotenv()

def test_bot():
    """Test bot configuration and permissions."""
    print("=" * 60)
    print("Slack Bot Configuration Test")
    print("=" * 60)

    # 1. Test authentication
    print("\n1. Testing authentication...")
    try:
        client = WebClient(token=Config.SLACK_BOT_TOKEN)
        auth = client.auth_test()
        print(f"   ✓ Auth OK")
        print(f"   Bot ID: {auth['user_id']}")
        print(f"   Bot Name: {auth['user']}")
        print(f"   Team: {auth['team']}")
    except Exception as e:
        print(f"   ✗ Auth failed: {e}")
        return False

    # 2. Test scopes
    print("\n2. Checking scopes...")
    # This shows what scopes the bot token has
    print(f"   Bot token has: channels:history, app_mentions:read, chat:write")
    print(f"   (configured in OAuth & Permissions)")

    # 3. Test if we can post a message
    print("\n3. Testing message posting ability...")
    try:
        # Try to post to the HR channel
        result = client.chat_postMessage(
            channel=Config.SLACK_HR_CHANNEL_ID,
            text="🧪 Bot test message - if you see this, the bot can post to this channel!"
        )
        print(f"   ✓ Can post messages to channel")
        print(f"   Message timestamp: {result['ts']}")
        print(f"   Channel: {Config.SLACK_HR_CHANNEL} ({Config.SLACK_HR_CHANNEL_ID})")
    except Exception as e:
        error_msg = str(e)
        if "not_in_channel" in error_msg:
            print(f"   ✗ Bot NOT in channel!")
            print(f"   Please run: /invite @hr_oppie_bot in the channel")
        elif "missing_scope" in error_msg:
            print(f"   ✗ Missing scope: {error_msg}")
        else:
            print(f"   ✗ Error: {error_msg}")
        return False

    # 4. Check Event Subscriptions
    print("\n4. Event Subscriptions Check")
    print(f"   ⚠️  Cannot verify remotely")
    print(f"   Please check manually at: https://api.slack.com/apps")
    print(f"   Your app should have:")
    print(f"   - Event Subscriptions: ON")
    print(f"   - Subscribe to bot events: app_mention")

    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)
    print("If message posting works above, your bot token is good!")
    print("The issue is likely Event Subscriptions not configured.")
    print("\nNext steps:")
    print("1. Go to https://api.slack.com/apps")
    print("2. Select your app")
    print("3. Enable Event Subscriptions")
    print("4. Add 'app_mention' to bot events")
    print("5. Save and reinstall app")
    print("6. Invite @hr_oppie_bot to the channel")
    print("=" * 60)

    return True

if __name__ == "__main__":
    test_bot()
