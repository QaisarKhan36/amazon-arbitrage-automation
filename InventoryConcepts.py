from collections import defaultdict
import math

# ---------- SAFE PARSERS ----------
def _to_int(x, default=0):
    try:
        v = str(x).strip()
        if v == "":
            return default
        return int(float(v))
    except:
        return default

def _to_float(x, default=0.0):
    try:
        v = str(x).strip()
        if v == "":
            return default
        return float(v)
    except:
        return default

# ---------- FIFO COST CALCULATION ----------
def calculate_fifo_cost(purchases, shipped_units):
    cost = 0.0
    remaining = shipped_units
    for price, qty in purchases:
        if remaining <= 0:
            break
        use = min(qty, remaining)
        cost += use * price
        remaining -= use
    return cost

# ---------- DATA EXTRACTION ----------
def extract_purchase_data(ws):
    """
    Columns: Name | Asin | Amazon Link | Cost/unit | Units | Total Cost | Tracking | Bought from | Update
    Only count rows with Update='Delivered'
    """
    asin_data = defaultdict(lambda: {'name': '', 'units': 0, 'purchases': []})
    rows = ws.get_all_values()
    if not rows:
        return asin_data

    headers = rows[0]
    update_col_idx = headers.index("Update") if "Update" in headers else -1

    for row in rows[1:]:
        try:
            asin = (row[1] if len(row) > 1 else "").strip()
            if not asin:
                continue
            is_delivered = (row[update_col_idx].strip().lower() == "delivered") if update_col_idx >= 0 else True
            if not is_delivered:
                continue

            name = (row[0] if len(row) > 0 else "").strip()
            cost = _to_float(row[3] if len(row) > 3 else 0.0)
            units = _to_int(row[4] if len(row) > 4 else 0)
            if units > 0:
                asin_data[asin]['name'] = asin_data[asin]['name'] or name
                asin_data[asin]['units'] += units
                asin_data[asin]['purchases'].append((cost, units))
        except:
            continue

    return asin_data

def extract_shipped_units(ws):
    """
    Reads SHIPPED sheet.
    ASIN: col 5 (F)
    QTY per order: col 28 (AB, 1-based)
    PACK: col 29 (AC, 1-based)
    """
    asin_units = defaultdict(int)
    rows = ws.get_all_values()
    if not rows:
        return asin_units

    for row in rows[1:]:
        try:
            asin = (row[5] if len(row) > 5 else "").strip()
            if not asin:
                continue
            qty_per_order = _to_int(row[27] if len(row) > 27 else 0)  # AB
            pack_size = _to_int(row[29] if len(row) > 29 else 1)     # AC
            asin_units[asin] += qty_per_order * pack_size
        except:
            continue

    return asin_units

# ---------- COST ADJUSTMENT ----------
def adjusted_cost_logic(available_required, data, borrowed_cost_to_partner_a, borrowed_cost_to_partner_b):
    partner_a_effective_units = data['partner_a_shipped'] - max(0, -available_required) if data['partner_a_shipped'] > 0 else 0
    partner_b_effective_units = data['partner_b_shipped'] - max(0, -available_required) if data['partner_b_shipped'] > 0 else 0

    partner_a_total_cost = calculate_fifo_cost(data['partner_a_purchases'], partner_a_effective_units)
    partner_b_total_cost = calculate_fifo_cost(data['partner_b_purchases'], partner_b_effective_units)

    partner_a_cost_avg = round((partner_a_total_cost + borrowed_cost_to_partner_a) / partner_a_effective_units, 2) if partner_a_effective_units > 0 else 0.0
    partner_b_cost_avg = round((partner_b_total_cost + borrowed_cost_to_partner_b) / partner_b_effective_units, 2) if partner_b_effective_units > 0 else 0.0

    return partner_a_cost_avg, partner_b_cost_avg

