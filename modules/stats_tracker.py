import time
import requests


_LOOKUP_COOLDOWN = 3.0  # seconds between player lookups


class StatsTracker:
    BASE_URL = "https://api.henrikdev.xyz/valorant"
    TIMEOUT = 10

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ValoOptimise/1.0"})
        self._last_lookup: float = 0.0

    def parse_riot_id(self, riot_id: str) -> tuple:
        """Parse 'Name#TAG' into ('Name', 'TAG'). Raises ValueError if invalid."""
        if "#" not in riot_id:
            raise ValueError("Riot ID must be in Name#TAG format (e.g. Player#NA1)")
        parts = riot_id.strip().split("#", 1)
        name, tag = parts[0].strip(), parts[1].strip()
        if not name or not tag:
            raise ValueError("Name and tag cannot be empty.")
        return name, tag

    def _safe_get(self, url: str, params: dict = None) -> dict:
        try:
            resp = self.session.get(url, params=params, timeout=self.TIMEOUT, verify=True)
            resp.raise_for_status()
            return resp.json()
        except requests.Timeout:
            raise ConnectionError("Request timed out. Check your internet connection.")
        except requests.ConnectionError:
            raise ConnectionError("Cannot reach the stats server. Check your internet connection.")
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            if code == 404:
                raise ValueError("Player not found. Check your Riot ID and region.")
            raise ConnectionError(f"API error ({code}). Please try again.")

    def get_account(self, name: str, tag: str) -> dict:
        url = f"{self.BASE_URL}/v1/account/{requests.utils.quote(name)}/{requests.utils.quote(tag)}"
        return self._safe_get(url)

    def get_mmr(self, region: str, name: str, tag: str) -> dict:
        url = f"{self.BASE_URL}/v2/mmr/{region}/{requests.utils.quote(name)}/{requests.utils.quote(tag)}"
        return self._safe_get(url)

    def get_match_history(self, region: str, name: str, tag: str, count: int = 5) -> dict:
        url = f"{self.BASE_URL}/v3/matches/{region}/{requests.utils.quote(name)}/{requests.utils.quote(tag)}"
        return self._safe_get(url, params={"size": count})

    def build_player_summary(self, riot_id: str, region: str) -> dict:
        """
        Orchestrates API calls and returns a structured player summary dict.
        Raises ValueError or ConnectionError on failure.
        """
        # Rate limiting — prevent hammering the API
        now = time.monotonic()
        elapsed = now - self._last_lookup
        if elapsed < _LOOKUP_COOLDOWN:
            remaining = round(_LOOKUP_COOLDOWN - elapsed, 1)
            raise ConnectionError(f"Please wait {remaining}s before looking up again.")
        self._last_lookup = now

        name, tag = self.parse_riot_id(riot_id)

        account_resp = self.get_account(name, tag)
        account_data = account_resp.get("data", {})

        mmr_resp = self.get_mmr(region, name, tag)
        mmr_data = mmr_resp.get("data", {})

        matches_resp = self.get_match_history(region, name, tag, count=5)
        matches_raw = matches_resp.get("data", [])

        recent_matches = []
        for m in matches_raw:
            meta = m.get("metadata", {})
            players = m.get("players", {})
            all_players = players.get("all_players", [])

            # Find this player's stats in the match
            puuid = account_data.get("puuid", "")
            player_stats = {}
            for p in all_players:
                if p.get("puuid") == puuid or (
                    p.get("name", "").lower() == name.lower()
                    and p.get("tag", "").lower() == tag.lower()
                ):
                    player_stats = p
                    break

            stats = player_stats.get("stats", {})
            kills = stats.get("kills", 0)
            deaths = stats.get("deaths", 1)
            assists = stats.get("assists", 0)
            kda = round((kills + assists) / max(deaths, 1), 2)

            teams = m.get("teams", {})
            player_team = player_stats.get("team", "").lower()
            team_data = teams.get(player_team, {})
            won = team_data.get("has_won", False)

            recent_matches.append({
                "map": meta.get("map", "Unknown"),
                "mode": meta.get("mode", "Unknown"),
                "won": won,
                "kills": kills,
                "deaths": deaths,
                "assists": assists,
                "kda_ratio": kda,
                "agent": player_stats.get("character", "Unknown"),
                "score": stats.get("score", 0),
                "date": meta.get("game_start_patched", ""),
            })

        computed = self._calculate_stats(recent_matches)

        current_data = mmr_data.get("current_data", {})
        peak = mmr_data.get("highest_rank", {})

        return {
            "account": {
                "name": account_data.get("name", name),
                "tag": account_data.get("tag", tag),
                "puuid": account_data.get("puuid", ""),
                "account_level": account_data.get("account_level", 0),
                "card_url": account_data.get("card", {}).get("small", ""),
            },
            "rank": {
                "current_tier_name": current_data.get("currenttierpatched", "Unranked"),
                "ranking_in_tier": current_data.get("ranking_in_tier", 0),
                "elo": current_data.get("elo", 0),
                "peak_rank": peak.get("patched_tier", "N/A"),
                "last_change": current_data.get("mmr_change_to_last_game", 0),
            },
            "recent_matches": recent_matches,
            "stats": computed,
        }

    def _calculate_stats(self, matches: list) -> dict:
        if not matches:
            return {"win_rate": 0.0, "avg_kda": 0.0, "most_played_agent": "N/A", "total_matches_checked": 0}
        wins = sum(1 for m in matches if m["won"])
        win_rate = round(wins / len(matches) * 100, 1)
        avg_kda = round(sum(m["kda_ratio"] for m in matches) / len(matches), 2)
        agent_counts: dict = {}
        for m in matches:
            a = m["agent"]
            agent_counts[a] = agent_counts.get(a, 0) + 1
        most_played = max(agent_counts, key=lambda k: agent_counts[k]) if agent_counts else "N/A"
        return {
            "win_rate": win_rate,
            "avg_kda": avg_kda,
            "most_played_agent": most_played,
            "total_matches_checked": len(matches),
        }
