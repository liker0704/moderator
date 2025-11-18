"""
Telegram categorized help system.

This module provides a comprehensive, user-friendly help system with:
- Categorized help content organized by topic
- Interactive navigation with inline keyboards
- Rich formatting with emojis and examples
- Command references and practical usage guides
- Troubleshooting tips and AI feature documentation

Categories:
- Setup & Configuration: Initial setup and Discord connection
- Settings & Management: DND, allowlist, and system settings
- Working with Message Cards: Interaction and reply workflows
- Troubleshooting: Common issues and solutions
- AI Features: AI-powered response generation

Each category provides detailed information with:
- Overview description
- List of related commands
- Practical examples
- Navigation buttons for easy browsing
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class HelpCategory:
    """
    Represents a help category with all content and metadata.

    Attributes:
        id: Unique category identifier (e.g., 'setup', 'manage')
        emoji: Category emoji for visual identification
        title: Category display title
        description: Brief category description for menu
        content: Full help content for this category
        commands: List of relevant commands for this category
        examples: List of practical usage examples
    """
    id: str
    emoji: str
    title: str
    description: str
    content: str
    commands: List[str]
    examples: List[str]


# =============================================================================
# Help Content Management
# =============================================================================

class HelpContent:
    """
    Manages all help content and provides access methods.

    This class provides a centralized source for all help documentation,
    organized by categories. It supports interactive navigation and
    dynamic content generation.
    """

    # Category definitions with complete content
    CATEGORIES: Dict[str, HelpCategory] = {
        'setup': HelpCategory(
            id='setup',
            emoji='🔧',
            title='Setup & Configuration',
            description='Initial setup and Discord connection',
            content="""🔧 **Setup & Configuration**

Get started with Moderator Console and connect your Discord account.

**Initial Setup Steps:**

1️⃣ Start the bot with /start
2️⃣ Configure Discord connection with /setup_discord
3️⃣ Add channels to monitor with /allow_channel
4️⃣ Test your connection with /test_connection

**Discord Connection:**

To connect your Discord account, you'll need your user token. The bot will guide you through the process securely. Your token is encrypted and stored safely in the database.

⚠️ **Security Notice:**
• User tokens are against Discord ToS
• Use at your own risk
• Never share your token with others
• Token is encrypted with AES-256

**Channel Management:**

After connecting Discord, add channels you want to monitor:
• Use /allow_channel to add channels
• Use /unallow_channel to remove channels
• Check status with /status

**Verification:**

Test your setup:
• /test_connection - Verify Discord connection
• /discord_status - Check connection details
• /status - View overall system status

