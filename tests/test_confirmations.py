"""
Comprehensive unit tests for the confirmation framework.

Tests cover:
- ConfirmationDialog dataclass structure and attributes
- ConfirmationBuilder.create_removal_confirmation() with various item types
- ConfirmationBuilder.create_toggle_confirmation() for feature toggles
- ConfirmationBuilder.format_confirmation() output structure
- create_dnd_toggle_confirmation() for DND mode
- Confirmation text includes proper state transitions
- Confirmation shows appropriate effects and warnings
- Keyboard structure and callback data formatting
"""

import os
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

from backend.src.telegram.confirmations import (
    ConfirmationDialog,
    ConfirmationBuilder,
    create_dnd_toggle_confirmation
)


# =============================================================================
# ConfirmationDialog Dataclass Tests
# =============================================================================

class TestConfirmationDialog:
    """Test suite for ConfirmationDialog dataclass."""

    def test_confirmation_dialog_creation_all_fields(self):
        """Test creating ConfirmationDialog with all fields."""
        # Arrange & Act
        dialog = ConfirmationDialog(
            title="Test Title",
            message="Test message",
            details="Test details",
            warning="Test warning",
            confirm_text="Confirm",
            cancel_text="Cancel",
            confirm_callback="confirm_test",
            cancel_callback="cancel_test",
            metadata={"key": "value"}
        )

        # Assert
        assert dialog.title == "Test Title"
        assert dialog.message == "Test message"
        assert dialog.details == "Test details"
        assert dialog.warning == "Test warning"
        assert dialog.confirm_text == "Confirm"
        assert dialog.cancel_text == "Cancel"
        assert dialog.confirm_callback == "confirm_test"
        assert dialog.cancel_callback == "cancel_test"
        assert dialog.metadata == {"key": "value"}

    def test_confirmation_dialog_minimal_fields(self):
        """Test creating ConfirmationDialog with only required fields."""
        # Arrange & Act
        dialog = ConfirmationDialog(
            title="Title",
            message="Message"
        )

        # Assert
        assert dialog.title == "Title"
        assert dialog.message == "Message"
        assert dialog.details is None
        assert dialog.warning is None
        assert dialog.confirm_text == "✅ Confirm"
        assert dialog.cancel_text == "❌ Cancel"
        assert dialog.confirm_callback == ""
        assert dialog.cancel_callback == ""
        assert dialog.metadata is None

    def test_confirmation_dialog_default_button_texts(self):
        """Test that default button texts have emojis."""
        # Arrange & Act
        dialog = ConfirmationDialog(
            title="Test",
            message="Test"
        )

        # Assert
        assert "✅" in dialog.confirm_text
        assert "❌" in dialog.cancel_text
        assert "Confirm" in dialog.confirm_text
        assert "Cancel" in dialog.cancel_text

    def test_confirmation_dialog_optional_details(self):
        """Test ConfirmationDialog with optional details field."""
        # Arrange & Act
        dialog = ConfirmationDialog(
            title="Test",
            message="Test",
            details="Additional details here"
        )

        # Assert
        assert dialog.details == "Additional details here"

    def test_confirmation_dialog_optional_warning(self):
        """Test ConfirmationDialog with optional warning field."""
        # Arrange & Act
        dialog = ConfirmationDialog(
            title="Test",
            message="Test",
            warning="⚠️ Warning message"
        )

        # Assert
        assert dialog.warning == "⚠️ Warning message"

    def test_confirmation_dialog_metadata_dict(self):
        """Test ConfirmationDialog with metadata dictionary."""
        # Arrange
        metadata = {
            "action": "delete",
            "item_id": 123,
            "item_type": "channel"
        }

        # Act
        dialog = ConfirmationDialog(
            title="Test",
            message="Test",
            metadata=metadata
        )

        # Assert
        assert dialog.metadata == metadata
        assert dialog.metadata["action"] == "delete"
        assert dialog.metadata["item_id"] == 123


