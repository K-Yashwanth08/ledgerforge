/* Dashboard views backed by the authenticated LedgerForge APIs. */
function dashboardTokenInput() {
  return `<div class="field full"><label for="sectionToken">Identity provider bearer token</label><input id="sectionToken" type="password" autocomplete="off" spellcheck="false" required placeholder="Paste token for this session"><small class="subtitle">LedgerForge does not issue tokens. Token is held only in this page and sent in the Authorization header.</small></div>`;
}

function sectionHeaders() {
  const token = el("sectionToken")?.value.trim();
  if (!token) throw Error("Enter an identity provider bearer token.");
  return { Authorization: `Bearer ${token}` };
}

function sectionError(box, error) {
  box.className = "unavailable";
  box.textContent = error?.message || "The request could not be completed.";
}

function claimsHint(token) {
  try {
    let part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    part += "=".repeat((4 - part.length % 4) % 4);
    return JSON.parse(atob(part)).role?.toLowerCase() || "employee";
  } catch { return "employee"; }
}

async function renderAttendance() {
  content.innerHTML = `${head("People operations", "Attendance", "Review recorded attendance, source working hours, and reported overtime.")}<section class="panel"><div class="formgrid"><div class="field"><label for="attendanceEmployee">Employee ID (optional)</label><input id="attendanceEmployee" autocomplete="off"></div><div class="field"><label for="attendanceMonth">Summary month</label><input id="attendanceMonth" type="month" value="${new Date().toISOString().slice(0, 7)}"></div><div class="field"><label for="attendanceStart">From</label><input id="attendanceStart" type="date"></div><div class="field"><label for="attendanceEnd">Through</label><input id="attendanceEnd" type="date"></div>${dashboardTokenInput()}<div class="full filters"><button class="button" id="attendanceLoad">Load records</button><button class="button secondary" id="attendanceSummary">Monthly summary</button></div></div><div id="attendanceSummaryBox"></div><div id="attendanceResult" class="empty">Attendance hours and overtime are displayed as recorded in the source.</div><div class="pagination"><button id="attendancePrev" class="button secondary" disabled>Previous</button><span id="attendancePage">No records loaded</span><button id="attendanceNext" class="button secondary" disabled>Next</button></div></section>`;
  let offset = 0, canNext = false;
  const box = el("attendanceResult");
  async function load() {
    const params = new URLSearchParams({ limit: "101", offset: String(offset) });
    const employee = el("attendanceEmployee").value.trim();
    const start = el("attendanceStart").value, end = el("attendanceEnd").value;
    if (employee) params.set("employee_id", employee);
    if (start) params.set("start_date", start);
    if (end) params.set("end_date", end);
    box.className = "empty"; box.textContent = "Loading attendance records…";
    try {
      const rows = await request(`/attendance?${params}`, { headers: sectionHeaders() });
      canNext = rows.length > 100;
      const visibleRows = rows.slice(0, 100);
      box.className = "";
      box.innerHTML = visibleRows.length ? `<div class="table-wrap"><table><thead><tr><th>Date</th><th>Employee</th><th>Status</th><th>Check in</th><th>Check out</th><th>Hours</th><th>Overtime</th><th>Late</th></tr></thead><tbody>${visibleRows.map(r => `<tr><td>${esc(r.attendance_date)}</td><td>${esc(r.employee_id)}</td><td>${esc(r.status)}</td><td>${esc(r.check_in || "—")}</td><td>${esc(r.check_out || "—")}</td><td>${esc(r.hours_worked ?? "—")}</td><td>${esc(r.overtime_hours ?? "—")}</td><td>${esc(r.late_flag || "—")}</td></tr>`).join("")}</tbody></table></div>` : `<div class="empty">No attendance records matched these filters.</div>`;
      el("attendancePage").textContent = `${visibleRows.length ? `Showing ${offset + 1}–${offset + visibleRows.length}` : "No records"}${canNext ? " · more available" : ""}`;
      el("attendancePrev").disabled = offset === 0; el("attendanceNext").disabled = !canNext;
    } catch (error) { sectionError(box, error); }
  }
  el("attendanceLoad").onclick = () => { offset = 0; load(); };
  el("attendancePrev").onclick = () => { offset = Math.max(0, offset - 100); load(); };
  el("attendanceNext").onclick = () => { if (canNext) { offset += 100; load(); } };
  el("attendanceSummary").onclick = async () => {
    const employee = el("attendanceEmployee").value.trim(), month = el("attendanceMonth").value, summary = el("attendanceSummaryBox");
    if (!employee || !month) { sectionError(summary, Error("Enter an employee ID and summary month.")); return; }
    summary.className = "empty"; summary.textContent = "Loading summary…";
    try {
      const r = await request(`/attendance/summary/${encodeURIComponent(employee)}?month=${encodeURIComponent(month)}`, { headers: sectionHeaders() });
      summary.className = "metrics";
      summary.innerHTML = [["PRESENT",r.days_present],["WFH",r.work_from_home_days],["ABSENT",r.absent_days],["PAID LEAVE",r.paid_leave_days],["UNPAID LEAVE",r.unpaid_leave_days],["OVERTIME HOURS",r.overtime_hours],["LATE",r.late_occurrences],["MISSING CHECKOUT",r.missing_checkout_records]].map(([label,value]) => `<article class="card metric"><div class="metric-label">${label}</div><div class="metric-value">${esc(value)}</div></article>`).join("");
    } catch (error) { sectionError(summary, error); }
  };
}

