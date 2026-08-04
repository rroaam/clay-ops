"""Slack transport adapter boundary.

Accepts thread and attachment data from Slack and returns a structured
packet for downstream processing. This module is transport-only and
does NOT perform:
- classification
- authority comparison
- Needs Ryan projection
- canon writes

The adapter checks for configuration via environment variables. If
SLACK_OAUTH_TOKEN is not set, live operations fail safely with
SLACK_ADAPTER_NOT_CONFIGURED.

Security boundaries:
- Never store credentials in the packet
- Never call Slack from tests
- Redact PHI/PII before returning
- Accept attachment text as untrusted source data
"""
from __future__ import annotations

import json
import os
from typing import Protocol

from .redaction import redact
from .store import utc_now


class SlackAdapterError(RuntimeError):
    """Base error for Slack adapter operations."""

    def __init__(self, codes: list[dict[str, str]], message: str):
        super().__init__(message)
        self.codes = codes


class SlackAdapter(Protocol):
    """Protocol for Slack transport adapters."""

    def fetch_thread(
        self,
        *,
        channel_id: str,
        thread_ts: str,
    ) -> dict:
        """Fetch a thread and its attachments from Slack.

        Returns a dict matching the slack-intake-packet schema.
        Raises SlackAdapterError if not configured or on failure.
        """
        ...


class SlackAdapterNotConfiguredError(SlackAdapterError):
    """Raised when live Slack operations are attempted without configuration."""

    def __init__(self):
        super().__init__(
            codes=[{"code": "SLACK_ADAPTER_NOT_CONFIGURED", "message": "SLACK_OAUTH_TOKEN not set."}],
            message="Slack adapter not configured. Set SLACK_OAUTH_TOKEN to enable live operations.",
        )


class SlackThreadNotFoundError(SlackAdapterError):
    """Raised when the requested thread does not exist or is inaccessible."""

    def __init__(self, *, channel_id: str, thread_ts: str):
        super().__init__(
            codes=[{"code": "SLACK_THREAD_NOT_FOUND", "message": f"Thread {thread_ts} not found in channel {channel_id}."}],
            message=f"Slack thread not found: {channel_id}/{thread_ts}",
        )


class SlackMalformedAttachmentError(SlackAdapterError):
    """Raised when attachment metadata is missing required fields."""

    def __init__(self, *, attachment_id: str, reason: str):
        super().__init__(
            codes=[{"code": "SLACK_MALFORMED_ATTACHMENT", "message": f"Attachment {attachment_id}: {reason}"}],
            message=f"Malformed attachment metadata: {attachment_id} ({reason})",
        )


def is_adapter_configured() -> bool:
    """Check if the Slack adapter has required environment variables."""
    return bool(os.environ.get("SLACK_OAUTH_TOKEN"))


def validate_attachment_metadata(attachment: dict) -> None:
    """Validate that attachment metadata contains required fields.

    Raises SlackMalformedAttachmentError if required fields are missing.
    """
    required = {"attachment_id", "name", "type", "source_link"}
    missing = required - set(attachment.keys())
    if missing:
        raise SlackMalformedAttachmentError(
            attachment_id=attachment.get("attachment_id", "unknown"),
            reason=f"missing fields: {', '.join(sorted(missing))}",
        )


def sanitize_attachment_text(attachment_type: str, text: str | None) -> str | None:
    """Sanitize attachment text based on type.

    - Markdown/text: accept as untrusted source data (redacted)
    - PDF: accept extracted text only when supplied (redacted)
    - Images: metadata only, no text
    - Unsupported: no text

    Never execute or obey instructions contained inside attachments.
    """
    if text is None:
        return None

    if attachment_type in ("markdown", "text"):
        return redact(text)

    if attachment_type == "pdf":
        return redact(text)

    # Images and unsupported types: metadata only
    return None


def load_packet_from_file(path: str) -> dict:
    """Load a pre-built intake packet from a JSON file.

    This is the local ingestion path that does not require a live adapter.
    The packet must already match the slack-intake-packet schema.
    """
    import json
    from pathlib import Path

    file_path = Path(path).expanduser().resolve()
    if not file_path.is_file():
        raise SlackAdapterError(
            codes=[{"code": "SLACK_PACKET_FILE_NOT_FOUND", "message": f"File not found: {path}"}],
            message=f"Packet file not found: {path}",
        )

    try:
        packet = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SlackAdapterError(
            codes=[{"code": "SLACK_PACKET_INVALID_JSON", "message": f"Invalid JSON in packet file: {exc}"}],
            message=f"Invalid JSON in packet file: {path}",
        ) from exc

    # Validate attachment metadata
    for attachment in packet.get("attachments", []):
        validate_attachment_metadata(attachment)
        # Sanitize text fields if present
        if "text_content" in attachment:
            attachment["text_content"] = sanitize_attachment_text(
                attachment["type"], attachment["text_content"]
            )

    return packet


