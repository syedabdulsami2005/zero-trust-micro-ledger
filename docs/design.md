> [!NOTE]
> **Project Status: Implemented & Complete**
> All phases (1-4) outlined in this document have been fully implemented.
> These documentation files have been consolidated into the docs/ directory for better organization.
# Security Operations Center Dashboard Design Specification

## Purpose
This document defines the visual and interaction design language for the local dashboard. The UI must feel like a focused SOC console for one device: stable, readable, high-contrast, and optimized for investigation.

## Tailwind Color Palette
### Base Backgrounds
- `bg-slate-950` for app shell
- `bg-slate-900` for main surfaces
- `bg-zinc-900` for cards and drawers
- `border-slate-800` for boundaries

### Healthy State Colors
- `text-teal-400`
- `bg-teal-500/10`
- `border-teal-500/30`
- `text-emerald-400`
- `bg-emerald-500/10`

### Warning Colors
- `text-amber-400`
- `bg-amber-500/10`
- `border-amber-500/30`

### Broken/Tampered Colors
- `text-rose-400`
- `text-red-400`
- `bg-red-500/10`
- `border-red-500/30`
- `shadow-red-500/20`

## Core UI Components
- Sidebar
- Alert Banner
- KPI Cards
- Live Ledger Feed
- Block Inspector
- Event Table
- Verification Panel
- Alerts List / Triage Panel
- Evidence Export Panel

## Screen-Level Design
### Overview
- KPI row
- Verification chart
- Recent alerts
- Latest events
- Critical files

### Monitored Files
- Toolbar
- Full-width file table
- Row detail drawer

### Event Stream
- Filter ribbon
- Searchable table
- Right detail drawer

### Micro-Ledger
- Left block list
- Right block inspector
- Chain relation strip

### Verification
- Summary metrics band
- Run history chart
- Failure table

### Alerts
- Severity summary row
- Main alert table
- Triage drawer

