from lxml import etree
from etl.text_extractor import extract_section_text

LIMS_NS = "http://justice.gc.ca/lims"


def _lims(attr):
    """Helper: get lims-namespaced attribute."""
    return f"{{{LIMS_NS}}}{attr}"


def parse_law_file(xml_path, law_type, language):
    """Parse one XML file into a law dict + list of section dicts."""
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    # Parse <Identification>
    ident = root.find("Identification")
    if ident is None:
        raise ValueError(f"No <Identification> element found in {xml_path}")

    law_data = {
        "code": _get_code(ident, law_type, xml_path),
        "short_title_en": (
            ident.findtext("ShortTitle")
            or ident.findtext("LongTitle")
            or xml_path.stem
        ),
        "long_title_en": ident.findtext("LongTitle"),
        "in_force": root.get("in-force", "yes") == "yes",
        "pit_date": _parse_date(root.get(_lims("pit-date"))),
        "last_amended": _parse_date(root.get(_lims("lastAmendedDate"))),
        "enabling_act_code": _get_enabling_act(ident),
    }

    # Parse <Body> → walk for Sections
    sections = []
    body = root.find("Body")
    if body is not None:
        _walk_body(body, sections, language)

    # Parse <Schedule> sections
    for schedule in root.iter("Schedule"):
        _walk_schedule(schedule, sections, language)

    return law_data, sections


def _parse_date(date_str):
    """Parse a date string, returning None if invalid or empty."""
    if not date_str:
        return None
    # Dates in the XML can be 'YYYY-MM-DD' or sometimes malformed
    try:
        from datetime import date
        parts = date_str.strip().split("-")
        if len(parts) == 3:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        pass
    return None


def _get_code(ident, law_type, xml_path):
    """Extract the law code (e.g., 'A-1', 'SOR-97-175')."""
    if law_type == "act":
        chapter = ident.find(".//ConsolidatedNumber")
        if chapter is not None and chapter.text:
            return chapter.text.strip()
        # Fallback: use the filename stem
        return xml_path.stem
    # Regulations use InstrumentNumber
    inst = ident.findtext("InstrumentNumber")
    if inst:
        return inst.strip().replace(",", "").replace(" ", "")
    return xml_path.stem


def _get_enabling_act(ident):
    """For regulations: extract the enabling act code from XRefExternal."""
    ea = ident.find("EnablingAuthority")
    if ea is not None:
        xref = ea.find("XRefExternal")
        if xref is not None:
            return xref.get("link")
    return None


def _walk_body(body, sections, language):
    """Walk the Body tree, tracking Heading context, extracting Sections."""
    current_heading = None
    current_part_label = None
    current_part_title = None

    for el in body:
        tag = etree.QName(el.tag).localname if "{" in el.tag else el.tag

        if tag == "Heading":
            level = el.get("level", "1")
            title = el.findtext("TitleText") or el.findtext("Label") or ""
            label = el.findtext("Label") or ""
            if level == "1":
                current_part_label = label
                current_part_title = title
            current_heading = title

        elif tag == "Section":
            section = _parse_section(el, language)
            section["heading"] = current_heading
            section["part_label"] = current_part_label
            section["part_title"] = current_part_title
            sections.append(section)

        elif tag in ("Part", "Division", "Subdivision", "Chapter"):
            # Track heading/part context at this level before recursing
            part_heading = el.findtext("Heading/TitleText") or el.findtext("Heading/Label")
            part_label = el.findtext("Heading/Label") or el.get("label")
            if part_heading or part_label:
                current_part_label = part_label or current_part_label
                current_part_title = part_heading or current_part_title
                current_heading = part_heading or current_heading
            _walk_body(el, sections, language)


def _parse_section(section_el, language):
    """Parse a single <Section> node into a dict."""
    lims_id = section_el.get(_lims("id"))
    label = section_el.findtext("Label") or ""
    marginal_note = section_el.findtext("MarginalNote") or ""

    content_text = extract_section_text(section_el)
    content_xml = etree.tostring(section_el, encoding="unicode", pretty_print=True)

    # Extract definitions
    definitions = []
    for defn in section_el.iter("Definition"):
        term_en = defn.findtext(".//DefinedTermEn")
        term_fr = defn.findtext(".//DefinedTermFr")
        if term_en or term_fr:
            definitions.append({"term_en": term_en, "term_fr": term_fr})

    # Extract cross-references
    cross_refs = []
    for xref in section_el.iter("XRefExternal"):
        cross_refs.append({
            "link": xref.get("link"),
            "type": xref.get("reference-type"),
            "text": xref.text or "",
        })

    # Determine chunk type
    chunk_type = "definition" if definitions else "section"

    # Rough token count (words / 0.75)
    token_count = int(len(content_text.split()) / 0.75) if content_text else 0

    return {
        "lims_id": lims_id,
        "label": label,
        "marginal_note": marginal_note,
        "content_text": content_text or f"Section {label}",
        "content_xml": content_xml,
        "chunk_type": chunk_type,
        "definitions": definitions,
        "cross_refs": cross_refs,
        "token_count": token_count,
    }


def _walk_schedule(schedule_el, sections, language):
    """Extract sections from Schedule nodes."""
    heading_text = (
        schedule_el.findtext(".//ScheduleFormHeading/Label")
        or schedule_el.findtext(".//Heading/TitleText")
        or "Schedule"
    )
    for section_el in schedule_el.iter("Section"):
        section = _parse_section(section_el, language)
        section["chunk_type"] = "schedule"
        section["heading"] = heading_text
        sections.append(section)