async function renderLeave() {
  const today = new Date(), year = today.getFullYear();
  let leaveOffset = 0, leaveHasNext = false;
  content.innerHTML = `${head("People operations", "Leave management", "View leave balances, policy types, holidays, and requests; submit or decide requests according to your role.")}<section class="panel"><div class="formgrid"><div class="field"><label for="leaveEmployee">Employee ID (optional for HR)</label><input id="leaveEmployee" autocomplete="off" placeholder="Employee ID"></div><div class="field"><label for="leaveStatus">Request status</label><select id="leaveStatus"><option value="">All statuses</option><option>Pending</option><option>Approved</option><option>Rejected</option></select></div><div class="field"><label for="holidayYear">Holiday year</label><input id="holidayYear" type="number" min="2000" max="2100" value="${year}"></div>${dashboardTokenInput()}<div class="full filters"><button class="button" id="leaveLoad">Load balances and requests</button><button class="button secondary" id="holidayLoad">Load holidays</button></div></div><div id="leaveBalances"></div><div id="leaveTypes"></div><div id="holidayList"></div><div id="leaveRequests" class="empty">Enter an employee ID, or use an HR/admin token to review all requests.</div><div class="pagination"><button id="leavePrev" class="button secondary" disabled>Previous</button><span id="leavePage">No requests loaded</span><button id="leaveNext" class="button secondary" disabled>Next</button></div><div id="leaveApplyPanel"></div></section>`;
  const employee = el("leaveEmployee");
  employee.onchange = () => { leaveOffset = 0; };
  el("leaveStatus").onchange = () => { leaveOffset = 0; };
  el("leaveLoad").onclick = async () => {
    const id = employee.value.trim(), box = el("leaveRequests");
    box.className = "empty"; box.textContent = "Loading leave records…";
    try {
      const headers = sectionHeaders(), isHr = ["hr", "admin"].includes(claimsHint(el("sectionToken").value));
      if (!id && !isHr) throw Error("Enter your employee ID. HR/admin users may leave it blank to review all requests.");
      const params = new URLSearchParams({ limit: "101", offset: String(leaveOffset) }), status = el("leaveStatus").value;
      if (id) params.set("employee_id", id); if (status) params.set("status", status);
      const [balances, types, requests] = await Promise.all([
        id ? request(`/leave/balances/${encodeURIComponent(id)}`, { headers }) : Promise.resolve([]),
        request("/leave/types", { headers }),
        request(`/leave/requests?${params}`, { headers }),
      ]);
      leaveHasNext = requests.length > 100;
      const visibleRequests = requests.slice(0, 100);
      el("leaveBalances").innerHTML = id ? `<h2 style="margin:18px">Balances</h2>${balances.length ? `<div class="table-wrap"><table><thead><tr><th>Type</th><th>FY</th><th>As of</th><th>Entitlement</th><th>Used</th><th>Available</th></tr></thead><tbody>${balances.map(b=>`<tr><td>${esc(b.leave_type_code)}</td><td>${esc(b.financial_year)}</td><td>${esc(b.as_of_date)}</td><td>${esc(b.entitlement_days)}</td><td>${esc(b.used_days)}</td><td>${esc(b.balance_days)}</td></tr>`).join("")}</tbody></table></div>` : `<div class="empty">No imported leave balance snapshots for this employee.</div>`}` : "";
      el("leaveTypes").innerHTML = `<details style="padding:16px"><summary>Leave types and supplied policy notes (${types.length})</summary><div class="table-wrap"><table><thead><tr><th>Code</th><th>Type</th><th>Pay</th><th>Annual quota</th><th>Carry forward</th><th>Policy note</th></tr></thead><tbody>${types.map(t=>`<tr><td>${esc(t.leave_type_code)}</td><td>${esc(t.leave_type_name)}</td><td>${esc(t.pay_type)}</td><td>${esc(t.annual_quota_days)}</td><td>${t.carry_forward_allowed?esc(t.max_carry_forward_days):"No"}</td><td>${esc(t.policy_note||"—")}</td></tr>`).join("")}</tbody></table></div></details>`;
      renderLeaveRequests(visibleRequests, box, headers);
      el("leavePage").textContent = `${visibleRequests.length ? `Showing ${leaveOffset + 1}–${leaveOffset + visibleRequests.length}` : "No requests"}${leaveHasNext ? " · more available" : ""}`;
      el("leavePrev").disabled = leaveOffset === 0; el("leaveNext").disabled = !leaveHasNext;
      if (id) renderLeaveApplication(types, headers, id, () => el("leaveLoad").click());
      else el("leaveApplyPanel").innerHTML = `<div class="subtitle" style="padding:16px">Select an employee to submit a request; employee ownership is checked by the API.</div>`;
    } catch (error) { sectionError(box, error); }
  };
  el("leavePrev").onclick = () => { leaveOffset = Math.max(0, leaveOffset - 100); el("leaveLoad").click(); };
  el("leaveNext").onclick = () => { if (leaveHasNext) { leaveOffset += 100; el("leaveLoad").click(); } };
  el("holidayLoad").onclick = async () => {
    const box = el("holidayList"), y = el("holidayYear").value;
    if (!y || Number(y) < 2000 || Number(y) > 2100) { sectionError(box, Error("Enter a valid calendar year.")); return; }
    box.className = "empty"; box.textContent = "Loading holidays…";
    try {
      const rows = await request(`/leave/holidays?start_date=${y}-01-01&end_date=${y}-12-31`, { headers: sectionHeaders() });
      box.className = "";
      box.innerHTML = `<h2 style="margin:18px">Holidays in ${esc(y)}</h2>${rows.length ? `<div class="table-wrap"><table><thead><tr><th>Date</th><th>Name</th><th>Type</th><th>Weekday</th><th>Weekend</th></tr></thead><tbody>${rows.map(h=>`<tr><td>${esc(h.holiday_date)}</td><td>${esc(h.holiday_name)}</td><td>${esc(h.holiday_type)}</td><td>${esc(h.weekday)}</td><td>${h.falls_on_weekend?"Yes":"No"}</td></tr>`).join("")}</tbody></table></div>` : `<div class="empty">No supplied holidays for this year.</div>`}`;
    } catch (error) { sectionError(box, error); }
  };
}