# =============================================================================
# ConfirmationBuilder - Removal Confirmation Tests
# =============================================================================

class TestCreateRemovalConfirmation:
    """Test suite for ConfirmationBuilder.create_removal_confirmation()."""

    def test_create_removal_confirmation_basic(self):
        """Test creating basic removal confirmation."""
        # Arrange & Act
        dialog = ConfirmationBuilder.create_removal_confirmation(
            item_type="channel",
            item_name="#general",
            item_id="123456789"
        )

        # Assert
        assert dialog.title == "🗑️ Remove Channel"
        assert "#general" in dialog.message
        assert "Remove channel" in dialog.message
        assert "123456789" in dialog.details
        assert dialog.warning == "⚠️ This action cannot be undone."
        assert "🗑️" in dialog.confirm_text
        assert "Remove" in dialog.confirm_text
        assert "❌" in dialog.cancel_text

    def test_create_removal_confirmation_with_consequences(self):
        """Test creating removal confirmation with consequences."""
        # Arrange
        consequences = "Messages from this channel will no longer be monitored"

        # Act
        dialog = ConfirmationBuilder.create_removal_confirmation(
            item_type="channel",
            item_name="#general",
            item_id="123456789",
            consequences=consequences
        )

        # Assert
        assert consequences in dialog.details

    def test_create_removal_confirmation_callback_data(self):
        """Test that removal confirmation has correct callback data."""
        # Arrange & Act
        dialog = ConfirmationBuilder.create_removal_confirmation(
            item_type="channel",
            item_name="#test",
            item_id="999"
        )

        # Assert
        assert dialog.confirm_callback == "confirm_remove_channel_999"
        assert dialog.cancel_callback == "cancel_remove_channel_999"

    def test_create_removal_confirmation_metadata(self):
        """Test that removal confirmation has proper metadata."""
        # Arrange & Act
        dialog = ConfirmationBuilder.create_removal_confirmation(
            item_type="task",
            item_name="Task #42",
            item_id="42"
        )

        # Assert
        assert dialog.metadata is not None
        assert dialog.metadata["action"] == "remove"
        assert dialog.metadata["item_type"] == "task"
        assert dialog.metadata["item_id"] == "42"

    def test_create_removal_confirmation_different_item_types(self):
        """Test creating removal confirmations for different item types."""
        # Arrange
        item_types = ["channel", "task", "reply", "user", "setting"]

        # Act & Assert
        for item_type in item_types:
            dialog = ConfirmationBuilder.create_removal_confirmation(
                item_type=item_type,
                item_name=f"Test {item_type}",
                item_id="123"
            )
            assert item_type.capitalize() in dialog.title
            assert item_type in dialog.message.lower()

    def test_create_removal_confirmation_title_capitalization(self):
        """Test that removal confirmation title capitalizes item type."""
        # Arrange & Act
        dialog = ConfirmationBuilder.create_removal_confirmation(
            item_type="channel",
            item_name="#test",
            item_id="123"
        )

        # Assert
        assert "Channel" in dialog.title  # Capitalized
        assert dialog.title.startswith("🗑️")

    def test_create_removal_confirmation_item_id_formatting(self):
        """Test that item ID is formatted with code markup."""
        # Arrange & Act
        dialog = ConfirmationBuilder.create_removal_confirmation(
            item_type="channel",
            item_name="#test",
            item_id="987654321"
        )

        # Assert
        assert "`987654321`" in dialog.details

    def test_create_removal_confirmation_no_consequences(self):
        """Test removal confirmation without consequences."""
        # Arrange & Act
        dialog = ConfirmationBuilder.create_removal_confirmation(
            item_type="channel",
            item_name="#test",
            item_id="123"
        )

        # Assert
        # Details should only have ID, not consequences
        assert "ID:" in dialog.details
        assert "123" in dialog.details


