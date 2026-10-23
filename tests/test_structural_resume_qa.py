"""Source/algorithm contracts only; these tests do not certify visual layout."""

import copy
import io
from html import escape

import pytest
from PIL import Image

from scripts.qa_modern_navy_layout import (
    STRUCTURAL_LAYOUTS, SECTION_LABELS, SemanticDocument, audit_html, coverage_errors,
    expected_field_order, expected_presentation, expected_sections, field_section,
    final_failures, fixtures, ordered_field_errors, pdf_column_streams, pdf_line_overlaps,
    source_ledger, synthetic_portrait_png, unchanged_content,
)
from tests.test_modern_navy_layout import valid_metrics


ORIGINAL_CASES = {
    'short-none', 'short-reserved', 'long-none', 'long-reserved', 'dense-none', 'dense-reserved',
    'compact-none', 'compact-reserved', 'long-embedded', 'production-reserved',
    'professional-none', 'professional-reserved', 'skills-long-raw-none',
    'skills-long-raw-reserved', 'skills-long-builder-none', 'skills-long-builder-reserved',
}


def manual_case(theme='modern-navy'):
    return {'name': 'manual-none', 'theme': theme, 'photo': 'none', 'max_pages': 1,
            'profile': {'name': 'Candidate QA', 'intent': 'Engineer', 'email': 'qa@example.invalid',
                        'phone': '0123', 'city': 'Example City',
                        'education': {'school': 'QA University', 'degree': 'MSc', 'major': 'CS',
                                      'time': '2018-2020', 'gpa': '3.8', 'awards': 'QA Award'},
                        'experience': [{'company': 'QA Company', 'role': 'Engineer', 'time': '2020-2024',
                                        'bullets': ['Ordered bullet 17.', 'Ordered bullet 23.']}],
                        'campus_experience': [{'name': 'QA Project', 'role': 'Owner', 'time': '2019',
                                               'bullets': ['Project fact 31.']}],
                        'skills': {'Tools': 'Git, Python'}}}


MANUAL_LEDGER = {
    'identity.name': 'Candidate QA', 'identity.title': 'Engineer', 'identity.phone': '0123',
    'identity.email': 'qa@example.invalid', 'identity.location': 'Example City',
    'education.school': 'QA University', 'education.degree': 'CS  MSc', 'education.time': '2018-2020',
    'education.grid.0.0': '3.8', 'education.grid.0.1': 'QA Award',
    'experience.0.org': 'QA Company', 'experience.0.role': 'Engineer', 'experience.0.time': '2020-2024',
    'experience.0.bullets.0': 'Ordered bullet 17.', 'experience.0.bullets.1': 'Ordered bullet 23.',
    'projects.0.name': 'QA Project', 'projects.0.role': 'Owner', 'projects.0.time': '2019',
    'projects.0.bullets.0': 'Project fact 31.', 'skills.0.label': 'Tools', 'skills.0.value': 'Git, Python',
}


def marked_html(case):
    """Algorithm test input, explicitly not screenshots or a production renderer."""
    theme = case['theme']
    ledger = MANUAL_LEDGER
    parts = ['<html><body><header>求职意向：']
    for key in list(ledger)[:5]:
        parts.append(f'<span data-field="{key}">{escape(ledger[key])}</span>')
    parts.append('••</header><main data-layout="' + STRUCTURAL_LAYOUTS[theme] + '">')
    sections = ['education', 'experience', 'projects', 'skills']
    if theme == 'silicon-clean':
        sections = ['education', 'experience', 'projects', 'skills']
    for section in sections:
        column = 'left' if section == 'experience' else 'right'
        if theme == 'silicon-clean' and section in ('experience', 'projects'):
            parts.append(f'<div data-column="{column}">')
        parts.append(f'<section id="{section}"><h2>{SECTION_LABELS[section]}</h2>')
        keys = [key for key in ledger if field_section(key) == section]
        if theme == 'classic-tech' and section != 'skills':
            date = next(key for key in keys if key.endswith('.time'))
            keys = [date] + [key for key in keys if key != date]
        entry = 'education' if section == 'education' else section + '.0'
        parts.append(f'<div data-entry="{entry}">')
        for key in keys:
            parts.append(f'<span data-field="{key}">{escape(ledger[key])}</span>')
        if section == 'skills':
            parts.append('：')
        parts.append('</div>')
        parts.append('</section>')
        if theme == 'silicon-clean' and section in ('experience', 'projects'):
            parts.append('</div>')
    return ''.join(parts) + '</main></body></html>'


