# Azure Release Verification & Synthetic Monitoring Platform  

---

## 1. Overview

This project implements a **realistic, enterprise-grade release verification platform** on Microsoft Azure. The platform is designed to validate the health, correctness, and performance of an internal application after deployment using automated verification, scalable execution, and audit-ready evidence.

The solution is **infrastructure-first and operations-focused**, intentionally avoiding unnecessary application complexity. It mirrors how platform, cloud, and reliability teams validate internal services in production environments.

The system continuously verifies a deployed API, scales verification workloads during release bursts, securely stores immutable verification evidence, and enforces identity- and network-based access controls.

---

## 2. High-Level Purpose

The platform enables infrastructure and platform teams to:

- Deploy and operate an internal web API
- Continuously verify service availability and correctness
- Measure performance characteristics (latency)
- Scale verification workloads under demand
- Securely store verification evidence
- Enforce least-privilege access and network isolation
- Provide audit-ready proof of operational correctness

This aligns naturally with **AZ-104 (Azure Administrator)** responsibilities and reflects real enterprise operational patterns.

---

## 3. Core Concept (Mental Model)

> “We operate a security intelligence service.  
> We run an internal verification platform that continuously checks it, scales under load, and stores evidence for release validation and audit.”

The system is divided into **three active components** and **three supporting components**.

---

## 4. Architecture Overview

### Active Components

1. **Target Application**  
   The service being validated.

2. **Verifier Service**  
   A control-plane service that performs validation logic and writes evidence.

3. **Execution Layer (VM Scale Set)**  
   Scalable workers that trigger verification.

### Supporting Components

4. **Azure Storage (Blob)**  
   Immutable evidence store.

5. **Azure Networking**  
   Private endpoints, subnets, DNS, and access restrictions.

6. **Microsoft Entra ID (Azure AD)**  
   Identity, RBAC, and separation of duties.

---

## 5. Target Application (Phase 1)

### Purpose
The target application represents an **internal Security Intelligence API** that aggregates breach data from Have I Been Pwned (HIBP).

### Platform
- Azure App Service (Linux)
- Python 3.11
- Flask + gunicorn
- Deployed via Azure CLI (ZIP deploy)

### Endpoints

| Endpoint | Purpose |
|--------|---------|
| `/health` | Liveness check |
| `/ready` | Readiness based on cache/API availability |
| `/version` | Application metadata |
| `/breaches` | Fetches and caches breach data |

### Design Notes
- In-memory TTL cache (default 30 minutes)
- Graceful degradation using stale cache
- Explicit production startup command
- No secrets stored in code

### Enterprise Realism
- Mirrors internal wrapper APIs used by security teams
- Exposes operational endpoints required for verification
- Designed to be validated externally, not trusted blindly

---

## 6. Verifier Service (Phase 2)

### Purpose
The Verifier is a **dedicated control-plane service** responsible for validating the target application and producing structured verification evidence.

### Platform
- Azure App Service (Linux, containerized)
- Container image stored in Azure Container Registry (ACR)
- System-assigned Managed Identity

### Responsibilities
- Call the target `/breaches` endpoint
- Validate:
  - HTTP status
  - JSON response
  - latency threshold
- Generate structured evidence
- Write evidence to Azure Blob Storage
- Return pass/fail status to the caller

### Key Design Decisions
- Verifier is **stateless**
- Workers do not write to storage directly
- Evidence format is consistent and centralized
- No secrets, keys, or connection strings used

### Storage Access
- Uses `DefaultAzureCredential`
- RBAC-based data-plane permissions
- Writes only to `results-raw/`

---

## 7. Evidence Storage (Azure Blob Storage)

### Structure

```bash
results-raw/
└── YYYY/MM/DD/<timestamp>-<check_id>.json
results-summary/
└── (reserved for future rollups)
```

