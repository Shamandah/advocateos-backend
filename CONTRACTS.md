# AdvocateOS — Team Contracts

> **This document is law.**
> Nothing merges to `main` that breaks a contract defined here.
> Any change to schema, endpoints, or component interfaces requires
> a PR comment from all 4 devs before merging.
> Last updated: August 2026 · Owner: All devs (Dev A maintains)

---

## 0. Rules of engagement

| Rule | Detail |
|------|--------|
| Branch strategy | `main` is always deployable. Feature branches: `feat/dev-a/matter-api`, `feat/dev-b/mpesa`, etc. |
| PR reviews | Every PR needs 1 approval. PRs touching this file need all 4 approvals. |
| Standup | 15 min daily async in Slack — format: *Done / Doing / Blocked* |
| Env vars | Never commit `.env`. All keys go in `.env.example` with a placeholder. |
| Migrations | Only Dev A creates and runs migrations. Others request via PR. |
| API versioning | All endpoints prefixed `/api/v1/`. No unversioned endpoints. |
| Dates/times | All datetimes stored UTC, returned ISO 8601. Frontend converts to EAT (Africa/Nairobi UTC+3). |
| Money | All amounts in **KES as integers (cents × 100)**. Never floats. `50000` = KES 500.00 |
| Error format | All errors return `{ "error": true, "code": "ERR_CODE", "detail": "..." }` |
| Auth header | `Authorization: Bearer <access_token>` on every protected request |

---

## 1. Database schema contracts

> Dev A owns migrations. Dev B, C, D request schema changes via PR.
> These are the canonical table definitions — Django models must match exactly.

### 1.1 `accounts_firm`
```
id              BIGSERIAL PRIMARY KEY
name            VARCHAR(255) NOT NULL
lsk_number      VARCHAR(50)  UNIQUE
address         TEXT
phone           VARCHAR(20)
email           VARCHAR(254)
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
```

### 1.2 `accounts_user`
```
id              BIGSERIAL PRIMARY KEY
email           VARCHAR(254) UNIQUE NOT NULL
first_name      VARCHAR(100) NOT NULL
last_name       VARCHAR(100) NOT NULL
firm_id         BIGINT REFERENCES accounts_firm(id) ON DELETE CASCADE
role            VARCHAR(30)  NOT NULL DEFAULT 'associate'
                -- values: managing_partner | partner | associate | paralegal | support
lsk_number      VARCHAR(50)
phone           VARCHAR(20)
is_active       BOOLEAN NOT NULL DEFAULT true
is_staff        BOOLEAN NOT NULL DEFAULT false
date_joined     TIMESTAMPTZ NOT NULL DEFAULT now()
password        VARCHAR(128) NOT NULL
```

### 1.3 `matters_client`
```
id              BIGSERIAL PRIMARY KEY
firm_id         BIGINT REFERENCES accounts_firm(id) ON DELETE CASCADE NOT NULL
name            VARCHAR(255) NOT NULL
email           VARCHAR(254)
phone           VARCHAR(20)
id_number       VARCHAR(50)
address         TEXT
is_company      BOOLEAN NOT NULL DEFAULT false
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
created_by_id   BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL
```

### 1.4 `matters_matter`
```
id              BIGSERIAL PRIMARY KEY
firm_id         BIGINT REFERENCES accounts_firm(id) ON DELETE CASCADE NOT NULL
reference       VARCHAR(50) UNIQUE NOT NULL   -- e.g. ADV/2026/001
title           VARCHAR(500) NOT NULL
cause_number    VARCHAR(100)                  -- court cause number
client_id       BIGINT REFERENCES matters_client(id) ON DELETE PROTECT NOT NULL
lead_attorney_id BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL
practice_area   VARCHAR(30) NOT NULL DEFAULT 'other'
                -- litigation | conveyancing | corporate | employment |
                -- family | succession | criminal | land | ip | other
status          VARCHAR(20) NOT NULL DEFAULT 'open'
                -- open | on_hold | closed | archived
court           VARCHAR(200)
judge           VARCHAR(200)
opened_date     DATE NOT NULL DEFAULT CURRENT_DATE
closed_date     DATE
description     TEXT
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
created_by_id   BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL
```

