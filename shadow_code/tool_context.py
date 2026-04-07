import os


class ToolContext:
    """Shared state accessible by all tools.

    Holds the current working directory (updated by bash after cd/pushd)
    and the set of files that have been read (used by edit_file validation).
    """

    def __init__(self, initial_cwd: str):
        self.cwd = initial_cwd
        self.read_files: set[str] = set()
        self.backups: dict[str, bytes] = {}  # file_path -> content for file_backup/restore

    def mark_file_read(self, path: str):
        self.read_files.add(os.path.abspath(path))

    def was_file_read(self, path: str) -> bool:
        return os.path.abspath(path) in self.read_files
