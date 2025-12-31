# Analytics Architecture

## Overview

UNIPA Reminder App adopts an **asset-based analytics architecture**
designed for **auditability, explainability, and long-term M&A resilience**.

All analytical information shown in the UI is derived from **immutable assets**.
The frontend never re-computes analytical results and never infers outcomes.

This architecture prioritizes:
- Deterministic behavior
- Historical reproducibility
- Safe refactoring
- External audit readiness

---

## Core Design Principles

### 1. Single Source of Truth (SSOT)

Each analytical fact is recorded exactly once.
No analytical truth is duplicated, inferred, or re-derived.

### 2. Immutable Assets

All analytics-related data is **append-only**.
Once written, assets are never overwritten or recalculated.

### 3. Read-only Analytics

The frontend **never performs analytical computation**.
It only selects and renders pre-computed assets.

### 4. Audit-first Design

Every improvement, recommendation, and decision must be explainable
by historical assets without executing business logic.

### 5. M&A-ready Architecture

All analytical conclusions can be reconstructed
from stored assets alone, making due diligence and handover safe.

---

## Asset Types

### OutcomeLog

Represents the truth at the moment a task deadline is reached.

- Records whether a task was completed or missed
- Immutable once created
- Serves as the ultimate ground truth for task outcomes

OutcomeLogs are never recalculated, even if task metadata changes later,
ensuring historical consistency and audit safety.

---

### ActionAppliedEvent

Represents an explicit user decision to apply a suggested action.

- Records *what* was applied, *when*, and *why*
- Stores optional metadata such as patch details and reasoning keys
- Append-only event asset

This asset captures **intent**, not outcome.

---

### ActionEffectivenessSnapshot

Represents a frozen analytical view computed from
OutcomeLogs and ActionAppliedEvents at a specific point in time.

- Versioned by `computed_at`
- Immutable once generated
- Never updated or re-computed

Snapshots are the **only** source used for analytics rendering in the UI.

---

## Data Flow

User Action
→ ActionAppliedEvent (event asset)
→ (asynchronous backend processing)
→ ActionEffectivenessSnapshot (immutable analytical asset)
→ Frontend read-only rendering

The frontend never triggers analytical computation.
It only chooses **which snapshot to display**.

---

## Frontend Responsibilities

The frontend is responsible for:

- Fetching analytical assets (snapshots and events)
- Rendering differences between immutable snapshots
- Displaying audit-friendly representations
- Providing traceability between actions and outcomes

The frontend must **never**:
- Recalculate metrics
- Infer outcomes
- Mutate analytical data

---

## Auditability and Explainability

For any analytical view, the system can answer:

- Which snapshot is being displayed
- When it was computed
- Which snapshot it is compared against
- Which actions were applied before that snapshot
- Why those actions were chosen

All answers are derived from stored assets alone.

---

## Why This Architecture Matters

This design enables:

- Full historical auditability
- Deterministic analytics behavior
- Safe refactoring and extension
- Reliable M&A due diligence
- Future compatibility with AI-driven optimization

The system favors **clarity over cleverness**.

---

## Explicit Non-Goals

This architecture explicitly avoids:

- Recomputing analytics in the frontend
- Overwriting historical outcomes
- Implicit or inferred decision logs
- Time-dependent calculations without provenance
- Magic numbers without recorded context

---

## Summary

UNIPA Reminder App treats analytics as **assets**, not computations.

By separating events, outcomes, and analytical snapshots,
the system remains robust, explainable, and safe to evolve.

This design allows both humans and machines
to reason about improvements with confidence.
