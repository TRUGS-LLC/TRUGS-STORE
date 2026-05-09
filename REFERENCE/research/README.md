# TRUGS_STORE Research Prompts

This directory contains focused research prompts for Gemini Deep Research to inform the TRUGS_STORE feasibility study.

## Purpose
The comprehensive feasibility prompt was too expansive for a single research session. These smaller prompts can be sent independently to Gemini Deep Research, and the results will be synthesized later.

## Strategic Context (Updated 2026-02-17)

**Go is the confirmed final destination** for the entire TRUGS system. Hyperledger Fabric integration is confirmed and requires Go. The central question is no longer "Go or Python?" but "Does a Python prototype phase justify the inevitable migration cost?" Prompt 06 (Fabric feasibility in Go) is now the **critical gating research**.

## Research Prompts

### 01_go_vs_python_graph_storage.md
**Focus**: Strategic language choice — reframed as "Does Python prototype justify migration cost?"
**Key Questions**: Educational value of Python phase, open-source value, migration costs vs Go ramp-up
**Status**: ✅ COMPLETE (synthesized from Docs 02–05, reframed 2026-02-17)
**Priority**: 🔴 CRITICAL - Decision 0 gates all other work

### 02_postgresql_graph_performance.md
**Focus**: Can PostgreSQL meet performance targets?
**Key Questions**: Recursive CTE performance, JSONB indexing, scaling to 100K+ nodes, production case studies
**Status**: ✅ COMPLETE (229 lines, 41 citations)
**Priority**: 🔴 CRITICAL - Conditional GO confirmed

### 03_python_postgresql_libraries.md
**Focus**: psycopg3 vs asyncpg vs SQLAlchemy
**Key Questions**: Performance, feature support, production maturity, graph storage fit
**Status**: ✅ COMPLETE (272 lines, 32 citations)
**Priority**: 🟡 HIGH - Relevant if Python prototype path chosen

### 04_storage_abstraction_patterns.md
**Focus**: Design patterns for multi-backend storage
**Key Questions**: Protocol pattern viability, repository pattern, adapter pattern, conformance testing, Fabric mapping
**Status**: ✅ COMPLETE (261 lines, 58 citations)
**Priority**: 🟡 HIGH - Patterns inform Go interface design

### 05_python_go_migration_costs.md
**Focus**: Real-world Python → Go migration timelines
**Key Questions**: Docker/Dropbox/Stream/Reddit/Zhihu case studies, migration tax vs onboarding tax
**Status**: ✅ COMPLETE (377 lines, 38 citations)
**Priority**: 🟡 HIGH - Central evidence for Decision 0

### 06_hyperledger_fabric_go_feasibility.md ⭐ NEW
**Focus**: Is Hyperledger Fabric integration feasible in Go?
**Key Questions**: Go SDK maturity, chaincode in Go, World State as graph storage, integration architecture, production viability
**Status**: ⏳ PROMPT READY
**Priority**: 🔴 CRITICAL - Must validate before committing to Go-direct path

## Research Workflow

### Phase 1: ✅ COMPLETE — Foundation Research (Docs 01–05)
All 5 initial research documents completed with 169 total citations.

### Phase 2: ⏳ IN PROGRESS — Strategic Validation
6. **06_hyperledger_fabric_go_feasibility.md** — ⭐ **Next action: Send to Gemini Deep Research**

→ Output: GO/NO-GO on Fabric integration in Go, which finalizes Decision 0

## Using These Prompts

### For Gemini Deep Research:
1. Send prompts one at a time (or in logical pairs)
2. Each prompt is self-contained (no TRUGS terminology)
3. Expected output: Traditional research report with citations
4. Allow 2-4 hours per research session

### For TRUGS Transformation:
After receiving Gemini research reports:
1. Extract key findings, claims, sources
2. Transform into Research Branch TRUG graphs
3. Store in: `HUB_LIBRARY/HUB_TECHNOLOGY_STACK/RESEARCH/`
4. Validate with: `trugs-validate <file>.trug.json`
5. Use findings to inform AAA.md FEASIBILITY phase decisions

## Success Criteria
- All 6 prompts researched with 20+ citations each
- Fabric integration validated in Go (Prompt 06 — CRITICAL)
- Decision 0 resolved: Go-direct or Python-prototype-then-Go
- Detailed implementation plan for chosen path
- Risk assessment with mitigation strategies
- Timeline estimate for FEASIBILITY → DELIVERY

## Notes
- These prompts avoid TRUGS-specific terminology (Gemini won't know what TRUGs are)
- Focus on fundamental technical questions
- Expect traditional documents, we'll convert to TRUG graphs later
- Can be researched in parallel if multiple Gemini sessions available