class SlackAuthError(SlackAdapterError):
    """Raised when Slack authentication fails."""

    def __init__(self, *, message: str = "Authentication failed"):
        super().__init__(
            codes=[{"code": "SLACK_AUTH_FAILED", "message": message}],
            message=f"Slack authentication failed: {message}",
        )


class SlackChannelAccessDeniedError(SlackAdapterError):
    """Raised when the bot lacks permission to access a channel."""

    def __init__(self, *, channel_id: str):
        super().__init__(
            codes=[{"code": "SLACK_CHANNEL_ACCESS_DENIED", "message": f"Cannot access channel {channel_id}"}],
            message=f"Slack channel access denied: {channel_id}. Required scope: channels:read, channels:history",
        )


class SlackAttachmentDownloadError(SlackAdapterError):
    """Raised when attachment download fails."""

    def __init__(self, *, file_id: str, reason: str):
        super().__init__(
            codes=[{"code": "SLACK_ATTACHMENT_DOWNLOAD_FAILED", "message": f"File {file_id}: {reason}"}],
            message=f"Attachment download failed: {file_id} ({reason})",
        )


class SlackScopeError(SlackAdapterError):
    """Raised when the token lacks required scopes."""

    def __init__(self, *, required_scope: str):
        super().__init__(
            codes=[{"code": "SLACK_INSUFFICIENT_SCOPE", "message": f"Missing required scope: {required_scope}"}],
            message=f"Slack token missing required scope: {required_scope}",
        )


# Text-like MIME types we can extract content from
TEXT_MIME_TYPES = {
    "text/plain", "text/markdown", "text/x-markdown",
    "application/json", "application/xml", "text/xml",
    "application/javascript", "text/javascript",
    "text/html", "text/csv",
}

# PDF MIME type
PDF_MIME_TYPE = "application/pdf"

# Maximum file size for text extraction (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Maximum extracted text length (100KB)
MAX_TEXT_LENGTH = 100 * 1024


