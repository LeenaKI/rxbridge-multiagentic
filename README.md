# RxBridge 
### AI-Powered Assistant for Rural Pharmacies

RxBridge is a multi-agent AI system built with **Google ADK** to help independent rural pharmacies manage daily operations — from drug interaction checks to missed prescription alerts and supplier reorder drafting.

> 🔴 **Demo video:** [https:your-cloud-run-url]

---

## 🧠 Architecture

RxBridge uses a **5-agent orchestration pattern** built on Google ADK:

```
User Query
    │
    ▼
rxbridge_orchestrator  ← Root agent, routes tasks
    │
    ├── inventory_agent    → Stock levels, reorder tracking
    ├── patient_agent      → Missed pickups, reminders
    ├── compliance_agent   → Drug interactions, allergies
    └── supplier_agent     → Reorder drafts, supplier contacts
```

Each agent has its own tools and instructions. The orchestrator decides which agent handles each request — or chains multiple agents for complex workflows.

---

## ✨ Features

- **Drug Interaction Detection** — Checks new prescriptions against a patient's current medications with severity levels: `CRITICAL / HIGH RISK / MODERATE / NONE`
- **Missed Pickup Alerts** — Flags prescriptions filled but not collected after 2+ days, with `URGENT` escalation for critical medications
- **Automated Patient Reminders** — Logs pickup reminder messages to Firestore for pharmacist review
- **Supplier Reorder Drafting** — Auto-drafts reorder request emails for low-stock medicines, logged to Firestore
- **Inventory Management** — Real-time stock level checks against reorder thresholds
- **Prescription Logging** — Log new prescriptions and mark them as collected

---

## 🗂️ Project Structure

```
rxbridge/
├── agent.py          # All agents, tools, and orchestrator
├── seed_db.py        # Firestore seed data (medicines, patients, prescriptions, suppliers)
├── .env              # Environment variables (edit with your Google credentials)
└── requirements.txt  # Python dependencies
```

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.10+
- Google Cloud project with Firestore enabled
- Google ADK installed
- GCP credentials configured

### 1. Clone the repo
```bash
git clone https://github.com/yourusername/rxbridge.git
cd rxbridge
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set environment variables
Create a `.env` file in the root:
```env
PROJECT_ID=your-gcp-project-id
MODEL=gemini-2.5-flash
```

### 4. Seed the database
```bash
python seed_db.py
```
This creates 4 Firestore collections:
- `inventory` — 9 medicines, 5 low stock
- `patients` — 5 patients with medications and allergies
- `prescriptions` — 6 prescriptions including missed pickups and edge cases
- `suppliers` — 3 suppliers with contact details

### 5. Run the agent
```bash
adk run agent.py
```

---

## 🧪 Test Cases

Use these prompts to test the live deployment:

| # | Prompt | Expected Response |
|---|--------|-------------------|
| 1 | *"What medicines are low on stock?"* | Lists 5 low-stock medicines with current vs reorder levels |
| 2 | *"Who hasn't collected their prescription?"* | Lists missed pickups — Mary (5 days, URGENT), Kofi (4 days), James (3 days), Robert (2 days) |
| 3 | *"Is it safe to give Ibuprofen to a patient already on Warfarin?"* | **HIGH RISK** — Increased bleeding risk. Recommend HOLD and consult doctor |
| 4 | *"Check interaction between Aspirin and Metformin"* | No known interaction. Safe to proceed |
| 5 | *"Run a full missed pickup check and flag any critical cases"* | Full summary with critical flags, reminders logged, drug interaction context for Kofi |
| 6 | *"Draft a reorder request for Warfarin"* | Draft email to MedSupply Co logged to Firestore |

---

## 🗄️ Firestore Collections

| Collection | Description |
|---|---|
| `inventory` | Medicine stock levels and reorder thresholds |
| `patients` | Patient profiles, current medications, allergies |
| `prescriptions` | Prescription status and pickup tracking |
| `suppliers` | Supplier contacts and lead times |
| `reorder_requests` | Drafted reorder emails pending pharmacist review |
| `reminders` | Patient pickup reminders logged by the system |

---

## 🛠️ Tech Stack

- **Google ADK** — Multi-agent orchestration
- **Gemini 2.5 Flash** — LLM for all agents
- **GCP Firestore** — NoSQL database
- **GCP Cloud Run** — Deployment
- **Python** — Backend logic

---

## ☁️ Deployment

RxBridge is deployed on **GCP Cloud Run**. To deploy your own instance:

```bash
gcloud run deploy rxbridge \
  --source . \
  --region us-central1 \
  --set-env-vars PROJECT_ID=your-project-id
```