### 1.5 `matters_matter_team` (M2M)
```
id              BIGSERIAL PRIMARY KEY
matter_id       BIGINT REFERENCES matters_matter(id) ON DELETE CASCADE
user_id         BIGINT REFERENCES accounts_user(id) ON DELETE CASCADE
UNIQUE(matter_id, user_id)
```

### 1.6 `calendar_events_courtevent`
```
id              BIGSERIAL PRIMARY KEY
matter_id       BIGINT REFERENCES matters_matter(id) ON DELETE CASCADE NOT NULL
firm_id         BIGINT REFERENCES accounts_firm(id) ON DELETE CASCADE NOT NULL
title           VARCHAR(500) NOT NULL
event_type      VARCHAR(20) NOT NULL DEFAULT 'hearing'
                -- hearing | deadline | deposition | mediation | mention | other
date            DATE NOT NULL
start_time      TIME
end_time        TIME
all_day         BOOLEAN NOT NULL DEFAULT false
court           VARCHAR(200)
judge           VARCHAR(200)
location        VARCHAR(300)
source          VARCHAR(10) NOT NULL DEFAULT 'manual'
                -- manual | jicms
jicms_id        VARCHAR(100) UNIQUE         -- null for manual events
status          VARCHAR(20) NOT NULL DEFAULT 'scheduled'
                -- scheduled | completed | adjourned | cancelled
notes           TEXT
outcome         TEXT
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
created_by_id   BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL
```

### 1.7 `billing_timeentry`
```
id              BIGSERIAL PRIMARY KEY
matter_id       BIGINT REFERENCES matters_matter(id) ON DELETE CASCADE NOT NULL
attorney_id     BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL
description     TEXT NOT NULL
date            DATE NOT NULL
hours           NUMERIC(5,2) NOT NULL
rate_kes        INTEGER NOT NULL             -- KES cents × 100
is_billed       BOOLEAN NOT NULL DEFAULT false
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
```

### 1.8 `billing_invoice`
```
id              BIGSERIAL PRIMARY KEY
firm_id         BIGINT REFERENCES accounts_firm(id) ON DELETE CASCADE NOT NULL
matter_id       BIGINT REFERENCES matters_matter(id) ON DELETE CASCADE NOT NULL
invoice_number  VARCHAR(50) UNIQUE NOT NULL
status          VARCHAR(20) NOT NULL DEFAULT 'draft'
                -- draft | sent | paid | overdue | cancelled
amount_kes      INTEGER NOT NULL             -- KES cents × 100
vat_kes         INTEGER NOT NULL DEFAULT 0
issued_date     DATE NOT NULL
due_date        DATE NOT NULL
notes           TEXT
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
created_by_id   BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL
```

### 1.9 `billing_mpesapayment`
```
id                    BIGSERIAL PRIMARY KEY
invoice_id            BIGINT REFERENCES billing_invoice(id) ON DELETE CASCADE NOT NULL
phone_number          VARCHAR(15) NOT NULL    -- format: 2547XXXXXXXX
amount_kes            INTEGER NOT NULL         -- KES cents × 100
checkout_request_id   VARCHAR(100) UNIQUE NOT NULL  -- from Daraja STK push
mpesa_receipt_number  VARCHAR(20)             -- from callback, null until confirmed
status                VARCHAR(10) NOT NULL DEFAULT 'pending'
                      -- pending | success | failed
result_description    VARCHAR(255)
initiated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
confirmed_at          TIMESTAMPTZ
```