# ---------- INVENTORY COMPILATION ----------
def update_inventory_instock(sheet, compiled):
    values = []

    for asin, data in compiled.items():
        total_units = data['partner_a_units'] + data['partner_b_units']
        total_shipped = data['partner_a_shipped'] + data['partner_b_shipped']
        available_required = total_units - total_shipped

                # Differences: how much stock each has after their shipments
        partner_a_diff = data['partner_a_units'] - data['partner_a_shipped']
        partner_b_diff = data['partner_b_units'] - data['partner_b_shipped']

        # Borrowed units and costs
        partner_b_from_partner_a = 0   # Col I
        partner_a_from_partner_b = 0   # Col J
        borrowed_cost_to_partner_b = 0.0  # Col M
        borrowed_cost_to_partner_a = 0.0  # Col N

        # Case 1: PartnerA shipped more than he had → borrowed from PartnerB
        if partner_a_diff < 0 and partner_b_diff > 0:
            borrow = min(abs(partner_a_diff), partner_b_diff)
            partner_a_from_partner_b = borrow
            borrowed_cost_to_partner_a = calculate_fifo_cost(data['partner_b_purchases'], borrow)

        # Case 2: PartnerB shipped more than he had → borrowed from PartnerA
        elif partner_b_diff < 0 and partner_a_diff > 0:
            borrow = min(abs(partner_b_diff), partner_a_diff)
            partner_b_from_partner_a = borrow
            borrowed_cost_to_partner_b = calculate_fifo_cost(data['partner_a_purchases'], borrow)


        partner_a_cost_avg, partner_b_cost_avg = adjusted_cost_logic(
            available_required, data, borrowed_cost_to_partner_a, borrowed_cost_to_partner_b
        )

        row = [
            data['name'], asin, total_units,
            data['partner_a_units'], data['partner_b_units'],
            data['partner_a_shipped'], data['partner_b_shipped'],
            available_required, partner_b_from_partner_a, partner_a_from_partner_b,
            partner_a_cost_avg, partner_b_cost_avg,
            round(borrowed_cost_to_partner_b, 2), round(borrowed_cost_to_partner_a, 2)
        ]
        values.append(row)

    num_existing_rows = len(sheet.get_all_values())
    if num_existing_rows > 1:
        sheet.batch_clear([f"A2:N{num_existing_rows}"])

    if values:
        sheet.update("A2", values)
        print(f"[DONE] InventoryInStock updated with {len(values)} rows.")
    else:
        print("[WARNING] No rows to update in InventoryInStock.")

# ---------- GET NAMES FROM 2STEP INVENTORY ----------
def populate_names_from_2step(gc, instock_ws, partner_a_sheet_id, partner_b_sheet_id):
    """
    Fill InventoryInStock!A (Name) based on ASIN.
    Priority:
      1. Name already present in InventoryInStock
      2. Name from 2StepInventory (PartnerA or PartnerB)
      3. Fallback: SHIPPED sheet if needed
    """
    instock_rows = instock_ws.get_all_values()
    if len(instock_rows) < 2:
        return

    def build_asin_name_map(sheet_id, sheet_name="2StepInventory"):
        """Map ASIN → Name from 2StepInventory"""
        ws = gc.open_by_key(sheet_id).worksheet(sheet_name)
        rows = ws.get_all_values()
        asin_name = {}
        for r in rows[1:]:
            try:
                asin = (r[2] if len(r) > 2 else "").strip()  # col C = ASIN
                name = (r[0] if len(r) > 0 else "").strip()  # col A = Name
                if asin and name:
                    asin_name[asin] = name
            except:
                continue
        return asin_name

    partner_a_map = build_asin_name_map(partner_a_sheet_id)
    partner_b_map = build_asin_name_map(partner_b_sheet_id)

    updates = []
    for idx, row in enumerate(instock_rows[1:], start=2):
        asin = (row[1] if len(row) > 1 else "").strip()  # col B = ASIN
        current_name = (row[0] if len(row) > 0 else "").strip()
        if not asin:
            continue

        # Priority: keep existing, else PartnerA, else PartnerB
        name = current_name or partner_a_map.get(asin) or partner_b_map.get(asin)

        if name and name != current_name:
            updates.append({'range': f"A{idx}", 'values': [[name]]})

    if updates:
        instock_ws.batch_update(updates)
        print(f"[DONE] Updated {len(updates)} names in InventoryInStock")
    else:
        print("[INFO] No missing names in InventoryInStock")


    
# ---------- COMPILE INVENTORY DATA ----------
def compile_inventory_data(gc):
    INVENTORY_SPREADSHEET_ID = 'YOUR_INVENTORY_SHEET_ID'
    PARTNER_A_INVENTORY_SHEET_NAME = 'PartnerAPurchase'
    PARTNER_B_INVENTORY_SHEET_NAME = 'PartnerBPurchase'
    INVENTORY_INSTOCK_SHEET_NAME = 'InventoryInStock'
    PARTNER_A_2STEP_SPREADSHEET_ID = 'YOUR_PARTNER_A_ORDERS_SHEET_ID'
    PARTNER_B_2STEP_SPREADSHEET_ID = 'YOUR_PARTNER_B_ORDERS_SHEET_ID'
    SHIPPED_SHEET_NAME = 'SHIPPED'

    inventory_doc = gc.open_by_key(INVENTORY_SPREADSHEET_ID)
    partner_a_purchase_ws = inventory_doc.worksheet(PARTNER_A_INVENTORY_SHEET_NAME)
    partner_b_purchase_ws = inventory_doc.worksheet(PARTNER_B_INVENTORY_SHEET_NAME)
    instock_ws = inventory_doc.worksheet(INVENTORY_INSTOCK_SHEET_NAME)

    partner_a_shipped_ws = gc.open_by_key(PARTNER_A_2STEP_SPREADSHEET_ID).worksheet(SHIPPED_SHEET_NAME)
    partner_b_shipped_ws = gc.open_by_key(PARTNER_B_2STEP_SPREADSHEET_ID).worksheet(SHIPPED_SHEET_NAME)

    # Delivered filter only for purchases
    partner_a_data = extract_purchase_data(partner_a_purchase_ws)
    partner_b_data = extract_purchase_data(partner_b_purchase_ws)

    # Shipped counts all rows
    partner_a_shipped = extract_shipped_units(partner_a_shipped_ws)
    partner_b_shipped = extract_shipped_units(partner_b_shipped_ws)

    all_asins = set(partner_a_shipped.keys()) | set(partner_b_shipped.keys()) | set(partner_a_data.keys()) | set(partner_b_data.keys())

    compiled = {}
    for asin in all_asins:
        jd = partner_a_data.get(asin, {})
        md = partner_b_data.get(asin, {})

        compiled[asin] = {
            'name': (jd.get('name') or md.get('name') or ''),
            'partner_a_units': jd.get('units', 0),
            'partner_b_units': md.get('units', 0),
            'partner_a_shipped': partner_a_shipped.get(asin, 0),
            'partner_b_shipped': partner_b_shipped.get(asin, 0),
            'partner_a_purchases': jd.get('purchases', []),
            'partner_b_purchases': md.get('purchases', []),
        }

    update_inventory_instock(instock_ws, compiled)

    # Update names from 2StepInventory for matching ASINs
    populate_names_from_2step(gc, instock_ws, PARTNER_A_2STEP_SPREADSHEET_ID, PARTNER_B_2STEP_SPREADSHEET_ID)