def test_oracle_is_independent_and_has_manually_verified_exact_fields():
    case = manual_case()
    before = copy.deepcopy(case)
    assert source_ledger(case) == MANUAL_LEDGER
    assert case == before
    case['profile']['unmodeled_claim'] = 'Do not silently omit this'
    with pytest.raises(ValueError, match='independent source-ledger support'):
        source_ledger(case)


@pytest.mark.parametrize('theme', STRUCTURAL_LAYOUTS)
def test_declared_layout_changes_section_or_date_order_only(theme):
    case = manual_case(theme)
    assert audit_html(marked_html(case), case)['errors'] == []
    assert expected_field_order(MANUAL_LEDGER, theme) == [field['id'] for field in SemanticDocument(marked_html(case)).fields]


@pytest.mark.parametrize('change', ['drop', 'duplicate', 'mutate', 'unannotated', 'bullets', 'relabel', 'hide_in_photo'])
def test_source_gate_rejects_loss_invention_repetition_or_reordering(change):
    case = manual_case()
    html = marked_html(case)
    first = '<span data-field="experience.0.bullets.0">Ordered bullet 17.</span>'
    second = '<span data-field="experience.0.bullets.1">Ordered bullet 23.</span>'
    if change == 'drop':
        html = html.replace(first, '')
    elif change == 'duplicate':
        html = html.replace(first, first + first)
    elif change == 'mutate':
        html = html.replace('Ordered bullet 17.', 'Ordered bullet 71.')
    elif change == 'unannotated':
        html = html.replace('</main>', '<p>Invented fact 99.</p></main>')
    elif change == 'bullets':
        html = html.replace(first + second, second + first)
    elif change == 'relabel':
        html = html.replace('data-field="experience.0.bullets.0"', 'data-field="experience.0.bullets.9"')
    else:
        html = html.replace(first, '').replace('</header>', f'<div class="photo-placeholder" hidden>{first}</div></header>')
    assert audit_html(html, case)['errors']


def test_duplicate_values_still_require_each_source_occurrence():
    case = manual_case()
    html = marked_html(case)
    assert sum(value == 'Engineer' for value in source_ledger(case).values()) == 2
    html = html.replace('<span data-field="experience.0.role">Engineer</span>', '')
    assert audit_html(html, case)['errors']
    assert coverage_errors('Engineer', {'a': 'Engineer', 'b': 'Engineer'}, '')


def test_wrong_column_is_rejected_even_with_complete_text():
    case = manual_case('silicon-clean')
    html = marked_html(case).replace('data-column="left"', 'data-column="right"', 1)
    assert any('wrong column' in error for error in audit_html(html, case)['errors'])


def test_legacy_equality_remains_strict_and_photo_normalization_is_narrow():
    before = '<body>Source fact 17.<div class="photo-placeholder">预留证件照<br>一寸 / 二寸</div>Second fact.</body>'
    after = '<body>Source fact 17.<div class="photo-placeholder"><img src="data:image/png;base64,x"></div>Second fact.</body>'
    assert unchanged_content(before, after, 'modern-corporate')
    assert not unchanged_content(before, after.replace('17', '71'), 'modern-corporate')
    assert not unchanged_content(before, '<body>Second fact.Source fact 17.</body>', 'modern-corporate')
    assert not unchanged_content(before, after.replace('</div>', 'Hidden invented fact</div>'), 'modern-corporate')
    hidden = '<body><div class="photo-placeholder" hidden>Source fact 17.</div>Second fact.</body>'
    assert not unchanged_content(hidden, '<body>Second fact.</body>', 'modern-corporate')


def test_no_photo_rejects_image_uri_without_an_img_tag():
    case = manual_case()
    html = marked_html(case).replace('<main ', '<main style="background:url(data:image/png;base64,x)" ')
    assert any('URI' in error for error in audit_html(html, case)['errors'])


