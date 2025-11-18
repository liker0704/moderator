"""
Confirmation dialog framework for Telegram interactions.

This module provides reusable confirmation dialogs for actions that require
user confirmation before execution (e.g., toggles, deletions, updates).

Key components:
- ConfirmationDialog: Dataclass representing a confirmation dialog
- ConfirmationBuilder: Factory class for creating standardized confirmations
- Format utilities: For Telegram-compatible text and keyboard formatting

Confirmation dialogs display:
- Title and main message
- Additional details or consequences
- Warning messages when appropriate
- Confirm/Cancel buttons with appropriate callback data

Typical workflow:
1. Create confirmation with ConfirmationBuilder
2. Format for Telegram with format_confirmation()
3. Send to user with inline keyboard
4. Handle confirmation/cancellation in callback handlers
"""

from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ConfirmationDialog:
    """
    Represents a confirmation dialog for user actions.

    Attributes:
        title: Dialog title (e.g., "⚠️ Confirm Action")
        message: Main message describing the action
        details: Optional additional details or context
        warning: Optional warning message to highlight risks/consequences
        confirm_text: Text for confirm button (default: "✅ Confirm")
        cancel_text: Text for cancel button (default: "❌ Cancel")
        confirm_callback: Callback data for confirm button
        cancel_callback: Callback data for cancel button
        metadata: Additional metadata for state tracking
    """
    title: str
    message: str
    details: Optional[str] = None
    warning: Optional[str] = None
    confirm_text: str = "✅ Confirm"
    cancel_text: str = "❌ Cancel"
    confirm_callback: str = ""
    cancel_callback: str = ""
    metadata: Optional[Dict[str, Any]] = None


