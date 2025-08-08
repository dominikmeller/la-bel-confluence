# Confluence Decision Logger

Synchronises a markdown decision log with a Confluence Cloud (or Server/Data Center) page.

---

## 1. What the script does

`confluence_decision_logger.py` reads a local markdown file where each top-level `##` heading represents a decision.  
It extracts:

* **Title** – text of the `##` heading
* **Participants** – people mentioned in `[[Name]]` blocks
* **Description** – body text beneath the heading (minus `[[Name]]` tags)

It then updates an existing Confluence page so that all decisions are displayed in a simple, clean layout:

```html
<h2>Decision title</h2>
<p><strong>Participants:</strong> Alice Smith, Bob Jones</p>
<p>Description of the decision …</p>
<hr/>
```

The script:

1. Connects to Confluence via the Atlassian REST API (using `atlassian-python-api`).
2. Reads the markdown file.
3. Parses new decisions, merges with existing ones on the Confluence page, and updates the page.
4. Prints a sync summary (added / updated / unchanged).

---

## 2. Required environment variables

| Variable | Purpose |
|----------|---------|
| `CONFLUENCE_URL` | Base URL e.g. `https://your-domain.atlassian.net/wiki` |
| `CONFLUENCE_USERNAME` | Atlassian account e-mail |
| `CONFLUENCE_API_TOKEN` | API token generated from <https://id.atlassian.com/manage-profile/security/api-tokens> |
| `DECISION_PAGE_ID` | Numeric content ID of the Confluence page to update |
| `DECISION_SPACE` | Space key (e.g. `ENG`, personal space like `~abc123`) |
| `DECISION_MD_LOCATION` | Absolute/relative path to the markdown file (used when no CLI path is given) |

---

## 3. Sample `.env`

```dotenv
# Confluence credentials
CONFLUENCE_URL=https://your-domain.atlassian.net/wiki
CONFLUENCE_USERNAME=alice@example.com
CONFLUENCE_API_TOKEN=YOUR_API_TOKEN

# Target content
DECISION_PAGE_ID=53215235
DECISION_SPACE=~71202065f1c76ac03e4dabb54293aba6562c63

# Default markdown path
DECISION_MD_LOCATION=/Users/alice/projects/decision-log/decisions.md
```

Place this `.env` file in the project root.  The script loads it automatically via `python-dotenv`.

---

## 4. Sample `decisions.md`

```markdown
# Project Decision Log

---

## Adopt OutSystems Low-Code Platform
[[Sarah Johnson]]

We have decided to standardise on OutSystems as our primary low-code development platform for building healthcare applications.

**Rationale:**
- Speed: Accelerated delivery
- Integration: Excellent AWS integration

---

## Implement Real-Time Patient Monitoring
[[Dr. Michael Chen]] [[Robert Martinez]]

Deploy real-time monitoring capabilities for critical patient metrics using IoT sensors and cloud analytics.

---

## Migrate All Services to AWS
[[Team]]

Move all workloads from on-prem to AWS to improve scalability and compliance.

---
```

---

## 5. Installation

```bash
python -m pip install -r requirements.txt
```

---

## 6. Usage

### Basic
```bash
python confluence_decision_logger.py decisions.md --page-id 53215235
```

### With environment defaults
```bash
# .env contains DECISION_MD_LOCATION and DECISION_PAGE_ID
python confluence_decision_logger.py
```

### Additional options
```
--no-preserve   Remove decisions that only exist in Confluence
--dry-run       Print what would change without updating Confluence
--space-key     Override DECISION_SPACE from CLI
```

---

## 7. Troubleshooting

* **Unknown macro error** – The script now uses only standard HTML; no macro dependencies.
* **Missing variables** – The script prints the names of any missing env vars.
* **Connection errors** – Verify `CONFLUENCE_URL`, credentials, and network.

---

© 2025 Your Company – MIT/Apache 2.0 licence as per repository.
