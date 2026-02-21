import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest import TestCase

from scripts_py import ci_attestation_gate


@contextmanager
def _temp_path() -> Path:
    fd, name = tempfile.mkstemp()
    os.close(fd)
    Path(name).unlink(missing_ok=True)
    try:
        yield Path(name)
    finally:
        Path(name).unlink(missing_ok=True)


class TestCiAttestationGate(TestCase):
    def test_default_gate_denies_non_push_event(self) -> None:
        allowed, reason = ci_attestation_gate.should_consider_skipping(
            github_event_name="pull_request",
            github_ref="refs/heads/main",
            allow_events=("push",),
            allow_refs=("refs/heads/main",),
        )
        self.assertFalse(allowed)
        self.assertIn("event", reason)

    def test_default_gate_denies_non_main_ref(self) -> None:
        allowed, reason = ci_attestation_gate.should_consider_skipping(
            github_event_name="push",
            github_ref="refs/heads/feature/foo",
            allow_events=("push",),
            allow_refs=("refs/heads/main",),
        )
        self.assertFalse(allowed)
        self.assertIn("ref", reason)

    def test_default_gate_allows_push_main(self) -> None:
        allowed, reason = ci_attestation_gate.should_consider_skipping(
            github_event_name="push",
            github_ref="refs/heads/main",
            allow_events=("push",),
            allow_refs=("refs/heads/main",),
        )
        self.assertTrue(allowed)
        self.assertEqual(reason, "allowed")

    def test_write_github_output_appends(self) -> None:
        with self.subTest("creates file"):
            with _temp_path() as output_path:
                ci_attestation_gate.write_github_output(
                    output_path=output_path,
                    key="skip",
                    value="true",
                )
                self.assertEqual(output_path.read_text(encoding="utf-8"), "skip=true\n")

        with self.subTest("appends"):
            with _temp_path() as output_path:
                output_path.write_text("foo=bar\n", encoding="utf-8")
                ci_attestation_gate.write_github_output(
                    output_path=output_path,
                    key="skip",
                    value="false",
                )
                self.assertEqual(
                    output_path.read_text(encoding="utf-8"),
                    "foo=bar\nskip=false\n",
                )

    def test_compute_skip_false_when_fetch_fails(self) -> None:
        class RunnerFailFetch:
            def run_check(self, argv):
                raise ci_attestation_gate.subprocess.CalledProcessError(1, list(argv))

            def run_capture(self, argv):
                raise AssertionError("run_capture should not be called")

        skip = ci_attestation_gate.compute_skip(
            runner=RunnerFailFetch(),
            task="check:all",
            notes_ref="refs/notes/nixos-setup-ci",
            remote="origin",
            sha="deadbeef",
            github_event_name="push",
            github_ref="refs/heads/main",
        )
        self.assertFalse(skip)

    def test_compute_skip_uses_has_attestation_result(self) -> None:
        calls: list[list[str]] = []

        class RunnerOk:
            def run_check(self, argv):
                calls.append(list(argv))

            def run_capture(self, argv):
                raise AssertionError("run_capture should not be called")

        def has_attestation_fn(*, opts, runner) -> bool:
            self.assertEqual(opts.commit, "deadbeef")
            self.assertEqual(opts.task, "check:all")
            self.assertEqual(opts.notes_ref, "refs/notes/nixos-setup-ci")
            return True

        skip = ci_attestation_gate.compute_skip(
            runner=RunnerOk(),
            task="check:all",
            notes_ref="refs/notes/nixos-setup-ci",
            remote="origin",
            sha="deadbeef",
            github_event_name="push",
            github_ref="refs/heads/main",
            has_attestation_fn=has_attestation_fn,
        )
        self.assertTrue(skip)
        self.assertTrue(any(cmd[:2] == ["git", "fetch"] for cmd in calls))

    def test_main_writes_output_when_configured(self) -> None:
        env = {
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": "deadbeef",
        }
        with _temp_path() as output_path:
            env["GITHUB_OUTPUT"] = str(output_path)

            class RunnerUnused:
                def run_check(self, argv):
                    raise AssertionError("runner should not be used")

                def run_capture(self, argv):
                    raise AssertionError("runner should not be used")

            def compute_skip_fn(**_kwargs: object) -> bool:
                return True

            exit_code = ci_attestation_gate.main(
                argv=["--task", "check:all", "--output-key", "skip"],
                env=env,
                runner=RunnerUnused(),
                compute_skip_fn=compute_skip_fn,
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "skip=true\n")

    def test_main_prints_output_when_github_output_missing(self) -> None:
        env = {
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": "deadbeef",
        }

        class RunnerUnused:
            def run_check(self, argv):
                raise AssertionError("runner should not be used")

            def run_capture(self, argv):
                raise AssertionError("runner should not be used")

        def compute_skip_fn(**_kwargs: object) -> bool:
            return False

        printed: list[str] = []

        def printer(msg: str) -> None:
            printed.append(msg)

        exit_code = ci_attestation_gate.main(
            argv=["--task", "check:all", "--output-key", "skip"],
            env=env,
            runner=RunnerUnused(),
            compute_skip_fn=compute_skip_fn,
            print_fn=printer,
        )
        self.assertEqual(exit_code, 0)
        self.assertIn("false", "\n".join(printed))

    def test_main_denies_when_not_allowed_event_ref(self) -> None:
        env = {
            "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": "deadbeef",
        }

        class RunnerMustNotBeUsed:
            def run_check(self, argv):
                raise AssertionError("runner should not be used")

            def run_capture(self, argv):
                raise AssertionError("runner should not be used")

        exit_code = ci_attestation_gate.main(
            argv=["--task", "check:all", "--output-key", "skip"],
            env=env,
            runner=RunnerMustNotBeUsed(),
        )
        self.assertEqual(exit_code, 0)
