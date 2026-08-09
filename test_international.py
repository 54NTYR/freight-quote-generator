import json
from app import app

client = app.test_client()

sample_payload = {
    "quote_name": "Cartagena International Quote",
    "origin_text": "Jerome, ID",
    "destination_text": "Cartagena, Colombia",
    "quote_notes": "Please review transit times and expedite if needed.",
    "example_pallets": 10,
    "lanes": [
        {
            "id": "Lane A",
            "description": "Jerome → Oakland → Port Oakland → CTG",
            "legs": [
                {"name": "Truck Jerome → Oakland", "costPerPallet": 250},
                {"name": "Transload & Dray to Port (Oakland)", "costPerPallet": 80}
            ],
            "oceanPerPallet": 420,
            "otherFees": 45
        },
        {
            "id": "Lane B",
            "description": "Salt Lake City → Jerome (dray) → Ocean → CTG",
            "legs": [
                {"name": "Dray SLC → Jerome", "costPerPallet": 110},
                {"name": "Return / reposition (if charged)", "costPerPallet": 0}
            ],
            "oceanPerPallet": 480,
            "otherFees": 55
        }
    ]
}

resp = client.post('/international', json=sample_payload)
print('Status code:', resp.status_code)
output_path = 'test_international_output.html'
with open(output_path, 'wb') as f:
    f.write(resp.data)
print('Saved output to', output_path)