Once setup is complete, you'll start receiving message cards from monitored channels!""",
            commands=[
                '/start - Initialize bot and create user account',
                '/setup_discord - Configure Discord connection (token setup)',
                '/test_connection - Verify Discord connection is working',
                '/discord_status - View Discord connection details',
                '/allow_channel <server_id> <channel_id> - Add channel to monitoring',
                '/unallow_channel <channel_id> - Remove channel from monitoring'
            ],
            examples=[
                '**Example: Complete Setup**\n'
                '1. /start\n'
                '2. /setup_discord\n'
                '   → Enter your Discord token when prompted\n'
                '3. /allow_channel 123456789 987654321\n'
                '4. /test_connection\n'
                '   → Verify connection is active',

                '**Example: Getting Discord IDs**\n'
                '1. Enable Developer Mode in Discord\n'
                '   (Settings → Advanced → Developer Mode)\n'
                '2. Right-click on server name → Copy ID\n'
                '3. Right-click on channel name → Copy ID\n'
                '4. Use these IDs with /allow_channel'
            ]
        ),

        'manage': HelpCategory(
            id='manage',
            emoji='⚙️',
            title='Settings & Management',
            description='DND mode, settings, and status monitoring',
            content="""⚙️ **Settings & Management**

Control your notification preferences and manage system settings.

**Do Not Disturb (DND) Mode:**

DND mode lets you pause notifications without disconnecting. Perfect for focused work time or when you're away.

**DND Commands:**
• /dnd - Show current DND status
• /dnd on - Enable DND mode
• /dnd off - Disable DND mode
• /dnd schedule - Configure DND schedule

**DND Schedules:**

Set automatic DND periods:
• "weeknights" - 22:00-08:00 Mon-Fri
• "always" - 24/7 DND mode
• Custom schedules (coming soon)

When DND is active, messages are queued but not sent to you. They'll be delivered when DND is disabled.

**System Status:**

Monitor your bot's status:
• /status - Complete system overview
• /discord_status - Discord connection details
• /settings - View all current settings

**Settings Overview:**

The /settings command shows:
• Discord connection status
• Monitored channels count
• DND configuration
• Notification preferences

You can modify settings using specific commands like /dnd, /allow_channel, etc.""",
            commands=[
                '/status - View overall system status',
                '/settings - Display all current settings',
                '/dnd - Show DND status',
                '/dnd on - Enable Do Not Disturb mode',
                '/dnd off - Disable Do Not Disturb mode',
                '/dnd schedule - Configure DND schedule'
            ],
            examples=[
                '**Example: Enable DND for evening**\n'
                '1. /dnd schedule\n'
                '2. Type: weeknights\n'
                '   → DND active 22:00-08:00 Mon-Fri\n'
                '3. /dnd on\n'
                '   → DND mode activated',

                '**Example: Check system status**\n'
                '/status\n'
                '→ Shows:\n'
                '  • Discord connection status\n'
                '  • Open tasks count\n'
                '  • DND mode status\n'
                '  • Allowed channels count'
            ]
        ),

        'cards': HelpCategory(
            id='cards',
            emoji='📝',
            title='Working with Message Cards',
            description='Reply to messages and use card features',
            content="""📝 **Working with Message Cards**

Message cards are your interface for reviewing and responding to Discord/Telegram messages.

**Card Structure:**

Each card shows:
• 📱 Platform and channel information
• 📚 Context: Recent conversation history
• 💬 Current message that needs review
• 🤖 AI suggested responses (if enabled)
• ⌨️ Action buttons

**Card Actions:**

**✍️ Ответить (Reply)**
Start composing a reply to the message. You'll be asked to type your response, then confirm before sending.

**📖 Показать больше (Show More)**
Load additional conversation context. Each click loads 10 more previous messages to help you understand the full conversation.

**🔕 DND**
Quick toggle for Do Not Disturb mode.

**Reply Workflow:**

1. Click "Ответить" on the card
2. Type your reply message
3. Review the preview
4. Click "Confirm & Send" to post
   OR "Cancel" to discard

Your reply will be posted to the original platform (Discord/Telegram) as a response to the message.

**Using AI Suggestions:**

If AI features are enabled, you'll see suggested responses:
• Each suggestion shows confidence level
• Click "Use Option X" to select
• You can edit before sending
• Or ignore and write your own

**Context Navigation:**

Use "Показать больше" to:
• Load more conversation history
• Understand the full context
• See earlier messages in thread
• Get better context for replies

**Tips:**
• Always review context before replying
• Use AI suggestions as starting points
• Verify recipient before sending
• Use /cancel to abort any action""",
            commands=[
                'Card buttons:',
                '  ✍️ Ответить - Start reply workflow',
                '  📖 Показать больше - Load more context',
                '  🔕 DND - Toggle Do Not Disturb',
                '',
                'AI features:',
                '  ✨ Use Option X - Use AI suggestion',
                '  🎨 Soften - Generate softer responses',
                '  🔄 More Variants - Generate more options',
                '',
                'Other commands:',
                '  /cancel - Cancel current action'
            ],
            examples=[
                '**Example: Reply to a message**\n'
                '1. Receive message card\n'
                '2. Read the context section\n'
                '3. Click "Ответить"\n'
                '4. Type: "Thanks for reporting! I\'ll look into this."\n'
                '5. Review preview\n'
                '6. Click "Confirm & Send"\n'
                '   → Reply posted to Discord',

                '**Example: Get more context**\n'
                '1. Receive message card\n'
                '2. Click "Показать больше"\n'
                '   → Loads 10 more messages\n'
                '3. Click "Показать больше" again\n'
                '   → Loads 10 more (20 total)\n'
                '4. Now you have full conversation context',

                '**Example: Use AI suggestion**\n'
                '1. Receive card with AI suggestions\n'
                '2. Review Options 1-3 with confidence %\n'
                '3. Click "✨ Use Option 1 (85%)"\n'
                '4. Preview the AI-generated reply\n'
                '5. Edit if needed, or send as-is\n'
                '6. Click "Confirm & Send"'
            ]
        ),

        'troubleshoot': HelpCategory(
            id='troubleshoot',
            emoji='🔍',
            title='Troubleshooting',
            description='Common issues and solutions',
            content="""🔍 **Troubleshooting**

Solutions to common problems and issues.

**Discord Connection Issues:**

❌ **Problem: "Discord not connected"**
**Solutions:**
1. Check your token with /test_connection
2. Verify token hasn't expired
3. Re-run /setup_discord with fresh token
4. Ensure token is correct (no extra spaces)

❌ **Problem: "Token invalid or expired"**
**Solutions:**
1. Discord tokens can expire
2. Get a new token from Discord
3. Run /setup_discord again
4. Never share your token

**Channel Issues:**

❌ **Problem: "Not receiving messages from channel"**
**Solutions:**
1. Verify channel is in allowlist: /status
2. Check channel ID is correct
3. Ensure Discord connection is active
4. Verify you have access to the channel in Discord

❌ **Problem: "Can't add channel to allowlist"**
**Solutions:**
1. Enable Developer Mode in Discord
2. Get correct server_id and channel_id
3. Use format: /allow_channel <server_id> <channel_id>
4. IDs must be numeric

**Reply Issues:**

❌ **Problem: "Reply failed to send"**
**Solutions:**
1. Check Discord connection: /test_connection
2. Verify you have permission to post in channel
3. Check message hasn't been deleted
4. Try again or use /retry command

❌ **Problem: "Reply confirmation not working"**
**Solutions:**
1. Don't close the bot during reply flow
2. Wait for confirmation keyboard to appear
3. Use /cancel if stuck
4. Try replying again

**DND Issues:**

❌ **Problem: "DND not working"**
**Solutions:**
1. Check DND status: /dnd
2. Verify schedule is configured correctly
3. Toggle DND: /dnd off then /dnd on
4. Check system time matches your timezone

**General Issues:**

❌ **Problem: "Bot not responding"**
**Solutions:**
1. Try /start to reinitialize
2. Check your internet connection
3. Wait a moment and try again
4. Contact administrator if persistent

❌ **Problem: "Database errors"**
**Solutions:**
1. Usually temporary
2. Try the command again
3. Report persistent errors

**Getting Help:**

If issues persist:
1. Note the exact error message
2. Check what command caused it
3. Try /status to check system health
4. Report to bot administrator with details

**Security Concerns:**

⚠️ If you suspect security issues:
1. Immediately run /setup_discord with new token
2. Change your Discord password
3. Enable 2FA on Discord
4. Contact administrator""",
            commands=[
                '/test_connection - Test Discord connectivity',
                '/discord_status - Check connection status',
                '/status - View system health',
                '/cancel - Cancel stuck operation',
                '/setup_discord - Reconfigure Discord connection',
                '/start - Reinitialize bot'
            ],
            examples=[
                '**Example: Fix connection issue**\n'
                '1. /test_connection\n'
                '   → "❌ Discord not connected"\n'
                '2. /setup_discord\n'
                '3. Get fresh token from Discord\n'
                '4. Enter new token\n'
                '5. /test_connection\n'
                '   → "✅ Discord connection active"',

                '**Example: Fix missing messages**\n'
                '1. /status\n'
                '   → Check "Allowed Channels: 0"\n'
                '2. Get channel IDs from Discord\n'
                '3. /allow_channel 123456 789012\n'
                '4. /status\n'
                '   → "Allowed Channels: 1"\n'
                '5. Messages now arrive from that channel'
            ]
        ),

        'ai': HelpCategory(
            id='ai',
            emoji='🤖',
            title='AI Features',
            description='AI-powered response generation and assistance',
            content="""🤖 **AI Features**

Use AI to help craft better responses and save time.

**AI Response Generation:**

The bot can suggest responses using AI models:
• Analyzes conversation context
• Generates appropriate replies
• Provides multiple variants
• Shows confidence scores

**How AI Suggestions Work:**

1. **Context Analysis**
   AI reads the conversation history to understand the situation

2. **Response Generation**
   Multiple response options are generated based on context

3. **Confidence Scoring**
   Each suggestion gets a confidence score (0-100%)

4. **Your Choice**
   You review, select, edit, or ignore suggestions

**AI Features on Cards:**

🟢 **High Confidence (80%+)**: Very reliable suggestion
🟡 **Medium Confidence (60-80%)**: Good suggestion, review before using
🔴 **Low Confidence (<60%)**: Use caution, may need editing

**Available AI Actions:**

**✨ Use Option X**
Select an AI-generated suggestion to use as your reply. You can still edit it before sending.

**🎨 Soften**
Regenerate responses with a softer, more diplomatic tone. Useful when the conversation is tense or sensitive.

**🔄 More Variants**
Generate additional response options if you don't like the initial suggestions.

**AI Best Practices:**

✅ **DO:**
• Review AI suggestions before sending
• Edit to match your voice/style
• Use AI for routine responses
• Check context is correct
• Verify tone is appropriate

❌ **DON'T:**
• Blindly send without reading
• Use for sensitive/serious matters without review
• Rely 100% on AI for important messages
• Ignore low confidence warnings
• Use AI-generated content for legal/critical issues

**AI Limitations:**

AI suggestions are helpful but have limits:
• May not understand nuanced context
• Can miss cultural/community-specific references
• Might generate generic responses
• Doesn't know your personal style/voice
• Can't access external information

**Privacy & AI:**

• Conversation context is processed to generate suggestions
• Data is not stored beyond session
• AI providers may process content (see their policies)
• Sensitive information should be handled manually

**When to Use AI:**

✅ **Good Use Cases:**
• Routine acknowledgments
• Common questions
• Polite redirects
• Standard moderation responses
• Time-saving for bulk messages

⚠️ **Use Caution:**
• Sensitive topics
• Conflicts/disputes
• Personal matters
• Legal issues
• Complex technical problems

**Customizing AI Responses:**

After selecting an AI suggestion:
1. Review the generated text
2. Click "✏️ Edit" if needed
3. Modify to match your style
4. Add personal touches
5. Send when satisfied

**Tips for Better AI Suggestions:**

• Load more context with "Показать больше"
• More context = better suggestions
• Use "Soften" for diplomatic responses
• Try "More Variants" for alternatives
• Combine AI suggestions with your own words""",
            commands=[
                'AI card buttons:',
                '  ✨ Use Option X - Select AI suggestion',
                '  🎨 Soften - Generate softer tone variants',
                '  🔄 More Variants - Generate more options',
                '  ✏️ Edit - Edit selected AI response',
                '',
                'Confidence indicators:',
                '  🟢 80%+ - High confidence',
                '  🟡 60-80% - Medium confidence',
                '  🔴 <60% - Low confidence'
            ],
            examples=[
                '**Example: Using AI suggestion**\n'
                '1. Receive card with 3 AI suggestions\n'
                '2. Review each option and confidence\n'
                '3. Option 1 (85%): "Thanks for the report!"\n'
                '4. Click "✨ Use Option 1 (85%)"\n'
                '5. Review preview\n'
                '6. Click "Confirm & Send"',

                '**Example: Softening a response**\n'
                '1. Initial suggestions seem too direct\n'
                '2. Click "🎨 Soften"\n'
                '3. New suggestions with gentler tone\n'
                '4. Option 1: "I appreciate you bringing this up..."\n'
                '5. Select and send the softer version',

                '**Example: Editing AI suggestion**\n'
                '1. Select "✨ Use Option 2"\n'
                '2. Preview: "Thanks! I\'ll handle this."\n'
                '3. Click "✏️ Edit"\n'
                '4. Modify to: "Thanks! I\'ll handle this right away."\n'
                '5. Click "Confirm & Send"\n'
                '   → Sends your edited version'
            ]
        )
    }

    # Category order for navigation
    CATEGORY_ORDER = ['setup', 'manage', 'cards', 'troubleshoot', 'ai']

    @classmethod
    def get_category(cls, category_id: str) -> Optional[HelpCategory]:
        """
        Get a help category by ID.

        Args:
            category_id: Category identifier (e.g., 'setup', 'manage')

        Returns:
            HelpCategory object or None if not found
        """
        return cls.CATEGORIES.get(category_id)

    @classmethod
    def get_main_menu(cls) -> str:
        """
        Get the main help menu text with category list.

        Returns:
            Formatted main menu text with all categories
        """
        menu = """📖 **Help Center**

Welcome to the Moderator Console Help Center! Select a category below to learn more.

**Available Categories:**

"""

        for cat_id in cls.CATEGORY_ORDER:
            category = cls.CATEGORIES[cat_id]
            menu += f"{category.emoji} **{category.title}**\n"
            menu += f"_{category.description}_\n\n"

        menu += "💡 **Quick Tips:**\n"
        menu += "• Use /start to initialize the bot\n"
        menu += "• Use /status to check system health\n"
        menu += "• Use /cancel to abort any operation\n"
        menu += "• Browse categories for detailed help\n\n"
        menu += "Select a category to get started!"

        return menu

    @classmethod
    def create_category_keyboard(cls) -> dict:
        """
        Create inline keyboard with all category buttons.

        Returns:
            Telegram inline keyboard markup dict
        """
        keyboard = {'inline_keyboard': []}

        # Create rows of 2 buttons each
        row = []
        for cat_id in cls.CATEGORY_ORDER:
            category = cls.CATEGORIES[cat_id]
            button = {
                'text': f"{category.emoji} {category.title}",
                'callback_data': f'help_cat_{cat_id}'
            }
            row.append(button)

            # Add row when we have 2 buttons, or it's the last category
            if len(row) == 2 or cat_id == cls.CATEGORY_ORDER[-1]:
                keyboard['inline_keyboard'].append(row)
                row = []

        return keyboard

    @classmethod
    def create_navigation_keyboard(cls, current_category: str) -> dict:
        """
        Create navigation keyboard for a category page.

        Includes Back to Menu button and Next category button if applicable.

        Args:
            current_category: Current category ID

        Returns:
            Telegram inline keyboard markup dict
        """
        keyboard = {'inline_keyboard': []}

        # Navigation row
        nav_row = []

        # Get current category index
        try:
            current_idx = cls.CATEGORY_ORDER.index(current_category)
        except ValueError:
            current_idx = 0

        # Previous category button (if not first)
        if current_idx > 0:
            prev_cat_id = cls.CATEGORY_ORDER[current_idx - 1]
            prev_cat = cls.CATEGORIES[prev_cat_id]
            nav_row.append({
                'text': f'⬅️ {prev_cat.emoji} {prev_cat.title}',
                'callback_data': f'help_cat_{prev_cat_id}'
            })

        # Next category button (if not last)
        if current_idx < len(cls.CATEGORY_ORDER) - 1:
            next_cat_id = cls.CATEGORY_ORDER[current_idx + 1]
            next_cat = cls.CATEGORIES[next_cat_id]
            nav_row.append({
                'text': f'{next_cat.emoji} {next_cat.title} ➡️',
                'callback_data': f'help_cat_{next_cat_id}'
            })

        if nav_row:
            keyboard['inline_keyboard'].append(nav_row)

        # Back to menu button
        keyboard['inline_keyboard'].append([
            {
                'text': '🏠 Back to Help Menu',
                'callback_data': 'help_main'
            }
        ])

        return keyboard


