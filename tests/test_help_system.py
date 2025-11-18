"""
Comprehensive unit tests for the help system.

Tests cover:
- HelpCategory dataclass structure and all required fields
- All 5 help categories exist and are properly configured
- HelpContent.get_category() returns correct category
- HelpContent.get_main_menu() generates proper menu text
- HelpContent.create_category_keyboard() creates proper inline keyboard structure
- HelpContent.create_navigation_keyboard() creates context-aware navigation
- format_help_category() formats content correctly with all sections
"""

import os
import sys
import pytest

# Set minimal required environment variables for testing
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'test_token')
os.environ.setdefault('MODERATOR_TG_USER_ID', '123456')
os.environ.setdefault('ALERT_CHAT_ID', '123456')
os.environ.setdefault('DB_HOST', 'localhost')
os.environ.setdefault('DB_PORT', '5432')
os.environ.setdefault('DB_NAME', 'test_db')
os.environ.setdefault('DB_USER', 'test_user')
os.environ.setdefault('DB_PASSWORD', 'test_password')
os.environ.setdefault('ENCRYPTION_KEY', 'test_key_32_characters_long!!!!')

from backend.src.telegram.help_content import (
    HelpCategory,
    HelpContent,
    format_help_category,
    create_example_help
)


# =============================================================================
# HelpCategory Dataclass Tests
# =============================================================================

class TestHelpCategory:
    """Test suite for HelpCategory dataclass."""

    def test_help_category_creation(self):
        """Test creating a HelpCategory instance with all fields."""
        # Arrange & Act
        category = HelpCategory(
            id='test',
            emoji='🧪',
            title='Test Category',
            description='Test description',
            content='Test content',
            commands=['command1', 'command2'],
            examples=['example1']
        )

        # Assert
        assert category.id == 'test'
        assert category.emoji == '🧪'
        assert category.title == 'Test Category'
        assert category.description == 'Test description'
        assert category.content == 'Test content'
        assert category.commands == ['command1', 'command2']
        assert category.examples == ['example1']

    def test_help_category_required_fields(self):
        """Test that all HelpCategory fields are required."""
        # Arrange & Act & Assert
        # All fields should be required, attempting to create without them should fail
        with pytest.raises(TypeError):
            HelpCategory(
                id='test',
                emoji='🧪'
                # Missing required fields
            )

    def test_help_category_empty_lists(self):
        """Test HelpCategory with empty command and example lists."""
        # Arrange & Act
        category = HelpCategory(
            id='test',
            emoji='🧪',
            title='Test',
            description='Test',
            content='Test',
            commands=[],
            examples=[]
        )

        # Assert
        assert category.commands == []
        assert category.examples == []


# =============================================================================
# HelpContent Category Tests
# =============================================================================

