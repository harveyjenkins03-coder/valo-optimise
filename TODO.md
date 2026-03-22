# Valo Optimise — Monetisation & Launch Roadmap

## Critical Path (do these first, in order)
- [ ] 1. Set up Paddle or Stripe payment processor account
- [ ] 2. Build licence key generation and validation system (server-side API)
- [ ] 3. Add hardware-locked licence key check to app startup (machine ID binding)
- [ ] 4. Define free vs Pro tier feature gating (gate 8 advanced tabs, keep 4 free)
- [ ] 5. Implement free tier limits in app (stats: 3 lookups/day, profiles: 1 max)
- [ ] 6. Add upgrade prompt UI when free user tries to access a Pro tab
- [ ] 7. Set up lightweight licence validation server (Flask or FastAPI on a VPS)
- [ ] 8. Add auto-update mechanism so Pro users always get the latest version

## Features & Polish
- [ ] 9. Add NVIDIA GPU feature parity (Reflex, shader cache, driver power settings)
- [ ] 10. Add opt-in telemetry/analytics to track most-used features

## Distribution
- [ ] 11. Package app as a signed Windows .exe installer (PyInstaller + code signing)
- [ ] 12. Set up GitHub Actions CI for automated builds and releases on each push

## Marketing & Growth
- [ ] 13. Create a Discord server for the Valo Optimise community
- [ ] 14. Write v1.0 launch post for r/VALORANT, r/pcgaming, r/pcmasterrace
- [ ] 15. Record short demo video showing the pre-game boost sequence (10-second hook)
- [ ] 16. Set up a landing page with pricing tiers (Free / Pro £4.99/mo / Lifetime £69.99)
- [ ] 17. Add referral system (share link = 1 month free) to drive organic growth
- [ ] 18. Submit to AppSumo or a gaming deal site for a Lifetime deal promotion
