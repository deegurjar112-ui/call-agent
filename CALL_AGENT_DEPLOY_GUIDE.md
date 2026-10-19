# 🚀 Aria 24/7 Voice AI - Deployment & GitHub Setup Guide

This guide explains how to push your code to your GitHub account and run it 24/7 on the cloud so it never stops—even when your laptop is turned off.

---

## 📁 Key Project Files

| File | Purpose |
|------|---------|
| `agent.py` | Core LiveKit Voice Agent (Google Gemini 3.8 Flash + Deepgram STT/TTS + Silero VAD) |
| `demo_server.py` | Web demo server & token generator (WebRTC connection to LiveKit Cloud) |
| `index.html` | High-converting client demo UI & real-time booking dispatch panel |
| `start_all_cloud.py` | Orchestrator that runs both `agent.py` and `demo_server.py` 24/7 in cloud |
| `requirements.txt` | Python dependencies for cloud build |
| `Procfile` | Configuration for Railway / Render one-click hosting |
| `.env.example` | Template for environment variables |

---

## 🔒 Security Notice: Your API Keys Are Protected!

Your `.env` and `.env.local` files contain secret API keys (`LIVEKIT_API_SECRET`, `GEMINI_API_KEY`, `DEEPGRAM_API_KEY`).
These are **strictly excluded** in `.gitignore` so they are **never uploaded to GitHub**.

When deploying to Railway, Render, or a VPS, you will paste these keys securely in the cloud platform's **Environment Variables** dashboard.

---

## 🛠️ Step 1: Push Code to Your GitHub

1. Go to **[https://github.com/new](https://github.com/new)** and create a new repository (e.g., `aria-voice-agent`). Set it to **Private** or **Public**.
2. Copy your new repository URL (e.g., `https://github.com/YOUR_USERNAME/aria-voice-agent.git`).
3. In your terminal / command prompt, run:
   ```bash
   # Set your GitHub user info
   git config user.name "Your Name"
   git config user.email "your-email@example.com"

   # Point the remote to YOUR new repository
   git remote set-url origin https://github.com/YOUR_USERNAME/aria-voice-agent.git

   # Add and commit all files
   git add agent.py demo_server.py index.html requirements.txt start_all_cloud.py Procfile .env.example CALL_AGENT_DEPLOY_GUIDE.md all_in_one_agent.py ALL_IN_ONE_SYSTEM_CODE.md start_public_demo.bat start_localtunnel_demo.bat run_dev.bat run_console.bat .gitignore

   git commit -m "feat: Add Aria 24/7 Voice AI Agent and Cloud Web Demo"

   # Push to your GitHub
   git branch -M main
   git push -u origin main
   ```

---

## ☁️ Step 2: Deploy 24/7 on Railway (Easiest & Recommended)

1. Open **[Railway.app](https://railway.app)** and log in with your GitHub account.
2. Click **"New Project"** -> **"Deploy from GitHub repo"**.
3. Select your repository (`aria-voice-agent`).
4. Go to **Variables** tab and add your keys from `.env.local`:
   * `LIVEKIT_URL` = `wss://dee-yfqt06tv.livekit.cloud`
   * `LIVEKIT_API_KEY` = `...`
   * `LIVEKIT_API_SECRET` = `...`
   * `GEMINI_API_KEY` = `...`
   * `GOOGLE_API_KEY` = `...`
   * `DEEPGRAM_API_KEY` = `...`
5. Go to **Settings** -> **Networking** -> Click **"Generate Domain"**.
6. **Done!** Railway will give you a public HTTPS link (e.g. `https://aria-agent-production.up.railway.app`).
   * This link runs 24 hours a day, 365 days a year.
   * You can close your laptop, turn off your internet, and the demo will always work!

---

## 🖥️ Alternative: Deploy on Ubuntu Cloud VPS (DigitalOcean / Hostinger / AWS)

1. Connect to your VPS via SSH.
2. Clone your repo:
   ```bash
   git clone https://github.com/YOUR_USERNAME/aria-voice-agent.git
   cd aria-voice-agent
   ```
3. Install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
4. Create `.env.local` on the VPS and paste your API keys.
5. Run 24/7 with `pm2` or `systemd`:
   ```bash
   pip install pm2 # or use systemd
   pm2 start start_all_cloud.py --name "aria-agent" --interpreter ./venv/bin/python
   pm2 save
   pm2 startup
   ```