class TestHelpContentCategories:
    """Test suite for HelpContent category management."""

    def test_all_five_categories_exist(self):
        """Test that all 5 required help categories exist."""
        # Arrange
        expected_categories = ['setup', 'manage', 'cards', 'troubleshoot', 'ai']

        # Act & Assert
        for cat_id in expected_categories:
            category = HelpContent.get_category(cat_id)
            assert category is not None, f"Category '{cat_id}' should exist"

    def test_category_count(self):
        """Test that there are exactly 5 categories."""
        # Arrange & Act
        categories = HelpContent.CATEGORIES

        # Assert
        assert len(categories) == 5

    def test_category_order(self):
        """Test that category order is defined correctly."""
        # Arrange
        expected_order = ['setup', 'manage', 'cards', 'troubleshoot', 'ai']

        # Act
        actual_order = HelpContent.CATEGORY_ORDER

        # Assert
        assert actual_order == expected_order

    def test_setup_category_content(self):
        """Test that setup category has all required content."""
        # Arrange & Act
        category = HelpContent.get_category('setup')

        # Assert
        assert category is not None
        assert category.id == 'setup'
        assert category.emoji == '🔧'
        assert category.title == 'Setup & Configuration'
        assert 'Initial setup and Discord connection' in category.description
        assert len(category.content) > 0
        assert len(category.commands) > 0
        assert len(category.examples) > 0

    def test_manage_category_content(self):
        """Test that manage category has all required content."""
        # Arrange & Act
        category = HelpContent.get_category('manage')

        # Assert
        assert category is not None
        assert category.id == 'manage'
        assert category.emoji == '⚙️'
        assert category.title == 'Settings & Management'
        assert 'DND mode' in category.description or 'settings' in category.description
        assert len(category.content) > 0
        assert len(category.commands) > 0
        assert len(category.examples) > 0

    def test_cards_category_content(self):
        """Test that cards category has all required content."""
        # Arrange & Act
        category = HelpContent.get_category('cards')

        # Assert
        assert category is not None
        assert category.id == 'cards'
        assert category.emoji == '📝'
        assert category.title == 'Working with Message Cards'
        assert 'Reply to messages' in category.description or 'card features' in category.description
        assert len(category.content) > 0
        assert len(category.commands) > 0
        assert len(category.examples) > 0

    def test_troubleshoot_category_content(self):
        """Test that troubleshoot category has all required content."""
        # Arrange & Act
        category = HelpContent.get_category('troubleshoot')

        # Assert
        assert category is not None
        assert category.id == 'troubleshoot'
        assert category.emoji == '🔍'
        assert category.title == 'Troubleshooting'
        assert 'Common issues' in category.description or 'solutions' in category.description
        assert len(category.content) > 0
        assert len(category.commands) > 0
        assert len(category.examples) > 0

    def test_ai_category_content(self):
        """Test that AI category has all required content."""
        # Arrange & Act
        category = HelpContent.get_category('ai')

        # Assert
        assert category is not None
        assert category.id == 'ai'
        assert category.emoji == '🤖'
        assert category.title == 'AI Features'
        assert 'AI' in category.description
        assert len(category.content) > 0
        assert len(category.commands) > 0
        assert len(category.examples) > 0


# =============================================================================
# HelpCategory Fields Validation Tests
# =============================================================================

class TestHelpCategoryFields:
    """Test suite for validating all category fields are properly populated."""

    def test_all_categories_have_emojis(self):
        """Test that all categories have emoji identifiers."""
        # Arrange & Act & Assert
        for cat_id in HelpContent.CATEGORY_ORDER:
            category = HelpContent.get_category(cat_id)
            assert category.emoji
            assert len(category.emoji) > 0

    def test_all_categories_have_titles(self):
        """Test that all categories have titles."""
        # Arrange & Act & Assert
        for cat_id in HelpContent.CATEGORY_ORDER:
            category = HelpContent.get_category(cat_id)
            assert category.title
            assert len(category.title) > 0

    def test_all_categories_have_descriptions(self):
        """Test that all categories have descriptions."""
        # Arrange & Act & Assert
        for cat_id in HelpContent.CATEGORY_ORDER:
            category = HelpContent.get_category(cat_id)
            assert category.description
            assert len(category.description) > 0

    def test_all_categories_have_content(self):
        """Test that all categories have substantial content."""
        # Arrange & Act & Assert
        for cat_id in HelpContent.CATEGORY_ORDER:
            category = HelpContent.get_category(cat_id)
            assert category.content
            assert len(category.content) > 50  # Substantial content

    def test_all_categories_have_commands(self):
        """Test that all categories have command lists."""
        # Arrange & Act & Assert
        for cat_id in HelpContent.CATEGORY_ORDER:
            category = HelpContent.get_category(cat_id)
            assert isinstance(category.commands, list)
            assert len(category.commands) > 0

    def test_all_categories_have_examples(self):
        """Test that all categories have example lists."""
        # Arrange & Act & Assert
        for cat_id in HelpContent.CATEGORY_ORDER:
            category = HelpContent.get_category(cat_id)
            assert isinstance(category.examples, list)
            assert len(category.examples) > 0

    def test_category_ids_match_keys(self):
        """Test that category IDs match their dictionary keys."""
        # Arrange & Act & Assert
        for key, category in HelpContent.CATEGORIES.items():
            assert category.id == key