### 1.10 `billing_trustaccount`
```
id              BIGSERIAL PRIMARY KEY
firm_id         BIGINT REFERENCES accounts_firm(id) ON DELETE CASCADE NOT NULL
matter_id       BIGINT REFERENCES matters_matter(id) ON DELETE CASCADE NOT NULL
entry_type      VARCHAR(15) NOT NULL         -- deposit | withdrawal
amount_kes      INTEGER NOT NULL             -- KES cents × 100
description     TEXT NOT NULL
date            DATE NOT NULL
reference       VARCHAR(100)
recorded_by_id  BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
```

---

## 2. API endpoint contracts

> Base URL (dev): `http://localhost:8000/api/v1/`
> Base URL (prod): `https://api.advocateos.co.ke/api/v1/`
> All responses: `Content-Type: application/json`
> Pagination: `{ "count": N, "next": "url|null", "previous": "url|null", "results": [...] }`

### 2.1 Auth endpoints (`/api/v1/auth/`)

#### POST `/api/v1/auth/register/`
Register a new firm + managing partner.
```json
// Request
{
  "firm_name": "Larkin & Associates",
  "lsk_number": "LSK/F/001",
  "first_name": "Jane",
  "last_name": "Larkin",
  "email": "jane@larkinlaw.co.ke",
  "password": "securepassword123",
  "phone": "+254712345678"
}

// Response 201
{
  "user": {
    "id": 1,
    "email": "jane@larkinlaw.co.ke",
    "first_name": "Jane",
    "last_name": "Larkin",
    "role": "managing_partner",
    "firm": { "id": 1, "name": "Larkin & Associates" }
  },
  "tokens": {
    "access": "<jwt_access_token>",
    "refresh": "<jwt_refresh_token>"
  }
}
```

#### POST `/api/v1/auth/login/`
```json
// Request
{ "email": "jane@larkinlaw.co.ke", "password": "securepassword123" }

// Response 200
{
  "access": "<jwt_access_token>",
  "refresh": "<jwt_refresh_token>",
  "user": { "id": 1, "email": "...", "role": "managing_partner", "firm_id": 1 }
}
```

#### POST `/api/v1/auth/token/refresh/`
```json
// Request
{ "refresh": "<jwt_refresh_token>" }
// Response 200
{ "access": "<new_access_token>" }
```

#### POST `/api/v1/auth/logout/`
```json
// Request (authenticated)
{ "refresh": "<jwt_refresh_token>" }
// Response 205  (blacklists refresh token)
{}
```

#### GET `/api/v1/auth/me/`
```json
// Response 200
{
  "id": 1,
  "email": "jane@larkinlaw.co.ke",
  "first_name": "Jane",
  "last_name": "Larkin",
  "role": "managing_partner",
  "lsk_number": "LSK/A/12345",
  "phone": "+254712345678",
  "firm": { "id": 1, "name": "Larkin & Associates", "lsk_number": "LSK/F/001" }
}
```

---

### 2.2 Team endpoints (`/api/v1/team/`)
> Only managing_partner and partner can invite/manage team members.

#### GET `/api/v1/team/`
List all users in the authenticated user's firm.
```json
// Response 200
{
  "count": 4,
  "results": [
    { "id": 1, "first_name": "Jane", "last_name": "Larkin",
      "email": "jane@larkinlaw.co.ke", "role": "managing_partner",
      "lsk_number": "LSK/A/12345", "is_active": true }
  ]
}
```

#### POST `/api/v1/team/invite/`
```json
// Request
{
  "email": "john@larkinlaw.co.ke",
  "first_name": "John",
  "last_name": "Patel",
  "role": "associate",
  "lsk_number": "LSK/A/67890"
}
// Response 201 — creates user, sends invite email with temp password
{ "id": 2, "email": "john@larkinlaw.co.ke", "role": "associate" }
```

#### PATCH `/api/v1/team/{id}/`
Update role or deactivate a team member.
```json
// Request
{ "role": "partner" }
// Response 200
{ "id": 2, "role": "partner" }
```

---

### 2.3 Client endpoints (`/api/v1/clients/`)

