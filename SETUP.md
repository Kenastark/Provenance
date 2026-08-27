# Setup

Everything to do **before** you paste the Phase 1 prompt into Claude Code.
Written for macOS on Apple Silicon. Budget about 30 minutes the first time.

---

## 0. What you already have

This repository is the completed Phase 0: the directory structure, tooling, CI,
Docker stack, test harness, reason-code registry, brand assets, and design
tokens. It is not an empty folder — it is a working, tested scaffold that
`make check` passes on today.

That means you start at Phase 1, not Phase 0. Phase 0 in the build-prompts
document is now a **verification** pass rather than a creation pass.

---

## 1. Install the toolchain

Check what you already have:

    git --version
    python3 --version      # want 3.12.x
    node --version         # want 20+
    docker --version

Install anything missing. With Homebrew:

    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    brew install git gh
    brew install --cask docker          # then launch Docker Desktop once
    curl -LsSf https://astral.sh/uv/install.sh | sh    # uv: Python env manager
    brew install node
    corepack enable && corepack prepare pnpm@9 --activate

`uv` is what `make install` uses. If you would rather not install it, `make
install-pip` does the same job with the standard library `venv` module.

Confirm Docker is actually running before you go further — `docker ps` should
return an empty table rather than an error.

---

## 2. Put the project somewhere sensible

Unzip `Provenance.zip` wherever you keep code. Avoid iCloud Drive and Dropbox
folders: file-sync daemons and `.venv` directories interact badly, and you will
lose an afternoon to it.

    mkdir -p ~/code && cd ~/code
    unzip ~/Downloads/Provenance.zip
    cd Provenance

---

## 3. Create the virtual environment

**Virtual environments are never committed.** `.venv/` is gitignored. Each
machine creates its own, which is why the zip does not contain one.

    make install        # creates .venv and installs the package with dev extras
    source .venv/bin/activate

If you do not have `uv`:

    make install-pip
    source .venv/bin/activate

Sanity check:

    prov --help
    prov codes list

You should see the reason-code registry — R01 through R21, with R18 and R19
marked as not counting toward the defect rate. That is the standing rule about
structural absence, already encoded.

Then the frontend:

    make web-install    # pnpm install in apps/web

---

## 4. Prove the scaffold works

    make check          # ruff + ruff format + mypy strict + pytest with coverage gate

All three must be clean. If they are not, fix that **before** involving Claude
Code — you want a known-good baseline so any later failure is unambiguously
caused by new work.

    make up             # Postgres + PostGIS
    make ps             # both healthy
    make down

    cd apps/web && pnpm test -- --run && cd ../..

---

## 5. Set up Git

### 5.1 Identify yourself (once per machine)

    git config --global user.name  "Your Name"
    git config --global user.email "you@example.com"
    git config --global init.defaultBranch main
    git config --global pull.rebase true

### 5.2 Initialise the repository

    git init
    git add .
    git commit -m "chore: phase 0 scaffold, tooling, CI, and brand assets"

Before that first commit, confirm nothing sensitive or heavy is staged:

    git status --short
    git ls-files | grep -E '^data/(raw|interim|processed)/' | grep -v .gitkeep

The second command must print nothing. If it prints anything, your data is about
to enter git history, which is very annoying to undo. Stop and fix `.gitignore`.

### 5.3 Install the pre-commit hooks

    make hooks

These run ruff, mypy, and a check that blocks commits under `data/`. They also
block commits directly to `main`, which is intentional — work happens on phase
branches.

### 5.4 Authenticate with GitHub

    gh auth login          # choose HTTPS, authenticate in the browser

SSH keys are an alternative if you prefer:

    ssh-keygen -t ed25519 -C "you@example.com"
    pbcopy < ~/.ssh/id_ed25519.pub      # paste into github.com/settings/keys

### 5.5 Create and configure the remote

    ./scripts/setup-github.sh <your-github-username> Provenance private

That creates the repository, pushes, and sets up labels (`phase:0`–`phase:7`,
`area:*`, `risk:demo-critical`), milestones dated to the build plan, and branch
protection where your plan allows it. Read the script first — it is short, and
you should know what it is about to do to your account.

Verify:

    git remote -v
    gh repo view --web

### 5.6 Tag the baseline

    git tag v0.0.1 -m "Phase 0: repository scaffold and test harness"
    git push --tags

---

## 6. Get the data in place

    cp -R /path/to/green-sentinel-export/*  data/raw/green_sentinel/
    cp -R /path/to/enclod-traffic-bundle/*  data/raw/enclod_traffic/

Nothing here is committed. Confirm:

    git status --short      # should show no data files

Phase 1 will read the real schema off these files rather than assuming one. Do
not edit `schema_assumptions.yaml` by hand first — the whole point is that the
loader observes and reports, and you fill in the nulls from what it found.

---

## 7. Install Claude Code

    npm install -g @anthropic-ai/claude-code

Then, from the repository root:

    cd ~/code/Provenance
    claude

Claude Code reads `CLAUDE.md` automatically at the start of every session, so the
standing rules do not need re-pasting. Confirm it has, by asking it something
cheap like *"what are the standing rules in this repo?"* before you give it real
work.

---

## 8. Before the first prompt — a checklist

- [ ] `make check` passes
- [ ] `make up` brings the database up healthy, `make down` cleans up
- [ ] `pnpm test -- --run` passes in `apps/web`
- [ ] `prov codes list` prints the registry
- [ ] `git log` shows the phase 0 commit, `git remote -v` shows origin
- [ ] `git ls-files | grep data/raw` prints nothing
- [ ] Real data sitting in `data/raw/`
- [ ] Claude Code launched from the repository root and has read `CLAUDE.md`

---

## 9. Running a phase

One phase per **fresh** Claude Code session. Paste the phase prompt from
`provenance-claude-code-build-prompts-v1.1-scaffold-and-brand.md` and let it run to completion.

    git checkout -b phase-1-audit
    # paste the Phase 1 prompt into Claude Code
    # when it finishes:
    make check
    git push -u origin phase-1-audit
    gh pr create --fill
    # merge, then:
    git checkout main && git pull
    git tag v0.1.0 -m "Phase 1: the audit engine"
    git push --tags

If a phase's test gate fails, do not move on. Paste the failure back into the
same session and fix it there. The gates are what make the phase-by-phase
fallback story real rather than aspirational.

---

## Troubleshooting

**`uv: command not found` after installing** — restart the shell, or
`source ~/.zshrc`. uv installs to `~/.local/bin`.

**Docker image pull fails on Apple Silicon** — every image in the compose file
has an arm64 variant. If one does not resolve, check Docker Desktop is running
and you are not behind a proxy that blocks the registry.

**`pnpm: command not found`** — `corepack enable` then reopen the terminal.

**mypy errors on a fresh clone** — you are probably outside the venv. `source
.venv/bin/activate`.

**Pre-commit blocks a commit to main** — that is deliberate. Branch first.

**Coverage gate fails after adding code** — add the tests. Lowering the gate is
not the fix; it is how a project quietly stops being testable in week five.
