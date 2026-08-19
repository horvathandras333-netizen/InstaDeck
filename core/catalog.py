"""Curated winget app catalog, categories and one-click presets.

Every entry maps to a real winget package identifier. `size` is an approximate
installer footprint in MB, used only for the "approx. Y MB" estimate in the UI.
"""

# Category hues follow the Modernist design system's four-hue legend:
# blue = browsers/dev, amber = media/security, green = gaming, orange = utilities.
HUE_BLUE = "#5b8cff"
HUE_AMBER = "#ffb020"
HUE_GREEN = "#3ddc84"
HUE_ORANGE = "#ff5c1a"

CATEGORIES = [
    {"id": "all",      "label": "All packages", "hue": HUE_ORANGE},
    {"id": "web",      "label": "Browsers",     "hue": HUE_BLUE},
    {"id": "media",    "label": "Media",        "hue": HUE_AMBER},
    {"id": "dev",      "label": "Development",  "hue": HUE_BLUE},
    {"id": "gaming",   "label": "Gaming",       "hue": HUE_GREEN},
    {"id": "utils",    "label": "Utilities",    "hue": HUE_ORANGE},
    {"id": "security", "label": "Security",     "hue": HUE_AMBER},
]

LEGEND = [
    {"name": "Browsers / Dev",   "hue": HUE_BLUE},
    {"name": "Media / Security", "hue": HUE_AMBER},
    {"name": "Gaming",           "hue": HUE_GREEN},
    {"name": "Utilities",        "hue": HUE_ORANGE},
]

CATEGORY_HUE = {c["id"]: c["hue"] for c in CATEGORIES}


def _app(pkg_id, name, publisher, category, desc, size, color, mark=None):
    return {
        "id": pkg_id,
        "name": name,
        "publisher": publisher,
        "category": category,
        "desc": desc,
        "size": size,
        "color": color,
        "mark": mark or name[0].upper(),
        "hue": CATEGORY_HUE.get(category, HUE_ORANGE),
        # Every curated entry is pinned to the official winget community
        # repository; search results carry whatever source winget reports.
        "source": "winget",
    }


