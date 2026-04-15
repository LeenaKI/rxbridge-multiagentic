import os
from datetime import datetime, timezone, timedelta
from google.cloud import firestore

db = firestore.Client(project=os.environ.get("PROJECT_ID"))

print("Seeding inventory...")
inventory = [
    {"name": "Metformin 500mg",   "stock": 8,  "reorder_level": 20, "supplier": "MedSupply Co", "category": "diabetes"},
    {"name": "Amlodipine 5mg",    "stock": 5,  "reorder_level": 15, "supplier": "PharmaPlus",   "category": "hypertension"},
    {"name": "Warfarin 5mg",      "stock": 3,  "reorder_level": 10, "supplier": "MedSupply Co", "category": "blood_thinner"},
    {"name": "Lisinopril 10mg",   "stock": 25, "reorder_level": 20, "supplier": "PharmaPlus",   "category": "hypertension"},
    {"name": "Aspirin 75mg",      "stock": 50, "reorder_level": 30, "supplier": "LocalMed",     "category": "general"},
    {"name": "Simvastatin 20mg",  "stock": 6,  "reorder_level": 15, "supplier": "MedSupply Co", "category": "cholesterol"},
    {"name": "Amoxicillin 500mg", "stock": 40, "reorder_level": 25, "supplier": "LocalMed",     "category": "antibiotic"},
    {"name": "Insulin Glargine",  "stock": 4,  "reorder_level": 10, "supplier": "PharmaPlus",   "category": "diabetes"},
    {"name": "Ibuprofen 400mg",   "stock": 35, "reorder_level": 20, "supplier": "LocalMed",     "category": "general"},  # NEW — triggers interactions
]
for item in inventory:
    db.collection("inventory").add(item)
print(f"  Added {len(inventory)} medicines")

print("Seeding patients...")
patients = [
    {
        "name": "James Okafor",
        "email": "james.okafor@email.com",
        "phone": "+1-555-0101",
        "medications": ["Metformin 500mg", "Lisinopril 10mg"],
        "allergies": ["Penicillin"],
        "condition": "Type 2 Diabetes, Hypertension"
    },
    {
        "name": "Mary Adeyemi",
        "email": "mary.adeyemi@email.com",
        "phone": "+1-555-0102",
        "medications": ["Warfarin 5mg"],
        "allergies": [],
        "condition": "Atrial Fibrillation"
    },
    {
        "name": "Robert Mensah",
        "email": "robert.mensah@email.com",
        "phone": "+1-555-0103",
        "medications": ["Simvastatin 20mg", "Aspirin 75mg"],
        "allergies": ["Sulfa drugs"],
        "condition": "High Cholesterol, Heart Disease"
    },
    {
        "name": "Fatima Diallo",
        "email": "fatima.diallo@email.com",
        "phone": "+1-555-0104",
        "medications": ["Insulin Glargine", "Metformin 500mg"],
        "allergies": [],
        "condition": "Type 1 Diabetes"
    },
    # NEW — edge case patient: missed pickup + drug interaction risk
    {
        "name": "Kofi Asante",
        "email": "kofi.asante@email.com",
        "phone": "+1-555-0105",
        "medications": ["Warfarin 5mg", "Lisinopril 10mg"],
        "allergies": ["Aspirin"],
        "condition": "Hypertension, Deep Vein Thrombosis"
    },
]
patient_ids = []
for p in patients:
    ref = db.collection("patients").add(p)
    patient_ids.append(ref[1].id)
print(f"  Added {len(patients)} patients")

print("Seeding prescriptions...")
now = datetime.now(timezone.utc)
prescriptions = [
    # Original 3 missed pickups
    {
        "patient_id": patient_ids[0],
        "patient_name": "James Okafor",
        "patient_email": "james.okafor@email.com",
        "medicine": "Metformin 500mg",
        "status": "filled",
        "is_critical": True,
        "filled_date": (now - timedelta(days=3)).isoformat(),
    },
    {
        "patient_id": patient_ids[1],
        "patient_name": "Mary Adeyemi",
        "patient_email": "mary.adeyemi@email.com",
        "medicine": "Warfarin 5mg",
        "status": "filled",
        "is_critical": True,
        "filled_date": (now - timedelta(days=5)).isoformat(),
    },
    {
        "patient_id": patient_ids[2],
        "patient_name": "Robert Mensah",
        "patient_email": "robert.mensah@email.com",
        "medicine": "Simvastatin 20mg",
        "status": "filled",
        "is_critical": False,
        "filled_date": (now - timedelta(days=2)).isoformat(),
    },
    # Already collected — should NOT appear in missed pickups
    {
        "patient_id": patient_ids[3],
        "patient_name": "Fatima Diallo",
        "patient_email": "fatima.diallo@email.com",
        "medicine": "Insulin Glargine",
        "status": "collected",
        "is_critical": True,
        "filled_date": (now - timedelta(days=1)).isoformat(),
    },
    # NEW — Kofi: missed pickup + his allergy to Aspirin + on Warfarin (HIGH RISK combo)
    {
        "patient_id": patient_ids[4],
        "patient_name": "Kofi Asante",
        "patient_email": "kofi.asante@email.com",
        "medicine": "Ibuprofen 400mg",   # interacts with both Warfarin and Lisinopril he is on
        "status": "filled",
        "is_critical": True,
        "filled_date": (now - timedelta(days=4)).isoformat(),
    },
    # NEW — Robert: second missed pickup for Aspirin (to demonstrate multi-interaction cascade)
    {
        "patient_id": patient_ids[2],
        "patient_name": "Robert Mensah",
        "patient_email": "robert.mensah@email.com",
        "medicine": "Aspirin 75mg",
        "status": "filled",
        "is_critical": False,
        "filled_date": (now - timedelta(days=4)).isoformat(),
    },
]
for rx in prescriptions:
    db.collection("prescriptions").add(rx)
print(f"  Added {len(prescriptions)} prescriptions")

print("Seeding suppliers...")
suppliers = [
    {"name": "MedSupply Co", "email": "orders@medsupply.com",  "phone": "+1-555-0200", "lead_days": 3},
    {"name": "PharmaPlus",   "email": "supply@pharmaplus.com", "phone": "+1-555-0201", "lead_days": 2},
    {"name": "LocalMed",     "email": "reorder@localmed.com",  "phone": "+1-555-0202", "lead_days": 1},
]
for s in suppliers:
    db.collection("suppliers").add(s)
print(f"  Added {len(suppliers)} suppliers")

print("\nDone! Firestore collections created:")
print("  - inventory      (9 medicines, 5 low stock)")
print("  - patients       (5 patients, 1 new edge-case patient)")
print("  - prescriptions  (5 missed pickups, 3 critical — includes interaction edge cases)")
print("  - suppliers      (3 suppliers)")
print("\nEdge cases seeded:")
print("  - Kofi Asante: missed Ibuprofen pickup + on Warfarin (HIGH RISK interaction)")
print("  - Robert Mensah: 2 missed pickups (Simvastatin + Aspirin)")
print("  - Mary Adeyemi: 5 days missed Warfarin (most urgent)")