# =============================================================================
# ConfirmationBuilder - Toggle Confirmation Tests
# =============================================================================

class TestCreateToggleConfirmation:
    """Test suite for ConfirmationBuilder.create_toggle_confirmation()."""

    def test_create_toggle_confirmation_enable(self):
        """Test creating toggle confirmation for enabling a feature."""
        # Arrange & Act
        dialog = ConfirmationBuilder.create_toggle_confirmation(
            feature="DND Mode",
            current_state=False  # Currently OFF, toggling to ON
        )

        # Assert
        assert "Enable" in dialog.message
        assert "DND Mode" in dialog.message
        assert "OFF" in dialog.details  # Current state
        assert "ON" in dialog.details  # New state
        assert "Enable" in dialog.confirm_text

    def test_create_toggle_confirmation_disable(self):
        """Test creating toggle confirmation for disabling a feature."""
        # Arrange & Act
        dialog = ConfirmationBuilder.create_toggle_confirmation(
            feature="Notifications",
            current_state=True  # Currently ON, toggling to OFF
        )

        # Assert
        assert "Disable" in dialog.message
        assert "Notifications" in dialog.message
        assert "ON" in dialog.details  # Current state
        assert "OFF" in dialog.details  # New state
        assert "Disable" in dialog.confirm_text

    def test_create_toggle_confirmation_state_transition(self):
        """Test that toggle confirmation shows state transition."""
        # Arrange & Act
        dialog = ConfirmationBuilder.create_toggle_confirmation(
            feature="Test Feature",
            current_state=False
        )

        # Assert
        assert "OFF" in dialog.details
        assert "ON" in dialog.details
        assert "→" in dialog.details  # Arrow showing transition

    def test_create_toggle_confirmation_with_effects(self):
        """Test creating toggle confirmation with effects description."""
        # Arrange
        effects = "You will not receive notifications during this time"

        # Act
        dialog = ConfirmationBuilder.create_toggle_confirmation(
            feature="DND Mode",
            current_state=False,
            effects=effects
        )

        # Assert
        assert effects in dialog.details

    def test_create_toggle_confirmation_callback_data(self):
        """Test that toggle confirmation has correct callback data."""
        # Arrange & Act
        dialog = ConfirmationBuilder.create_toggle_confirmation(
            feature="DND Mode",
            current_state=False,
            feature_id="dnd"
        )

        # Assert
        assert dialog.confirm_callback == "confirm_toggle_dnd_True"
        assert dialog.cancel_callback == "cancel_toggle_dnd"

    def test_create_toggle_confirmation_callback_with_new_state(self):
        """Test that confirm callback includes new state."""
        # Arrange & Act
        # Current state is True (ON), so new state will be False (OFF)
        dialog = ConfirmationBuilder.create_toggle_confirmation(
            feature="Test",
            current_state=True,
            feature_id="test"
        )

        # Assert
        assert "False" in dialog.confirm_callback  # New state is False

    def test_create_toggle_confirmation_metadata(self):
        """Test that toggle confirmation has proper metadata."""
        # Arrange & Act
        dialog = ConfirmationBuilder.create_toggle_confirmation(
            feature="DND Mode",
            current_state=False,
            feature_id="dnd"
        )

        # Assert
        assert dialog.metadata is not None
        assert dialog.metadata["action"] == "toggle"
        assert dialog.metadata["feature"] == "DND Mode"
        assert dialog.metadata["feature_id"] == "dnd"
        assert dialog.metadata["current_state"] is False
        assert dialog.metadata["new_state"] is True

    def test_create_toggle_confirmation_feature_id_auto_generation(self):
        """Test that feature_id is auto-generated from feature name if not provided."""
        # Arrange & Act
        dialog = ConfirmationBuilder.create_toggle_confirmation(
            feature="DND Mode",
            current_state=False
        )

        # Assert
        # Should convert "DND Mode" to "dnd_mode"
        assert "dnd_mode" in dialog.confirm_callback

    def test_create_toggle_confirmation_no_warning(self):
        """Test that toggle confirmations don't have warnings by default."""
        # Arrange & Act
        dialog = ConfirmationBuilder.create_toggle_confirmation(
            feature="Test",
            current_state=False
        )

        # Assert
        assert dialog.warning is None

    def test_create_toggle_confirmation_emoji_enable(self):
        """Test that enabling uses correct emoji."""
        # Arrange & Act
        dialog = ConfirmationBuilder.create_toggle_confirmation(
            feature="DND Mode",
            current_state=False  # Enabling
        )

        # Assert
        assert "🔕" in dialog.title or "🔕" in dialog.confirm_text

    def test_create_toggle_confirmation_emoji_disable(self):
        """Test that disabling uses correct emoji."""
        # Arrange & Act
        dialog = ConfirmationBuilder.create_toggle_confirmation(
            feature="DND Mode",
            current_state=True  # Disabling
        )

        # Assert
        assert "🔔" in dialog.title or "🔔" in dialog.confirm_text