APPS = [
    # --- Web & Browsers -----------------------------------------------------
    _app("Google.Chrome", "Google Chrome", "Google LLC", "web",
         "The most widely used web browser on the planet.", 110, "#4285F4", "C"),
    _app("Brave.Brave", "Brave", "Brave Software", "web",
         "Privacy-first browser with a built-in ad blocker.", 145, "#FB542B", "B"),
    _app("Mozilla.Firefox", "Mozilla Firefox", "Mozilla", "web",
         "Open-source browser built for independence.", 60, "#FF7139", "F"),
    _app("Microsoft.Edge", "Microsoft Edge", "Microsoft Corporation", "web",
         "Chromium browser deeply integrated with Windows.", 150, "#0F7EBD", "E"),
    _app("Vivaldi.Vivaldi", "Vivaldi", "Vivaldi Technologies", "web",
         "Highly customisable browser for power users.", 95, "#EF3939", "V"),
    _app("Opera.Opera", "Opera", "Opera Software", "web",
         "Chromium browser with a built-in VPN and workspaces.", 105, "#FF1B2D", "O"),

    # --- Gaming & Launchers -------------------------------------------------
    _app("Valve.Steam", "Steam", "Valve Corporation", "gaming",
         "The largest PC game store and library manager.", 320, "#1B2838", "S"),
    _app("EpicGames.EpicGamesLauncher", "Epic Games Launcher", "Epic Games, Inc.", "gaming",
         "Home of Fortnite and the weekly free game giveaway.", 280, "#2A2A2A", "E"),
    _app("Discord.Discord", "Discord", "Discord Inc.", "gaming",
         "Voice, video and text chat built for gamers.", 190, "#5865F2", "D"),
    _app("Blizzard.BattleNet", "Battle.net", "Blizzard Entertainment", "gaming",
         "Launcher for Blizzard and Activision titles.", 160, "#00AEFF", "B"),
    _app("ElectronicArts.EADesktop", "EA app", "Electronic Arts", "gaming",
         "Successor to Origin for the EA game catalogue.", 210, "#FF4747", "EA"),
    _app("Ubisoft.Connect", "Ubisoft Connect", "Ubisoft", "gaming",
         "Launcher and rewards hub for Ubisoft games.", 175, "#0F8CE9", "U"),
    _app("GOG.Galaxy", "GOG Galaxy", "GOG.com", "gaming",
         "DRM-free store that unifies all your libraries.", 240, "#8A2BE2", "G"),
    _app("Guru3D.Afterburner", "MSI Afterburner", "Guru3D", "gaming",
         "GPU overclocking, monitoring and on-screen stats.", 55, "#C8102E", "MA"),

    # --- Media & Streaming --------------------------------------------------
    _app("VideoLAN.VLC", "VLC Media Player", "VideoLAN", "media",
         "Plays practically every media format ever made.", 45, "#FF8800", "VL"),
    _app("OBSProject.OBSStudio", "OBS Studio", "OBS Project", "media",
         "Free studio-grade streaming and screen recording.", 130, "#302E31", "OB"),
    _app("Spotify.Spotify", "Spotify", "Spotify AB", "media",
         "Streaming music, podcasts and audiobooks.", 175, "#1DB954", "S"),
    _app("HandBrake.HandBrake", "HandBrake", "HandBrake Team", "media",
         "Batch video transcoder with finely tuned presets.", 90, "#F5A623", "HB"),
    _app("Audacity.Audacity", "Audacity", "Audacity Team", "media",
         "Multi-track audio recording and editing.", 80, "#1E40E5", "A"),
    _app("GIMP.GIMP.3", "GIMP", "The GIMP Team", "media",
         "Full-featured open-source image editor.", 350, "#5C5543", "G"),
    _app("Gyan.FFmpeg", "FFmpeg", "Gyan Doshi", "media",
         "The command-line backbone of media conversion.", 85, "#3B7A57", "FF"),

    # --- Utilities & P2P ----------------------------------------------------
    _app("qBittorrent.qBittorrent", "qBittorrent", "The qBittorrent Project", "utils",
         "Lightweight, ad-free BitTorrent client.", 40, "#2F67BA", "qB"),
    _app("7zip.7zip", "7-Zip", "Igor Pavlov", "utils",
         "Fast archiver with the best-in-class 7z format.", 6, "#0B7C3F", "7z"),
    _app("Microsoft.PowerToys", "PowerToys", "Microsoft Corporation", "utils",
         "Power-user utilities: FancyZones, Run and more.", 220, "#0078D4", "PT"),
    _app("Rufus.Rufus", "Rufus", "Akeo Consulting", "utils",
         "Creates bootable USB drives in seconds.", 5, "#C4302B", "R"),
    _app("voidtools.Everything", "Everything", "voidtools", "utils",
         "Instant filename search across every drive.", 8, "#F2B705", "Ev"),
    _app("Notepad++.Notepad++", "Notepad++", "Notepad++ Team", "utils",
         "Fast tabbed text editor with syntax highlighting.", 20, "#90C43C", "N+"),
    _app("ShareX.ShareX", "ShareX", "ShareX Team", "utils",
         "Screenshot, screen record and instant upload.", 95, "#2D8CF0", "SX"),
    _app("AntibodySoftware.WizTree", "WizTree", "Antibody Software", "utils",
         "Finds what is eating your disk space, fast.", 12, "#4A90D9", "WT"),
    _app("RARLab.WinRAR", "WinRAR", "RARLab", "utils",
         "The classic RAR and ZIP archive manager.", 15, "#7E3FF2", "WR"),

    # --- Developer Tools ----------------------------------------------------
    _app("Microsoft.VisualStudioCode", "Visual Studio Code", "Microsoft Corporation", "dev",
         "The extensible editor most developers live in.", 120, "#0078D4", "VS"),
    _app("Git.Git", "Git", "The Git Development Community", "dev",
         "Distributed version control, plus Git Bash.", 65, "#F1502F", "G"),
    _app("Docker.DockerDesktop", "Docker Desktop", "Docker Inc.", "dev",
         "Build and run containers locally on Windows.", 1400, "#2496ED", "Dk"),
    _app("OpenJS.NodeJS.LTS", "Node.js (LTS)", "OpenJS Foundation", "dev",
         "JavaScript runtime with npm, long-term support.", 90, "#539E43", "Nd"),
    _app("Python.Python.3.13", "Python 3.13", "Python Software Foundation", "dev",
         "The Python interpreter, pip and IDLE.", 110, "#3776AB", "Py"),
    _app("GitHub.cli", "GitHub CLI", "GitHub, Inc.", "dev",
         "Manage pull requests and issues from a terminal.", 35, "#24292E", "gh"),
    _app("Postman.Postman", "Postman", "Postman, Inc.", "dev",
         "Design, test and document HTTP APIs.", 480, "#FF6C37", "Pm"),
    _app("Microsoft.WindowsTerminal", "Windows Terminal", "Microsoft Corporation", "dev",
         "Modern tabbed terminal with GPU rendering.", 45, "#3A96DD", "WT"),
    _app("WinSCP.WinSCP", "WinSCP", "Martin Prikryl", "dev",
         "SFTP, FTP and SCP file transfer client.", 30, "#1F7BC1", "WS"),

    # --- Security -----------------------------------------------------------
    _app("Bitwarden.Bitwarden", "Bitwarden", "Bitwarden Inc.", "security",
         "Vault with autofill and passkey storage.", 88, "#175DDC", "Bw"),
    _app("KeePassXCTeam.KeePassXC", "KeePassXC", "KeePassXC Team", "security",
         "Offline password vault in a local KDBX file.", 45, "#2C6E9B", "KP"),
    _app("Malwarebytes.Malwarebytes", "Malwarebytes", "Malwarebytes Corp.", "security",
         "On-demand scanner that runs alongside Defender.", 268, "#0D3B66", "Mb"),
    _app("IDRIX.VeraCrypt", "VeraCrypt", "IDRIX", "security",
         "Full-disk and container encryption volumes.", 44, "#F5C400", "VC"),
    _app("Proton.ProtonVPN", "Proton VPN", "Proton AG", "security",
         "Swiss-based encrypted VPN with a free tier.", 120, "#6D4AFF", "P"),
    _app("Cloudflare.Warp", "Cloudflare WARP", "Cloudflare, Inc.", "security",
         "Encrypted DNS and tunnelling via 1.1.1.1.", 60, "#F6821F", "CW"),
]


