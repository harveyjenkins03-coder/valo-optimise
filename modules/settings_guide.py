class SettingsGuide:
    """Pure static data class. No network calls, no system interaction."""

    GUIDE_DATA = {
        "display": {
            "title": "Display Settings",
            "settings": [
                {
                    "name": "Display Mode",
                    "recommended": "Fullscreen",
                    "note": "True fullscreen gives exclusive GPU access and the lowest possible input lag. Avoid Windowed Fullscreen.",
                },
                {
                    "name": "Resolution",
                    "recommended": "1920x1080 (native) or 1280x960 (stretched)",
                    "note": "Native gives best clarity. Stretched (4:3) widens hit boxes visually — requires custom resolution in GPU control panel.",
                },
                {
                    "name": "Refresh Rate",
                    "recommended": "Highest supported (144Hz / 240Hz / 360Hz)",
                    "note": "Set this in both Windows Display Settings AND Valorant. Higher = smoother motion and lower input lag.",
                },
                {
                    "name": "Limit FPS (Always)",
                    "recommended": "Off, or cap at monitor refresh rate",
                    "note": "Uncapped FPS reduces input lag. If your GPU runs hot, cap to 2x your refresh rate.",
                },
                {
                    "name": "Limit FPS (Menu / Background)",
                    "recommended": "30 FPS",
                    "note": "Saves GPU heat and power when you're not in-game.",
                },
            ],
        },
        "graphics": {
            "title": "Graphics Settings",
            "settings": [
                {
                    "name": "Material Quality",
                    "recommended": "Low",
                    "note": "No gameplay impact. Low gives maximum FPS.",
                },
                {
                    "name": "Texture Quality",
                    "recommended": "Low",
                    "note": "No gameplay impact. Low gives maximum FPS.",
                },
                {
                    "name": "Detail Quality",
                    "recommended": "Low",
                    "note": "No gameplay impact. Low gives maximum FPS.",
                },
                {
                    "name": "UI Quality",
                    "recommended": "Low",
                    "note": "No gameplay impact.",
                },
                {
                    "name": "Vignette",
                    "recommended": "Off",
                    "note": "Removes the dark screen edges that can obscure peripheral vision.",
                },
                {
                    "name": "VSync",
                    "recommended": "Off",
                    "note": "VSync adds 1-2 frames of input lag. Always turn off for competitive play.",
                },
                {
                    "name": "Anti-Aliasing",
                    "recommended": "MSAA 4x",
                    "note": "Makes agent outlines cleaner, helping you spot enemies. MSAA is better than FXAA for clarity.",
                },
                {
                    "name": "Anisotropic Filtering",
                    "recommended": "4x",
                    "note": "Improves floor/ground texture sharpness at angles. Small performance cost.",
                },
                {
                    "name": "Improve Clarity",
                    "recommended": "On",
                    "note": "Sharpens the overall image with minimal performance cost. Helps spot enemies.",
                },
                {
                    "name": "Bloom",
                    "recommended": "Off",
                    "note": "Disabling bloom removes distracting glow around bright objects.",
                },
                {
                    "name": "Distortion",
                    "recommended": "Off",
                    "note": "Removes heat-wave visual distortions that can obscure targets.",
                },
                {
                    "name": "Cast Shadows",
                    "recommended": "Off",
                    "note": "Significant FPS gain. Shadows add visual noise and have no competitive benefit.",
                },
                {
                    "name": "NVIDIA Reflex (if available)",
                    "recommended": "Enabled + Boost",
                    "note": "Reduces system latency by up to 30%. One of the biggest impact settings if you have an NVIDIA GPU.",
                },
            ],
        },
        "mouse": {
            "title": "Mouse Settings",
            "settings": [
                {
                    "name": "DPI",
                    "recommended": "400–1600 DPI",
                    "note": "Most pros use 400–800 DPI. Lower DPI = more physical movement = more precise micro-corrections. Find what fits your mouse pad size.",
                },
                {
                    "name": "In-Game Sensitivity",
                    "recommended": "0.2–0.5 (at 800 DPI)",
                    "note": "eDPI (DPI × Sensitivity) of 200–400 is the pro average. Calculate: your_dpi × sensitivity = eDPI.",
                },
                {
                    "name": "Scoped Sensitivity Multiplier",
                    "recommended": "1.0",
                    "note": "Keeping it at 1.0 means your muscle memory transfers to scoped shots. Only change if you play a lot of Operator.",
                },
                {
                    "name": "Windows Mouse Pointer Speed",
                    "recommended": "6/11 (default)",
                    "note": "Keep at the default Windows setting. Changing this applies Windows acceleration which breaks consistency.",
                },
                {
                    "name": "Enhance Pointer Precision (Windows)",
                    "recommended": "Off",
                    "note": "This is mouse acceleration. Turn it OFF in Windows Mouse Settings → Pointer Options for consistent aim.",
                },
                {
                    "name": "Mouse Polling Rate",
                    "recommended": "1000Hz or higher",
                    "note": "Higher polling rate = more frequent position updates. 1000Hz is the minimum; 8000Hz mice exist for ultra-low latency.",
                },
            ],
        },
        "crosshair": {
            "title": "Crosshair Recommendations",
            "settings": [
                {
                    "name": "Crosshair Color",
                    "recommended": "Cyan or Green",
                    "note": "High contrast against common map colors (brown, grey, beige). Avoid white or red — these blend with the map or damage indicators.",
                },
                {
                    "name": "Outlines",
                    "recommended": "On, Opacity 0.5, Thickness 1",
                    "note": "Outlines make your crosshair visible on all backgrounds. Light outline is better than none.",
                },
                {
                    "name": "Center Dot",
                    "recommended": "On, Opacity 1, Thickness 2",
                    "note": "A center dot gives you a precise aiming reference point, especially important for one-tapping.",
                },
                {
                    "name": "Inner Lines",
                    "recommended": "Off (for small crosshair) or 1/3/2/2",
                    "note": "Many pros use crosshair code 0;s;1;P;c;5;h;0;0t;1;0l;3;0a;1;0f;0;1t;0;1l;0;1a;0;1m;0;1s;0;S;c;4;o;1. Experiment to find comfort.",
                },
                {
                    "name": "Show Movement / Firing Error",
                    "recommended": "Off",
                    "note": "Turn off so your crosshair stays static. The spread is already happening — a moving crosshair just distracts you from your aim.",
                },
                {
                    "name": "Pro Crosshair Code (example)",
                    "recommended": "0;s;1;P;c;5;h;0;0t;1;0l;2;0a;1;0f;0;1b;0",
                    "note": "Import codes via Crosshair > Import Profile Code. Adjust size to your preference after importing.",
                },
            ],
        },
        "audio": {
            "title": "Audio Settings",
            "settings": [
                {
                    "name": "Master Volume",
                    "recommended": "85–100%",
                    "note": "Keep high so footsteps and ability sounds are audible at comfortable listening levels.",
                },
                {
                    "name": "Sound Effects Volume",
                    "recommended": "100%",
                    "note": "Footsteps, gunshots, and ability sounds are all here. This is the most competitive audio channel.",
                },
                {
                    "name": "Voice-over Volume",
                    "recommended": "50–75%",
                    "note": "Agent voice lines and callouts. Reduce if they distract you during fights.",
                },
                {
                    "name": "Music Volume",
                    "recommended": "0%",
                    "note": "Music can mask footsteps. Turn off for competitive play.",
                },
                {
                    "name": "HRTF (Headphones)",
                    "recommended": "On",
                    "note": "Head-Related Transfer Function simulates 3D positional audio through headphones. Dramatically improves ability to locate enemies by sound.",
                },
                {
                    "name": "Windows Audio: Spatial Sound",
                    "recommended": "Off (Windows Sonic / Dolby off)",
                    "note": "Windows spatial sound can interfere with Valorant's own HRTF. Disable it in Windows Sound Settings → Spatial Sound.",
                },
            ],
        },
    }

    def get_all_categories(self) -> list:
        return list(self.GUIDE_DATA.keys())

    def get_category(self, category: str) -> dict:
        return self.GUIDE_DATA.get(category, {})

    def get_all_data(self) -> dict:
        return self.GUIDE_DATA