# =============================================================================
# get_category() Method Tests
# =============================================================================

class TestGetCategory:
    """Test suite for HelpContent.get_category() method."""

    def test_get_category_returns_correct_category(self):
        """Test that get_category returns the correct category."""
        # Arrange & Act
        setup_cat = HelpContent.get_category('setup')

        # Assert
        assert setup_cat is not None
        assert setup_cat.id == 'setup'
        assert setup_cat.title == 'Setup & Configuration'

    def test_get_category_returns_none_for_invalid_id(self):
        """Test that get_category returns None for non-existent category."""
        # Arrange & Act
        category = HelpContent.get_category('nonexistent')

        # Assert
        assert category is None

    def test_get_category_for_all_valid_ids(self):
        """Test that get_category works for all valid category IDs."""
        # Arrange
        valid_ids = ['setup', 'manage', 'cards', 'troubleshoot', 'ai']

        # Act & Assert
        for cat_id in valid_ids:
            category = HelpContent.get_category(cat_id)
            assert category is not None
            assert category.id == cat_id

    def test_get_category_case_sensitive(self):
        """Test that get_category is case-sensitive."""
        # Arrange & Act
        category = HelpContent.get_category('SETUP')  # Wrong case

        # Assert
        assert category is None  # Should not find it


# =============================================================================
# get_main_menu() Method Tests
# =============================================================================

class TestGetMainMenu:
    """Test suite for HelpContent.get_main_menu() method."""

    def test_get_main_menu_returns_string(self):
        """Test that get_main_menu returns a string."""
        # Arrange & Act
        menu = HelpContent.get_main_menu()

        # Assert
        assert isinstance(menu, str)
        assert len(menu) > 0

    def test_main_menu_contains_title(self):
        """Test that main menu contains the help center title."""
        # Arrange & Act
        menu = HelpContent.get_main_menu()

        # Assert
        assert "Help Center" in menu or "📖" in menu

    def test_main_menu_contains_all_categories(self):
        """Test that main menu lists all categories."""
        # Arrange
        categories = HelpContent.CATEGORY_ORDER

        # Act
        menu = HelpContent.get_main_menu()

        # Assert
        for cat_id in categories:
            category = HelpContent.get_category(cat_id)
            assert category.title in menu
            assert category.emoji in menu

    def test_main_menu_contains_category_descriptions(self):
        """Test that main menu contains category descriptions."""
        # Arrange & Act
        menu = HelpContent.get_main_menu()

        # Assert
        for cat_id in HelpContent.CATEGORY_ORDER:
            category = HelpContent.get_category(cat_id)
            assert category.description in menu

    def test_main_menu_contains_quick_tips(self):
        """Test that main menu contains quick tips section."""
        # Arrange & Act
        menu = HelpContent.get_main_menu()

        # Assert
        assert "Quick Tips" in menu or "💡" in menu

    def test_main_menu_formatting(self):
        """Test that main menu has proper Markdown formatting."""
        # Arrange & Act
        menu = HelpContent.get_main_menu()

        # Assert
        assert "**" in menu  # Has bold text
        assert "\n" in menu  # Has line breaks


# =============================================================================
# create_category_keyboard() Method Tests
# =============================================================================

