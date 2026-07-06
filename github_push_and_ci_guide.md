# GitHub Push & Multi-Platform Packaging Guide

This guide details the step-by-step process of pushing your local Git repository to GitHub, setting up authentication, and configuring a modern **GitHub Actions CI/CD Workflow** to automatically build standalone, bundled executables for Windows and macOS using **PyInstaller**.

---

## 1. Pushing the Local Repo to GitHub

### Step 1: Create a Repository on GitHub
1. Go to [github.com](https://github.com) and log in.
2. In the top-right corner, click the **`+`** icon and select **New repository**.
3. Name your repository (e.g., `fireworks-screensaver`).
4. Keep the repository **Public** or **Private** as desired.
5. > [!IMPORTANT]
   > Do **NOT** check "Add a README file", "Add .gitignore", or "Choose a license". Our local repository already contains a customized `.gitignore` and files, and we want to push our clean history without conflicts.
6. Click **Create repository**.

### Step 2: Choose Your Authentication Method
You can authenticate with GitHub using either **SSH Keys** (recommended for passwordless convenience) or a **Personal Access Token (PAT)**.

#### Option A: SSH Authentication (Recommended)
If you already have SSH keys set up on your machine and added to your GitHub account:
```bash
# Verify connection
ssh -T git@github.com
```

#### Option B: Personal Access Token (PAT)
If you prefer HTTPS authentication:
1. Go to your GitHub **Settings** > **Developer Settings** > **Personal Access Tokens** > **Tokens (classic)**.
2. Click **Generate new token (classic)**.
3. Name it and select the **`repo`** scope.
4. Copy the generated token immediately (you won't be able to see it again).

---

### Step 3: Add Remote and Push
On your local machine, open your terminal in the codebase folder (`/home/sumner/src/fireworks`) and execute:

```bash
# 1. (Optional) Rename your default branch to 'main' to match modern GitHub standards
git branch -M main

# 2. Add the remote GitHub origin (replace with your username and repo name)
# If using SSH:
git remote add origin git@github.com:your_username/fireworks-screensaver.git

# If using HTTPS (you will use your Personal Access Token as the password):
git remote add origin https://github.com/your_username/fireworks-screensaver.git

# 3. Push your main branch up to GitHub
git push -u origin main
```

---

## 2. Setting Up GitHub Actions CI/CD Pipeline

To automatically bundle the visualizer into standard standalone executable packages for Windows (`.exe`) and macOS (`.app` / zip), we will configure a GitHub Actions workflow using **PyInstaller**.

The configuration file is located under `.github/workflows/package.yml`.

### The `.github/workflows/package.yml` File Contents

```yaml
name: Package Executables

on:
  push:
    tags:
      - 'v*' # Triggers on tags like v1.0.0, v2.1.3
  workflow_dispatch: # Allows manual trigger from the GitHub Actions tab

jobs:
  build:
    name: Build on ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [windows-latest, macos-latest]

    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-on-environment: true
          python-version: '3.10'
          cache: 'pip'

      - name: Install System Dependencies (macOS)
        if: matrix.os == 'macos-latest'
        run: |
          brew install pygobject3 gtk+3

      - name: Install Python Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pyinstaller
          pip install -r requirements.txt

      - name: Download Static FFmpeg (Windows)
        if: matrix.os == 'windows-latest'
        shell: pwsh
        run: |
          curl.exe -L -o ffmpeg.zip https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v4.4.1/ffmpeg-4.4.1-win-64.zip
          Expand-Archive ffmpeg.zip -DestinationPath .
          Remove-Item ffmpeg.zip

      - name: Download Static FFmpeg (macOS)
        if: matrix.os == 'macos-latest'
        run: |
          curl -L -o ffmpeg.zip https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v4.4.1/ffmpeg-4.4.1-osx-64.zip
          unzip ffmpeg.zip
          chmod +x ffmpeg
          rm ffmpeg.zip

      - name: Build Standalone Executable (Windows)
        if: matrix.os == 'windows-latest'
        run: |
          pyinstaller --onefile --noconsole --add-binary "ffmpeg.exe;." --name="FireworksVisualizer" main.py

      - name: Build Standalone Executable (macOS)
        if: matrix.os == 'macos-latest'
        run: |
          pyinstaller --windowed --add-binary "ffmpeg:." --name="FireworksVisualizer" main.py

      - name: Upload Artifacts
        uses: actions/upload-artifact@v4
        with:
          name: FireworksVisualizer-${{ matrix.os }}
          path: |
            dist/FireworksVisualizer.exe
            dist/FireworksVisualizer.app
            dist/FireworksVisualizer
```

### To publish a Release automatically:
Once you push a tag (e.g. `git tag -a v1.0.0 -m "Release v1.0.0" && git push origin v1.0.0`), the workflow runs and outputs packaged binaries directly into your **GitHub Actions** tab for instant download or releases!

---

## 3. How Multi-Platform Support is Achieved

| Feature | Windows Behavior | macOS Behavior | Linux Behavior |
| :--- | :--- | :--- | :--- |
| **Audio Playback** | Tries `mpv` subprocess; falls back to background **`sounddevice` + `soundfile`/`audioread`** decoder | Tries `mpv` subprocess; falls back to background **`sounddevice` + `soundfile`/`audioread`** decoder | Uses `mpv` subprocess if installed; falls back to `sounddevice` output |
| **Script Cache Path** | Created under `%TEMP%\fireworks_cache\` | Created under `$TMPDIR/fireworks_cache/` | Created under `/tmp/fireworks_cache/` |
| **Hashed Subdirectories** | Double-nested layout (e.g., `cb\54\<hash>.json`) preventing lookup delays and storage clutter | Double-nested layout (e.g., `cb/54/<hash>.json`) preventing lookup delays and storage clutter | Double-nested layout (e.g., `cb/54/<hash>.json`) |
| **Recording Feature** | Resolved dynamically. Fails with graceful error message if FFmpeg is absent | Resolved dynamically. Fails with graceful error message if FFmpeg is absent | Runs locally with `/home/sumner/bin/ffmpeg` or resolved system path |