# =============================================================================
# Content Formatting Functions
# =============================================================================

def format_help_category(category: HelpCategory) -> str:
    """
    Format a help category for display.

    Creates a comprehensive, well-formatted help page with:
    - Category title and description
    - Main content
    - Commands list
    - Practical examples
    - Navigation hints

    Args:
        category: HelpCategory object to format

    Returns:
        Formatted help text ready for display
    """
    output = f"{category.emoji} **{category.title}**\n\n"

    # Main content
    output += category.content

    # Commands section
    if category.commands:
        output += "\n\n**📋 Commands:**\n\n"
        for command in category.commands:
            # Check if it's a section header (doesn't start with /)
            if command.startswith(' '):
                output += f"{command}\n"
            elif not command.startswith('/'):
                output += f"\n{command}\n"
            else:
                output += f"`{command}`\n"

    # Examples section
    if category.examples:
        output += "\n\n**📚 Examples:**\n\n"
        for idx, example in enumerate(category.examples, 1):
            if len(category.examples) > 1:
                output += f"{example}\n\n"
            else:
                output += f"{example}\n"

    # Navigation hint
    output += "\n---\n"
    output += "💡 Use the buttons below to navigate between help topics"

    return output


# =============================================================================
# Example Usage
# =============================================================================

def create_example_help() -> tuple[str, dict]:
    """
    Create example help menu for testing.

    Returns:
        Tuple of (menu_text, keyboard)
    """
    menu_text = HelpContent.get_main_menu()
    keyboard = HelpContent.create_category_keyboard()

    return menu_text, keyboard


if __name__ == '__main__':
    # Test help system
    print("=== Main Help Menu ===")
    menu_text, keyboard = create_example_help()
    print(menu_text)
    print(f"\nKeyboard: {len(keyboard['inline_keyboard'])} rows")

    print("\n\n=== Setup Category ===")
    setup_cat = HelpContent.get_category('setup')
    if setup_cat:
        print(format_help_category(setup_cat))
        nav_keyboard = HelpContent.create_navigation_keyboard('setup')
        print(f"\nNavigation: {len(nav_keyboard['inline_keyboard'])} rows")

    print("\n\n=== AI Category ===")
    ai_cat = HelpContent.get_category('ai')
    if ai_cat:
        content = format_help_category(ai_cat)
        print(f"Content length: {len(content)} characters")
        print(content[:500] + "...\n[truncated for display]")
