import ctypes
import winreg

# Win32 constants
SPI_SETANIMATION  = 0x0049
SPI_GETANIMATION  = 0x0048
SPI_SETUIEFFECTS  = 0x103F
SPI_GETUIEFFECTS  = 0x103E
SPIF_SENDCHANGE   = 0x0002


class _ANIMATIONINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("iMinAnimate", ctypes.c_int)]


class VisualOptimizer:

    # ── Visual Effects ───────────────────────────────────────────────────────

    def get_visual_effects_mode(self) -> str:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
                0, winreg.KEY_READ
            ) as key:
                val, _ = winreg.QueryValueEx(key, "VisualFXSetting")
                return {0: "Let Windows choose", 1: "Best Appearance",
                        2: "Best Performance", 3: "Custom"}.get(val, "Unknown")
        except Exception:
            return "Unknown"

    def set_best_performance(self) -> tuple:
        """Sets all visual effects to Best Performance and applies immediately."""
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
                0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, "VisualFXSetting", 0, winreg.REG_DWORD, 2)
        except Exception as e:
            return False, f"Registry write failed: {e}"

        # Apply animations off immediately
        anim = _ANIMATIONINFO()
        anim.cbSize = ctypes.sizeof(_ANIMATIONINFO)
        anim.iMinAnimate = 0
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETANIMATION, ctypes.sizeof(_ANIMATIONINFO),
            ctypes.byref(anim), SPIF_SENDCHANGE
        )
        # Disable UI effects
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETUIEFFECTS, 0, ctypes.c_bool(False), SPIF_SENDCHANGE
        )
        return True, "Visual effects set to Best Performance. Animations disabled immediately."

    def restore_visual_effects(self) -> tuple:
        """Restores Windows default visual effects (Let Windows choose)."""
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
                0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, "VisualFXSetting", 0, winreg.REG_DWORD, 0)
        except Exception as e:
            return False, f"Registry write failed: {e}"

        anim = _ANIMATIONINFO()
        anim.cbSize = ctypes.sizeof(_ANIMATIONINFO)
        anim.iMinAnimate = 1
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETANIMATION, ctypes.sizeof(_ANIMATIONINFO),
            ctypes.byref(anim), SPIF_SENDCHANGE
        )
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETUIEFFECTS, 0, ctypes.c_bool(True), SPIF_SENDCHANGE
        )
        return True, "Visual effects restored to Windows defaults."

    # ── Game Mode ────────────────────────────────────────────────────────────

    def get_game_mode_status(self) -> str:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\GameBar",
                0, winreg.KEY_READ
            ) as key:
                val, _ = winreg.QueryValueEx(key, "AllowAutoGameMode")
                return "Enabled" if val == 1 else "Disabled"
        except Exception:
            return "Unknown"

    def enable_game_mode(self) -> tuple:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\GameBar",
                0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, "AllowAutoGameMode",   0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "AutoGameModeEnabled", 0, winreg.REG_DWORD, 1)
            return True, "Windows Game Mode enabled."
        except Exception as e:
            return False, str(e)

    def disable_game_mode(self) -> tuple:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\GameBar",
                0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, "AllowAutoGameMode",   0, winreg.REG_DWORD, 0)
                winreg.SetValueEx(key, "AutoGameModeEnabled", 0, winreg.REG_DWORD, 0)
            return True, "Windows Game Mode disabled."
        except Exception as e:
            return False, str(e)

    # ── Transparency ─────────────────────────────────────────────────────────

    def get_transparency_status(self) -> str:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                0, winreg.KEY_READ
            ) as key:
                val, _ = winreg.QueryValueEx(key, "EnableTransparency")
                return "Enabled" if val == 1 else "Disabled"
        except Exception:
            return "Unknown"

    def disable_transparency(self) -> tuple:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, "EnableTransparency", 0, winreg.REG_DWORD, 0)
            return True, "Transparency effects disabled. GPU freed from taskbar/window rendering."
        except Exception as e:
            return False, str(e)

    def enable_transparency(self) -> tuple:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, "EnableTransparency", 0, winreg.REG_DWORD, 1)
            return True, "Transparency effects re-enabled."
        except Exception as e:
            return False, str(e)
