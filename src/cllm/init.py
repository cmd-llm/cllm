"""
Initialize .cllm directories with templates.

Implements ADR-0015: Add Init Command for .cllm Directory Setup
Implements ADR-0023: Configurable Init with CLI Flags
"""

import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

try:
    # Python 3.9+
    from importlib.resources import files
except ImportError:
    # Fallback for Python 3.8
    from importlib_resources import files


class InitError(Exception):
    """Exception raised during initialization."""

    pass


def get_home_cllm_dir() -> Path:
    """Get the global .cllm directory path (~/.cllm)."""
    return Path.home() / ".cllm"


def get_local_cllm_dir() -> Path:
    """Get the local .cllm directory path (./.cllm)."""
    return Path.cwd() / ".cllm"


def get_template_dir() -> Path:
    """
    Get the path to the templates directory in the installed package.

    Returns:
        Path to examples/configs directory
    """
    try:
        # Try importlib.resources (Python 3.9+)
        package_files = files("cllm")
        # Go up to package root, then to examples/configs
        # Package structure: src/cllm/ (installed as cllm/)
        # Templates are at: examples/configs/
        # Since we're in the cllm package, we need to go to parent, then examples
        template_path = package_files.parent / "examples" / "configs"
        if not template_path.is_dir():
            # Fallback for development: try relative to source
            src_root = Path(__file__).parent.parent.parent
            template_path = src_root / "examples" / "configs"
        return Path(str(template_path))
    except Exception as e:
        # Fallback: try relative to source file
        src_root = Path(__file__).parent.parent.parent
        template_path = src_root / "examples" / "configs"
        if not template_path.is_dir():
            raise InitError(
                f"Could not locate template directory. Checked: {template_path}"
            ) from e
        return template_path


def discover_templates() -> Dict[str, Path]:
    """
    Discover available templates from the examples/configs directory.

    Returns:
        Dictionary mapping template names to file paths
        (e.g., {"code-review": Path("code-review.Cllmfile.yml")})
    """
    template_dir = get_template_dir()
    templates = {}

    for file_path in template_dir.glob("*.Cllmfile.yml"):
        # Extract template name from filename
        # e.g., "code-review.Cllmfile.yml" -> "code-review"
        template_name = file_path.stem.replace(".Cllmfile", "")
        templates[template_name] = file_path

    return templates


def get_default_template() -> Path:
    """Get the path to the default Cllmfile.yml template."""
    template_dir = get_template_dir()
    default_template = template_dir / "Cllmfile.yml"

    if not default_template.exists():
        raise InitError(
            f"Default template not found at {default_template}. "
            "Please reinstall the package."
        )

    return default_template


def list_available_templates() -> None:
    """Print a list of available templates."""
    templates = discover_templates()

    print("Available templates:")
    print()

    # Template descriptions (hardcoded for now, could be extracted from files later)
    descriptions = {
        "code-review": "GPT-4 configuration for code review with structured output",
        "summarize": "Optimized for summarization tasks",
        "creative": "Higher temperature for creative writing",
        "debug": "Configuration for debugging assistance",
        "extraction": "Data extraction with structured output",
        "task-parser": "Parse tasks from natural language",
        "context-demo": "Demonstrates dynamic context injection",
    }

    for name in sorted(templates.keys()):
        desc = descriptions.get(name, "No description available")
        print(f"  {name:<20} - {desc}")

    print()
    print("Usage: cllm init --template <name>")
    print("       cllm init (uses default template)")


def create_directory_structure(
    target_dir: Path, force: bool = False
) -> tuple[bool, List[str]]:
    """
    Create .cllm directory structure.

    Args:
        target_dir: The .cllm directory to create
        force: If True, proceed even if directory exists

    Returns:
        Tuple of (created_new, messages) where:
        - created_new: True if directory was newly created
        - messages: List of status messages

    Raises:
        InitError: If directory exists and force=False
    """
    messages = []

    if target_dir.exists():
        if not force:
            raise InitError(
                f"Directory {target_dir} already exists. Use --force to reinitialize."
            )
        messages.append(f"Directory {target_dir} already exists (reinitializing)")
        created_new = False
    else:
        target_dir.mkdir(parents=True, exist_ok=True)
        messages.append(f"✓ Created {target_dir}/")
        created_new = True

    # Create conversations subdirectory
    conversations_dir = target_dir / "conversations"
    if not conversations_dir.exists():
        conversations_dir.mkdir(parents=True, exist_ok=True)
        messages.append(f"✓ Created {target_dir}/conversations/")
    else:
        messages.append(f"  {target_dir}/conversations/ already exists")

    return created_new, messages