function renderLeaveRequests(requests, box, headers) {
  const isHr = ["hr", "admin"].includes(claimsHint(el("sectionToken").value));
  box.className = "";
  box.innerHTML = `<h2 style="margin:18px">Leave requests</h2>${requests.length ? `<div class="table-wrap"><table><thead><tr><th>Request</th><th>Employee</th><th>Type</th><th>Dates</th><th>Days</th><th>Status</th><th>Reason</th>${isHr?"<th>Decision</th>":""}</tr></thead><tbody>${requests.map(r=>`<tr><td>${esc(r.leave_request_id)}</td><td>${esc(r.employee_id)}</td><td>${esc(r.leave_type_code)}</td><td>${esc(r.start_date)} – ${esc(r.end_date)}</td><td>${esc(r.days)}</td><td>${esc(r.status)}</td><td>${esc(r.reason)}</td>${isHr?`<td>${r.status==="Pending"?`<button class="button smallbtn" data-leave-decision="approve" data-id="${esc(r.leave_request_id)}">Approve</button> <button class="button secondary smallbtn" data-leave-decision="reject" data-id="${esc(r.leave_request_id)}">Reject</button>`:"—"}</td>`:""}</tr>`).join("")}</tbody></table></div>` : `<div class="empty">No leave requests found.</div>`}`;
  box.querySelectorAll("[data-leave-decision]").forEach(button => button.onclick = async () => {
    button.disabled = true;
    try {
      await request(`/leave/requests/${encodeURIComponent(button.dataset.id)}/${button.dataset.leaveDecision}`, { method: "POST", headers });
      el("leaveLoad").click();
    } catch (error) { button.disabled = false; sectionError(box, error); }
  });
  // The server remains authoritative for employee ownership and HR authorization.
}

