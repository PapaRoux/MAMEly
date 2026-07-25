import os
import re
import shlex
import shutil
import subprocess
import xml.etree.ElementTree as ET

from config import Config, PlatformConfig, SkinConfig


class DiagnosticIssue:
    def __init__(self, level, category, message, fix=None, path=None):
        self.level = level
        self.category = category
        self.message = message
        self.fix = fix
        self.path = path

    def format(self, verbose=True):
        line = f"[{self.level.upper()}] {self.category}: {self.message}"
        if verbose and self.fix:
            line += f"\n         -> {self.fix}"
        if verbose and self.path:
            line += f"\n         @ {self.path}"
        return line


CONFIG_MAP = """
MAMEly configuration map
========================

App entry / launcher
  MAMEly.py                 Start the frontend
  main.py                   Application logic
  config.xml                Screen size + platform list (landscape)
  config-vertical.xml       Platform list for portrait layout

Per-platform folder: platforms/<PLATFORM>/
  config_*_<resolution>.txt Emulator command, ROM paths, extensions
  config_*_<resolution>.skin UI layout, fonts, colors, background image
  MAMEly.xml                Game database (titles, genres, favorites)
  _flags.txt                Per-ROM emulator flags (optional)
  _skipGenre.txt / _skipRating.txt  Filter lists (optional)

External emulator settings (not in MAMEly repo)
  Snap Snes9x:  ~/snap/snes9x-gtk/current/.config/snes9x/snes9x.conf
                fullscreen, filters, gamepad bindings, Esc behavior
  Flatpak Snes9x (if used): ~/.var/app/com.snes9x.Snes9x/config/snes9x/snes9x.conf
  MAMEly Snes9x overrides:   platforms/SNES/mamely-snes9x-config/ (Flatpak only)

Useful commands
  python MAMEly.py --check         Validate all platform configs
  python MAMEly.py --config-map    Show this settings map
  python MAMEly.py --wizard        Launch interactive Setup Wizard
  snap connections snes9x-gtk      Check Snap permissions (joystick, media)
  sudo snap connect snes9x-gtk:joystick
"""


def _executable_issues(emulator_executable):
    issues = []
    if not emulator_executable:
        issues.append(DiagnosticIssue(
            "error", "emulator",
            "emulatorExecutable is not set",
            "Set emulatorExecutable in the platform config .txt file",
        ))
        return issues

    exe = emulator_executable.strip()
    if "flatpak" in exe:
        if "--file-forwarding" not in exe:
            issues.append(DiagnosticIssue(
                "warn", "emulator",
                "Flatpak launch string is missing --file-forwarding",
                "Add --file-forwarding before the app id, or switch to a native/snap binary",
            ))
        if not shutil.which("flatpak"):
            issues.append(DiagnosticIssue(
                "error", "emulator",
                "flatpak is not installed but emulatorExecutable uses Flatpak",
                "Install flatpak or change emulatorExecutable to a local binary",
            ))
    elif exe.startswith("/"):
        if not os.path.isfile(exe) and not os.path.islink(exe):
            issues.append(DiagnosticIssue(
                "error", "emulator",
                f"Emulator path not found: {exe}",
                "Install the emulator or update emulatorExecutable",
                exe,
            ))
    else:
        resolved = shutil.which(shlex_first_token(exe))
        if not resolved:
            issues.append(DiagnosticIssue(
                "error", "emulator",
                f"Emulator command not found in PATH: {shlex_first_token(exe)}",
                "Install the emulator or use the full path in emulatorExecutable",
            ))

    if "snes9x" in exe.lower() or "/snap/bin/snes9x-gtk" in exe:
        issues.extend(_snes9x_issues(exe))

    return issues


def shlex_first_token(command):
    parts = shlex.split(command)
    return parts[0] if parts else command


