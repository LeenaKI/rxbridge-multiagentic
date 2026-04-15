import os
from datetime import datetime, timezone
from google.cloud import firestore
from google.adk.agents import Agent
from google.adk.tools import FunctionTool

# ── Firestore client ─────────────────────────────────────────────
db = firestore.Client(project=os.environ.get("PROJECT_ID"))

# ════════════════════════════════════════════════════════════════
# TOOL FUNCTIONS — called by sub-agents
# ════════════════════════════════════════════════════════════════

def check_low_stock() -> dict:
    """Check all medicines where stock is below reorder level."""
    try:
        items = db.collection("inventory").stream()
        low = []
        for item in items:
            d = item.to_dict()
            if d.get("stock", 0) <= d.get("reorder_level", 10):
                low.append({
                    "medicine_id": item.id,
                    "name": d.get("name"),
                    "stock": d.get("stock"),
                    "reorder_level": d.get("reorder_level"),
                    "supplier": d.get("supplier")
                })
        return {"low_stock_items": low, "count": len(low)}
    except Exception as e:
        return {"error": str(e)}


def get_medicine_details(medicine_name: str) -> dict:
    """Get details of a specific medicine from inventory."""
    try:
        results = db.collection("inventory")\
            .where("name", "==", medicine_name).stream()
        items = [{"id": d.id, **d.to_dict()} for d in results]
        if not items:
            return {"found": False, "message": f"{medicine_name} not found"}
        return {"found": True, "medicine": items[0]}
    except Exception as e:
        return {"error": str(e)}


def update_stock(medicine_id: str, new_stock: int) -> dict:
    """Update stock level for a medicine after reorder received."""
    try:
        db.collection("inventory").document(medicine_id).update({
            "stock": new_stock,
            "last_updated": datetime.now(timezone.utc).isoformat()
        })
        return {"updated": True, "medicine_id": medicine_id, "new_stock": new_stock}
    except Exception as e:
        return {"error": str(e)}


def get_missed_pickups() -> dict:
    """Find prescriptions filled but not picked up after 2+ days."""
    try:
        all_rx = db.collection("prescriptions")\
            .where("status", "==", "filled").stream()
        missed = []
        now = datetime.now(timezone.utc)
        for rx in all_rx:
            d = rx.to_dict()
            filled_date = d.get("filled_date")
            if filled_date:
                if isinstance(filled_date, str):
                    filled_dt = datetime.fromisoformat(filled_date)
                    if filled_dt.tzinfo is None:
                        filled_dt = filled_dt.replace(tzinfo=timezone.utc)
                else:
                    filled_dt = filled_date
                days_waiting = (now - filled_dt).days
                if days_waiting >= 2:
                    missed.append({
                        "rx_id": rx.id,
                        "patient_id": d.get("patient_id"),
                        "patient_name": d.get("patient_name"),
                        "patient_email": d.get("patient_email"),
                        "medicine": d.get("medicine"),
                        "days_waiting": days_waiting,
                        "is_critical": d.get("is_critical", False)
                    })
        return {"missed_pickups": missed, "count": len(missed)}
    except Exception as e:
        return {"error": str(e)}


def get_patient_medications(patient_id: str) -> dict:
    """Get current medications for a patient to check interactions."""
    try:
        doc = db.collection("patients").document(patient_id).get()
        if not doc.exists:
            return {"found": False, "message": f"Patient {patient_id} not found"}
        d = doc.to_dict()
        return {
            "found": True,
            "patient_name": d.get("name"),
            "current_medications": d.get("medications", []),
            "allergies": d.get("allergies", [])
        }
    except Exception as e:
        return {"error": str(e)}