# =============================================================================
# ConfirmationBuilder - Format Confirmation Tests
# =============================================================================

class TestFormatConfirmation:
    """Test suite for ConfirmationBuilder.format_confirmation()."""

    def test_format_confirmation_returns_tuple(self):
        """Test that format_confirmation returns a tuple."""
        # Arrange
        dialog = ConfirmationDialog(
            title="Test",
            message="Test message"
        )

        # Act
        result = ConfirmationBuilder.format_confirmation(dialog)

        # Assert
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_format_confirmation_text_structure(self):
        """Test that formatted text has correct structure."""
        # Arrange
        dialog = ConfirmationDialog(
            title="Test Title",
            message="Test message",
            details="Test details",
            warning="Test warning"
        )

        # Act
        text, keyboard = ConfirmationBuilder.format_confirmation(dialog)

        # Assert
        assert isinstance(text, str)
        assert "Test Title" in text
        assert "Test message" in text
        assert "Test details" in text
        assert "Test warning" in text

    def test_format_confirmation_keyboard_structure(self):
        """Test that formatted keyboard has correct structure."""
        # Arrange
        dialog = ConfirmationDialog(
            title="Test",
            message="Test",
            confirm_callback="confirm_test",
            cancel_callback="cancel_test"
        )

        # Act
        text, keyboard = ConfirmationBuilder.format_confirmation(dialog)

        # Assert
        assert isinstance(keyboard, dict)
        assert 'inline_keyboard' in keyboard
        assert len(keyboard['inline_keyboard']) == 1  # One row
        assert len(keyboard['inline_keyboard'][0]) == 2  # Two buttons

    def test_format_confirmation_button_structure(self):
        """Test that formatted buttons have correct structure."""
        # Arrange
        dialog = ConfirmationDialog(
            title="Test",
            message="Test",
            confirm_text="Confirm",
            cancel_text="Cancel",
            confirm_callback="confirm",
            cancel_callback="cancel"
        )

        # Act
        text, keyboard = ConfirmationBuilder.format_confirmation(dialog)
        buttons = keyboard['inline_keyboard'][0]

        # Assert
        assert len(buttons) == 2
        # First button (confirm)
        assert buttons[0]['text'] == "Confirm"
        assert buttons[0]['callback_data'] == "confirm"
        # Second button (cancel)
        assert buttons[1]['text'] == "Cancel"
        assert buttons[1]['callback_data'] == "cancel"

    def test_format_confirmation_text_without_details(self):
        """Test formatting confirmation without details."""
        # Arrange
        dialog = ConfirmationDialog(
            title="Test Title",
            message="Test message"
        )

        # Act
        text, keyboard = ConfirmationBuilder.format_confirmation(dialog)

        # Assert
        assert "Test Title" in text
        assert "Test message" in text
        # Should not have empty lines for missing details

    def test_format_confirmation_text_without_warning(self):
        """Test formatting confirmation without warning."""
        # Arrange
        dialog = ConfirmationDialog(
            title="Test Title",
            message="Test message",
            details="Test details"
        )

        # Act
        text, keyboard = ConfirmationBuilder.format_confirmation(dialog)

        # Assert
        assert "Test details" in text
        # Warning should not appear

    def test_format_confirmation_text_line_breaks(self):
        """Test that formatted text has proper line breaks."""
        # Arrange
        dialog = ConfirmationDialog(
            title="Title",
            message="Message",
            details="Details",
            warning="Warning"
        )

        # Act
        text, keyboard = ConfirmationBuilder.format_confirmation(dialog)

        # Assert
        assert "\n" in text  # Has line breaks
        lines = text.split("\n")
        assert len(lines) > 1

    def test_format_confirmation_complete_removal_dialog(self):
        """Test formatting a complete removal confirmation dialog."""
        # Arrange
        dialog = ConfirmationBuilder.create_removal_confirmation(
            item_type="channel",
            item_name="#test",
            item_id="123",
            consequences="This will stop monitoring"
        )

        # Act
        text, keyboard = ConfirmationBuilder.format_confirmation(dialog)

        # Assert
        assert "Remove Channel" in text
        assert "#test" in text
        assert "123" in text
        assert "This will stop monitoring" in text
        assert "cannot be undone" in text
        assert len(keyboard['inline_keyboard']) == 1
        assert len(keyboard['inline_keyboard'][0]) == 2

    def test_format_confirmation_complete_toggle_dialog(self):
        """Test formatting a complete toggle confirmation dialog."""
        # Arrange
        dialog = ConfirmationBuilder.create_toggle_confirmation(
            feature="DND Mode",
            current_state=False,
            effects="You will not receive notifications"
        )

        # Act
        text, keyboard = ConfirmationBuilder.format_confirmation(dialog)

        # Assert
        assert "DND Mode" in text or "Do Not Disturb" in text
        assert "OFF" in text
        assert "ON" in text
        assert "You will not receive notifications" in text