def _snap_joystick_connected(snap_connections_output):
    """Return True/False if joystick slot is connected, or None if unknown."""
    for line in snap_connections_output.splitlines():
        if "snes9x-gtk:joystick" not in line:
            continue
        # Connected:   joystick  snes9x-gtk:joystick  :joystick  manual
        # Disconnected: joystick  snes9x-gtk:joystick  -          manual
        if re.search(r"snes9x-gtk:joystick\s+:joystick\b", line):
            return True
        if re.search(r"snes9x-gtk:joystick\s+-\s", line):
            return False
    return None


def _snes9x_issues(emulator_executable):
    issues = []

    if "/snap/bin/snes9x-gtk" in emulator_executable or emulator_executable.strip() == "snes9x-gtk":
        try:
            result = subprocess.run(
                ["snap", "connections", "snes9x-gtk"],
                capture_output=True, text=True, timeout=5,
            )
            connected = _snap_joystick_connected(result.stdout)
            if connected is False:
                issues.append(DiagnosticIssue(
                    "error", "gamepad",
                    "Snap Snes9x joystick interface is not connected",
                    "Run: sudo snap connect snes9x-gtk:joystick",
                ))
        except (FileNotFoundError, subprocess.TimeoutExpired):
            issues.append(DiagnosticIssue(
                "warn", "gamepad",
                "Could not verify Snap joystick permission",
                "Run: snap connections snes9x-gtk",
            ))

    conf_paths = [
        os.path.expanduser("~/snap/snes9x-gtk/current/.config/snes9x/snes9x.conf"),
    ]
    for conf_path in conf_paths:
        if not os.path.isfile(conf_path):
            continue
        unset = _count_unset_joypad_buttons(conf_path)
        if unset:
            issues.append(DiagnosticIssue(
                "warn", "gamepad",
                f"Snes9x config has {unset} unmapped gamepad buttons",
                "Open Snes9x Preferences -> Input and bind your controller, or edit snes9x.conf",
                conf_path,
            ))
        break

    return issues


ESSENTIAL_SNES_BUTTONS = {
    "Up", "Down", "Left", "Right", "A", "B", "X", "Y", "L", "R", "Select", "Start",
}


def _count_unset_joypad_buttons(conf_path):
    count = 0
    current_pad = None
    try:
        with open(conf_path, "r") as f:
            for line in f:
                line = line.strip()
                match = re.match(r"\[Joypad (\d+)\]", line)
                if match:
                    current_pad = int(match.group(1))
                    continue
                if line.startswith("["):
                    current_pad = None
                    continue
                if current_pad not in (0, 1):
                    continue
                if "= Unset" not in line:
                    continue
                button = line.split("=", 1)[0].strip()
                if button in ESSENTIAL_SNES_BUTTONS:
                    count += 1
    except OSError:
        return 0
    return count


