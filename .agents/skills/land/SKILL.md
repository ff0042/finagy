---
name: land
description: Completes post-PR merge cleanup. Switches to main, pulls latest changes, deletes merged local and remote feature branches, and prunes tracking refs. Trigger with /land.
---

# Land Workflow (/land)

When the user triggers `/land` (or asks to complete post-merge cleanup):

## Execution Steps

1. **Switch to Main Branch:**
   - Run `git checkout main`.

2. **Pull Latest Merged Changes:**
   - Run `git pull origin main`.

3. **Identify & Delete Merged Local Branches:**
   - Inspect merged local branches (`git branch --merged main`).
   - Safely delete any feature branches merged into `main` (`git branch -d <branch_name>`). Do not delete `main`.

4. **Delete Merged Remote Branches:**
   - Inspect merged remote branches (`git branch -r --merged origin/main`).
   - Safely delete merged remote feature branches (`git push origin --delete <branch_name>`). Do not delete `main` or active unmerged branches.

5. **Prune Tracking References:**
   - Run `git fetch --prune`.

6. **Verify Environment Health:**
   - Run unit test suite (`uv run pytest` in `backend/`) to confirm `main` is completely healthy.
   - Present a clear summary of pulled changes and cleaned branches.
