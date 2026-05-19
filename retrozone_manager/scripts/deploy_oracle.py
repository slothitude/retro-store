"""
RetroMonkey Oracle Cloud Deploy Script
=======================================
Automated deployment of the RetroMonkey Flask store to Oracle Cloud Free Tier.
Uses paramiko SSH to configure a fresh Ubuntu instance.

Usage:
    python deploy_oracle.py <oracle-ip> [--env-file .env] [--db retro_store.db]

Prerequisites:
    - Oracle Cloud instance running Ubuntu 22.04+
    - SSH key access as ubuntu user
    - Domain DNS pointed to oracle-ip (retromonkey.com.au + www.retromonkey.com.au)
    - pip install paramiko
"""

import argparse
import os
import sys
import time

try:
    import paramiko
except ImportError:
    print("ERROR: paramiko required. pip install paramiko")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REMOTE_DIR = "/opt/retro-store"
DOMAIN = "retromonkey.com.au"

# Caddyfile: serve HTTP on IP + HTTPS on domain (for pre-DNS and post-DNS)
CADDYFILE = f""":80 {{
    reverse_proxy localhost:5000
    encode gzip
    header {{
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
    }}
}}

{DOMAIN}, www.{DOMAIN} {{
    reverse_proxy localhost:5000
    encode gzip
    header {{
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
    }}
}}
"""

SYSTEMD_SERVICE = """[Unit]
Description=RetroMonkey Web Store
After=network.target

[Service]
User=ubuntu
WorkingDirectory={remote}
ExecStart={remote}/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:5000 wsgi:app
Restart=always
Environment=PYTHONPATH={remote}

[Install]
WantedBy=multi-user.target
""".format(remote=REMOTE_DIR)


