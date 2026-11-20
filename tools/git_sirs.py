#!/usr/bin/env python3
"""Git-only SIRS synchronization. No database or application dependencies."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


class Refused(RuntimeError):
    pass


def git(repo, *args, check=True):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], text=True, encoding="utf-8",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise Refused(f"git {' '.join(args)}\n{result.stdout}{result.stderr}")
    return result


def sha(repo, ref):
    return git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").stdout.strip()


def ancestor(repo, older, newer):
    result = git(repo, "merge-base", "--is-ancestor", older, newer, check=False)
    if result.returncode not in (0, 1):
        raise Refused(result.stderr)
    return result.returncode == 0


def fetch(repo):
    # Explicit refspecs also work in a single-branch checkout. No forced updates.
    git(repo, "fetch", "--no-tags", "origin",
        "refs/heads/development:refs/remotes/origin/development",
        "refs/heads/sirs:refs/remotes/origin/sirs")


def clean(repo):
    if git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout:
        raise Refused("Modifications locales ou fichiers non suivis : arrêt sans modification.")
    for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"):
        path = git(repo, "rev-parse", "--path-format=absolute", "--git-path", name).stdout.strip()
        if Path(path).exists():
            raise Refused(f"Opération Git en cours ({name}) : terminer cette opération d'abord.")


def validate(repo, development, previous_sirs, candidate="HEAD"):
    for parent in (development, previous_sirs):
        if not ancestor(repo, parent, candidate):
            raise Refused(f"La fusion ne conserve pas l'ascendance {parent}.")
    instructions = git(repo, "rev-parse", "--verify", f"{development}:AGENTS.md").stdout
    if git(repo, "rev-parse", "--verify", f"{candidate}:AGENTS.md").stdout != instructions:
        raise Refused("AGENTS.md diffère de development : résolution explicite nécessaire.")
    deleted = git(repo, "diff", "--name-only", "--diff-filter=D", development, candidate,
                  "--", "demo/", "cabbalr/", "plugin/").stdout
    if deleted:
        raise Refused(f"Suppressions de fichiers du socle par SIRS interdites :\n{deleted}")
    git(repo, "diff", "--check", previous_sirs, candidate)


def merge(repo, development):
    # Identity is scoped to this command, not persisted in the user's config.
    result = git(repo, "-c", "user.name=github-actions[bot]", "-c",
                 "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                 "-c", "commit.gpgsign=false", "merge", "--no-edit", development, check=False)
    if result.returncode:
        conflicts = git(repo, "diff", "--name-only", "--diff-filter=U").stdout.strip()
        if conflicts:
            raise Refused(
                f"Conflits :\n{conflicts}\norigin/sirs reste inchangée. Dans un worktree SIRS "
                "propre : git fetch origin ; git merge origin/development ; résoudre chaque "
                "fichier en préservant les changements SIRS, contrôler, committer puis pousser "
                "sirs. Relancer ensuite le workflow. Aucun choix automatique ours/theirs."
            )
        raise Refused(f"Fusion refusée :\n{result.stdout}{result.stderr}")


def pull_request(repo, development):
    repository = os.environ.get("GITHUB_REPOSITORY")
    if repository != "jln-codes/gemapi-app":
        raise Refused("Le mode PR est réservé au dépôt jln-codes/gemapi-app.")

    def gh(*args):
        result = subprocess.run(["gh", *args], cwd=repo, text=True, encoding="utf-8",
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode:
            raise Refused(f"gh : {result.stderr}")
        return result.stdout.strip()

    prs = json.loads(gh("pr", "list", "--repo", repository, "--base", "sirs", "--head",
                        "development", "--state", "open", "--json", "url"))
    if prs:
        url = prs[0]["url"]
    else:
        url = gh("pr", "create", "--repo", repository, "--base", "sirs", "--head", "development",
                 "--title", "Synchroniser development vers sirs",
                 "--body", "Fusion normale du socle vers SIRS. Les contrôles obligatoires et "
                 "les protections de sirs doivent être satisfaits avant intégration.")
    print(f"PR de synchronisation : {url}", flush=True)
    # Never --admin, squash or rebase: the original development commits must remain ancestors.
    gh("pr", "merge", url, "--merge", "--auto", "--match-head-commit", development)
    fetch(repo)
    if not ancestor(repo, "origin/development", "origin/sirs"):
        raise Refused(f"PR en attente des contrôles/approbations : {url}. "
                      "La synchronisation n'a pas encore atteint origin/sirs.")


def sync(repo, attempts=4, mode="direct"):
    clean(repo)
    # All merges occur in a disposable linked worktree, including conflict states.
    # The caller's checkout and local sirs branch are never switched or reset.
    audits = Path(repo) / "audits"
    audits.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="git-sirs-", dir=audits) as directory:
        work = Path(directory) / "merge"
        for attempt in range(1, attempts + 1):
            fetch(repo)
            development = sha(repo, "origin/development")
            sirs = sha(repo, "origin/sirs")
            if ancestor(repo, development, sirs):
                validate(repo, development, sirs, sirs)
                print("origin/sirs est déjà synchronisée ; aucune opération.", flush=True)
                return
            count = git(repo, "rev-list", "--count", f"{sirs}..{development}").stdout.strip()
            print(f"Tentative {attempt}/{attempts} : {count} commit(s) du socle à intégrer.", flush=True)
            git(repo, "worktree", "add", "--detach", str(work), sirs)
            try:
                merge(work, development)
                validate(work, development, sirs)
                if mode == "pull-request":
                    pull_request(repo, development)
                    return
                result = git(work, "push", "origin", "HEAD:refs/heads/sirs", check=False)
                if result.returncode:
                    fetch(repo)
                    if sha(repo, "origin/sirs") != sirs:
                        print("origin/sirs a évolué : nouvelle fusion depuis sa nouvelle pointe.", flush=True)
                        continue
                    raise Refused(
                        f"Publication refusée ; aucun contournement :\n{result.stderr}\n"
                        "Si sirs exige une PR, configurer SIRS_SYNC_MODE=pull-request, "
                        "les contrôles requis et l'auto-merge (voir README)."
                    )
            finally:
                # --force only removes OUR disposable worktree, never a branch or user's files.
                git(repo, "worktree", "remove", "--force", str(work))
            fetch(repo)
            if ancestor(repo, "origin/development", "origin/sirs"):
                print("Synchronisation publiée et vérifiée sur origin/sirs.", flush=True)
                return
            print("development a encore évolué : intégration de sa nouvelle pointe.", flush=True)
    raise Refused("Branches encore actives après les tentatives sûres ; relancer le workflow.")


def common_dir(repo):
    return Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()).resolve()


def update(repo, worktree):
    worktree = Path(worktree).expanduser().resolve()
    if not worktree.is_dir():
        raise Refused(f"Worktree absent : {worktree}")
    top = Path(git(worktree, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    gitdir = Path(git(worktree, "rev-parse", "--absolute-git-dir").stdout.strip()).resolve()
    if top != worktree or common_dir(worktree) != common_dir(repo) or gitdir == common_dir(worktree):
        raise Refused("Le répertoire n'est pas un worktree lié au même dépôt GEMAPI-App.")
    if git(worktree, "symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip() != "sirs":
        raise Refused("Le worktree doit être sur la branche locale sirs.")
    clean(worktree)
    fetch(worktree)
    local = sha(worktree, "HEAD")
    remote = sha(worktree, "origin/sirs")
    ahead, behind = map(int, git(worktree, "rev-list", "--left-right", "--count",
                                f"{local}...{remote}").stdout.split())
    if ahead:
        state = "divergent" if behind else "en avance"
        raise Refused(f"Worktree {state} : {ahead} commit(s) local(aux) non poussé(s), "
                      f"{behind} distant(s). Arrêt sans modification des fichiers.")
    if behind:
        print(f"Worktree en retard de {behind} commit(s) ; mise à jour fast-forward.", flush=True)
        git(worktree, "merge", "--ff-only", remote)
    else:
        print("Worktree déjà synchronisé avec origin/sirs.", flush=True)
    if sha(worktree, "HEAD") != remote:
        raise Refused("La pointe locale ne correspond pas à la référence récupérée.")
    if not ancestor(worktree, "origin/development", remote):
        raise Refused("Worktree à jour avec origin/sirs, mais la synchronisation GitHub "
                      "development → sirs reste en attente ou en échec.")
    print("Worktree synchronisé ; évolutions du socle présentes.", flush=True)


def guard(repo, base, head, common, sirs, source=""):
    if source == "sirs":
        raise Refused("Flux inverse interdit : la branche source est sirs.")
    paths = git(repo, "diff", "--name-only", base, head, "--", "sirs/").stdout
    if paths:
        raise Refused(f"Changements spécifiques SIRS vers le socle interdits :\n{paths}")
    # Exclude common commits already inherited by sirs. In a production PR these
    # may be newer than main; they are legitimate development → main changes.
    specific = git(repo, "rev-list", sirs, "--not", base, common).stdout.splitlines()
    for commit in specific:
        if ancestor(repo, commit, head):
            raise Refused(f"Ascendance spécifique SIRS vers le socle interdite : {commit}")
    print("Politique Git : aucun flux inverse SIRS détecté.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    synchronizer = commands.add_parser("sync")
    synchronizer.add_argument("--mode", choices=("direct", "pull-request"), default="direct")
    updater = commands.add_parser("update")
    updater.add_argument("--worktree", default=str(Path.home() / "Projects/gemapi-app-sirs"))
    policy = commands.add_parser("guard")
    for option in ("base", "head", "common", "sirs"):
        policy.add_argument(f"--{option}", required=True)
    policy.add_argument("--source", default="")
    checker = commands.add_parser("validate")
    checker.add_argument("--development", default="origin/development")
    checker.add_argument("--sirs", default="origin/sirs")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    try:
        if args.command == "sync":
            sync(repo, mode=args.mode)
        elif args.command == "update":
            update(repo, args.worktree)
        elif args.command == "guard":
            guard(repo, args.base, args.head, args.common, args.sirs, args.source)
        else:
            validate(repo, args.development, args.sirs)
    except Refused as error:
        print(f"ERREUR : {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
