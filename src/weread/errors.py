class WereadError(Exception):
    """Base exception for all weread errors."""

class LoginExpiredError(WereadError):
    """Cookie expired and user did not complete login."""

class ChapterLoadError(WereadError):
    """Chapter failed to render within timeout."""
    def __init__(self, chapter_num: int, chapter_name: str, reason: str):
        self.chapter_num = chapter_num
        self.chapter_name = chapter_name
        super().__init__(f"Chapter {chapter_num} ({chapter_name}): {reason}")

class ConvertError(WereadError):
    """Format conversion failed."""
    def __init__(self, format_name: str, reason: str):
        self.format_name = format_name
        super().__init__(f"Failed to convert to {format_name}: {reason}")
