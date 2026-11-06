import os, re, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

def register_demo_routes(app, db_path):
    bp = Blueprint("nexora_demos", __name__)
    MAX_UPLOAD = 10 * 1024 * 1024

    def connect():
        con = sqlite3.connect(db_path, timeout=20)
        con.execute("PRAGMA busy_timeout=20000")
        con.row_factory = sqlite3.Row
        return con

    def now():
        return datetime.now(timezone.utc).isoformat()

    def init():
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS factory_orders (
                id TEXT PRIMARY KEY, order_no TEXT UNIQUE NOT NULL, product TEXT NOT NULL,
                quantity INTEGER NOT NULL, due_date TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL)""")
            con.execute("""CREATE TABLE IF NOT EXISTS crm_leads (
                id TEXT PRIMARY KEY, company TEXT NOT NULL, contact TEXT NOT NULL,
                email TEXT NOT NULL DEFAULT '', value INTEGER NOT NULL, stage TEXT NOT NULL,
                follow_up TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)""")
            con.execute("""CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, filename TEXT NOT NULL, file_type TEXT NOT NULL,
                extracted_text TEXT NOT NULL, fields_json TEXT NOT NULL,
                status TEXT NOT NULL, created_at TEXT NOT NULL)""")
            if con.execute("SELECT COUNT(*) FROM factory_orders").fetchone()[0] == 0:
                rows = [
                    ("WO-1048","Industrial valve",240,"2026-11-08","In production"),
                    ("WO-1047","Steel coupling",500,"2026-11-08","Quality check"),
                    ("WO-1046","Pump housing",120,"2026-11-09","Queued"),
                    ("WO-1045","Precision shaft",360,"2026-11-07","Completed")]
                for r in rows:
                    con.execute("INSERT INTO factory_orders VALUES(?,?,?,?,?,?,?)",
                        (str(uuid.uuid4()),*r,now()))
            if con.execute("SELECT COUNT(*) FROM crm_leads").fetchone()[0] == 0:
                rows = [
                    ("Aster Components","Riya Shah","riya@example.com",350000,"Proposal","2026-11-10"),
                    ("BluePeak Logistics","Aman Mehta","aman@example.com",240000,"Negotiation","2026-11-09"),
                    ("Vertex Realty","Neel Patel","neel@example.com",180000,"Contacted","2026-11-11"),
                    ("Orbit Industrial","Karan Desai","karan@example.com",425000,"New","2026-11-12")]
                for r in rows:
                    con.execute("INSERT INTO crm_leads VALUES(?,?,?,?,?,?,?,?)",
                        (str(uuid.uuid4()),*r,now()))

    def fail(message, code=400):
        return jsonify({"error": message}), code

    @bp.get("/api/factoryos/orders")
    def orders_list():
        with connect() as con:
            rows = con.execute("SELECT * FROM factory_orders ORDER BY created_at DESC").fetchall()
        return jsonify([dict(r) for r in rows])

    @bp.post("/api/factoryos/orders")
    def orders_create():
        d = request.get_json(silent=True) or {}
        product = str(d.get("product","")).strip()[:120]
        due = str(d.get("due_date","")).strip()[:20]
        try: qty = int(d.get("quantity",0))
        except (TypeError,ValueError): qty = 0
        if not product or not due or qty < 1 or qty > 10000000:
            return fail("Enter a product, valid due date and quantity.")
        try: datetime.strptime(due,"%Y-%m-%d")
        except ValueError: return fail("Due date must use YYYY-MM-DD.")
        with connect() as con:
            order_no = "WO-" + str(1000 + con.execute("SELECT COUNT(*) FROM factory_orders").fetchone()[0] + 1)
            ident = str(uuid.uuid4())
            con.execute("INSERT INTO factory_orders VALUES(?,?,?,?,?,?,?)",
                (ident,order_no,product,qty,due,"Queued",now()))
            row = con.execute("SELECT * FROM factory_orders WHERE id=?",(ident,)).fetchone()
        return jsonify(dict(row)),201

    @bp.patch("/api/factoryos/orders/<ident>")
    def orders_update(ident):
        d = request.get_json(silent=True) or {}
        status = d.get("status")
        if status not in {"Queued","In production","Quality check","Completed"}:
            return fail("Invalid work-order status.")
        with connect() as con:
            cur = con.execute("UPDATE factory_orders SET status=? WHERE id=?",(status,ident))
            if not cur.rowcount: return fail("Work order not found.",404)
            row = con.execute("SELECT * FROM factory_orders WHERE id=?",(ident,)).fetchone()
        return jsonify(dict(row))

    @bp.get("/api/clientflow/leads")
    def leads_list():
        with connect() as con:
            rows = con.execute("SELECT * FROM crm_leads ORDER BY created_at DESC").fetchall()
        return jsonify([dict(r) for r in rows])

    @bp.post("/api/clientflow/leads")
    def leads_create():
        d = request.get_json(silent=True) or {}
        company = str(d.get("company","")).strip()[:120]
        contact = str(d.get("contact","")).strip()[:100]
        email = str(d.get("email","")).strip()[:254]
        follow = str(d.get("follow_up","")).strip()[:20]
        try: value = int(d.get("value",0))
        except (TypeError,ValueError): value = -1
        if not company or not contact or value < 0 or value > 100000000000:
            return fail("Enter a company, contact and valid deal value.")
        if email and ("@" not in email or len(email.split("@")[-1]) < 3):
            return fail("Enter a valid email address.")
        if follow:
            try: datetime.strptime(follow,"%Y-%m-%d")
            except ValueError: return fail("Follow-up date must use YYYY-MM-DD.")
        ident = str(uuid.uuid4())
        with connect() as con:
            con.execute("INSERT INTO crm_leads VALUES(?,?,?,?,?,?,?,?)",
                (ident,company,contact,email,value,"New",follow,now()))
            row = con.execute("SELECT * FROM crm_leads WHERE id=?",(ident,)).fetchone()
        return jsonify(dict(row)),201

    @bp.patch("/api/clientflow/leads/<ident>")
    def leads_update(ident):
        d = request.get_json(silent=True) or {}
        stage = d.get("stage")
        follow = str(d.get("follow_up","")).strip()[:20]
        if stage not in {"New","Contacted","Proposal","Negotiation","Won","Lost"}:
            return fail("Invalid pipeline stage.")
        if follow:
            try: datetime.strptime(follow,"%Y-%m-%d")
            except ValueError: return fail("Follow-up date must use YYYY-MM-DD.")
        with connect() as con:
            cur = con.execute("UPDATE crm_leads SET stage=?,follow_up=? WHERE id=?",(stage,follow,ident))
            if not cur.rowcount: return fail("Lead not found.",404)
            row = con.execute("SELECT * FROM crm_leads WHERE id=?",(ident,)).fetchone()
        return jsonify(dict(row))

    def extract_fields(text):
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        invoice = re.search(r"(?i)(?:invoice\s*(?:no|number|#)?|inv\s*#?)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/]{2,})",text)
        date = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b",text)
        amount = re.search(r"(?i)(?:grand\s*total|total\s*(?:amount|due)?|amount\s*payable)\s*[:\-]?\s*(?:INR|Rs\.?|₹)?\s*([0-9,]+(?:\.\d{1,2})?)",text)
        supplier = lines[0][:120] if lines else ""
        return {"supplier":supplier,"invoice_number":invoice.group(1) if invoice else "",
                "invoice_date":date.group(1) if date else "",
                "total_amount":amount.group(1).replace(",","") if amount else ""}

    @bp.get("/api/documind/documents")
    def documents_list():
        import json
        with connect() as con:
            rows = con.execute("SELECT id,filename,file_type,fields_json,status,created_at FROM documents ORDER BY created_at DESC LIMIT 100").fetchall()
        result=[]
        for r in rows:
            item=dict(r); item["fields"]=json.loads(item.pop("fields_json")); result.append(item)
        return jsonify(result)

    @bp.post("/api/documind/process")
    def documents_process():
        import json
        f = request.files.get("file")
        if not f or not f.filename: return fail("Choose a PDF or TXT document.")
        filename = secure_filename(f.filename)[:180] or "sample-document"
        ext = filename.rsplit(".",1)[-1].lower() if "." in filename else ""
        if ext not in {"pdf","txt"}: return fail("This version supports text-based PDF and TXT files. Image OCR and scanned PDFs need an AI/OCR provider.")
        raw = f.read(MAX_UPLOAD+1)
        if len(raw)>MAX_UPLOAD: return fail("File is too large. Maximum upload size is 10 MB.")
        try:
            if ext=="txt":
                extracted = raw.decode("utf-8-sig")
            else:
                if not raw.startswith(b"%PDF-"):
                    return fail("The selected file does not appear to be a valid PDF.")
                from pypdf import PdfReader
                import io
                reader=PdfReader(io.BytesIO(raw))
                extracted="\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            return fail("Could not read this file. Try a valid text-based PDF or UTF-8 TXT file.")
        extracted=extracted[:100000]
        if not extracted.strip():
            return fail("No selectable text was found. Scanned PDFs require OCR; this demo currently supports text-based PDFs.")
        fields=extract_fields(extracted)
        ident=str(uuid.uuid4())
        with connect() as con:
            con.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?)",
                (ident,filename,ext,extracted,json.dumps(fields), "Pending",now()))
        return jsonify({"id":ident,"filename":filename,"file_type":ext,"fields":fields,"status":"Pending","extracted_preview":extracted[:3000]}),201

    @bp.patch("/api/documind/documents/<ident>")
    def documents_update(ident):
        d=request.get_json(silent=True) or {}
        status=d.get("status")
        if status not in {"Approved","Needs review"}: return fail("Invalid review status.")
        with connect() as con:
            cur=con.execute("UPDATE documents SET status=? WHERE id=?",(status,ident))
            if not cur.rowcount: return fail("Document not found.",404)
            row=con.execute("SELECT id,filename,file_type,fields_json,status,created_at FROM documents WHERE id=?",(ident,)).fetchone()
        item=dict(row); item["fields"]=json.loads(item.pop("fields_json"))
        return jsonify(item)

    init()
    app.register_blueprint(bp)
