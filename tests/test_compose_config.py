"""Validate published ports without starting containers or touching volumes."""

import json
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ComposePortsTest(unittest.TestCase):
    def config(self, **overrides):
        env = os.environ.copy()
        for key in ("MUSIC_GATHERINGS_FRONTEND_PORT", "MUSIC_GATHERINGS_BACKEND_PORT"):
            env.pop(key, None)
        env.update(overrides)
        result = subprocess.run(
            ["docker", "compose", "--env-file", "/dev/null", "config", "--format", "json"],
            cwd=ROOT, env=env, check=True, capture_output=True, text=True,
        )
        return json.loads(result.stdout)["services"]

    def check_ports(self, services, frontend, backend):
        for service, published, target in (
            ("frontend", frontend, 8080), ("backend", backend, 8000),
        ):
            ports = services[service]["ports"]
            self.assertEqual(len(ports), 1)
            self.assertEqual(str(ports[0]["published"]), str(published))
            self.assertEqual(ports[0]["target"], target)
        for name, service in services.items():
            if name not in ("frontend", "backend"):
                self.assertFalse(service.get("ports"), name)

    def test_defaults(self):
        self.check_ports(self.config(), 3000, 8000)

    def test_custom_host_ports(self):
        self.check_ports(self.config(
            MUSIC_GATHERINGS_FRONTEND_PORT="3100",
            MUSIC_GATHERINGS_BACKEND_PORT="8100",
        ), 3100, 8100)

    def test_empty_overrides_keep_defaults(self):
        self.check_ports(self.config(
            MUSIC_GATHERINGS_FRONTEND_PORT="",
            MUSIC_GATHERINGS_BACKEND_PORT="",
        ), 3000, 8000)