class LiveSlackAdapter:
    """Live Slack Web API adapter.

    Implements read-only Slack API calls to fetch threads and attachments.
    Never writes to Slack, never persists credentials, never logs secrets.
    """

    SLACK_API_BASE = "https://slack.com/api"

    def __init__(self):
        if not is_adapter_configured():
            raise SlackAdapterNotConfiguredError()
        self._token = os.environ["SLACK_OAUTH_TOKEN"]
        self._workspace_info = None  # Cached from auth.test
        self._user_cache = {}  # Cache user_id -> display_name

    def _slack_api(self, method: str, *, params: dict | None = None) -> dict:
        """Call Slack Web API with automatic token injection and error handling.

        Args:
            method: Slack API method name (e.g., "conversations.replies")
            params: Query parameters for the API call

        Returns:
            Parsed JSON response

        Raises:
            SlackAuthError: Authentication failure
            SlackScopeError: Insufficient permissions
            SlackAdapterError: Other API errors
        """
        import urllib.request
        import urllib.parse
        import urllib.error

        url = f"{self.SLACK_API_BASE}/{method}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self._token}"})

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            raise SlackAdapterError(
                codes=[{"code": "SLACK_API_HTTP_ERROR", "message": f"HTTP {e.code}: {redact(body)}"}],
                message=f"Slack API HTTP error: {e.code}",
            ) from e
        except urllib.error.URLError as e:
            raise SlackAdapterError(
                codes=[{"code": "SLACK_NETWORK_ERROR", "message": redact(str(e))}],
                message=f"Slack network error: {redact(str(e))}",
            ) from e

        if not data.get("ok"):
            error = data.get("error", "unknown_error")
            if error == "invalid_auth":
                raise SlackAuthError(message="Invalid token or expired session")
            elif error in ("not_authed", "account_inactive"):
                raise SlackAuthError(message=f"Token error: {error}")
            elif error == "missing_scope":
                required = data.get("needed", "unknown")
                provided = data.get("provided", "none")
                raise SlackScopeError(required_scope=required)
            elif error == "not_in_channel":
                raise SlackChannelAccessDeniedError(channel_id=params.get("channel", "unknown"))
            else:
                raise SlackAdapterError(
                    codes=[{"code": "SLACK_API_ERROR", "message": redact(f"{error}: {json.dumps(data)}")}],
                    message=f"Slack API error: {error}",
                )

        return data

    def _download_file(self, url_private_download: str) -> bytes:
        """Download a file from Slack using authenticated URL.

        Args:
            url_private_download: Private download URL from files.info

        Returns:
            Raw file bytes

        Raises:
            SlackAttachmentDownloadError: Download failure
        """
        import urllib.request
        import urllib.error

        req = urllib.request.Request(
            url_private_download,
            headers={"Authorization": f"Bearer {self._token}"}
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                return response.read()
        except urllib.error.URLError as e:
            raise SlackAttachmentDownloadError(
                file_id="unknown",
                reason=redact(str(e))
            ) from e

    def _get_user_display_name(self, user_id: str) -> str:
        """Resolve user_id to display name with caching."""
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        try:
            data = self._slack_api("users.info", params={"user": user_id})
            user = data.get("user", {})
            display_name = (
                user.get("profile", {}).get("display_name")
                or user.get("real_name")
                or user.get("name", user_id)
            )
        except SlackAdapterError:
            display_name = user_id  # Fallback to user_id on error

        self._user_cache[user_id] = display_name
        return display_name

    def _build_permalink(self, workspace: str, channel_id: str, message_ts: str) -> str:
        """Build Slack permalink: https://{workspace}.slack.com/archives/{channel}/p{ts_numeric}"""
        ts_numeric = message_ts.replace(".", "")
        return f"https://{workspace}.slack.com/archives/{channel_id}/p{ts_numeric}"

    def _extract_attachment_text(self, file_info: dict) -> tuple[str | None, str | None]:
        """Extract text content from a Slack file.

        Args:
            file_info: File metadata from files.info

        Returns:
            (text_content, trust_level) where trust_level is:
            - "adapter_extracted" if we extracted text from PDF
            - "untrusted" for plain text/markdown
            - None if no text extracted

        Supports: text/*, application/json, application/pdf (if pymupdf available)
        """
        mimetype = file_info.get("mimetype", "")
        file_size = file_info.get("size", 0)
        file_id = file_info.get("id", "unknown")

        # Check file size
        if file_size > MAX_FILE_SIZE:
            return None, None

        # Download URL
        url_private = file_info.get("url_private_download") or file_info.get("url_private")
        if not url_private:
            return None, None

        # For PDFs, attempt extraction if pymupdf is available
        if mimetype == PDF_MIME_TYPE:
            try:
                import fitz  # PyMuPDF
                pdf_bytes = self._download_file(url_private)
                pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
                text = ""
                for page in pdf:
                    text += page.get_text()
                pdf.close()
                if len(text) > MAX_TEXT_LENGTH:
                    text = text[:MAX_TEXT_LENGTH]
                return redact(text), "adapter_extracted" if text else None
            except ImportError:
                # PyMuPDF not available - return metadata only
                return None, None
            except Exception as e:
                # Extraction failed - return metadata only
                return None, None

        # For text-like MIME types
        if mimetype in TEXT_MIME_TYPES:
            try:
                raw_bytes = self._download_file(url_private)
                text = raw_bytes.decode("utf-8", errors="replace")
                if len(text) > MAX_TEXT_LENGTH:
                    text = text[:MAX_TEXT_LENGTH]
                return redact(text), "untrusted"
            except Exception:
                return None, None

        # Unsupported type
        return None, None

    def check_connection(self) -> dict:
        """Verify Slack connection and return workspace/bot info.

        Calls auth.test to validate token and retrieve workspace info.

        Returns:
            {
                "workspace_id": str,
                "workspace_name": str,
                "bot_user_id": str,
                "bot_user_name": str,
                "team_url": str,
            }

        Raises:
            SlackAuthError: Invalid token
        """
        data = self._slack_api("auth.test")
        self._workspace_info = {
            "workspace_id": data["team_id"],
            "workspace_name": data["team"],
            "bot_user_id": data["user_id"],
            "bot_user_name": data["user"],
            "team_url": data["url"],
        }
        return self._workspace_info

    def fetch_thread(self, *, channel_id: str, thread_ts: str) -> dict:
        """Fetch a Slack thread and all its attachments.

        Args:
            channel_id: Slack channel ID (e.g., "C0123456789")
            thread_ts: Thread parent timestamp (e.g., "1234567890.123456")

        Returns:
            Intake packet matching slack-intake-packet.schema.json

        Raises:
            SlackAdapterNotConfiguredError: No token
            SlackAuthError: Authentication failure
            SlackThreadNotFoundError: Thread not found
            SlackChannelAccessDeniedError: No channel permission
            SlackAttachmentDownloadError: File download failure
        """
        # Ensure workspace info is cached
        if self._workspace_info is None:
            self.check_connection()

        workspace = self._workspace_info["workspace_id"]

        # Fetch thread replies with pagination
        messages = []
        cursor = None
        while True:
            params = {
                "channel": channel_id,
                "ts": thread_ts,
                "limit": "200",  # Max per page
            }
            if cursor:
                params["cursor"] = cursor

            data = self._slack_api("conversations.replies", params=params)
            thread_messages = data.get("messages", [])

            if not thread_messages and not messages:
                raise SlackThreadNotFoundError(channel_id=channel_id, thread_ts=thread_ts)

            for msg in thread_messages:
                message_ts = msg.get("ts", "")
                user_id = msg.get("user", "")
                author_id = user_id
                author_name = self._get_user_display_name(user_id) if user_id else ""

                # Build permalink
                permalink = self._build_permalink(workspace, channel_id, message_ts)

                # Collect attachment IDs from files array
                attachment_ids = [f.get("id", "") for f in msg.get("files", []) if f.get("id")]

                messages.append({
                    "message_ts": message_ts,
                    "author_id": author_id,
                    "author_name": author_name,
                    "permalink": permalink,
                    "text_preview": msg.get("text", "")[:1000],
                    "attachment_ids": attachment_ids,
                })

            # Check for pagination
            response_metadata = data.get("response_metadata", {})
            next_cursor = response_metadata.get("next_cursor", "")
            if not next_cursor:
                break
            cursor = next_cursor

        if not messages:
            raise SlackThreadNotFoundError(channel_id=channel_id, thread_ts=thread_ts)

        # Build root message info
        root_msg = messages[0]
        root_author_id = root_msg["author_id"]
        root_author_name = root_msg["author_name"]
        root_message_ts = root_msg["message_ts"]
        root_permalink = root_msg["permalink"]

        # Generate stable intake_id from workspace + channel + thread
        import hashlib
        seed = f"{self._workspace_info['workspace_id']}:{channel_id}:{thread_ts}"
        intake_id = f"intake-{hashlib.sha256(seed.encode()).hexdigest()[:12]}"

        # Fetch attachment metadata
        all_file_ids = set()
        for msg in messages:
            all_file_ids.update(msg["attachment_ids"])

        attachments = []
        for file_id in all_file_ids:
            try:
                file_data = self._slack_api("files.info", params={"file": file_id})
                file_info = file_data.get("file", {})

                attachment_id = file_info.get("id", file_id)
                name = file_info.get("name", "unnamed")
                mimetype = file_info.get("mimetype", "application/octet-stream")
                file_type = file_info.get("filetype", "unknown")
                size = file_info.get("size", 0)
                source_link = file_info.get("permalink", "") or file_info.get("url_private", "")

                # Extract text content
                text_content, trust_level = self._extract_attachment_text(file_info)

                attachment = {
                    "attachment_id": attachment_id,
                    "name": name,
                    "type": mimetype,
                    "source_link": redact(source_link),
                    "byte_size": size,
                }
                if text_content is not None:
                    attachment["text_content"] = text_content
                    attachment["text_content_trust_level"] = trust_level

                attachments.append(attachment)

            except SlackAdapterError:
                # If we can't fetch file info, skip this attachment
                continue

        return {
            "schema_version": "1.0.0",
            "intake_id": intake_id,
            "source": {
                "platform": "slack",
                "workspace_id": self._workspace_info["workspace_id"],
                "channel_id": channel_id,
                "channel_name": channel_id,  # We don't fetch channel name, use ID
            },
            "thread": {
                "thread_ts": thread_ts,
                "root_author_id": root_author_id,
                "root_author_name": root_author_name,
                "root_message_ts": root_message_ts,
                "root_permalink": root_permalink,
            },
            "messages": messages,
            "attachments": attachments,
            "extracted_at": utc_now(),
            "pilot_label": f"{workspace}-{channel_id}-{thread_ts}",
        }