# =============================================================================
# DND Toggle Confirmation Tests
# =============================================================================

class TestCreateDndToggleConfirmation:
    """Test suite for create_dnd_toggle_confirmation() function."""

    def test_dnd_toggle_enable(self):
        """Test creating DND toggle confirmation for enabling DND."""
        # Arrange & Act
        dialog = create_dnd_toggle_confirmation(current_state=False)

        # Assert
        assert "Do Not Disturb" in dialog.title or "DND" in dialog.message
        assert "Enable" in dialog.message or "Enable" in dialog.confirm_text

    def test_dnd_toggle_disable(self):
        """Test creating DND toggle confirmation for disabling DND."""
        # Arrange & Act
        dialog = create_dnd_toggle_confirmation(current_state=True)

        # Assert
        assert "Disable" in dialog.message or "Disable" in dialog.confirm_text

    def test_dnd_toggle_enable_effects(self):
        """Test that enabling DND shows appropriate effects."""
        # Arrange & Act
        dialog = create_dnd_toggle_confirmation(current_state=False)

        # Assert
        assert "Effects when enabled" in dialog.details or "📵" in dialog.details
        assert "NOT receive message cards" in dialog.details or "not receive" in dialog.details.lower()
        assert "Tasks will still be created" in dialog.details or "tasks" in dialog.details.lower()

    def test_dnd_toggle_disable_effects(self):
        """Test that disabling DND shows appropriate effects."""
        # Arrange & Act
        dialog = create_dnd_toggle_confirmation(current_state=True)

        # Assert
        assert "Effects when disabled" in dialog.details or "🔔" in dialog.details
        assert "receive message cards normally" in dialog.details or "receive" in dialog.details.lower()

    def test_dnd_toggle_state_transition(self):
        """Test that DND toggle shows state transition."""
        # Arrange & Act
        dialog = create_dnd_toggle_confirmation(current_state=False)

        # Assert
        # Should show OFF → ON transition
        assert "OFF" in dialog.details
        assert "ON" in dialog.details

    def test_dnd_toggle_feature_id(self):
        """Test that DND toggle has correct feature_id in callbacks."""
        # Arrange & Act
        dialog = create_dnd_toggle_confirmation(current_state=False)

        # Assert
        assert "dnd" in dialog.confirm_callback
        assert "dnd" in dialog.cancel_callback

    def test_dnd_toggle_metadata(self):
        """Test that DND toggle has proper metadata."""
        # Arrange & Act
        dialog = create_dnd_toggle_confirmation(current_state=False)

        # Assert
        assert dialog.metadata is not None
        assert dialog.metadata["action"] == "toggle"
        assert dialog.metadata["feature_id"] == "dnd"
        assert dialog.metadata["current_state"] is False
        assert dialog.metadata["new_state"] is True

    def test_dnd_toggle_formatting(self):
        """Test that DND toggle can be formatted correctly."""
        # Arrange
        dialog = create_dnd_toggle_confirmation(current_state=False)

        # Act
        text, keyboard = ConfirmationBuilder.format_confirmation(dialog)

        # Assert
        assert text
        assert keyboard
        assert 'inline_keyboard' in keyboard

    def test_dnd_toggle_enable_mentions_benefits(self):
        """Test that enabling DND mentions benefits/use cases."""
        # Arrange & Act
        dialog = create_dnd_toggle_confirmation(current_state=False)

        # Assert
        # Should mention use cases like meetings, sleep, focus time
        details_lower = dialog.details.lower()
        assert any(keyword in details_lower for keyword in ['meeting', 'sleep', 'focus'])

    def test_dnd_toggle_disable_mentions_normal_operation(self):
        """Test that disabling DND mentions normal operation."""
        # Arrange & Act
        dialog = create_dnd_toggle_confirmation(current_state=True)

        # Assert
        # Should mention normal notifications/workflow
        details_lower = dialog.details.lower()
        assert any(keyword in details_lower for keyword in ['normal', 'active', 'receive'])