function renderLeaveApplication(types, headers, employeeId, onSaved) {
  const box = el("leaveApplyPanel");
  box.innerHTML = `<details style="padding:16px"><summary>Submit a leave request</summary><form id="leaveForm" class="formgrid"><div class="field"><label for="leaveType">Leave type</label><select id="leaveType" required>${types.map(t=>`<option value="${esc(t.leave_type_code)}">${esc(t.leave_type_name)} (${esc(t.pay_type)})</option>`).join("")}</select></div><div class="field"><label for="leaveStart">Start date</label><input id="leaveStart" type="date" required></div><div class="field"><label for="leaveEnd">End date</label><input id="leaveEnd" type="date" required></div><label class="field"><span>Half day</span><input id="leaveHalf" type="checkbox"></label><div class="field full"><label for="leaveReason">Reason</label><input id="leaveReason" maxlength="500" required></div><div class="full"><button class="button" type="submit">Submit request</button><span id="leaveFormMessage" class="subtitle" role="status"></span></div></form></details>`;
  el("leaveForm").onsubmit = async event => {
    event.preventDefault(); const message = el("leaveFormMessage");
    try {
      await request("/leave/requests", { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify({ employee_id: employeeId, leave_type_code: el("leaveType").value, start_date: el("leaveStart").value, end_date: el("leaveEnd").value, is_half_day: el("leaveHalf").checked, reason: el("leaveReason").value.trim() }) });
      message.textContent = "Request submitted."; onSaved();
    } catch (error) { message.textContent = error.message; }
  };
}