# ── IMPROVED: Expanded drug interaction dictionary ────────────────
def check_drug_interaction(medicine_1: str, medicine_2: str) -> dict:
    """Check if two medicines have a known interaction."""
    known_interactions = {
        # Blood thinners
        ("warfarin", "aspirin"):            "HIGH RISK: Increased bleeding risk",
        ("aspirin", "warfarin"):            "HIGH RISK: Increased bleeding risk",
        ("warfarin", "ibuprofen"):          "HIGH RISK: Increased bleeding risk",
        ("ibuprofen", "warfarin"):          "HIGH RISK: Increased bleeding risk",
        ("warfarin", "amoxicillin"):        "MODERATE: Antibiotic may potentiate warfarin effect",
        ("amoxicillin", "warfarin"):        "MODERATE: Antibiotic may potentiate warfarin effect",

        # Diabetes
        ("metformin", "alcohol"):           "MODERATE: Risk of lactic acidosis",
        ("alcohol", "metformin"):           "MODERATE: Risk of lactic acidosis",
        ("metformin", "ibuprofen"):         "MODERATE: NSAIDs may reduce metformin efficacy",
        ("ibuprofen", "metformin"):         "MODERATE: NSAIDs may reduce metformin efficacy",
        ("insulin glargine", "alcohol"):    "HIGH RISK: Alcohol can mask hypoglycemia symptoms",
        ("alcohol", "insulin glargine"):    "HIGH RISK: Alcohol can mask hypoglycemia symptoms",

        # Hypertension
        ("lisinopril", "potassium"):        "MODERATE: Risk of hyperkalemia",
        ("potassium", "lisinopril"):        "MODERATE: Risk of hyperkalemia",
        ("lisinopril", "ibuprofen"):        "MODERATE: NSAIDs reduce ACE inhibitor effectiveness",
        ("ibuprofen", "lisinopril"):        "MODERATE: NSAIDs reduce ACE inhibitor effectiveness",
        ("amlodipine", "simvastatin"):      "MODERATE: Amlodipine increases simvastatin exposure",
        ("simvastatin", "amlodipine"):      "MODERATE: Amlodipine increases simvastatin exposure",

        # Cholesterol
        ("simvastatin", "amiodarone"):      "HIGH RISK: Risk of myopathy and rhabdomyolysis",
        ("amiodarone", "simvastatin"):      "HIGH RISK: Risk of myopathy and rhabdomyolysis",
        ("simvastatin", "erythromycin"):    "HIGH RISK: Risk of myopathy",
        ("erythromycin", "simvastatin"):    "HIGH RISK: Risk of myopathy",

        # Antibiotics
        ("amoxicillin", "methotrexate"):    "HIGH RISK: Amoxicillin reduces methotrexate clearance",
        ("methotrexate", "amoxicillin"):    "HIGH RISK: Amoxicillin reduces methotrexate clearance",

        # Psychiatric
        ("ssri", "maoi"):                   "CRITICAL: Serotonin syndrome risk — life threatening",
        ("maoi", "ssri"):                   "CRITICAL: Serotonin syndrome risk — life threatening",
        ("ssri", "tramadol"):               "HIGH RISK: Risk of serotonin syndrome",
        ("tramadol", "ssri"):               "HIGH RISK: Risk of serotonin syndrome",

        # Aspirin combinations
        ("aspirin", "ibuprofen"):           "MODERATE: Ibuprofen may reduce aspirin's cardioprotective effect",
        ("ibuprofen", "aspirin"):           "MODERATE: Ibuprofen may reduce aspirin's cardioprotective effect",
    }
    key = (medicine_1.lower(), medicine_2.lower())
    if key in known_interactions:
        severity_label = known_interactions[key].split(":")[0]
        return {
            "interaction_found": True,
            "severity": known_interactions[key],
            "severity_label": severity_label,
            "medicine_1": medicine_1,
            "medicine_2": medicine_2
        }
    return {
        "interaction_found": False,
        "severity_label": "NONE",
        "message": f"No known interaction between {medicine_1} and {medicine_2}"
    }


