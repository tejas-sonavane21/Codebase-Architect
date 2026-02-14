"""
Gem Manager for Codebase Architect

Professional class-based gem management using gemini_webapi.
All operations use gem IDs directly - NO fetch_gems() calls.

Usage:
    from utils.gem_manager import GemManager
    
    # Get gem ID for a node
    gem_id = GemManager.get_id("surveyor")
    
    # Sync all gems with current prompts
    await GemManager.sync_all(client)
"""

import json
import asyncio
from pathlib import Path
from typing import Optional, Dict
from utils.console import console
from utils.paths import GEMS_CONFIG_PATH


class GemManager:
    """
    Professional gem management with local config persistence.
    
    All API operations use gem IDs directly (no fetch_gems).
    Config stored in artifacts/gems_config.json.
    """
    
    CONFIG_FILE = GEMS_CONFIG_PATH
    
    # =========================================================
    # GEM CONFIGURATIONS - Central definition for all gems
    # =========================================================
    
    @classmethod
    def get_gem_configs(cls) -> Dict[str, dict]:
        """
        Get gem configurations. Imports prompts lazily to avoid circular imports.
        """
        from utils.prompts import PROMPTS
        
        return {
            "surveyor": {
                "name": "codebase-surveyor",
                "prompt": PROMPTS["surveyor"],
                "description": "SURVEYOR-PRIME: Elite code reconnaissance specialist"
            },
            "summarizer_pass1": {
                "name": "codebase-summarizer-p1",
                "prompt": PROMPTS["summarizer_pass1"],
                "description": "KNOWLEDGE-FORGE: Semantic code extraction engine"
            },
            "summarizer_pass2": {
                "name": "codebase-summarizer-p2",
                "prompt": PROMPTS["summarizer_pass2"],
                "description": "ARCHITECT-VISION: Cross-file relationship analyst"
            },
            "architect": {
                "name": "codebase-architect",
                "prompt": PROMPTS["architect"],
                "description": "DIAGRAM-STRATEGIST: Strategic diagram planner"
            },
            "drafter": {
                "name": "codebase-drafter",
                "prompt": PROMPTS["drafter"],
                "description": "PLANTUML-ENGINE: Zero-tolerance PlantUML generator"
            },
            "plan_auditor": {
                "name": "codebase-plan-auditor",
                "prompt": PROMPTS["plan_auditor"],
                "description": "DIAGRAM-AUDITOR: Intelligent diagram plan auditor (Phase 1)"
            },
            "code_auditor": {
                "name": "codebase-code-auditor",
                "prompt": PROMPTS["code_auditor"],
                "description": "CODE-AUDITOR: PlantUML content comparison auditor (Phase 2)"
            },
            "supervisor": {
                "name": "codebase-supervisor",
                "prompt": PROMPTS["supervisor"],
                "description": "SENIOR-REVIEWER: Agentic self-correction supervisor"
            },
        }
    
    REQUIRED_GEMS = ["surveyor", "summarizer_pass1", "summarizer_pass2", "architect", "drafter", "plan_auditor", "code_auditor", "supervisor"]
    
    # =========================================================
    # CONFIG OPERATIONS (Local File)
    # =========================================================
    
    @classmethod
    def load_config(cls) -> Dict[str, str]:
        """Load gem IDs from local config file."""
        if not cls.CONFIG_FILE.exists():
            return {}
        
        try:
            with open(cls.CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {k: v for k, v in data.items() if not k.startswith("_")}
        except Exception as e:
            console.warning(f"Failed to load gems config: {e}", indent=1)
            return {}
    
    @classmethod
    def save_config(cls, gems: Dict[str, str]):
        """Save gem IDs to local config file."""
        cls.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        data = {"_comment": "Gemini Gems - managed by GemManager"}
        data.update(gems)
        
        try:
            with open(cls.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            console.warning(f"Failed to save gems config: {e}", indent=1)
    
    @classmethod
    def get_id(cls, key: str) -> Optional[str]:
        """Get gem ID from local config (no API call)."""
        return cls.load_config().get(key)
    
    @classmethod
    def has_gem(cls, key: str) -> bool:
        """Check if a gem exists in local config."""
        return key in cls.load_config()
    
    @classmethod
    def list_all(cls) -> Dict[str, str]:
        """Get all gems from local config."""
        return cls.load_config()
    
    # =========================================================
    # ASYNC API OPERATIONS (gemini_webapi)
    # =========================================================
    
    @classmethod
    async def create_async(cls, client, key: str, name: str, prompt: str, description: str = "") -> Optional[str]:
        """
        Create a new gem via API and save ID to config.
        
        Args:
            client: Initialized GeminiClient (with _client attribute)
            key: Config key (e.g., 'surveyor')
            name: Display name for the gem
            prompt: System prompt / instructions
            description: Optional description
            
        Returns:
            Gem ID if successful, None otherwise.
        """
        try:
            new_gem = await client._client.create_gem(
                name=name,
                prompt=prompt,
                description=description or f"Gem for {key}"
            )
            
            gem_id = new_gem.id if hasattr(new_gem, 'id') else str(new_gem)
            
            # Save to config
            gems = cls.load_config()
            gems[key] = gem_id
            cls.save_config(gems)
            
            return gem_id
            
        except Exception as e:
            console.error(f"Failed to create gem '{key}': {e}", indent=1)
            return None
    
    @classmethod
    async def update_async(cls, client, key: str, name: str, prompt: str, description: str = "") -> bool:
        """
        Update an existing gem via API (using gem ID, no fetch_gems).
        
        Args:
            client: Initialized GeminiClient (with _client attribute)
            key: Config key of gem to update
            name: New display name
            prompt: New system prompt
            description: New description
            
        Returns:
            True if successful.
        """
        gem_id = cls.get_id(key)
        
        if not gem_id:
            console.warning(f"Gem '{key}' not found in config - use create instead", indent=1)
            return False
        
        try:
            # Pass gem ID string directly (NO fetch_gems needed!)
            await client._client.update_gem(
                gem=gem_id,
                name=name,
                prompt=prompt,
                description=description or f"Gem for {key}"
            )
            return True
            
        except Exception as e:
            console.error(f"Failed to update gem '{key}': {e}", indent=1)
            return False
    
    @classmethod
    async def delete_async(cls, client, key: str) -> bool:
        """
        Delete a gem via API and remove from config.
        
        Args:
            client: Initialized GeminiClient (with _client attribute)
            key: Config key of gem to delete
            
        Returns:
            True if successful.
        """
        gem_id = cls.get_id(key)
        
        if not gem_id:
            console.warning(f"Gem '{key}' not found in config", indent=1)
            return False
        
        try:
            # Pass gem ID string directly (NO fetch_gems needed!)
            await client._client.delete_gem(gem_id)
            console.success(f"Deleted gem '{key}' from API", indent=1)
        except Exception as e:
            console.warning(f"API delete failed (may already be deleted): {e}", indent=1)
        
        # Remove from config regardless
        gems = cls.load_config()
        if key in gems:
            del gems[key]
            cls.save_config(gems)
        
        return True
    
    # =========================================================
    # SYNC WRAPPERS (for non-async contexts)
    # =========================================================
    
    @classmethod
    def create(cls, client, key: str, name: str, prompt: str, description: str = "") -> Optional[str]:
        """Sync wrapper for create_async."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, need to use create_task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        cls.create_async(client, key, name, prompt, description)
                    )
                    return future.result()
            return loop.run_until_complete(cls.create_async(client, key, name, prompt, description))
        except RuntimeError:
            return asyncio.run(cls.create_async(client, key, name, prompt, description))
    
    @classmethod
    def update(cls, client, key: str, name: str, prompt: str, description: str = "") -> bool:
        """Sync wrapper for update_async."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        cls.update_async(client, key, name, prompt, description)
                    )
                    return future.result()
            return loop.run_until_complete(cls.update_async(client, key, name, prompt, description))
        except RuntimeError:
            return asyncio.run(cls.update_async(client, key, name, prompt, description))
    
    @classmethod
    def delete(cls, client, key: str) -> bool:
        """Sync wrapper for delete_async."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        cls.delete_async(client, key)
                    )
                    return future.result()
            return loop.run_until_complete(cls.delete_async(client, key))
        except RuntimeError:
            return asyncio.run(cls.delete_async(client, key))
    
    # =========================================================
    # BATCH OPERATIONS (for CLI)
    # =========================================================
    
    @classmethod
    async def sync_all(cls, client) -> Dict[str, str]:
        """
        Sync all gems with current prompts (update existing, create missing).
        
        Returns:
            Dict of gem keys to IDs.
        """
        configs = cls.get_gem_configs()
        current = cls.load_config()
        result = {}
        
        for key, config in configs.items():
            gem_id = current.get(key)
            console.status(f"Syncing '{key}'...")
            
            try:
                if gem_id:
                    # Update existing
                    await client._client.update_gem(
                        gem=gem_id,
                        name=config["name"],
                        prompt=config["prompt"],
                        description=config["description"]
                    )
                    console.status(f"Updated (ID: {gem_id})", done=True)
                    result[key] = gem_id
                else:
                    # Create new
                    new_gem = await client._client.create_gem(
                        name=config["name"],
                        prompt=config["prompt"],
                        description=config["description"]
                    )
                    new_id = new_gem.id if hasattr(new_gem, 'id') else str(new_gem)
                    console.status(f"Created (ID: {new_id})", done=True)
                    result[key] = new_id
                    
            except Exception as e:
                console.error(f"Failed: {e}", indent=1)
                if gem_id:
                    result[key] = gem_id  # Keep old ID
        
        cls.save_config(result)
        return result
    
    @classmethod
    async def create_all(cls, client) -> Dict[str, str]:
        """Create all gems fresh (for first-time setup)."""
        configs = cls.get_gem_configs()
        result = {}
        
        for key, config in configs.items():
            console.status(f"Creating '{key}'...")
            
            try:
                new_gem = await client._client.create_gem(
                    name=config["name"],
                    prompt=config["prompt"],
                    description=config["description"]
                )
                new_id = new_gem.id if hasattr(new_gem, 'id') else str(new_gem)
                console.status(f"Created (ID: {new_id})", done=True)
                result[key] = new_id
            except Exception as e:
                console.error(f"Failed: {e}", indent=1)
        
        cls.save_config(result)
        return result
    
    @classmethod
    async def delete_all(cls, client) -> int:
        """Delete all gems from config."""
        current = cls.load_config()
        deleted = 0
        
        for key, gem_id in list(current.items()):
            console.status(f"Deleting '{key}'...")
            
            try:
                await client._client.delete_gem(gem_id)
                console.status("Deleted", done=True)
                deleted += 1
            except Exception as e:
                console.error(f"Failed: {e}", indent=1)
        
        cls.save_config({})
        return deleted
    
    @classmethod
    def print_status(cls):
        """Print current gem status."""
        gems = cls.load_config()
        
        console.section("Gem Status")
        
        if not gems:
            console.warning("No gems configured.")
            console.info("Run: python main.py --gems-sync")
        else:
            rows = [[k, v] for k, v in gems.items()]
            console.table(["Gem Name", "Gem ID"], rows)
        
        console.debug(f"Config file: {cls.CONFIG_FILE}")


# =========================================================
# BACKWARD COMPATIBILITY - Module-level functions
# =========================================================

def get_gem_id(key: str) -> Optional[str]:
    """Get gem ID from config. Used by nodes."""
    return GemManager.get_id(key)


def get_gem_id_for_prompt(prompt_type: str) -> Optional[str]:
    """Get gem ID for a prompt type. Used by prompts.py."""
    return GemManager.get_id(prompt_type)


def update_gem(client, key: str, name: str, prompt: str, description: str = "") -> bool:
    """Update a gem. Used by drafter.py."""
    return GemManager.update(client, key, name, prompt, description)


def list_gems() -> Dict[str, str]:
    """List all gems."""
    return GemManager.list_all()


def has_gem(key: str) -> bool:
    """Check if gem exists."""
    return GemManager.has_gem(key)