# =============================================================================
# Integration Tests
# =============================================================================

class TestConfirmationIntegration:
    """Integration tests for the complete confirmation workflow."""

    def test_removal_confirmation_complete_flow(self):
        """Test complete flow for removal confirmation."""
        # Arrange & Act
        # 1. Create removal confirmation
        dialog = ConfirmationBuilder.create_removal_confirmation(
            item_type="channel",
            item_name="#general",
            item_id="123456789",
            consequences="Messages will no longer be monitored"
        )

        # 2. Format for Telegram
        text, keyboard = ConfirmationBuilder.format_confirmation(dialog)

        # Assert
        # Dialog should be properly created
        assert dialog.title
        assert dialog.message
        assert dialog.warning
        # Text should be formatted
        assert "#general" in text
        assert "cannot be undone" in text
        # Keyboard should be ready
        assert len(keyboard['inline_keyboard']) == 1
        assert keyboard['inline_keyboard'][0][0]['text']  # Confirm button
        assert keyboard['inline_keyboard'][0][1]['text']  # Cancel button

    def test_toggle_confirmation_complete_flow(self):
        """Test complete flow for toggle confirmation."""
        # Arrange & Act
        # 1. Create toggle confirmation
        dialog = ConfirmationBuilder.create_toggle_confirmation(
            feature="DND Mode",
            current_state=False,
            effects="No notifications during this time",
            feature_id="dnd"
        )

        # 2. Format for Telegram
        text, keyboard = ConfirmationBuilder.format_confirmation(dialog)

        # Assert
        # Dialog should be properly created
        assert dialog.title
        assert dialog.message
        assert dialog.metadata
        # Text should show state transition
        assert "OFF" in text
        assert "ON" in text
        # Keyboard should be ready
        assert keyboard['inline_keyboard']

    def test_dnd_confirmation_complete_flow(self):
        """Test complete flow for DND-specific confirmation."""
        # Arrange & Act
        # 1. Create DND confirmation
        dialog = create_dnd_toggle_confirmation(current_state=False)

        # 2. Format for Telegram
        text, keyboard = ConfirmationBuilder.format_confirmation(dialog)

        # Assert
        # Should have DND-specific content
        assert "Do Not Disturb" in text or "DND" in text
        assert "message cards" in text.lower() or "notifications" in text.lower()
        # Should be fully formatted
        assert text
        assert keyboard
        assert len(keyboard['inline_keyboard']) > 0