### Security Controls
- Public network access disabled
- HTTPS only, TLS 1.2 enforced
- Access via Private Endpoint
- Private DNS resolution inside the VNet
- RBAC enforced for data-plane access

### Role Separation
- **Writer:** Verifier Managed Identity
- **Readers:** Human roles (Platform Engineers)
- **No deletes or overwrites**

### Purpose
Blob Storage acts as the **system of record** for release verification and audit review.

---

## 8. Execution Layer (Phase 3)

### Platform
- Azure Virtual Machine Scale Set (Uniform)
- Ubuntu Linux
- Autoscaling enabled (1–5 instances)

### Worker Behavior
- Each VM is an independent worker
- Periodically triggers: 
  ```bash
  POST /verify/breaches
  ```
- No local state
- No direct storage access

### Bootstrapping
- VMSS Custom Script Extension
- Script pulled from GitHub
- Installs dependencies
- Creates cron job
- Ensures repeatability on scale-out

### Autoscaling
- CPU-based scaling rules
- Scale-out and scale-in verified using **evidence volume**, not assumptions

### Enterprise Pattern
- Centralized validation logic
- Horizontally scalable execution
- Workers treated as disposable

---

## 9. Network Security & Isolation (Phase 4)

### VNet Design
- Private subnets
- No public exposure for internal services

### Key Controls
- Storage accessed only via Private Endpoint
- Private DNS (`privatelink.blob.core.windows.net`)
- Verifier App Service VNet Integration
- Verifier inbound restricted to VMSS subnet
- External calls receive `403 Forbidden`

### Validation
- Evidence writes succeed only via private path
- Jumpbox/laptop access blocked
- VMSS workers continue to operate normally

---

## 10. Identity & Access Control

### Managed Identity
- Verifier uses system-assigned Managed Identity
- No secrets anywhere in the platform

### Human Access (Final Phase)

#### Entra ID Group
- **Name:** `Platform-Engineers-Verification-Readers`

#### Sample User
- **User:** `platform.engineer@example.com`
- Member of the above group

#### RBAC Assignments

| Scope | Role |
|-----|------|
| Resource Group | Reader |
| Storage Container (`results-raw`) | Storage Blob Data Reader |

### Result
Platform Engineers can:
- View resources (read-only)
- List and download verification evidence
- Validate releases using evidence

They **cannot**:
- Modify infrastructure
- Change verification logic
- Write or delete evidence

---

## 11. Roles & Responsibilities

### Cloud / Infrastructure Engineering
- Designs and maintains the platform
- Owns networking, identity, scaling, and storage
- Ensures verification system reliability

### Platform Engineering / SRE
- Consumes verification evidence
- Reviews post-deployment results
- Makes release go/no-go decisions
- Operates with read-only access

### Security / Audit (Oversight)
- Reviews access controls and evidence
- Validates network isolation and RBAC
- Uses storage as audit source of truth

---

## 12. Operational Workflow

1. Application is deployed
2. VMSS workers trigger verification
3. Verifier validates target behavior
4. Evidence is written to private Blob Storage
5. Platform Engineers review results
6. Release health is confirmed or escalated

---

## 13. AZ-104 Skills Demonstrated

- Azure App Service (code + containers)
- Azure Container Registry
- Managed Identity
- RBAC (control plane vs data plane)
- Virtual Networks and subnets
- VM Scale Sets and autoscaling
- Private Endpoints and Private DNS
- Secure PaaS-to-PaaS communication
- CLI-first provisioning and validation

---

## 14. Design Principles

- Infrastructure-first
- Evidence over assumptions
- Least privilege everywhere
- Stateless and scalable components
- No unnecessary services
- Enterprise realism over exam checklists

---

## 15. Project Status

**Status:** Complete and production-aligned

**Outcome:**  
A secure, scalable, and auditable release verification platform that mirrors real enterprise platform engineering practices.

This project is intentionally designed to **ship as-is**, with optional future enhancements (summaries, alerts, dashboards) clearly separated from core functionality.

