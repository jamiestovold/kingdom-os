# Kingdom -- Design Philosophy

> Ultra-powerful, locally controlled, human-approved, and absurdly cheap to run.

## Six Rules

Rule 1: Local First
If it can run locally, run it locally.
SQLite instead of managed database.
ChromaDB instead of hosted vector store.
React served on VPS not on external hosting.
Local models where quality is sufficient.
Pay for cloud only when local genuinely cannot do it.

Rule 2: Pay Only For Intelligence
Spend money on AI reasoning.
Do not spend money on dashboards, databases, auth systems,
vector stores, monitoring platforms, or workflow tools.
Those are infrastructure problems. Solve them yourself.

Rule 3: Human-In-The-Loop
AI thinks. AI proposes. AI prepares.
Human approves.
No output is ever applied automatically.
No task ever completes without explicit human action.

Rule 4: One VPS
One VPS. One backup destination. One control panel.
No external dependencies that can disappear or change pricing overnight.
Everything lives in /home/kingdom-os.

Rule 5: Buy Reliability, Not Features
Spend extra money on backups, VPS snapshots, or better hardware.
Not on additional services.
Test: does this make Kingdom smarter or just more expensive?
If the second, do not add it.

Rule 6: Backups Are Mandatory
Everything else can be rebuilt. Data cannot.
No feature is complete until it can be restored.
Hourly DB backup. Daily full backup. Weekly snapshot.
Two independent recovery paths. Recovery time under 30 minutes.

## The Approval Principle
AI proposes. Human approves. Always.
That boundary makes Kingdom powerful and safe.

## Growth Path
More capability means bigger VPS, better local model, more disk.
Not more subscriptions.