PRESETS = [
    {
        "id": "fresh",
        "label": "Fresh laptop",
        "blurb": "The things you install on every new machine.",
        "apps": ["Google.Chrome", "7zip.7zip", "VideoLAN.VLC",
                 "Notepad++.Notepad++", "Microsoft.PowerToys", "voidtools.Everything"],
    },
    {
        "id": "gaming",
        "label": "Gaming rig",
        "blurb": "Every launcher, chat and tuning tool that matters.",
        "apps": ["Valve.Steam", "EpicGames.EpicGamesLauncher", "Discord.Discord",
                 "Blizzard.BattleNet", "Guru3D.Afterburner", "qBittorrent.qBittorrent"],
    },
    {
        "id": "streaming",
        "label": "Streaming rig",
        "blurb": "Capture, edit, encode and ship your content.",
        "apps": ["OBSProject.OBSStudio", "HandBrake.HandBrake", "Audacity.Audacity",
                 "ShareX.ShareX", "GIMP.GIMP.3", "Gyan.FFmpeg"],
    },
    {
        "id": "devbox",
        "label": "Dev box",
        "blurb": "Editor, toolchain, shell and containers.",
        "apps": ["Microsoft.VisualStudioCode", "Git.Git", "Python.Python.3.13",
                 "OpenJS.NodeJS.LTS", "Microsoft.WindowsTerminal", "GitHub.cli"],
    },
    {
        "id": "hardened",
        "label": "Hardened",
        "blurb": "Vault, scanner and encrypted transport.",
        "apps": ["Bitwarden.Bitwarden", "Malwarebytes.Malwarebytes",
                 "IDRIX.VeraCrypt", "Cloudflare.Warp"],
    },
]


def by_id(pkg_id):
    """Case-insensitive catalog lookup, or None."""
    needle = pkg_id.lower()
    for app in APPS:
        if app["id"].lower() == needle:
            return app
    return None
