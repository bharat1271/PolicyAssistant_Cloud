"""
generate_synthetic_policy.py
────────────────────────────────────────────────────────────────────────────────
Generates a SYNTHETIC master-data governance policy document (.docx) for the
portfolio version of the Policy Assistant RAG project.

This document is entirely fictional. It mirrors the STRUCTURE of a real
internal policy doc this project was originally built around (bold section
headers, chapters, embedded rule tables, metadata lines) so the ingestion and
retrieval code can be demonstrated and explained honestly — but contains no
real company data, names, or content.

Run once:
    python generate_synthetic_policy.py

Output:
    data/MasterDataGovernancePolicy.docx
"""

from pathlib import Path
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

BASE_DIR = Path(__file__).parent
OUT_PATH = BASE_DIR / "data" / "MasterDataGovernancePolicy.docx"

doc = Document()
doc.styles["Normal"].font.name = "Calibri"
doc.styles["Normal"].font.size = Pt(11)


def title(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(20)


def header(text):
    """Bold short paragraph — this is what the parser detects as a section header."""
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(13)


def meta(text):
    """Bold metadata line (Owner/Date/Version) — parser treats these as noise, not headers."""
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(10)


def body(text):
    doc.add_paragraph(text)


def table(headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    hdr_cells = t.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = h
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = str(val)
    doc.add_paragraph("")  # spacing after table


# ─────────────────────────────────────────────────────────────────────────────
# Title page / preamble
# ─────────────────────────────────────────────────────────────────────────────

title("Master Entity Data Governance Policy")
meta("Version: 2.3")
meta("Owner: Enterprise Data Governance Team")
meta("Date: June 2026")
meta("Target Audience: Data Stewards, Curation Analysts, New Team Members")
body(
    "This document defines the rules and procedures used by the Enterprise Data "
    "Governance Team to maintain consistent, high-quality records in the "
    "organizational entity master database (\"EntityDB\"). It covers naming "
    "conventions, address capture, entity classification, hierarchy levels, "
    "relationship types, name variants, and record lifecycle management."
)

header("Purpose")
body(
    "EntityDB is the single source of truth for every organizational entity "
    "referenced across internal systems: customers, vendors, academic "
    "institutions, government bodies, and corporate subsidiaries. Consistent "
    "curation prevents duplicate records, broken links between systems, and "
    "incorrect reporting. This policy exists so that any data steward — new or "
    "experienced — can apply the same rules the same way."
)

header("Concepts")
body(
    "Entity: any organization tracked in EntityDB. EntityID: the unique "
    "identifier assigned to an entity at creation and never reused. Steward: "
    "the analyst responsible for curating a given entity record."
)

# ─────────────────────────────────────────────────────────────────────────────
# Chapter 1 — EntityNames
# ─────────────────────────────────────────────────────────────────────────────

header("EntityNames")
meta("Go back to Table of Contents")
body(
    "The EntityName field stores the official, current name of an entity. "
    "Names must be captured exactly as they appear on the entity's official "
    "registration or public-facing materials, with the following normalization "
    "rules applied."
)

header("Rules for Capturing EntityNames")
body(
    "1. Use the full legal or commonly recognized name, not an internal "
    "shorthand. Example: capture \"Meridian Health Systems\" rather than "
    "\"Meridian.\"\n"
    "2. Preserve official punctuation and capitalization (e.g., \"eBay Inc.\", "
    "\"3M Company\").\n"
    "3. Do not include legal suffixes (Inc., Ltd., GmbH) unless the entity is "
    "commonly known with the suffix attached.\n"
    "4. If the entity has a native-language name in addition to an English "
    "name, capture the native-language name as a Variant (see the Variants "
    "chapter), not as the primary EntityName.\n"
    "5. Abbreviations are only used as the primary name if the abbreviation is "
    "more widely recognized than the expanded form (e.g., \"IBM\" rather than "
    "\"International Business Machines Corporation\")."
)

header("Special Characters in EntityNames")
body(
    "Ampersands (&), hyphens, and accented characters are preserved exactly as "
    "registered. Do not substitute 'and' for '&'. Do not strip diacritics from "
    "names such as \"Nestlé\" or \"Societe Generale\"."
)
meta("Note: This rule was added after several duplicate records were created "
     "for the same entity due to inconsistent handling of special characters.")

# ─────────────────────────────────────────────────────────────────────────────
# Chapter 2 — EntityAddresses
# ─────────────────────────────────────────────────────────────────────────────

header("EntityAddresses")
body(
    "Every entity record should carry at least one verified address. Addresses "
    "are captured at the most specific level available: street, city, region/"
    "state, postal code, and country."
)

header("Country-Specific Address Formatting")
table(
    ["Country", "Formatting Rule"],
    [
        ["United States", "City, State abbreviation, ZIP code"],
        ["United Kingdom", "City, County (if applicable), Postcode"],
        ["India", "City, State, PIN code"],
        ["Germany", "Postal code precedes city name"],
        ["Japan", "Address captured in both Kanji and Romanized form"],
    ],
)

header("Affiliations Missing City Information")
body(
    "Some entities — particularly small regional offices or historical records "
    "— do not have a documented city in the source material. In these cases, "
    "do not guess or infer a city from the entity name. Instead, mark the "
    "EntityAddress field as 'City Unverified' and flag the record for review "
    "by a senior steward. Never leave the field blank, since blank fields are "
    "indistinguishable from missing-data errors during audits."
)

# ─────────────────────────────────────────────────────────────────────────────
# Chapter 3 — EntityType
# ─────────────────────────────────────────────────────────────────────────────

header("EntityType")
body(
    "Every entity must be classified into exactly one EntityType. This "
    "classification drives downstream reporting and validation rules."
)

header("EntityType Definitions")
table(
    ["EntityType", "Definition"],
    [
        ["Corporate", "A for-profit company operating independently"],
        ["Subsidiary", "A company majority-owned and controlled by a parent Corporate entity"],
        ["Government", "A national, regional, or municipal government body"],
        ["Academic", "A university, college, or degree-granting research institution"],
        ["Non-Profit", "A registered non-profit or charitable organization"],
        ["Branch Office", "A physical location of a Corporate or Subsidiary entity with no separate legal status"],
        ["Consortium", "A formal alliance of multiple independent entities operating under a shared name"],
    ],
)

# ─────────────────────────────────────────────────────────────────────────────
# Chapter 4 — Determining EntityLevel for Organizations
# ─────────────────────────────────────────────────────────────────────────────

header("Determining EntityLevel for Organizations")
body(
    "EntityLevel encodes an entity's position in its organizational hierarchy. "
    "Getting this right is critical for roll-up reporting, since an incorrect "
    "level can cause a subsidiary's data to be double-counted or dropped "
    "entirely from parent-level totals."
)

header("EntityLevel Definitions")
table(
    ["Level", "Meaning", "Example"],
    [
        ["Level 1", "Top-level parent entity with no controlling parent", "Meridian Health Systems"],
        ["Level 2", "Direct subsidiary or division of a Level 1 entity", "Meridian West Region"],
        ["Level 3", "Branch, campus, or department under a Level 2 entity", "Meridian West — Riverside Campus"],
        ["Level 4", "Sub-unit of a Level 3 entity (labs, clinics, specific offices)", "Riverside Campus — Cardiology Wing"],
    ],
)
body(
    "When in doubt, assign the level based on legal and financial reporting "
    "structure, not on physical size or headcount. A large Level 3 branch is "
    "still Level 3 even if it has more staff than the Level 2 entity above it."
)

# ─────────────────────────────────────────────────────────────────────────────
# Chapter 5 — Guidelines for RelTypes
# ─────────────────────────────────────────────────────────────────────────────

header("Guidelines for RelTypes")
body(
    "RelType records the relationship between two entities in EntityDB. Every "
    "relationship must use exactly one of the following approved RelType "
    "values."
)

header("Approved RelType Values")
table(
    ["RelType", "Definition"],
    [
        ["Parent-Of", "Entity A directly controls Entity B"],
        ["Subsidiary-Of", "Entity A is majority-owned by Entity B"],
        ["Merged-With", "Entity A and Entity B combined into a single surviving entity"],
        ["Acquired-By", "Entity A was purchased by Entity B and ceased independent operation"],
        ["Renamed-To", "Entity A changed its legal name and is now recorded as Entity B"],
        ["Alias-Of", "Entity A and Entity B refer to the same real-world organization"],
        ["Predecessor-Of", "Entity A operated before, and was succeeded by, Entity B"],
        ["Successor-Of", "Entity A began operating in place of a discontinued Entity B"],
        ["Jointly-Owned-By", "Entity A is owned collectively by two or more parent entities"],
    ],
)
meta("Owner: Enterprise Data Governance Team")
body(
    "A common mistake is confusing 'Jointly-Owned-By' with simple ownership "
    "questions about who owns or maintains a record — those are steward "
    "assignment questions, not RelType questions, and are answered in the "
    "document metadata (see the Owner field at the top of each chapter), not "
    "in the RelType table."
)

# ─────────────────────────────────────────────────────────────────────────────
# Chapter 6 — Variants
# ─────────────────────────────────────────────────────────────────────────────

header("Variants")
body(
    "A Variant is any alternate name an entity is known by: a native-language "
    "name, a former legal name, a common abbreviation, or a 'doing business "
    "as' (DBA) name. Variants are searchable but never used as the primary "
    "EntityName."
)

header("Capturing a Variant")
body(
    "1. Add the alternate name to the Variants table linked to the EntityID.\n"
    "2. Tag the variant type: Native-Language, Former-Name, Abbreviation, or "
    "DBA.\n"
    "3. If the variant includes a city or region qualifier (e.g., a regional "
    "trading name), capture the city alongside the variant so it can be "
    "distinguished from similarly named entities elsewhere.\n"
    "4. Variants do not require their own EntityID — they are always attached "
    "to an existing entity record."
)

# ─────────────────────────────────────────────────────────────────────────────
# Chapter 7 — Process for Deprecating Entities
# ─────────────────────────────────────────────────────────────────────────────

header("Process for Deprecating Entities")
body(
    "Entities are deprecated (marked inactive) rather than deleted, so that "
    "historical references in linked systems continue to resolve correctly."
)

header("Deprecation Steps")
table(
    ["Step", "Action"],
    [
        [1, "Confirm the entity has ceased operations, merged, or was created in error"],
        [2, "Identify the surviving entity, if any, and record the RelType linking the two (Merged-With, Acquired-By, or Renamed-To)"],
        [3, "Set the entity status flag to 'Deprecated'"],
        [4, "Redirect any incoming references to the surviving entity's EntityID"],
        [5, "Log the deprecation reason and date in the audit trail"],
        [6, "Notify downstream system owners if the entity had greater than 100 linked records"],
    ],
)
meta("Note: Deprecated entities are never removed from EntityDB. Removal breaks "
     "historical audit trails.")

# ─────────────────────────────────────────────────────────────────────────────
# Chapter 8 — Multi-Location Organizations
# ─────────────────────────────────────────────────────────────────────────────

header("Multi-Location Organizations")
body(
    "Large entities that operate as a single legal organization across "
    "multiple physical locations (a 'system') require special handling to "
    "avoid one location's data being mistaken for the whole organization's "
    "data, or vice versa."
)

header("System-Level Entities")
body(
    "When an organization operates as a system of otherwise-independent "
    "campuses or branches under one shared governing body, create a Level 1 "
    "entity for the system itself, and a Level 2 entity for each member "
    "location. Do not merge the system and its members into a single record — "
    "this causes reporting errors when a single member location leaves the "
    "system."
)

header("Multi-Campus Entities")
body(
    "A multi-campus entity (for example, a university with several physical "
    "campuses in different cities) should have one Level 1 parent entity and "
    "a Level 2 entity per campus, each with its own EntityAddress. If a "
    "campus is later closed, deprecate the Level 2 entity for that campus but "
    "retain the Level 1 parent."
)

# ─────────────────────────────────────────────────────────────────────────────
# Chapter 9 — Change Log
# ─────────────────────────────────────────────────────────────────────────────

header("Change Log")
meta("V 2.3 — Added Consortium EntityType and clarified Jointly-Owned-By rules")
meta("V 2.2 — Added Multi-Campus Entities chapter")
meta("V 2.1 — Clarified special character handling in EntityNames")
meta("V 2.0 — Migrated from paper process to EntityDB digital record")

doc.save(str(OUT_PATH))
print(f"Saved synthetic policy document -> {OUT_PATH}")
print(f"Paragraphs: {len(doc.paragraphs)} | Tables: {len(doc.tables)}")