#### GET `/api/v1/clients/`
```
Query params: ?search=name_or_email  ?is_company=true|false  ?page=1
```
```json
// Response 200
{
  "count": 24,
  "results": [
    { "id": 1, "name": "John Otieno", "email": "john@email.com",
      "phone": "+254712345678", "is_company": false,
      "matter_count": 2, "created_at": "2026-08-17T09:00:00Z" }
  ]
}
```

#### POST `/api/v1/clients/`
```json
// Request
{
  "name": "Acme Corporation Ltd",
  "email": "legal@acme.co.ke",
  "phone": "+254720000000",
  "id_number": "CPR/2019/12345",
  "is_company": true,
  "address": "Upper Hill, Nairobi"
}
// Response 201 — full client object
```

#### GET `/api/v1/clients/{id}/`
Full client detail including matter list.

#### PATCH `/api/v1/clients/{id}/`  |  DELETE `/api/v1/clients/{id}/`

---

### 2.4 Matter endpoints (`/api/v1/matters/`)

#### GET `/api/v1/matters/`
```
Query params: ?status=open|closed  ?practice_area=litigation
              ?client_id=1  ?lead_attorney_id=1  ?search=title_or_ref  ?page=1
```
```json
// Response 200
{
  "count": 12,
  "results": [
    {
      "id": 1,
      "reference": "ADV/2026/001",
      "title": "Smith v. Acme Corp",
      "cause_number": "HCCC/123/2026",
      "status": "open",
      "practice_area": "litigation",
      "client": { "id": 1, "name": "John Smith" },
      "lead_attorney": { "id": 1, "first_name": "Jane", "last_name": "Larkin" },
      "court": "High Court Nairobi",
      "opened_date": "2026-08-01",
      "updated_at": "2026-08-17T09:00:00Z"
    }
  ]
}
```

#### POST `/api/v1/matters/`
```json
// Request
{
  "title": "Smith v. Acme Corp",
  "cause_number": "HCCC/123/2026",
  "client_id": 1,
  "lead_attorney_id": 1,
  "practice_area": "litigation",
  "court": "High Court Nairobi",
  "judge": "Hon. Justice Kariuki",
  "description": "Breach of contract claim",
  "team_ids": [2, 3]
}
// Response 201 — full matter object
// reference auto-generated: ADV/2026/001
```

#### GET `/api/v1/matters/{id}/`
Full matter detail including team, recent events, recent notes.

#### PATCH `/api/v1/matters/{id}/`  |  DELETE `/api/v1/matters/{id}/`

#### GET `/api/v1/matters/{id}/notes/`
#### POST `/api/v1/matters/{id}/notes/`
```json
// Request
{ "body": "Client confirmed settlement position..." }
// Response 201
{ "id": 1, "body": "...", "author": { "id": 1, "first_name": "Jane" }, "created_at": "..." }
```

---

### 2.5 Calendar endpoints (`/api/v1/calendar/`)

#### GET `/api/v1/calendar/events/`
```
Query params: ?matter_id=1  ?date_from=2026-08-01  ?date_to=2026-08-31
              ?event_type=hearing  ?assigned_to_me=true  ?page=1
```
```json
// Response 200
{
  "count": 7,
  "results": [
    {
      "id": 1,
      "title": "Smith v. Acme — Motion Hearing",
      "event_type": "hearing",
      "date": "2026-08-18",
      "start_time": "09:30:00",
      "end_time": "11:00:00",
      "all_day": false,
      "court": "High Court Nairobi, Courtroom 4",
      "judge": "Hon. Justice Kariuki",
      "status": "scheduled",
      "source": "manual",
      "matter": { "id": 1, "reference": "ADV/2026/001", "title": "Smith v. Acme Corp" },
      "assigned_to": [{ "id": 1, "first_name": "Jane", "last_name": "Larkin" }],
      "notes": "Bring certified copies"
    }
  ]
}
```

#### POST `/api/v1/calendar/events/`
```json
// Request
{
  "matter_id": 1,
  "title": "Smith v. Acme — Motion Hearing",
  "event_type": "hearing",
  "date": "2026-08-18",
  "start_time": "09:30:00",
  "all_day": false,
  "court": "High Court Nairobi, Courtroom 4",
  "assigned_to_ids": [1],
  "notes": "Bring certified copies"
}
// Response 201
```

