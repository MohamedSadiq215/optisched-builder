# 📅 OptiSched Builder

**Dynamic workforce schedule optimizer powered by OR-Tools CP-SAT + Streamlit + openpyxl**

---

## Features

| Category | Details |
|----------|---------|
| **Shift Registry** | Full CRUD — create, edit, delete shifts with configurable start/end times |
| **Agent Profiles** | Gender, eligibility, fixed-schedule assignments, per-shift access control |
| **Distribution Matrix** | Editable MAX / MIN caps per shift per weekday with auto-derived Max OFF/day |
| **Calendar Events** | Tag dates with event names shown in the schedule banner |
| **CP-SAT Solver** | OR-Tools engine with all hard constraints (see below) |
| **Validation Dashboard** | Real-time Reconciled / Discrepancy status with violation callouts |
| **Excel Export** | Two-tab `.xlsx` with coloured cells, frozen panes, compliance heatmap |

---

## Constraints Enforced by the Solver

1. **Fixed schedule assignments** — lock specific agents to shifts on specific days
2. **Gender / eligibility filtering** — female-only shifts (e.g. Shift MS)
3. **12-hour minimum rest rule** — e.g. Shift B (ends 01:00) → Shift A (starts 07:00) is blocked
4. **5-day consecutive work ceiling** — 6th consecutive day forced to OFF
5. **Previous-month boundary buffer** — tail assignments from last month prevent cross-boundary violations
6. **Daily min/max caps** — per shift per weekday, read live from the distribution matrix

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/<your-username>/optisched-builder.git
cd optisched-builder

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
streamlit run app.py
```

---

## Project Structure

```
optisched-builder/
├── app.py                  # Streamlit entry point
├── state.py                # Session state initialisation & defaults
├── requirements.txt
├── ui/
│   ├── sidebar.py          # All configuration panels + Generate button
│   ├── calendar.py         # Horizontal event calendar banner
│   ├── matrix.py           # Interactive coloured schedule matrix
│   ├── validation.py       # Pre-flight validation dashboard
│   └── export.py           # Excel export button
└── engine/
    ├── solver.py            # CP-SAT model + post-solve validator + coverage builder
    └── excel.py             # openpyxl two-tab workbook generator
```

---

## Configuration Guide

### Shift Registry defaults

| Shift | Start | End | Working |
|-------|-------|-----|---------|
| A | 07:00 | 16:00 | ✅ |
| MS | 11:00 | 20:00 | ✅ |
| B | 16:00 | 01:00 | ✅ |
| C | 00:00 | 09:00 | ✅ |
| OFF | — | — | ❌ |
| AL | — | — | ❌ |

### Agent Profile columns

| Column | Description |
|--------|-------------|
| Name | Unique agent identifier |
| Gender | M / F (used for eligibility rules) |
| Fixed Shift | Leave blank for dynamic assignment |
| Fixed Days | e.g. `Mon-Fri`, `Sat,Sun` |
| Shift Access | Comma-separated shift names the agent can be assigned |

### Distribution Matrix

- **MAX caps** — absolute ceiling per shift per weekday
- **MIN required** — mandatory floor; solver will reject infeasible combinations
- **Max OFF/day** — auto-calculated: Total Agents − Σ(MIN caps for that weekday)

---

## Excel Export Tabs

**Tab 1 — Master Schedule**
- Row 1: title
- Row 2: calendar event banner (gold background for days with events)
- Row 3: day-of-week abbreviations
- Row 4: day numbers (dark navy header)
- Rows 5+: agent assignments with pastel conditional fills
- Frozen panes at B5

**Tab 2 — Coverage & Compliance**
- Actual counts per shift per day
- 🟢 green = within bounds, 🟡 yellow = below MIN, 🔴 red = above MAX
- MIN and MAX reference tables below the counts
- Frozen panes at B3

---

## Editing This Project

This repository is maintained as a live reference. Open an issue or start a conversation in the linked Claude chat to request changes, fixes, or new features.