def copy_template(
    target_dir: Path,
    template_name: Optional[str] = None,
    force: bool = False,
    config_overrides: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Copy template file to target directory with optional configuration overrides.

    Implements ADR-0023: Configurable Init with CLI Flags

    When template_name is None, creates Cllmfile.yml (default config).
    When template_name is provided, creates {template_name}.Cllmfile.yml (named config).
    If config_overrides are provided, they are merged with the template content (overrides take precedence).

    Args:
        target_dir: The .cllm directory
        template_name: Name of template to use (None for default)
        force: If True, overwrite existing file
        config_overrides: Optional dict of configuration overrides to merge with template

    Returns:
        List of status messages

    Raises:
        InitError: If template not found or file exists and force=False
    """
    messages = []

    # Determine target filename based on template
    if template_name is None:
        # Default: Cllmfile.yml
        target_file = target_dir / "Cllmfile.yml"
    else:
        # Named template: {template_name}.Cllmfile.yml
        target_file = target_dir / f"{template_name}.Cllmfile.yml"

    # Check if file exists
    if target_file.exists() and not force:
        raise InitError(f"File {target_file} already exists. Use --force to overwrite.")

    # Get source template
    if template_name is None:
        # Use default template
        source_file = get_default_template()
        message_suffix = "with starter configuration"
    else:
        # Use named template
        templates = discover_templates()
        if template_name not in templates:
            available = ", ".join(sorted(templates.keys()))
            raise InitError(
                f"Template '{template_name}' not found. "
                f"Available templates: {available}\n"
                f"Run 'cllm init --list-templates' to see all templates."
            )

        source_file = templates[template_name]
        message_suffix = "as named configuration"

    # ADR-0023: Merge template with config overrides if provided
    if config_overrides:
        # Load template content
        with open(source_file, "r") as f:
            template_config = yaml.safe_load(f) or {}

        # Merge overrides (overrides take precedence)
        merged_config = {**template_config, **config_overrides}

        # Write merged config to target file
        with open(target_file, "w") as f:
            yaml.dump(
                merged_config,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

        # Build message showing what was overridden
        override_keys = list(config_overrides.keys())
        override_summary = ", ".join(override_keys)
        messages.append(
            f"✓ Created {target_file} {message_suffix} (overridden: {override_summary})"
        )
    else:
        # No overrides - just copy the file
        shutil.copy2(source_file, target_file)
        messages.append(f"✓ Created {target_file} {message_suffix}")

    return messages


def update_gitignore(cllm_dir: Path) -> List[str]:
    """
    Update or create .gitignore to exclude conversation history.

    Only applies to local .cllm directories (not global ~/.cllm).

    Args:
        cllm_dir: The .cllm directory

    Returns:
        List of status messages
    """
    messages = []

    # Only update .gitignore for local .cllm directories
    if cllm_dir.resolve() == get_home_cllm_dir().resolve():
        # Don't update .gitignore for global directory
        return messages

    # Find .gitignore in current directory
    gitignore_path = Path.cwd() / ".gitignore"

    # Entries to add
    entries = [
        ".cllm/conversations/",
        ".cllm/*.log",
    ]

    if gitignore_path.exists():
        # Read existing content
        existing_content = gitignore_path.read_text()
        lines = existing_content.splitlines()

        # Check which entries are missing
        missing_entries = []
        for entry in entries:
            if entry not in lines:
                missing_entries.append(entry)

        if missing_entries:
            # Append missing entries
            with gitignore_path.open("a") as f:
                f.write("\n# CLLM\n")
                for entry in missing_entries:
                    f.write(f"{entry}\n")
            messages.append("✓ Updated .gitignore to exclude conversation history")
        else:
            messages.append("  .gitignore already contains CLLM entries")
    else:
        # Create new .gitignore
        with gitignore_path.open("w") as f:
            f.write("# CLLM\n")
            for entry in entries:
                f.write(f"{entry}\n")
        messages.append("✓ Created .gitignore to exclude conversation history")

    return messages


def print_next_steps(cllm_dir: Path, template_name: Optional[str] = None) -> None:
    """
    Print helpful next steps after initialization.

    Args:
        cllm_dir: The .cllm directory that was created
        template_name: Name of template used (if any)
    """
    print()
    print("Next steps:")

    if template_name:
        # Named template was created
        config_file = f"{cllm_dir}/{template_name}.Cllmfile.yml"
        print(f"1. Review {config_file}")
        print('2. Set your API key: export OPENAI_API_KEY="sk-..."')

        # Template-specific usage guidance
        if template_name == "code-review":
            print(f"3. Try it out: git diff | cllm --config {template_name}")
        elif template_name == "summarize":
            print(f"3. Try it out: cat document.txt | cllm --config {template_name}")
        elif template_name == "creative":
            print(
                f'3. Try it out: echo "Write a story about..." | cllm --config {template_name}'
            )
        elif template_name == "debug":
            print(f"3. Try it out: cat error.log | cllm --config {template_name}")
        else:
            print(f'3. Try it out: echo "Hello" | cllm --config {template_name}')
    else:
        # Default Cllmfile.yml was created
        print(f"1. Edit {cllm_dir}/Cllmfile.yml to configure your defaults")
        print('2. Set your API key: export OPENAI_API_KEY="sk-..."')
        print('3. Try it out: echo "Hello" | cllm')

    print()
    print("Documentation: https://github.com/owenzanzal/cllm")


def initialize(
    global_init: bool = False,
    local_init: bool = False,
    template_name: Optional[str] = None,
    force: bool = False,
    cllm_path: Optional[str] = None,
    config_overrides: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Initialize .cllm directory structure.

    Implements ADR-0016: Configurable .cllm Directory Path
    Implements ADR-0023: Configurable Init with CLI Flags

    Args:
        global_init: If True, initialize ~/.cllm
        local_init: If True, initialize ./.cllm
        template_name: Optional template name to use
        force: If True, overwrite existing files
        cllm_path: Optional custom directory path (overrides global_init/local_init)
        config_overrides: Optional configuration overrides to merge with template

    Raises:
        InitError: If initialization fails
    """
    # Determine which directories to initialize
    dirs_to_init = []

    # ADR-0016: Custom path takes precedence
    if cllm_path:
        custom_path = Path(cllm_path)
        dirs_to_init.append(("custom", custom_path))
    elif global_init and local_init:
        dirs_to_init.append(("global", get_home_cllm_dir()))
        dirs_to_init.append(("local", get_local_cllm_dir()))
    elif global_init:
        dirs_to_init.append(("global", get_home_cllm_dir()))
    elif local_init:
        dirs_to_init.append(("local", get_local_cllm_dir()))
    else:
        # Default: local init
        dirs_to_init.append(("local", get_local_cllm_dir()))

    # Initialize each directory
    for location, cllm_dir in dirs_to_init:
        print(f"Initializing {location} .cllm directory: {cllm_dir}")
        print()

        try:
            # Create directory structure
            _created_new, dir_messages = create_directory_structure(
                cllm_dir, force=force
            )
            for msg in dir_messages:
                print(msg)

            # Copy template (ADR-0023: with optional config overrides)
            template_messages = copy_template(
                cllm_dir,
                template_name,
                force=force,
                config_overrides=config_overrides,
            )
            for msg in template_messages:
                print(msg)

            # Update .gitignore (local only)
            gitignore_messages = update_gitignore(cllm_dir)
            for msg in gitignore_messages:
                print(msg)

            # Print next steps
            print_next_steps(cllm_dir, template_name)

        except InitError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