# =============================================================================
# Edge Cases and Error Conditions
# =============================================================================

class TestConfirmationEdgeCases:
    """Test suite for edge cases and error conditions."""

    def test_removal_confirmation_empty_item_name(self):
        """Test removal confirmation with empty item name."""
        # Arrange & Act
        dialog = ConfirmationBuilder.create_removal_confirmation(
            item_type="channel",
            item_name="",
            item_id="123"
        )

        # Assert
        assert dialog.message  # Should still create message

    def test_removal_confirmation_numeric_item_id(self):
        """Test removal confirmation with numeric item ID."""
        # Arrange & Act
        dialog = ConfirmationBuilder.create_removal_confirmation(
            item_type="task",
            item_name="Task",
            item_id=12345  # Numeric instead of string
        )

        # Assert
        assert "12345" in dialog.details

    def test_toggle_confirmation_empty_effects(self):
        """Test toggle confirmation with empty effects string."""
        # Arrange & Act
        dialog = ConfirmationBuilder.create_toggle_confirmation(
            feature="Test",
            current_state=False,
            effects=""
        )

        # Assert
        assert dialog.details  # Should still have state transition

    def test_format_confirmation_empty_callback_data(self):
        """Test formatting confirmation with empty callback data."""
        # Arrange
        dialog = ConfirmationDialog(
            title="Test",
            message="Test"
        )

        # Act
        text, keyboard = ConfirmationBuilder.format_confirmation(dialog)

        # Assert
        # Should still create keyboard with empty callbacks
        assert keyboard['inline_keyboard'][0][0]['callback_data'] == ""
        assert keyboard['inline_keyboard'][0][1]['callback_data'] == ""

    def test_confirmation_with_special_characters(self):
        """Test confirmation with special characters in content."""
        # Arrange
        dialog = ConfirmationDialog(
            title="Test <>&",
            message="Message with **bold** and `code`",
            details="Details with @#$%"
        )

        # Act
        text, keyboard = ConfirmationBuilder.format_confirmation(dialog)

        # Assert
        assert "Test <>&" in text
        assert "**bold**" in text
        assert "`code`" in text
        assert "@#$%" in text

    def test_confirmation_with_multiline_content(self):
        """Test confirmation with multiline content."""
        # Arrange
        dialog = ConfirmationDialog(
            title="Title",
            message="Line 1\nLine 2",
            details="Detail 1\nDetail 2\nDetail 3"
        )

        # Act
        text, keyboard = ConfirmationBuilder.format_confirmation(dialog)

        # Assert
        assert "Line 1\nLine 2" in text
        assert "Detail 1\nDetail 2\nDetail 3" in text

    def test_removal_confirmation_none_consequences(self):
        """Test removal confirmation with None consequences (not empty string)."""
        # Arrange & Act
        dialog = ConfirmationBuilder.create_removal_confirmation(
            item_type="channel",
            item_name="#test",
            item_id="123",
            consequences=None
        )

        # Assert
        # Should not include consequences section
        assert dialog.details
        assert "ID:" in dialog.details