class ConfirmationBuilder:
    """
    Factory class for creating standardized confirmation dialogs.

    Provides static methods for common confirmation types:
    - Removal confirmations (deleting channels, clearing data, etc.)
    - Toggle confirmations (enabling/disabling features)
    - Update confirmations (changing settings, configurations, etc.)

    All methods return ConfirmationDialog instances that can be
    formatted for Telegram using format_confirmation().
    """

    @staticmethod
    def create_removal_confirmation(
        item_type: str,
        item_name: str,
        item_id: Any,
        consequences: Optional[str] = None
    ) -> ConfirmationDialog:
        """
        Create a confirmation dialog for removing/deleting an item.

        Args:
            item_type: Type of item being removed (e.g., "channel", "task", "reply")
            item_name: Display name of the item
            item_id: Identifier for the item
            consequences: Optional description of what happens when removed

        Returns:
            ConfirmationDialog configured for removal action

        Example:
            >>> dialog = ConfirmationBuilder.create_removal_confirmation(
            ...     item_type="channel",
            ...     item_name="#general",
            ...     item_id="123456789",
            ...     consequences="Messages from this channel will no longer be monitored"
            ... )
        """
        message = f"Remove {item_type} **{item_name}**?"

        details = f"ID: `{item_id}`"
        if consequences:
            details += f"\n\n{consequences}"

        warning = "⚠️ This action cannot be undone."

        return ConfirmationDialog(
            title=f"🗑️ Remove {item_type.capitalize()}",
            message=message,
            details=details,
            warning=warning,
            confirm_text="🗑️ Remove",
            cancel_text="❌ Cancel",
            confirm_callback=f"confirm_remove_{item_type}_{item_id}",
            cancel_callback=f"cancel_remove_{item_type}_{item_id}",
            metadata={
                "action": "remove",
                "item_type": item_type,
                "item_id": item_id
            }
        )

    @staticmethod
    def create_toggle_confirmation(
        feature: str,
        current_state: bool,
        effects: Optional[str] = None,
        feature_id: Optional[str] = None
    ) -> ConfirmationDialog:
        """
        Create a confirmation dialog for toggling a feature on/off.

        Args:
            feature: Name of the feature being toggled (e.g., "DND Mode", "Notifications")
            current_state: Current state (True=enabled, False=disabled)
            effects: Optional description of what happens when toggled
            feature_id: Optional identifier for the feature (for callback routing)

        Returns:
            ConfirmationDialog configured for toggle action

        Example:
            >>> dialog = ConfirmationBuilder.create_toggle_confirmation(
            ...     feature="DND Mode",
            ...     current_state=False,
            ...     effects="You will not receive message notifications",
            ...     feature_id="dnd"
            ... )
        """
        new_state = not current_state
        new_state_text = "ON" if new_state else "OFF"
        current_state_text = "ON" if current_state else "OFF"

        # Determine emoji and action text
        if new_state:
            emoji = "🔕"
            action = "Enable"
        else:
            emoji = "🔔"
            action = "Disable"

        message = f"{action} **{feature}**?"

        details = f"Current: {current_state_text} → New: **{new_state_text}**"

        if effects:
            details += f"\n\n{effects}"

        # Build callback data
        feature_slug = feature_id or feature.lower().replace(" ", "_")

        return ConfirmationDialog(
            title=f"{emoji} {action} {feature}",
            message=message,
            details=details,
            warning=None,
            confirm_text=f"{emoji} {action}",
            cancel_text="❌ Cancel",
            confirm_callback=f"confirm_toggle_{feature_slug}_{new_state}",
            cancel_callback=f"cancel_toggle_{feature_slug}",
            metadata={
                "action": "toggle",
                "feature": feature,
                "feature_id": feature_slug,
                "current_state": current_state,
                "new_state": new_state
            }
        )

    @staticmethod
    def format_confirmation(dialog: ConfirmationDialog) -> tuple[str, dict]:
        """
        Format a ConfirmationDialog for Telegram display.

        Converts dialog into formatted message text and inline keyboard
        that can be sent via bot.send_message().

        Args:
            dialog: ConfirmationDialog to format

        Returns:
            Tuple of (formatted_text, inline_keyboard_dict)

        Example:
            >>> text, keyboard = ConfirmationBuilder.format_confirmation(dialog)
            >>> await bot.send_message(chat_id, text, reply_markup=keyboard)
        """
        # Build message text
        lines = [dialog.title, ""]

        lines.append(dialog.message)

        if dialog.details:
            lines.append("")
            lines.append(dialog.details)

        if dialog.warning:
            lines.append("")
            lines.append(dialog.warning)

        text = "\n".join(lines)

        # Build inline keyboard
        keyboard = {
            'inline_keyboard': [
                [
                    {
                        'text': dialog.confirm_text,
                        'callback_data': dialog.confirm_callback
                    },
                    {
                        'text': dialog.cancel_text,
                        'callback_data': dialog.cancel_callback
                    }
                ]
            ]
        }

        logger.debug(f"Formatted confirmation: {dialog.title}")

        return text, keyboard


def create_dnd_toggle_confirmation(current_state: bool) -> ConfirmationDialog:
    """
    Create a confirmation dialog specifically for DND mode toggle.

    This is a convenience function that uses ConfirmationBuilder with
    DND-specific messaging and effects.

    Args:
        current_state: Current DND state (True=enabled, False=disabled)

    Returns:
        ConfirmationDialog configured for DND toggle

    Example:
        >>> dialog = create_dnd_toggle_confirmation(current_state=False)
        >>> text, keyboard = ConfirmationBuilder.format_confirmation(dialog)
        >>> await bot.send_message(chat_id, text, reply_markup=keyboard)
    """
    new_state = not current_state

    if new_state:
        # Enabling DND
        effects = (
            "📵 Effects when enabled:\n"
            "• You will NOT receive message cards\n"
            "• Tasks will still be created and stored\n"
            "• You can check pending tasks anytime\n"
            "• Useful during meetings, sleep, or focus time"
        )
    else:
        # Disabling DND
        effects = (
            "🔔 Effects when disabled:\n"
            "• You will receive message cards normally\n"
            "• New messages trigger instant notifications\n"
            "• Full moderation workflow active"
        )

    return ConfirmationBuilder.create_toggle_confirmation(
        feature="Do Not Disturb",
        current_state=current_state,
        effects=effects,
        feature_id="dnd"
    )