class TestCreateCategoryKeyboard:
    """Test suite for HelpContent.create_category_keyboard() method."""

    def test_create_category_keyboard_returns_dict(self):
        """Test that create_category_keyboard returns a dictionary."""
        # Arrange & Act
        keyboard = HelpContent.create_category_keyboard()

        # Assert
        assert isinstance(keyboard, dict)

    def test_keyboard_has_inline_keyboard_key(self):
        """Test that keyboard has 'inline_keyboard' key."""
        # Arrange & Act
        keyboard = HelpContent.create_category_keyboard()

        # Assert
        assert 'inline_keyboard' in keyboard

    def test_keyboard_inline_keyboard_is_list(self):
        """Test that inline_keyboard is a list of rows."""
        # Arrange & Act
        keyboard = HelpContent.create_category_keyboard()

        # Assert
        assert isinstance(keyboard['inline_keyboard'], list)

    def test_keyboard_has_buttons_for_all_categories(self):
        """Test that keyboard has buttons for all 5 categories."""
        # Arrange & Act
        keyboard = HelpContent.create_category_keyboard()
        all_buttons = []
        for row in keyboard['inline_keyboard']:
            all_buttons.extend(row)

        # Assert
        assert len(all_buttons) == 5  # 5 categories

    def test_keyboard_buttons_have_correct_structure(self):
        """Test that all buttons have required 'text' and 'callback_data' fields."""
        # Arrange & Act
        keyboard = HelpContent.create_category_keyboard()

        # Assert
        for row in keyboard['inline_keyboard']:
            for button in row:
                assert 'text' in button
                assert 'callback_data' in button
                assert isinstance(button['text'], str)
                assert isinstance(button['callback_data'], str)

    def test_keyboard_callback_data_format(self):
        """Test that callback data has correct format 'help_cat_{category_id}'."""
        # Arrange & Act
        keyboard = HelpContent.create_category_keyboard()

        # Assert
        for row in keyboard['inline_keyboard']:
            for button in row:
                callback = button['callback_data']
                assert callback.startswith('help_cat_')

    def test_keyboard_buttons_have_emojis(self):
        """Test that all category buttons include their emojis."""
        # Arrange & Act
        keyboard = HelpContent.create_category_keyboard()
        all_buttons = []
        for row in keyboard['inline_keyboard']:
            all_buttons.extend(row)

        # Assert
        for cat_id in HelpContent.CATEGORY_ORDER:
            category = HelpContent.get_category(cat_id)
            # Find button for this category
            found = False
            for button in all_buttons:
                if category.emoji in button['text']:
                    found = True
                    break
            assert found, f"Button for category '{cat_id}' should have emoji {category.emoji}"

    def test_keyboard_rows_layout(self):
        """Test that keyboard has proper row layout (max 2 buttons per row)."""
        # Arrange & Act
        keyboard = HelpContent.create_category_keyboard()

        # Assert
        for row in keyboard['inline_keyboard']:
            assert len(row) <= 2  # Maximum 2 buttons per row


# =============================================================================
# create_navigation_keyboard() Method Tests
# =============================================================================

