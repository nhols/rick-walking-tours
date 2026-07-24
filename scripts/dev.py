import os
import signal
import subprocess
from io import StringIO
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    subprocess.run(
        ["npx", "supabase", "start"],
        cwd=PROJECT_ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
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
    print("Local Supabase is ready at http://127.0.0.1:54321", flush=True)

    commands = [
        [
            "uv",
            "run",
            "uvicorn",
            "tour_worker.local:app",
            "--reload",
            "--host",
            "0.0.0.0",
            "--port",
            "8001",
        ]
    ]
    frontend_package = PROJECT_ROOT / "frontend" / "package.json"
    if frontend_package.is_file():
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


def _required(values: dict[str, str | None], key: str) -> str:
    value = values.get(key)
    if not value:
        raise RuntimeError(f"Supabase status did not provide {key}")
    return value


def _first_required(values: dict[str, str | None], *keys: str) -> str:
    for key in keys:
        value = values.get(key)
        if value:
            return value
    raise RuntimeError(f"Supabase status did not provide any of: {', '.join(keys)}")


if __name__ == "__main__":
    main()