# ---------- SHIPPED COST UPDATING ----------
def update_shipped_cost_column(gc):
    """
    Pull per-ASIN avg cost from InventoryInStock (PartnerA: col 11, PartnerB: col 12)
    and write Final Shipping+Prep Cost into SHIPPED!J for both spreadsheets.
    """
    INVENTORY_SPREADSHEET_ID = 'YOUR_INVENTORY_SHEET_ID'
    INVENTORY_INSTOCK_SHEET_NAME = 'InventoryInStock'
    PARTNER_A_2STEP_SPREADSHEET_ID = 'YOUR_PARTNER_A_ORDERS_SHEET_ID'
    PARTNER_B_2STEP_SPREADSHEET_ID = 'YOUR_PARTNER_B_ORDERS_SHEET_ID'
    SHIPPED_SHEET_NAME = 'SHIPPED'

    instock_ws = gc.open_by_key(INVENTORY_SPREADSHEET_ID).worksheet(INVENTORY_INSTOCK_SHEET_NAME)
    instock_data = instock_ws.get_all_values()
    asin_cost_map = {}

    # Store PartnerA/PartnerB avg costs
    for row in instock_data[1:]:
        try:
            asin = (row[1] if len(row) > 1 else "").strip()
            if not asin:
                continue
            partner_a_cost = _to_float(row[10] if len(row) > 10 else "0")
            partner_b_cost = _to_float(row[11] if len(row) > 11 else "0")
            asin_cost_map[asin] = {'partner_a': partner_a_cost, 'partner_b': partner_b_cost}
        except:
            continue

        def calc_shipping_and_prep(qty, weight):
            """Implements label + prepping fee rules (ignores pack size)"""
            total_packages = qty
            total_weight = qty * weight  # weight per package × qty

            if total_packages <= 0:
                return 0.0

            # Prepping cost: $1.8 per package
            prep_cost = total_packages * 1.8

            # Label cost: 1 label covers up to 8 lbs, each $2.2
            if total_weight <= 0:
                labels_needed = 1  # at least 1 label if something ships
            else:
                labels_needed = math.ceil(total_weight / 8)

            label_cost = labels_needed * 2.2

            return round(label_cost + prep_cost, 2)


    def update_sheet(sheet_id, is_partner_a=True):
        ws = gc.open_by_key(sheet_id).worksheet(SHIPPED_SHEET_NAME)
        rows = ws.get_all_values()
        updates = []

        for idx, row in enumerate(rows[1:], start=2):
            try:
                asin = (row[5] if len(row) > 5 else "").strip()
                if not asin:
                    continue

                qty_per_order = _to_int(row[27] if len(row) > 27 else 1, 1)   # AB
                weight        = _to_float(row[33] if len(row) > 33 else 0.0)  # AH

                final_cost = calc_shipping_and_prep(qty_per_order, weight)

                # Write final numeric cost to column J
                updates.append({'range': f'J{idx}', 'values': [[final_cost]]})
            except Exception as e:
                print(f"[ERROR] Row {idx} in {sheet_id}: {e}")
                continue

        if updates:
            ws.batch_update(updates)
            print(f"[DONE] Updated {len(updates)} rows in SHIPPED ({'PartnerA' if is_partner_a else 'PartnerB'})")

    update_sheet(PARTNER_A_2STEP_SPREADSHEET_ID, is_partner_a=True)
    update_sheet(PARTNER_B_2STEP_SPREADSHEET_ID, is_partner_a=False)