class TestCreateNavigationKeyboard:
    """Test suite for HelpContent.create_navigation_keyboard() method."""

    def test_navigation_keyboard_returns_dict(self):
        """Test that create_navigation_keyboard returns a dictionary."""
        # Arrange & Act
        keyboard = HelpContent.create_navigation_keyboard('setup')

        # Assert
        assert isinstance(keyboard, dict)

    def test_navigation_keyboard_has_inline_keyboard_key(self):
        """Test that navigation keyboard has 'inline_keyboard' key."""
        # Arrange & Act
        keyboard = HelpContent.create_navigation_keyboard('setup')

        # Assert
        assert 'inline_keyboard' in keyboard

    def test_navigation_keyboard_always_has_back_button(self):
        """Test that navigation keyboard always includes back to menu button."""
        # Arrange & Act & Assert
        for cat_id in HelpContent.CATEGORY_ORDER:
            keyboard = HelpContent.create_navigation_keyboard(cat_id)
            # Flatten all buttons
            all_buttons = []
            for row in keyboard['inline_keyboard']:
                all_buttons.extend(row)
            # Check for back button
            back_button_found = any(
                'Back to Help Menu' in button['text'] or '🏠' in button['text']
                for button in all_buttons
            )
            assert back_button_found, f"Category '{cat_id}' should have back button"

    def test_navigation_keyboard_first_category_no_previous(self):
        """Test that first category has no previous button."""
        # Arrange & Act
        keyboard = HelpContent.create_navigation_keyboard('setup')
        all_buttons = []
        for row in keyboard['inline_keyboard']:
            all_buttons.extend(row)

        # Assert
        # Should not have a previous button (no ⬅️)
        previous_button_found = any(
            '⬅️' in button['text']
            for button in all_buttons
        )
        assert not previous_button_found

    def test_navigation_keyboard_last_category_no_next(self):
        """Test that last category has no next button."""
        # Arrange & Act
        keyboard = HelpContent.create_navigation_keyboard('ai')  # Last category
        all_buttons = []
        for row in keyboard['inline_keyboard']:
            all_buttons.extend(row)

        # Assert
        # Should not have a next button (no ➡️ at the end)
        next_button_found = any(
            '➡️' in button['text']
            for button in all_buttons
        )
        assert not next_button_found

    def test_navigation_keyboard_middle_category_has_both_buttons(self):
        """Test that middle categories have both previous and next buttons."""
        # Arrange & Act
        keyboard = HelpContent.create_navigation_keyboard('manage')  # Middle category
        all_buttons = []
        for row in keyboard['inline_keyboard']:
            all_buttons.extend(row)

        # Assert
        previous_button_found = any('⬅️' in button['text'] for button in all_buttons)
        next_button_found = any('➡️' in button['text'] for button in all_buttons)
        assert previous_button_found
        assert next_button_found

    def test_navigation_keyboard_callback_data_format(self):
        """Test that navigation buttons have correct callback data."""
        # Arrange & Act
        keyboard = HelpContent.create_navigation_keyboard('manage')

        # Assert
        for row in keyboard['inline_keyboard']:
            for button in row:
                callback = button['callback_data']
                # Should be either help_cat_{id} or help_main
                assert callback.startswith('help_cat_') or callback == 'help_main'

    def test_navigation_keyboard_invalid_category(self):
        """Test navigation keyboard with invalid category defaults gracefully."""
        # Arrange & Act
        keyboard = HelpContent.create_navigation_keyboard('nonexistent')

        # Assert
        # Should still create a keyboard (might just have back button)
        assert 'inline_keyboard' in keyboard
        assert len(keyboard['inline_keyboard']) > 0


# =============================================================================
# format_help_category() Function Tests
# =============================================================================

