"""Load inheritable, bundled discipline profiles and authored protocols."""

from __future__ import annotations

from importlib.resources import files
import json
from pathlib import Path
from typing import Any

from ..schemas import Profile


class ProfileError(ValueError):
    """Raised when a discipline profile is invalid or cannot be resolved."""


_RESOURCE_ROOT = files("reviscope.profiles")


def available_profiles() -> tuple[str, ...]:
    return tuple(sorted(item.name for item in _RESOURCE_ROOT.iterdir()
                        if item.is_dir() and item.joinpath("profile.json").is_file()))


def _read_json(profile_id: str) -> dict[str, Any]:
    if "/" in profile_id or "\\" in profile_id or profile_id.startswith("."):
        raise ProfileError(f"Invalid profile id: {profile_id!r}")
    path = _RESOURCE_ROOT.joinpath(profile_id, "profile.json")
    if not path.is_file():
        raise ProfileError(f"Unknown profile {profile_id!r}; choose from {available_profiles()}")
    return json.loads(path.read_text(encoding="utf-8"))


def _merge(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    merged = dict(parent)
    for key, value in child.items():
        if key in {"terminology", "severity_guidance", "metadata"}:
            merged[key] = {**parent.get(key, {}), **value}
        elif key == "modules":
            merged[key] = list(dict.fromkeys([*parent.get("modules", []), *value]))
        else:
            merged[key] = value
    return merged


def _resolve(profile_id: str, trail: tuple[str, ...] = ()) -> dict[str, Any]:
    if profile_id in trail:
        raise ProfileError(f"Profile inheritance cycle: {' -> '.join((*trail, profile_id))}")
    raw = _read_json(profile_id)
    return _merge(_resolve(raw["extends"], (*trail, profile_id)), raw) if raw.get("extends") else raw


def _protocol(profile_ids: list[str], module_id: str, kind: str) -> str:
    parts = []
    for profile_id in profile_ids:
        path = _RESOURCE_ROOT.joinpath(profile_id, f"{module_id}.{kind}.md")
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8").strip())
    if not parts:
        raise ProfileError(f"Missing {kind} protocol for module {module_id!r}")
    return "\n\n".join(parts)


def load_profile(profile_id: str) -> Profile:
    resolved = _resolve(profile_id)
    ancestry: list[str] = []
    cursor: str | None = profile_id
    while cursor:
        ancestry.append(cursor)
        cursor = _read_json(cursor).get("extends")
    ancestry.reverse()
    missing = {"id", "name", "status", "modules"} - resolved.keys()
    if missing:
        raise ProfileError(f"Profile {profile_id!r} lacks: {', '.join(sorted(missing))}")
    terminology = resolved.get("terminology", {})
    terminology_prompt = ("Discipline terminology for this review: " +
                          "; ".join(f"{key} = {value}" for key, value in terminology.items()) + ".")
    module_prompts = {module_id: f"{terminology_prompt}\n\n{_protocol(ancestry, module_id, 'generation')}"
                      for module_id in resolved["modules"]}
    verification_prompt = "\n\n".join(_protocol(ancestry, module_id, "verification")
                                        for module_id in resolved["modules"])
    editorial_parts = [_RESOURCE_ROOT.joinpath(item, "editorial.md") for item in ancestry]
    editorial_text = "\n\n".join(path.read_text(encoding="utf-8").strip()
                                    for path in editorial_parts if path.is_file())
    metadata = {**resolved.get("metadata", {}), "status": resolved["status"],
                "terminology": terminology,
                "severity_guidance": resolved.get("severity_guidance", {}), "ancestry": ancestry}
    return Profile(id=resolved["id"], title=resolved["name"], modules=list(resolved["modules"]),
                   module_prompts=module_prompts, verification_prompt=verification_prompt,
                   editorial_prompt=editorial_text, metadata=metadata)


def load_profile_path(path: str | Path, trail: tuple[str, ...] = ()) -> Profile:
    """Load a user-authored profile directory, inheriting bundled or sibling profiles.

    External profiles are JSON and Markdown only: loading them never imports or
    executes user code. ``extends`` first resolves a sibling directory, then a
    bundled profile id.
    """
    directory = Path(path).expanduser().resolve()
    if directory.is_file():
        if directory.name != "profile.json":
            raise ProfileError("An external profile file must be named profile.json")
        directory = directory.parent
    manifest = directory / "profile.json"
    if not manifest.is_file():
        raise ProfileError(f"External profile has no profile.json: {directory}")
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    profile_id = str(raw.get("id", ""))
    if not profile_id or profile_id in trail:
        raise ProfileError(f"Invalid or cyclic external profile inheritance: {(*trail, profile_id)}")
    parent_id = raw.get("extends")
    if parent_id:
        sibling = directory.parent / str(parent_id)
        parent = load_profile_path(sibling, (*trail, profile_id)) if (sibling / "profile.json").is_file() else load_profile(str(parent_id))
    else:
        parent = Profile(id="", title="", modules=[], metadata={})
    own_modules = raw.get("modules", [])
    if not isinstance(own_modules, list) or any(not isinstance(item, str) for item in own_modules):
        raise ProfileError("External profile modules must be a list of string ids")
    modules = list(dict.fromkeys([*parent.modules, *own_modules]))
    terminology = {**parent.metadata.get("terminology", {}), **raw.get("terminology", {})}
    terminology_prompt = ("Discipline terminology for this review: " +
                          "; ".join(f"{key} = {value}" for key, value in terminology.items()) + ".")
    prompts = dict(parent.module_prompts)
    verification_parts = [parent.verification_prompt] if parent.verification_prompt else []
    for module_id in modules:
        generation = directory / f"{module_id}.generation.md"
        verification = directory / f"{module_id}.verification.md"
        if generation.is_file():
            authored = generation.read_text(encoding="utf-8").strip()
            prompts[module_id] = "\n\n".join(filter(None, [prompts.get(module_id), authored]))
        if module_id not in prompts:
            raise ProfileError(f"Missing generation protocol for external module {module_id!r}")
        if verification.is_file():
            verification_parts.append(verification.read_text(encoding="utf-8").strip())
    prompts = {key: f"{terminology_prompt}\n\n{value}" for key, value in prompts.items()}
    editorial = directory / "editorial.md"
    editorial_text = "\n\n".join(filter(None, [parent.editorial_prompt,
        editorial.read_text(encoding="utf-8").strip() if editorial.is_file() else ""]))
    metadata = {**parent.metadata, **raw.get("metadata", {}), "status": raw.get("status", "custom_unvalidated"),
                "terminology": terminology, "severity_guidance": {
                    **parent.metadata.get("severity_guidance", {}), **raw.get("severity_guidance", {})},
                "ancestry": [*parent.metadata.get("ancestry", []), profile_id], "source": str(directory)}
    return Profile(id=profile_id, title=str(raw.get("name", profile_id)), modules=modules,
                   module_prompts=prompts, verification_prompt="\n\n".join(verification_parts),
                   editorial_prompt=editorial_text, metadata=metadata)
