def extract_section_text(section_el):
    """Flatten a Section element into readable text with label hierarchy."""
    parts = []

    mn = section_el.findtext("MarginalNote")
    if mn:
        parts.append(mn)

    label = section_el.findtext("Label") or ""

    # Direct text children
    for text_el in section_el.findall("Text"):
        parts.append(f"{label} {_get_all_text(text_el)}".strip())

    # Definitions at section level
    for defn in section_el.findall("Definition"):
        text_el = defn.find("Text")
        if text_el is not None:
            parts.append(_get_all_text(text_el))

    # Subsections
    for sub in section_el.findall("Subsection"):
        sub_label = sub.findtext("Label") or ""
        sub_mn = sub.findtext("MarginalNote")
        if sub_mn:
            parts.append(sub_mn)
        for text_el in sub.findall("Text"):
            parts.append(f"{sub_label} {_get_all_text(text_el)}".strip())
        # Paragraphs within subsection
        for para in sub.findall("Paragraph"):
            _extract_paragraph(para, parts, indent=1)

    # Direct paragraphs (some acts put them directly under Section)
    for para in section_el.findall("Paragraph"):
        _extract_paragraph(para, parts, indent=1)

    return "\n".join(filter(None, parts))


def _extract_paragraph(para_el, parts, indent=1):
    """Recursively extract paragraphs and subparagraphs."""
    prefix = "  " * indent
    label = para_el.findtext("Label") or ""
    for text_el in para_el.findall("Text"):
        parts.append(f"{prefix}{label} {_get_all_text(text_el)}".strip())
    for subpara in para_el.findall("Subparagraph"):
        _extract_paragraph(subpara, parts, indent=indent + 1)
    for clause in para_el.findall("Clause"):
        _extract_paragraph(clause, parts, indent=indent + 2)


def _get_all_text(el):
    """Get all text from element and children (handles XRefExternal, DefinedTermEn, etc.)."""
    return "".join(el.itertext()).strip()
