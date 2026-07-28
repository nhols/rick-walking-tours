import json
import os
import signal
import shutil
import subprocess
from collections.abc import Mapping
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from dotenv import dotenv_values, load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKER_IMAGE = "rick-worker:local"


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    if shutil.which("sam") is None:
        raise RuntimeError("AWS SAM CLI is required; install it before running make up")

    worker_secrets = {
        name: _required(os.environ, name)
        for name in (
            "GOOGLE_API_KEY",
            "GOOGLE_MAPS_API_KEY",
            "LOGFIRE_TOKEN",
            "MAPBOX_ACCESS_TOKEN",
        )
    }
    subprocess.run(
        [
            "docker",
            "build",
            "--platform",
            "linux/arm64",
            "--file",
            "infra/aws/Dockerfile",
            "--tag",
            WORKER_IMAGE,
            ".",
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )
    subprocess.run(
        ["npx", "supabase", "start"],
        cwd=PROJECT_ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        ["npx", "supabase", "migration", "up", "--local"],
        cwd=PROJECT_ROOT,
        check=True,
    )
    status_output = subprocess.check_output(
        ["npx", "supabase", "status", "-o", "env"],
        cwd=PROJECT_ROOT,
        text=True,
        stderr=subprocess.DEVNULL,
    )
    supabase_environment = dotenv_values(stream=StringIO(status_output))

    child_environment = os.environ.copy()
    child_environment["SUPABASE_URL"] = _required(
        supabase_environment,
        "API_URL",
    )
    child_environment["SUPABASE_SERVICE_ROLE_KEY"] = _required(
        supabase_environment,
        "SERVICE_ROLE_KEY",
    )
    child_environment["VITE_SUPABASE_URL"] = child_environment["SUPABASE_URL"]
    child_environment["VITE_SUPABASE_ANON_KEY"] = _first_required(
        supabase_environment,
        "PUBLISHABLE_KEY",
        "ANON_KEY",
    )
    child_environment["AWS_ACCESS_KEY_ID"] = "local"
    child_environment["AWS_SECRET_ACCESS_KEY"] = "local"
    child_environment["AWS_DEFAULT_REGION"] = "eu-west-2"
    child_environment.pop("AWS_SESSION_TOKEN", None)
    print("Local Supabase is ready at http://127.0.0.1:54321", flush=True)

    with TemporaryDirectory(prefix="rick-") as temporary_directory:
        lambda_environment = {
            "SUPABASE_URL": child_environment["SUPABASE_URL"].replace(
                "127.0.0.1", "host.docker.internal"
            ),
            "SUPABASE_SERVICE_ROLE_KEY": child_environment[
                "SUPABASE_SERVICE_ROLE_KEY"
            ],
            **worker_secrets,
        }
        environment_file = Path(temporary_directory) / "lambda-env.json"
        environment_file.write_text(
            json.dumps({"WorkerFunction": lambda_environment})
        )
        commands = [
            [
                "sam",
                "local",
                "start-lambda",
                "--template",
                "infra/aws/template.yaml",
                "--invoke-image",
                f"WorkerFunction={WORKER_IMAGE}",
                "--env-vars",
                str(environment_file),
                "--parameter-overrides",
                _local_parameters(),
                "--host",
                "0.0.0.0",
                "--add-host",
                "host.docker.internal:host-gateway",
                "--warm-containers",
                "LAZY",
            ]
        ]
        if (PROJECT_ROOT / "frontend" / "package.json").is_file():
            commands.append(["npm", "--prefix", "frontend", "run", "dev"])

        children = [
            subprocess.Popen(command, cwd=PROJECT_ROOT, env=child_environment)
            for command in commands
        ]
        try:
            exit_code = children[0].wait()
            raise SystemExit(exit_code)
        except KeyboardInterrupt:
            pass
        finally:
            for child in children:
                if child.poll() is None:
                    child.send_signal(signal.SIGINT)
            for child in children:
                try:
                    child.wait(timeout=5)
                except (subprocess.TimeoutExpired, KeyboardInterrupt):
                    child.terminate()


def _local_parameters() -> str:
    names = (
        "SupabaseUrl",
        "SupabaseServiceRoleKey",
        "GoogleApiKey",
        "GoogleMapsApiKey",
        "LogfireToken",
        "MapboxAccessToken",
    )
    values = [f"ParameterKey={name},ParameterValue=local" for name in names]
    values.append(f"ParameterKey=WorkerImageUri,ParameterValue={WORKER_IMAGE}")
    return " ".join(values)


def _required(values: Mapping[str, str | None], key: str) -> str:
    value = values.get(key)
    if not value:
        raise RuntimeError(f"{key} is required")
    return value


def _first_required(values: Mapping[str, str | None], *keys: str) -> str:
    for key in keys:
        value = values.get(key)
        if value:
            return value
    raise RuntimeError(f"Supabase status did not provide any of: {', '.join(keys)}")


if __name__ == "__main__":
    main()
