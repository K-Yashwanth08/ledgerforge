from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..invoices_service import (cancel_invoice, create_invoice, invoice_detail, invoice_query,
    receivables_by_client, record_payment, refresh_overdue, send_invoice, update_draft_invoice)
from ..models import Client, Invoice
from ..schemas import (ClientCreate, ClientOut, ClientPatch, InvoiceCancel, InvoiceCreate, InvoiceOut,
    InvoiceUpdate, PaymentCreate, InvoicePaymentOut, ReceivableOut)
from ..security import admin_actor, hr_actor

router=APIRouter(tags=["clients and receivables"])

@router.get("/clients",response_model=list[ClientOut])
def clients(search:str|None=None,active_only:bool=False,limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0),
            db:Session=Depends(get_db),_actor:dict=Depends(hr_actor)):
    q=db.query(Client)
    if search:q=q.filter(Client.client_name.ilike(f"%{search}%"))
    if active_only:q=q.filter(Client.is_active.is_(True))
    return q.order_by(Client.client_name,Client.client_id).offset(offset).limit(limit).all()

@router.post("/clients",response_model=ClientOut,status_code=201)
def create_client(payload:ClientCreate,db:Session=Depends(get_db),_actor:dict=Depends(hr_actor)):
    if db.get(Client,payload.client_id):raise HTTPException(409,"client_id already exists")
    client=Client(**payload.model_dump());db.add(client)
    try:db.commit();db.refresh(client);return client
    except Exception:db.rollback();raise

@router.get("/clients/{client_id}",response_model=ClientOut)
def client_detail(client_id:str,db:Session=Depends(get_db),_actor:dict=Depends(hr_actor)):
    client=db.get(Client,client_id)
    if not client:raise HTTPException(404,"Client not found")
    return client

@router.patch("/clients/{client_id}",response_model=ClientOut)
def update_client(client_id:str,payload:ClientPatch,db:Session=Depends(get_db),_actor:dict=Depends(hr_actor)):
    client=db.get(Client,client_id)
    if not client:raise HTTPException(404,"Client not found")
    for key,value in payload.model_dump(exclude_unset=True).items():setattr(client,key,value)
    try:db.commit();db.refresh(client);return client
    except Exception:db.rollback();raise

@router.get("/invoices",response_model=list[InvoiceOut])
def invoices(status:str|None=None,client_id:str|None=None,search:str|None=None,
             limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0),
             db:Session=Depends(get_db),_actor:dict=Depends(hr_actor)):
    refresh_overdue(db)
    q=invoice_query(db)
    if status:q=q.filter_by(status=status.upper())
    if client_id:q=q.filter_by(client_id=client_id)
    if search:q=q.filter(Invoice.invoice_number.ilike(f"%{search}%"))
    result=q.order_by(Invoice.invoice_date.desc()).offset(offset).limit(limit).all()
    db.commit()
    return [{**{k:getattr(x,k) for k in ("invoice_id","invoice_number","client_id","invoice_date","due_date","currency","subtotal","gst_rate_percent","gst_amount","total_amount","amount_paid","balance_due","status","po_number","ledger_entry_id")},
        "client_name":x.client.client_name if x.client else None,"items":x.items,"payments":x.payments} for x in result]

@router.post("/invoices",response_model=InvoiceOut,status_code=201)
def create_invoice_route(payload:InvoiceCreate,db:Session=Depends(get_db),actor:dict=Depends(hr_actor)):
    try:
        invoice=create_invoice(db,payload,actor["sub"]);db.commit();db.refresh(invoice)
        return invoice_detail(db,invoice.invoice_id)
    except Exception:db.rollback();raise

@router.get("/invoices/{invoice_id}",response_model=InvoiceOut)
def invoice_route(invoice_id:str,db:Session=Depends(get_db),_actor:dict=Depends(hr_actor)):
    return invoice_detail(db,invoice_id)

@router.patch("/invoices/{invoice_id}",response_model=InvoiceOut)
def update_invoice_route(invoice_id:str,payload:InvoiceUpdate,db:Session=Depends(get_db),_actor:dict=Depends(hr_actor)):
    try:
        update_draft_invoice(db,invoice_id,payload);db.commit();return invoice_detail(db,invoice_id)
    except Exception:db.rollback();raise

@router.post("/invoices/{invoice_id}/send",response_model=InvoiceOut)
def send_invoice_route(invoice_id:str,db:Session=Depends(get_db),actor:dict=Depends(hr_actor)):
    try:
        send_invoice(db,invoice_id,actor["sub"]);db.commit();return invoice_detail(db,invoice_id)
    except Exception:db.rollback();raise

@router.post("/invoices/{invoice_id}/payments",response_model=InvoicePaymentOut,status_code=201)
def payment_route(invoice_id:str,payload:PaymentCreate,db:Session=Depends(get_db),actor:dict=Depends(admin_actor)):
    try:
        payment=record_payment(db,invoice_id,payload,actor["sub"]);db.commit();db.refresh(payment);return payment
    except Exception:db.rollback();raise

@router.post("/invoices/{invoice_id}/cancel",response_model=InvoiceOut)
def cancel_route(invoice_id:str,payload:InvoiceCancel,db:Session=Depends(get_db),actor:dict=Depends(admin_actor)):
    try:
        cancel_invoice(db,invoice_id,payload.reason,actor["sub"]);db.commit();return invoice_detail(db,invoice_id)
    except Exception:db.rollback();raise

@router.get("/receivables",response_model=list[ReceivableOut])
def receivables(db:Session=Depends(get_db),_actor:dict=Depends(hr_actor)):
    refresh_overdue(db);db.commit();return receivables_by_client(db)
