from __future__ import annotations

import re

from fir.instantiate.render import _ACT_LABEL, _val
from fir.schema.if1 import ExtractedField, FirRecord, Person


def _escape(value: object) -> str:
    text = str(value).strip().replace('\r', ' ').replace('\n', ' ')
    for char in ('\\', '`', '*', '_', '[', ']', '<', '>', '|'):
        text = text.replace(char, f'\\{char}')
    text = re.sub(r'^([#+-])', r'\\\1', text)
    text = re.sub(r'^(\d+)([.)])', r'\1\\\2', text)
    return text or '—'


def _field(value: ExtractedField, annotate: bool) -> str:
    shown = '—' if not value.is_filled else _val(value, annotate)
    if value.officer_note:
        shown += f' · Officer note: {value.officer_note}'
    return _escape(shown)


def _table(rows: list[tuple[str, str]]) -> list[str]:
    return ['| Detail | Value |', '| --- | --- |', *(f'| {_escape(label)} | {value} |' for label, value in rows), '']


def _person(person: Person, annotate: bool) -> list[str]:
    return _table([
        ('Name', _field(person.name, annotate)),
        (f"{person.relative_type.title()}'s name" if person.relative_type else "Father's / husband's name", _field(person.relative_name, annotate)),
        ('Date / year of birth', _field(person.dob_or_age, annotate)),
        ('Nationality', _field(person.nationality, annotate)),
        ('Passport number', _field(person.passport.number, annotate)),
        ('Passport date and place of issue', _field(person.passport.date_place_of_issue, annotate)),
        ('Occupation', _field(person.occupation, annotate)),
        ('Address', _field(person.address, annotate)),
        ('Contact', _field(person.contact, annotate)),
    ])