#### PATCH `/api/v1/calendar/events/{id}/`
#### DELETE `/api/v1/calendar/events/{id}/`

#### POST `/api/v1/calendar/sync/jicms/`
Trigger JICMS causelist sync for the firm.
```json
// Response 202
{ "status": "sync_started", "task_id": "abc123" }
```

---

### 2.6 Billing endpoints (`/api/v1/billing/`)

#### GET `/api/v1/billing/time-entries/`
```
Query params: ?matter_id=1  ?attorney_id=1  ?is_billed=false  ?date_from=  ?date_to=
```

#### POST `/api/v1/billing/time-entries/`
```json
// Request
{
  "matter_id": 1,
  "description": "Drafted motion to compel",
  "date": "2026-08-17",
  "hours": "2.50",
  "rate_kes": 1500000   // KES 15,000.00 per hour in cents
}
// Response 201
```

#### GET `/api/v1/billing/invoices/`
#### POST `/api/v1/billing/invoices/`
```json
// Request
{
  "matter_id": 1,
  "amount_kes": 7500000,   // KES 75,000.00
  "vat_kes": 1200000,      // KES 12,000.00
  "issued_date": "2026-08-17",
  "due_date": "2026-08-31",
  "notes": "Professional fees — August 2026"
}
// Response 201 — invoice_number auto-generated: INV/2026/001
```

#### POST `/api/v1/billing/invoices/{id}/send/`
Sends invoice to client via email + WhatsApp.
```json
// Response 200
{ "status": "sent", "sent_at": "2026-08-17T10:00:00Z" }
```

#### POST `/api/v1/billing/mpesa/stk-push/`
Initiate M-Pesa STK push for an invoice.
```json
// Request
{
  "invoice_id": 1,
  "phone_number": "254712345678"  // no + prefix
}
// Response 202
{
  "checkout_request_id": "ws_CO_17082026_...",
  "message": "STK push initiated. Awaiting customer confirmation."
}
```

#### POST `/api/v1/billing/mpesa/callback/`
**Internal — Daraja callback URL. Dev B owns this.**
Not called by frontend. Safaricom POSTs here after payment.

#### GET `/api/v1/billing/trust/`
#### POST `/api/v1/billing/trust/`
Trust account ledger entries — Cap 16 compliant.

---

## 3. Frontend component contracts

> Dev C consumes these. Shapes are what the API returns — no transformation needed.

### 3.1 Auth token storage
```
Access token:  sessionStorage key = "ao_access"
Refresh token: localStorage key  = "ao_refresh"
Axios default header set on login:
  axios.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`
```

### 3.2 Core TypeScript types
```typescript
// All frontend components must use these types — no inline type definitions.
// File: src/types/index.ts

export type Role =
  | 'managing_partner' | 'partner'
  | 'associate' | 'paralegal' | 'support';

export type PracticeArea =
  | 'litigation' | 'conveyancing' | 'corporate'
  | 'employment' | 'family' | 'succession'
  | 'criminal' | 'land' | 'ip' | 'other';

export type MatterStatus = 'open' | 'on_hold' | 'closed' | 'archived';
export type EventType    = 'hearing' | 'deadline' | 'deposition' | 'mediation' | 'mention' | 'other';
export type EventStatus  = 'scheduled' | 'completed' | 'adjourned' | 'cancelled';
export type EventSource  = 'manual' | 'jicms';
export type InvoiceStatus= 'draft' | 'sent' | 'paid' | 'overdue' | 'cancelled';