def ssh_connect(host: str, username: str = "ubuntu", key_path: str | None = None) -> paramiko.SSHClient:
    """Connect to Oracle instance via SSH."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connect_kwargs = {"hostname": host, "username": username}
    if key_path:
        connect_kwargs["key_filename"] = os.path.expanduser(key_path)
    else:
        # Try Oracle-specific key, then default SSH keys
        oracle_key = os.path.expanduser("~/.oci/retromonkey_ssh_key")
        default_key = os.path.expanduser("~/.ssh/id_rsa")
        if os.path.exists(oracle_key):
            connect_kwargs["key_filename"] = oracle_key
        elif os.path.exists(default_key):
            connect_kwargs["key_filename"] = default_key
    print(f"Connecting to {username}@{host}...")
    client.connect(**connect_kwargs)
    print("Connected.")
    return client


def run(client: paramiko.SSHClient, cmd: str, check: bool = True, sudo: bool = False) -> tuple[str, str, int]:
    """Run a command via SSH, return (stdout, stderr, exit_code)."""
    if sudo and not cmd.startswith("sudo"):
        cmd = f"sudo {cmd}"
    print(f"  $ {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=300)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if check and exit_code != 0:
        print(f"  ERROR (exit {exit_code}): {err}")
        raise RuntimeError(f"Command failed: {cmd}\n{err}")
    if out:
        safe = out[:200].encode("ascii", errors="replace").decode("ascii")
        print(f"  >> {safe}")
    return out, err, exit_code


def step(name: str):
    print(f"\n{'='*60}\n  {name}\n{'='*60}")


def setup_swap(client: paramiko.SSHClient):
    """Create 2GB swap file with swappiness=10."""
    step("Setting up 2GB swap file")
    out, _, _ = run(client, "swapon --show", check=False)
    if "/swapfile" in out:
        print("  Swap already exists, skipping.")
        return
    run(client, "fallocate -l 2G /swapfile", sudo=True)
    run(client, "chmod 600 /swapfile", sudo=True)
    run(client, "mkswap /swapfile", sudo=True)
    run(client, "swapon /swapfile", sudo=True)
    run(client, "bash -c 'echo /swapfile none swap sw 0 0 >> /etc/fstab'", sudo=True)
    run(client, "bash -c 'echo vm.swappiness=10 >> /etc/sysctl.conf'", sudo=True)
    run(client, "sysctl -p", sudo=True)
    print("  Swap configured.")


def open_firewall(client: paramiko.SSHClient):
    """Open OS-level iptables for HTTP/HTTPS (insert before REJECT rule)."""
    step("Opening OS firewall ports (80, 443)")
    # Oracle default iptables has REJECT at rule ~6. Insert before it.
    # Use line number detection for robustness.
    run(client, (
        "bash -c 'REJECT_LINE=$(iptables -L INPUT -n --line-numbers | grep REJECT | head -1 | awk \"{{print \\$1}}\") && "
        "iptables -I INPUT $REJECT_LINE -p tcp --dport 443 -j ACCEPT && "
        "iptables -I INPUT $REJECT_LINE -p tcp --dport 80 -j ACCEPT'"
    ), sudo=True)
    # Persist
    run(client, "netfilter-persistent save", check=False, sudo=True)
    run(client, "bash -c 'mkdir -p /etc/iptables && iptables-save > /etc/iptables/rules.v4'", check=False, sudo=True)
    print("  Firewall ports opened.")


def install_system_deps(client: paramiko.SSHClient):
    """Install Python venv, pip, and Caddy."""
    step("Installing system dependencies")
    run(client, "apt update", sudo=True)
    run(client, "apt install -y python3-venv python3-pip git", sudo=True)

    # Install Caddy
    step("Installing Caddy")
    run(client, "apt install -y debian-keyring debian-archive-keyring apt-transport-https curl", sudo=True)
    run(client, (
        "bash -c 'curl -1sLf \"https://dl.cloudsmith.io/public/caddy/stable/gpg.key\" "
        "| gpg --batch --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg'"
    ), sudo=True, check=False)
    run(client, (
        "bash -c 'curl -1sLf \"https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt\" "
        "| tee /etc/apt/sources.list.d/caddy-stable.list'"
    ), sudo=True)
    run(client, "apt update", sudo=True)
    run(client, "apt install -y caddy", sudo=True)
    print("  Caddy installed.")


def deploy_app(client: paramiko.SSHClient, env_path: str | None = None):
    """Clone repo, set up venv, install requirements."""
    step("Deploying application")

    # Check if repo already exists
    out, _, _ = run(client, f"test -d {REMOTE_DIR} && echo exists || echo missing", check=False)
    if "exists" in out:
        print(f"  {REMOTE_DIR} exists, pulling latest...")
        run(client, f"cd {REMOTE_DIR} && git pull || true")
    else:
        print(f"  Cloning repo to {REMOTE_DIR}...")
        local_remote, _, _ = run_local_git_remote()
        run(client, f"git clone {local_remote} {REMOTE_DIR}", sudo=True)
        run(client, f"chown -R ubuntu:ubuntu {REMOTE_DIR}", sudo=True)

    # Create wsgi.py entry point (Flask factory pattern)
    sftp = client.open_sftp()
    with sftp.file(f"{REMOTE_DIR}/wsgi.py", "w") as f:
        f.write("from app import create_app\napp = create_app()\n")
    sftp.close()

    # Create venv and install requirements
    run(client, f"python3 -m venv {REMOTE_DIR}/venv")
    run(client, f"{REMOTE_DIR}/venv/bin/pip install --upgrade pip")
    run(client, f"{REMOTE_DIR}/venv/bin/pip install -r {REMOTE_DIR}/requirements.txt")
    print("  Python venv + requirements installed.")


def run_local_git_remote() -> tuple[str, str, int]:
    """Get the git remote URL from the local repo."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, cwd=BASE_DIR, timeout=10
        )
        url = result.stdout.strip()
        return url, result.stderr.strip(), result.returncode
    except Exception:
        return "", "not a git repo", 1


def push_env(client: paramiko.SSHClient, env_path: str | None = None):
    """Copy .env file to remote."""
    step("Pushing .env file")
    if env_path and os.path.exists(env_path):
        sftp = client.open_sftp()
        sftp.put(env_path, f"{REMOTE_DIR}/.env")
        sftp.close()
        print(f"  Pushed {env_path} -> {REMOTE_DIR}/.env")
    else:
        print("  No .env provided. Creating minimal template...")
        sftp = client.open_sftp()
        with sftp.file(f"{REMOTE_DIR}/.env", "w") as f:
            f.write("# RetroMonkey Production Environment\n")
            f.write("FLASK_ENV=production\n")
            f.write("SESSION_COOKIE_SECURE=true\n")
            f.write("SITE_URL=https://retromonkey.com.au\n")
            f.write("# Add your keys: STRIPE_SECRET_KEY, STRIPE_PUBLIC_KEY, etc.\n")
        sftp.close()
        print(f"  Created template at {REMOTE_DIR}/.env -- EDIT BEFORE GOING LIVE")


