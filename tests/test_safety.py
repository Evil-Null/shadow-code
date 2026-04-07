"""Tests for safety.py -- destructive command detection."""

import unittest

from shadow_code.safety import check_destructive


class TestCheckDestructive(unittest.TestCase):
    """Tests for check_destructive()."""

    # --- Safe commands (should return None) ---

    def test_safe_echo(self):
        self.assertIsNone(check_destructive("echo hello"))

    def test_safe_ls(self):
        self.assertIsNone(check_destructive("ls -la"))

    def test_safe_git_commit(self):
        self.assertIsNone(check_destructive("git commit -m 'fix bug'"))

    def test_safe_git_push(self):
        self.assertIsNone(check_destructive("git push origin main"))

    def test_safe_rm_single_file(self):
        self.assertIsNone(check_destructive("rm file.txt"))

    def test_empty_string(self):
        self.assertIsNone(check_destructive(""))

    def test_none_like_empty(self):
        self.assertIsNone(check_destructive("   "))

    # --- Destructive: rm -rf variants ---

    def test_rm_rf(self):
        result = check_destructive("rm -rf /")
        self.assertIsNotNone(result)
        self.assertIn("Recursive force delete", result)

    def test_rm_rf_dir(self):
        result = check_destructive("rm -rf /tmp/mydir")
        self.assertIsNotNone(result)

    def test_rm_fr(self):
        result = check_destructive("rm -fr /tmp/mydir")
        self.assertIsNotNone(result)

    # --- Destructive: git force push ---

    def test_git_push_force(self):
        result = check_destructive("git push --force origin main")
        self.assertIsNotNone(result)
        self.assertIn("Force push", result)

    def test_git_push_f(self):
        result = check_destructive("git push -f origin main")
        self.assertIsNotNone(result)

    # --- Destructive: git reset --hard ---

    def test_git_reset_hard(self):
        result = check_destructive("git reset --hard HEAD~3")
        self.assertIsNotNone(result)
        self.assertIn("Hard reset", result)

    # --- Destructive: git clean -f ---

    def test_git_clean_f(self):
        result = check_destructive("git clean -fd")
        self.assertIsNotNone(result)
        self.assertIn("Git clean", result)

    # --- Destructive: git branch -D ---

    def test_git_branch_D(self):
        result = check_destructive("git branch -D feature-branch")
        self.assertIsNotNone(result)
        self.assertIn("Force delete branch", result)

    # --- Destructive: SQL ---

    def test_drop_table(self):
        result = check_destructive("DROP TABLE users;")
        self.assertIsNotNone(result)
        self.assertIn("DROP TABLE", result)

    def test_drop_table_case_insensitive(self):
        result = check_destructive("drop table users;")
        self.assertIsNotNone(result)

    def test_truncate_table(self):
        result = check_destructive("TRUNCATE TABLE logs;")
        self.assertIsNotNone(result)
        self.assertIn("TRUNCATE TABLE", result)

    def test_drop_database(self):
        result = check_destructive("DROP DATABASE mydb;")
        self.assertIsNotNone(result)
        self.assertIn("DROP DATABASE", result)

    # --- Destructive: system-level ---

    def test_mkfs(self):
        result = check_destructive("mkfs.ext4 /dev/sda1")
        self.assertIsNotNone(result)
        self.assertIn("Format filesystem", result)

    def test_dd(self):
        result = check_destructive("dd if=/dev/zero of=/dev/sda")
        self.assertIsNotNone(result)
        self.assertIn("Raw disk write", result)

    def test_block_device_write(self):
        result = check_destructive("echo foo > /dev/sda")
        self.assertIsNotNone(result)
        self.assertIn("block device", result)

    def test_chmod_777(self):
        result = check_destructive("chmod -R 777 /var/www")
        self.assertIsNotNone(result)
        self.assertIn("world-writable", result)

    def test_sudo_rm(self):
        result = check_destructive("sudo rm -rf /")
        self.assertIsNotNone(result)
        self.assertIn("Privileged delete", result)

    # --- Multiple patterns matched ---

    def test_multiple_matches(self):
        result = check_destructive("sudo rm -rf / && git push --force")
        self.assertIsNotNone(result)
        self.assertIn("Recursive force delete", result)
        self.assertIn("Privileged delete", result)
        self.assertIn("Force push", result)

    # --- Warning format ---

    def test_warning_contains_command(self):
        result = check_destructive("rm -rf /important")
        self.assertIn("rm -rf /important", result)
        self.assertIn("WARNING", result)


if __name__ == "__main__":
    unittest.main()