def test_all_original_cases_remain_and_portrait_pairs_share_exact_sources():
    for theme in ['modern-navy', 'classic-tech', 'silicon-clean', 'modern-corporate', 'academic-postgraduate']:
        cases = {case['name']: case for case in fixtures(theme)}
        assert ORIGINAL_CASES <= cases.keys()
        for case in cases.values():
            if case['photo'] == 'none' and not case.get('source_photo'):
                counterpart = cases[case['name'].removesuffix('-none') + '-embedded']
                assert counterpart['profile'] == case['profile']
                assert counterpart['mode'] == case['mode']
        for mode in ('raw', 'builder'):
            case = cases[f'source-photo-{mode}-none']
            assert case['source_photo'] and case['photo_data_uri'].startswith('data:image/png;base64,')
        assert all(source_ledger(case) for case in cases.values())


def test_portrait_is_deterministic_nonuniform_and_three_to_four():
    first = synthetic_portrait_png()
    assert first == synthetic_portrait_png()
    with Image.open(io.BytesIO(first)) as image:
        assert image.size == (120, 160)
        assert len(image.getcolors()) > 3
        assert image.getpixel((3, 3)) == (194, 82, 82)


def glyph_line(text, page, x, y):
    return {'page': page, 'pageWidth': 600, 'bbox': (x, y, x + len(text) * 4, y + 10),
            'text': text, 'chars': [{'c': char, 'bbox': (x + i * 4, y, x + i * 4 + 3, y + 10)} for i, char in enumerate(text)]}


def test_pdf_reading_is_column_aware_across_continuation_pages():
    geometry = {'pageWidth': 600, 'headerBottom': 50, 'printPaddingMm': 0,
                'columns': [{'name': 'left', 'left': 30, 'right': 270}, {'name': 'right', 'left': 320, 'right': 570}]}
    lines = [glyph_line('Name', 1, 30, 20), glyph_line('实习经历', 1, 30, 65), glyph_line('校园与实践经历', 1, 320, 65), glyph_line('Left one', 1, 30, 80),
             glyph_line('Right one', 1, 320, 80), glyph_line('Left two', 2, 30, 40),
             glyph_line('Right two', 2, 320, 40), glyph_line('专业技能', 2, 30, 90), glyph_line('Skills', 2, 30, 105)]
    streams, errors = pdf_column_streams(lines, geometry)
    assert errors == []
    assert streams == {'opening': 'Name', 'left': '实习经历LeftoneLefttwo', 'right': '校园与实践经历RightoneRighttwo', 'ending': '专业技能Skills'}
    ledger = {'one': 'Left one', 'two': 'Left two'}
    assert ordered_field_errors(streams['left'], ['one', 'two'], ledger) == []
    assert ordered_field_errors('Left two Left one', ['one', 'two'], ledger)
    assert pdf_column_streams(lines, {})[1]
    assert pdf_column_streams(lines + [glyph_line('Lost', 2, 290, 60)], geometry)[1]


def test_pdf_collisions_cannot_be_hidden_by_dom_geometry():
    first = glyph_line('First text', 1, 30, 40)
    assert not pdf_line_overlaps([first, glyph_line('Next text', 1, 30, 60)])
    assert pdf_line_overlaps([first, glyph_line('Bad overlap', 1, 30, 42)])
    assert not pdf_line_overlaps([first, glyph_line('Other page', 2, 30, 40)])


@pytest.mark.parametrize('regression', ['source', 'pdf_source', 'pdf_overlap', 'pdf_column', 'hidden', 'photo_slot', 'photo_image', 'photo_padding'])
def test_new_failures_are_wired_into_final_gate(regression):
    metrics = valid_metrics()
    case = {'name': 'manual-none', 'photo': 'none', 'max_pages': 1}
    if regression == 'source':
        metrics['sourceAudit'] = {'errors': ['missing field']}
    elif regression == 'pdf_source':
        metrics['pdf']['sourceErrors'] = ['duplicate claim']
    elif regression == 'pdf_overlap':
        metrics['pdf']['overlaps'] = [{}]
    elif regression == 'pdf_column':
        metrics['pdf']['columnErrors'] = ['ambiguous glyph']
    elif regression == 'hidden':
        metrics['screen']['fields'] = [{'id': 'identity.name', 'text': 'Name', 'visible': False}]
    else:
        metrics['screen'].update({'photoSlots': 0, 'identityPaddingRight': 0})
        if regression == 'photo_slot':
            metrics['screen']['photoSlots'] = 1
        elif regression == 'photo_image':
            metrics['screen']['images'] = [{'complete': True, 'width': 120}]
        else:
            metrics['screen']['identityPaddingRight'] = 12
    assert final_failures(metrics, case)


