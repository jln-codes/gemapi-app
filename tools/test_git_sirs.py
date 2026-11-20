#!/usr/bin/env python3
"""Integration tests using isolated bare remotes; never access business databases."""

from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import git_sirs as policy


class GitSirsTests(unittest.TestCase):
    def setUp(self):
        audits = Path(__file__).resolve().parents[1] / "audits"
        audits.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="git-sirs-test-", dir=audits)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / "origin.git"
        self.repo = self.root / "common"
        self.repo.mkdir()
        policy.git(self.repo, "init", "--bare", str(self.remote))
        policy.git(self.repo, "init", "-b", "development")
        policy.git(self.repo, "config", "user.name", "Test")
        policy.git(self.repo, "config", "user.email", "test@example.invalid")
        policy.git(self.repo, "config", "commit.gpgsign", "false")
        policy.git(self.repo, "remote", "add", "origin", str(self.remote))
        self.commit(self.repo, ".gitignore", "/audits/\n__pycache__/\n")
        for name in ("AGENTS.md", "demo/data.txt", "cabbalr/data.txt", "plugin/code.py", "common.txt"):
            self.commit(self.repo, name, "initial\n")
        self.initial = policy.sha(self.repo, "HEAD")
        policy.git(self.repo, "branch", "main")
        policy.git(self.repo, "branch", "sirs")
        policy.git(self.repo, "push", "origin", "development", "main", "sirs")
        policy.fetch(self.repo)
        self.work = self.root / "sirs-worktree"
        policy.git(self.repo, "worktree", "add", str(self.work), "sirs")
        self.main = policy.sha(self.remote, "main")

    def tearDown(self):
        # Every scenario preserves main and all protected data directories.
        self.assertEqual(policy.sha(self.remote, "main"), self.main)
        for directory in ("demo", "cabbalr", "plugin"):
            self.assertTrue(policy.git(self.remote, "ls-tree", "-r", "--name-only", "sirs",
                                       "--", directory).stdout)

    def commit(self, repo, name, content):
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        policy.git(repo, "add", name)
        policy.git(repo, "commit", "-m", f"Update {name}")
        return policy.sha(repo, "HEAD")

    def development(self, name="common.txt", content="new common\n"):
        commit = self.commit(self.repo, name, content)
        policy.git(self.repo, "push", "origin", "development")
        return commit

    def specialized(self, name="sirs/schema.sql", content="specialized\n"):
        commit = self.commit(self.work, name, content)
        policy.git(self.work, "push", "origin", "sirs")
        return commit

    def assert_synced(self, *preserved):
        policy.fetch(self.repo)
        self.assertTrue(policy.ancestor(self.repo, "origin/development", "origin/sirs"))
        for commit in preserved:
            self.assertTrue(policy.ancestor(self.repo, commit, "origin/sirs"))
        self.assertEqual(policy.git(self.repo, "show", "origin/development:AGENTS.md").stdout,
                         policy.git(self.repo, "show", "origin/sirs:AGENTS.md").stdout)

    def test_new_commit(self):
        self.development()
        policy.sync(self.repo)
        self.assert_synced()

    def test_successive_pushes_and_multiple_commits(self):
        commits = []
        for index in range(3):
            commits.append(self.development(f"change-{index}.txt", f"change {index}\n"))
        policy.sync(self.repo)
        self.assert_synced(*commits)
        later = self.development("later.txt")
        policy.sync(self.repo)
        self.assert_synced(later, *commits)

    def test_specialized_commits_preserved_normal_merge(self):
        special = self.specialized()
        self.development()
        policy.sync(self.repo)
        self.assert_synced(special)
        parents = policy.git(self.repo, "show", "-s", "--format=%P", "origin/sirs").stdout.split()
        self.assertEqual(len(parents), 2)
        self.assertEqual(policy.git(self.repo, "show", "origin/sirs:sirs/schema.sql").stdout, "specialized\n")

    def test_no_new_commit_no_push(self):
        with patch.object(policy, "git", wraps=policy.git) as calls:
            policy.sync(self.repo)
        self.assertFalse(any("push" in call.args[1:] for call in calls.call_args_list))
        self.assertEqual(policy.sha(self.remote, "sirs"), self.initial)

    def test_no_new_common_commit_with_sirs_commits(self):
        special = self.specialized()
        policy.sync(self.repo)
        self.assertEqual(policy.sha(self.remote, "sirs"), special)

    def test_protected_mode_pending_pr_is_not_success(self):
        self.development()
        original = policy.subprocess.run

        def gh_pending(args, **kwargs):
            if args[0] != "gh":
                return original(args, **kwargs)
            output = '[]' if args[1:3] == ["pr", "list"] else 'https://github.com/jln-codes/gemapi-app/pull/1'
            return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")

        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "jln-codes/gemapi-app"}):
            with patch.object(policy.subprocess, "run", side_effect=gh_pending):
                with self.assertRaisesRegex(policy.Refused, "PR en attente"):
                    policy.sync(self.repo, mode="pull-request")
        self.assertEqual(policy.sha(self.remote, "sirs"), self.initial)

    def test_protected_mode_reuses_pr_and_checks_actual_remote(self):
        development = self.development()
        original = policy.subprocess.run
        commands = []

        def gh_merged(args, **kwargs):
            if args[0] != "gh":
                return original(args, **kwargs)
            commands.append(args)
            if args[1:3] == ["pr", "list"]:
                output = '[{"url":"https://github.com/jln-codes/gemapi-app/pull/1"}]'
            else:
                policy.git(self.remote, "update-ref", "refs/heads/sirs", development, self.initial)
                output = "merged"
            return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")

        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "jln-codes/gemapi-app"}):
            with patch.object(policy.subprocess, "run", side_effect=gh_merged):
                policy.sync(self.repo, mode="pull-request")
        self.assert_synced()
        self.assertFalse(any(args[1:3] == ["pr", "create"] for args in commands))

    def test_simultaneous_non_conflicting_edits_same_file(self):
        lines = "".join(f"line {index}\n" for index in range(30))
        self.development(content=lines)
        policy.sync(self.repo)
        policy.update(self.repo, self.work)
        special = self.specialized("common.txt", lines.replace("line 1\n", "SIRS line\n"))
        self.development(content=lines.replace("line 28\n", "Common line\n"))
        policy.sync(self.repo)
        self.assert_synced(special)
        merged = policy.git(self.repo, "show", "origin/sirs:common.txt").stdout
        self.assertIn("SIRS line", merged)
        self.assertIn("Common line", merged)

    def test_conflict_no_remote_or_local_change(self):
        special = self.specialized("common.txt", "SIRS value\n")
        self.development(content="common value\n")
        before = policy.sha(self.repo, "HEAD")
        with self.assertRaisesRegex(policy.Refused, "Conflits.*|common.txt"):
            policy.sync(self.repo)
        self.assertEqual(policy.sha(self.remote, "sirs"), special)
        self.assertEqual(policy.sha(self.repo, "HEAD"), before)
        self.assertEqual((self.work / "common.txt").read_text(), "SIRS value\n")
        self.assertEqual(len(policy.git(self.repo, "worktree", "list", "--porcelain").stdout.split("worktree ")) - 1, 2)

    def test_concurrent_sirs_push_retry_preserves_both(self):
        self.development()
        original = policy.git
        concurrent = []

        def race(repo, *args, **kwargs):
            if args[:3] == ("push", "origin", "HEAD:refs/heads/sirs") and not concurrent:
                concurrent.append(self.specialized())
            return original(repo, *args, **kwargs)

        with patch.object(policy, "git", side_effect=race):
            policy.sync(self.repo)
        self.assert_synced(*concurrent)

    def test_development_push_during_sync_integrates_latest(self):
        first = self.development()
        original = policy.git
        concurrent = []

        def race(repo, *args, **kwargs):
            result = original(repo, *args, **kwargs)
            if args[:3] == ("push", "origin", "HEAD:refs/heads/sirs") and not concurrent:
                concurrent.append(self.development("second.txt"))
            return result

        with patch.object(policy, "git", side_effect=race):
            policy.sync(self.repo)
        self.assert_synced(first, *concurrent)

    def test_rejected_push_never_claims_success(self):
        self.development()
        hook = self.remote / "hooks/pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        with self.assertRaisesRegex(policy.Refused, "Publication refusée"):
            policy.sync(self.repo)
        self.assertEqual(policy.sha(self.remote, "sirs"), self.initial)

    def test_reverse_ancestry_and_source_refused_common_allowed(self):
        special = self.specialized("extension.txt")
        common = self.development()
        policy.sync(self.repo)
        policy.guard(self.repo, self.initial, common, common, "origin/sirs", "development")
        with self.assertRaisesRegex(policy.Refused, "Ascendance spécifique"):
            policy.guard(self.repo, common, "origin/sirs", common, "origin/sirs", "other-name")
        with self.assertRaisesRegex(policy.Refused, "source est sirs"):
            policy.guard(self.repo, common, common, common, special, "sirs")

    def test_sirs_path_refused_without_sirs_ancestry(self):
        change = self.development("sirs/schema.sql")
        with self.assertRaisesRegex(policy.Refused, "Changements spécifiques"):
            policy.guard(self.repo, self.initial, change, self.initial, "origin/sirs")

    def test_update_clean_behind_fast_forward_then_noop(self):
        self.development()
        policy.sync(self.repo)
        policy.update(self.repo, self.work)
        policy.update(self.repo, self.work)
        self.assertEqual(policy.sha(self.work, "HEAD"), policy.sha(self.remote, "sirs"))

    def test_update_dirty_including_untracked_refused(self):
        before = policy.sha(self.work, "HEAD")
        for name in ("local-only.txt", "common.txt"):
            with self.subTest(name=name):
                target = self.work / name
                previous = target.read_bytes() if target.exists() else None
                target.write_text("local change\n", encoding="utf-8")
                with self.assertRaisesRegex(policy.Refused, "Modifications locales"):
                    policy.update(self.repo, self.work)
                self.assertEqual(target.read_text(), "local change\n")
                self.assertEqual(policy.sha(self.work, "HEAD"), before)
                if previous is None:
                    target.unlink()
                else:
                    target.write_bytes(previous)

    def test_update_ahead_and_divergent_refused(self):
        local = self.commit(self.work, "sirs/local.txt", "unpushed\n")
        with self.assertRaisesRegex(policy.Refused, "en avance"):
            policy.update(self.repo, self.work)
        self.development()
        policy.sync(self.repo)
        with self.assertRaisesRegex(policy.Refused, "divergent"):
            policy.update(self.repo, self.work)
        self.assertEqual(policy.sha(self.work, "HEAD"), local)
        self.assertEqual((self.work / "sirs/local.txt").read_text(), "unpushed\n")

    def test_update_wrong_worktree_refused(self):
        with self.assertRaisesRegex(policy.Refused, "worktree lié"):
            policy.update(self.repo, self.repo)
        policy.git(self.work, "switch", "-c", "temporary")
        with self.assertRaisesRegex(policy.Refused, "branche locale sirs"):
            policy.update(self.repo, self.work)

    def test_update_reports_pending_github_sync(self):
        self.development()
        with self.assertRaisesRegex(policy.Refused, "synchronisation GitHub"):
            policy.update(self.repo, self.work)

    def test_validation_rejects_sirs_instruction_drift(self):
        special = self.specialized("AGENTS.md", "different instructions\n")
        self.development()
        with self.assertRaisesRegex(policy.Refused, "AGENTS.md diffère"):
            policy.sync(self.repo)
        self.assertEqual(policy.sha(self.remote, "sirs"), special)

    def test_validation_rejects_sirs_data_deletion(self):
        for directory in ("demo", "cabbalr", "plugin"):
            policy.git(self.work, "rm", "-r", directory)
        policy.git(self.work, "commit", "-m", "Forbidden SIRS deletions")
        policy.git(self.work, "push", "origin", "sirs")
        before = policy.sha(self.remote, "sirs")
        self.development()
        with self.assertRaisesRegex(policy.Refused, "Suppressions de fichiers"):
            policy.sync(self.repo)
        self.assertEqual(policy.sha(self.remote, "sirs"), before)
        # Restore only this test's temporary remote for the shared preservation assertion.
        for directory, file in (("demo", "data.txt"), ("cabbalr", "data.txt"), ("plugin", "code.py")):
            self.commit(self.work, f"{directory}/{file}", "initial\n")
        policy.git(self.work, "push", "origin", "sirs")


if __name__ == "__main__":
    unittest.main(verbosity=2)
