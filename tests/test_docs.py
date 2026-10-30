"""The two docs a player or an operator reads. docs/flow.md went stale once already (slice 1), so the
words in them are checked against the code rather than trusted."""
import pathlib
import re

import table

DOCS = [(path, pathlib.Path(path).read_text()) for path in ("README.md", "docs/flow.md")]

# Retired by this mission: the one-chat flow, and the corrections the spec puts Out of Scope.
RETIRED_VERBS = ("play", "reset")
# AD5, AD16 (S4.13) — the wind names are retired prose, not just retired code: a doc that still says
# `pick a wind` fails the suite rather than going stale quietly.
RETIRED_WORDS = ("Manual Edits", "Remove Last", "chatStatus", "util.py", "session(", "howtopay()",
                 "東", "南", "西", "北", "pick a wind", "WINDS")


def verbs_in(text):
    """Slash verbs, ignoring URLs and paths (`/` preceded by a word char or another `/` is not a verb)."""
    return set(re.findall(r"(?<![\w/])/([a-z]{3,})\b", text))


# S7.1 — a doc that advertises a verb the bot does not answer is worse than no doc: the reader tries it,
# nothing happens, and they conclude the bot is broken. Every verb named must be one commands_for knows.
def test_the_docs_name_only_verbs_the_bot_has():
    live = {verb.lstrip("/") for verb in table.COMMAND_HELP}
    for path, doc in DOCS:
        unknown = verbs_in(doc) - live
        assert not unknown, "%s advertises %s" % (path, sorted(unknown))


# S7.2 — and none of the retired ones survive anywhere in them, prose included.
def test_the_retired_flow_is_gone_from_the_docs():
    for path, doc in DOCS:
        stale = sorted(set(RETIRED_VERBS) & verbs_in(doc)) + [w for w in RETIRED_WORDS if w in doc]
        assert not stale, "%s still describes %s" % (path, stale)


# S7.4 — the other way docs go stale is silence: a verb ships and the README never mentions it. Every verb
# a player can use has to be in the README's command table.
def test_the_readme_names_every_verb_the_bot_has():
    readme = dict(DOCS)["README.md"]
    silent = {verb.lstrip("/") for verb in table.COMMAND_HELP} - verbs_in(readme)
    assert not silent, "README never mentions %s" % sorted(silent)


# S8.2 (05/S8.1) — the two things a player taps that are not verbs, so the verb net above cannot see them go.
# The labels are the constants the keyboard rows are built from (`table.UNDO_LAST`, `table.CHANGE_NAMES`):
# a doc that never names one describes a bot with the hole it filled still in it.
def test_both_docs_describe_the_buttons_that_are_not_verbs():
    for path, doc in DOCS:
        for label in (table.UNDO_LAST, table.CHANGE_NAMES):
            assert label in doc, "%s never mentions %s" % (path, label)


# S7.3 — the operator knobs are read from the environment by exactly one file; a table of variables that
# does not match it teaches an operator to set something that does nothing.
def test_the_env_table_covers_the_variables_the_bot_actually_reads():
    source = pathlib.Path("mjbot.py").read_text() + pathlib.Path("config.py").read_text()
    read = set(re.findall(r"environ\.get\(['\"](MJ_[A-Z_]+)", source)) | set(
        re.findall(r"environ\[['\"](MJ_[A-Z_]+)['\"]", source))
    readme = dict(DOCS)["README.md"]
    documented = set(re.findall(r"\|\s*`(MJ_[A-Z_]+)`", readme))
    missing, extra = read - documented, documented - read
    assert not missing, "README's table is missing %s" % sorted(missing)
    assert not extra, "README documents %s, which nothing reads" % sorted(extra)


# NFR1 — the rules core imports no telebot, which is what lets every payout assertion in the suite run
# with no token and no socket. docs/flow.md § 10 promises the split, and the CI file rules a linter out
# on purpose ("No lint, no coverage"), so the promise needed a check that is not a tool: this file
# already reads source text for the env table, and the two files NFR1 names are checked the same way.
def test_the_rules_core_imports_no_telebot():
    for path in ("table.py", "score.py"):
        source = pathlib.Path(path).read_text()
        assert not re.search(r"^\s*(?:import|from)\s+telebot\b", source, re.M), \
            "%s imports telebot — NFR1 says the rules core does not" % path
