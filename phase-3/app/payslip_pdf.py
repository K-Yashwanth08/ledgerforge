"""Reusable, float-free Indian-currency payslip PDF template."""
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from io import BytesIO

def indian_currency(amount) -> str:
    value = Decimal(str(amount or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    negative = value < 0
    whole, fraction = f"{abs(value):.2f}".split(".")
    if len(whole) > 3:
        tail, head = whole[-3:], whole[:-3]
        groups=[]
        while head:
            groups.insert(0, head[-2:]); head=head[:-2]
        whole=",".join(groups+[tail])
    return f"{'-' if negative else ''}INR {whole}.{fraction}"

def build_payslip_pdf(data: dict) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    except ImportError as exc:
        raise RuntimeError("Payslip PDF dependency is missing. Install requirements.txt (reportlab).") from exc
    out=BytesIO()
    doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=15*mm,bottomMargin=15*mm)
    styles=getSampleStyleSheet()
    title=ParagraphStyle("LFTitle",parent=styles["Title"],fontName="Helvetica-Bold",fontSize=19,textColor=colors.HexColor("#145b50"),spaceAfter=5)
    heading=ParagraphStyle("LFHeading",parent=styles["Heading2"],fontSize=11,textColor=colors.HexColor("#145b50"),spaceBefore=10,spaceAfter=6)
    small=ParagraphStyle("LFSmall",parent=styles["Normal"],fontSize=8,textColor=colors.HexColor("#596775"))
    story=[Paragraph(escape(data["company_name"]),title)]
    company=data.get("company_details") or {}
    legal_lines=[]
    if company.get("legal_name"): legal_lines.append(f"Legal name: {escape(company['legal_name'])}")
    if company.get("address"): legal_lines.append(f"Address: {escape(company['address'])}")
    contact=" · ".join(escape(company[k]) for k in ("contact_email","contact_phone") if company.get(k))
    if contact: legal_lines.append(f"Contact: {contact}")
    if legal_lines: story.append(Paragraph("<br/>".join(legal_lines),small))
    story += [Paragraph("Salary statement · Confidential",small),Spacer(1,12)]
    emp=data["employee"]
    details=[["Employee",emp["full_name"],"Employee ID",emp["employee_id"]],
             ["Department",emp.get("department_name") or "—","Role",emp.get("role_title") or "—"],
             ["Payroll period",f"{data['period_start']} – {data['period_end']}","Pay date",data.get("pay_date") or "—"],
             ["Run ID",data["run_id"],"Currency",data["currency"]]]
    info=Table(details,colWidths=[26*mm,58*mm,24*mm,55*mm])
    info.setStyle(TableStyle([("BACKGROUND",(0,0),(0,-1),colors.HexColor("#f0f5f4")),("BACKGROUND",(2,0),(2,-1),colors.HexColor("#f0f5f4")),
        ("TEXTCOLOR",(0,0),(0,-1),colors.HexColor("#596775")),("TEXTCOLOR",(2,0),(2,-1),colors.HexColor("#596775")),
        ("FONTNAME",(0,0),(-1,-1),"Helvetica"),("FONTSIZE",(0,0),(-1,-1),8),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#dbe4e8")),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)]))
    story += [info,Paragraph("Earnings",heading)]
    earnings=[["Description","Amount (INR)"]]+[[r["label"],indian_currency(r["amount"])] for r in data["earnings"]]
    earnings += [["Total earnings",indian_currency(data["gross_pay"])]]
    deductions=[["Description","Amount (INR)"]]+[[r["label"],indian_currency(r["amount"])] for r in data["deductions"]]
    deductions += [["Total deductions",indian_currency(data["total_deductions"])]]
    def money_table(rows):
        t=Table(rows,colWidths=[116*mm,47*mm],hAlign="LEFT")
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#f0f5f4")),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("ALIGN",(1,0),(1,-1),"RIGHT"),("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#dbe4e8")),
            ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),
            ("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#f7faf9"))]))
        return t
    story += [money_table(earnings),Paragraph("Deductions",heading),money_table(deductions),Spacer(1,16)]
    net=Table([["NET PAY",indian_currency(data["net_pay"])]],colWidths=[116*mm,47*mm])
    net.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#145b50")),("TEXTCOLOR",(0,0),(-1,-1),colors.white),
        ("FONTNAME",(0,0),(-1,-1),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),16),("ALIGN",(1,0),(1,0),"RIGHT"),
        ("TOPPADDING",(0,0),(-1,-1),12),("BOTTOMPADDING",(0,0),(-1,-1),12)]))
    story += [net,Spacer(1,12)]
    if data.get("company_details_note"):
        story.append(Paragraph(escape(data["company_details_note"]),small))
    story.append(Paragraph("This statement is generated from the stored payroll result. Contact HR for corrections.",small))
    doc.build(story)
    return out.getvalue()