def render_if1_markdown(rec: FirRecord, *, annotate: bool = True, source_ta: str = '', source_en: str = '', from_audio: bool = False) -> str:
    title = 'Community Service Register — advisory' if rec.status == 'csr_advisory' else 'First Information Report'
    lines = [
        f'# {title}',
        'Form IF-1 · Section 173, BNSS 2023',
        '',
        '> **DRAFT — officer review required.** This document has not been filed or verified. Machine-filled fields, legal suggestions and both speech outputs must be checked against the original account.',
        '',
    ]
    lines += _table([
        ('Record ID', _escape(rec.record_id)),
        ('Status', _escape(rec.status.replace('_', ' ').title())),
        ('Document version', _escape(rec.document_version)),
        ('Schema', _escape(rec.schema_version)),
        ('Machine-filled fields', _escape(len(rec.machine_filled_fields()))),
    ])

    lines += ['## 1. Jurisdiction and registration', '']
    lines += _table([
        ('State', _escape(rec.jurisdiction.state)),
        ('District', _field(rec.jurisdiction.district, annotate)),
        ('Police station', _field(rec.jurisdiction.police_station, annotate)),
        ('P.S. code', _escape(rec.jurisdiction.ps_code or '—')),
        ('Year', _escape(rec.fir_year or '—')),
        ('FIR number', _escape(rec.fir_number or '—')),
        ('FIR date', _escape(rec.fir_date or '—')),
    ])

    lines += ['## 2. Acts and sections', '']
    if not rec.acts_sections:
        lines += ['No section has been applied. Officer to determine.', '']
    for index, section in enumerate(rec.acts_sections, 1):
        lines += [f'### {index}. {_escape(_ACT_LABEL.get(section.act, section.act))}, section {_escape(section.section)}', '']
        lines += _table([
            ('Offence / description', _escape(section.description_en or '—')),
            ('IPC source', _escape(section.ipc_source or '—')),
            ('Cognizability', _escape('Cognizable' if section.cognizable is True else 'Non-cognizable' if section.cognizable is False else 'Undetermined')),
            ('Mapping', 'Officer confirmation required' if section.mapping_ambiguous else 'Mapped candidate; officer verification required'),
        ])
        if section.elements:
            lines += ['| Element | Assessment | Basis |', '| --- | --- | --- |']
            lines += [f'| {_escape(element.element)} | {_escape(element.satisfied)} | {_escape(element.justification or "—")} |' for element in section.elements]
            lines.append('')
        else:
            lines += ['Elements not analysed for this section.', '']

    occurrence = rec.occurrence
    lines += ['## 3. Occurrence and station entry', '']
    lines += _table([
        ('Occurred from', _field(occurrence.from_datetime, annotate)),
        ('Occurred to', _field(occurrence.to_datetime, annotate)),
        ('Information received at P.S.', _field(occurrence.info_received_at_ps, annotate)),
        ('General Diary reference', _field(occurrence.gd_reference, annotate)),
    ])
    lines += ['## 4. Type of information', '']
    lines += _table([('Type', _escape(rec.information_type.title() if rec.information_type else '—'))])

    place = rec.place_of_occurrence
    lines += ['## 5. Place of occurrence', '']
    lines += _table([
        ('Direction from P.S.', _field(place.direction_from_ps, annotate)),
        ('Distance from P.S. (km)', _field(place.distance_from_ps_km, annotate)),
        ('Beat number', _field(place.beat_no, annotate)),
        ('Address', _field(place.address, annotate)),
        ('Outside this P.S. limits', 'Yes' if place.outside_ps_limits else 'No'),
        ('Other P.S.', _field(place.other_ps_name, annotate)),
        ('Other district', _field(place.other_district, annotate)),
    ])

    lines += ['## 6. Complainant / informant', '']
    lines += _person(rec.complainant, annotate)
    lines += ['## 7. Accused persons', '']
    if not rec.accused:
        lines += ['No accused details entered.', '']
    for index, person in enumerate(rec.accused, 1):
        kind = 'Known' if person.known else 'Unknown' if person.unknown else 'Suspected'
        lines += [f'### Accused {index} · {kind}', '']
        lines += _table([
            ('Name', _field(person.name, annotate)),
            ('Alias', _field(person.alias, annotate)),
            ("Father's / husband's name", _field(person.relative_name, annotate)),
            ('Physical description', _field(person.physical_description, annotate)),
            ('Address', _field(person.address, annotate)),
        ])

    lines += ['## 8. Delay in reporting', '']
    lines += _table([('Reason', _field(rec.delay_reason, annotate))])
    lines += ['## 9. Property involved', '']
    if not rec.properties_involved:
        lines += ['No property details entered.', '']
    for index, item in enumerate(rec.properties_involved, 1):
        lines += [f'### Property {index}', '']
        lines += _table([
            ('Category', _field(item.category, annotate)),
            ('Description', _field(item.description, annotate)),
            ('Estimated value (INR)', _field(item.estimated_value_inr, annotate)),
        ])
    lines += ['## 10. Total property value', '']
    lines += _table([('Total value (INR)', _field(rec.total_property_value_inr, annotate))])
    lines += ['## 11. Inquest / U.D. reference', '']
    lines += _table([('Case number', _field(rec.inquest_ud_case_no, annotate))])

    lines += ['## 12. FIR contents and source account', '']
    if source_ta.strip():
        lines += [f'### {"Original-language speech transcript" if from_audio else "Source account"} · unverified', '', _escape(source_ta), '']
    if source_en.strip():
        lines += [f'### {"Direct audio-to-English output" if from_audio else "Provided English text"} · unverified', '', _escape(source_en), '']
    lines += ['### System-assembled narrative', '']
    lines += [_escape(rec.narrative.en or rec.narrative.ta or '—'), '']
    grounding = rec.narrative.grounding
    supported = sum(entry.supported for entry in grounding)
    lines += [f'System grounding annotations: {supported}/{len(grounding)} sentences marked supported. This is not a verification of the source account.', '']
    lines += ['### Cognizability · system assessment', '']
    lines += _table([
        ('Decision', _escape(rec.cognizability.decision)),
        ('Route', _escape(rec.cognizability.route)),
        ('Rationale', _escape(rec.cognizability.rationale or '—')),
        ('Schedule reference', _escape(rec.cognizability.schedule_ref or '—')),
    ])

    if rec.witnesses:
        lines += ['### Witnesses', '']
        for index, witness in enumerate(rec.witnesses, 1):
            lines += [f'#### Witness {index}', '']
            lines += _person(witness, annotate)

    lines += ['## 13. Action taken', '', '— Officer to complete.', '']
    lines += ['## 14. Complainant / informant signature or thumb impression', '', '— Pending.', '']
    lines += ['## 15. Dispatch to court', '', 'Date and time: —', '']
    lines += ['---', '', '**Draft only.** The officer remains the author of record and must verify all details before registration.', '']
    return '\n'.join(lines)