def check_platform(base_path, platform_def):
    issues = []
    platform_path = os.path.join(base_path, "platforms", platform_def.folder)
    config_path = os.path.join(platform_path, platform_def.config_file)
    skin_path = os.path.join(platform_path, platform_def.skin_file)
    xml_path = os.path.join(platform_path, "MAMEly.xml")

    if not os.path.isdir(platform_path):
        issues.append(DiagnosticIssue(
            "error", "paths",
            f"Platform folder not found: {platform_def.folder}",
            "Check the <folder> entry in config.xml",
            platform_path,
        ))
        return issues

    if not os.path.isfile(config_path):
        issues.append(DiagnosticIssue(
            "error", "paths",
            f"Platform config not found: {platform_def.config_file}",
            "Check the <config> entry in config.xml",
            config_path,
        ))
        return issues

    if not os.path.isfile(skin_path):
        issues.append(DiagnosticIssue(
            "error", "paths",
            f"Skin file not found: {platform_def.skin_file}",
            "Check the <skin> entry in config.xml",
            skin_path,
        ))

    p_conf = PlatformConfig(platform_path, platform_def.config_file)
    skin = SkinConfig(platform_path, platform_def.skin_file)

    issues.extend(_executable_issues(p_conf.emulator_executable))

    if p_conf.emulator_base_path and not os.path.isdir(p_conf.emulator_base_path):
        issues.append(DiagnosticIssue(
            "error", "paths",
            f"emulatorBasePath does not exist: {p_conf.emulator_base_path}",
            "Update emulatorBasePath in the platform config .txt file",
            p_conf.emulator_base_path,
        ))

    if p_conf.rom_directory:
        if not os.path.isdir(p_conf.rom_directory):
            issues.append(DiagnosticIssue(
                "error", "paths",
                f"ROM directory not found: {p_conf.rom_directory}",
                "Create the folder or fix romDirectory / emulatorBasePath",
                p_conf.rom_directory,
            ))
        else:
            rom_count = _count_rom_files(p_conf.rom_directory, p_conf.rom_extension)
            if rom_count == 0:
                issues.append(DiagnosticIssue(
                    "warn", "roms",
                    f"No ROM files found in {p_conf.rom_directory}",
                    f"Add *{p_conf.rom_extension} files or update romDirectory",
                    p_conf.rom_directory,
                ))
            else:
                issues.append(DiagnosticIssue(
                    "info", "roms",
                    f"Found {rom_count} ROM file(s) in {p_conf.rom_directory}",
                    path=p_conf.rom_directory,
                ))

    if p_conf.rom_snap_directory and not os.path.isdir(p_conf.rom_snap_directory):
        issues.append(DiagnosticIssue(
            "warn", "paths",
            f"Snapshot directory not found: {p_conf.rom_snap_directory}",
            "Screenshots will not display until this folder exists",
            p_conf.rom_snap_directory,
        ))

    if not os.path.isfile(xml_path):
        issues.append(DiagnosticIssue(
            "error", "roms",
            "MAMEly.xml not found",
            "Generate it with the platform's *_generateMAMElyXML.py script",
            xml_path,
        ))
    else:
        game_count = _count_xml_games(xml_path)
        if game_count == 0:
            issues.append(DiagnosticIssue(
                "warn", "roms",
                "MAMEly.xml contains no games",
                "Regenerate MAMEly.xml from your ROM list",
                xml_path,
            ))
        else:
            issues.append(DiagnosticIssue(
                "info", "roms",
                f"MAMEly.xml lists {game_count} game(s)",
                path=xml_path,
            ))

    bg = skin.get("backgroundImage")
    if bg:
        bg_path = os.path.join(platform_path, bg)
        if not os.path.isfile(bg_path):
            issues.append(DiagnosticIssue(
                "warn", "skin",
                f"Background image not found: {bg}",
                "Add the image or update backgroundImage in the .skin file",
                bg_path,
            ))

    for font_key in ("romListDisplayFont", "genreSetFont", "romFileNameDisplayBoxFont"):
        font_name = skin.get(font_key)
        if font_name:
            font_path = os.path.join(platform_path, font_name)
            if not os.path.isfile(font_path):
                issues.append(DiagnosticIssue(
                    "warn", "skin",
                    f"Font not found: {font_name}",
                    "Add the font to the platform folder or change the .skin file",
                    font_path,
                ))

    issues.append(DiagnosticIssue(
        "info", "config",
        f"Platform config: {platform_def.config_file}",
        path=config_path,
    ))
    issues.append(DiagnosticIssue(
        "info", "config",
        f"Skin / UI layout: {platform_def.skin_file}",
        path=skin_path,
    ))

    return issues


def _count_rom_files(rom_directory, extension):
    count = 0
    try:
        with os.scandir(rom_directory) as entries:
            for entry in entries:
                if entry.is_file() and entry.name.endswith(extension):
                    count += 1
    except OSError:
        return 0
    return count


def _count_xml_games(xml_path):
    try:
        tree = ET.parse(xml_path)
        return sum(1 for child in tree.getroot() if child.tag == "game")
    except ET.ParseError:
        return 0


