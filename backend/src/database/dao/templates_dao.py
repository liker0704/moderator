"""
Templates Data Access Object.

Provides async database operations for templates table using asyncpg.
Handles template creation, retrieval, update, deletion, and usage tracking.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import asyncpg


class TemplatesDAO:
    """
    Data Access Object for templates table.

    Manages quick reply templates for moderators.
    """

    @staticmethod
    async def create_template(
        conn: asyncpg.Connection,
        user_id: int,
        name: str,
        content: str,
    ) -> int:
        """
        Create a new template for a user.

        Args:
            conn: AsyncPG database connection
            user_id: User ID who owns the template
            name: Template name (unique per user)
            content: Template content

        Returns:
            int: ID of the created template

        Raises:
            asyncpg.UniqueViolationError: If template with same name exists for user
            asyncpg.ForeignKeyViolationError: If user_id is invalid
            asyncpg.PostgresError: On other database errors

        Example:
            >>> template_id = await TemplatesDAO.create_template(
            ...     conn=conn,
            ...     user_id=1,
            ...     name='greeting',
            ...     content='Hello {{author}}! Welcome to our community.'
            ... )
        """
        query = """
            INSERT INTO templates (user_id, name, content, created_at, updated_at, usage_count)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """

        now = datetime.utcnow()
        row = await conn.fetchrow(query, user_id, name, content, now, now, 0)
        return row['id']

    @staticmethod
    async def get_templates(
        conn: asyncpg.Connection,
        user_id: int,
        order_by: str = 'created_at',
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all templates for a user.

        Args:
            conn: AsyncPG database connection
            user_id: User ID
            order_by: Sort order - 'created_at', 'usage_count', or 'name' (default: created_at)
            limit: Maximum number of templates to return (optional)

        Returns:
            List of template dictionaries ordered by specified field

        Example:
            >>> # Get all templates ordered by creation date
            >>> templates = await TemplatesDAO.get_templates(conn, user_id=1)
            >>>
            >>> # Get top 3 most used templates
            >>> popular = await TemplatesDAO.get_templates(
            ...     conn, user_id=1, order_by='usage_count', limit=3
            ... )
        """
        # Validate order_by to prevent SQL injection
        valid_orders = {
            'created_at': 'created_at DESC',
            'usage_count': 'usage_count DESC',
            'name': 'name ASC',
        }

        if order_by not in valid_orders:
            order_by = 'created_at'

        order_clause = valid_orders[order_by]

        query = f"""
            SELECT id, user_id, name, content, created_at, updated_at, usage_count
            FROM templates
            WHERE user_id = $1
            ORDER BY {order_clause}
        """

        if limit:
            query += f" LIMIT {int(limit)}"

        rows = await conn.fetch(query, user_id)
        return [dict(row) for row in rows]

    @staticmethod
    async def get_template_by_id(
        conn: asyncpg.Connection,
        template_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a template by ID.

        Args:
            conn: AsyncPG database connection
            template_id: Template ID

        Returns:
            Dictionary with template data or None if not found

        Example:
            >>> template = await TemplatesDAO.get_template_by_id(conn, 123)
            >>> if template:
            ...     print(f"Template: {template['name']}")
        """
        query = """
            SELECT id, user_id, name, content, created_at, updated_at, usage_count
            FROM templates
            WHERE id = $1
        """

        row = await conn.fetchrow(query, template_id)
        return dict(row) if row else None

    @staticmethod
    async def get_template_by_name(
        conn: asyncpg.Connection,
        user_id: int,
        name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a template by name for a specific user.

        Args:
            conn: AsyncPG database connection
            user_id: User ID
            name: Template name

        Returns:
            Dictionary with template data or None if not found

        Example:
            >>> template = await TemplatesDAO.get_template_by_name(
            ...     conn, user_id=1, name='greeting'
            ... )
        """
        query = """
            SELECT id, user_id, name, content, created_at, updated_at, usage_count
            FROM templates
            WHERE user_id = $1 AND name = $2
        """

        row = await conn.fetchrow(query, user_id, name)
        return dict(row) if row else None

    @staticmethod
    async def update_template(
        conn: asyncpg.Connection,
        user_id: int,
        name: str,
        content: str,
    ) -> bool:
        """
        Update template content.

        Args:
            conn: AsyncPG database connection
            user_id: User ID
            name: Template name
            content: New template content

        Returns:
            True if template was updated, False if template not found

        Example:
            >>> updated = await TemplatesDAO.update_template(
            ...     conn, user_id=1, name='greeting',
            ...     content='Updated greeting message'
            ... )
        """
        query = """
            UPDATE templates
            SET content = $1,
                updated_at = $2
            WHERE user_id = $3 AND name = $4
        """

        result = await conn.execute(query, content, datetime.utcnow(), user_id, name)
        return result.split()[-1] != '0'

    @staticmethod
    async def delete_template(
        conn: asyncpg.Connection,
        user_id: int,
        name: str,
    ) -> bool:
        """
        Delete a template by name.

        Args:
            conn: AsyncPG database connection
            user_id: User ID
            name: Template name

        Returns:
            True if template was deleted, False if template not found

        Example:
            >>> deleted = await TemplatesDAO.delete_template(
            ...     conn, user_id=1, name='greeting'
            ... )
        """
        query = """
            DELETE FROM templates
            WHERE user_id = $1 AND name = $2
        """

        result = await conn.execute(query, user_id, name)
        return result.split()[-1] != '0'

    @staticmethod
    async def delete_template_by_id(
        conn: asyncpg.Connection,
        template_id: int,
    ) -> bool:
        """
        Delete a template by ID.

        Args:
            conn: AsyncPG database connection
            template_id: Template ID

        Returns:
            True if template was deleted, False if template not found

        Example:
            >>> deleted = await TemplatesDAO.delete_template_by_id(conn, 123)
        """
        query = """
            DELETE FROM templates
            WHERE id = $1
        """

        result = await conn.execute(query, template_id)
        return result.split()[-1] != '0'

    @staticmethod
    async def increment_usage(
        conn: asyncpg.Connection,
        template_id: int,
    ) -> bool:
        """
        Increment the usage count for a template.

        Args:
            conn: AsyncPG database connection
            template_id: Template ID

        Returns:
            True if usage was incremented, False if template not found

        Example:
            >>> incremented = await TemplatesDAO.increment_usage(conn, 123)
        """
        query = """
            UPDATE templates
            SET usage_count = usage_count + 1,
                updated_at = $1
            WHERE id = $2
        """

        result = await conn.execute(query, datetime.utcnow(), template_id)
        return result.split()[-1] != '0'

    @staticmethod
    async def get_template_count(
        conn: asyncpg.Connection,
        user_id: int,
    ) -> int:
        """
        Get the total number of templates for a user.

        Args:
            conn: AsyncPG database connection
            user_id: User ID

        Returns:
            Number of templates

        Example:
            >>> count = await TemplatesDAO.get_template_count(conn, user_id=1)
            >>> print(f"User has {count} templates")
        """
        query = """
            SELECT COUNT(*) as count
            FROM templates
            WHERE user_id = $1
        """

        row = await conn.fetchrow(query, user_id)
        return row['count'] if row else 0

    @staticmethod
    async def search_templates(
        conn: asyncpg.Connection,
        user_id: int,
        search_term: str,
    ) -> List[Dict[str, Any]]:
        """
        Search templates by name or content.

        Args:
            conn: AsyncPG database connection
            user_id: User ID
            search_term: Search term (case-insensitive)

        Returns:
            List of matching template dictionaries

        Example:
            >>> results = await TemplatesDAO.search_templates(
            ...     conn, user_id=1, search_term='welcome'
            ... )
        """
        query = """
            SELECT id, user_id, name, content, created_at, updated_at, usage_count
            FROM templates
            WHERE user_id = $1
                AND (
                    LOWER(name) LIKE LOWER($2)
                    OR LOWER(content) LIKE LOWER($2)
                )
            ORDER BY usage_count DESC, name ASC
        """

        search_pattern = f"%{search_term}%"
        rows = await conn.fetch(query, user_id, search_pattern)
        return [dict(row) for row in rows]

    @staticmethod
    def substitute_variables(
        content: str,
        variables: Dict[str, str],
    ) -> str:
        """
        Substitute variables in template content.

        Supports variable substitution in the format {{variable_name}}.

        Args:
            content: Template content with variables
            variables: Dictionary of variable name -> value mappings

        Returns:
            Content with variables substituted

        Example:
            >>> content = "Hello {{author}}! Welcome to {{channel}}."
            >>> variables = {'author': 'John', 'channel': '#general'}
            >>> result = TemplatesDAO.substitute_variables(content, variables)
            >>> print(result)
            'Hello John! Welcome to #general.'
        """
        result = content

        for var_name, var_value in variables.items():
            placeholder = f"{{{{{var_name}}}}}"
            result = result.replace(placeholder, str(var_value))

        return result

    @staticmethod
    def extract_variables(content: str) -> List[str]:
        """
        Extract variable names from template content.

        Args:
            content: Template content

        Returns:
            List of variable names found in the template

        Example:
            >>> content = "Hello {{author}}! Welcome to {{channel}}."
            >>> variables = TemplatesDAO.extract_variables(content)
            >>> print(variables)
            ['author', 'channel']
        """
        import re

        # Match {{variable_name}} pattern
        pattern = r'\{\{(\w+)\}\}'
        matches = re.findall(pattern, content)

        return matches