export interface Firm {
  id: number; name: string; lsk_number?: string;
}
export interface UserSummary {
  id: number; first_name: string; last_name: string; email: string; role: Role;
}
export interface User extends UserSummary {
  lsk_number?: string; phone?: string; firm: Firm;
}
export interface ClientSummary {
  id: number; name: string; email?: string; phone?: string;
  is_company: boolean; matter_count: number;
}
export interface MatterSummary {
  id: number; reference: string; title: string; cause_number?: string;
  status: MatterStatus; practice_area: PracticeArea;
  client: ClientSummary; lead_attorney?: UserSummary;
  court?: string; opened_date: string; updated_at: string;
}
export interface CourtEvent {
  id: number; title: string; event_type: EventType;
  date: string; start_time?: string; end_time?: string; all_day: boolean;
  court?: string; judge?: string; location?: string;
  status: EventStatus; source: EventSource; jicms_id?: string;
  matter: MatterSummary; assigned_to: UserSummary[]; notes?: string;
}
export interface Invoice {
  id: number; invoice_number: string; status: InvoiceStatus;
  amount_kes: number; vat_kes: number;
  issued_date: string; due_date: string;
  matter: MatterSummary; notes?: string;
}

// Money display helper — always use this, never raw division
export const formatKES = (cents: number): string =>
  `KES ${(cents / 100).toLocaleString('en-KE', { minimumFractionDigits: 2 })}`;
```

### 3.3 API base client
```typescript
// src/lib/api.ts — Dev C sets this up Week 1
import axios from 'axios';

const api = axios.create({ baseURL: process.env.NEXT_PUBLIC_API_URL });

// Attach token
api.interceptors.request.use(config => {
  const token = sessionStorage.getItem('ao_access');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-refresh on 401
api.interceptors.response.use(
  res => res,
  async err => {
    if (err.response?.status === 401) {
      const refresh = localStorage.getItem('ao_refresh');
      if (refresh) {
        const { data } = await axios.post('/api/v1/auth/token/refresh/', { refresh });
        sessionStorage.setItem('ao_access', data.access);
        err.config.headers.Authorization = `Bearer ${data.access}`;
        return api(err.config);
      }
    }
    return Promise.reject(err);
  }
);

export default api;
```

---

## 4. Shared conventions

### 4.1 Money — always integers
```python
# Dev A / Dev B — Django
# Store as IntegerField, represent as KES cents × 100
amount_kes = models.IntegerField()   # 7500000 = KES 75,000.00
# Never: DecimalField for money (floating point risk)
```
```typescript
// Dev C / Dev D — Frontend
// Always use formatKES() helper. Never divide manually in components.
formatKES(7500000)  // → "KES 75,000.00"
```

### 4.2 Dates
```
- Backend stores: UTC (Django USE_TZ=True, TIME_ZONE='Africa/Nairobi')
- API returns:    ISO 8601 strings "2026-08-17T09:00:00Z"
- Frontend shows: EAT (UTC+3) using date-fns-tz or Intl.DateTimeFormat
- Date-only fields (matter opened_date, event date): "YYYY-MM-DD" string, no timezone
```

### 4.3 Multi-tenancy rule
```python
# Dev A enforces — every queryset must filter by firm
# WRONG:
Matter.objects.all()
# RIGHT:
Matter.objects.filter(firm=request.user.firm)
```

### 4.4 Error codes
```
ERR_AUTH_INVALID       — wrong credentials
ERR_AUTH_EXPIRED       — token expired
ERR_PERMISSION_DENIED  — role does not allow this action
ERR_NOT_FOUND          — resource not in this firm's data
ERR_VALIDATION         — request body invalid (detail will have field errors)
ERR_MPESA_FAILED       — Daraja API error
ERR_JICMS_UNAVAILABLE  — JICMS sync service unreachable
```

---

## 5. Sign-off

> All 4 devs confirm they have read and agree to these contracts before
> writing any feature code. Record your sign-off as a git commit:
> `git commit --allow-empty -m "chore: contracts sign-off — Dev A (Amanda)"`

| Dev | Role | Sign-off commit |
|-----|------|----------------|
| Dev A | Backend Lead | pending |
| Dev B | AI + Integrations | pending |
| Dev C | Frontend Lead | pending |
| Dev D | QA + Product | pending |