def check_all(base_path, config_file="config.xml"):
    config = Config(base_path, config_file)
    issues = []

    main_config_path = os.path.join(base_path, config_file)
    if not os.path.isfile(main_config_path):
        issues.append(DiagnosticIssue(
            "error", "config",
            f"Main config not found: {config_file}",
            "Create config.xml or pass --config=yourfile.xml",
            main_config_path,
        ))
        return issues

    if not config.platforms:
        issues.append(DiagnosticIssue(
            "error", "config",
            "No platforms defined in config.xml",
            "Add at least one <platform> block to config.xml",
            main_config_path,
        ))
        return issues

    for platform_def in config.platforms:
        issues.append(DiagnosticIssue(
            "info", "platform",
            f"Checking platform: {platform_def.name} ({platform_def.folder})",
        ))
        issues.extend(check_platform(base_path, platform_def))

    return issues


def format_report(issues, verbose=True):
    lines = []
    errors = warns = infos = 0
    for issue in issues:
        if issue.level == "error":
            errors += 1
        elif issue.level == "warn":
            warns += 1
        else:
            infos += 1
        lines.append(issue.format(verbose=verbose))

    summary = f"\nSummary: {errors} error(s), {warns} warning(s), {infos} info"
    return "\n".join(lines) + summary


def print_report(issues, verbose=True):
    print(format_report(issues, verbose=verbose))


def has_errors(issues):
    return any(issue.level == "error" for issue in issues)


def build_osd_lines(base_path, platform_def, platform_config, rom_count, issues):
    platform_path = os.path.join(base_path, "platforms", platform_def.folder)
    lines = [
        "MAMEly — Config & Help",
        "",
        f"Platform: {platform_def.name} ({platform_def.folder})",
        f"Main config: {os.path.basename(getattr(platform_config, 'config_file', '') or platform_def.config_file)}",
        f"Skin: {platform_def.skin_file}",
        f"Config folder: {platform_path}",
        "",
        "Paths",
        f"  emulatorBasePath: {platform_config.emulator_base_path or '(not set)'}",
        f"  romDirectory:     {platform_config.rom_directory or '(not set)'}",
        f"  romSnapDirectory: {platform_config.rom_snap_directory or '(not set)'}",
        "",
        "Emulator",
        f"  {platform_config.emulator_executable or '(not set)'}",
        "",
        f"ROMs in list: {rom_count}",
        "",
        "Controls",
        "  Up/Down     scroll   Tab      genre",
        "  Enter       launch   E        platform",
        "  F           favorite I        ignore",
        "  Esc         quit     F1       this panel",
        "",
        "Settings live in:",
        "  config.xml              — platforms & resolution",
        "  platforms/<P>/config_*.txt — emulator & ROM paths",
        "  platforms/<P>/config_*.skin — UI layout",
        "  platforms/<P>/MAMEly.xml    — game database",
        "  Emulator prefs (e.g. Snap Snes9x):",
        "    ~/snap/snes9x-gtk/current/.config/snes9x/snes9x.conf",
        "",
        "Troubleshooting:",
        "  python MAMEly.py --check",
        "  python MAMEly.py --config-map",
    ]

    problems = [i for i in issues if i.level in ("error", "warn")]
    if problems:
        lines.extend(["", "Issues"])
        for issue in problems[:6]:
            prefix = "!" if issue.level == "error" else "?"
            lines.append(f"  {prefix} {issue.message}")
            if issue.fix:
                lines.append(f"    -> {issue.fix}")
        if len(problems) > 6:
            lines.append(f"  ... +{len(problems) - 6} more (run --check)")

    return lines


def startup_message(issues):
    errors = [i for i in issues if i.level == "error"]
    warns = [i for i in issues if i.level == "warn"]
    if errors:
        return f"Config error: {errors[0].message}"
    if warns:
        return f"Config warning: {warns[0].message}"
    return ""