class TestFormatHelpCategory:
    """Test suite for format_help_category() function."""

    def test_format_help_category_returns_string(self):
        """Test that format_help_category returns a string."""
        # Arrange
        category = HelpContent.get_category('setup')

        # Act
        formatted = format_help_category(category)

        # Assert
        assert isinstance(formatted, str)
        assert len(formatted) > 0

    def test_formatted_contains_title_and_emoji(self):
        """Test that formatted output contains category title and emoji."""
        # Arrange
        category = HelpContent.get_category('setup')

        # Act
        formatted = format_help_category(category)

        # Assert
        assert category.emoji in formatted
        assert category.title in formatted

    def test_formatted_contains_main_content(self):
        """Test that formatted output contains the main content."""
        # Arrange
        category = HelpContent.get_category('setup')

        # Act
        formatted = format_help_category(category)

        # Assert
        assert category.content in formatted

    def test_formatted_contains_commands_section(self):
        """Test that formatted output has commands section."""
        # Arrange
        category = HelpContent.get_category('setup')

        # Act
        formatted = format_help_category(category)

        # Assert
        assert "Commands" in formatted or "📋" in formatted
        # Check that at least one command is present
        assert any(cmd in formatted for cmd in category.commands)

    def test_formatted_contains_examples_section(self):
        """Test that formatted output has examples section."""
        # Arrange
        category = HelpContent.get_category('setup')

        # Act
        formatted = format_help_category(category)

        # Assert
        assert "Examples" in formatted or "📚" in formatted

    def test_formatted_contains_navigation_hint(self):
        """Test that formatted output contains navigation hint."""
        # Arrange
        category = HelpContent.get_category('setup')

        # Act
        formatted = format_help_category(category)

        # Assert
        assert "---" in formatted or "buttons below" in formatted

    def test_formatted_all_categories_valid(self):
        """Test that format_help_category works for all categories."""
        # Arrange & Act & Assert
        for cat_id in HelpContent.CATEGORY_ORDER:
            category = HelpContent.get_category(cat_id)
            formatted = format_help_category(category)
            assert len(formatted) > 0
            assert category.title in formatted

    def test_formatted_with_empty_commands_list(self):
        """Test formatting category with empty commands list."""
        # Arrange
        category = HelpCategory(
            id='test',
            emoji='🧪',
            title='Test',
            description='Test',
            content='Test content',
            commands=[],
            examples=['example']
        )

        # Act
        formatted = format_help_category(category)

        # Assert
        assert len(formatted) > 0
        # Commands section should not appear
        assert "📋 Commands" not in formatted

    def test_formatted_with_empty_examples_list(self):
        """Test formatting category with empty examples list."""
        # Arrange
        category = HelpCategory(
            id='test',
            emoji='🧪',
            title='Test',
            description='Test',
            content='Test content',
            commands=['/command'],
            examples=[]
        )

        # Act
        formatted = format_help_category(category)

        # Assert
        assert len(formatted) > 0
        # Examples section should not appear
        assert "📚 Examples" not in formatted

    def test_formatted_markdown_formatting(self):
        """Test that formatted output has proper Markdown formatting."""
        # Arrange
        category = HelpContent.get_category('setup')

        # Act
        formatted = format_help_category(category)

        # Assert
        assert "**" in formatted  # Bold text
        assert "\n" in formatted  # Line breaks
        assert "`" in formatted or "/" in formatted  # Code or commands


# =============================================================================
# create_example_help() Function Tests
# =============================================================================

class TestCreateExampleHelp:
    """Test suite for create_example_help() utility function."""

    def test_create_example_help_returns_tuple(self):
        """Test that create_example_help returns a tuple."""
        # Arrange & Act
        result = create_example_help()

        # Assert
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_create_example_help_text_is_string(self):
        """Test that first element (text) is a string."""
        # Arrange & Act
        text, keyboard = create_example_help()

        # Assert
        assert isinstance(text, str)
        assert len(text) > 0

    def test_create_example_help_keyboard_is_dict(self):
        """Test that second element (keyboard) is a dict."""
        # Arrange & Act
        text, keyboard = create_example_help()

        # Assert
        assert isinstance(keyboard, dict)
        assert 'inline_keyboard' in keyboard

    def test_create_example_help_text_is_main_menu(self):
        """Test that returned text is the main menu."""
        # Arrange & Act
        text, keyboard = create_example_help()
        expected_menu = HelpContent.get_main_menu()

        # Assert
        assert text == expected_menu

    def test_create_example_help_keyboard_matches_category_keyboard(self):
        """Test that returned keyboard matches category keyboard."""
        # Arrange & Act
        text, keyboard = create_example_help()
        expected_keyboard = HelpContent.create_category_keyboard()

        # Assert
        assert keyboard == expected_keyboard


# =============================================================================
# Integration Tests
# =============================================================================