def push_db(client: paramiko.SSHClient, db_path: str | None = None):
    """Copy local SQLite DB to remote."""
    step("Pushing database")
    local_db = db_path or os.path.join(BASE_DIR, "retro_store.db")
    if not os.path.exists(local_db):
        print(f"  No DB at {local_db}, skipping.")
        return
    sftp = client.open_sftp()
    sftp.put(local_db, f"{REMOTE_DIR}/retro_store.db")
    sftp.close()
    print(f"  Pushed {local_db} -> {REMOTE_DIR}/retro_store.db")


def write_caddyfile(client: paramiko.SSHClient):
    """Write Caddyfile to /etc/caddy/Caddyfile."""
    step("Writing Caddyfile")
    sftp = client.open_sftp()
    with sftp.file("/tmp/Caddyfile", "w") as f:
        f.write(CADDYFILE)
    sftp.close()
    run(client, "cp /tmp/Caddyfile /etc/caddy/Caddyfile", sudo=True)
    run(client, "chown root:root /etc/caddy/Caddyfile", sudo=True)
    print("  Caddyfile written.")


def write_systemd(client: paramiko.SSHClient):
    """Write and enable systemd service."""
    step("Setting up systemd service")
    sftp = client.open_sftp()
    with sftp.file("/tmp/retromonkey.service", "w") as f:
        f.write(SYSTEMD_SERVICE)
    sftp.close()
    run(client, "cp /tmp/retromonkey.service /etc/systemd/system/retromonkey.service", sudo=True)
    run(client, "systemctl daemon-reload", sudo=True)
    run(client, "systemctl enable retrozone", sudo=True)
    print("  systemd service configured.")


def start_services(client: paramiko.SSHClient):
    """Start gunicorn + caddy."""
    step("Starting services")
    run(client, "systemctl restart retrozone", sudo=True)
    time.sleep(3)
    run(client, "systemctl status retrozone --no-pager", check=False, sudo=True)
    run(client, "systemctl restart caddy", sudo=True)
    time.sleep(2)
    run(client, "systemctl status caddy --no-pager", check=False, sudo=True)
    print("  Services started.")


def verify(client: paramiko.SSHClient, host: str):
    """Quick health check."""
    step("Verification")
    out, _, code = run(client, "curl -sI http://localhost:5000 2>&1 | head -5", check=False)
    if "200" in out or "302" in out or "301" in out:
        print("  Flask responding on localhost:5000 [OK]")
    else:
        print(f"  WARNING: Flask may not be responding: {out}")

    out, _, _ = run(client, "curl -sI http://localhost 2>&1 | head -5", check=False)
    if "200" in out or "308" in out:
        print("  Caddy proxy responding [OK]")

    print(f"\n  HTTP (IP):    http://{host}")
    print(f"  HTTPS (live): https://{DOMAIN}")
    print(f"  SSH:          ssh -i ~/.oci/retromonkey_ssh_key ubuntu@{host}")
    print("\n  REMINDER: Once DNS propagates, restart Caddy for TLS certs:")
    print("            sudo systemctl restart caddy")
    print("  REMINDER: Update Stripe webhook to https://retromonkey.com.au/webhook")


def main():
    parser = argparse.ArgumentParser(description="Deploy RetroMonkey to Oracle Cloud")
    parser.add_argument("host", help="Oracle Cloud public IP")
    parser.add_argument("--user", default="ubuntu", help="SSH user (default: ubuntu)")
    parser.add_argument("--key", default=None, help="SSH private key path")
    parser.add_argument("--env-file", default=None, help="Local .env file to push")
    parser.add_argument("--db", default=None, help="Local retro_store.db to push")
    parser.add_argument("--skip-swap", action="store_true", help="Skip swap setup")
    parser.add_argument("--skip-firewall", action="store_true", help="Skip firewall config")
    args = parser.parse_args()

    print(f"RetroMonkey Oracle Deploy")
    print(f"  Target: {args.user}@{args.host}")
    print(f"  App dir: {REMOTE_DIR}")

    client = ssh_connect(args.host, args.user, args.key)

    try:
        if not args.skip_swap:
            setup_swap(client)
        if not args.skip_firewall:
            open_firewall(client)
        install_system_deps(client)
        deploy_app(client, args.env_file)
        push_env(client, args.env_file)
        push_db(client, args.db)
        write_caddyfile(client)
        write_systemd(client)
        start_services(client)
        verify(client, args.host)
    finally:
        client.close()
        print("\nDone. SSH connection closed.")


if __name__ == "__main__":
    main()