async function renderPayslips() {
  content.innerHTML = `${head("Payroll", "Payslips", "Choose a saved payroll result and view its details or download its PDF.")}<section class="panel"><div class="formgrid"><div class="field"><label for="payslipEmployee">Employee ID</label><input id="payslipEmployee" autocomplete="off"></div>${dashboardTokenInput()}<div class="full"><button id="payslipLoad" class="button">Find available payslips</button></div></div><div id="payslipResult" class="empty">Payslips are read from persisted payroll items. No recalculation is performed.</div></section>`;
  el("payslipLoad").onclick = async () => {
    const id = el("payslipEmployee").value.trim(), box = el("payslipResult");
    if (!id) { sectionError(box, Error("Enter an employee ID.")); return; }
    box.className = "empty"; box.textContent = "Loading saved payroll runs…";
    try {
      const headers = sectionHeaders(), runs = await request(`/payslips/employee/${encodeURIComponent(id)}/runs`, { headers });
      box.className = "";
      if (!runs.length) { box.innerHTML = `<div class="empty">No saved payslips are available for this employee.</div>`; return; }
      box.innerHTML = `<div class="formgrid"><div class="field"><label for="payslipRun">Payroll period</label><select id="payslipRun">${runs.map(r=>`<option value="${esc(r.run_id)}">${esc(r.period_start)} – ${esc(r.period_end)} · ${esc(r.run_id)}</option>`).join("")}</select></div><div class="field" style="align-self:end"><button id="payslipView" class="button">View details</button> <button id="payslipPdf" class="button secondary">Download PDF</button></div></div><div id="payslipDetails"></div>`;
      async function showDetails() {
        const result = el("payslipDetails"), runId = el("payslipRun").value;
        result.className = "empty"; result.textContent = "Loading persisted payslip…";
        try {
          const data = await request(`/payslips/${encodeURIComponent(id)}/${encodeURIComponent(runId)}/data`, { headers });
          result.className = "";
          const rows = items => items.map(x=>`<tr><td>${esc(x.label)}</td><td>${money(x.amount)}</td></tr>`).join("") || `<tr><td colspan="2" class="empty">None recorded</td></tr>`;
          const company=data.company_details||{}, companyLine=[company.legal_name,company.address,company.contact_email,company.contact_phone].filter(Boolean).map(esc).join(" · ");
          result.innerHTML = `<div style="padding:18px"><p><strong>${esc(data.employee.full_name)}</strong> · ${esc(data.employee.department_name||"—")} · ${esc(data.employee.role_title||"—")}</p><p class="subtitle">${esc(data.period_start)} – ${esc(data.period_end)} · Pay date ${esc(data.pay_date||"—")}</p>${companyLine?`<p class="subtitle">${companyLine}</p>`:`<p class="subtitle">${esc(data.company_details_note||"")}</p>`}<h2>Earnings</h2><table><tbody>${rows(data.earnings)}</tbody></table><h2 style="margin-top:18px">Deductions</h2><table><tbody>${rows(data.deductions)}</tbody></table><div class="metrics"><article class="card metric"><div class="metric-label">GROSS</div><div class="metric-value">${money(data.gross_pay)}</div></article><article class="card metric"><div class="metric-label">DEDUCTIONS</div><div class="metric-value">${money(data.total_deductions)}</div></article><article class="card metric"><div class="metric-label">NET PAY</div><div class="metric-value">${money(data.net_pay)}</div></article></div></div>`;
        } catch (error) { sectionError(result, error); }
      }
      el("payslipView").onclick = showDetails;
      el("payslipPdf").onclick = async event => {
        const button = event.currentTarget; button.disabled = true;
        try {
          const response = await fetch(`${API_BASE}/payslips/${encodeURIComponent(id)}/${encodeURIComponent(el("payslipRun").value)}`, { headers });
          if (!response.ok) { let body; try { body = await response.json(); } catch {} throw Error(body?.detail || `Request failed (${response.status})`); }
          const url = URL.createObjectURL(await response.blob()), anchor = document.createElement("a");
          anchor.href = url; anchor.download = `payslip-${id}-${el("payslipRun").value}.pdf`; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (error) { sectionError(el("payslipDetails"), error); }
        finally { button.disabled = false; }
      };
      showDetails();
    } catch (error) { sectionError(box, error); }
  };
}

async function renderLedger() {
  content.innerHTML = `${head("Finance", "Accounting ledger", "Browse the chart of accounts and immutable posted journal entries.")}<section class="panel"><div class="formgrid"><div class="field"><label for="ledgerStart">From</label><input id="ledgerStart" type="date"></div><div class="field"><label for="ledgerEnd">Through</label><input id="ledgerEnd" type="date"></div><div class="field"><label for="ledgerAccount">Account filter</label><select id="ledgerAccount"><option value="">All accounts</option></select></div><div class="field"><label for="ledgerAsOf">Balance as of</label><input id="ledgerAsOf" type="date" value="${new Date().toISOString().slice(0,10)}"></div>${dashboardTokenInput()}<div class="full filters"><button id="ledgerLoad" class="button">Load ledger</button><button id="ledgerBalance" class="button secondary">Account balance</button></div></div><div id="ledgerBalanceResult"></div><div id="ledgerResult" class="empty">Journal lines and totals are read from posted ledger records.</div><div class="pagination"><button id="ledgerPrev" class="button secondary" disabled>Previous</button><span id="ledgerPage">No entries loaded</span><button id="ledgerNext" class="button secondary" disabled>Next</button></div></section>`;
  let offset = 0, canNext = false;
  const box = el("ledgerResult");
  async function load() {
    const params = new URLSearchParams({ limit: "50", offset: String(offset) }), start=el("ledgerStart").value, end=el("ledgerEnd").value, account=el("ledgerAccount").value;
    if (start) params.set("start_date", start); if (end) params.set("end_date", end); if (account) params.set("account_code", account);
    box.className="empty"; box.textContent="Loading ledger records…";
    try {
      const headers=sectionHeaders(), [accounts, entries]=await Promise.all([request("/ledger/accounts",{headers}),request(`/ledger/journal-entries?${params}`,{headers})]);
      const select=el("ledgerAccount"), chosen=select.value;
      select.innerHTML=`<option value="">All accounts</option>${accounts.map(a=>`<option value="${esc(a.account_code)}">${esc(a.account_code)} · ${esc(a.account_name)}</option>`).join("")}`; select.value=chosen;
      canNext=entries.length===50; box.className="";
      const debit=entries.reduce((sum,e)=>sum+Number(e.total_debit),0), credit=entries.reduce((sum,e)=>sum+Number(e.total_credit),0);
      box.innerHTML=entries.length?`<p class="subtitle" style="padding:14px">Page totals · Debits ${money(debit)} · Credits ${money(credit)}</p>${entries.map(e=>`<details class="panel" style="margin:10px"><summary style="padding:14px">${esc(e.entry_date)} · ${esc(e.entry_id)} · ${esc(e.description)} · Dr ${money(e.total_debit)} / Cr ${money(e.total_credit)}</summary><p class="subtitle" style="padding:0 14px 10px">${esc(e.source_type)} ${esc(e.source_id||"")} · ${esc(e.status)} · ${esc(e.financial_year)}</p><div class="table-wrap"><table><thead><tr><th>Account</th><th>Description</th><th>Debit</th><th>Credit</th></tr></thead><tbody>${e.lines.map(l=>`<tr><td>${esc(l.account_code)}</td><td>${esc(l.line_description)}</td><td>${money(l.debit)}</td><td>${money(l.credit)}</td></tr>`).join("")}</tbody></table></div></details>`).join("")}`:`<div class="empty">No journal entries matched these filters.</div>`;
      el("ledgerPage").textContent=`${entries.length?`Showing ${offset+1}–${offset+entries.length}`:"No entries"}${canNext?" · more available":""}`; el("ledgerPrev").disabled=offset===0; el("ledgerNext").disabled=!canNext;
    } catch(error) { sectionError(box,error); }
  }
  el("ledgerLoad").onclick=()=>{offset=0;load()}; el("ledgerPrev").onclick=()=>{offset=Math.max(0,offset-50);load()}; el("ledgerNext").onclick=()=>{if(canNext){offset+=50;load()}};
  el("ledgerBalance").onclick=async()=>{const code=el("ledgerAccount").value, asOf=el("ledgerAsOf").value, result=el("ledgerBalanceResult"); if(!code){sectionError(result,Error("Select an account to view its balance."));return} try{const r=await request(`/ledger/accounts/${encodeURIComponent(code)}/balance?as_of=${encodeURIComponent(asOf)}`,{headers:sectionHeaders()});result.className="metrics";result.innerHTML=[["DEBITS",r.debits],["CREDITS",r.credits],["BALANCE",r.balance]].map(([label,value])=>`<article class="card metric"><div class="metric-label">${label} · ${esc(r.account_code)}</div><div class="metric-value">${money(value)}</div><div class="metric-note">As of ${esc(r.as_of)} · ${esc(r.normal_balance)} normal</div></article>`).join("")}catch(error){sectionError(result,error)}};
}

async function renderReceivables(initialTab) {
  let tab=initialTab, offset=0, canNext=false, clientSearchValue="", invoiceSearchValue="", invoiceStatusValue="", invoiceClientValue="";
  content.innerHTML=`${head("Finance", "Clients and receivables", "Review client records, invoice lines, recorded payments, and outstanding balances.")}<section class="panel"><div class="formgrid">${dashboardTokenInput()}<div class="full filters"><button class="button secondary" data-recv-tab="clients">Clients</button><button class="button secondary" data-recv-tab="invoices">Invoices and payments</button><button class="button secondary" data-recv-tab="balances">Open balances</button></div><div id="receivablesFilters" class="full"></div><div id="receivablesResult" class="full empty">Loading records…</div><div class="pagination full"><button id="receivablesPrev" class="button secondary" disabled>Previous</button><span id="receivablesPage">No records loaded</span><button id="receivablesNext" class="button secondary" disabled>Next</button></div></div></section>`;
  const box=el("receivablesResult");
  document.querySelectorAll("[data-recv-tab]").forEach(b=>b.onclick=()=>{tab=b.dataset.recvTab;offset=0;load()});
  async function load(){
    const headers=sectionHeaders(), filters=el("receivablesFilters"); box.className="empty";box.textContent="Loading records…";
    try {
      if(tab==="clients"){
        filters.innerHTML=`<div class="filters"><input id="clientSearch" value="${esc(clientSearchValue)}" placeholder="Search client name" aria-label="Search clients"><button class="button" id="receivablesSearch">Search</button></div>`;
        el("receivablesSearch").onclick=()=>{clientSearchValue=el("clientSearch").value.trim();offset=0;load()};
        const p=new URLSearchParams({limit:"50",offset:String(offset)}); if(clientSearchValue)p.set("search",clientSearchValue);
        const rows=await request(`/clients?${p}`,{headers});canNext=rows.length===50;box.className="";
        box.innerHTML=rows.length?`<div class="table-wrap"><table><thead><tr><th>Client</th><th>Location</th><th>Type</th><th>Contact</th><th>Terms</th><th>Active</th><th>Details</th></tr></thead><tbody>${rows.map(c=>`<tr><td>${esc(c.client_name)}<div class="meta">${esc(c.client_id)}</div></td><td>${esc([c.city,c.state_or_region,c.country].filter(Boolean).join(", "))}</td><td>${esc(c.client_type||"—")}</td><td>${esc(c.contact_email||"—")}</td><td>${esc(c.payment_terms_days)} days</td><td>${c.is_active?"Yes":"No"}</td><td><details><summary>View</summary><p>Industry: ${esc(c.industry||"?")}</p><p>GST: ${esc(c.gst_registration||"?")}</p><p>Service line: ${esc(c.primary_service_line||"?")}</p><p>Onboarded: ${esc(c.onboarded_on||"?")}</p><p>Payment behaviour: ${esc(c.payment_behaviour||"?")}</p></details></td></tr>`).join("")}</tbody></table></div>`:`<div class="empty">No clients matched the search.</div>`;
        el("receivablesPage").textContent=`${rows.length?`Showing ${offset+1}–${offset+rows.length}`:"No clients"}${canNext?" · more available":""}`;
      } else if(tab==="invoices"){
        filters.innerHTML=`<div class="filters"><input id="invoiceSearch" value="${esc(invoiceSearchValue)}" placeholder="Invoice number" aria-label="Search invoice number"><select id="invoiceStatus"><option value="">All statuses</option>${["DRAFT","SENT","OVERDUE","PARTIALLY_PAID","PAID","CANCELLED"].map(s=>`<option value="${s}" ${invoiceStatusValue===s?"selected":""}>${s}</option>`).join("")}</select><input id="invoiceClient" value="${esc(invoiceClientValue)}" placeholder="Client ID" aria-label="Client ID"><button class="button" id="receivablesSearch">Search</button></div>`;
        el("receivablesSearch").onclick=()=>{invoiceSearchValue=el("invoiceSearch").value.trim();invoiceStatusValue=el("invoiceStatus").value;invoiceClientValue=el("invoiceClient").value.trim();offset=0;load()};
        const p=new URLSearchParams({limit:"50",offset:String(offset)}); if(invoiceSearchValue)p.set("search",invoiceSearchValue);if(invoiceStatusValue)p.set("status",invoiceStatusValue);if(invoiceClientValue)p.set("client_id",invoiceClientValue);
        const rows=await request(`/invoices?${p}`,{headers});canNext=rows.length===50;box.className="";
        box.innerHTML=rows.length?`<div class="table-wrap"><table><thead><tr><th>Invoice</th><th>Client</th><th>Dates</th><th>Status</th><th>Total</th><th>Paid</th><th>Due</th><th>Details</th></tr></thead><tbody>${rows.map(i=>`<tr><td>${esc(i.invoice_number)}</td><td>${esc(i.client_name||i.client_id)}</td><td>${esc(i.invoice_date)} / due ${esc(i.due_date)}</td><td>${esc(i.status)}</td><td>${money(i.total_amount)}</td><td>${money(i.amount_paid)}</td><td>${money(i.balance_due)}</td><td><details><summary>Lines and payments</summary><strong>Items</strong><ul>${i.items.map(x=>`<li>${esc(x.description)} · ${esc(x.quantity)} × ${money(x.unit_price)} = ${money(x.amount)}</li>`).join("")||"<li>None</li>"}</ul><strong>Recorded payments</strong><ul>${i.payments.map(x=>`<li>${esc(x.payment_date)} · ${esc(x.payment_mode)} · ${money(x.amount)} · ${esc(x.reference_no||"—")}</li>`).join("")||"<li>None</li>"}</ul></details></td></tr>`).join("")}</tbody></table></div>`:`<div class="empty">No invoices matched these filters.</div>`;
        el("receivablesPage").textContent=`${rows.length?`Showing ${offset+1}–${offset+rows.length}`:"No invoices"}${canNext?" · more available":""}`;
      } else {
        filters.innerHTML=`<p class="subtitle">Outstanding balances include SENT, OVERDUE, and PARTIALLY_PAID invoices as returned by the receivables API.</p>`;
        const rows=await request("/receivables",{headers});box.className="";const total=rows.reduce((s,r)=>s+Number(r.outstanding_balance),0);
        box.innerHTML=rows.length?`<p class="subtitle" style="padding:14px">Total outstanding ${money(total)}</p><div class="table-wrap"><table><thead><tr><th>Client</th><th>Client ID</th><th>Outstanding</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.client_name)}</td><td>${esc(r.client_id)}</td><td>${money(r.outstanding_balance)}</td></tr>`).join("")}</tbody></table></div>`:`<div class="empty">No open receivables.</div>`;canNext=false;el("receivablesPage").textContent=`${rows.length} client balances`;
      }
      el("receivablesPrev").disabled=offset===0;el("receivablesNext").disabled=!canNext;
    } catch(error){sectionError(box,error);el("receivablesPrev").disabled=true;el("receivablesNext").disabled=true;}
  }
  el("receivablesPrev").onclick=()=>{offset=Math.max(0,offset-50);load()};el("receivablesNext").onclick=()=>{if(canNext){offset+=50;load()}};
  await load();
}
