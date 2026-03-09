#!/usr/bin/env python3
"""
aquilon_comms.py

Queries preset (Master Memory) names and indexes from an Analog Way LivePremier
unit via its HTTP REST API.

The LivePremier exposes a REST API at http://<host>/api/tpp/v1/
Memories (presets) are listed at GET /api/tpp/v1/memories
"""

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AquilonPreset:
    """A single Master Memory (preset) from the LivePremier."""
    memory_id: int   # Integer ID used in Companion action options (memoryId)
    name: str        # Human-readable name shown on the button

    def __repr__(self):
        return f"AquilonPreset(memory_id={self.memory_id}, name={self.name!r})"


class AquilonComms:
    """
    HTTP REST client for the Analog Way LivePremier (Aquilon).

    The LivePremier exposes its control API at:
        http://<host>/api/tpp/v1/

    This class is intentionally thin — it only queries memories (presets).
    All write operations (loading memories) are handled by Companion directly
    via the analogway-livepremier module.
    """

    DEFAULT_PORT = 80
    TIMEOUT_SECONDS = 5

    def __init__(self, host: str, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}/api/tpp/v1"

    def _get(self, path: str) -> dict | list:
        """Make a GET request to the LivePremier API and return parsed JSON."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        logger.debug(f"GET {url}")
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.TIMEOUT_SECONDS) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.URLError as e:
            raise ConnectionError(
                f"Cannot reach LivePremier at {url}: {e.reason}"
            ) from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in response from {url}: {e}") from e

    def get_presets(self) -> list[AquilonPreset]:
        """
        Query all Master Memories from the LivePremier and return them as a
        sorted list of AquilonPreset objects.

        Returns:
            List of AquilonPreset sorted by memory_id.

        Raises:
            ConnectionError: If the unit is unreachable.
            ValueError: If the response cannot be parsed.

        TODO: Verify the exact API endpoint path and response structure
              against the LivePremier REST API documentation.
              Current assumption: GET /api/tpp/v1/memories returns a list of
              objects with at minimum `id` (int) and `name` (str) fields.
        """
        data = self._get("memories")

        presets = self._parse_memories(data)
        presets.sort(key=lambda p: p.memory_id)
        logger.info(f"Retrieved {len(presets)} presets from {self.host}")
        return presets

    def _parse_memories(self, data: dict | list) -> list[AquilonPreset]:
        """
        Parse the /memories API response into AquilonPreset objects.

        TODO: Update field names once the actual response schema is confirmed.
        Assumed response shapes:
          List: [ {"id": 1, "name": "Wide"}, ... ]
          Dict: { "memories": [ {"id": 1, "name": "Wide"}, ... ] }
        """
        # Handle both a bare list and a dict with a "memories" key
        if isinstance(data, dict):
            items = data.get("memories", data.get("items", data.get("data", [])))
        elif isinstance(data, list):
            items = data
        else:
            raise ValueError(f"Unexpected response format from /memories: {type(data)}")

        presets = []
        for item in items:
            # TODO: confirm the field names — "id" / "memoryId" / "index"
            #        and "name" / "label" / "title"
            try:
                memory_id = int(item.get("id", item.get("memoryId", item.get("index"))))
                name = str(item.get("name", item.get("label", item.get("title", ""))))
                if not name:
                    logger.warning(f"Preset {memory_id} has no name, skipping")
                    continue
                presets.append(AquilonPreset(memory_id=memory_id, name=name))
            except (TypeError, ValueError) as e:
                logger.warning(f"Could not parse memory entry {item!r}: {e}")

        return presets