def log_prescription(patient_id: str, medicine: str,
                     patient_name: str, patient_email: str,
                     is_critical: bool = False) -> dict:
    """Log a new prescription as filled and waiting for pickup."""
    try:
        rx_data = {
            "patient_id": patient_id,
            "patient_name": patient_name,
            "patient_email": patient_email,
            "medicine": medicine,
            "status": "filled",
            "is_critical": is_critical,
            "filled_date": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        ref = db.collection("prescriptions").add(rx_data)
        return {"logged": True, "rx_id": ref[1].id, "medicine": medicine}
    except Exception as e:
        return {"error": str(e)}


def mark_prescription_collected(rx_id: str) -> dict:
    """Mark a prescription as collected by the patient."""
    try:
        db.collection("prescriptions").document(rx_id).update({
            "status": "collected",
            "collected_at": datetime.now(timezone.utc).isoformat()
        })
        return {"updated": True, "rx_id": rx_id, "status": "collected"}
    except Exception as e:
        return {"error": str(e)}


def get_supplier_list() -> dict:
    """Get all registered suppliers for reordering."""
    try:
        suppliers = db.collection("suppliers").stream()
        result = [{"id": s.id, **s.to_dict()} for s in suppliers]
        return {"suppliers": result, "count": len(result)}
    except Exception as e:
        return {"error": str(e)}


def draft_reorder_request(medicine_name: str, quantity: int,
                          supplier_name: str, supplier_email: str) -> dict:
    """Draft a reorder request and log it to Firestore."""
    try:
        draft = {
            "type": "reorder_request",
            "medicine": medicine_name,
            "quantity_requested": quantity,
            "supplier_name": supplier_name,
            "supplier_email": supplier_email,
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "draft_email_subject": f"Urgent Reorder Request: {medicine_name}",
            "draft_email_body": (
                f"Dear {supplier_name},\n\n"
                f"We urgently require {quantity} units of {medicine_name}.\n"
                f"Please confirm availability and expected delivery date.\n\n"
                f"RxBridge Pharmacy System\n"
                f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
            )
        }
        ref = db.collection("reorder_requests").add(draft)
        return {
            "drafted": True,
            "request_id": ref[1].id,
            "email_subject": draft["draft_email_subject"],
            "email_body": draft["draft_email_body"],
            "message": f"Reorder request drafted and saved. Send to {supplier_email}"
        }
    except Exception as e:
        return {"error": str(e)}


# ── NEW: View pending reorder requests ───────────────────────────
def get_pending_reorders() -> dict:
    """Get all reorder requests that have been drafted but not yet sent."""
    try:
        reorders = db.collection("reorder_requests")\
            .where("status", "==", "draft").stream()
        result = []
        for r in reorders:
            d = r.to_dict()
            result.append({
                "request_id": r.id,
                "medicine": d.get("medicine"),
                "quantity_requested": d.get("quantity_requested"),
                "supplier_name": d.get("supplier_name"),
                "supplier_email": d.get("supplier_email"),
                "created_at": d.get("created_at"),
                "email_subject": d.get("draft_email_subject"),
            })
        return {"pending_reorders": result, "count": len(result)}
    except Exception as e:
        return {"error": str(e)}


# ── NEW: Send patient pickup reminder (logged to Firestore) ──────
def send_pickup_reminder(patient_name: str, patient_email: str,
                         medicine: str, days_waiting: int,
                         rx_id: str) -> dict:
    """Log a pickup reminder for a patient with missed prescription."""
    try:
        urgency = "URGENT" if days_waiting >= 5 else "REMINDER"
        reminder = {
            "type": "pickup_reminder",
            "patient_name": patient_name,
            "patient_email": patient_email,
            "medicine": medicine,
            "days_waiting": days_waiting,
            "urgency": urgency,
            "rx_id": rx_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "message_subject": f"{urgency}: Please collect your prescription — {medicine}",
            "message_body": (
                f"Dear {patient_name},\n\n"
                f"This is a {'urgent ' if urgency == 'URGENT' else ''}reminder that your prescription "
                f"for {medicine} has been ready for {days_waiting} day(s) and is awaiting collection.\n\n"
                f"Please visit the pharmacy at your earliest convenience.\n"
                f"{'⚠️ This is a critical medication. Please collect it as soon as possible.' if days_waiting >= 3 else ''}\n\n"
                f"RxBridge Pharmacy System"
            )
        }
        ref = db.collection("reminders").add(reminder)
        return {
            "sent": True,
            "reminder_id": ref[1].id,
            "urgency": urgency,
            "patient_name": patient_name,
            "message_subject": reminder["message_subject"],
            "message_body": reminder["message_body"],
            "message": f"{urgency} reminder logged for {patient_name} regarding {medicine}"
        }
    except Exception as e:
        return {"error": str(e)}


# ════════════════════════════════════════════════════════════════
# SUB-AGENTS
# ════════════════════════════════════════════════════════════════

inventory_agent = Agent(
    name="inventory_agent",
    model="gemini-2.5-flash",
    description="Manages pharmacy inventory. Checks stock levels, identifies low-stock medicines, updates stock after deliveries, and drafts supplier reorder requests.",
    instruction="""You are the Inventory Agent for RxBridge rural pharmacy assistant.

Your responsibilities:
1. Check which medicines are running low (stock at or below reorder level)
2. Get details of specific medicines when asked
3. Update stock levels when new deliveries arrive
4. Draft reorder requests to suppliers when stock is critical
5. Retrieve supplier contact information
6. Show pending reorder requests that are still in draft status

Always be specific: name the medicines, state exact stock levels, and suggest reorder quantities (typically 3x current stock level).
When drafting reorders, use the draft_reorder_request tool to log it to the system.
""",
    tools=[
        FunctionTool(check_low_stock),
        FunctionTool(get_medicine_details),
        FunctionTool(update_stock),
        FunctionTool(get_supplier_list),
        FunctionTool(draft_reorder_request),
        FunctionTool(get_pending_reorders),      # NEW
    ]
)

patient_agent = Agent(
    name="patient_agent",
    model="gemini-2.5-flash",
    description="Manages patient prescriptions and pickup reminders. Detects missed pickups, sends reminders, and escalates critical medication cases.",
    instruction="""You are the Patient Agent for RxBridge rural pharmacy assistant.

Your responsibilities:
1. Find prescriptions that have not been picked up after 2+ days
2. Identify which missed pickups involve critical medications (diabetes, heart, hypertension)
3. Get patient medication history to provide context
4. Mark prescriptions as collected when patients arrive
5. Log new prescriptions into the system
6. Send pickup reminders to patients with missed prescriptions

For missed pickups:
- Flag as URGENT if is_critical=True or days_waiting >= 5
- Always provide patient name, medicine name, and days waiting
- Suggest contacting the prescribing doctor for critical cases >= 3 days
- Always use send_pickup_reminder tool to log a reminder for every missed pickup

Be concise and action-oriented — pharmacists are busy.
""",
    tools=[
        FunctionTool(get_missed_pickups),
        FunctionTool(get_patient_medications),
        FunctionTool(log_prescription),
        FunctionTool(mark_prescription_collected),
        FunctionTool(send_pickup_reminder),      # NEW
    ]
)

compliance_agent = Agent(
    name="compliance_agent",
    model="gemini-2.5-flash",
    description="Checks drug interactions and compliance. Validates new prescriptions against patient's existing medications and flags safety concerns.",
    instruction="""You are the Compliance Agent for RxBridge rural pharmacy assistant.

Your responsibilities:
1. Check drug interactions between a new prescription and patient's current medications
2. Retrieve patient's full medication list before dispensing
3. Flag allergies and contraindications
4. Generate compliance summaries for audit purposes

For every interaction check:
- State the severity clearly: CRITICAL / HIGH RISK / MODERATE / NONE
- Explain what the risk is in plain language
- Recommend action: HOLD prescription, consult doctor, or safe to proceed

When checking a patient's new prescription:
- First get their current medications using get_patient_medications
- Then check the new medicine against EACH of their current medications using check_drug_interaction
- Report ALL interactions found, not just the first one

Patient safety is your top priority. When in doubt, flag it.
""",
    tools=[
        FunctionTool(get_patient_medications),
        FunctionTool(check_drug_interaction),
    ]
)

supplier_agent = Agent(
    name="supplier_agent",
    model="gemini-2.5-flash",
    description="Handles supplier communications and reorder management. Drafts reorder emails, tracks supplier information, and shows pending reorders.",
    instruction="""You are the Supplier Agent for RxBridge rural pharmacy assistant.

Your responsibilities:
1. Retrieve the list of registered suppliers
2. Draft reorder request emails for low-stock medicines
3. Log reorder requests to the system for tracking
4. Match medicines to their correct suppliers
5. Show all pending reorder requests that haven't been sent yet

When drafting reorders:
- Always specify exact quantity needed
- Use professional but direct language
- Include urgency level based on current stock
- Log every request using draft_reorder_request tool

Output the complete draft email text so the pharmacist can review and send it.
""",
    tools=[
        FunctionTool(get_supplier_list),
        FunctionTool(draft_reorder_request),
        FunctionTool(check_low_stock),
        FunctionTool(get_pending_reorders),      # NEW
    ]
)

# ════════════════════════════════════════════════════════════════
# PRIMARY ORCHESTRATOR AGENT
# ════════════════════════════════════════════════════════════════

root_agent = Agent(
    name="rxbridge_orchestrator",
    model="gemini-2.5-flash",
    description="Primary orchestrator for RxBridge — a multi-agent AI assistant for rural pharmacies. Coordinates inventory, patient, compliance, and supplier agents to handle complex pharmacy workflows.",
    instruction="""You are RxBridge, an AI assistant built specifically for independent rural pharmacies.
You coordinate a team of specialised agents to help pharmacists manage their daily operations.

Your sub-agents:
- inventory_agent: stock levels, reorder lists, medicine details, pending reorders
- patient_agent: missed pickups, pickup reminders, prescription logging, patient records
- compliance_agent: drug interaction checks, patient medication history
- supplier_agent: reorder drafts, supplier contacts, pending reorders

How to handle requests:

INVENTORY questions ("what's low?", "do we have X?", "update stock", "pending reorders"):
→ Route to inventory_agent

PATIENT questions ("who hasn't collected?", "missed pickups", "log prescription", "send reminder"):
→ Route to patient_agent

COMPLIANCE questions ("is it safe to give X with Y?", "check interactions", "patient allergies"):
→ Route to compliance_agent

SUPPLIER questions ("draft reorder", "contact supplier", "send order", "show pending reorders"):
→ Route to supplier_agent

COMPLEX workflows (e.g. "full stock check and draft reorders for everything low"):
→ Use inventory_agent first, then supplier_agent with those results

MISSED PICKUP CASCADE (most important workflow):
When asked to run the missed pickup check:
1. Use patient_agent to get all missed pickups
2. patient_agent will automatically log reminders for each missed pickup
3. For any critical medications (is_critical=True or days_waiting >= 3):
   - Use compliance_agent to check their medication context
   - Flag for doctor notification
4. Summarise: total missed, critical cases, reminders sent, recommended actions

Always give a clear, structured summary at the end.
Pharmacists are busy — be direct, specific, and actionable.
Start every response by stating what you found and what actions were taken.
""",
    sub_agents=[
        inventory_agent,
        patient_agent,
        compliance_agent,
        supplier_agent,
    ]
)