class TestHelpSystemIntegration:
    """Integration tests for the complete help system workflow."""

    def test_complete_help_navigation_flow(self):
        """Test complete user flow through help system."""
        # Arrange & Act
        # 1. Get main menu
        main_menu = HelpContent.get_main_menu()
        main_keyboard = HelpContent.create_category_keyboard()

        # 2. Navigate to a category
        setup_category = HelpContent.get_category('setup')
        setup_text = format_help_category(setup_category)
        setup_keyboard = HelpContent.create_navigation_keyboard('setup')

        # 3. Navigate to next category
        manage_category = HelpContent.get_category('manage')
        manage_text = format_help_category(manage_category)
        manage_keyboard = HelpContent.create_navigation_keyboard('manage')

        # Assert
        assert main_menu
        assert main_keyboard['inline_keyboard']
        assert setup_text
        assert setup_keyboard['inline_keyboard']
        assert manage_text
        assert manage_keyboard['inline_keyboard']

    def test_all_categories_have_complete_content(self):
        """Test that all categories have complete, well-formed content."""
        # Arrange & Act & Assert
        for cat_id in HelpContent.CATEGORY_ORDER:
            category = HelpContent.get_category(cat_id)

            # Verify category exists and has all fields
            assert category is not None
            assert category.id
            assert category.emoji
            assert category.title
            assert category.description
            assert category.content
            assert len(category.commands) > 0
            assert len(category.examples) > 0

            # Verify formatting works
            formatted = format_help_category(category)
            assert len(formatted) > 0

            # Verify navigation works
            keyboard = HelpContent.create_navigation_keyboard(cat_id)
            assert keyboard['inline_keyboard']

    def test_help_system_consistency(self):
        """Test consistency across all help system components."""
        # Arrange
        categories = HelpContent.CATEGORIES
        category_order = HelpContent.CATEGORY_ORDER

        # Act & Assert
        # All ordered categories should exist in CATEGORIES dict
        for cat_id in category_order:
            assert cat_id in categories

        # All categories in dict should be in order
        for cat_id in categories.keys():
            assert cat_id in category_order

        # Category count should match
        assert len(categories) == len(category_order)


# =============================================================================
# Edge Cases and Error Conditions
# =============================================================================

class TestHelpSystemEdgeCases:
    """Test suite for edge cases and error conditions."""

    def test_get_category_with_empty_string(self):
        """Test get_category with empty string returns None."""
        # Arrange & Act
        category = HelpContent.get_category('')

        # Assert
        assert category is None

    def test_get_category_with_none(self):
        """Test get_category with None raises appropriate error."""
        # Arrange & Act & Assert
        # This might raise TypeError or return None depending on implementation
        try:
            category = HelpContent.get_category(None)
            assert category is None
        except TypeError:
            # Also acceptable behavior
            pass

    def test_create_navigation_keyboard_with_empty_string(self):
        """Test create_navigation_keyboard with empty string."""
        # Arrange & Act
        keyboard = HelpContent.create_navigation_keyboard('')

        # Assert
        # Should still create a keyboard structure
        assert 'inline_keyboard' in keyboard

    def test_format_help_category_with_minimal_category(self):
        """Test formatting a category with minimal content."""
        # Arrange
        minimal_category = HelpCategory(
            id='minimal',
            emoji='📄',
            title='Minimal',
            description='Minimal description',
            content='Minimal content',
            commands=[],
            examples=[]
        )

        # Act
        formatted = format_help_category(minimal_category)

        # Assert
        assert len(formatted) > 0
        assert 'Minimal' in formatted
        assert 'Minimal content' in formatted

    def test_category_with_special_characters(self):
        """Test category with special characters in content."""
        # Arrange
        category = HelpCategory(
            id='special',
            emoji='🎨',
            title='Special <>&',
            description='Test @#$%',
            content='Content with **bold** and `code`',
            commands=['/test <arg>'],
            examples=['Example with * and _']
        )

        # Act
        formatted = format_help_category(category)

        # Assert
        assert len(formatted) > 0
        assert 'Special <>&' in formatted
        assert '**bold**' in formatted