def test_entry_reordering_is_rejected_even_when_every_fact_and_count_matches():
    case = manual_case()
    second = {'company': 'Second Company', 'role': 'Researcher', 'time': '2017-2018',
              'bullets': ['Second entry fact 43.']}
    case['profile']['experience'].append(second)
    html = marked_html(manual_case())
    first_start = html.index('<div data-entry="experience.0">')
    first_end = html.index('</div>', first_start) + len('</div>')
    original_entry = html[first_start:first_end]
    second_entry = '<div data-entry="experience.1">' + ''.join(
        f'<span data-field="experience.1.{key}">{text}</span>' for key, text in (
            ('org', 'Second Company'), ('role', 'Researcher'), ('time', '2017-2018'),
            ('bullets.0', 'Second entry fact 43.'))) + '</div>'
    correct = html[:first_end] + second_entry + html[first_end:]
    assert audit_html(correct, case)['errors'] == []
    swapped = correct.replace(original_entry + second_entry, second_entry + original_entry)
    assert any('order' in error for error in audit_html(swapped, case)['errors'])


def test_embedded_portrait_cannot_be_replaced_by_placeholder_or_another_image():
    case = manual_case()
    case.update(photo='embedded', photo_data_uri='data:image/png;base64,expected')
    photo = '<div class="photo-placeholder"><img src="data:image/png;base64,expected"></div>'
    html = marked_html(case).replace('</header>', photo + '</header>')
    assert audit_html(html, case)['errors'] == []
    assert audit_html(html.replace(photo, '<div class="photo-placeholder">预留证件照<br>一寸 / 二寸</div>'), case)['errors']
    assert audit_html(html.replace('base64,expected', 'base64,another-image'), case)['errors']


def test_structural_gate_fails_closed_when_either_source_audit_is_missing():
    case = manual_case()
    metrics = valid_metrics()
    assert 'source ledger audit was not run' in final_failures(metrics, case)
    metrics['sourceAudit'] = {'errors': []}
    assert 'PDF source ledger audit was not run' in final_failures(metrics, case)


@pytest.mark.parametrize('regression', ['hidden', 'zero', 'crop', 'frame', 'print_only'])
def test_embedded_portrait_geometry_is_enforced_in_screen_and_print(regression):
    metrics = valid_metrics()
    image = {'complete': True, 'width': 120, 'height': 160, 'displayWidth': 72,
             'displayHeight': 96, 'objectFit': 'contain', 'visible': True, 'contained': True}
    metrics['screen']['images'] = [copy.deepcopy(image)]
    metrics['print']['images'] = [copy.deepcopy(image)]
    case = {'name': 'portrait-embedded', 'photo': 'embedded', 'max_pages': 1}
    assert final_failures(metrics, case) == []
    target = metrics['print' if regression == 'print_only' else 'screen']['images'][0]
    if regression in ('hidden', 'print_only'):
        target['visible'] = False
    elif regression == 'zero':
        target['displayHeight'] = 0
    elif regression == 'crop':
        target.update(displayWidth=96, objectFit='cover')
    else:
        target['contained'] = False
    assert final_failures(metrics, case)


@pytest.mark.parametrize('theme', STRUCTURAL_LAYOUTS)
def test_pilot_generator_modes_preserve_source_ledger(theme):
    """Real source integration only; this never launches or substitutes a browser."""
    from scripts.qa_modern_navy_layout import ROOT, render_html
    # One source per generator mode and photo mode. The browser QA owns the
    # full density matrix; shared field/photo contracts have their own tests.
    cases = {case['name']: case for case in fixtures(theme)}
    for name in ('all-fields-none', 'dense-reserved', 'compact-embedded'):
        case = cases[name]
        audit = audit_html(render_html(ROOT, case), case)
        assert audit['errors'] == [], (case['name'], audit['errors'])
